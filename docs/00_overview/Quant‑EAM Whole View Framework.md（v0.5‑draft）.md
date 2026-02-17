# Quant‑EAM Whole View Framework（v0.5‑draft / Fetch‑Integrated Mainline）
> 目的：作为“总蓝图 + 硬约束 + 交付物 DoD”的主路真理文档，指导 Codex 施工不跑偏。  
> 环境：Linux + Docker + Python。  
> 版本策略：主路文档只描述 **边界/契约/工作流/DoD**；实现细节与运行快照放在附录文档（例如 QA_Fetch 集成说明）。  

---

## CHANGELOG（v0.4 → v0.5 的核心变化）
1) **Data Plane 主路引入 FetchAdapter（qa_fetch）**：统一入口为 `fetch_request(intent)`，并规定证据落盘与 UI 审阅。  
2) 引入 **FetchRequest / FetchResultMeta / DataSnapshot** 的 contract 体系（版本化）。  
3) 明确 **DataAccessFacade + FetchPlanner** 为 Agents 获取数据的唯一通道（禁止 agent 直连 provider/DB）。  
4) 把 “取数正确性” 升级为可工程化验收：结构检查 + Golden Queries +（最终）time‑travel 可得性约束。  
5) Phase‑3 明确拆为 **3A FetchAdapter MVP / 3B DataLake snapshot / 3C DataCatalog time‑travel**，以便分步闭环。

---

## 0. Definition：你要构建的系统是什么
这是一个 **可审计的经验资产系统（Experience Asset Machine, EAM）**，不是“策略工厂”。

系统必须做到：
- 用户只在 **Web UI** 输入想法与约束，并在多个审阅点确认证据（不看源码）。
- 系统把想法固化为 **可编译规格（Blueprint/DSL + DataIntent）**，由确定性 Kernel 编译成 RunSpec。
- 回测/诊断产出 **证据包（Dossier，append‑only）**。
- 策略是否“有效”的裁决只能由 **GateRunner（确定性 Gate 套件）**给出（PASS/FAIL），可回放、可追溯。
- 通过 **Experience Card（经验卡）**沉淀模块/诊断/验证方法，并支持组合（Composer）。

---

## 1. 系统硬约束（写入 GOVERNANCE.md + CI 强制）
这些约束是“真理”，任何 Agent/Codex/脚本不能绕过：

1) **Policies 只读**
- execution/cost/as-of/latency/risk/gate_suite 等 policy 只能引用 `policy_id`，禁止策略覆盖或内联修改。

2) **策略生成只能生成 Blueprint/DSL（+ DataIntent）**
- 禁止生成可执行脚本直接跑回测（必须经 Compiler）。

3) **裁决只允许 Gate + Dossier**
- PASS/FAIL/入库晋升必须引用 Dossier artifacts；纯文本意见无效。

4) **Final Holdout 不可污染**
- 生成/调参循环不得看到 holdout 细节，只允许 `pass/fail + 极少摘要`。

5) **模块必须有单元测试**
- 至少覆盖：lookahead/对齐/NaN/索引单调性/边界条件/时间窗端点。

6) **预算与停止条件强制**
- 候选策略数上限、参数网格上限、连续无提升停止，避免无限搜索挖假阳性。

7) **数据访问必须可审计**
- 任何数据获取必须通过 DataAccessFacade，并落 `fetch_request / fetch_result_meta / preview / error` 等证据。

---

## 2. 总体架构：五个平面（Planes）
- **Data Plane**：FetchAdapter → DataLake → DataCatalog（time‑travel：as_of / available_at）
- **Backtest Plane**：vectorbt（引擎）+ vectorbt adapter（协议翻译）
- **Deterministic Kernel（真理层）**：Contracts/Policies/Compiler/Runner/Gates/Dossier/Registry/Holdout/Budget
- **Agents Plane**：LLM Agents + Codex（全部通过 harness；只产候选/解释/诊断/计划）
- **UI Plane**：端到端证据审阅（不看源码）

---

## 3. Whole View 工作流（UI Checkpoint 驱动的状态机）
核心：把“对话式生成”变成“可回放的状态机流水线”。

### Phase‑0：Idea → Blueprint Draft（拆想法）
- UI 输入：品种/期限/频率/约束/想法描述
- 产物：IdeaSpec.json + Blueprint.draft.json + DataIntent.draft.json
- **审阅点 #1（UI）**：
  - 数据需求（DataIntent：asset/freq/universe/symbols/start/end/fields/adjust）
  - 评估协议（train/test/holdout，purge/embargo）
  - 关键假设（成交价、延迟、复权、缺失处理）
  - 预算（候选数、参数网格）

> 注：审阅点#1 不要求“已取到数据”，但必须能展示 DataIntent，并允许用户打开“自动补全样本（symbols 为空时）”等开关。

### Phase‑1：Blueprint → Pseudocode + Variable Dictionary + Trace Plan（你确认逻辑）
- 产物：
  - strategy_pseudocode.md（给人看）
  - variable_dictionary.json（变量 DAG：source/compute/depends_on/alignment/missing_policy/invariants）
  - calc_trace_plan.json（demo 如何抽样、画图、表格列、断言）
- **审阅点 #2（UI）**：
  - 变量定义 & 对齐：lag/window/端点/NaN/复权/成交价假设
  - 明确 DataIntent 的“符号补全策略”（如：list→sample→day）

### Phase‑2：Demo Tests（小样本可视化验证）
- 目标：不是追收益，是验证“逻辑是否按想法跑、数据是否对齐”
- 运行：确定性 demo_runner（通过 DataCatalog/DataAccessFacade 取数据）
- 产物：demo_dossier（K 线叠加 + trace 表 + sanity metrics + fetch evidence）
- **审阅点 #3（UI）**：
  - K 线叠加审核 entry/exit 是否符合预期
  - trace assertions（如 lag>=1、available_at<=as_of）是否通过
  - 不通过则回到 Phase‑1

### Phase‑3：Research Backtest（大规模回测 + 参数/品种）
- Compiler 产出 RunSpec
- Runner + vectorbt adapter 执行，写 Dossier
- GateRunner 执行 gate_suite，写 gate_results.json
- UI：Dossier 详情 + Gate 详情（证据链）

### Phase‑4：评估/改进/入库/组合（多 Agent + 可治理沉淀）
- Attribution（归因）→ Improvement（改进候选）→ Registry（经验卡）→ Composer（组合）

---

## 4. 核心对象模型（系统只认这些 I/O）
### 4.1 IdeaSpec（意图规格）
- universe/symbols/frequency/holding_horizon/constraints/paradigm_hint/evaluation_intent

### 4.2 DataIntent / FetchRequest（数据意图与执行请求）
**DataIntent（面向人/蓝图）**：描述“我要什么数据”  
**FetchRequest（面向执行）**：描述“怎么取数、怎么失败、怎么落证据”

建议 v1 schema 字段（示意）：
- mode: demo | backtest
- intent:
  - asset, freq, universe, symbols(nullable), start, end, adjust
  - fields(optional), dataset_hint(optional)
  - auto_symbols(bool), sample(n/method)
- policy:
  - on_no_data: error | pass_empty | retry
  - max_symbols/max_rows, retry_strategy(optional)

### 4.3 Blueprint（策略蓝图：可编译规格）
必须可静态分析：
- policy_bundle_id（只读引用）
- data_requirements（来自 DataIntent 的“需求表达”，而不是“怎么取数”）
- strategy_spec（DSL 或模块组合）
- engine_contract（vectorbt_signal_v1）
- evaluation_protocol（train/test/holdout，purge/embargo）
- report_spec（图/表/trace）

### 4.4 RunSpec（运行规格：Compiler 输出）
明确本次运行如何复现：
- blueprint_hash, data_snapshot_id, policy_bundle_id
- segments（含 as_of），param_grid，adapter，output_spec

### 4.5 Dossier（证据包：append‑only，UI 数据源）
建议目录（可扩展）：

dossiers/<run_id>/
  config_snapshot.json
  data_manifest.json
  fetch/                          # fetch 证据（必须）
    fetch_steps_index.json
    step_001_fetch_request.json
    step_001_fetch_result_meta.json
    step_001_fetch_preview.csv
    step_001_fetch_error.json     # only on failure
  metrics.json
  curve.csv
  trades.csv
  positions.csv
  exposures.csv
  cost_breakdown.csv
  gate_results.json
  calc_trace/
  diagnostics/
  reports/
  logs/

### 4.6 GateResults（确定性裁决）
- 每个 gate：pass/fail + metrics + threshold + reason + version

### 4.7 Experience Card（经验卡）
- 适用条件、失效模式、敏感性、风险画像、引用证据（run_id）、状态机（draft/challenger/champion/retired）

---

## 5. Contracts（Schema）体系：让 LLM/Codex 能产、Kernel 能编译、UI 能渲染
原则：版本化 + 可静态分析 + 对齐显式化 + 计划/结果分离。

### 5.1 必须落地的 Contracts（v1 最小集合）
- blueprint_schema_v1.json  
- signal_dsl_v1.json  
- variable_dictionary_v1.json  
- calc_trace_plan_v1.json  
- run_spec_schema_v1.json  
- dossier_schema_v1.json  
- diagnostic_spec_v1.json（临时诊断）
- gate_spec_v1.json（诊断晋升为 gate）
- experience_card_schema_v1.json  

### 5.2 Data Contracts（v1 新增）
- fetch_request_schema_v1.json
- fetch_result_meta_schema_v1.json
- data_snapshot_manifest_v1.json（DataLake ingest）
- datacatalog_query_v1.json（time‑travel query 请求/响应）

> 说明：fetch_request 是“执行输入”；data_requirements 属于 blueprint 的“需求表达”。二者要区分。

---

## 6. 模块与职责边界（Deterministic vs Agent）
### 6.1 Data Plane（主路：FetchAdapter → DataLake → DataCatalog）
#### 6.1.1 FetchAdapter（执行层）
- 统一入口：execute_fetch_by_intent(intent, policy, mode)（函数解析/执行由 runtime 负责）
- 必须落 fetch evidence（见 Dossier/fetch）
- 不允许 agent 直接 import provider/DB：只能通过 DataAccessFacade→FetchAdapter

#### 6.1.2 DataLake（可复现快照）
- Fetch 输出写入 raw parquet（或等价存储）
- 生成 snapshot_id + manifest（包含 request_hash、时间范围、字段、coverage、available_at 口径等）
- 同 snapshot_id/query 可复现

#### 6.1.3 DataCatalog（time‑travel 查询）
- query(snapshot_id, as_of, dataset, symbols, fields, freq) → 返回对齐后的 df + coverage stats
- 强制 `available_at <= as_of`，防止偷看未来
- 返回缺失统计、截断说明、对齐策略说明

> Phase‑3 推荐拆分：  
> 3A FetchAdapter MVP（先把取数证据与 UI 审阅打通）  
> 3B DataLake snapshot（止血：可复现与缓存）  
> 3C DataCatalog time‑travel（上强度：可得性约束与 gates 基础）

---

### 6.2 Backtest Plane
- vectorbt_adapter（deterministic）：RunSpec → vectorbt inputs → 产出 trades/curve/metrics/cost 写 Dossier
- 成本/成交价假设/延迟全部来自 policies（不可由策略覆盖）

---

### 6.3 Deterministic Kernel（真理层）
- contracts（schemas + 校验）
- policies（冻结）
- compiler（Blueprint → RunSpec；注入预算；合规校验）
- runner（执行回测，写 Dossier）
- gate_runner（执行 gates，写 GateResults）
- holdout_vault（锁箱隔离）
- dossier_builder（图/表/报告生成，append‑only）
- registry（TrialLog + Experience Cards）
- budget_stop（预算/停止条件）

---

### 6.4 Agents Plane（LLM + Codex，全部通过 harness 运行）
Agents 只能输出候选与解释，不能裁决。推荐分工：

- Orchestrator（deterministic）：状态机编排/权限/回放/审阅点控制（不是 LLM）
- Intent Agent：Idea → Blueprint.draft + DataIntent.draft
- StrategySpec Agent：Blueprint.draft → DSL + VariableDict + TracePlan + Pseudocode
- Spec‑QA Agent：静态检查（lookahead/对齐/缺失/端点），输出风险清单与 demo_test_plan
- Demo Agent：触发 demo run（确定性 runner），整理 demo_dossier
- Backtest Agent：触发大规模 backtest（确定性 runner）
- Attribution Agent：基于 Dossier 产归因报告（必须引用 artifacts）
- Improvement Agent：基于 gate_fail + 归因，生成 Blueprint diff（受预算限制）
- Registry Curator：PASS 才可入库，生成 Experience Card
- Composer Agent：基于 Cards 组合并回测（仍走 RunSpec/Dossier/Gates）
- Diagnostics Agent（Codex 驱动）：从 dossier 派生 DiagnosticSpec 并运行落盘

#### 6.4.1 数据获取的唯一通道：DataAccessFacade + FetchPlanner
- DataAccessFacade：对 agent 暴露 `get(fetch_request)->(df, meta, snapshot_id?)`
- FetchPlanner（规则优先）：当 symbols 为空且 auto_symbols=true 时执行 list→sample→day 等多步取数
- Planner 输出每步都必须落证据（step index），避免黑盒

---

## 7. Codex 的定位：探索者 + 工具工，不是裁判
### 7.1 临时诊断（Ephemeral Diagnostics）
- Codex 产出 DiagnosticSpec（声明式方法：输入 artifacts、步骤、输出图表/表格）
- deterministic runner 执行并落 `dossiers/<run_id>/diagnostics/...`
- UI 展示：方法（spec）+ 证据（artifacts）+ 结论（report，必须引证）

### 7.2 晋升机制（Promote → Gate）
当某诊断通用且稳定：
- DiagnosticSpec 升级为 GateSpec（加入阈值与 reason）
- Codex 生成 gate 插件代码 + tests
- 走治理流程发布 gate_suite 新版本

---

## 8. UI 信息架构（不看源码的审阅体验）
MVP 必须覆盖以下能力（页面可合并）：
1) Idea 输入（自然语言 + 约束表单 + 自动补全样本开关）
2) Blueprint Review（含 policy 引用、data_requirements、evaluation_protocol）
3) Pseudocode & Variable Dictionary Review（审阅点#2）
4) Calc Trace Review（K 线叠加 + trace 表，审阅点#3）
5) Runs 队列（状态/预算/日志摘要）
6) Dossier 详情（曲线/回撤/交易/成本/暴露/分段）
7) Gate 详情（逐项 pass/fail + 证据链接）
8) Registry & Composer（经验卡、组合回测）

**新增强制 UI 能力（v0.5）：Fetch Evidence Viewer**
- 展示 fetch_steps_index.json
- 每步 fetch_request/meta/preview/error 可点开查看
- 允许用户在审阅点#2/#3 发现“取数不对”并回退

---

## 9. “取到正确的数”的工程化验收口径
必须把“数据正确性”从口头变成可测试：

1) 结构性检查（Schema/Index/Monotonicity）
- 时间索引单调递增、无重复
- 必要字段齐全（OHLCV 等）
- dtype 合理，缺失率统计一致

2) Golden Queries（最小黄金回归集）
- 固定 symbol + 固定窗口（10 个以内）
- 记录 row_count、min/max date、columns、hash（允许可控漂移则定义阈值）
- 漂移必须在报告中出现（可追溯 provider 变化）

3) 可得性检查（time‑travel）
- as_of 早于 available_at 的数据必须不可见
- 这既是 DataCatalog 的职责，也是 Gate(no_lookahead) 的基础

---

## 10. 推荐仓库结构（主路对齐）
quant-eam/
  README.md
  GOVERNANCE.md

  contracts/
  policies/

  fetch_adapter/                 # 或 qa_fetch/（统一命名后再迁移）
  data_lake/
  datacatalog/

  backtest/
    adapters/vectorbt_signal_v1.py

  kernel/
    compiler.py
    runner.py
    demo_runner.py
    gate_runner.py
    dossier_builder.py
    registry.py
    holdout_vault.py
    budget.py
    contracts/validate.py

  agents/
    orchestrator/
    intent/
    strategy_spec/
    spec_qa/
    demo/
    backtest/
    attribution/
    improvement/
    diagnostics/

  ui/
    server/
    static/
    templates/

  dossiers/
  registry/
  trial_log/

  docker/
    Dockerfile.api
    Dockerfile.worker
    docker-compose.yml

---

## 11. “不跑偏”检查清单（每次新增功能前先对齐）
- 是否新增/修改了 contract？是否版本化？是否有 schema 校验与 examples/tests？
- 是否触碰 policies？是否走治理流程？
- 是否有确定性产物落到 dossier（append‑only）？UI 是否只读展示 dossier？
- 是否违反“裁判只能 GateRunner”？
- 是否可能污染 holdout？
- 是否设置预算与停止条件？
- 是否包含 tests + docs？
- 是否绕过 DataAccessFacade 直接取数据？（必须禁止）

---

## 12. 版本路线（建议）
- v0.5：FetchAdapter 并入主路 + Fetch contracts + UI fetch evidence + demo 闭环稳定
- v0.6：DataLake snapshot 完整化 + DataCatalog time‑travel + gate(no_lookahead/delay) 强化
- v0.7：Registry/Composer 完整闭环 + 诊断晋升机制规模化
