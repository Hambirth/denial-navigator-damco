from pathlib import Path
from typing import Optional

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)
ROOT = Path(__file__).resolve().parents[2]
TEXT_FIXTURE_DIR = ROOT / "demo-data" / "synthetic" / "text"


def load_text(name: str) -> str:
    return (TEXT_FIXTURE_DIR / name).read_text(encoding="utf-8")


def analyze_text(eob_file: str, auth_file: Optional[str] = None, use_llm_reasoning: bool = False):
    payload = {
        "eob_text": load_text(eob_file),
        "authorization_text": load_text(auth_file) if auth_file else None,
        "use_llm_reasoning": use_llm_reasoning,
    }
    response = client.post("/api/analyze-text", json=payload)
    return response.status_code, response.json()


def test_text_valid_auth_matching_dos_routes_to_reprocess():
    status, body = analyze_text("valid-authorization-eob.txt", "valid-authorization-auth.txt")
    assert status == 200
    assert body["recommended_action"] == "reprocess"
    assert body["requires_human_review"] is False
    assert body["reasoning_source"] == "deterministic"
    assert body["extracted_evidence"]["extracted_claim"]["claim_id"] == "DEMO-CLM-001"
    assert body["extracted_evidence"]["extracted_authorization"]["authorization_number"] == "AUTH-DEMO-001"


def test_text_auth_exists_but_dos_outside_range_records_contradiction():
    status, body = analyze_text("dos-mismatch-eob.txt", "dos-mismatch-auth.txt")
    assert status == 200
    assert body["recommended_action"] == "manual_review"
    assert body["requires_human_review"] is True
    assert any(item["field"] == "date_of_service" for item in body["contradictions"])
    assert any(item["type"] == "authorization_date_range" and item["status"] == "mismatched" for item in body["evidence"])


def test_text_missing_authorization_does_not_hallucinate_reprocess():
    status, body = analyze_text("missing-authorization-eob.txt")
    assert status == 200
    assert body["recommended_action"] == "manual_review"
    assert body["requires_human_review"] is True
    assert body["confidence"] <= 0.3
    assert body["extracted_evidence"]["authorization"] is None
    assert "authorization number" in body["missing_evidence"]


def test_text_deterministic_cpt_mismatch_routes_to_corrected_claim():
    status, body = analyze_text("cpt-mismatch-eob.txt", "cpt-mismatch-auth.txt")
    assert status == 200
    assert body["recommended_action"] == "corrected_claim"
    assert any(item["field"] == "cpt_code" for item in body["contradictions"])
    assert any(item["type"] == "cpt_code" and item["status"] == "mismatched" for item in body["evidence"])


def test_text_deterministic_payer_mismatch_routes_to_manual_review():
    status, body = analyze_text("payer-mismatch-eob.txt", "payer-mismatch-auth.txt")
    assert status == 200
    assert body["recommended_action"] == "manual_review"
    assert any(item["field"] == "payer" for item in body["contradictions"])


def test_text_malformed_date_returns_422():
    eob = load_text("valid-authorization-eob.txt").replace("Date of Service: 2026-01-15", "Date of Service: January 15")
    response = client.post(
        "/api/analyze-text",
        json={"eob_text": eob, "authorization_text": load_text("valid-authorization-auth.txt")},
    )
    assert response.status_code == 422
    assert "date_of_service" in response.json()["detail"]


def test_text_missing_required_claim_field_returns_422():
    eob = load_text("valid-authorization-eob.txt").replace("Member ID: DEMO-MEMBER-001\n", "")
    response = client.post(
        "/api/analyze-text",
        json={"eob_text": eob, "authorization_text": load_text("valid-authorization-auth.txt")},
    )
    assert response.status_code == 422
    assert "member_id" in response.json()["detail"]


def test_llm_summary_cannot_change_deterministic_action(monkeypatch):
    from app.services import reasoning_service

    monkeypatch.setenv("REASONING_MODE", "llm")
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-test-key")
    monkeypatch.setattr(
        reasoning_service,
        "_generate_llm_summary",
        lambda _decision: "LLM summary only; deterministic fields remain authoritative.",
    )

    status, body = analyze_text("dos-mismatch-eob.txt", "dos-mismatch-auth.txt", use_llm_reasoning=True)
    assert status == 200
    assert body["reasoning_source"] == "llm"
    assert body["recommended_action"] == "manual_review"
    assert any(item["field"] == "date_of_service" for item in body["contradictions"])


def test_llm_failure_falls_back_to_deterministic_reasoning(monkeypatch):
    from app.services import reasoning_service

    monkeypatch.setenv("REASONING_MODE", "llm")
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-test-key")

    def fail(_decision):
        raise RuntimeError("synthetic LLM failure")

    monkeypatch.setattr(reasoning_service, "_generate_llm_summary", fail)
    status, body = analyze_text("valid-authorization-eob.txt", "valid-authorization-auth.txt", use_llm_reasoning=True)
    assert status == 200
    assert body["reasoning_source"] == "deterministic"
    assert body["recommended_action"] == "reprocess"
