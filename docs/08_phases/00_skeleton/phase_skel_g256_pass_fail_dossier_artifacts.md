# Phase G256: Requirement Gap Closure (WV-020)

## Goal
- Close requirement gap `WV-020` from `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md:39`.

## Requirements
- Requirement ID: WV-020
- Owner Track: skeleton
- Clause: PASS/FAIL/入库晋升必须引用 Dossier artifacts；纯文本意见无效。

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
1. Add `G256` goal writeback in `docs/12_workflows/skeleton_ssot_v1.yaml` with:
   - `track: skeleton`
   - `requirement_ids: [WV-020]`
   - allowed paths constrained to this phase doc, SSOT, `docs/05_data_plane/**`, and `artifacts/subagent_control/G256/**`.
2. Mark requirement `WV-020` as implemented in SSOT:
   - `status_now: implemented`
   - `mapped_goal_ids: [G256]`
   - `acceptance_verified: true`
3. Keep PASS/FAIL/promotion evidence semantics explicit:
   - PASS/FAIL/入库晋升 decisions must cite dossier artifact references.
   - pure free-text adjudication remains invalid.
