# Phase G314: Requirement Gap Closure (QF-069/QF-070/QF-071/QF-072)

## Goal
- Close requirement gap bundle `QF-069/QF-070/QF-071/QF-072` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:131`.

## Requirements
- Requirement IDs: QF-069/QF-070/QF-071/QF-072
- Owner Track: impl_fetchdata
- Clause[QF-069]: 先执行对应 *_list 获取候选集合；
- Clause[QF-070]: 执行 sample（随机/流动性/行业分层等，具体策略由主控决定）；
- Clause[QF-071]: 再执行 *_day 拉取行情数据；
- Clause[QF-072]: 每一步必须落 step evidence（可审计）。

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
TBD by controller at execution time.
