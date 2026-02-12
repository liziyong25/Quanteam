# Phase-42: Contracts Completion for DiagnosticSpec/GateSpec (G22)

## 1) 目标（Goal）
- 完成 G22：将 `diagnostic_spec_v1` / `gate_spec_v1` 作为一等契约落地，支持本地可验证示例与文档审计。

## 2) 背景（Background）
- 当前仓库已有 run/gate/dossier 等核心契约，但缺少 diagnostics promotion 链路的专用契约。
- G23 及后续 UI/agents productization 依赖这两个契约作为稳定输入输出边界。

## 3) 范围（Scope）
### In Scope
- 新增契约文件：`contracts/diagnostic_spec_v1.json`、`contracts/gate_spec_v1.json`。
- 新增契约示例：`contracts/examples/diagnostic_spec_*.json`、`contracts/examples/gate_spec_*.json`。
- 新增契约文档：`docs/03_contracts/diagnostic_spec_v1.md`、`docs/03_contracts/gate_spec_v1.md`。
- 更新契约示例校验脚本与测试覆盖。

### Out of Scope
- 改动 policies。
- 改动 holdout 可见性规则。
- 改动 runtime 业务流程（留到 G23+）。

## 4) 任务卡（Task Card）
### Single Deliverable
- `G22` from `planned` to `implemented`.

### Allowed Paths
- `contracts/diagnostic_spec_v1.json`
- `contracts/gate_spec_v1.json`
- `contracts/examples/**`
- `scripts/check_contracts_examples.py`
- `tests/test_contracts_examples.py`
- `docs/03_contracts/**`
- `docs/08_phases/00_skeleton/phase_42_contracts_completion_g22.md`
- `docs/12_workflows/skeleton_ssot_v1.yaml`
- `artifacts/subagent_control/phase_42/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停（G22 exception 白名单内除外）。

## 5) Subagent Control Packet
- `phase_id`: `phase_42`
- `packet_root`: `artifacts/subagent_control/phase_42/`
- evidence_policy: `hardened`

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_contracts_examples.py`
- `docker compose run --rm api python3 scripts/check_contracts_examples.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_42`

## 7) 预期产物（Artifacts）
- `contracts/diagnostic_spec_v1.json`
- `contracts/gate_spec_v1.json`
- `contracts/examples/diagnostic_spec_ok.json`
- `contracts/examples/diagnostic_spec_bad.json`
- `contracts/examples/gate_spec_ok.json`
- `contracts/examples/gate_spec_bad.json`
- `artifacts/subagent_control/phase_42/task_card.yaml`
- `artifacts/subagent_control/phase_42/executor_report.yaml`
- `artifacts/subagent_control/phase_42/validator_report.yaml`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-11
- End Date: 2026-02-11
- Notes:
  - Published by orchestrator before subagent execution.
  - Added `diagnostic_spec_v1` / `gate_spec_v1` contracts with OK/BAD examples.
  - Extended contract example checker coverage to include the two new schemas.
  - Added dedicated regression test `tests/test_contracts_examples.py`.
