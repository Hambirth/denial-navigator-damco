from app.schemas.analysis import EvidenceFinding, EvidenceStatus
from app.services.decision_engine import calculate_confidence


def finding(status: EvidenceStatus) -> EvidenceFinding:
    return EvidenceFinding(type="demo", source="test", value="demo", status=status)


def test_confidence_high_when_all_required_evidence_matches():
    checks = [finding(EvidenceStatus.MATCHED) for _ in range(8)]
    assert calculate_confidence(checks) == 1.0


def test_confidence_medium_when_one_noncritical_check_is_missing():
    checks = [finding(EvidenceStatus.MATCHED) for _ in range(7)] + [finding(EvidenceStatus.MISSING)]
    assert calculate_confidence(checks) == 0.76


def test_confidence_lower_when_contradictions_exist():
    checks = [finding(EvidenceStatus.MATCHED) for _ in range(6)] + [
        finding(EvidenceStatus.MISMATCHED),
        finding(EvidenceStatus.MISMATCHED),
    ]
    assert calculate_confidence(checks) == 0.59


def test_confidence_low_when_no_validation_checks_exist():
    assert calculate_confidence([]) == 0.1
