# Phase G264: Requirement Gap Closure (WV-024)

## Goal
- Close requirement gap `WV-024` from `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md:45`.

## Requirements
- Requirement ID: WV-024
- Owner Track: skeleton
- Clause: 至少覆盖：lookahead/对齐/NaN/索引单调性/边界条件/时间窗端点。

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
1. Add `G264` goal writeback in `docs/12_workflows/skeleton_ssot_v1.yaml` with:
   - `track: skeleton`
   - `requirement_ids: [WV-024]`
   - allowed paths constrained to this phase doc, SSOT, `docs/05_data_plane/**`, and `artifacts/subagent_control/G264/**`.
2. Mark requirement `WV-024` as implemented in SSOT:
   - `status_now: implemented`
   - `mapped_goal_ids: [G264]`
   - `acceptance_verified: true`
3. Keep requirement-governance constraints explicit:
   - no edits to `contracts/**` or `policies/**`.
   - no holdout visibility expansion.
