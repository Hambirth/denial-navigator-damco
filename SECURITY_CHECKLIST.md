# Security Checklist Before Public Release

Complete every item before this repository is made public.

## Repository Isolation

- [ ] Confirm this repository was created without copying `.git` directories.
- [ ] Confirm this repository has fresh Git history only.
- [ ] Confirm no private remotes from source repositories are configured.
- [ ] Confirm no private branch names or internal deployment URLs are required.

## Secrets

- [ ] Confirm no `.env` files exist except `.env.example`.
- [ ] Confirm `.env.example` contains placeholder values only.
- [ ] Confirm no OpenAI, Pinecone, Supabase, MongoDB, OAuth, JWT, session, or service-role secrets are present.
- [ ] Rotate any secret that was ever committed in a source system before using this public repo.
- [ ] Run a secret scanner before first public push.
- [ ] Confirm `REASONING_MODE=deterministic` remains the default and no LLM key is required for tests.

## Data / PHI / PII

- [ ] Confirm no real patient names, dates of birth, phone numbers, email addresses, addresses, MRNs, member IDs, claim numbers, auth numbers, NPIs, TINs, or payer identifiers are present.
- [ ] Confirm all demo data is synthetic and clearly labeled as synthetic.
- [ ] Confirm no uploaded PDFs, generated PDFs, screenshots, database dumps, vector exports, or logs are present.
- [ ] Confirm no Pinecone metadata or retrieved document chunks from private data are copied.

## Documents And Templates

- [ ] Confirm no proprietary payer documents are included unless redistribution rights are clear.
- [ ] Prefer generated mock PDFs or text fixtures for the challenge demo.
- [ ] Confirm generated fixtures do not resemble real people or real claims.

## Application Security

- [ ] Add request-size limits for document upload endpoints.
- [ ] Restrict CORS to local/demo domains.
- [ ] Avoid exposing arbitrary URL proxy endpoints.
- [ ] Avoid logging full document text or patient fields.
- [ ] Validate LLM outputs with schemas.
- [ ] Confirm LLM summaries cannot mutate recommendation, confidence, evidence status, contradictions, or human-review routing.
- [ ] Return structured decisions with evidence references and confidence.
- [ ] Make hallucination/uncertainty behavior explicit.
- [ ] Upgrade frontend dependencies before public release if `npm install` reports security advisories.

## Public Presentation

- [ ] Add architecture diagram.
- [ ] Add local setup instructions.
- [ ] Add synthetic demo walkthrough.
- [ ] Add limitations and safety note.
- [ ] Add tests or evaluation fixtures showing expected decisions.
