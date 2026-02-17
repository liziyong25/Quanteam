# Phase G252: Requirement Gap Closure (WV-018)

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
1. Add `G252` goal writeback in `docs/12_workflows/skeleton_ssot_v1.yaml` with:
   - `track: skeleton`
   - `requirement_ids: [WV-018]`
   - allowed paths constrained to this phase doc, SSOT, `docs/05_data_plane/**`, and `artifacts/subagent_control/G252/**`.
2. Mark requirement `WV-018` as implemented in SSOT:
   - `status_now: implemented`
   - `mapped_goal_ids: [G252]`
   - `acceptance_verified: true`
3. Keep compiler-bound execution semantics explicit:
   - no direct executable-script backtest path is introduced.
   - execution remains compiler-mediated.
