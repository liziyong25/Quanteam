# Phase G226: Requirement Gap Closure (WV-005)

## Goal
- Close requirement gap `WV-005` from `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md:11`.

## Requirements
- Requirement ID: WV-005
- Owner Track: skeleton
- Clause: 明确 **DataAccessFacade + FetchPlanner** 为 Agents 获取数据的唯一通道（禁止 agent 直连 provider/DB）。

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
- Anchor `WV-005` closure to existing data-plane boundary docs that freeze the
  non-bypass data path (`docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md`,
  `docs/05_data_plane/qa_fetch_dataaccess_facade_boundary_v1.md`,
  `docs/05_data_plane/qa_fetch_autosymbols_planner_contract_v1.md`).

### 2) Concrete Writeback
- Add `goal_checklist` entry `G226` in `docs/12_workflows/skeleton_ssot_v1.yaml`
  with `status_now: implemented`, `track: skeleton`, and task-scoped
  `allowed_paths`/`still_forbidden`.
- Update `requirements_trace_v1` entry `WV-005` in
  `docs/12_workflows/skeleton_ssot_v1.yaml` from `planned` to `implemented`,
  mapped to `G226` with `acceptance_verified: true`.
- Update capability cluster roll-up in `docs/12_workflows/skeleton_ssot_v1.yaml`
  so `CL_LEGACY_CORE` includes `G226` and has `latest_phase_id: G226`.

### 3) Acceptance
- `python3 scripts/check_docs_tree.py`
- `rg -n "G226|WV-005" docs/12_workflows/skeleton_ssot_v1.yaml`

## Execution Record
- Date: 2026-02-14.
- Verified SSOT goal state:
  - `goal_checklist` includes `G226` with `status_now: implemented`.
- Verified SSOT requirement trace state:
  - `requirements_trace_v1` entry `WV-005` has `status_now: implemented`.
  - `requirements_trace_v1` entry `WV-005` maps to `G226`.
- Verified capability cluster roll-up:
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` includes `G226`.
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` has `latest_phase_id: G226`.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `rg -n "G226|WV-005" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
