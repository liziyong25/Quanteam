# Phase G90: Requirement Gap Closure (WV-003)

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
- Perform requirement-gap writeback only.
- Keep scope documentation-only and limited to allowed paths.
- Keep WV-003 clause realization anchored to existing fetch governance docs (`qa_fetch_dataaccess_facade_boundary_v1.md`, `qa_fetch_dossier_evidence_contract_v1.md`).

### 2) Concrete Writeback
- Add `goal_checklist` entry `G90` in `docs/12_workflows/skeleton_ssot_v1.yaml` with `status_now: implemented`.
- Update `requirements_trace_v1` entry `WV-003` in `docs/12_workflows/skeleton_ssot_v1.yaml` from `planned` to `implemented`, and map it to `G90`.
- Update capability cluster roll-up in `docs/12_workflows/skeleton_ssot_v1.yaml` so `CL_LEGACY_CORE` includes `G90` and points `latest_phase_id` to `G90`.

### 3) Acceptance
- `python3 scripts/check_docs_tree.py`
- `rg -n "G90|WV-003" docs/12_workflows/skeleton_ssot_v1.yaml`

## Execution Record
- Date: 2026-02-13.
- Verified SSOT goal state:
  - `goal_checklist` includes `G90` with `status_now: implemented`.
- Verified SSOT requirement trace state:
  - `requirements_trace_v1` entry `WV-003` has `status_now: implemented`.
  - `requirements_trace_v1` entry `WV-003` maps to `G90`.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `rg -n "G90|WV-003" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
