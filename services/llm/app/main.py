"""CodeOrigin llm service: Ollama client with token accounting, a judge
endpoint, and a deterministic MOCK_LLM mode so CI never needs a GPU."""
import json
import os
import re
import time
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="CodeOrigin llm", version="0.1.0")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://codeorigin-ollama:11434")
DEFAULT_MODEL = os.getenv("LLM_MODEL", "llama2")
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "gemma:2b")
TIMEOUT = float(os.getenv("LLM_TIMEOUT_SECONDS", "300"))


def mock_enabled() -> bool:
    return os.getenv("MOCK_LLM", "0") == "1"


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1)
    system: Optional[str] = None
    model: Optional[str] = None
    temperature: float = 0.0
    seed: int = 42
    max_tokens: int = Field(default=400, ge=1, le=4096)


class JudgeRequest(BaseModel):
    question: str
    answer: str
    gold_answer: str
    evidence: Optional[str] = None
    model: Optional[str] = None


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


# ---------------------------------------------------------------- mock mode
_EVIDENCE_REF = re.compile(r'<evidence ref="([^"]+)"[^>]*>(.*?)</evidence>', re.S)


def mock_generate(prompt: str) -> str:
    """Deterministic stand-in: answers from the first evidence block, citing it.
    With no evidence it answers from nothing, like a baseline model would."""
    blocks = _EVIDENCE_REF.findall(prompt)
    if not blocks:
        return "I do not have enough information to say why this was done."
    ref, body = blocks[0]
    first = re.split(r"(?<=[.!?])\s+|\n", body.strip())[0][:240]
    return f"According to the repository evidence, {first} [{ref}]"


def mock_judge(req: JudgeRequest) -> dict:
    gold = set(re.findall(r"[a-z0-9]{4,}", req.gold_answer.lower()))
    ans = set(re.findall(r"[a-z0-9]{4,}", req.answer.lower()))
    overlap = len(gold & ans) / len(gold) if gold else 0.0
    return {
        "correctness": 2 if overlap >= 0.6 else 1 if overlap >= 0.25 else 0,
        "completeness": 2 if overlap >= 0.8 else 1 if overlap >= 0.4 else 0,
        "hallucination": False,
        "rationale": f"mock judge: lexical overlap {overlap:.2f}",
    }


# -------------------------------------------------------------------- ollama
def _ollama_generate(model: str, prompt: str, system, temperature: float, seed: int, max_tokens: int, fmt=None):
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature, "seed": seed, "num_predict": max_tokens},
    }
    num_ctx = int(os.getenv("OLLAMA_NUM_CTX", "0"))
    if num_ctx:  # identical for every mode; a smaller window lets a 7B model fit a 6 GB GPU
        payload["options"]["num_ctx"] = num_ctx
    if system:
        payload["system"] = system
    if fmt:
        payload["format"] = fmt
    try:
        r = httpx.post(f"{OLLAMA_HOST}/api/generate", json=payload, timeout=TIMEOUT)
        r.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"ollama error {exc.response.status_code}: {exc.response.text[:200]}")
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"ollama unreachable: {exc}")
    return r.json()


def parse_json_loose(text: str):
    """First JSON object in `text`, or None."""
    if not text:
        return None
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            depth += text[i] == "{"
            depth -= text[i] == "}"
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    break
        start = text.find("{", start + 1)
    return None


@app.get("/health")
def health():
    if mock_enabled():
        return {"status": "ok", "mock": True}
    try:
        httpx.get(f"{OLLAMA_HOST}/api/tags", timeout=5).raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"ollama unreachable: {exc}")
    return {"status": "ok", "mock": False}


@app.get("/models")
def models():
    if mock_enabled():
        return {"models": [DEFAULT_MODEL, "codellama:7b", "starcoder2:3b", JUDGE_MODEL], "mock": True}
    try:
        r = httpx.get(f"{OLLAMA_HOST}/api/tags", timeout=10)
        r.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"ollama unreachable: {exc}")
    return {"models": [m["name"] for m in r.json().get("models", [])], "mock": False}


@app.post("/generate")
def generate(req: GenerateRequest):
    model = req.model or DEFAULT_MODEL
    t0 = time.perf_counter()
    if mock_enabled():
        text = mock_generate(req.prompt)
        tin, tout = _approx_tokens(req.prompt + (req.system or "")), _approx_tokens(text)
    else:
        data = _ollama_generate(model, req.prompt, req.system, req.temperature, req.seed, req.max_tokens)
        text = data.get("response", "").strip()
        tin = data.get("prompt_eval_count") or _approx_tokens(req.prompt)
        tout = data.get("eval_count") or _approx_tokens(text)
    return {
        "model": model,
        "text": text,
        "tokens_in": tin,
        "tokens_out": tout,
        "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
        "mock": mock_enabled(),
    }


JUDGE_PROMPT = """You are grading an answer about a software repository's history.
Question: {question}
Reference (gold) answer: {gold}
Candidate answer: {answer}
{evidence}
Score the candidate against the reference. Reply with ONLY a JSON object:
{{"correctness": 0|1|2, "completeness": 0|1|2, "hallucination": true|false, "rationale": "<one sentence>"}}
correctness: 2 = matches the reference, 1 = partly, 0 = wrong or unrelated.
hallucination: true if the candidate states specifics that the reference/evidence does not support."""


@app.post("/judge")
def judge(req: JudgeRequest):
    model = req.model or JUDGE_MODEL
    t0 = time.perf_counter()
    if mock_enabled():
        parsed, raw = mock_judge(req), "mock"
    else:
        ev = f"Evidence available to the candidate:\n{req.evidence[:1500]}" if req.evidence else ""
        prompt = JUDGE_PROMPT.format(question=req.question, gold=req.gold_answer, answer=req.answer, evidence=ev)
        data = _ollama_generate(model, prompt, None, 0.0, 42, 200, fmt="json")
        raw = data.get("response", "")
        parsed = parse_json_loose(raw)
        if parsed is not None:
            try:
                parsed = {
                    "correctness": max(0, min(2, int(parsed.get("correctness", 0)))),
                    "completeness": max(0, min(2, int(parsed.get("completeness", 0)))),
                    "hallucination": bool(parsed.get("hallucination", False)),
                    "rationale": str(parsed.get("rationale", ""))[:300],
                }
            except (TypeError, ValueError):
                parsed = None
    return {
        "model": model,
        "parsed": parsed,
        "raw": raw if parsed is None else None,
        "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
    }
