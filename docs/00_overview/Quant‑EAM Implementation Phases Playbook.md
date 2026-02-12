# Quant‑EAM Implementation Phases Playbook（Linux + Docker + Python）
> 目的：把系统拆成可执行的 Phase，给 Codex 逐步实现。  
> 每个 Phase 统一输出：实施方案、目标、背景、编码内容、文档编写、验收标准（DoD）。  
> 原则：先打通端到端闭环（UI 可审阅 + Dossier/Gates 可回放），再扩展 agent/组合/诊断晋升。

---

## 0. 施工总原则（Codex 任务组织）
### 0.1 单次 Codex 任务必须满足
- **只改一个模块目录**（例如仅 `datacatalog/` 或仅 `kernel/`）。
- 必须包含：**代码 + tests + docs（README）**。
- 不得改动：`policies/`、`contracts/`（除非 Phase 明确要求，并走治理流程）。
- 所有输出必须能在 Docker 环境中一键运行：`docker compose up` + `pytest`.

### 0.2 全局质量门槛（CI 必须强制）
- `pytest -q` 全绿
- schema 校验：Blueprint/RunSpec/Dossier 等 JSON 必须通过校验
- 静态检查：ruff/black/mypy（可选但推荐）
- 产物一致性：runner 必须落盘 dossier（append-only），并带 config_snapshot/hash

---

## 1. 技术栈建议（可替换，但先固定）
### 1.1 基础
- Python 3.11+
- Docker + docker-compose
- 依赖管理：`uv` 或 `poetry`（二选一；先固定一种）
- 测试：pytest
- 结构化配置：pydantic + YAML
- 可视化：matplotlib/plotly（二选一；先固定）

### 1.2 服务（MVP）
- API/UI：FastAPI + Jinja2 + HTMX（减少前端负担）
- Worker：python worker 进程（同镜像）
- 存储：
  - artifacts（dossier）先用本地文件系统（volume）
  - metadata 用 sqlite（MVP），后续可切 Postgres

---

## 2. Phase 模板（后续你要我写每个 phase 标准内容，就按这个模板）
> 你后续每次点名 “Phase‑X”，我会按此结构输出“可直接喂给 Codex 的任务书”。

### Phase‑X 标准输出结构
1) **目标（Goal）**  
2) **背景（Background）**  
3) **范围（Scope / Out‑of‑Scope）**  
4) **实施方案（Implementation Plan）**  
5) **编码内容（Code Deliverables）**：文件/目录/接口/命令  
6) **文档编写（Docs Deliverables）**  
7) **验收标准（Acceptance / DoD）**：可执行命令 + 预期产物  
8) **Codex 任务卡（Task Card）**：可复制的 prompt（含边界与禁止项）  

---

## 3. Phase 列表（推荐施工顺序）

### Phase‑0：Repo Bootstrap（工程地基）
**目标**
- 建立可运行的 monorepo、Docker、测试与基础工具链。

**背景**
- 没有可复现环境，后续任何“回放/审计”都会失真。

**编码内容**
- `pyproject.toml` / lockfile
- `docker/`：Dockerfile.api、Dockerfile.worker
- `docker-compose.yml`：api + worker + (sqlite volume) + (optional redis)
- `Makefile`：`make up / make test / make fmt`

**文档**
- README：如何启动、如何跑测试

**验收（DoD）**
- `docker compose up` 能启动空服务
- `pytest` 可跑通（至少 1 个示例测试）

**Codex 任务卡**
- “在 quant-eam/ 初始化 Python 项目 + Docker compose + pytest skeleton，并提供 README/Makefile。”

---

### Phase‑1：Contracts v1（Blueprint/RunSpec/Dossier/Trace/VariableDict）
**目标**
- 固化最小可用 schema（版本化），并提供校验器与示例样本。

**背景**
- LLM/Codex 的输出如果没有 contract，会导致 Kernel/UI 无法稳定对接。

**编码内容**
- `contracts/`：
  - `blueprint_schema_v1.json`
  - `signal_dsl_v1.json`
  - `variable_dictionary_v1.json`
  - `calc_trace_plan_v1.json`
  - `run_spec_schema_v1.json`
  - `dossier_schema_v1.json`
- `kernel/contracts/validate.py`：统一校验入口
- `contracts/examples/`：每个 schema 至少 1 个合法样本 + 1 个非法样本

**文档**
- `contracts/README.md`：版本策略、字段语义（尤其 as_of/available_at/lag）

**验收（DoD）**
- `python -m kernel.contracts.validate contracts/examples/blueprint_ok.json` 返回成功
- 非法样本返回明确错误

**Codex 任务卡**
- “仅在 contracts/ 与 kernel/contracts/ 下实现：schema + validator + examples + tests，不触碰其它模块。”

---

### Phase‑2：Policies v1（冻结 + 治理）
**目标**
- execution/cost/as-of/latency/risk/gate_suite 的 policy 文件落地，并冻结治理。

**背景**
- 你需要明确：成交价假设、成本模型、可得性延迟口径、风险限制等，且策略不能改。

**编码内容**
- `policies/*.yaml`（v1）
- `GOVERNANCE.md`：Policies/Contracts 变更流程
- CI hook：禁止未走流程修改 policies/contracts

**文档**
- `policies/README.md`

**验收**
- Blueprint 不引用 policy_id -> Compiler 必须拒绝
- 修改 policies 未按流程 -> CI fail（本地可用 pre-commit 先拦）

---

### Phase‑3：Data Plane MVP（wequant_adapter + data_lake + datacatalog）
**目标**
- 形成可复现的数据快照（snapshot_id）与 time‑travel 查询（as_of）。

**背景**
- 任何回测与 gate 都要建立在“数据可复现 + 不偷看未来”的基础上。

**实施方案**
- wequant_adapter：标准化 fetch → raw parquet + ingest_manifest
- data_lake：parquet partition + snapshot manifest + metadata sqlite
- datacatalog：`query(snapshot_id, as_of, dataset, symbols, fields, freq)` 返回对齐后 df + coverage stats；强制 `available_at <= as_of`

**编码内容**
- `wequant_adapter/`
- `data_lake/`
- `datacatalog/`

**文档**
- 每个模块 README：输入/输出/示例命令

**验收**
- 同 snapshot_id + 同 query 可复现一致结果
- as_of 早于 available_at 的数据不会出现（用单测验证）

---

### Phase‑4：Backtest Plane MVP（vectorbt_adapter + Runner + 基础 Dossier）
**目标**
- 最小闭环：RunSpec → vectorbt → Dossier（curve/trades/metrics/cost）。

**背景**
- 先实现“signal -> portfolio”向量化范式，覆盖你最常用的策略类型。

**编码内容**
- `backtest/adapters/vectorbt_signal_v1.py`
- `kernel/runner.py`：调用 adapter，写 dossier
- `kernel/dossier_builder.py`：生成 metrics.json、curve.csv、trades.csv

**文档**
- `backtest/README.md`：支持的 DSL 字段与限制
- `dossier/README.md`：目录规范

**验收**
- 运行一个 example Blueprint 能产出完整 dossier 目录
- 成本来自 policy（策略不可自定义）

---

### Phase‑5：Gate Suite v1 + HoldoutVault（确定性裁判）
**目标**
- 实现最小 gate 套件与锁箱隔离，打通 PASS/FAIL。

**背景**
- 没有 gate，系统就变成“跑出曲线就算完”，无法治理与入库。

**编码内容**
- `kernel/gate_runner.py`
- `kernel/holdout_vault.py`
- `policies/gate_suite_v1.yaml`（引用具体 gate）
- gates（至少）
  - no_lookahead
  - delay_plus_1bar
  - cost_x2
  - param_perturb（鲁棒性）
  - holdout_summary（只给摘要）

**文档**
- `kernel/gates/README.md`：每个 gate 的指标/阈值/失败原因

**验收**
- gate_results.json 写入 dossier
- holdout 细节不可被 Agents 读取（用权限/路径隔离 + 单测）

---

### Phase‑6：UI MVP（审阅点 #1/#2/#3 + Dossier/Gate 可视化）
**目标**
- 用户不看源码，通过 UI 完成：想法→审阅→demo→回测→gate→入库候选。

**背景**
- 这是你最核心的使用方式：只看结果与证据，不看代码。

**实施方案（MVP）**
- FastAPI + Jinja/HTMX
- 页面：
  1) Idea 输入
  2) Blueprint Review（含 policy、data_requirements、evaluation_protocol）
  3) Variable Dictionary Review
  4) Calc Trace Review（K 线叠加 + trace 表）
  5) Runs 列表
  6) Dossier 详情
  7) Gate 详情

**编码内容**
- `ui/server/`：routes/templates/static
- `kernel/dossier_builder.py` 增加可视化图输出（png/html）

**文档**
- `ui/README.md`

**验收**
- UI 可加载并展示 dossier artifacts
- 三个审阅点存在，并可阻塞流程推进（未确认不进入下一阶段）

---

### Phase‑7：Orchestrator（状态机编排 + 回放）
**目标**
- 把全流程变成可回放的 workflow_run（状态机），管理审阅点与权限。

**背景**
- 没有 orchestrator，多 agent 会退化成“聊天串”，不可控不可追踪。

**编码内容**
- `agents/orchestrator/`（注意：orchestrator 可以是 deterministic service）
- workflow 表（sqlite）：
  - workflow_run_id
  - current_state
  - artifacts_index（指向 blueprint/run_id/dossier）
  - approvals（审阅点状态）

**文档**
- `agents/orchestrator/README.md`：状态机图 + 事件

**验收**
- 能从任意 state 回放（replay）并产出一致 artifacts 索引

---

### Phase‑8：Agents v1（Intent / StrategySpec / Spec‑QA / Report / Improvement）
**目标**
- 落地可执行 harness：输入 JSON → 输出 JSON/MD；严格对齐 contracts。

**背景**
- 你要“提出需求后 agent 完成全流程”；agent 必须工程化（harness + schema + tests）。

**编码内容**
- `agents/intent/`
- `agents/strategy_spec/`
- `agents/spec_qa/`
- `agents/report/`
- `agents/improvement/`
- 每个 agent：
  - `run.py`
  - `prompt.md`（规则、禁止项、输出格式）
  - `io_schema.json`
  - `tests/`

**文档**
- `agents/README.md`：如何运行、如何回放、输出字段解释

**验收**
- agent 输出能被 Compiler 接收并跑通
- agent 不得直接裁决（只能输出建议/候选；裁决看 gate_results）

---

### Phase‑9：Demo Pipeline（trace results + demo_dossier）
**目标**
- 你提出的“先小 demo 在 K 线上审逻辑”的标准化落地。

**背景**
- 这是防止策略逻辑错/对齐错/偷看未来的高性价比环节。

**编码内容**
- `kernel/demo_runner.py`：按 calc_trace_plan 生成 demo artifacts
- `dossiers/<run_id>/calc_trace/...` 规范化写入

**文档**
- `calc_trace/README.md`：计划与结果的字段语义

**验收**
- UI 能展示 K 线叠加与 trace 表
- trace assertion（例如 lag>=1）失败可在 UI 明确提示

---

### Phase‑10：Registry（经验卡）+ 入库规则
**目标**
- PASS run_id → Experience Card 入库；并支持检索与复评。

**背景**
- 你需要“模块化资产”可沉淀、可组合、可复用、可治理。

**编码内容**
- `kernel/registry.py`
- `registry/`（cards + index）
- 入库门槛：必须引用 Gate PASS 的 run_id

**文档**
- `registry/README.md`：卡片字段、状态机、晋升/退役规则

**验收**
- UI 可浏览 cards
- 每张 card 可追溯到 dossier/gates

---

### Phase‑11：Composer（组合）v1
**目标**
- 组合多个 cards 并形成组合 blueprint → 组合 run → 组合 gates → 组合 card。

**背景**
- 你最终会把多个模块组合运用。

**编码内容**
- `kernel/composer.py`（组合逻辑：等权/风险平价/约束优化（可先简化））
- `backtest/adapters/portfolio_v1.py`（可选，或复用 signal adapter）

**验收**
- 组合结果同样有 dossier/gate_results，并可入库

---

### Phase‑12：Diagnostics（Codex 提出验证方法）+ 晋升 Gate
**目标**
- Codex 在 dossier 上提出通用诊断/验证方法；可晋升为 gate。

**背景**
- 你一个人无法穷尽验证逻辑；但必须保持“裁判确定性”。

**编码内容**
- `contracts/diagnostic_spec_v1.json`
- `kernel/diagnostics_runner.py`
- `kernel/gates/` 增加 promote 流程（diagnostic → gate）

**验收**
- 任意 run 可附加 diagnostics 目录
- 晋升后 gate_suite 可引用新 gate，并在 CI 有 tests

---

## 4. 每个 Phase 给 Codex 的“标准任务卡模板”（你后续可反复复用）
> 你后续点名某个 Phase 时，我会把下面模板填满，并附上更细的文件清单与接口定义。

### Codex Task Card Template
**任务名**：Phase‑X <模块名>  
**修改范围**：仅允许修改 `<dir_a>/`, `<dir_b>/`（禁止其它目录）  
**目标**：一句话  
**输入/输出 Contract**：引用哪些 schema（版本号）  
**必须实现**：
- 功能点 A/B/C
- CLI 命令（示例）
- 单元测试（覆盖点）
- README（用法 + 示例）

**禁止项**：
- 不得修改 `policies/`、`contracts/`（除非任务明确）
- 不得引入网络请求（除非明确）
- 不得绕过 DataCatalog 直接读取数据
- 不得输出“策略是否有效”的裁决文本（裁决仅看 GateResults）

**验收命令**：
- `docker compose up -d`
- `pytest -q`
- `python -m ...`（给出具体命令）
- 产物检查：`dossiers/<run_id>/...` 应存在哪些文件

---

## 5. 结束语（施工顺序建议）
如果你要最快看到“可用系统”，建议优先打通：
- Phase‑0 → Phase‑1 → Phase‑2 → Phase‑3 → Phase‑4 → Phase‑5 → Phase‑6  
即：**Contracts/Policies/DataCatalog/Runner/Dossier/Gates/UI** 先闭环。  
Agents 与 Codex 的自动化放在闭环之后（Phase‑7/8/12），否则会变成“自动产生不可审计的结果”。

---