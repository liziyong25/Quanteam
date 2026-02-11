# Governance & Development Rules

Docs SSOT entry is `docs/README.md`. Do not add a second docs entry file that can drift.

## 1. Core Non‑Negotiables（硬约束）
1) Policies 只读：任何策略/模块只能引用 `policy_id`，禁止覆盖、内联修改、或“临时注入 policy”。
2) 策略生成只能输出 Blueprint/DSL（声明式）：禁止输出可直接执行的回测脚本绕过 Compiler/Kernel。
3) 裁决只允许 Gate + Dossier：PASS/FAIL/Registry 入库必须引用 dossier artifacts（证据链）。
4) Final Holdout 不可污染：迭代环不得获得 holdout 细节；Holdout 只允许输出 pass/fail + 极少摘要。
5) Dossier append-only：历史 run 产物不可覆盖/回写；如需迁移必须 ADR + 明确迁移方案 + 回放兼容策略。
6) 强制 budget/stop：任何搜索/迭代必须有预算与停止条件，防无限搜索挖假阳性。
7) Agents 必须 harness 化：I/O schema + tests + 可回放；agent 只能提议/分析，不得裁决策略有效性。

> 注：以上硬约束对应 Kernel/Agents/UI 的职责边界。

## 1.1 Enforcement（由谁执行）

- CI / Code review：检查 docs/ADR/phase log 是否更新，拒绝越权变更与漂移入口文件。
- Kernel：运行时进行 schema/policy_id 校验、拒绝绕过路径（拒绝无 dossier 证据链的裁决/入库）。
- UI：审阅点只展示 dossier/gate/artifacts，缺证据则阻塞推进（不允许“口头 pass”）。

## 2. Repo Rules
- `contracts/`：只放 schema 本体（JSON Schema/Pydantic models），必须版本化。
- `policies/`：只放冻结 policy（YAML），变更需走审批流程。
- `dossiers/`：append‑only，不允许回写/覆盖历史 run 的 artifacts。
- `agents/`：每个 agent 必须是可执行 harness（输入 JSON/输出 JSON/MD），并具备 tests。
- `ui/`：UI 只读展示 dossier/gate/artifacts，不依赖源码展示。

## 3. Change Management
### 3.1 Contracts 变更
- 只能新增版本（如 `*_v2`），不得破坏旧版本回放。
- 必须更新：`docs/03_contracts/<name>.md`
- 必须新增 ADR（影响字段语义/兼容性/渲染逻辑）

### 3.2 Policies 变更
- 默认冻结；变更必须：
  1) 新增版本（如 `execution_policy_v2.yaml`）
  2) 更新 `docs/04_policies/`
  3) 新增 ADR
  4) 重新跑回归用例（指定基准 Blueprint/RunSpec）

## 4. Determinism & Reproducibility
- Runner/Gates/Diagnostics 必须可复现（seed 固定、依赖版本锁定、禁止网络 IO）。
- 每次 run 必须写入 `config_snapshot`、`manifest`、`hashes`。

## 5. Definition of Done（通用 DoD）
任何 Phase/PR 合并前必须满足：
- tests 全绿（pytest）
- schema 校验通过（若本 Phase 涉及 contracts）
- 产物落盘符合 dossier 规范（若本 Phase 涉及 runner/ui）
- docs 更新：`docs/08_phases/phase_XX_*.md` +（必要时）ADR

## 6. Contracts/Policies Boundary (Do Not Drift)

- Contracts describe **I/O schemas** and must be versioned. No breaking changes to replay old dossiers.
- Policies are governance inputs selected by `policy_id`. Code must treat them as read-only.
- Any change that could affect holdout isolation, arbitration, or determinism requires an ADR.
