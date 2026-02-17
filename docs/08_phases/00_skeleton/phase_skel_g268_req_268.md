# Phase G268: Requirement Gap Closure (WV-026)

## Goal
- Close requirement gap `WV-026` from `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md:48`.

## Requirements
- Requirement ID: WV-026
- Owner Track: skeleton
- Clause: 候选策略数上限、参数网格上限、连续无提升停止，避免无限搜索挖假阳性。

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
1. Add `G268` goal writeback in `docs/12_workflows/skeleton_ssot_v1.yaml` with:
   - `track: skeleton`
   - `requirement_ids: [WV-026]`
   - allowed paths constrained to this phase doc, SSOT, `docs/05_data_plane/**`, and `artifacts/subagent_control/G268/**`.
2. Mark requirement `WV-026` as implemented in SSOT:
   - `status_now: implemented`
   - `mapped_goal_ids: [G268]`
   - `acceptance_verified: true`
3. Keep requirement-governance constraints explicit:
   - no edits to `contracts/**` or `policies/**`.
   - no holdout visibility expansion.
