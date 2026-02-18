# 用户导向实时策略工作台 UI 改造方案（主控 + Subagent 执行版）

## 0. 文档信息
- 文档版本: `v1`
- 建议路径: `docs/12_workflows/workbench_ui_productization_v1.md`
- 适用范围: `3002 UI` 产品化改造，不替换现有审阅链路
- 本文性质: 改造背景 + 需求 + 方案 + 主控/子代理开发流程（本轮不改代码）

## 0.1 状态说明（`2026-02-18`）
- 本文包含“目标态”与“当前实现态”两层信息。
- 目标态用于产品规划；当前实现态以代码为准：
  - `src/quant_eam/api/ui_routes.py`
  - `src/quant_eam/orchestrator/workflow.py`
  - `src/quant_eam/agents/harness.py`
- G357 已闭环 `WB-011/WB-012/WB-013/WB-014/WB-020`：会话与真实 job 绑定、continue 自动审批推进、Phase‑0 fetch 预览可视化、Strategy 可读摘要、会话事件审计增强。

## 0.2 两套主控链路（必须区分）
- `开发执行层主控 + Subagent`（Codex 自动化交付）：
  - `scripts/whole_view_autopilot.py` + `artifacts/subagent_control/*`
  - 用于开发任务分发、代码修改、packet 验证、SSOT 回写。
- `运行时业务链主控 + Agents Plane`（真实策略回测）：
  - `jobs_api -> worker -> orchestrator -> harness -> runner/gates`
  - 用于真实 job 的策略生成、回测、评估、优化。
- 两者不是同一条调用链，不能混用职责。

## 0.3 Workbench Recipes（SSOT 入口）
- 本文是 Workbench 产品化“母文档”：定义边界、共性需求、治理约束、验收口径。
- 具体研究闭环场景（例如 MA250 年线有效性）使用 recipe 文档承载，不在母文档硬编码场景细节。
- Recipe 与母文档职责分离：
  - 母文档：稳定需求与治理边界（避免 requirement 编号频繁漂移）。
  - Recipe：可执行场景规格（接口入参、时序、DoD、任务卡）。
- 当前首个 recipe：`docs/10_ui/workbench_ma250_effectiveness_demo_v1.md`。
- Recipe 变更原则：优先新增/迭代 recipe，不重写母文档正文条款（除非单开 requirement splitter + SSOT 对齐轮次）。

## 1. 改造背景
当前 `3002` UI 以审阅和证据链为中心，优势是可治理、可回放、可审计。  
当前用户痛点是“结果导向体验不足”：用户希望快速看到数据、信号、交易和回测摘要，而不是先面对开发式事件流。  
系统内核能力已经具备全链路基础能力（Idea/Agent/Run/Gate/Registry/Composer），但交互层缺少“用户工作台”编排层。  
结论：问题不在内核缺能力，问题在 UI 交互模型与用户目标不匹配。

## 2. 产品目标与非目标
## 2.1 产品目标
- 在不破坏现有 `review UI` 的前提下新增 `用户工作台 UI`。
- 用户可在一个入口完成 Phase‑0 到 Phase‑4 的串联操作与结果查看。
- 每一步都返回“用户可读结果卡片”，默认隐藏底层证据细节。
- 仍保留治理边界: 证据落盘、可追溯、可审批、可重放。

## 2.2 非目标
- 不删除现有 `/ui/jobs`、`/ui/runs`、`/ui/qa-fetch` 等审阅页面。
- 不绕过 contracts/policies/gates 的治理规则。
- 不将 Agent 变成最终裁决者（裁决仍由 deterministic kernel + gates 完成）。

## 3. 需求定义（产品与技术）
## 3.1 关键产品需求
- 交互模式: `对话 + 结果面板`。
- 上线方式: 新增入口 ` /ui/workbench `。
- 首发范围: 全链路到 Composer。
- 步骤编辑: 每个 step 先草稿，支持人工修改并继续。
- 草稿持久化: 版本化追加，不覆盖原稿。

## 3.2 核心功能需求（FR）
- `FR-001` 工作台会话创建: 用户输入 Idea 约束后创建会话与关联 job。
- `FR-002` 一键推进: 在每个检查点可点击“继续”，系统自动审批并推进到下一检查点或终态。
- `FR-003` 取数即时反馈: 用户在 Phase‑0 即可触发 fetch 预览并看到表格样本。
- `FR-004` 逻辑可读输出: Strategy 阶段展示 pseudocode、变量字典摘要、trace plan 摘要。
- `FR-005` demo 验证反馈: 展示 K 线叠加、trace assertion、sanity 指标。
- `FR-006` 回测结果反馈: 展示信号摘要、交易样本、收益/回撤/Gate 摘要。
- `FR-007` 改进与沉淀: 展示 attribution 摘要、improvement 候选、registry/card、composer 结果。
- `FR-008` 高级证据展开: 每张卡片可展开原始 artifact 路径与明细 JSON/CSV。
- `FR-009` 失败可恢复: 支持重跑当前 step、应用历史草稿、回退到上一步草稿。
- `FR-010` 全程审计: 用户动作与系统动作都写会话事件日志。

## 3.3 非功能需求（NFR）
- `NFR-001` 不破坏现有 API/UI 行为。
- `NFR-002` 兼容现有 job/event append-only 语义。
- `NFR-003` 对外结果可在单页及时刷新（轮询或 SSE）。
- `NFR-004` 对同一会话动作幂等（重复点击不会破坏状态）。
- `NFR-005` 全链路错误可解释（UI 给出可读失败原因 + evidence 引用）。

## 4. 总体方案
## 4.1 架构原则
- 新增工作台编排层，不改 deterministic kernel 的职责边界。
- 维持 orchestrator 为主状态机，工作台只是“用户友好驱动器 + 视图模型”。
- 默认展示业务结果卡片，高级证据按需展开。
- 继续采用 contracts/policies 作为 I/O SSOT。

## 4.2 组件改造
- 新增 `Workbench API`。
- 新增 `Workbench UI` 页面与组件。
- 新增 `Session Store` 与 `Step Draft Store`。
- 新增 `Result Card Builder`（从已有 artifacts 组装用户摘要卡）。
- 运行时 `Harness` 保持 `run_agent + provider(mock/real_http)` 路线；`codex_cli` 不作为运行时 agent 执行源。
- `codex_cli` 当前用于开发执行层（subagent packet 流程），不是运行时 job 主链。

## 4.3 路由与接口（新增）
- `POST /workbench/sessions`
- `GET /workbench/sessions/{session_id}`
- `POST /workbench/sessions/{session_id}/message`
- `POST /workbench/sessions/{session_id}/continue`
- `GET /workbench/sessions/{session_id}/events`（SSE 或轮询兼容）
- `POST /workbench/sessions/{session_id}/fetch-probe`
- `POST /workbench/sessions/{session_id}/steps/{step}/drafts`
- `POST /workbench/sessions/{session_id}/steps/{step}/drafts/{version}/apply`
- `GET /ui/workbench`
- `GET /ui/workbench/{session_id}`

## 4.4 数据落盘（新增）
- `artifacts/workbench/sessions/<session_id>/session.json`
- `artifacts/workbench/sessions/<session_id>/events.jsonl`
- `artifacts/jobs/<job_id>/outputs/workbench/cards/*.json`
- `artifacts/jobs/<job_id>/outputs/workbench/step_drafts/<step>/draft_vNN.json`
- `artifacts/jobs/<job_id>/outputs/workbench/step_drafts/<step>/selected.json`

## 5. Phase 对应的用户结果卡定义
## 5.1 Phase‑0（Idea -> Blueprint Draft）
- 展示卡: DataIntent 卡、FetchRequest 卡、FetchPreview 表格卡、评估协议卡、预算卡。
- 可操作: auto_symbols/sample 开关、字段选择、时间窗调整、立即 fetch-probe。
- 里程碑冻结（WB-046）: 本阶段先保证 `Idea -> Blueprint Draft` checkpoint 落盘与 `WAITING_APPROVAL(step=blueprint)` 证据稳定。
- 明确递延: `WB-047`（展示卡细化）与 `WB-048`（可操作项细化）在后续目标单独收敛，不并入本次 checkpoint 实现。

## 5.2 Phase‑1（Strategy 规格确认）
- 展示卡: strategy_pseudocode 卡、variable_dictionary 摘要卡、calc_trace_plan 摘要卡、Spec-QA 风险卡。
- 可操作: 草稿编辑并应用、回退上一草稿版本。

## 5.3 Phase‑2（Demo 验证）
- 展示卡: K 线叠加卡、trace assertion 卡、fetch evidence 摘要卡、sanity metrics 卡。
- 可操作: 不通过时回退到 Phase‑1 并重跑。

## 5.4 Phase‑3（Research Backtest）
- 展示卡: 回测摘要卡、交易样本卡、信号摘要卡、Gate 摘要卡、Run 跳转卡。
- 可操作: 继续到 Phase‑4、重跑当前 step。

## 5.5 Phase‑4（评估/改进/入库/组合）
- 展示卡: attribution 摘要卡、improvement 候选卡、registry 状态卡、composer 结果卡。
- 可操作: 生成并应用改进候选、组合运行与结果查看。

## 6. 主控 + Subagent 执行流程（参考 docs/12_workflows）
说明：本节是“开发执行层”流程，不是运行时业务链。  
执行流程遵循 `docs/12_workflows/subagent_dev_workflow_v1.md`。

## 6.1 主控职责
- 基于 SSOT 生成任务卡与允许路径。
- 每轮只下发一个可验收子目标。
- 聚合 Subagent 输出并做合规检查。
- 触发验证子代理，汇总 PASS/FAIL 与证据。
- 回写阶段文档与 SSOT 进度。

## 6.2 Subagent 分工建议
- `Subagent-A` Workbench API 与 Session Store。
- `Subagent-B` Workbench UI 页面与卡片组件。
- `Subagent-C` Result Card Builder 与 artifact 解析。
- `Subagent-D` 开发执行层 `codex_cli` packet 工具链增强（非运行时 agent 执行源）。
- `Subagent-E` 集成测试、回归测试、验收报告。

## 6.3 每轮任务卡最小模板
- 任务目标（单一交付）。
- 允许路径（白名单）。
- 禁止项（contracts/policies/holdout redline）。
- 验收命令。
- UI 黑盒检查点。
- 证据产物路径。

## 6.4 建议迭代顺序
1. 工作台会话 API + `/ui/workbench` 空页面 + `continue` 推进能力。  
2. Phase‑0~2 用户卡片与草稿版本化编辑闭环。  
3. Phase‑3~4 卡片与 Composer 集成。  
4. 开发执行层 `codex_cli` packet 能力补强（运行时仍走 harness + provider）。  
5. 回归与灰度发布。

## 7. 风险与控制
- 风险: 工作台推进与现有审批语义冲突。  
- 控制: `continue` 仅调用既有 approve + advance，禁止绕过事件模型。  
- 风险: Codex CLI 输出不稳定。  
- 控制: schema 强校验 + output guard + 自动 fallback mock。  
- 风险: 页面复杂度过高。  
- 控制: 卡片化 + 高级详情折叠 + 渐进暴露。  
- 风险: 全链路首发范围过大。  
- 控制: 采用阶段门禁，任一步未达标即冻结下一步。

## 8. 验收标准（DoD）
- 功能验收:
- 用户可在 ` /ui/workbench ` 完成 Phase‑0~4 全链路。
- 每个 phase 至少返回 1 张用户可读结果卡。
- 可创建、编辑、应用 step 草稿并继续推进。
- 技术验收:
- 新增 API 测试、UI E2E 测试、全链路集成测试通过。
- 现有 `/ui/jobs`、`/ui/runs`、`/ui/qa-fetch` 回归通过。
- 治理验收:
- 事件 append-only 不破坏。
- 证据文件可追溯且路径稳定。
- 合约与策略红线未被破坏。

## 9. 与现有文档体系的对齐
- 工作流与执行规范: `docs/12_workflows/subagent_dev_workflow_v1.md`
- 状态机与审批语义: `docs/12_workflows/orchestrator_v1.md`
- 总体目标与对象模型: `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md`
- 数据链路与 fetch 语义: `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md`

## 10. 实施备注
- 本文是“开发交付用方案文档”，本轮不涉及代码修改。  
- 下一步应由主控将本文拆成任务卡，按子代理流水线执行并持续回写证据。  

## 11. 当前实现对齐（真实进度 vs 本文目标）

### 11.1 FR 对齐状态（按代码现状）

1. `FR-001` 已实现：
   - `POST /workbench/sessions` 在 real-jobs 模式下支持基于 Idea 约束创建真实 idea job，并绑定 workbench session。
   - 代码：`src/quant_eam/api/ui_routes.py`
2. `FR-002` 已实现：
   - `POST /workbench/sessions/{session_id}/continue` 在 checkpoint 上自动追加 APPROVED 并驱动 `advance_job_once` 推进到下一 checkpoint 或终态。
   - 代码：`src/quant_eam/api/ui_routes.py`
3. `FR-003` 已实现：
   - `POST /workbench/sessions/{session_id}/fetch-probe` 支持 runtime 预览、错误状态回写与样本表格展示。
   - 代码：`src/quant_eam/api/ui_routes.py`、`src/quant_eam/ui/templates/workbench.html`
4. `FR-004` 已实现：
   - Strategy checkpoint 展示 pseudocode、variable dictionary 摘要、trace plan 摘要（基于 job outputs 组装）。
   - 代码：`src/quant_eam/api/ui_routes.py`、`src/quant_eam/ui/templates/workbench.html`
5. `FR-005` 已实现：
   - Demo 阶段卡片展示 K 线叠加（基于 trace preview 采样）、trace assertion 摘要与 sanity metrics。
   - 代码：`src/quant_eam/api/ui_routes.py`、`src/quant_eam/ui/templates/workbench.html`
6. `FR-006` 已实现：
   - Backtest 阶段卡片展示 signal summary、trade samples、return/drawdown/Gate 摘要。
   - 代码：`src/quant_eam/api/ui_routes.py`、`src/quant_eam/ui/templates/workbench.html`
7. `FR-007` 已实现：
   - Improvements 阶段卡片展示 attribution 摘要、improvement 候选、registry/card 状态、composer 结果。
   - 代码：`src/quant_eam/api/ui_routes.py`、`src/quant_eam/ui/templates/workbench.html`
8. `FR-008` 已实现：
   - 每张卡片支持安全路径约束下的 evidence 展开，并提供 JSON/CSV 明细预览视图。
   - 代码：`src/quant_eam/api/ui_routes.py`、`src/quant_eam/ui/templates/workbench.html`
9. `FR-009` 未完成：
   - 未形成“失败后重跑当前 step / 回退到上一步草稿并重跑 job”的闭环控制。
10. `FR-010` 已实现（会话侧）：
   - 用户动作（create/message/continue/fetch-probe/draft）与系统动作（auto-approve/advance/fetch success|failed）均写入 session 事件日志。
   - 代码：`src/quant_eam/api/ui_routes.py`

### 11.2 与运行时 Agents Plane 的已闭环项

G357 已完成以下最小闭环：

1. `workbench_session_create`：真实创建 idea job（`create_job_from_ideaspec`）并写回 session 绑定。
2. `workbench_session_continue`：按 checkpoint 自动审批并推进状态机，不绕过等待审批语义。
3. `workbench_session_fetch_probe`：使用 runtime 查询路径并将 preview/attempt evidence 写入会话上下文。
4. Strategy 卡片改为读取 job outputs 生成可读摘要，不再仅依赖占位摘要。

### 11.3 前后端 + agent + LLM 的正确调用方式

1. 前端：
   - 仅调用后端 API，不直接调用 agent 函数。
2. 后端：
   - 通过 `jobs_api` + `orchestrator` 推进状态机。
3. Agent 调用：
   - orchestrator 内部调用 `run_agent(...)`（`src/quant_eam/agents/harness.py`）。
4. LLM 调用（运行时）：
   - harness 读取 `EAM_LLM_PROVIDER` / `EAM_LLM_MODE`，通过 provider（如 `real_http`）HTTP 调用模型端点。
5. `codex_cli`：
   - 当前只用于开发执行层（subagent packet 流程），不用于运行时业务 job 主链。

### 11.4 Recipe 对齐状态（代码现实）

为支持 recipe（如 MA250 one-shot）并保持与代码一致，当前主要剩余：

1. 对“投资结论”的输出尚未形成 report 扩展规范：
   - 需在 recipe 中明确 `report_context.json` 输入与 `report_summary.json.decision` 输出字段。
   - 代码基线：`src/quant_eam/agents/report_agent.py`、`src/quant_eam/agents/harness.py`

## 12. Recipe 索引

| recipe_id | 场景 | 文档路径 | 状态 | 说明 |
|---|---|---|---|---|
| `WB-RECIPE-MA250-V1` | A股 MA250 年线有效性 one-shot 闭环 | `docs/10_ui/workbench_ma250_effectiveness_demo_v1.md` | active | 以 message-only -> intake -> fetch -> 回测 -> 结论为最小闭环，支持跨品种 intent 泛化。 |
