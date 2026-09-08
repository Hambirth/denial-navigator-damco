from pathlib import Path

from scripts.run_evals import run_golden_evals


ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "tests" / "evals" / "golden_cases.json"


def test_golden_eval_thresholds_are_met():
    report = run_golden_evals(DATASET)
    metrics = report["metrics"]
    assert metrics["recommended_action_accuracy"] >= 0.90
    assert metrics["human_review_accuracy"] >= 0.95
    assert metrics["missing_evidence_detection_accuracy"] >= 0.95
    assert metrics["safe_error_handling_accuracy"] >= 0.95
    assert metrics["overall_case_pass_rate"] >= 0.95


def test_current_golden_dataset_is_fully_passing():
    report = run_golden_evals(DATASET)
    failed = [item["case_id"] for item in report["cases"] if not item["passed"]]
    assert failed == []
