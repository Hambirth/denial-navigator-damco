import json
import os
from typing import Literal, Optional

from pydantic import BaseModel, ValidationError

from app.schemas.analysis import AnalysisResponse


class ReasoningResult(BaseModel):
    reasoning_summary: str
    reasoning_source: Literal["deterministic", "llm"]


class LLMReasoningSummary(BaseModel):
    reasoning_summary: str


def build_grounded_reasoning(decision: AnalysisResponse, requested_llm: bool = False) -> ReasoningResult:
    mode = os.getenv("REASONING_MODE", "deterministic").strip().lower()
    if requested_llm:
        mode = "llm"

    if mode == "llm" and os.getenv("OPENAI_API_KEY"):
        try:
            return ReasoningResult(
                reasoning_summary=_generate_llm_summary(decision),
                reasoning_source="llm",
            )
        except Exception:
            pass

    return ReasoningResult(
        reasoning_summary=decision.reasoning_summary,
        reasoning_source="deterministic",
    )


def apply_grounded_reasoning(decision: AnalysisResponse, requested_llm: bool = False) -> AnalysisResponse:
    reasoning = build_grounded_reasoning(decision, requested_llm=requested_llm)
    meta = decision.meta.model_copy(update={"reasoning_source": reasoning.reasoning_source})
    return decision.model_copy(
        update={
            "reasoning_summary": reasoning.reasoning_summary,
            "reasoning_source": reasoning.reasoning_source,
            "meta": meta,
        }
    )


def _generate_llm_summary(decision: AnalysisResponse) -> str:
    payload = decision.model_dump(mode="json")
    prompt = (
        "Summarize this already-validated denial decision for a claims analyst. "
        "Do not change the recommended_action, confidence, evidence statuses, contradictions, "
        "or human-review flag. Return JSON with only reasoning_summary.\n\n"
        f"{json.dumps(payload, indent=2)}"
    )

    from openai import OpenAI  # type: ignore

    client = OpenAI()
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[
            {
                "role": "system",
                "content": "You write concise grounded summaries from provided facts only.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0,
        response_format={"type": "json_object"},
        timeout=15,
    )
    content: Optional[str] = response.choices[0].message.content
    if not content:
        raise ValueError("LLM returned an empty response")
    try:
        parsed = LLMReasoningSummary.model_validate_json(content)
    except ValidationError as exc:
        raise ValueError("LLM response did not match the expected reasoning schema") from exc
    return parsed.reasoning_summary.strip()
