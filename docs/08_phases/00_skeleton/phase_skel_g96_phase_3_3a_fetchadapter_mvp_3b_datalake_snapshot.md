# Phase G96: Requirement Gap Closure (WV-007)

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
- Perform requirement-gap writeback only.
- Keep scope documentation-only and limited to allowed paths.
- Anchor WV-007 clause closure to existing phase split docs (`phase_03_data_plane_mvp.md`, `phase_03b_wequant_adapter_ingest.md`, `wequant_adapter_ingest.md`, `snapshot_catalog_v1.md`) without touching contracts/policies/runtime code.

### 2) Concrete Writeback
- Add `goal_checklist` entry `G96` in `docs/12_workflows/skeleton_ssot_v1.yaml` with `status_now: implemented`.
- Update `requirements_trace_v1` entry `WV-007` in `docs/12_workflows/skeleton_ssot_v1.yaml` from `planned` to `implemented`, and map it to `G96`.
- Update capability cluster roll-up in `docs/12_workflows/skeleton_ssot_v1.yaml` so `CL_LEGACY_CORE` includes `G96` and points `latest_phase_id` to `G96`.

### 3) Acceptance
- `python3 scripts/check_docs_tree.py`
- `rg -n "G96|WV-007" docs/12_workflows/skeleton_ssot_v1.yaml`

## Execution Record
- Date: 2026-02-13.
- Verified SSOT goal state:
  - `goal_checklist` includes `G96` with `status_now: implemented`.
- Verified SSOT requirement trace state:
  - `requirements_trace_v1` entry `WV-007` has `status_now: implemented`.
  - `requirements_trace_v1` entry `WV-007` maps to `G96`.
- Verified capability cluster roll-up:
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` includes `G96`.
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` has `latest_phase_id: G96`.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `rg -n "G96|WV-007" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
