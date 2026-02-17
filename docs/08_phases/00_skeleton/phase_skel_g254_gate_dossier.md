# Phase G254: Requirement Gap Closure (WV-019)

## Goal
- Close requirement gap `WV-019` from `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md:38`.

## Requirements
- Requirement ID: WV-019
- Owner Track: skeleton
- Clause: **裁决只允许 Gate + Dossier**

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
1. Add `G254` goal writeback in `docs/12_workflows/skeleton_ssot_v1.yaml` with:
   - `track: skeleton`
   - `requirement_ids: [WV-019]`
   - allowed paths constrained to this phase doc, SSOT, `docs/05_data_plane/**`, and `artifacts/subagent_control/G254/**`.
2. Mark requirement `WV-019` as implemented in SSOT:
   - `status_now: implemented`
   - `mapped_goal_ids: [G254]`
   - `acceptance_verified: true`
3. Keep arbitration hard-constraint semantics explicit:
   - adjudication remains Gate + Dossier only.
   - no alternative non-gate arbitration route is introduced.
