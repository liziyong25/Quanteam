# Phase G171: Requirement Gap Closure (WV-051)

## Goal
- Close requirement gap `WV-051` from `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md:87`.

## Requirements
- Requirement ID: WV-051
- Owner Track: skeleton
- Clause: Quant‑EAM Whole View Framework（v0.5‑draft / Fetch‑Integrated Mainline） / 3. Whole View 工作流（UI Checkpoint 驱动的状态机） / Phase‑2：Demo Tests（小样本可视化验证）

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
- Anchor `WV-051` closure to SSOT requirement trace and goal linkage, with clause
  coverage fixed as: Quant‑EAM Whole View Framework（v0.5‑draft / Fetch‑Integrated
  Mainline） / 3. Whole View 工作流（UI Checkpoint 驱动的状态机） / Phase‑2：Demo
  Tests（小样本可视化验证）.

### 2) Concrete Writeback
- Add `goal_checklist` entry `G171` in `docs/12_workflows/skeleton_ssot_v1.yaml`
  with `status_now: implemented`.
- Update `requirements_trace_v1` entry `WV-051` in
  `docs/12_workflows/skeleton_ssot_v1.yaml` from `planned` to `implemented`,
  mapped to `G171`.
- Preserve capability cluster linkage in `docs/12_workflows/skeleton_ssot_v1.yaml`
  with `CL_LEGACY_CORE` including `G171` and `latest_phase_id: G171`.

### 3) Acceptance
- `python3 scripts/check_docs_tree.py`
- `rg -n "G171|WV-051" docs/12_workflows/skeleton_ssot_v1.yaml`

## Execution Record
- Date: 2026-02-14.
- Verified SSOT goal state:
  - `goal_checklist` includes `G171` with `status_now: implemented`.
- Verified SSOT requirement trace state:
  - `requirements_trace_v1` entry `WV-051` has `status_now: implemented`.
  - `requirements_trace_v1` entry `WV-051` maps to `G171`.
- Verified capability cluster roll-up:
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` includes `G171`.
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` has `latest_phase_id: G171`.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `rg -n "G171|WV-051" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
