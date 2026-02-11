# Quant‑EAM Whole View Framework（v0.4‑draft）
> 目的：作为“总蓝图 + 内部细节约束”的对齐文档，防止施工跑偏。  
> 环境：Linux + Docker + Python。  
> 基于：Quant‑EAM（wequant + vectorbt）v0.3 架构草案（并补齐策略生成分工、demo 验证、Codex 诊断沉淀）。  

---

## 0. 你要构建的系统是什么（Definition）
这是一个 **可审计的经验资产系统**（Experience Asset Machine, EAM），不是“策略工厂”。

系统必须做到：
- 用户只在 **Web UI** 输入想法、选择品种与期限、逐步审核证据（不看源码）。
- 系统将想法固化为 **可编译规格（Blueprint/DSL）**，由确定性 Kernel 编译成 RunSpec，跑回测，产出 **证据包（Dossier）**。
- 策略是否“有效”的裁决，必须由 **GateRunner（确定性 Gate 套件）**给出（PASS/FAIL），并可回放、可追溯。
- 通过 **Experience Card（经验卡）**沉淀策略模块/验证方法/诊断方法，并支持组合（Portfolio/Composer）。

---

## 1. 系统硬约束（写入 GOVERNANCE.md + CI 强制）
这些约束是“真理”，任何 Agent/Codex/脚本不能绕过：

1) **Policies 只读**
- execution/cost/as-of/risk/gate_suite/latency 等 policy 只能“引用 policy_id”，禁止策略覆盖或内联修改。

2) **策略生成只能生成 Blueprint/DSL**
- 禁止生成“可执行策略脚本”直接跑回测（必须经 Compiler）。

3) **裁决只允许 Gate + Dossier**
- PASS/FAIL/入库晋升必须引用证据包 artifacts；纯文本意见无效。

4) **Final Holdout 不可污染**
- 生成/调参循环不得看到 holdout 细节，只允许 `pass/fail + 极少摘要`。

5) **模块必须有单元测试**
- 至少覆盖：lookahead/对齐/NaN/索引单调性/边界条件。

6) **预算与停止条件强制**
- 候选策略数上限、参数网格上限、连续无提升停止，避免无限搜索挖假阳性。

---

## 2. 总体架构：五个平面（Planes）
- **Data Plane**：wequant → Data Lake → DataCatalog（time‑travel：as_of / available_at）
- **Backtest Plane**：vectorbt（引擎）+ vectorbt adapter（协议翻译）
- **Deterministic Kernel（真理层）**：Contracts/Policies/Compiler/Runner/Gates/Dossier/Registry/Holdout/Budget
- **Agents Plane**：GPT Pro Agents + Codex CLI（只产候选、解释、诊断/测试计划）
- **UI Plane**：端到端可视化审阅（不要求用户看源码）

---

## 3. Whole View 工作流（UI Checkpoint 驱动的状态机）
核心：把“对话式生成”变成“可回放的状态机流水线”。

### Phase‑0：Idea → Blueprint Draft（拆想法）
- UI 输入：品种/期限/频率/约束/想法描述
- 产物：IdeaSpec.json + Blueprint.draft.json
- **审阅点 #1（UI）**：数据需求/范式/评估协议/关键假设

### Phase‑1：Blueprint → Pseudocode + Variable Dictionary + Trace Plan（你确认逻辑）
- 产物：
  - strategy_pseudocode.md（给人看）
  - variable_dictionary.json（变量/依赖/对齐/缺失处理）
  - calc_trace_plan.json（demo 要怎么画、怎么抽样、怎么验）
- **审阅点 #2（UI）**：变量定义 & 对齐（lag/window/端点/NaN/复权/成交价假设）

### Phase‑2：Demo Tests（小样本可视化验证）
- 目标：不是追收益，是验证“逻辑是否按想法跑”
- 产物：demo_dossier（K 线叠加 + trace 表 + sanity metrics）
- **审阅点 #3（UI）**：K 线叠加审核 entry/exit 是否符合预期；不通过则回到 Phase‑1

### Phase‑3：Research Backtest（大规模回测 + 参数/品种）
- Compiler 产出 RunSpec，Runner + vectorbt adapter 执行，写入 Dossier
- GateRunner 执行 gate_suite，写 gate_results.json
- UI：Dossier 详情 + Gate 详情（证据链）

### Phase‑4：评估/改进/入库/组合（多 Agent + 可治理沉淀）
- Attribution（归因）→ Improvement（改进候选）→ Registry（经验卡入库）→ Composer（组合）

---

## 4. 核心对象模型（系统只认这些 I/O）
### 4.1 IdeaSpec（意图规格）
- universe/symbols/frequency/holding_horizon/constraints/paradigm_hint/evaluation_intent

### 4.2 Blueprint（策略蓝图：可编译规格）
必须可静态分析：
- policy_bundle_id（只读引用）
- data_requirements（字段/频率/可得性/延迟假设）
- strategy_spec（DSL 或模块组合）
- engine_contract（vectorbt_signal_v1）
- evaluation_protocol（train/test/holdout，purge/embargo）
- report_spec（图/表/trace）

### 4.3 RunSpec（运行规格：Compiler 输出）
明确本次运行如何复现：
- blueprint_hash, data_snapshot_id, policy_bundle_id
- segments（含 as_of），param_grid，adapter，output_spec

### 4.4 Dossier（证据包：append‑only，UI 数据源）
建议目录：

dossiers/<run_id>/
config_snapshot.json
data_manifest.json
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


### 4.5 GateResults（确定性裁决）
- 每个 gate：pass/fail + metrics + threshold + reason + version

### 4.6 Experience Card（经验卡）
- 适用条件、失效模式、敏感性、风险画像、引用证据（run_id）、状态机（draft/challenger/champion/retired）

---

## 5. Contracts（Schema）体系：让 LLM/Codex 能产、Kernel 能编译、UI 能渲染
> 原则：版本化 + 可静态分析 + 对齐显式化 + trace 计划/结果分离。

### 5.1 必须落地的 Contracts（v1）
1) blueprint_schema_v1.json  
2) signal_dsl_v1.json（首版 DSL，贴合 vectorbt：entry/exit/sizing/risk/constraints/execution_ref）  
3) variable_dictionary_v1.json（变量 DAG：source/compute/depends_on/alignment/missing_policy/invariants）  
4) calc_trace_plan_v1.json（demo 如何画/抽样/表格列/断言）  
5) run_spec_schema_v1.json  
6) dossier_schema_v1.json  
7) diagnostic_spec_v1.json（Codex/Agent 的“临时诊断”声明式描述）  
8) gate_spec_v1.json（诊断晋升为 Gate 的声明式描述）  
9) experience_card_schema_v1.json  

> 说明：trace **计划**由 LLM/Codex 生成；trace **结果**由 Runner（确定性）生成。

---

## 6. 模块（Modules）与职责边界（Deterministic vs Agent）
### 6.1 Data Plane
- wequant_adapter：标准化 fetch → ingest_manifest
- data_lake：parquet + manifest + snapshot_id
- datacatalog：time‑travel 查询；强制 `available_at <= as_of`；对齐/缺失统计

### 6.2 Backtest Plane
- vectorbt_adapter（deterministic）：RunSpec → vectorbt inputs → 产出 trades/curve/metrics/cost 写 Dossier

### 6.3 Deterministic Kernel（真理层）
- contracts（schemas + 校验）
- policies（冻结：execution/cost/as-of/risk/gate_suite/latency）
- compiler（Blueprint → RunSpec；注入预算；合规校验）
- runner（执行回测，写 Dossier）
- gate_runner（执行 gates，写 GateResults）
- holdout_vault（锁箱隔离）
- dossier_builder（图/表/报告生成，append‑only）
- registry（TrialLog + Experience Cards）
- budget_stop（预算/停止条件）

### 6.4 Agents Plane（LLM + Codex，全部通过 harness 运行）
推荐 Agent 分工（对应你 whole view）：
- Orchestrator：状态机编排/权限/回放/审阅点控制（不是 LLM）
- Intent Agent：Idea → Blueprint.draft
- StrategySpec Agent：Blueprint.draft → DSL + VariableDict + TracePlan + Pseudocode
- Spec‑QA Agent：静态检查（lookahead/对齐/缺失/端点），输出风险清单与 demo_test_plan
- Demo Agent：触发 demo run（确定性 runner），整理 demo_dossier
- Backtest Agent：触发大规模 backtest（确定性 runner）
- Attribution Agent：基于 Dossier 产归因报告（必须引用 artifacts）
- Improvement Agent：基于 gate_fail + 归因，生成 Blueprint diff（受预算限制）
- Registry Curator：PASS 才可入库，生成 Experience Card
- Composer Agent：基于 Cards 组合并回测（仍走 RunSpec/Dossier/Gates）
- Diagnostics Agent（Codex 驱动）：从 dossier 派生“诊断方法”并写 DiagnosticSpec/产物

---

## 7. Codex CLI 的定位：探索者 + 工具工，不是裁判
你希望 Codex “看结果找规律/提出验证方法”——这必须制度化：

### 7.1 临时诊断（Ephemeral Diagnostics）
- Codex 产出 DiagnosticSpec（声明式方法：输入 artifacts、步骤、输出图表/表格）
- deterministic runner 执行并落入 `dossiers/<run_id>/diagnostics/...`
- UI 展示：方法（spec）+ 证据（artifacts）+ 结论（report，引证 artifacts）

### 7.2 晋升机制（Promote → Gate/Library）
当某诊断通用且稳定：
- 将 DiagnosticSpec 升级为 GateSpec（加入 pass/fail 阈值与 failure reason）
- Codex 生成 gate 插件代码 + tests
- 走治理流程：发布 gate_suite_v2（版本化）

---

## 8. UI 信息架构（不看源码的审阅体验）
必须覆盖 8 个页面（首版可合并）：
1) Idea 输入（自然语言 + 约束表单）
2) Blueprint Review（含 policy 引用、数据需求、评估协议）
3) Pseudocode & Variable Dictionary Review（审阅点#2）
4) Calc Trace Review（K 线叠加 + trace 表，审阅点#3）
5) Runs 队列（状态/预算/日志摘要）
6) Dossier 详情（曲线/回撤/交易/成本/暴露/分段）
7) Gate 详情（逐项 pass/fail + 证据链接）
8) Registry & Composer（经验卡、组合回测）

---

## 9. 仓库与运行形态（Linux + Docker + Python）
推荐仓库结构：

quant-eam/
README.md
GOVERNANCE.md

contracts/
policies/

wequant_adapter/
data_lake/
datacatalog/

backtest/
adapters/vectorbt_signal_v1.py

kernel/
compiler.py
runner.py
gate_runner.py
dossier_builder.py
registry.py
holdout_vault.py
budget.py

agents/
orchestrator/
intent/
strategy_spec/
spec_qa/
report/
improvement/
diagnostics/

ui/
server/ # FastAPI + Jinja/HTMX（或 Streamlit MVP）
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

## 10. “不跑偏”检查清单（每次新增功能前先对齐）
- 是否新增/修改了 contract？是否版本化？是否有 schema 校验与回放样例？
- 是否触碰 policies？是否走治理流程（CodeOwners/CI）？
- 是否有确定性产物落到 dossier？UI 是否只读展示 dossier？
- 是否违反“裁判只能 GateRunner”？
- 是否可能污染 holdout？
- 是否设置预算与停止条件？
- 是否包含 tests + docs？

---

## 11. 版本路线（建议）
- v0.4：补齐 contracts（Blueprint/DSL/VariableDict/Trace/Diagnostic）+ demo trace + UI 审阅点
- v0.5：Gate suite 扩展 + Registry/Composer + 诊断晋升机制
- v0.6：event‑driven adapter（可选）+ 更强的组合/风险模型
