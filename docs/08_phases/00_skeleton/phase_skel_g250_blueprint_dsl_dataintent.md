# Phase G250: Requirement Gap Closure (WV-017)

## Goal
- Close requirement gap `WV-017` from `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md:35`.

## Requirements
- Requirement ID: WV-017
- Owner Track: skeleton
- Clause: **策略生成只能生成 Blueprint/DSL（+ DataIntent）**

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
1. Add `G250` goal writeback in `docs/12_workflows/skeleton_ssot_v1.yaml` with:
   - `track: skeleton`
   - `requirement_ids: [WV-017]`
   - allowed paths constrained to this phase doc, SSOT, `docs/05_data_plane/**`, and `artifacts/subagent_control/G250/**`.
2. Mark requirement `WV-017` as implemented in SSOT:
   - `status_now: implemented`
   - `mapped_goal_ids: [G250]`
   - `acceptance_verified: true`
3. Keep hard-constraint semantics explicit:
   - strategy generation output remains declarative (`Blueprint/DSL + DataIntent`) only.
   - no direct executable-script generation path is introduced.
