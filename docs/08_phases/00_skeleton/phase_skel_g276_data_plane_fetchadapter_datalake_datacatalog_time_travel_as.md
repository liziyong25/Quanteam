# Phase G276: Requirement Gap Closure (WV-030)

## Goal
- Close requirement gap `WV-030` from `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md:56`.

## Requirements
- Requirement ID: WV-030
- Owner Track: skeleton
- Clause: **Data Plane**：FetchAdapter → DataLake → DataCatalog（time‑travel：as_of / available_at）

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
1. Add `G276` goal writeback in `docs/12_workflows/skeleton_ssot_v1.yaml` with:
   - `track: skeleton`
   - `requirement_ids: [WV-030]`
   - allowed paths constrained to this phase doc, SSOT, `docs/05_data_plane/**`, and `artifacts/subagent_control/G276/**`.
2. Mark requirement `WV-030` as implemented in SSOT:
   - `status_now: implemented`
   - `mapped_goal_ids: [G276]`
   - `acceptance_verified: true`
3. Keep requirement-governance constraints explicit:
   - no edits to `contracts/**` or `policies/**`.
   - no holdout visibility expansion.
