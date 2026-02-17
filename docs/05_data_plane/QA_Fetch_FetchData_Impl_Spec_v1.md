# QA‑Fetch FetchData Implementation Spec (v1)
> 角色：Quant‑EAM Data Plane 的 FetchAdapter 实现（source=fetch），为 UI→Orchestrator→Agents harness→Runner/Gates 提供可审计、可复现、可回归的数据获取能力。  
> 本文档是“实现类总纲”：以目标/需求/架构/接口为主；具体实现方案由主控在执行时自行决定。

---

## 0. 目的与定位
### 0.1 目的
把现有 `fetch_*` 能力从“旁路可用”升级为“主路闭环能力”，满足最终链路：

**UI → Orchestrator → Agents harness → Data (QA‑Fetch) → Runner → Dossier → Gates → UI审阅**

### 0.2 定位（系统边界）
QA‑Fetch 负责：
- 接受来自主链路的 `fetch_request`（intent 优先）；
- 通过统一 runtime 解析/执行 fetch；
- 为每次取数强制落盘证据；
- 为 DataCatalog/time‑travel 与 gates 提供可审计输入基础；
- 支持多步取数（如 list→sample→day）并可追溯。

QA‑Fetch 不负责：
- 策略逻辑生成、回测引擎实现（属于 Backtest Plane / Kernel）；
- 策略是否有效的裁决（只允许 GateRunner 裁决）；
- UI 的交互实现（但必须规定 UI 可审阅的证据接口与产物）。

---

## 1. 现有事实基线（必须保持可回归）
### 1.1 函数基线
- 基线函数数：71  
- 函数注册表：`docs/05_data_plane/qa_fetch_function_registry_v1.json`
- 对外语义：`source=fetch`
- 引擎拆分：`engine=mongo|mysql`（分布：mongo 48、mysql 23）

### 1.2 机器路由与可用性证据
- 路由注册表：`docs/05_data_plane/qa_fetch_registry_v1.json`
- probe 证据：`docs/05_data_plane/qa_fetch_probe_v3/probe_summary_v3_notebook_params.json`
  - 覆盖 71
  - pass_has_data=52
  - pass_empty=19
- 结论：基线函数均可调用（按当前 smoke 口径），无 runtime 阻塞。

### 1.3 运行入口（已存在）
- runtime：`src/quant_eam/qa_fetch/runtime.py`
  - `execute_fetch_by_intent(...)`
  - `execute_fetch_by_name(...)`

---

## 2. 顶层设计目标（Goals）
### G1 单一取数通道（Single Data Access Channel）
所有 Agents 必须通过 **DataAccessFacade + FetchPlanner**（或等价组件）取数；
禁止 agent 直接 import provider/DB 或直接调用底层 fetch 函数集合。

### G2 证据链可审计（Auditability）
每次取数必须产出可追溯证据，且证据必须进入 Dossier 主索引（不得只散落 jobs outputs）。

### G3 正确性工程化（Correctness as Engineering）
必须同时满足：
- time‑travel 可得性（`available_at <= as_of`）；
- no‑lookahead（防前视）；
- 数据结构性 sanity checks；
- Golden Queries 回归与漂移报告（最小集）。

### G4 自适应取数（Adaptive Data Planning）
当用户未提供 symbol/code 时，系统必须能在 Agent 侧自动完成：
- `*_list` → 选择样本 → `*_day`（例如 MA250 年线用例）
并且该多步规划必须可审计（step index）。

### G5 UI 可审阅与可回退（Review & Rollback）
UI 必须能展示 fetch evidence，并支持“审阅失败→回退→重跑→再审阅”的闭环。

---

## 3. 对外接口与 Contracts（Interfaces）
### 3.1 FetchRequest v1（intent-first）
原则：UI/Orchestrator/Agent 表达的是“我要什么数据”（intent），不是“调用哪个函数”（function）。

最小字段：
- mode: demo | backtest
- intent:
  - asset, freq, (universe/venue), adjust
  - symbols（可为空/缺省）
  - start, end
  - fields（可选，技术指标默认 OHLCV）
  - auto_symbols（bool，可选）
  - sample（可选：n/method）
- policy:
  - on_no_data: error | pass_empty | retry
  - （可选）max_symbols/max_rows/retry_strategy

约束：
- FetchRequest 必须在编排前通过 schema+逻辑校验（非法直接 fail-fast）。
- intent 与 function 只能二选一：默认 intent；只有“强控函数”场景才允许 function 模式。

### 3.2 FetchResultMeta v1
必须返回并落盘（不要求包含数据本体）：
- selected_function（最终执行的 fetch_*）
- engine（mongo/mysql）
- row_count/col_count
- min_ts/max_ts
- request_hash（复现与缓存键）
- coverage（symbols 覆盖、缺失率）
- probe_status（可选：pass_has_data/pass_empty）
- warnings（数组）

---

## 4. Evidence Bundle 规范（必须进入 Dossier）
### 4.1 单步证据（四件套）
每次 fetch 至少产出：
- fetch_request.json
- fetch_result_meta.json
- fetch_preview.csv
- fetch_error.json（仅失败时，但失败必须有）

### 4.2 多步证据（step index）
任何多步规划（例如 list→sample→day）必须产出：
- fetch_steps_index.json
- step_XXX_fetch_request.json / step_XXX_fetch_result_meta.json / step_XXX_fetch_preview.csv / step_XXX_fetch_error.json

### 4.3 Dossier 归档要求
在 `artifacts/dossiers/<run_id>/fetch/` 下必须可一跳追溯全部步骤证据：
- UI 只读 Dossier 即可展示 fetch evidence（不需要跳转 jobs outputs 路径）。

---

## 5. 自适应规划规则（Planner Requirements）
### 5.1 symbols 缺省时的必备行为
当 `symbols` 为空且 `auto_symbols=true`：
1) 先执行对应 `*_list` 获取候选集合；
2) 执行 sample（随机/流动性/行业分层等，具体策略由主控决定）；
3) 再执行 `*_day` 拉取行情数据；
4) 每一步必须落 step evidence（可审计）。

### 5.2 技术指标默认数据形态
若任务属于 MA/RSI/MACD 等技术指标：
- 默认 freq=day
- 默认 fields 至少包含 OHLCV
- adjust 默认 raw（用户明确才切换复权口径）

---

## 6. 正确性保障（Correctness）
### 6.1 time-travel 可得性
- DataCatalog 层必须强制 `available_at <= as_of`；
- fetch 证据必须记录 as_of 与可得性相关摘要（用于复盘与 gate 解释）。

### 6.2 Gate 双重约束
- GateRunner 必须包含 no_lookahead 与 data_snapshot_integrity（或等价 gates）；
- 任何缺失 fetch evidence / snapshot manifest 的 run 必须 gate fail（不可默默跳过）。

### 6.3 结构性 sanity checks（必须自动化）
对 df 做结构性检查并落盘报告：
- 时间索引单调递增、无重复（或明确记录允许规则）
- dtype 合理
- 缺失率统计（列级）
- 空数据语义与 policy.on_no_data 一致

### 6.4 Golden Queries（回归与漂移）
必须维护最小 Golden 请求集（建议 5~10 个）：
- 固定请求 → 产出 meta/hash/row_count/columns
- 漂移必须产出报告（报告文件位置由主控定义，但必须可被 CI 或 nightly 读取）

---

## 7. UI 集成要求（Review & Rollback）
### 7.1 Fetch Evidence Viewer
UI 必须展示：
- fetch_steps_index.json
- 每个 step 的 meta 与 preview
- 错误（error.json）

### 7.2 审阅点与回退
UI 必须提供 fetch 审阅 checkpoint：
- approve → 进入下一阶段
- reject → 回退并允许修改 fetch_request（或重跑）
- 证据必须 append-only（保留历史 attempt）

---

## 8. Definition of Done（主路闭环验收）
当以下条件全部满足，QA‑Fetch 才算“并入主路”：

1) Contract 校验：
- fetch_request / fetch_result_meta schema 存在且被编排前强制校验；
- 非法请求 fail-fast（有单测）。

2) 单一取数通道：
- Agents 全部通过 facade/planner 取数；
- 存在“禁止直连”测试（禁止 import provider/DB 或绕过 facade）。

3) Evidence 主路化：
- 多步取数有 step index；
- Dossier 中可一跳追溯全部 fetch 证据；
- UI 能展示（只读 Dossier）。

4) UI 回退闭环：
- 集成测试覆盖：审阅失败→回退→重跑→再审阅。

5) 正确性工程化：
- sanity checks + Golden Queries + time‑travel + gates 均可回归；
- 违规直接 gate fail。

### 8.1 验收环境口径（必须显式声明）
后续每一轮 fetch 开发/验收，必须先声明并记录“执行环境口径”，禁止混用后不说明。

口径 A：Notebook Kernel 验收（优先用于手工参数与真实取数联调）
- 在 Jupyter notebook kernel 内执行（`notebooks/qa_fetch_manual_params_v3.ipynb` 对应 kernel）。
- 使用 notebook kernel 的 `sys.executable` 执行命令，不得替换为宿主 `/usr/bin/python3`。
- 适用于验证“notebook 参数集是否可拿到数据”。

口径 B：宿主终端验收（CI/自动化回归）
- 在仓库宿主终端执行命令（cwd 必须为 repo root）。
- 用于 contracts/orchestrator/tests 的自动化回归，不等价于 notebook kernel 结果。

### 8.2 本轮已记录的宿主终端环境（基线样例）
以下为已确认的宿主终端环境样例（recorded_at_utc=`2026-02-17T06:36:29Z`），后续可作为“口径 B”对照：
- 依赖基线：`G344` 已实现且 `acceptance_verified: true`；本轮 git baseline commit 记录为 `NO_HEAD_COMMIT`（当前仓库无可解析 HEAD 提交）
- cwd: `/data/quanteam`
- shell binary: `/bin/bash`
- shell process: `bash`
- OS/kernel: `Linux 6.8.0-90-generic x86_64 GNU/Linux`
- Python bin: `/usr/bin/python3`
- Python version: `3.12.3`
- Python sys.executable: `/usr/bin/python3`
- Python sys.prefix/base_prefix: `/usr` / `/usr`
- VIRTUAL_ENV: `<unset>`
- dot-venv python path: `/data/quanteam/.venv/bin/python`（解析目标 `/usr/bin/python3.12`）
- pip bin/version: `/home/qlib/.local/bin/pip3` / `pip 26.0.1`
- pytest bin/version: `/home/qlib/.local/bin/pytest` / `9.0.2`
- ripgrep bin/version: `/usr/bin/rg` / `14.1.0`
- git bin/version: `/usr/bin/git` / `2.43.0`
- pandas/numpy: `2.3.3` / `2.3.5`
- shell mount namespace: `mnt:[4026531841]`

本轮宿主终端实际命令：
1. `pwd && readlink /proc/$$/ns/mnt`
2. `echo $SHELL && ps -p $$ -o comm=`
3. `uname -srmo`
4. `command -v python3 && python3 -V`
5. `echo "VIRTUAL_ENV=${VIRTUAL_ENV:-<unset>}" && command -v pip3 && python3 -m pip --version`
6. `command -v pytest && python3 -m pytest --version`
7. `command -v rg && rg --version | head -n 1 && command -v git && git --version`
8. `python3 - <<'PY'`（输出 sys.executable/prefix/base_prefix + pandas/numpy 版本）
9. `test -x .venv/bin/python && .venv/bin/python -V`
10. `python3 scripts/check_docs_tree.py`
11. `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
12. `rg -n "G349|QF-114" docs/12_workflows/skeleton_ssot_v1.yaml`

本轮宿主终端环境采样输出（可复现实录）：
```text
recorded_at_utc=2026-02-17T06:36:29Z
baseline_commit=NO_HEAD_COMMIT
$ pwd && readlink /proc/$$/ns/mnt
/data/quanteam
mnt:[4026531841]
$ echo $SHELL && ps -p $$ -o comm=
/bin/bash
bash
$ uname -srmo
Linux 6.8.0-90-generic x86_64 GNU/Linux
$ command -v python3 && python3 -V
/usr/bin/python3
Python 3.12.3
$ echo "VIRTUAL_ENV=${VIRTUAL_ENV:-<unset>}" && command -v pip3 && python3 -m pip --version
VIRTUAL_ENV=<unset>
/home/qlib/.local/bin/pip3
pip 26.0.1 from /home/qlib/.local/lib/python3.12/site-packages/pip (python 3.12)
$ command -v pytest && python3 -m pytest --version
/home/qlib/.local/bin/pytest
pytest 9.0.2
$ command -v rg && rg --version | head -n 1 && command -v git && git --version
/usr/bin/rg
ripgrep 14.1.0
/usr/bin/git
git version 2.43.0
$ python3 - <<'PY'
sys.executable=/usr/bin/python3
sys.version=3.12.3 (main, Jan 22 2026, 20:57:42) [GCC 13.3.0]
sys.prefix=/usr
sys.base_prefix=/usr
platform.platform=Linux-6.8.0-90-generic-x86_64-with-glibc2.39
pandas=2.3.3
numpy=2.3.5
venv_active=no
$ test -x .venv/bin/python && .venv/bin/python -V
Python 3.12.3
```

命令 10~12（docs tree / runtime pytest / SSOT grep）的执行输出见：
- `artifacts/subagent_control/G349/acceptance_run_log.jsonl`

本轮宿主终端基线采样明细（字段化原始记录）见：
- `artifacts/subagent_control/G349/host_terminal_baseline_sample.log`
- `artifacts/subagent_control/G349/host_terminal_baseline_values.env`
- `artifacts/subagent_control/G349/dependency_verification.log`

约束结论（必须遵守）：
- 上述结果仅代表“宿主终端 Python 3.12.3”。
- 若任务要求“严格按 notebook 环境复现”，必须在 notebook kernel 内直接执行，不得用 `/usr/bin/python3` 代跑。

---

## 9. 附录：MA250 年线用例（最小可接受行为）
用户输入：“我要测试 A 股 MA250 年线策略作用。”
系统必须能在未提供 code 的情况下自动完成：
- list（A股股票集合）→ sample（样本选择）→ day（行情）→ MA250 计算
并可在 Dossier/ UI 中追溯每一步取数证据。
