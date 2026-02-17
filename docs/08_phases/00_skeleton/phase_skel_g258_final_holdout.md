# Phase G258: Requirement Gap Closure (WV-021)

## Goal
- Close requirement gap `WV-021` from `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md:41`.

## Requirements
- Requirement ID: WV-021
- Owner Track: skeleton
- Clause: **Final Holdout 不可污染**

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
1. Add `G258` goal writeback in `docs/12_workflows/skeleton_ssot_v1.yaml` with:
   - `track: skeleton`
   - `requirement_ids: [WV-021]`
   - allowed paths constrained to this phase doc, SSOT, `docs/05_data_plane/**`, and `artifacts/subagent_control/G258/**`.
2. Mark requirement `WV-021` as implemented in SSOT:
   - `status_now: implemented`
   - `mapped_goal_ids: [G258]`
   - `acceptance_verified: true`
3. Keep final holdout anti-contamination semantics explicit:
   - no holdout visibility expansion is introduced.
   - holdout remains isolated from generation/tuning loops.
