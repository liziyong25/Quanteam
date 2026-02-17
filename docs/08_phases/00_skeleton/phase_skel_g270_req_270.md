# Phase G270: Requirement Gap Closure (WV-027)

## Goal
- Close requirement gap `WV-027` from `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md:50`.

## Requirements
- Requirement ID: WV-027
- Owner Track: skeleton
- Clause: **数据访问必须可审计**

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
1. Add `G270` goal writeback in `docs/12_workflows/skeleton_ssot_v1.yaml` with:
   - `track: skeleton`
   - `requirement_ids: [WV-027]`
   - allowed paths constrained to this phase doc, SSOT, `docs/05_data_plane/**`, and `artifacts/subagent_control/G270/**`.
2. Mark requirement `WV-027` as implemented in SSOT:
   - `status_now: implemented`
   - `mapped_goal_ids: [G270]`
   - `acceptance_verified: true`
3. Keep requirement-governance constraints explicit:
   - no edits to `contracts/**` or `policies/**`.
   - no holdout visibility expansion.
