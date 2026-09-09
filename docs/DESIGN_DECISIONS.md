# Design Decisions

## Decision 1: Use Deterministic Validation For Factual Claim Matching

Context: Claim-denial workflows depend on exact factual checks such as dates, CPT codes, payer names, provider identifiers, and member IDs.

Decision: Validate factual matches with deterministic Python code.

Why: These facts are auditable and should not depend on probabilistic model behavior.

Tradeoff: The system is narrower and needs explicit rules for each supported denial family.

## Decision 2: LLM Only Explains Validated Results

Context: LLMs are useful for summarization, but they can hallucinate or overstate uncertain evidence.

Decision: The optional LLM receives the already-validated structured decision and may only return a reasoning summary.

Why: This preserves AI usefulness while keeping recommendation, confidence, contradictions, and human-review routing deterministic.

Tradeoff: The LLM cannot rescue incomplete validation logic; better rules and evidence extraction still need engineering work.

## Decision 3: Default Reasoning Mode Is Deterministic

Context: A public hiring challenge should run without secrets or external services.

Decision: `REASONING_MODE=deterministic` is the default.

Why: Reviewers can run tests, evals, API, and UI without an API key.

Tradeoff: The default explanation is less fluent than a tuned LLM summary.

## Decision 4: Use Synthetic Data For Public Challenge

Context: Healthcare data can contain PHI/PII and private claim details.

Decision: Use clearly synthetic patients, claims, payers, providers, and authorization numbers.

Why: This keeps the repository safe to make public.

Tradeoff: Synthetic data does not prove production performance.

## Decision 5: Support One Denial Family Deeply Rather Than Many Superficially

Context: Denial workflows vary significantly by denial family and payer.

Decision: Focus on `CO-197` authorization-related denials.

Why: This allows the demo to show extraction, validation, contradictions, recommendations, and safe failure handling end to end.

Tradeoff: Unsupported denial codes must route to manual review.

## Decision 6: Use Golden Evaluation Dataset For Regression Testing

Context: AI-adjacent workflows need repeatable checks to avoid silent behavior regressions.

Decision: Create a synthetic golden dataset and run it through the real pipeline.

Why: It makes expected behavior executable and easy to inspect.

Tradeoff: Golden cases must be maintained as functionality expands.

## Decision 7: Keep Proposed Agent Architecture Separate From Current Implementation

Context: The challenge demo is intentionally small, but a reviewer may still want to see production AI engineering judgment.

Decision: Document a proposed production agent/orchestrator architecture separately from the current implementation.

Why: This shows how the system could evolve without overstating what is already built.

Tradeoff: The docs are longer and require careful wording to avoid implying that queues, RAG, Redis, or LangGraph are implemented today.

## Decision 8: Bound Agent Tool Use With A Workflow Graph

Context: An unconstrained agent can loop, call unnecessary tools, or produce recommendations from incomplete evidence.

Decision: A production agent should use an explicit state machine or workflow graph with approved tools, max steps, max tool calls, timeouts, and deterministic terminal states.

Why: Claim-denial decisions need auditability and predictable failure behavior.

Tradeoff: The agent is less flexible than an open-ended assistant, but safer for revenue-cycle workflows.

## Decision 9: Treat Human Review As A Safe Terminal State

Context: Incorrect confident recommendations can create operational and compliance risk.

Decision: Missing evidence, contradictions, unsupported denial families, weak retrieval, and tool failures should route to human review.

Why: Escalating uncertain cases is safer than guessing.

Tradeoff: More cases may require manual review until extraction, validation, and policy coverage mature.

## Decision 10: Evaluate AI Systems Beyond Unit Tests

Context: Unit tests prove code behavior, but AI systems also need extraction, retrieval, grounding, and agent-behavior checks.

Decision: A production CI/CD pipeline should include golden evals, retrieval evals, LLM/agent evals, regression comparison, and safety gates.

Why: Model, prompt, retrieval, and tool changes can regress behavior without breaking ordinary unit tests.

Tradeoff: Evaluation infrastructure adds maintenance work and slows deployment, but catches higher-impact failures.
