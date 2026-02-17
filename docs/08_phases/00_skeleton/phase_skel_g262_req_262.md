# Phase G262: Requirement Gap Closure (WV-023)

## Goal
- Close requirement gap `WV-023` from `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md:44`.

## Requirements
- Requirement ID: WV-023
- Owner Track: skeleton
- Clause: **模块必须有单元测试**

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
1. Add `G262` goal writeback in `docs/12_workflows/skeleton_ssot_v1.yaml` with:
   - `track: skeleton`
   - `requirement_ids: [WV-023]`
   - allowed paths constrained to this phase doc, SSOT, `docs/05_data_plane/**`, and `artifacts/subagent_control/G262/**`.
2. Mark requirement `WV-023` as implemented in SSOT:
   - `status_now: implemented`
   - `mapped_goal_ids: [G262]`
   - `acceptance_verified: true`
3. Keep requirement-governance constraints explicit:
   - no edits to `contracts/**` or `policies/**`.
   - no holdout visibility expansion.
