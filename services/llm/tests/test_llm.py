import httpx
import pytest
from fastapi.testclient import TestClient

from app import main


@pytest.fixture()
def mock_client(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "1")
    return TestClient(main.app)


def test_mock_generate_cites_first_evidence(mock_client):
    prompt = '<evidence ref="commit:abc1234" type="commit">Switched to JWT after the session bug. More text.</evidence>\nQ?'
    r = mock_client.post("/generate", json={"prompt": prompt, "model": "llama2"}).json()
    assert "[commit:abc1234]" in r["text"] and r["mock"] is True
    assert r["tokens_in"] > 0 and r["tokens_out"] > 0


def test_mock_generate_without_evidence_has_no_citation(mock_client):
    r = mock_client.post("/generate", json={"prompt": "Why JWT?"}).json()
    assert "[" not in r["text"]


def test_mock_judge_scores_by_overlap(mock_client):
    ok = mock_client.post("/judge", json={"question": "q", "answer": "switched to jwt because sessions leaked",
                                          "gold_answer": "switched to jwt because sessions leaked"}).json()
    bad = mock_client.post("/judge", json={"question": "q", "answer": "unrelated words entirely",
                                           "gold_answer": "switched to jwt because sessions leaked"}).json()
    assert ok["parsed"]["correctness"] == 2 and bad["parsed"]["correctness"] == 0


def test_health_and_models_in_mock(mock_client):
    assert mock_client.get("/health").json()["mock"] is True
    assert "llama2" in mock_client.get("/models").json()["models"]


@pytest.mark.parametrize(
    "text,expected",
    [
        ('{"correctness": 2}', {"correctness": 2}),
        ('Sure! Here: {"a": {"b": 1}, "c": 2} thanks', {"a": {"b": 1}, "c": 2}),
        ("no json here", None),
        ("{broken", None),
    ],
)
def test_parse_json_loose(text, expected):
    assert main.parse_json_loose(text) == expected


def test_real_path_calls_ollama_and_reports_tokens(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "0")

    def fake_post(url, json=None, timeout=None):
        assert url.endswith("/api/generate") and json["options"]["temperature"] == 0.0
        return httpx.Response(200, json={"response": " hi ", "prompt_eval_count": 11, "eval_count": 3},
                              request=httpx.Request("POST", url))

    monkeypatch.setattr(main.httpx, "post", fake_post)
    r = TestClient(main.app).post("/generate", json={"prompt": "x", "model": "codellama:7b"}).json()
    assert r["text"] == "hi" and r["tokens_in"] == 11 and r["tokens_out"] == 3 and r["model"] == "codellama:7b"


def test_judge_real_path_parses_and_clamps(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "0")

    def fake_post(url, json=None, timeout=None):
        return httpx.Response(200, json={"response": '{"correctness": 5, "completeness": 1, "hallucination": true, "rationale": "r"}'},
                              request=httpx.Request("POST", url))

    monkeypatch.setattr(main.httpx, "post", fake_post)
    r = TestClient(main.app).post("/judge", json={"question": "q", "answer": "a", "gold_answer": "g"}).json()
    assert r["parsed"] == {"correctness": 2, "completeness": 1, "hallucination": True, "rationale": "r"}


def test_judge_unparseable_returns_raw(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "0")
    monkeypatch.setattr(main.httpx, "post", lambda url, json=None, timeout=None: httpx.Response(
        200, json={"response": "I think it is fine"}, request=httpx.Request("POST", url)))
    r = TestClient(main.app).post("/judge", json={"question": "q", "answer": "a", "gold_answer": "g"}).json()
    assert r["parsed"] is None and r["raw"] == "I think it is fine"


def test_ollama_down_gives_503(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "0")

    def boom(*a, **k):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(main.httpx, "post", boom)
    assert TestClient(main.app).post("/generate", json={"prompt": "x"}).status_code == 503
