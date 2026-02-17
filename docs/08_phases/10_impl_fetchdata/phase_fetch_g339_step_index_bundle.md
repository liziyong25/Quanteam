# Phase G339: Requirement Gap Closure (QF-102/QF-103/QF-104/QF-105)

## Goal
- Close requirement gap bundle `QF-102/QF-103/QF-104/QF-105` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:194`.

## Requirements
- Requirement IDs: QF-102/QF-103/QF-104/QF-105
- Owner Track: impl_fetchdata
- Clause[QF-102]: 多步取数有 step index；
- Clause[QF-103]: Dossier 中可一跳追溯全部 fetch 证据；
- Clause[QF-104]: UI 能展示（只读 Dossier）。
- Clause[QF-105]: 集成测试覆盖：审阅失败→回退→重跑→再审阅。

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.
- Bundling criterion: same owner track + same source document + same parent requirement + near-adjacent source lines.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
- Implement `execute_ui_llm_query` dossier payload enrichment with:
  - attempts timeline sourced from review checkpoint attempts,
  - per-step timeline from each attempt `fetch_steps_index.json`,
  - rollback metadata needed for read-only one-hop UI re-review.
- Preserve QF-102 step-index semantics in multi-step evidence emission and expose normalized step index order in the dossier timeline.
- Add dossier-level visibility assertion coverage:
  - dossier payload includes timeline/retry fields for successful and failed attempts,
  - fail → rollback → rerun flow retains read-only re-reviewability.
- Update `docs/12_workflows/skeleton_ssot_v1.yaml`:
  - add `G339` implementation goal,
  - mark `QF-102`~`QF-105` implemented with `mapped_goal_ids: [G339]` and verified.
