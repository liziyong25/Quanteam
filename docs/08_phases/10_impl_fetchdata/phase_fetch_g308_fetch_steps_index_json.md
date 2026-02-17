# Phase G308: Requirement Gap Closure (QF-063)

## Goal
- Close requirement gap `QF-063` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:119`.
- Freeze runtime emission contract so `fetch_steps_index.json` is deterministic and reviewable under `artifacts/dossiers/<run_id>/fetch/`.

## Requirements
- Requirement IDs: QF-063
- Owner Track: impl_fetchdata
- Clause[QF-063]: fetch_steps_index.json
- Dependency: `G307` must already be implemented; reuse its multi-step `step_index` evidence baseline and add filename/index-contract hardening.

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.
- Bundling criterion: same owner track + same source document + same parent requirement + near-adjacent source lines.
- Runtime writes `fetch_steps_index.json` for both single-step and multi-step evidence bundles, with deterministic ordered entries and stable step artifact paths.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.
- `fetch_steps_index.json` filename contract is enforced at Dossier path and validated by runtime tests for contiguous `step_index` + deterministic path semantics.

## Implementation Plan
TBD by controller at execution time.
