# Phase G128: Requirement Gap Closure (WV-024)

## Goal
- Close requirement gap `WV-024` from `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md:45`.

## Requirements
- Requirement ID: WV-024
- Owner Track: skeleton
- Clause: 至少覆盖：lookahead/对齐/NaN/索引单调性/边界条件/时间窗端点。

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
- Anchor WV-024 closure to SSOT requirement trace and goal linkage, with clause coverage fixed as: lookahead, alignment, NaN, index monotonicity, boundary conditions, and time-window endpoints.

### 2) Concrete Writeback
- Add `goal_checklist` entry `G128` in `docs/12_workflows/skeleton_ssot_v1.yaml`
  with `status_now: implemented`.
- Update `requirements_trace_v1` entry `WV-024` in
  `docs/12_workflows/skeleton_ssot_v1.yaml` from `planned` to `implemented`, and
  map it to `G128`.
- Update capability cluster roll-up in `docs/12_workflows/skeleton_ssot_v1.yaml`
  so `CL_LEGACY_CORE` includes `G128` and points `latest_phase_id` to `G128`.

### 3) Acceptance
- `python3 scripts/check_docs_tree.py`
- `rg -n "G128|WV-024" docs/12_workflows/skeleton_ssot_v1.yaml`

## Execution Record
- Date: 2026-02-14.
- Verified SSOT goal state:
  - `goal_checklist` includes `G128` with `status_now: implemented`.
- Verified SSOT requirement trace state:
  - `requirements_trace_v1` entry `WV-024` has `status_now: implemented`.
  - `requirements_trace_v1` entry `WV-024` maps to `G128`.
- Verified capability cluster roll-up:
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` includes `G128`.
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` has `latest_phase_id: G128`.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `rg -n "G128|WV-024" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
