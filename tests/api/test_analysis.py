import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)
ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "demo-data" / "synthetic"


def load_scenario(name: str) -> dict:
    with (FIXTURE_DIR / f"{name}.json").open("r", encoding="utf-8") as handle:
        scenario = json.load(handle)
    return {"claim": scenario["claim"], "authorization": scenario["authorization"]}


def analyze(payload: dict):
    response = client.post("/api/analyze-denial", json=payload)
    return response.status_code, response.json()


def test_valid_auth_matching_dos_routes_to_reprocess():
    status, body = analyze(load_scenario("valid-authorization"))
    assert status == 200
    assert body["denial"]["family"] == "authorization"
    assert body["recommended_action"] == "reprocess"
    assert body["requires_human_review"] is False
    assert body["confidence"] >= 0.9
    assert body["contradictions"] == []


def test_auth_exists_but_dos_outside_valid_period_routes_to_manual_review():
    status, body = analyze(load_scenario("dos-mismatch"))
    assert status == 200
    assert body["recommended_action"] == "manual_review"
    assert body["requires_human_review"] is True
    assert any(item["field"] == "date_of_service" for item in body["contradictions"])
    assert any(item["type"] == "authorization_date_range" and item["status"] == "mismatched" for item in body["evidence"])


def test_missing_auth_evidence_does_not_hallucinate_valid_recommendation():
    status, body = analyze(load_scenario("missing-authorization"))
    assert status == 200
    assert body["recommended_action"] == "manual_review"
    assert body["requires_human_review"] is True
    assert body["confidence"] <= 0.3
    assert "authorization number" in body["missing_evidence"]


def test_deterministic_cpt_mismatch_routes_to_corrected_claim():
    payload = load_scenario("valid-authorization")
    payload["authorization"]["approved_cpt_codes"] = ["27447"]
    status, body = analyze(payload)
    assert status == 200
    assert body["recommended_action"] == "corrected_claim"
    assert any(item["field"] == "cpt_code" for item in body["contradictions"])


def test_deterministic_payer_mismatch_routes_to_manual_review():
    payload = load_scenario("valid-authorization")
    payload["authorization"]["payer"] = "Other Demo Payer"
    status, body = analyze(payload)
    assert status == 200
    assert body["recommended_action"] == "manual_review"
    assert any(item["field"] == "payer" for item in body["contradictions"])


def test_malformed_invalid_api_input_returns_422():
    payload = load_scenario("valid-authorization")
    payload["claim"]["provider_npi"] = "BAD-NPI"
    response = client.post("/api/analyze-denial", json=payload)
    assert response.status_code == 422
