from pathlib import Path
import hashlib
import logging
import time

from fastapi import APIRouter, HTTPException

from app.schemas.analysis import AnalysisRequest, AnalysisResponse, TextAnalysisRequest, TextAnalysisResponse
from app.services.decision_engine import analyze_authorization_denial
from app.services.evidence_extractor import ExtractionError, extract_text_analysis


router = APIRouter(tags=["denial-analysis"])
logger = logging.getLogger("denial_navigator.analysis")

DEMO_DATA_DIR = Path(__file__).resolve().parents[4] / "demo-data" / "synthetic"
TEXT_DATA_DIR = DEMO_DATA_DIR / "text"

SCENARIOS = {
    "valid-authorization": {
        "title": "Valid Authorization Evidence",
        "description": "CO-197 denial where authorization evidence matches the claim.",
        "eob_file": "valid-authorization-eob.txt",
        "authorization_file": "valid-authorization-auth.txt",
    },
    "dos-mismatch": {
        "title": "Authorization DOS Mismatch",
        "description": "Authorization exists, but it does not cover the claim date of service.",
        "eob_file": "dos-mismatch-eob.txt",
        "authorization_file": "dos-mismatch-auth.txt",
    },
    "missing-authorization": {
        "title": "Missing Authorization Evidence",
        "description": "CO-197 denial without authorization evidence.",
        "eob_file": "missing-authorization-eob.txt",
        "authorization_file": None,
    },
    "cpt-mismatch": {
        "title": "Authorization CPT Mismatch",
        "description": "Authorization exists, but it does not include the billed CPT.",
        "eob_file": "cpt-mismatch-eob.txt",
        "authorization_file": "cpt-mismatch-auth.txt",
    },
    "payer-mismatch": {
        "title": "Authorization Payer Mismatch",
        "description": "Authorization exists, but it belongs to a different payer.",
        "eob_file": "payer-mismatch-eob.txt",
        "authorization_file": "payer-mismatch-auth.txt",
    },
}


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/scenarios")
def list_scenarios():
    scenarios = [
        {"id": scenario_id, "title": scenario["title"], "description": scenario["description"]}
        for scenario_id, scenario in SCENARIOS.items()
    ]
    return {"scenarios": scenarios}


@router.get("/scenarios/{scenario_id}")
def get_scenario(scenario_id: str):
    scenario = SCENARIOS.get(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return {
        "scenario_id": scenario_id,
        "title": scenario["title"],
        "description": scenario["description"],
        "eob_text": _read_text_fixture(scenario["eob_file"]),
        "authorization_text": _read_text_fixture(scenario["authorization_file"]) if scenario["authorization_file"] else None,
    }


@router.post("/analyze-denial", response_model=AnalysisResponse)
def analyze_denial(request: AnalysisRequest):
    start = time.perf_counter()
    decision = analyze_authorization_denial(request)
    _log_decision(decision, request.claim.claim_id, start)
    return decision


@router.post("/analyze-text", response_model=TextAnalysisResponse)
def analyze_text(request: TextAnalysisRequest):
    start = time.perf_counter()
    try:
        claim, authorization, extracted_evidence = extract_text_analysis(request)
    except ExtractionError as exc:
        _log_extraction_error(str(exc), start)
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    decision = analyze_authorization_denial(
        AnalysisRequest(
            claim=claim,
            authorization=authorization,
            use_llm_reasoning=request.use_llm_reasoning,
        )
    )
    _log_decision(decision, claim.claim_id, start)
    return TextAnalysisResponse(**decision.model_dump(), extracted_evidence=extracted_evidence)


def _read_text_fixture(file_name: str) -> str:
    path = TEXT_DATA_DIR / file_name
    if not path.exists():
        raise HTTPException(status_code=500, detail=f"Synthetic fixture missing: {file_name}")
    return path.read_text(encoding="utf-8")


def _log_decision(decision: AnalysisResponse, claim_id: str, start: float) -> None:
    logger.info(
        "denial_analysis_completed",
        extra={
            "case_ref": _safe_case_ref(claim_id),
            "denial_family": decision.denial.family,
            "recommended_action": decision.recommended_action.value,
            "confidence": decision.confidence,
            "requires_human_review": decision.requires_human_review,
            "reasoning_source": decision.reasoning_source,
            "supported": decision.supported,
            "duration_ms": round((time.perf_counter() - start) * 1000, 2),
        },
    )


def _log_extraction_error(error: str, start: float) -> None:
    logger.warning(
        "denial_analysis_extraction_failed",
        extra={
            "error_type": error.split(":", 1)[0],
            "duration_ms": round((time.perf_counter() - start) * 1000, 2),
        },
    )


def _safe_case_ref(claim_id: str) -> str:
    return hashlib.sha256(claim_id.encode("utf-8")).hexdigest()[:12]
