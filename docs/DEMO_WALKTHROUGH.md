# Demo Walkthrough

Target length: about 7 minutes.

## 0:00-0:45 Problem And Background

This project is about healthcare claim denials, specifically `CO-197` authorization denials.

The key idea is that the denial code is not enough. `CO-197` may say authorization is missing, but the provider may actually have a valid authorization letter. The real question is whether the evidence matches the denied claim: payer, member, provider, CPT, date of service, and authorization dates.

I built this because denial work is evidence-heavy, repetitive, and easy to get wrong if a system jumps straight from code to recommendation.

## 0:45-2:30 Live Demo: Valid Authorization

Open the app and select the valid authorization scenario.

Point out:

- source EOB text
- source authorization text
- extracted claim fields
- extracted authorization fields
- validation rows marked matched
- recommendation: `reprocess`
- confidence: high
- human review: not required for the demo decision
- reasoning source: deterministic

Explain that the system recommends reprocessing because all core evidence matches. The payer denial likely reflects an authorization linkage or processing issue.

## 2:30-3:30 Edge Case: DOS Mismatch

Switch to the DOS mismatch scenario.

Point out:

- authorization evidence exists
- authorization number is present
- member, payer, provider, and CPT may match
- date of service is outside the authorization effective range
- contradiction is recorded
- recommendation changes to `manual_review`

Explain that this is the key safety behavior. The system does not say valid authorization just because an authorization document exists.

## 3:30-5:00 Architecture And Code Flow

Walk through the pipeline:

```txt
Next.js UI
-> FastAPI endpoint
-> evidence extractor
-> typed evidence bundle
-> deterministic validators
-> decision engine
-> reasoning service
-> structured response
```

Mention the most important files:

- `apps/api/app/services/evidence_extractor.py`
- `apps/api/app/services/decision_engine.py`
- `apps/api/app/services/reasoning_service.py`
- `tests/evals/golden_cases.json`
- `scripts/run_evals.py`

## 5:00-6:00 Why Deterministic Validation Instead Of LLM-Only

Facts like date ranges, CPT matching, payer matching, provider matching, missing evidence, and contradictions are not good places to rely on an LLM.

The LLM can be useful for explaining validated facts, but it should not decide whether a date is inside an authorization range or whether a CPT matches.

The default mode is deterministic. If optional LLM mode fails or returns malformed output, the system falls back to deterministic reasoning.

## 6:00-6:45 Evaluation

Run:

```bash
python3 -m pytest
python3 scripts/run_evals.py
```

Explain:

- 30 automated tests
- 12 synthetic golden eval cases
- tests cover valid auth, DOS mismatch, CPT mismatch, payer/provider/member mismatch, missing evidence, malformed dates, unsupported denials, and LLM failures
- current synthetic golden pass rate is 100%

Be clear that this is synthetic evaluation, not production performance.

## 6:45-7:30 Limitations And Production Improvements

Current limitations:

- only `CO-197`
- synthetic labelled text
- no OCR
- no production payer policy system
- no production RAG
- no expert-labelled historical evaluation

Production evolution:

- de-identified historical claims
- payer-specific rule/versioning
- OCR and stronger extraction
- source citations
- human-in-the-loop workflow
- audit trails
- authentication and tenant isolation
- broader denial family coverage
- latency and cost monitoring
