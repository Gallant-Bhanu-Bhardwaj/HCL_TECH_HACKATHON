# Ujjwal Rail — AI-Powered Train Travel Assistant

HCLTech Future Ready AI Engineer Hackathon submission. This README is a
Phase 0 skeleton; sections below are filled in through Phase 1–5 by
their owning module (see `docs/architecture.md` §7).

**Status:** Phase 0 (repository skeleton, shared contracts, SQLite
schema, settings registry, stub API) is implemented on `phase0/skeleton`.
No business logic, RAG, LLM, UI or dataset generation yet.

## Team

Five contributors: RAG, Backend, AI/LLM, Frontend, Data & Testing
Engineer. The official hackathon guide (`docs/*.docx`, §1) states a team
of up to 4; the organizers separately permitted five for this team
(architecture.md D1). Each member is still assessed individually per
§9.4 of the guide and signs their own declaration of original work
(§8 of the guide).

*To be completed in Phase 5:* who built what, per-member contributions.

## Design documents

* [docs/architecture.md](docs/architecture.md) — approved architecture (v1.2)
* [docs/api-contracts.md](docs/api-contracts.md) — approved API & module contracts (v1.2)
* [docs/phase0-tasks.md](docs/phase0-tasks.md) — Phase 0 task plan

## Running (Phase 0)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # MOCK_LLM=true by default
uvicorn app.main:app --reload
# in another shell:
pytest
```

`docker compose up` and the Streamlit UI arrive once Backend/Frontend
implement the real services behind the Phase 0 contracts (Phase 1+).

## What's real right now

* All 7 contract endpoints respond with contract-valid, mostly-canned
  data from the fakes in `tests/fakes/` (not real trains/fares/refunds yet).
* `db/schema.sql` creates the full mandatory + approved-additive schema.
* `/ingest` really validates `settings_changes` against the registered
  key list (`app/contracts/settings_keys.py`) — document text ingestion
  itself is stubbed pending the RAG parser.

## Stack deviations from the guide's §5 suggestion

None yet. Phase 0 uses only FastAPI/Pydantic/pytest/httpx, all on the
guide's suggested stack.

## AI tooling disclosure

*To be completed as the project proceeds (guide §8 "a note on which
parts were written with AI tools").* This repository's Phase 0 skeleton,
shared contracts, SQLite schema and the architecture/API-contract
documents were drafted with Claude Code (Anthropic) under direct human
review and approval at each step (see `docs/architecture.md` decision
log, §3).
