import json
import os
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.schemas.analysis import AnalysisResponse


DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_OPENAI_TIMEOUT_SECONDS = 15.0
OPENAI_PROVIDER = "openai"


class ReasoningResult(BaseModel):
    reasoning_summary: str
    reasoning_source: Literal["deterministic", "llm"]
    reasoning_mode: Literal["llm", "deterministic_fallback"]
    reasoning_provider: Optional[str] = None
    reasoning_model: Optional[str] = None


class LLMReasoningSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reasoning_summary: str = Field(..., min_length=1, max_length=1200)


def build_grounded_reasoning(decision: AnalysisResponse, requested_llm: bool = False) -> ReasoningResult:
    mode = os.getenv("REASONING_MODE", "deterministic").strip().lower()
    if requested_llm:
        mode = "llm"

    provider = OPENAI_PROVIDER if mode == "llm" else None
    model = os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL).strip() or DEFAULT_OPENAI_MODEL

    if mode == "llm" and decision.supported and os.getenv("OPENAI_API_KEY"):
        try:
            return ReasoningResult(
                reasoning_summary=_generate_llm_summary(decision),
                reasoning_source="llm",
                reasoning_mode="llm",
                reasoning_provider=provider,
                reasoning_model=model,
            )
        except Exception:
            pass

    return ReasoningResult(
        reasoning_summary=decision.reasoning_summary,
        reasoning_source="deterministic",
        reasoning_mode="deterministic_fallback",
        reasoning_provider=provider,
        reasoning_model=model if provider else None,
    )


def apply_grounded_reasoning(decision: AnalysisResponse, requested_llm: bool = False) -> AnalysisResponse:
    reasoning = build_grounded_reasoning(decision, requested_llm=requested_llm)
    meta = decision.meta.model_copy(
        update={
            "reasoning_source": reasoning.reasoning_source,
            "reasoning_mode": reasoning.reasoning_mode,
            "reasoning_provider": reasoning.reasoning_provider,
            "reasoning_model": reasoning.reasoning_model,
        }
    )
    return decision.model_copy(
        update={
            "reasoning_summary": reasoning.reasoning_summary,
            "reasoning_source": reasoning.reasoning_source,
            "reasoning_mode": reasoning.reasoning_mode,
            "reasoning_provider": reasoning.reasoning_provider,
            "reasoning_model": reasoning.reasoning_model,
            "meta": meta,
        }
    )


def _generate_llm_summary(decision: AnalysisResponse) -> str:
    payload = _build_grounded_prompt_payload(decision)
    prompt = (
        "You are explaining an already validated decision.\n"
        "Do not change the recommended action.\n"
        "Do not invent missing facts.\n"
        "Use only the supplied evidence.\n"
        "If evidence is missing or contradictory, state that explicitly.\n"
        "Return JSON with only this key: reasoning_summary.\n\n"
        f"{json.dumps(payload, indent=2)}"
    )

    from openai import OpenAI  # type: ignore

    client = OpenAI()
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
        messages=[
            {
                "role": "system",
                "content": "You write concise grounded summaries from provided facts only.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0,
        response_format={"type": "json_object"},
        timeout=_openai_timeout_seconds(),
    )
    content: Optional[str] = response.choices[0].message.content
    if not content:
        raise ValueError("LLM returned an empty response")
    try:
        parsed = LLMReasoningSummary.model_validate_json(content)
    except ValidationError as exc:
        raise ValueError("LLM response did not match the expected reasoning schema") from exc
    return parsed.reasoning_summary.strip()


def _openai_timeout_seconds() -> float:
    try:
        return float(os.getenv("OPENAI_TIMEOUT_SECONDS", str(DEFAULT_OPENAI_TIMEOUT_SECONDS)))
    except ValueError:
        return DEFAULT_OPENAI_TIMEOUT_SECONDS


def _build_grounded_prompt_payload(decision: AnalysisResponse) -> dict:
    return {
        "denial": decision.denial.model_dump(mode="json"),
        "validated_facts": [
            item.model_dump(mode="json")
            for item in decision.evidence
            if item.status.value == "matched"
        ],
        "contradictions": [item.model_dump(mode="json") for item in decision.contradictions],
        "missing_evidence": decision.missing_evidence,
        "deterministic_recommended_action": decision.recommended_action.value,
        "deterministic_confidence": decision.confidence,
        "requires_human_review": decision.requires_human_review,
        "root_cause": decision.root_cause,
    }
