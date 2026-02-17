# Phase G236: Requirement Gap Closure (WV-010)

## Goal
- Close requirement gap `WV-010` from `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md:22`.

## Requirements
- Requirement ID: WV-010
- Owner Track: skeleton
- Clause: 系统把想法固化为 **可编译规格（Blueprint/DSL + DataIntent）**，由确定性 Kernel 编译成 RunSpec。

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
- Anchor `WV-010` closure to the deterministic Blueprint/DSL + DataIntent to
  RunSpec compilation contract.

### 2) Concrete Writeback
- Add `goal_checklist` entry `G236` in `docs/12_workflows/skeleton_ssot_v1.yaml`
  with `status_now: implemented`, `track: skeleton`, and task-scoped
  `allowed_paths`/`still_forbidden`.
- Update `requirements_trace_v1` entry `WV-010` in
  `docs/12_workflows/skeleton_ssot_v1.yaml` from `planned` to `implemented`,
  mapped to `G236` with `acceptance_verified: true`.
- Update capability cluster roll-up in `docs/12_workflows/skeleton_ssot_v1.yaml`
  so `CL_LEGACY_CORE` includes `G236`, removes closed requirement `WV-010` from
  pending requirement IDs, and sets `latest_phase_id: G236`.

### 3) Acceptance
- `python3 scripts/check_docs_tree.py`
- `rg -n "G236|WV-010" docs/12_workflows/skeleton_ssot_v1.yaml`

## Execution Record
- Date: 2026-02-14.
- Verified SSOT goal state:
  - `goal_checklist` includes `G236` with `status_now: implemented`.
- Verified SSOT requirement trace state:
  - `requirements_trace_v1` entry `WV-010` has `status_now: implemented`.
  - `requirements_trace_v1` entry `WV-010` maps to `G236`.
- Verified capability cluster roll-up:
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` includes `G236`.
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` no longer lists `WV-010` in
    pending requirement IDs.
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` has `latest_phase_id: G236`.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `rg -n "G236|WV-010" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
