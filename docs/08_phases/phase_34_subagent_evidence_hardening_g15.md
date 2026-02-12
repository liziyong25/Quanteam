# Phase-34: Subagent Evidence Hardening (G15)

## 1) 目标（Goal）
- 完成 G15：将 subagent packet 校验从“自报校验”升级为“真实 workspace 证据交叉验证”。

## 2) 背景（Background）
- 当前 `scripts/check_subagent_packet.py` 主要依赖 `executor_report.yaml` 中的自报字段。
- 无人值守主控模式下，需要防止“只写报告、未真实执行”或“变更集不一致”风险。

## 3) 范围（Scope）
### In Scope
- 在 packet 协议中引入 `evidence_policy` 与 `evidence_files`。
- 支持 `hardened` 模式，校验 before/after workspace 快照与 acceptance 执行日志。
- 保持 legacy packet 向后兼容。
- 增加针对 hardened/legacy 的测试覆盖。

### Out of Scope
- 修改 contracts/policies。
- 引入新的 API 路由。

## 4) 任务卡（Task Card）
### Single Deliverable
- `G15` from `planned` to `implemented`.

### Allowed Paths
- `scripts/check_subagent_packet.py`
- `tests/test_subagent_packet_phase15.py`
- `docs/12_workflows/subagent_control_packet_v1.md`
- `docs/12_workflows/templates/subagent_task_card_v1.yaml`
- `docs/12_workflows/templates/subagent_executor_report_v1.yaml`
- `docs/12_workflows/templates/subagent_validator_report_v1.yaml`
- `docs/08_phases/phase_34_subagent_evidence_hardening_g15.md`
- `docs/12_workflows/agents_ui_ssot_v1.yaml`
- `artifacts/subagent_control/phase_34/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停并上报用户。

## 5) Subagent Control Packet
- `phase_id`: `phase_34`
- `packet_root`: `artifacts/subagent_control/phase_34/`
- Required:
  - `task_card.yaml`
  - `executor_report.yaml`
  - `validator_report.yaml`
  - `workspace_before.json` (hardened)
  - `workspace_after.json` (hardened)
  - `acceptance_run_log.jsonl` (hardened)

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_subagent_packet_phase15.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_34`

## 7) 预期产物（Artifacts）
- `scripts/check_subagent_packet.py` hardened 证据校验能力可用。
- `tests/test_subagent_packet_phase15.py` 通过。
- `docs/12_workflows/agents_ui_ssot_v1.yaml` 中 `G15.status_now=implemented`。
- `artifacts/subagent_control/phase_34/*` packet 完整并校验通过。

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-11
- End Date: 2026-02-11
- Notes:
  - Published by orchestrator before execution.
  - Acceptance:
    - `docker compose run --rm api pytest -q tests/test_subagent_packet_phase15.py` -> pass
    - `python3 scripts/check_docs_tree.py` -> pass
    - `python3 scripts/check_subagent_packet.py --phase-id phase_34` -> pass
  - Packet evidence includes workspace before/after snapshots and acceptance JSONL log.

## 9) 遗留问题（Open Issues）
- [ ] 后续可把 acceptance_run_log 自动采集工具脚本化，减少手工拼接日志。
