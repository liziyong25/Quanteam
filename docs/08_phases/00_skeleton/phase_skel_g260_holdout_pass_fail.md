# Phase G260: Requirement Gap Closure (WV-022)

## Goal
- Close requirement gap `WV-022` from `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md:42`.

## Requirements
- Requirement ID: WV-022
- Owner Track: skeleton
- Clause: 生成/调参循环不得看到 holdout 细节，只允许 `pass/fail + 极少摘要`。

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
1. Add `G260` goal writeback in `docs/12_workflows/skeleton_ssot_v1.yaml` with:
   - `track: skeleton`
   - `requirement_ids: [WV-022]`
   - allowed paths constrained to this phase doc, SSOT, `docs/05_data_plane/**`, and `artifacts/subagent_control/G260/**`.
2. Mark requirement `WV-022` as implemented in SSOT:
   - `status_now: implemented`
   - `mapped_goal_ids: [G260]`
   - `acceptance_verified: true`
3. Keep holdout visibility constraints explicit:
   - generation/tuning loops cannot access holdout internals.
   - output remains restricted to `pass/fail + 极少摘要`.
