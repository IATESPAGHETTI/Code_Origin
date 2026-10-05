import httpx
import pytest
from fastapi.testclient import TestClient

from app import main


class FakeHTTP:
    """Records forwarded requests and answers from a route table."""

    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def request(self, method, url, headers=None, json=None, content=None, **kw):
        self.calls.append({"method": method, "url": url, "headers": headers or {}, "json": json, "content": content})
        for (m, suffix), (status, body) in self.routes.items():
            if m == method and url.endswith(suffix):
                return httpx.Response(status, json=body, request=httpx.Request(method, url))
        return httpx.Response(404, json={"detail": "nf"}, request=httpx.Request(method, url))

    def get(self, url, timeout=None):
        return httpx.Response(200, json={}, request=httpx.Request("GET", url))


ASK_OK = {"mode": "code_history", "refused": True, "refusal_type": "off_topic", "tokens": {"in": 5, "out": 7},
          "guardrails": [{"id": "G1", "triggered": True, "action": "refused"}], "answer": "no"}


@pytest.fixture()
def gw(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.setenv("ALLOW_LOCAL_REPOS", "0")
    main.limiter._hits.clear()
    fake = FakeHTTP({("POST", "/ask"): (200, ASK_OK), ("POST", "/repos"): (202, {"repo_id": "o__r", "job_id": 1}),
                     ("GET", "/repos"): (200, {"repos": []}), ("POST", "/webhooks/github"): (200, {"ok": True}),
                     ("POST", "/expand"): (200, {"chunks": [{"ref": "commit:abc1234"}]}),
                     ("GET", "/runs/1/report"): (200, {"x": 1}),
                     ("GET", "/runs/1/results?with_response=false"): (200, {"results": [{"item_id": "a"}]})})
    main._http["c"] = fake
    return TestClient(main.app), fake


def test_health_and_request_id_header(gw):
    client, _ = gw
    r = client.get("/health", headers={"x-request-id": "abc"})
    assert r.json() == {"status": "ok"} and r.headers["x-request-id"] == "abc"
    assert client.get("/health").headers["x-request-id"]


def test_request_id_is_forwarded_downstream(gw):
    client, fake = gw
    client.get("/api/repos", headers={"x-request-id": "trace-1"})
    assert fake.calls[-1]["headers"]["x-request-id"] == "trace-1"


@pytest.mark.parametrize("src,ok", [
    ("https://github.com/owner/repo", True), ("owner/repo", True), ("https://github.com/owner/repo.git", True),
    ("https://gitlab.com/o/r", False), ("/etc/passwd", False), ("C:\\Users\\me\\repo", False),
    ("file:///etc/passwd", False), ("git@github.com:o/r.git", False), ("../../etc", False),
])
def test_repo_source_allow_list_g7(gw, src, ok):
    client, _ = gw
    r = client.post("/api/repos", json={"source": src})
    assert (r.status_code == 202) is ok, r.text


def test_local_paths_allowed_only_when_enabled(gw, monkeypatch):
    client, _ = gw
    monkeypatch.setenv("ALLOW_LOCAL_REPOS", "1")
    assert client.post("/api/repos", json={"source": "/demo-repo"}).status_code == 202


def test_issues_file_is_blocked_in_production_mode(gw):
    client, _ = gw
    assert client.post("/api/repos", json={"source": "o/r", "issues_file": "/etc/passwd"}).status_code == 400


def test_question_length_and_mode_limits(gw):
    client, _ = gw
    assert client.post("/api/ask", json={"repo": "r", "question": "x" * 1001}).status_code == 422
    assert client.post("/api/ask", json={"repo": "r", "question": "Why?", "mode": "oracle"}).status_code == 422
    assert client.post("/api/ask", json={"repo": "r", "question": "Why JWT here?"}).status_code == 200


def test_ask_updates_guardrail_metrics(gw):
    client, _ = gw
    client.post("/api/ask", json={"repo": "r", "question": "weather in paris?"})
    text = client.get("/metrics").text
    assert 'codeorigin_guardrail_triggers_total{action="refused",guardrail="G1"}' in text
    assert 'codeorigin_refusals_total{type="off_topic"}' in text
    assert 'codeorigin_llm_tokens_total{direction="out",mode="code_history"}' in text


def test_rate_limit_per_client(gw, monkeypatch):
    client, _ = gw
    monkeypatch.setenv("RATE_LIMIT_ASK_PER_MIN", "2")
    codes = [client.post("/api/ask", json={"repo": "r", "question": "Why JWT here?"}).status_code for _ in range(4)]
    assert codes == [200, 200, 429, 429]
    assert client.post("/api/ask", json={"repo": "r", "question": "Why JWT here?"}).headers["retry-after"]


def test_sliding_window_expires():
    w = main.SlidingWindow()
    assert w.allow("k", 1, now=0)[0] and not w.allow("k", 1, now=10)[0] and w.allow("k", 1, now=61)[0]


def test_api_key_required_when_configured(gw, monkeypatch):
    client, _ = gw
    monkeypatch.setenv("API_KEY", "k1")
    assert client.get("/api/repos").status_code == 401
    assert client.get("/api/repos", headers={"x-api-key": "k1"}).status_code == 200
    assert client.get("/health").status_code == 200


def test_webhook_forwards_raw_body_and_signature_not_api_key(gw, monkeypatch):
    client, fake = gw
    monkeypatch.setenv("API_KEY", "k1")
    r = client.post("/api/webhooks/github", content=b'{"a":1}', headers={"x-hub-signature-256": "sha256=abc", "x-github-event": "push"})
    assert r.status_code == 200
    call = fake.calls[-1]
    assert call["content"] == b'{"a":1}' and call["headers"]["x-hub-signature-256"] == "sha256=abc"


def test_downstream_error_status_is_propagated(gw):
    client, _ = gw
    assert client.get("/api/jobs/5").status_code == 404


def test_evidence_lookup_and_404(gw):
    client, fake = gw
    assert client.get("/api/evidence/o__r/commit:abc1234").json()["chunks"][0]["ref"] == "commit:abc1234"
    fake.routes[("POST", "/expand")] = (200, {"chunks": []})
    assert client.get("/api/evidence/o__r/issue:%2399").status_code == 404


def test_downstream_down_gives_503(gw):
    client, fake = gw

    def boom(*a, **k):
        raise httpx.ConnectError("refused")

    fake.request = boom
    assert client.get("/api/repos").status_code == 503


def test_ask_stream_proxies_events_and_records_metrics(gw, monkeypatch):
    import json as _json
    client, _ = gw
    result = {"mode": "code_history", "refused": False, "tokens": {"in": 11, "out": 3},
              "guardrails": [{"id": "G5", "triggered": True, "action": "neutralised"}], "answer": "ok"}
    events = [{"type": "stage", "stage": "retrieve", "status": "done", "detail": {}}, {"type": "result", "result": result}]
    body = "".join("data: " + _json.dumps(e) + "\n\n" for e in events)

    class FakeStream:
        status_code = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def iter_text(self):
            yield body[:20]          # split mid-event on purpose: the gateway must reassemble before parsing
            yield body[20:]

    monkeypatch.setattr(main.httpx, "stream", lambda *a, **k: FakeStream())
    r = client.post("/api/ask/stream", json={"repo": "r", "question": "Why JWT here?"})
    assert r.headers["content-type"].startswith("text/event-stream") and r.text == body
    metrics = client.get("/metrics").text
    assert 'codeorigin_guardrail_triggers_total{action="neutralised",guardrail="G5"}' in metrics


def test_ask_stream_validates_like_ask(gw):
    client, _ = gw
    assert client.post("/api/ask/stream", json={"repo": "r", "question": "x" * 1001}).status_code == 422
    assert client.post("/api/ask/stream", json={"repo": "r", "question": "Why?", "mode": "oracle"}).status_code == 422


def test_ask_stream_downstream_down_is_an_error_event(gw, monkeypatch):
    client, _ = gw

    def boom(*a, **k):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(main.httpx, "stream", boom)
    r = client.post("/api/ask/stream", json={"repo": "r", "question": "Why JWT here?"})
    assert '"type": "error"' in r.text and "503" in r.text


def test_eval_results_are_proxied_for_live_progress(gw):
    client, _ = gw
    assert client.get("/api/eval/runs/1/results").json() == {"results": [{"item_id": "a"}]}
