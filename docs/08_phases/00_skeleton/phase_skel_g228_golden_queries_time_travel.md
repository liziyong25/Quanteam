# Phase G228: Requirement Gap Closure (WV-006)

## Goal
- Close requirement gap `WV-006` from `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md:12`.

## Requirements
- Requirement ID: WV-006
- Owner Track: skeleton
- Clause: 把 “取数正确性” 升级为可工程化验收：结构检查 + Golden Queries +（最终）time‑travel 可得性约束。

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
- Anchor `WV-006` closure to existing fetch quality artifacts that define
  structure checks, golden-query coverage, and time-travel availability
  expectations (`docs/05_data_plane/qa_fetch_golden_queries_v1.md`,
  `docs/05_data_plane/qa_fetch_asof_availability_summary_contract_v1.md`,
  `docs/05_data_plane/snapshot_catalog_v1.md`).

### 2) Concrete Writeback
- Add `goal_checklist` entry `G228` in `docs/12_workflows/skeleton_ssot_v1.yaml`
  with `status_now: implemented`, `track: skeleton`, and task-scoped
  `allowed_paths`/`still_forbidden`.
- Update `requirements_trace_v1` entry `WV-006` in
  `docs/12_workflows/skeleton_ssot_v1.yaml` from `planned` to `implemented`,
  mapped to `G228` with `acceptance_verified: true`.
- Update capability-cluster roll-up in `docs/12_workflows/skeleton_ssot_v1.yaml`
  so `CL_LEGACY_CORE` includes `G228`, removes closed requirement `WV-006` from
  pending requirement IDs, and sets `latest_phase_id: G228`.

### 3) Acceptance
- `python3 scripts/check_docs_tree.py`
- `rg -n "G228|WV-006" docs/12_workflows/skeleton_ssot_v1.yaml`

## Execution Record
- Date: 2026-02-14.
- Verified SSOT goal state:
  - `goal_checklist` includes `G228` with `status_now: implemented`.
- Verified SSOT requirement trace state:
  - `requirements_trace_v1` entry `WV-006` has `status_now: implemented`.
  - `requirements_trace_v1` entry `WV-006` maps to `G228`.
- Verified capability cluster roll-up:
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` includes `G228`.
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` no longer lists `WV-006` in
    pending requirement IDs.
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` has `latest_phase_id: G228`.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `rg -n "G228|WV-006" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
