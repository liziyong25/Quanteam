# Phase G390: Requirement Gap Closure (WB-066/WB-067/WB-068)

## Goal
- Close requirement gap bundle `WB-066/WB-067/WB-068` from `docs/00_overview/workbench_ui_productization_v1.md:183`.

## Requirements
- Requirement IDs: WB-066/WB-067/WB-068
- Owner Track: impl_workbench
- Clause[WB-066]: 用户可在 /ui/workbench 完成 Phase‑0~4 全链路。
- Clause[WB-067]: 每个 phase 至少返回 1 张用户可读结果卡。
- Clause[WB-068]: 可创建、编辑、应用 step 草稿并继续推进。

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.
- Bundling criterion: same owner track + same source document + same parent requirement + near-adjacent source lines.
- G390 precondition: `G387` (`WB-065`) is implemented and `/ui/workbench` + session-store contract (`workbench_session_store_contract_v1`) are stable.
- Blocking point: if G387 route/session contract drifts, G390 must stop before phase-chain and draft-lifecycle integration.

## DoD
- `/ui/workbench` supports Phase-0 -> Phase-4 continuous progression (WB-066).
- Each phase renders at least one user-readable result card with title/summary/status-next-step cues (WB-067).
- Step draft create/edit/apply/rollback works and apply does not block continue-to-next-phase (WB-068).
- Acceptance commands pass (`check_docs_tree`, targeted `pytest`, SSOT `rg` check).
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
TBD by controller at execution time.
