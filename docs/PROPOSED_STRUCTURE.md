# Proposed Directory Structure

```txt
denial-navigator-damco/
  apps/
    web/
      # Next.js UI for the Denial Navigator challenge demo
    api/
      app/
        routers/
          # FastAPI routes: extraction, analysis, decision
        services/
          # Extraction, validation, classification, reasoning
        schemas/
          # Pydantic request/response models
  packages/
    shared/
      # Shared decision schemas and constants
  demo-data/
    synthetic/
      # Synthetic claim/EOB/network/auth examples only
  docs/
      # Architecture and security documentation
  scripts/
      # Local setup, test, and pre-public audit scripts
  tests/
    api/
    fixtures/
```

## Source Concepts Rebuilt For The Challenge

- Denial workbench flow: source document view, extracted evidence, validation result view.
- FastAPI denial analysis router.
- EOB extraction concepts: deterministic labelled-field extraction, source tracking, confidence.
- Authorization extraction and authorization-to-claim matching.
- Claim linkage validation.
- Workflow action engine.
- Structured recommendation output.

## Components To Exclude From Public Challenge Version

- Patient management portal.
- User/admin auth product flow.
- OAuth.
- Cloud uploads.
- Production database integration.
- MCP/direct action server.
- Payer-specific proprietary PDF templates.
- Existing uploads, sample PDFs, generated claim PDFs, and any PDF whose data provenance is not guaranteed synthetic.
- Private `.env` files and all Git history.
