from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)

VALID_EOB = """Synthetic Explanation of Benefits
Document Type: EOB
Claim ID: DEMO-FAIL-001
Patient: Demo Patient
Member ID: DEMO-MEMBER-FAIL
Payer: Demo Health Plan
Date of Service: 2026-01-15
CPT: 29881
Provider: Demo Orthopedic Group
Provider NPI: 1234567890
Denial Code: CO-197
Denial Reason: Precertification authorization absent
Amount: 1000.00"""

VALID_AUTH = """Synthetic Authorization Letter
Document Type: Authorization
Authorization Number: AUTH-FAIL-001
Patient: Demo Patient
Member ID: DEMO-MEMBER-FAIL
Payer: Demo Health Plan
Effective Start: 2026-01-01
Effective End: 2026-02-28
Approved CPT: 29881
Provider: Demo Orthopedic Group
Provider NPI: 1234567890"""


def post_text(eob_text=VALID_EOB, authorization_text=VALID_AUTH, use_llm_reasoning=False):
    return client.post(
        "/api/analyze-text",
        json={
            "eob_text": eob_text,
            "authorization_text": authorization_text,
            "use_llm_reasoning": use_llm_reasoning,
        },
    )


def test_malformed_request_returns_422():
    response = client.post("/api/analyze-text", json={"eob_text": 123, "authorization_text": VALID_AUTH})
    assert response.status_code == 422


def test_malformed_dates_return_422():
    response = post_text(authorization_text=VALID_AUTH.replace("Effective End: 2026-02-28", "Effective End: soon"))
    assert response.status_code == 422
    assert "effective_end" in response.json()["detail"]


def test_unexpected_denial_code_is_unsupported_manual_review():
    eob = VALID_EOB.replace("Denial Code: CO-197", "Denial Code: CO-50").replace(
        "Denial Reason: Precertification authorization absent",
        "Denial Reason: Non-covered service",
    )
    response = post_text(eob_text=eob)
    body = response.json()
    assert response.status_code == 200
    assert body["supported"] is False
    assert body["meta"]["supported"] is False
    assert body["recommended_action"] == "manual_review"
    assert body["requires_human_review"] is True


def test_unexpected_denial_code_with_authorization_language_is_still_unsupported():
    eob = VALID_EOB.replace("Denial Code: CO-197", "Denial Code: CO-198")
    response = post_text(eob_text=eob)
    body = response.json()
    assert response.status_code == 200
    assert body["supported"] is False
    assert body["recommended_action"] == "manual_review"
    assert body["confidence"] == 0.1


def test_empty_source_text_returns_422():
    response = post_text(eob_text="")
    assert response.status_code == 422


def test_missing_eob_returns_422():
    response = client.post("/api/analyze-text", json={"authorization_text": VALID_AUTH})
    assert response.status_code == 422


def test_reasoning_service_exception_falls_back_to_deterministic(monkeypatch):
    from app.services import reasoning_service

    monkeypatch.setenv("REASONING_MODE", "llm")
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-test-key")

    def fail(_decision):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(reasoning_service, "_generate_llm_summary", fail)
    response = post_text(use_llm_reasoning=True)
    body = response.json()
    assert response.status_code == 200
    assert body["reasoning_source"] == "deterministic"
    assert body["meta"]["reasoning_source"] == "deterministic"
    assert body["recommended_action"] == "reprocess"


def test_simulated_llm_timeout_falls_back_to_deterministic(monkeypatch):
    from app.services import reasoning_service

    monkeypatch.setenv("REASONING_MODE", "llm")
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-test-key")

    def timeout(_decision):
        raise TimeoutError("synthetic timeout")

    monkeypatch.setattr(reasoning_service, "_generate_llm_summary", timeout)
    response = post_text(use_llm_reasoning=True)
    body = response.json()
    assert response.status_code == 200
    assert body["reasoning_source"] == "deterministic"
    assert body["recommended_action"] == "reprocess"


def test_malformed_llm_structured_response_falls_back_to_deterministic(monkeypatch):
    from app.services import reasoning_service

    monkeypatch.setenv("REASONING_MODE", "llm")
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-test-key")

    def malformed(_decision):
        raise ValueError("LLM response did not match the expected reasoning schema")

    monkeypatch.setattr(reasoning_service, "_generate_llm_summary", malformed)
    response = post_text(use_llm_reasoning=True)
    body = response.json()
    assert response.status_code == 200
    assert body["reasoning_source"] == "deterministic"
    assert body["recommended_action"] == "reprocess"


def test_extractor_unable_to_identify_required_field_returns_422():
    eob = VALID_EOB.replace("Provider NPI: 1234567890\n", "")
    response = post_text(eob_text=eob)
    assert response.status_code == 422
    assert "provider_npi" in response.json()["detail"]
