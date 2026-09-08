# Evaluation System

This project uses a small synthetic golden dataset to prove that the denial-analysis pipeline behaves predictably across important CO-197 authorization scenarios.

Golden datasets matter because they turn expected product behavior into executable checks. They are especially useful for AI workflows because they catch silent regressions in extraction, validation, recommendations, and safe failure handling.

## What Is Evaluated

The evaluator runs each case through the real application pipeline:

```txt
synthetic EOB/auth text
-> deterministic extraction
-> typed evidence
-> deterministic validation
-> structured decision
-> grounded reasoning metadata
```

The runner does not duplicate decision logic. It calls the same extractor and decision engine used by the API.

Current golden checks:

- recommended action
- human-review routing
- contradiction detection
- missing-evidence detection
- expected matched fields
- safe handling of malformed or incomplete source text

## Current Dataset

The dataset lives at:

```txt
tests/evals/golden_cases.json
```

It contains 12 synthetic cases:

- valid authorization
- DOS before authorization effective date
- DOS after authorization expiration date
- CPT mismatch
- payer mismatch
- provider mismatch
- member mismatch
- missing authorization
- missing DOS
- malformed authorization dates
- multiple mismatches
- second fully valid claim with valid authorization

## Running Evals

```bash
python3 scripts/run_evals.py
```

Current expected output:

```txt
Cases: 12
Recommended Action Accuracy: 100.0%
Human Review Accuracy: 100.0%
Contradiction Detection: 100.0%
Missing Evidence Detection: 100.0%
Field Validation Accuracy: 100.0%
Safe Error Handling: 100.0%
Overall Golden Case Pass Rate: 100.0%
```

Pytest also gates the evals:

```bash
python3 -m pytest
```

Current thresholds:

- recommended action accuracy >= 90%
- human-review accuracy >= 95%
- missing-evidence accuracy >= 95%
- safe error handling >= 95%
- overall golden pass rate >= 95%

## Confidence Rules

Confidence is deterministic. The LLM never generates or changes confidence.

For matched authorization evidence, confidence is calculated from validation checks:

```txt
matched_count / total_checks
- 0.08 for each mismatched field
- 0.12 for each missing field
```

The value is clamped at 0.0 and rounded to two decimals.

Operational interpretation:

- High confidence: all required evidence matches.
- Medium confidence: a non-critical field is missing or limited mismatch exists.
- Low confidence: critical evidence is missing, contradictions exist, or the denial family is unsupported.

Special low-confidence cases:

- missing authorization evidence: 0.20
- unsupported denial family: 0.10
- no validation checks available: 0.10

## Safe Failure Behavior

The system should not crash or invent evidence when inputs are malformed.

Current safe failures include:

- malformed request body -> FastAPI 422
- empty EOB/source text -> FastAPI 422
- missing EOB -> FastAPI 422
- missing required extracted field -> extraction 422
- malformed dates -> extraction 422
- unexpected denial code -> structured `supported: false` manual review response
- reasoning service exception -> deterministic fallback
- simulated LLM timeout -> deterministic fallback
- malformed LLM response -> deterministic fallback

## Production Release Blockers

This evaluation setup is credible for a challenge demo, but it is not a production evaluation system.

Production release should be blocked until the project has:

- de-identified historical cases
- RCM expert labels, and clinician labels where clinically relevant
- payer-specific slices
- denial-code family coverage beyond CO-197
- regression tracking over time
- grounding and citation checks for document-based claims
- latency and cost monitoring
- adversarial and malformed-document testing
- privacy review for logging and retention

## Limitations

The current dataset is synthetic and intentionally small. It proves deterministic behavior for core demo cases, not real-world generalization.

This project does not currently include OCR, uploaded PDFs, production RAG, payer-specific policy retrieval, external payer integrations, or production storage.
