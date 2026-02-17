# Phase G167: Requirement Gap Closure (WV-047)

## Goal
- Close requirement gap `WV-047` from `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md:82`.

## Requirements
- Requirement ID: WV-047
- Owner Track: skeleton
- Clause: calc_trace_plan.json（demo 如何抽样、画图、表格列、断言）

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
- Keep scope documentation-only and constrained to allowed paths.
- Anchor `WV-047` closure to SSOT requirement trace and goal linkage, with clause
  coverage fixed as: calc_trace_plan.json（demo 如何抽样、画图、表格列、断言）.

### 2) Concrete Writeback
- Add `goal_checklist` entry `G167` in `docs/12_workflows/skeleton_ssot_v1.yaml`
  with `status_now: implemented`.
- Update `requirements_trace_v1` entry `WV-047` in
  `docs/12_workflows/skeleton_ssot_v1.yaml` from `planned` to `implemented`,
  mapped to `G167`.
- Preserve capability cluster linkage in `docs/12_workflows/skeleton_ssot_v1.yaml`
  with `CL_LEGACY_CORE` including `G167` and `latest_phase_id: G167`.

### 3) Acceptance
- `python3 scripts/check_docs_tree.py`
- `rg -n "G167|WV-047" docs/12_workflows/skeleton_ssot_v1.yaml`

## Execution Record
- Date: 2026-02-14.
- Verified SSOT goal state:
  - `goal_checklist` includes `G167` with `status_now: implemented`.
- Verified SSOT requirement trace state:
  - `requirements_trace_v1` entry `WV-047` has `status_now: implemented`.
  - `requirements_trace_v1` entry `WV-047` maps to `G167`.
- Verified capability cluster roll-up:
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` includes `G167`.
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` has `latest_phase_id: G167`.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `rg -n "G167|WV-047" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
