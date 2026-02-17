# 用户导向实时策略工作台 UI 改造方案（主控 + Subagent 执行版）

## 0. 文档信息
- 文档版本: `v1`
- 建议路径: `docs/12_workflows/workbench_ui_productization_v1.md`
- 适用范围: `3002 UI` 产品化改造，不替换现有审阅链路
- 本文性质: 改造背景 + 需求 + 方案 + 主控/子代理开发流程（本轮不改代码）

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
- 扩展 `Harness` 执行源，支持 `codex_cli`（覆盖全部 agent），并保留 mock fallback。

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
- `Subagent-D` Harness codex_cli 执行器接入（全部 agent）。
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
4. Harness 内置 `codex_cli`（全部 agent）+ fallback + 审计。  
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
