# Quant-EAM：量化经验资产管理系统框架与流程（v1）

> 目标：前期把接口/口径/纪律一次性钉死；中期策略研发变成“一句话”；后期用沉淀的经验资产组装模型与组合。
> 约束：所有“有效性”必须由数据与确定性 Gate 裁决；任何口径漂移/未来函数/统计泄漏都应被系统拒绝。

---

## 1. 背景与目标

你已具备：
- 多品种数据接口：股票（行情/技术指标）、TF 期货、债券等
- 既有回测引擎：用于验证策略想法

你要构建的是 **经验资产管理系统（Experience Asset Management, EAM）**，不是“AI 策略生成工厂”。

系统目标：
1. 将“想法”固化为可编译规格（Spec/Blueprint），自动验证与归档
2. 让 Codex 自动生成/组合模块并跑回测与压测（必须产出证据包）
3. 通过 Gate 的结果沉淀为 **Experience Cards（经验卡）**，进入长期经验户
4. 提供每日/定期复评（可选）：只允许配置级自适应（启停/调权/小范围参数漂移）
5. 后期用经验卡组装模型（regime gating / ensemble / allocator）

---

## 2. 非目标（明确不做，避免跑偏）

- 不做“端到端 LLM 直接下单决策”（不可复现/难压测/泄漏风险高）
- 不做“在回测时实时检索 PDF/研报并即时问 LLM 决策”（会引入未来文档与索引泄漏）
- 不允许“策略自行覆盖执行/成本/as-of口径”（会导致经验不可比）

---

## 3. 关键原则：防跑偏六条硬约束（写入 GOVERNANCE.md 并用 CI 强制）

1. **Execution/Cost/As-of Policy 只读**
   - 策略/模块只能引用 `policy_id`，禁止覆盖或内联修改
2. **策略生成只能生成 Blueprint**
   - 禁止绕开编译器写“策略脚本”直接跑回测
3. **裁判只允许 Gate + Dossier**
   - 任何 PASS/FAIL/晋升必须引用证据包产物；纯文本意见无效
4. **锁箱（Final Holdout）不可污染**
   - 生成/调参循环不得获得锁箱细节（只拿 pass/fail + 极少摘要）
5. **模块必须有单元测试**
   - 至少覆盖：lookahead/对齐/NaN/索引单调性
6. **实验预算与停止条件强制**
   - 每轮候选数上限、连续无提升停止，避免无限搜索必挖到假阳性

---

## 4. 总体架构：三层 + 两条闭环

### 4.1 三层架构（谁能改什么必须明确）

**Layer 1：物理层（不可谈判/冻结）**
- 数据可得性（as-of/延迟/修订）
- 交易日历
- 执行口径（成交时点/撮合）
- 成本模型（手续费/滑点/冲击）
- 期货：连续合约/展期规则/保证金简化
- 风控硬约束（杠杆、单标的上限、换手上限等）

> 物理层写入 policies/ 与 contracts/，必须只读。

**Layer 2：研究层（可探索但受控）**
- 模块库：Entry / Exit / Risk / Sizing / Fusion
- Blueprint 组合（在注册表允许的模块与参数范围内）
- 实验设计：分阶段筛选、消融、交互项测试
- 回测/压测与归因：生成 Dossier

**Layer 3：治理层（你说了算）**
- 晋升：Draft → Challenger（影子期）→ Champion
- 下线：Champion → Retired
- 失败模式沉淀为新 Gate/Policy（防重复踩坑）

### 4.2 两条闭环（Slow/Fast）

**Slow Loop（研发固化）**
Idea/Blueprint → 编译检查（schema/as-of/policy）→ 回测 → Gate → Dossier → 经验卡入库

**Fast Loop（每日/定期复评，可选）**
Market Snapshot → Scoreboard 更新 → 启停/调权建议（只改配置）→ 日报

---

## 5. 核心产物（系统只认这些对象）

1. **Contracts（契约）**
   - data_schema.yaml / availability.yaml / document_contract.yaml
   - intent_schemas.json / alpha_signal_schema.json（可选）
   - blueprint_schema.json / dossier_schema.json / event_schema.json / feature_schema.yaml

2. **Policies（冻结口径）**
   - execution_equity_v1.yaml / execution_futures_tf_v1.yaml / execution_bond_v1.yaml
   - cost_model_v1.yaml / altdata_latency_v1.yaml / risk_limits_global_v1.yaml
   - gate_suite_v1.yaml

3. **Blueprint（策略蓝图）**
   - 结构化描述：模块选择与参数、引用的 policy_id、评估协议

4. **Dossier（证据包，append-only）**
   - metrics、曲线、交易明细、压测结果、消融/归因、配置快照、版本哈希、日志

5. **Gate Results（确定性裁决）**
   - gate_results.json：每项 Gate 的 pass/fail 与关键指标

6. **Experience Card（经验卡）**
   - 适用品种/频率/行情标签、失效模式、成本敏感、证据摘要、版本、半衰期建议、状态（draft/challenger/champion）

7. **Trial Log（试验台账）**
   - 记录每次实验：blueprint_hash、数据版本、policy_id、结果摘要、是否晋升

---

## 6. 项目目录结构（建议）

quant-eam/
GOVERNANCE.md
README.md

contracts/
data_schema.yaml
availability.yaml
document_contract.yaml
event_schema.json
feature_schema.yaml
blueprint_schema.json
dossier_schema.json
intent_schemas.json

policies/
execution_equity_v1.yaml
execution_futures_tf_v1.yaml
execution_bond_v1.yaml
cost_model_v1.yaml
altdata_latency_v1.yaml
risk_limits_global_v1.yaml
gate_suite_v1.yaml

data/
ingestion/
lake/ # append-only
metadata/ # sqlite/postgres

index/ # 可选（必须支持available_at过滤）
fts/
vector/

events/
extractors/
store/

features/
build_features.py
store/

skills/
entry/
exit/
risk/
sizing/
fusion/
_registry.yaml

blueprints/
templates/
candidates/
champions/

runner/
compiler.py
backtest_adapter.py
dossier_builder.py
gate_runner.py

dossiers/
<run_id>/...

trial_log/
trials.sqlite

registry/
experience_cards/
scoreboard/

orchestrator/
run.py # eam run "一句话"
prompts/
budget_policy.yaml

composer/
assemble.py
allocator.py


---

## 7. “一句话策略研发”工作流（中期核心）

### 7.1 对外唯一入口（建议 CLI）

- `eam run "一句话描述你的策略想法"`  
  例：
  - `eam run "股票日频，趋势突破，加入最近低点止损，控制换手<=0.3，成本敏感，做walk-forward验证"`
  - `eam run "TF期货，趋势跟随，考虑展期成本，延迟+1bar压测必须通过"`

### 7.2 编排器（Orchestrator）必须做的事

1. 解析一句话 → 生成 `IdeaSpec.json`（结构化意图）
2. 根据 `skills/_registry.yaml` 构建可用模块集合（按品种/频率过滤）
3. 让 Codex 输出若干候选 `Blueprint.json`（带实验计划、消融要求）
4. 对每个 Blueprint 执行：
   - `compiler`: schema 检查 + as-of 检查 + policy 锁定检查
   - `runner`: 调用回测引擎产出 Dossier
   - `gate_runner`: 跑 Gate Suite 产出 gate_results.json
5. 根据 gate_results 判定 PASS/FAIL
6. PASS → 生成 Experience Card（默认 Challenger），入库 registry；FAIL → 记录失败原因与阻断项
7. 写 trial_log，应用预算与停止条件

### 7.3 Codex 的职责边界（必须遵守）

Codex 只允许产出：
- Blueprint（结构化）
- 缺失模块时新增 skills/ 模块 + 单测
- 报告草稿（必须引用 Dossier 字段），但不改变裁决

Codex 不允许：
- 修改 policies/ 或 contracts/（CI 拦截）
- 绕过 compiler/gate 直接“给结论”

---

## 8. 文档型另类数据（新闻/研报）接入架构（可回测挖掘）

### 8.1 核心原则：time-travel + 防语料泄漏

- 历史时点 t，只能使用 `available_at <= t` 的文档/事件/特征
- 任何语料统计（TF-IDF/topic/标准化/训练）必须 rolling-fit 或 expanding-fit，不能用全语料

### 8.2 三段式管线（强制）

**Document Pack（原文+元数据+版本+索引） → Event Store（离线结构化事件） → Feature Store（数值特征）**

回测只消费 Feature Store；禁止回测时现场读 PDF 再问模型。

### 8.3 必备字段（document_contract.yaml）

- doc_id, source, doc_type
- published_at, received_at, available_at（关键）
- revision_id/version, supersedes_doc_id（版本链）
- content_uri, content_hash
- entities/asset_ids（映射标的）
- ingest_pipeline_version

### 8.4 文档特有 Gate（加入 gate_suite_v1.yaml）

- latency +1bar / +1day
- source dropout（去掉某源是否崩）
- revision sensitivity（只用初版 vs 最终版）
- coverage bias（覆盖率不足禁止晋升）

---

## 9. 后期：用经验资产组装模型（Model Composer）

当经验卡积累到一定规模后，进入 composer/：

1. **Regime Gating**
   - 市场状态（趋势/震荡、高/低波动、流动性）→ 选择/加权 Champion 模块
2. **Ensemble / Stacking**
   - 多个模块输出作为输入，训练二级融合器（rolling/expanding）
3. **Allocator（资金分配器）**
   - 在多个 Champion 策略之间做风险平价/CVaR/相关性约束分配

> 这阶段的核心是“复用与组合”，不是继续无限发明。

---

## 10. 实施 Phase（按你的三阶段目标组织）

### Phase A（前期）：接口与口径冻结
**目标**：contracts + policies + gate_suite 固定，并由 compiler 强制执行。

交付物：
- contracts/*（含文档契约）
- policies/*（执行/成本/as-of/延迟）
- runner/compiler.py（能拒绝违规）
- smoke tests（保证只读约束生效）

DoD：
- 策略无法覆盖 policy
- as-of 违规在编译期失败
- Dossier 目录规范稳定

---

### Phase B（中期）：一句话研发全自动
**目标**：实现 `eam run "一句话"` 的完整闭环。

交付物：
- orchestrator/run.py
- trial_log（sqlite）
- dossier_builder + gate_runner
- 最小技能库 + 三段 Harness（Entry/Exit/Integration）

DoD：
- 一条命令完成：生成候选 → 回测 → Gate → 入库草案
- 连续无提升自动停止
- 任何“通过”都能复现并定位证据

---

### Phase C（后期）：经验驱动模型组装 + 复评（可选）
**目标**：从经验卡组装模型/组合，并实现配置级自适应复评。

交付物：
- composer/assemble.py + allocator.py
- registry/scoreboard（短期记分牌）
- daily reports（启停/调权建议 + 证据）

DoD：
- 只改配置，不改结构（结构改动回到 Phase B 走 Gate）
- 漂移警报与下线机制可用

---

## 11. 附录：示例对象（可作为模板）

### 11.1 Blueprint（示意）

```json
{
  "strategy_id": "equity_trend_breakout_v1",
  "asset_pack": "equity",
  "frequency": "1d",
  "policy_id": "execution_equity_v1",
  "modules": {
    "entry": {"id": "breakout_entry_v1", "params": {"lookback": 20}},
    "exit": {"id": "swing_low_stop_v1", "params": {"lookback": 10}},
    "risk": {"id": "drawdown_guard_v1", "params": {"max_dd": 0.12}},
    "sizing": {"id": "target_vol_v1", "params": {"vol_target": 0.10}}
  },
  "evaluation": {
    "protocol": "walk_forward",
    "gates": "gate_suite_v1"
  }
}

11.2 Dossier 目录（示意）

dossiers/<run_id>/
  config_snapshot.json
  metrics.json
  curve.csv
  trades.csv
  gate_results.json
  ablation.json
  regime_buckets.json
  logs/

11.3 Experience Card（示意）

card_id: equity_trend_breakout_v1__2026-02-05
status: challenger
asset_pack: equity
frequency: 1d
depends_on:
  features: [ohlcv, tech_indicators]
  altdata: false
edge_profile:
  cost_sensitive: high
  capacity_risk: medium
regime_tags:
  - trend
  - mid_high_vol
failure_modes:
  - range_bound
  - gap_risk
evidence:
  run_id: "20260205_103012_abcd"
  gates_passed: ["no_lookahead", "cost_x2", "delay_plus_1bar", "param_perturbation"]
half_life_days: 180