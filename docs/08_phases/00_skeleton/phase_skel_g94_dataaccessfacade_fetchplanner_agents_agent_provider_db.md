# Phase G94: Requirement Gap Closure (WV-005)

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
- Perform requirement-gap writeback only.
- Keep scope documentation-only and limited to allowed paths.
- Anchor WV-005 closure to existing single-channel fetch governance docs (`qa_fetch_dataaccess_facade_boundary_v1.md`, `qa_fetch_autosymbols_planner_contract_v1.md`, `QA_Fetch_FetchData_Impl_Spec_v1.md`) without touching `contracts/**` or runtime code.

### 2) Concrete Writeback
- Add `goal_checklist` entry `G94` in `docs/12_workflows/skeleton_ssot_v1.yaml` with `status_now: implemented`.
- Update `requirements_trace_v1` entry `WV-005` in `docs/12_workflows/skeleton_ssot_v1.yaml` from `planned` to `implemented`, and map it to `G94`.
- Update capability cluster roll-up in `docs/12_workflows/skeleton_ssot_v1.yaml` so `CL_LEGACY_CORE` includes `G94` and points `latest_phase_id` to `G94`.

### 3) Acceptance
- `python3 scripts/check_docs_tree.py`
- `rg -n "G94|WV-005" docs/12_workflows/skeleton_ssot_v1.yaml`

## Execution Record
- Date: 2026-02-13.
- Verified SSOT goal state:
  - `goal_checklist` includes `G94` with `status_now: implemented`.
- Verified SSOT requirement trace state:
  - `requirements_trace_v1` entry `WV-005` has `status_now: implemented`.
  - `requirements_trace_v1` entry `WV-005` maps to `G94`.
- Verified capability cluster roll-up:
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` includes `G94`.
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` has `latest_phase_id: G94`.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `rg -n "G94|WV-005" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
