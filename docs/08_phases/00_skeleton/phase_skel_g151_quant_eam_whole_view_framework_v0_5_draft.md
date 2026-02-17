# Phase G151: Requirement Gap Closure (WV-036)

## Goal
- Close requirement gap `WV-036` from `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md:67`.

## Requirements
- Requirement ID: WV-036
- Owner Track: skeleton
- Clause: Quant‑EAM Whole View Framework（v0.5‑draft / Fetch‑Integrated Mainline） / 3. Whole View 工作流（UI Checkpoint 驱动的状态机） / Phase‑0：Idea → Blueprint Draft（拆想法）

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
- Anchor `WV-036` closure to SSOT requirement trace and goal linkage, with clause
  coverage fixed as: Quant‑EAM Whole View Framework（v0.5‑draft / Fetch‑Integrated
  Mainline） / 3. Whole View 工作流（UI Checkpoint 驱动的状态机） / Phase‑0：Idea →
  Blueprint Draft（拆想法）.

### 2) Concrete Writeback
- Add `goal_checklist` entry `G151` in `docs/12_workflows/skeleton_ssot_v1.yaml`
  with `status_now: implemented`.
- Update `requirements_trace_v1` entry `WV-036` in
  `docs/12_workflows/skeleton_ssot_v1.yaml` from `planned` to `implemented`,
  mapped to `G151`.
- Preserve capability cluster linkage in `docs/12_workflows/skeleton_ssot_v1.yaml`
  with `CL_LEGACY_CORE` including `G151`.

### 3) Acceptance
- `python3 scripts/check_docs_tree.py`
- `rg -n "G151|WV-036" docs/12_workflows/skeleton_ssot_v1.yaml`

## Execution Record
- Date: 2026-02-14.
- Verified SSOT goal state:
  - `goal_checklist` includes `G151` with `status_now: implemented`.
- Verified SSOT requirement trace state:
  - `requirements_trace_v1` entry `WV-036` has `status_now: implemented`.
  - `requirements_trace_v1` entry `WV-036` maps to `G151`.
- Verified capability cluster roll-up:
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` includes `G151`.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `rg -n "G151|WV-036" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
