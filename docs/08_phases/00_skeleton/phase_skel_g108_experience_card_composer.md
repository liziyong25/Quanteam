# Phase G108: Requirement Gap Closure (WV-013)

## Goal
- Close requirement gap `WV-013` from `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md:25`.

## Requirements
- Requirement ID: WV-013
- Owner Track: skeleton
- Clause: 通过 **Experience Card（经验卡）**沉淀模块/诊断/验证方法，并支持组合（Composer）。

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
- Anchor WV-013 closure to existing Experience Card + Composer semantics already represented
  in SSOT (registry cards/trial log artifacts, composer workflow integration, and composer
  role evidence), without touching contracts/policies/runtime code.

### 2) Concrete Writeback
- Add `goal_checklist` entry `G108` in `docs/12_workflows/skeleton_ssot_v1.yaml` with
  `status_now: implemented`.
- Update `requirements_trace_v1` entry `WV-013` in `docs/12_workflows/skeleton_ssot_v1.yaml`
  from `planned` to `implemented`, and map it to `G108`.
- Update capability cluster roll-up in `docs/12_workflows/skeleton_ssot_v1.yaml` so
  `CL_LEGACY_CORE` includes `G108` and points `latest_phase_id` to `G108`.

### 3) Acceptance
- `python3 scripts/check_docs_tree.py`
- `rg -n "G108|WV-013" docs/12_workflows/skeleton_ssot_v1.yaml`

## Execution Record
- Date: 2026-02-13.
- Verified SSOT goal state:
  - `goal_checklist` includes `G108` with `status_now: implemented`.
- Verified SSOT requirement trace state:
  - `requirements_trace_v1` entry `WV-013` has `status_now: implemented`.
  - `requirements_trace_v1` entry `WV-013` maps to `G108`.
- Verified capability cluster roll-up:
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` includes `G108`.
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` has `latest_phase_id: G108`.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `rg -n "G108|WV-013" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
