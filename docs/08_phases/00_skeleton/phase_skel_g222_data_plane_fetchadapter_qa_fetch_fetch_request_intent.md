# Phase G222: Requirement Gap Closure (WV-003)

## Goal
- Close requirement gap `WV-003` from `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md:9`.

## Requirements
- Requirement ID: WV-003
- Owner Track: skeleton
- Clause: **Data Plane 主路引入 FetchAdapter（qa_fetch）**：统一入口为 `fetch_request(intent)`，并规定证据落盘与 UI 审阅。

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
- Anchor `WV-003` closure to explicit SSOT goal linkage while preserving existing
  requirement dependency ordering.

### 2) Concrete Writeback
- Add `goal_checklist` entry `G222` in `docs/12_workflows/skeleton_ssot_v1.yaml`
  with `status_now: implemented`, `track: skeleton`, and task-scoped
  `allowed_paths`/`still_forbidden`.
- Update `requirements_trace_v1` entry `WV-003` in
  `docs/12_workflows/skeleton_ssot_v1.yaml` from `planned` to `implemented`,
  mapped to `G222` with `acceptance_verified: true`.
- Preserve capability cluster roll-up in
  `docs/12_workflows/skeleton_ssot_v1.yaml` with `CL_LEGACY_CORE` including
  `G222` and `latest_phase_id: G222`.

### 3) Acceptance
- `python3 scripts/check_docs_tree.py`
- `rg -n "G222|WV-003" docs/12_workflows/skeleton_ssot_v1.yaml`

## Execution Record
- Date: 2026-02-14.
- Verified SSOT goal state:
  - `goal_checklist` includes `G222` with `status_now: implemented`.
- Verified SSOT requirement trace state:
  - `requirements_trace_v1` entry `WV-003` has `status_now: implemented`.
  - `requirements_trace_v1` entry `WV-003` maps to `G222`.
- Verified capability cluster roll-up:
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` includes `G222`.
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` has `latest_phase_id: G222`.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `rg -n "G222|WV-003" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
