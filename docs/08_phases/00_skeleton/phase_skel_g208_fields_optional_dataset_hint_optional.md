# Phase G208: Requirement Gap Closure (WV-072)

## Goal
- Close requirement gap `WV-072` from `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md:119`.

## Requirements
- Requirement ID: WV-072
- Owner Track: skeleton
- Clause: fields(optional), dataset_hint(optional)

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
- Anchor `WV-072` closure to SSOT goal linkage and requirement trace with clause
  coverage fixed as: `fields(optional), dataset_hint(optional)`.

### 2) Concrete Writeback
- Add `goal_checklist` entry `G208` in `docs/12_workflows/skeleton_ssot_v1.yaml`
  with `status_now: implemented`.
- Update `requirements_trace_v1` entry `WV-072` in
  `docs/12_workflows/skeleton_ssot_v1.yaml` from `planned` to `implemented`,
  mapped to `G208`.
- Preserve capability cluster roll-up in
  `docs/12_workflows/skeleton_ssot_v1.yaml` with `CL_LEGACY_CORE` including
  `G208` and `latest_phase_id: G208`.

### 3) Acceptance
- `python3 scripts/check_docs_tree.py`
- `rg -n "G208|WV-072" docs/12_workflows/skeleton_ssot_v1.yaml`

## Execution Record
- Date: 2026-02-14.
- Verified SSOT goal state:
  - `goal_checklist` includes `G208` with `status_now: implemented`.
- Verified SSOT requirement trace state:
  - `requirements_trace_v1` entry `WV-072` has `status_now: implemented`.
  - `requirements_trace_v1` entry `WV-072` maps to `G208`.
- Verified capability cluster roll-up:
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` includes `G208`.
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` has `latest_phase_id: G208`.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `rg -n "G208|WV-072" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
