# Phase G116: Requirement Gap Closure (WV-018)

## Goal
- Close requirement gap `WV-018` from `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md:36`.

## Requirements
- Requirement ID: WV-018
- Owner Track: skeleton
- Clause: 禁止生成可执行脚本直接跑回测（必须经 Compiler）。

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
- Anchor WV-018 closure to existing compiler-bound execution semantics already represented
  in SSOT: backtest execution must flow through the Compiler boundary rather than
  direct executable-script generation.

### 2) Concrete Writeback
- Add `goal_checklist` entry `G116` in `docs/12_workflows/skeleton_ssot_v1.yaml` with
  `status_now: implemented`.
- Update `requirements_trace_v1` entry `WV-018` in `docs/12_workflows/skeleton_ssot_v1.yaml`
  from `planned` to `implemented`, and map it to `G116`.
- Update capability cluster roll-up in `docs/12_workflows/skeleton_ssot_v1.yaml` so
  `CL_LEGACY_CORE` includes `G116` and points `latest_phase_id` to `G116`.

### 3) Acceptance
- `python3 scripts/check_docs_tree.py`
- `rg -n "G116|WV-018" docs/12_workflows/skeleton_ssot_v1.yaml`

## Execution Record
- Date: 2026-02-13.
- Verified SSOT goal state:
  - `goal_checklist` includes `G116` with `status_now: implemented`.
- Verified SSOT requirement trace state:
  - `requirements_trace_v1` entry `WV-018` has `status_now: implemented`.
  - `requirements_trace_v1` entry `WV-018` maps to `G116`.
- Verified capability cluster roll-up:
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` includes `G116`.
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` has `latest_phase_id: G116`.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `rg -n "G116|WV-018" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
