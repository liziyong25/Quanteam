# Phase-07: Registry v1 (TrialLog + Experience Cards)

## Goal

- Add a file-based append-only Registry:
  - TrialLog (all runs)
  - Experience Cards (created only from Gate PASS runs)

## Scope

In scope:

- Registry storage layout and APIs
- Contracts for TrialEvent and ExperienceCard
- CLI for recording trials and managing cards
- Offline tests and docs

Out of scope:

- UI
- Composer/Allocator
- Agents/LLM
- Database (v1 uses JSON/JSONL files only)

## Deliverables

- `contracts/trial_event_schema_v1.json`
- `contracts/experience_card_schema_v1.json`
- `src/quant_eam/registry/**`
- `docs/09_registry/**`

## Acceptance

- TrialLog is append-only and idempotent by run_id
- Experience Card creation requires Gate PASS and references dossier/gate_results evidence
- `pytest -q` passes offline
- docs tree check passes

## Execution Log

- Start Date (Asia/Taipei): 2026-02-10
- End Date (Asia/Taipei): 2026-02-10
- Commit: unknown (repo has no git metadata or HEAD not available)

Notes:

- Implemented file-based Registry root `EAM_REGISTRY_ROOT` (default `${EAM_ARTIFACT_ROOT}/registry`).
- TrialLog: `trial_log.jsonl` append-only with `trial_event_v1` contract.
- Cards: immutable `card_v1.json` + append-only `events.jsonl` for promotions.
- Enforced "Gate PASS required" for card creation (no text arbitration).

