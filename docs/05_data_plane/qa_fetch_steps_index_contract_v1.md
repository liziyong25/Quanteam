# QA Fetch Steps Index Contract v1

## Purpose

Define a stable, machine-readable multi-step fetch evidence index so review checkpoints can trace list-to-day planning without source inspection.

## Contract

- File: `fetch_steps_index.json`
- Emission rule:
  - MUST exist for every fetch evidence bundle.
  - Dossier mode MUST emit at `artifacts/dossiers/<run_id>/fetch/fetch_steps_index.json`.
  - Single-step execution writes one step entry (`step_index=1`).
  - Multi-step planning appends additional step entries in order.

## Schema (logical)

- `schema_version`: fixed string, `qa_fetch_steps_index_v1`
- `generated_at`: UTC ISO-8601 timestamp
- `steps`: ordered array
  - `step_index`: positive integer, contiguous from 1..N (no gaps/duplicates)
  - `step_kind`: enum-like text (e.g., `single_fetch`, `list`, `sample`, `day`)
  - `status`: mirrors runtime status semantics (`pass_has_data`, `pass_empty`, `blocked_source_missing`, `error_runtime`)
  - `request_path`: deterministic path to request evidence
  - `result_meta_path`: deterministic path to result meta evidence
  - `preview_path`: deterministic path to preview evidence
  - `error_path`: optional, present when failure evidence exists

## Governance

- Paths must remain stable and deterministic for replay and packet validation.
- Contract is read-only governance evidence in skeleton track; runtime enforcement belongs to impl track goals.
- Freeze record: accepted by G66 unattended autopilot phase execution.
