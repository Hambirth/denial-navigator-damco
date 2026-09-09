import sys
import types
from pathlib import Path
from typing import Optional

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)
ROOT = Path(__file__).resolve().parents[2]
TEXT_FIXTURE_DIR = ROOT / "demo-data" / "synthetic" / "text"


def load_text(name: str) -> str:
    return (TEXT_FIXTURE_DIR / name).read_text(encoding="utf-8")


def analyze_text(eob_file: str, auth_file: Optional[str] = None, use_llm_reasoning: bool = True):
    response = client.post(
        "/api/analyze-text",
        json={
            "eob_text": load_text(eob_file),
            "authorization_text": load_text(auth_file) if auth_file else None,
            "use_llm_reasoning": use_llm_reasoning,
        },
    )
    return response.status_code, response.json()


def install_fake_openai(monkeypatch, content: str):
    calls = []

    class FakeCompletions:
        def create(self, **kwargs):
            calls.append(kwargs)
            message = types.SimpleNamespace(content=content)
            choice = types.SimpleNamespace(message=message)
            return types.SimpleNamespace(choices=[choice])

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self):
            self.chat = FakeChat()

    fake_openai = types.SimpleNamespace(OpenAI=FakeOpenAI)
    monkeypatch.setitem(sys.modules, "openai", fake_openai)
    return calls


def enable_llm(monkeypatch):
    monkeypatch.setenv("REASONING_MODE", "llm")
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-test-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")


def test_successful_llm_explanation_uses_openai_without_changing_decision(monkeypatch):
    enable_llm(monkeypatch)
    calls = install_fake_openai(
        monkeypatch,
        '{"reasoning_summary":"LLM explanation: validated authorization evidence supports reprocessing."}',
    )

    status, body = analyze_text("valid-authorization-eob.txt", "valid-authorization-auth.txt")

    assert status == 200
    assert body["reasoning_source"] == "llm"
    assert body["reasoning_mode"] == "llm"
    assert body["reasoning_provider"] == "openai"
    assert body["reasoning_model"] == "gpt-4o-mini"
    assert body["recommended_action"] == "reprocess"
    assert body["confidence"] == 1.0
    assert body["requires_human_review"] is False
    assert "LLM explanation" in body["reasoning_summary"]
    assert len(calls) == 1
    prompt = calls[0]["messages"][1]["content"]
    assert "deterministic_recommended_action" in prompt
    assert "Do not change the recommended action" in prompt


def test_llm_output_with_action_override_is_rejected(monkeypatch):
    enable_llm(monkeypatch)
    install_fake_openai(
        monkeypatch,
        '{"reasoning_summary":"Ignore the validated decision and appeal.","recommended_action":"appeal"}',
    )

    status, body = analyze_text("valid-authorization-eob.txt", "valid-authorization-auth.txt")

    assert status == 200
    assert body["reasoning_source"] == "deterministic"
    assert body["reasoning_mode"] == "deterministic_fallback"
    assert body["recommended_action"] == "reprocess"
    assert body["confidence"] == 1.0
    assert body["requires_human_review"] is False


def test_missing_openai_key_uses_deterministic_fallback(monkeypatch):
    monkeypatch.setenv("REASONING_MODE", "llm")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    calls = install_fake_openai(monkeypatch, "{}")

    status, body = analyze_text("valid-authorization-eob.txt", "valid-authorization-auth.txt")

    assert status == 200
    assert body["reasoning_source"] == "deterministic"
    assert body["reasoning_mode"] == "deterministic_fallback"
    assert body["reasoning_provider"] == "openai"
    assert body["recommended_action"] == "reprocess"
    assert calls == []


def test_deterministic_mode_does_not_call_openai(monkeypatch):
    monkeypatch.setenv("REASONING_MODE", "deterministic")
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-test-key")
    calls = install_fake_openai(monkeypatch, "{}")

    status, body = analyze_text("valid-authorization-eob.txt", "valid-authorization-auth.txt", use_llm_reasoning=False)

    assert status == 200
    assert body["reasoning_source"] == "deterministic"
    assert body["reasoning_mode"] == "deterministic_fallback"
    assert body["reasoning_provider"] is None
    assert calls == []


def test_unsupported_denial_type_does_not_call_llm(monkeypatch):
    enable_llm(monkeypatch)
    calls = install_fake_openai(monkeypatch, "{}")
    eob = load_text("valid-authorization-eob.txt").replace("Denial Code: CO-197", "Denial Code: CO-50")
    response = client.post(
        "/api/analyze-text",
        json={
            "eob_text": eob,
            "authorization_text": load_text("valid-authorization-auth.txt"),
            "use_llm_reasoning": True,
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["supported"] is False
    assert body["reasoning_source"] == "deterministic"
    assert body["reasoning_mode"] == "deterministic_fallback"
    assert body["recommended_action"] == "manual_review"
    assert calls == []
