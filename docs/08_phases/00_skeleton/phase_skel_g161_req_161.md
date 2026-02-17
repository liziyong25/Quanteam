# Phase G161: Requirement Gap Closure (WV-043)

## Goal
- Close requirement gap `WV-043` from `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md:74`.

## Requirements
- Requirement ID: WV-043
- Owner Track: skeleton
- Clause: 预算（候选数、参数网格）

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
- Anchor `WV-043` closure to SSOT requirement trace and goal linkage, with clause
  coverage fixed as: 预算（候选数、参数网格）.

### 2) Concrete Writeback
- Add `goal_checklist` entry `G161` in `docs/12_workflows/skeleton_ssot_v1.yaml`
  with `status_now: implemented`.
- Update `requirements_trace_v1` entry `WV-043` in
  `docs/12_workflows/skeleton_ssot_v1.yaml` from `planned` to `implemented`,
  mapped to `G161`.
- Preserve capability cluster linkage in `docs/12_workflows/skeleton_ssot_v1.yaml`
  with `CL_LEGACY_CORE` including `G161` and `latest_phase_id: G161`.

### 3) Acceptance
- `python3 scripts/check_docs_tree.py`
- `rg -n "G161|WV-043" docs/12_workflows/skeleton_ssot_v1.yaml`

## Execution Record
- Date: 2026-02-14.
- Verified SSOT goal state:
  - `goal_checklist` includes `G161` with `status_now: implemented`.
- Verified SSOT requirement trace state:
  - `requirements_trace_v1` entry `WV-043` has `status_now: implemented`.
  - `requirements_trace_v1` entry `WV-043` maps to `G161`.
- Verified capability cluster roll-up:
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` includes `G161`.
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` has `latest_phase_id: G161`.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `rg -n "G161|WV-043" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
