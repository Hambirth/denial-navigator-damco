# Phase 2 Scope

## Goal

Build a minimal sanitized Denial Navigator demo for the Damco AI Engineer challenge.

The first implemented denial scenario is `CO-197`, an authorization-related denial.

## Included Flow

```txt
Synthetic denied claim
-> structured claim/evidence intake
-> deterministic evidence validation
-> denial classification
-> deterministic decision logic
-> structured recommendation
```

## Deterministic Checks

- Patient name match
- Member ID match
- Payer match
- Provider NPI match
- Provider name match
- Authorization number present
- Claim date of service inside authorization effective date range
- Billed CPT included in approved authorization CPTs

## LLM Usage

No LLM call is required in Phase 2. The API includes a `use_llm_reasoning` request flag for future extension, but factual validation is deterministic.

## Synthetic Fixtures

- `valid-authorization.json`
- `dos-mismatch.json`
- `missing-authorization.json`

All demo values use synthetic identifiers such as `Demo Patient`, `DEMO-CLM-001`, `AUTH-DEMO-001`, and `DEMO-MEMBER-001`.
