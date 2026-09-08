#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.schemas.analysis import AnalysisRequest, TextAnalysisRequest  # noqa: E402
from app.services.decision_engine import analyze_authorization_denial  # noqa: E402
from app.services.evidence_extractor import ExtractionError, extract_text_analysis  # noqa: E402


DEFAULT_DATASET = ROOT / "tests" / "evals" / "golden_cases.json"


def run_golden_evals(dataset_path: Path = DEFAULT_DATASET) -> Dict[str, Any]:
    cases = json.loads(dataset_path.read_text(encoding="utf-8"))
    results = [_run_case(case) for case in cases]
    metrics = _calculate_metrics(results)
    return {"cases": results, "metrics": metrics}


def _run_case(case: Dict[str, Any]) -> Dict[str, Any]:
    expected_error = bool(case.get("expected_error", False))
    try:
        claim, authorization, _bundle = extract_text_analysis(
            TextAnalysisRequest(
                eob_text=case.get("eob_text", ""),
                authorization_text=case.get("authorization_text"),
                use_llm_reasoning=False,
            )
        )
        decision = analyze_authorization_denial(AnalysisRequest(claim=claim, authorization=authorization))
    except (ExtractionError, ValueError) as exc:
        return {
            "case_id": case["case_id"],
            "description": case["description"],
            "expected_error": expected_error,
            "actual_error": True,
            "error": str(exc),
            "passed": expected_error and _contains_expected_error(str(exc), case.get("expected_error_contains")),
            "checks": {
                "action": expected_error,
                "human_review": expected_error,
                "contradictions": expected_error,
                "missing_evidence": expected_error,
                "matched_fields": expected_error,
            },
        }

    actual_contradictions = {item.field for item in decision.contradictions}
    actual_missing = set(decision.missing_evidence)
    actual_matched = {item.type for item in decision.evidence if item.status.value == "matched"}
    checks = {
        "action": decision.recommended_action.value == case["expected_action"],
        "human_review": decision.requires_human_review == case["expected_requires_human_review"],
        "contradictions": actual_contradictions == set(case["expected_contradictions"]),
        "missing_evidence": actual_missing == set(case["expected_missing_evidence"]),
        "matched_fields": set(case["expected_matched_fields"]).issubset(actual_matched),
        "family": decision.denial.family == case["expected_denial_family"],
    }
    return {
        "case_id": case["case_id"],
        "description": case["description"],
        "expected_error": expected_error,
        "actual_error": False,
        "expected": {
            "action": case["expected_action"],
            "human_review": case["expected_requires_human_review"],
            "contradictions": case["expected_contradictions"],
            "missing_evidence": case["expected_missing_evidence"],
            "matched_fields": case["expected_matched_fields"],
        },
        "actual": {
            "action": decision.recommended_action.value,
            "human_review": decision.requires_human_review,
            "contradictions": sorted(actual_contradictions),
            "missing_evidence": sorted(actual_missing),
            "matched_fields": sorted(actual_matched),
            "confidence": decision.confidence,
            "supported": decision.supported,
        },
        "checks": checks,
        "passed": not expected_error and all(checks.values()),
    }


def _calculate_metrics(results: List[Dict[str, Any]]) -> Dict[str, float]:
    non_error_results = [item for item in results if not item["expected_error"]]
    return {
        "cases": float(len(results)),
        "recommended_action_accuracy": _accuracy(non_error_results, "action"),
        "human_review_accuracy": _accuracy(non_error_results, "human_review"),
        "contradiction_detection_accuracy": _accuracy(non_error_results, "contradictions"),
        "missing_evidence_detection_accuracy": _accuracy(non_error_results, "missing_evidence"),
        "field_validation_accuracy": _accuracy(non_error_results, "matched_fields"),
        "safe_error_handling_accuracy": _error_accuracy(results),
        "overall_case_pass_rate": sum(1 for item in results if item["passed"]) / len(results),
    }


def _accuracy(results: List[Dict[str, Any]], check_name: str) -> float:
    if not results:
        return 1.0
    return sum(1 for item in results if item["checks"][check_name]) / len(results)


def _error_accuracy(results: List[Dict[str, Any]]) -> float:
    expected_error_results = [item for item in results if item["expected_error"]]
    if not expected_error_results:
        return 1.0
    return sum(1 for item in expected_error_results if item["passed"]) / len(expected_error_results)


def _contains_expected_error(actual_error: str, expected: Optional[str]) -> bool:
    if not expected:
        return True
    return expected.lower() in actual_error.lower()


def _format_percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def main() -> int:
    dataset_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DATASET
    report = run_golden_evals(dataset_path)
    metrics = report["metrics"]
    failed = [item for item in report["cases"] if not item["passed"]]

    print("Evaluation Results")
    print()
    print(f"Cases: {int(metrics['cases'])}")
    print(f"Recommended Action Accuracy: {_format_percent(metrics['recommended_action_accuracy'])}")
    print(f"Human Review Accuracy: {_format_percent(metrics['human_review_accuracy'])}")
    print(f"Contradiction Detection: {_format_percent(metrics['contradiction_detection_accuracy'])}")
    print(f"Missing Evidence Detection: {_format_percent(metrics['missing_evidence_detection_accuracy'])}")
    print(f"Field Validation Accuracy: {_format_percent(metrics['field_validation_accuracy'])}")
    print(f"Safe Error Handling: {_format_percent(metrics['safe_error_handling_accuracy'])}")
    print(f"Overall Golden Case Pass Rate: {_format_percent(metrics['overall_case_pass_rate'])}")

    if failed:
        print()
        print("Failed Cases")
        for item in failed:
            print(f"- {item['case_id']}: {item['description']}")
            print(f"  expected={item.get('expected')} actual={item.get('actual') or item.get('error')}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
