# Phase G307: Requirement Gap Closure (QF-062)

## Goal
- Close requirement gap `QF-062` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:117`.
- Implement QF-062 §4.2 in runtime evidence emission: multi-step Dossier evidence must carry explicit and auditable `step_index`.

## Requirements
- Requirement IDs: QF-062
- Owner Track: impl_fetchdata
- Clause[QF-062]: QA‑Fetch FetchData Implementation Spec (v1) / 4. Evidence Bundle 规范（必须进入 Dossier） / 4.2 多步证据（step index）
- Dependency: `G306` must be completed first; reuse G306 single-step evidence outputs (`fetch_request.json`, `fetch_result_meta.json`, `fetch_preview.csv`, `fetch_error.json`) as the base bundle contract.

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.
- Bundling criterion: same owner track + same source document + same parent requirement + near-adjacent source lines.
- G307 extends G306 by enforcing ordered multi-step evidence indexing on top of the existing evidence bundle writer and dossier path layout.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.
- Multi-step `fetch_steps_index.json` entries contain explicit contiguous `step_index` values and deterministic step-file paths under `artifacts/dossiers/<run_id>/fetch/`.

## Implementation Plan
TBD by controller at execution time.
