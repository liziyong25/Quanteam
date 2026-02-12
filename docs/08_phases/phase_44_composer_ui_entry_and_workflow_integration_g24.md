# Phase-44: Composer UI Entry and Workflow Integration (G24)

## 1) 目标（Goal）
- 完成 G24：提供 `/ui/composer` 入口，从 registry cards 组合生成 governed composed run，并在 UI 中可追踪 dossier/gate 证据。

## 2) 背景（Background）
- 现有 `quant_eam.composer.run` 已具备 deterministic compose 能力，但 UI 侧缺少入口与受控提交流程。
- 需要补齐“UI -> composer -> dossier/gates -> registry”闭环，避免依赖命令行手工触发。

## 3) 范围（Scope）
### In Scope
- 新增 `/ui/composer` 页面与表单提交入口。
- 新增 composer UI 提交路由并接入 `composer_run_once`。
- 在 UI 中展示 compose 结果并跳转到 `/ui/runs/<run_id>`。
- 新增回归测试覆盖 composer UI 提交、产物与页面可见性。

### Out of Scope
- 修改 `contracts/**` 或 `policies/**`。
- 扩展 holdout 可见性。

## 4) 任务卡（Task Card）
### Single Deliverable
- `G24` from `planned` to `implemented`.

### Allowed Paths
- `src/quant_eam/composer/**`
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/**`
- `src/quant_eam/ui/static/**`
- `tests/test_composer*.py`
- `docs/11_composer/**`
- `docs/08_phases/phase_44_composer_ui_entry_and_workflow_integration_g24.md`
- `docs/12_workflows/agents_ui_ssot_v1.yaml`
- `artifacts/subagent_control/phase_44/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停（G24 exception 白名单范围内除外）。

## 5) Subagent Control Packet
- `phase_id`: `phase_44`
- `packet_root`: `artifacts/subagent_control/phase_44/`
- evidence_policy: `hardened`

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_composer_ui_phase24.py tests/test_ui_mvp.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_44`

## 7) 预期产物（Artifacts）
- `dossiers/<run_id>/dossier_manifest.json`
- `dossiers/<run_id>/gate_results.json`
- `registry/trial_log.jsonl`
- `registry/cards/card_<run_id>/card_v1.json`（若 gate pass）
- `artifacts/subagent_control/phase_44/task_card.yaml`
- `artifacts/subagent_control/phase_44/executor_report.yaml`
- `artifacts/subagent_control/phase_44/validator_report.yaml`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-11
- End Date: 2026-02-11
- Notes:
  - Published by orchestrator before subagent execution.
  - Added `/ui/composer` and `/ui/composer/compose` routes for governed compose workflow.
  - Added `composer.html` template and top navigation entry for composer UI.
  - Added UI regression coverage in `tests/test_composer_ui_phase24.py`.
  - Hardened `/ui/runs/<run_id>` to degrade gracefully when composed run has no DataCatalog-backed snapshot.
