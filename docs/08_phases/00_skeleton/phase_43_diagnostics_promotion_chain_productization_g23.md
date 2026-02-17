# Phase-43: Diagnostics Promotion Chain Productization (G23)

## 1) 目标（Goal）
- 完成 G23：DiagnosticSpec 可确定性执行，写入 dossier diagnostics 证据，并产出可推广 GateSpec 候选件。

## 2) 背景（Background）
- G22 已完成 contracts 层补齐，但 diagnostics 执行链路尚未产品化落地到 artifacts/API/UI。
- 需要形成“spec -> deterministic report -> promotion candidate gate_spec”的可审计链。

## 3) 范围（Scope）
### In Scope
- 新增 diagnostics promotion chain 执行模块（deterministic）。
- 新增 runs API 入口用于执行与读取 diagnostics artifacts。
- 在 `/ui/runs/<run_id>` 增加 diagnostics evidence 可见性。
- 新增回归测试覆盖 diagnostics artifacts 与 promotion candidate。

### Out of Scope
- 改动 contracts（G23 明确禁止）。
- 扩展 holdout 可见性。

## 4) 任务卡（Task Card）
### Single Deliverable
- `G23` from `planned` to `implemented`.

### Allowed Paths
- `src/quant_eam/diagnostics/**`
- `src/quant_eam/gates/**`
- `src/quant_eam/api/**`
- `src/quant_eam/ui/templates/**`
- `src/quant_eam/ui/static/**`
- `tests/test_diagnostic*.py`
- `tests/test_gate*.py`
- `docs/08_gates/**`
- `docs/14_trace_preview/**`
- `docs/08_phases/00_skeleton/phase_43_diagnostics_promotion_chain_productization_g23.md`
- `docs/12_workflows/skeleton_ssot_v1.yaml`
- `artifacts/subagent_control/phase_43/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停（G23 exception 白名单内除外）。

## 5) Subagent Control Packet
- `phase_id`: `phase_43`
- `packet_root`: `artifacts/subagent_control/phase_43/`
- evidence_policy: `hardened`

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_diagnostic_promotion_phase23.py tests/test_ui_mvp.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_43`

## 7) 预期产物（Artifacts）
- `dossiers/<run_id>/diagnostics/<diag_id>/diagnostic_spec.json`
- `dossiers/<run_id>/diagnostics/<diag_id>/diagnostic_report.json`
- `dossiers/<run_id>/diagnostics/<diag_id>/diagnostic_outputs/**`
- `dossiers/<run_id>/diagnostics/<diag_id>/promotion_candidate/gate_spec.json`
- `artifacts/subagent_control/phase_43/task_card.yaml`
- `artifacts/subagent_control/phase_43/executor_report.yaml`
- `artifacts/subagent_control/phase_43/validator_report.yaml`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-11
- End Date: 2026-02-11
- Notes:
  - Published by orchestrator before subagent execution.
  - Added deterministic diagnostics promotion chain executor at `src/quant_eam/diagnostics/promotion_chain.py`.
  - Added write API `POST /runs/{run_id}/diagnostics` and read APIs for diagnostics list/detail.
  - Extended `/ui/runs/{run_id}` with diagnostics evidence and promotion candidate visibility.
  - Added regression test `tests/test_diagnostic_promotion_phase23.py`.
