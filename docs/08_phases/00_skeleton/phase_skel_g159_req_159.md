# Phase G159: Requirement Gap Closure (WV-042)

## Goal
- Close requirement gap `WV-042` from `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md:73`.

## Requirements
- Requirement ID: WV-042
- Owner Track: skeleton
- Clause: 关键假设（成交价、延迟、复权、缺失处理）

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
- Anchor `WV-042` closure to SSOT requirement trace and goal linkage, with clause
  coverage fixed as: 关键假设（成交价、延迟、复权、缺失处理）.

### 2) Concrete Writeback
- Add `goal_checklist` entry `G159` in `docs/12_workflows/skeleton_ssot_v1.yaml`
  with `status_now: implemented`.
- Update `requirements_trace_v1` entry `WV-042` in
  `docs/12_workflows/skeleton_ssot_v1.yaml` from `planned` to `implemented`,
  mapped to `G159`.
- Preserve capability cluster linkage in `docs/12_workflows/skeleton_ssot_v1.yaml`
  with `CL_LEGACY_CORE` including `G159`.

### 3) Acceptance
- `python3 scripts/check_docs_tree.py`
- `rg -n "G159|WV-042" docs/12_workflows/skeleton_ssot_v1.yaml`

## Execution Record
- Date: 2026-02-14.
- Verified SSOT goal state:
  - `goal_checklist` includes `G159` with `status_now: implemented`.
- Verified SSOT requirement trace state:
  - `requirements_trace_v1` entry `WV-042` has `status_now: implemented`.
  - `requirements_trace_v1` entry `WV-042` maps to `G159`.
- Verified capability cluster roll-up:
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` includes `G159`.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `rg -n "G159|WV-042" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
- `python3 scripts/check_subagent_packet.py --phase-id G159` passed.
