from datetime import date
from typing import List, Optional

from app.schemas.analysis import (
    AnalysisRequest,
    AnalysisResponse,
    Contradiction,
    DenialSummary,
    EvidenceFinding,
    EvidenceStatus,
    RecommendedAction,
    ResponseMeta,
)
from app.services.reasoning_service import apply_grounded_reasoning


AUTHORIZATION_CODES = {"CO-197"}
PIPELINE_VERSION = "phase-4-eval-v1"


def analyze_authorization_denial(request: AnalysisRequest) -> AnalysisResponse:
    claim = request.claim
    authorization = request.authorization
    family = classify_denial_family(claim.denial_code, claim.denial_description)

    evidence: List[EvidenceFinding] = []
    missing_evidence: List[str] = []
    contradictions: List[Contradiction] = []

    if family != "authorization":
        return _finalize(
            AnalysisResponse(
                supported=False,
                denial=DenialSummary(
                    code=claim.denial_code,
                    family=family,
                    summary="This demo currently supports authorization-related CO-197 scenarios only.",
                ),
                root_cause="Unsupported denial family for this challenge demo.",
                evidence=[],
                missing_evidence=["supported CO-197 authorization denial"],
                contradictions=[],
                recommended_action=RecommendedAction.MANUAL_REVIEW,
                confidence=0.1,
                requires_human_review=True,
                reasoning_summary="This demo currently supports authorization-related CO-197 scenarios only.",
                meta=ResponseMeta(pipeline_version=PIPELINE_VERSION, supported=False),
            ),
            request,
        )

    if authorization is None:
        required = [
            "authorization number",
            "authorization patient/member identity",
            "authorization payer",
            "authorization effective dates",
            "authorized CPT/service",
            "authorized provider",
        ]
        return _finalize(
            AnalysisResponse(
                denial=_denial_summary(claim.denial_code, claim.denial_description),
                root_cause="The claim was denied for missing or invalid authorization, but no authorization evidence was provided.",
                evidence=[
                    EvidenceFinding(
                        type="authorization_document",
                        source="request.authorization",
                        value="not provided",
                        status=EvidenceStatus.MISSING,
                    )
                ],
                missing_evidence=required,
                contradictions=[],
                recommended_action=RecommendedAction.MANUAL_REVIEW,
                confidence=0.2,
                requires_human_review=True,
                reasoning_summary="A confident reprocess or reconsideration recommendation would be hallucinated without authorization evidence.",
                meta=ResponseMeta(pipeline_version=PIPELINE_VERSION),
            ),
            request,
        )

    checks = [
        _check("patient_identity", authorization.source, claim.patient_name, authorization.patient_name),
        _check("member_id", authorization.source, claim.member_id, authorization.member_id),
        _check("payer", authorization.source, claim.payer, authorization.payer),
        _check("provider_npi", authorization.source, claim.provider_npi, authorization.provider_npi),
        _check("provider_name", authorization.source, claim.provider_name, authorization.provider_name),
        _check_present("authorization_number", authorization.source, authorization.authorization_number),
        _check_cpt(claim.cpt_code, authorization.approved_cpt_codes, authorization.source),
        _check_dos(claim.date_of_service, authorization.effective_start, authorization.effective_end, authorization.source),
    ]

    evidence.extend(checks)
    contradictions.extend(_build_contradictions(checks, claim, authorization))

    missing_evidence.extend(_missing_from_checks(checks))
    confidence = calculate_confidence(checks)

    dos_valid = _status_for(checks, "authorization_date_range") == EvidenceStatus.MATCHED
    cpt_valid = _status_for(checks, "cpt_code") == EvidenceStatus.MATCHED
    payer_valid = _status_for(checks, "payer") == EvidenceStatus.MATCHED
    identity_valid = (
        _status_for(checks, "patient_identity") == EvidenceStatus.MATCHED
        and _status_for(checks, "member_id") == EvidenceStatus.MATCHED
    )
    provider_valid = (
        _status_for(checks, "provider_npi") == EvidenceStatus.MATCHED
        or _status_for(checks, "provider_name") == EvidenceStatus.MATCHED
    )
    auth_number_valid = _status_for(checks, "authorization_number") == EvidenceStatus.MATCHED

    all_core_valid = all([dos_valid, cpt_valid, payer_valid, identity_valid, provider_valid, auth_number_valid])

    if all_core_valid:
        recommended_action = RecommendedAction.REPROCESS
        requires_human_review = False
        root_cause = "Valid authorization evidence matches the denied claim. The denial likely reflects payer-side authorization linkage or processing error."
        reasoning = "Deterministic checks matched identity, payer, DOS, CPT, provider, and authorization number. Reprocess is the first operational path; reconsideration remains the fallback if payer refuses simple reprocessing."
    elif authorization and not dos_valid:
        recommended_action = RecommendedAction.MANUAL_REVIEW
        requires_human_review = True
        root_cause = "Authorization evidence exists, but the date of service is outside the authorization effective date range."
        reasoning = "The system found authorization evidence but refused to treat it as valid for this claim because the DOS validation failed."
    elif authorization and not cpt_valid:
        recommended_action = RecommendedAction.CORRECTED_CLAIM
        requires_human_review = True
        root_cause = "Authorization evidence exists, but it does not include the billed CPT/service."
        reasoning = "The CPT mismatch is deterministic. The claim should not be sent as a valid-auth reprocess without human review."
    else:
        recommended_action = RecommendedAction.MANUAL_REVIEW
        requires_human_review = True
        root_cause = "Authorization evidence is incomplete or does not fully match the denied claim."
        reasoning = "One or more deterministic checks failed, so the system avoided a confident reprocess recommendation."

    return _finalize(
        AnalysisResponse(
            denial=_denial_summary(claim.denial_code, claim.denial_description),
            root_cause=root_cause,
            evidence=evidence,
            missing_evidence=missing_evidence,
            contradictions=contradictions,
            recommended_action=recommended_action,
            confidence=confidence,
            requires_human_review=requires_human_review,
            reasoning_summary=reasoning,
            meta=ResponseMeta(pipeline_version=PIPELINE_VERSION),
        ),
        request,
    )


def _finalize(decision: AnalysisResponse, request: AnalysisRequest) -> AnalysisResponse:
    return apply_grounded_reasoning(decision, requested_llm=request.use_llm_reasoning)


def calculate_confidence(checks: List[EvidenceFinding]) -> float:
    if not checks:
        return 0.1
    matched_count = sum(1 for item in checks if item.status == EvidenceStatus.MATCHED)
    mismatched_count = sum(1 for item in checks if item.status == EvidenceStatus.MISMATCHED)
    missing_count = sum(1 for item in checks if item.status == EvidenceStatus.MISSING)
    return round(max(0.0, (matched_count / len(checks)) - (0.08 * mismatched_count) - (0.12 * missing_count)), 2)


def classify_denial_family(code: str, description: str) -> str:
    normalized_code = code.strip().upper()
    if normalized_code in AUTHORIZATION_CODES:
        return "authorization"
    return "unknown"


def _denial_summary(code: str, description: str) -> DenialSummary:
    return DenialSummary(
        code=code,
        family="authorization",
        summary=f"{code} indicates the payer denied the claim for an authorization or precertification issue: {description}",
    )


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().upper().split())


def _check(field_type: str, source: str, claim_value: str, evidence_value: str) -> EvidenceFinding:
    if not evidence_value:
        return EvidenceFinding(type=field_type, source=source, value="missing", status=EvidenceStatus.MISSING)
    status = EvidenceStatus.MATCHED if _normalize(claim_value) == _normalize(evidence_value) else EvidenceStatus.MISMATCHED
    return EvidenceFinding(type=field_type, source=source, value=evidence_value, status=status)


def _check_present(field_type: str, source: str, value: str) -> EvidenceFinding:
    status = EvidenceStatus.MATCHED if value.strip() else EvidenceStatus.MISSING
    return EvidenceFinding(type=field_type, source=source, value=value or "missing", status=status)


def _check_cpt(claim_cpt: str, approved_cpts: List[str], source: str) -> EvidenceFinding:
    if not approved_cpts:
        return EvidenceFinding(type="cpt_code", source=source, value="missing", status=EvidenceStatus.MISSING)
    status = EvidenceStatus.MATCHED if claim_cpt in approved_cpts else EvidenceStatus.MISMATCHED
    return EvidenceFinding(type="cpt_code", source=source, value=", ".join(approved_cpts), status=status)


def _check_dos(dos: date, start: date, end: date, source: str) -> EvidenceFinding:
    status = EvidenceStatus.MATCHED if start <= dos <= end else EvidenceStatus.MISMATCHED
    return EvidenceFinding(
        type="authorization_date_range",
        source=source,
        value=f"{start.isoformat()} to {end.isoformat()}",
        status=status,
    )


def _status_for(checks: List[EvidenceFinding], field_type: str) -> EvidenceStatus:
    for item in checks:
        if item.type == field_type:
            return item.status
    return EvidenceStatus.MISSING


def _missing_from_checks(checks: List[EvidenceFinding]) -> List[str]:
    return [item.type for item in checks if item.status == EvidenceStatus.MISSING]


def _build_contradictions(checks: List[EvidenceFinding], claim, authorization) -> List[Contradiction]:
    contradictions = []
    for item in checks:
        if item.status != EvidenceStatus.MISMATCHED:
            continue
        if item.type == "authorization_date_range":
            contradictions.append(
                Contradiction(
                    field="date_of_service",
                    claim_value=claim.date_of_service.isoformat(),
                    evidence_value=item.value,
                    explanation="Claim DOS is outside the authorization effective date range.",
                )
            )
        elif item.type == "cpt_code":
            contradictions.append(
                Contradiction(
                    field="cpt_code",
                    claim_value=claim.cpt_code,
                    evidence_value=item.value,
                    explanation="Billed CPT is not included in the authorization approval.",
                )
            )
        elif item.type == "payer":
            contradictions.append(
                Contradiction(
                    field="payer",
                    claim_value=claim.payer,
                    evidence_value=authorization.payer,
                    explanation="Authorization evidence belongs to a different payer.",
                )
            )
        elif item.type in {"patient_identity", "member_id", "provider_npi", "provider_name"}:
            contradictions.append(
                Contradiction(
                    field=item.type,
                    claim_value=getattr(claim, _claim_attr(item.type)),
                    evidence_value=item.value,
                    explanation=f"{item.type.replace('_', ' ').title()} does not match the claim.",
                )
            )
    return contradictions


def _claim_attr(field_type: str) -> str:
    return {
        "patient_identity": "patient_name",
        "member_id": "member_id",
        "provider_npi": "provider_npi",
        "provider_name": "provider_name",
    }[field_type]
