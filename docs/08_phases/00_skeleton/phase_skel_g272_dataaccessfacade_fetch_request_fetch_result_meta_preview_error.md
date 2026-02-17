# Phase G272: Requirement Gap Closure (WV-028)

## Goal
- Close requirement gap `WV-028` from `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md:51`.

## Requirements
- Requirement ID: WV-028
- Owner Track: skeleton
- Clause: 任何数据获取必须通过 DataAccessFacade，并落 `fetch_request / fetch_result_meta / preview / error` 等证据。

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
1. Add `G272` goal writeback in `docs/12_workflows/skeleton_ssot_v1.yaml` with:
   - `track: skeleton`
   - `requirement_ids: [WV-028]`
   - allowed paths constrained to this phase doc, SSOT, `docs/05_data_plane/**`, and `artifacts/subagent_control/G272/**`.
2. Mark requirement `WV-028` as implemented in SSOT:
   - `status_now: implemented`
   - `mapped_goal_ids: [G272]`
   - `acceptance_verified: true`
3. Keep requirement-governance constraints explicit:
   - no edits to `contracts/**` or `policies/**`.
   - no holdout visibility expansion.
