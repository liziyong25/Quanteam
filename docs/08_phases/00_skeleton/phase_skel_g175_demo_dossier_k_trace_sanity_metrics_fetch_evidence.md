# Phase G175: Requirement Gap Closure (WV-054)

## Goal
- Close requirement gap `WV-054` from `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md:90`.

## Requirements
- Requirement ID: WV-054
- Owner Track: skeleton
- Clause: 产物：demo_dossier（K 线叠加 + trace 表 + sanity metrics + fetch evidence）

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
- Anchor `WV-054` closure to SSOT requirement trace and goal linkage, with clause
  coverage fixed as: 产物：demo_dossier（K 线叠加 + trace 表 + sanity metrics + fetch evidence）.

### 2) Concrete Writeback
- Add `goal_checklist` entry `G175` in `docs/12_workflows/skeleton_ssot_v1.yaml`
  with `status_now: implemented`.
- Update `requirements_trace_v1` entry `WV-054` in
  `docs/12_workflows/skeleton_ssot_v1.yaml` from `planned` to `implemented`,
  mapped to `G175`.
- Preserve capability cluster linkage in `docs/12_workflows/skeleton_ssot_v1.yaml`
  with `CL_LEGACY_CORE` including `G175` and `latest_phase_id: G175`.

### 3) Acceptance
- `python3 scripts/check_docs_tree.py`
- `rg -n "G175|WV-054" docs/12_workflows/skeleton_ssot_v1.yaml`

## Execution Record
- Date: 2026-02-14.
- Verified SSOT goal state:
  - `goal_checklist` includes `G175` with `status_now: implemented`.
- Verified SSOT requirement trace state:
  - `requirements_trace_v1` entry `WV-054` has `status_now: implemented`.
  - `requirements_trace_v1` entry `WV-054` maps to `G175`.
- Verified capability cluster roll-up:
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` includes `G175`.
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` has `latest_phase_id: G175`.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `rg -n "G175|WV-054" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
