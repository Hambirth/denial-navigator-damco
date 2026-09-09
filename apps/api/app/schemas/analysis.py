from datetime import date
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class EvidenceStatus(str, Enum):
    MATCHED = "matched"
    MISMATCHED = "mismatched"
    MISSING = "missing"


class RecommendedAction(str, Enum):
    REPROCESS = "reprocess"
    RECONSIDERATION = "reconsideration"
    APPEAL = "appeal"
    CORRECTED_CLAIM = "corrected_claim"
    MANUAL_REVIEW = "manual_review"


class Claim(BaseModel):
    claim_id: str = Field(..., min_length=1)
    patient_name: str = Field(..., min_length=1)
    member_id: str = Field(..., min_length=1)
    payer: str = Field(..., min_length=1)
    date_of_service: date
    cpt_code: str = Field(..., min_length=4, max_length=5)
    provider_name: str = Field(..., min_length=1)
    provider_npi: str = Field(..., min_length=10, max_length=10)
    denial_code: str = Field(..., min_length=1)
    denial_description: str = Field(..., min_length=1)

    @field_validator("denial_code")
    @classmethod
    def normalize_denial_code(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("cpt_code", "provider_npi")
    @classmethod
    def digits_only(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned.isdigit():
            raise ValueError("must contain digits only")
        return cleaned


class AuthorizationEvidence(BaseModel):
    source: str = Field(default="Synthetic Authorization Letter", min_length=1)
    authorization_number: str = Field(..., min_length=1)
    patient_name: str = Field(..., min_length=1)
    member_id: str = Field(..., min_length=1)
    payer: str = Field(..., min_length=1)
    effective_start: date
    effective_end: date
    approved_cpt_codes: List[str] = Field(..., min_length=1)
    provider_name: str = Field(..., min_length=1)
    provider_npi: str = Field(..., min_length=10, max_length=10)

    @field_validator("approved_cpt_codes")
    @classmethod
    def validate_cpt_codes(cls, values: List[str]) -> List[str]:
        cleaned = [value.strip() for value in values]
        if any(not value.isdigit() or len(value) not in (4, 5) for value in cleaned):
            raise ValueError("approved CPT codes must be 4 or 5 digit strings")
        return cleaned


class AnalysisRequest(BaseModel):
    claim: Claim
    authorization: Optional[AuthorizationEvidence] = None
    use_llm_reasoning: bool = False


class DenialSummary(BaseModel):
    code: str
    family: str
    summary: str


class EvidenceFinding(BaseModel):
    type: str
    source: str
    value: str
    status: EvidenceStatus


class Contradiction(BaseModel):
    field: str
    claim_value: str
    evidence_value: str
    explanation: str


class ResponseMeta(BaseModel):
    pipeline_version: str = "phase-4-eval-v1"
    reasoning_source: str = "deterministic"
    reasoning_mode: str = "deterministic_fallback"
    reasoning_provider: Optional[str] = None
    reasoning_model: Optional[str] = None
    supported: bool = True


class AnalysisResponse(BaseModel):
    supported: bool = True
    denial: DenialSummary
    root_cause: str
    evidence: List[EvidenceFinding]
    missing_evidence: List[str]
    contradictions: List[Contradiction]
    recommended_action: RecommendedAction
    confidence: float = Field(..., ge=0.0, le=1.0)
    requires_human_review: bool
    reasoning_summary: str
    reasoning_source: str = "deterministic"
    reasoning_mode: str = "deterministic_fallback"
    reasoning_provider: Optional[str] = None
    reasoning_model: Optional[str] = None
    meta: ResponseMeta = Field(default_factory=ResponseMeta)


class EvidenceField(BaseModel):
    name: str
    value: Optional[str] = None
    source: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class ClaimEvidence(BaseModel):
    fields: List[EvidenceField]


class EvidenceBundle(BaseModel):
    claim: ClaimEvidence
    authorization: Optional[ClaimEvidence] = None
    extracted_claim: Optional[Claim] = None
    extracted_authorization: Optional[AuthorizationEvidence] = None


class TextAnalysisRequest(BaseModel):
    eob_text: str = Field(..., min_length=20)
    authorization_text: Optional[str] = None
    use_llm_reasoning: bool = False


class TextAnalysisResponse(AnalysisResponse):
    extracted_evidence: EvidenceBundle
