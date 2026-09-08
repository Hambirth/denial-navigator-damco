from datetime import date
from typing import Dict, List, Optional, Tuple

from pydantic import ValidationError

from app.schemas.analysis import (
    AuthorizationEvidence,
    Claim,
    ClaimEvidence,
    EvidenceBundle,
    EvidenceField,
    TextAnalysisRequest,
)


class ExtractionError(ValueError):
    pass


CLAIM_LABELS = {
    "claim_id": "Claim ID",
    "patient_name": "Patient",
    "member_id": "Member ID",
    "payer": "Payer",
    "date_of_service": "Date of Service",
    "cpt_code": "CPT",
    "provider_name": "Provider",
    "provider_npi": "Provider NPI",
    "denial_code": "Denial Code",
    "denial_description": "Denial Reason",
}

AUTH_LABELS = {
    "authorization_number": "Authorization Number",
    "patient_name": "Patient",
    "member_id": "Member ID",
    "payer": "Payer",
    "effective_start": "Effective Start",
    "effective_end": "Effective End",
    "approved_cpt_codes": "Approved CPT",
    "provider_name": "Provider",
    "provider_npi": "Provider NPI",
}


def extract_text_analysis(request: TextAnalysisRequest) -> Tuple[Claim, Optional[AuthorizationEvidence], EvidenceBundle]:
    claim_values, claim_fields = _extract_fields(request.eob_text, CLAIM_LABELS, "Synthetic EOB Text")
    claim = _build_claim(claim_values)

    authorization = None
    authorization_evidence = None
    if request.authorization_text and request.authorization_text.strip():
        auth_values, auth_fields = _extract_fields(
            request.authorization_text,
            AUTH_LABELS,
            "Synthetic Authorization Text",
        )
        authorization = _build_authorization(auth_values)
        authorization_evidence = ClaimEvidence(fields=auth_fields)

    bundle = EvidenceBundle(
        claim=ClaimEvidence(fields=claim_fields),
        authorization=authorization_evidence,
        extracted_claim=claim,
        extracted_authorization=authorization,
    )
    return claim, authorization, bundle


def _extract_fields(text: str, labels: Dict[str, str], source: str) -> Tuple[Dict[str, str], List[EvidenceField]]:
    parsed_lines = _parse_labelled_lines(text)
    values: Dict[str, str] = {}
    fields: List[EvidenceField] = []
    for name, label in labels.items():
        value = parsed_lines.get(_normalize_label(label))
        values[name] = value or ""
        fields.append(EvidenceField(name=name, value=value, source=source, confidence=1.0 if value else 0.0))
    return values, fields


def _parse_labelled_lines(text: str) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for raw_line in text.splitlines():
        if ":" not in raw_line:
            continue
        label, value = raw_line.split(":", 1)
        label = _normalize_label(label)
        if label and value.strip():
            values[label] = value.strip()
    return values


def _build_claim(values: Dict[str, str]) -> Claim:
    required = [name for name in CLAIM_LABELS if not values.get(name)]
    if required:
        raise ExtractionError(f"EOB text is missing required claim fields: {', '.join(required)}")

    try:
        return Claim(
            claim_id=values["claim_id"],
            patient_name=values["patient_name"],
            member_id=values["member_id"],
            payer=values["payer"],
            date_of_service=_parse_date(values["date_of_service"], "date_of_service"),
            cpt_code=values["cpt_code"],
            provider_name=values["provider_name"],
            provider_npi=values["provider_npi"],
            denial_code=values["denial_code"],
            denial_description=values["denial_description"],
        )
    except (ValidationError, ValueError) as exc:
        raise ExtractionError(f"EOB text contains invalid claim data: {exc}") from exc


def _build_authorization(values: Dict[str, str]) -> AuthorizationEvidence:
    required = [name for name in AUTH_LABELS if not values.get(name)]
    if required:
        raise ExtractionError(f"Authorization text is missing required fields: {', '.join(required)}")

    try:
        return AuthorizationEvidence(
            source="Synthetic Authorization Text",
            authorization_number=values["authorization_number"],
            patient_name=values["patient_name"],
            member_id=values["member_id"],
            payer=values["payer"],
            effective_start=_parse_date(values["effective_start"], "effective_start"),
            effective_end=_parse_date(values["effective_end"], "effective_end"),
            approved_cpt_codes=[item.strip() for item in values["approved_cpt_codes"].split(",") if item.strip()],
            provider_name=values["provider_name"],
            provider_npi=values["provider_npi"],
        )
    except (ValidationError, ValueError) as exc:
        raise ExtractionError(f"Authorization text contains invalid data: {exc}") from exc


def _parse_date(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise ExtractionError(f"{field_name} must use YYYY-MM-DD format") from exc


def _normalize_label(value: str) -> str:
    return " ".join(value.strip().lower().split())
