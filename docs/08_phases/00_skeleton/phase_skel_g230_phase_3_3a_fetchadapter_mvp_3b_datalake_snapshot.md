# Phase G230: Requirement Gap Closure (WV-007)

## Goal
- Close requirement gap `WV-007` from `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md:13`.

## Requirements
- Requirement ID: WV-007
- Owner Track: skeleton
- Clause: Phase‑3 明确拆为 **3A FetchAdapter MVP / 3B DataLake snapshot / 3C DataCatalog time‑travel**，以便分步闭环。

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
### 1) Execution Strategy
- Perform requirement-gap SSOT writeback only.
- Keep scope documentation-only and constrained to allowed paths.
- Anchor `WV-007` closure to existing split artifacts for fetch adapter and
  snapshot layers (`docs/05_data_plane/wequant_adapter_ingest.md`,
  `docs/05_data_plane/snapshot_catalog_v1.md`,
  `docs/05_data_plane/qa_fetch_asof_availability_summary_contract_v1.md`).

### 2) Concrete Writeback
- Add `goal_checklist` entry `G230` in `docs/12_workflows/skeleton_ssot_v1.yaml`
  with `status_now: implemented`, `track: skeleton`, and task-scoped
  `allowed_paths`/`still_forbidden`.
- Update `requirements_trace_v1` entry `WV-007` in
  `docs/12_workflows/skeleton_ssot_v1.yaml` from `planned` to `implemented`,
  mapped to `G230` with `acceptance_verified: true`.
- Update capability cluster roll-up in `docs/12_workflows/skeleton_ssot_v1.yaml`
  so `CL_LEGACY_CORE` includes `G230`, removes closed requirement `WV-007` from
  pending requirement IDs, and sets `latest_phase_id: G230`.

### 3) Acceptance
- `python3 scripts/check_docs_tree.py`
- `rg -n "G230|WV-007" docs/12_workflows/skeleton_ssot_v1.yaml`

## Execution Record
- Date: 2026-02-14.
- Verified SSOT goal state:
  - `goal_checklist` includes `G230` with `status_now: implemented`.
- Verified SSOT requirement trace state:
  - `requirements_trace_v1` entry `WV-007` has `status_now: implemented`.
  - `requirements_trace_v1` entry `WV-007` maps to `G230`.
- Verified capability cluster roll-up:
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` includes `G230`.
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` no longer lists `WV-007` in
    pending requirement IDs.
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` has `latest_phase_id: G230`.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `rg -n "G230|WV-007" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
