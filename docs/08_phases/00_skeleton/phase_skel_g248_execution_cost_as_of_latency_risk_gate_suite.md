# Phase G248: Requirement Gap Closure (WV-016)

## Goal
- Close requirement gap `WV-016` from `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md:33`.

## Requirements
- Requirement ID: WV-016
- Owner Track: skeleton
- Clause: execution/cost/as-of/latency/risk/gate_suite 等 policy 只能引用 `policy_id`，禁止策略覆盖或内联修改。

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
1. Add `G248` goal writeback in `docs/12_workflows/skeleton_ssot_v1.yaml` with:
   - `track: skeleton`
   - `requirement_ids: [WV-016]`
   - allowed paths constrained to this phase doc, SSOT, `docs/05_data_plane/**`, and `artifacts/subagent_control/G248/**`.
2. Mark requirement `WV-016` as implemented in SSOT:
   - `status_now: implemented`
   - `mapped_goal_ids: [G248]`
   - `acceptance_verified: true`
3. Keep policy governance boundary explicit:
   - execution/cost/as-of/latency/risk/gate_suite policy usage is by `policy_id` reference only.
   - no strategy-level policy override and no inline policy mutation.
