# Phase G364: Requirement Gap Closure (WB-015/WB-016/WB-017/WB-018)

## Goal
- Close requirement gap bundle `WB-015/WB-016/WB-017/WB-018` from `docs/00_overview/workbench_ui_productization_v1.md:66`.

## Requirements
- Requirement IDs: WB-015/WB-016/WB-017/WB-018
- Owner Track: impl_workbench
- Clause[WB-015]: FR-005 demo 验证反馈: 展示 K 线叠加、trace assertion、sanity 指标。
- Clause[WB-016]: FR-006 回测结果反馈: 展示信号摘要、交易样本、收益/回撤/Gate 摘要。
- Clause[WB-017]: FR-007 改进与沉淀: 展示 attribution 摘要、improvement 候选、registry/card、composer 结果。
- Clause[WB-018]: FR-008 高级证据展开: 每张卡片可展开原始 artifact 路径与明细 JSON/CSV。

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.
- Bundling criterion: same owner track + same source document + same parent requirement + near-adjacent source lines.

## Dependency Validation (G356)
- Baseline dependency `G356` deliverables are available and reused as stable contracts:
  - Session/job binding and workbench route schema from `src/quant_eam/api/ui_routes.py`.
  - Job output index contract (`jobs/<job_id>/outputs/outputs.json`) from `src/quant_eam/jobstore/store.py`.
- Field mapping used by this phase:
  - `calc_trace_preview_path`, `trace_meta_path`, `calc_trace_plan_path` -> WB-015 (K-line overlay + trace assertion + sanity).
  - `signal_dsl_path`, `dossier_path`, `gate_results_path` -> WB-016 (signal/trade/return-drawdown-gate summary).
  - `improvement_proposals_path`, `report_summary_path`, `composer_agent_plan_path`, `card_id` -> WB-017 (attribution/improvement/registry/composer).
  - `evidence.artifacts` + card/session/events index paths -> WB-018 (per-card expandable evidence with safe path normalization).

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
1. Extend phase card builders in `src/quant_eam/api/ui_routes.py`:
   - `trace_preview` card: K-line overlay metrics, trace assertion summary, sanity metrics.
   - `runspec` card: signal summary, trade samples, return/drawdown/gate summary.
   - `improvements` card: attribution summary, improvement candidates, registry/card status, composer result.
2. Add per-card evidence expansion with path safety + preview throttling:
   - Resolve evidence paths only under repo/artifact roots.
   - Block traversal/out-of-root references.
   - Render JSON/CSV/text previews with size/row limits.
3. Update `src/quant_eam/ui/templates/workbench.html` to render WB-015~WB-018 card sections and expandable evidence panels.
4. Update SSOT goal/requirement mapping for `G364` + `WB-015|WB-016|WB-017|WB-018`.
5. Run acceptance commands and attach results under `artifacts/subagent_control/G364/`.
