# Phase-49: QA Fetch Probe Evidence Pipeline Baseline (G29)

## 1) 目标（Goal）
- 完成 G29：建立 qa_fetch probe 证据流水线基线，使探测结果以稳定、可机器读取的 evidence pack 输出并可用于 UI 侧审阅。

## 2) 背景（Background）
- Whole View Framework 要求 Demo/Trace 证据可复核、可复放、可审计，不依赖读源码理解。
- G28 已完成 resolver 运行时契约强化；G29 需把 probe 输出固化为统一证据产物与总结。

## 3) 范围（Scope）
### In Scope
- 校准 `qa_fetch` probe 证据产物输出（json/csv/summary/candidate 列表）与最小回归防线。
- 确认证据文档与产物目录契约可被机器/人同时消费。
- 通过 subagent packet hardened 模式完成闭环留痕。

### Out of Scope
- 修改 `contracts/**`。
- 修改 `policies/**`。
- 扩展 holdout 可见性。
- 修改与 G29 无关的 API/UI 路由行为。

## 4) 任务卡（Task Card）
### Single Deliverable
- `G29` from `planned` to `implemented`.

### Allowed Paths
- `scripts/run_qa_fetch_probe_v3.py`
- `src/quant_eam/qa_fetch/probe.py`
- `tests/test_qa_fetch_probe.py`
- `docs/05_data_plane/qa_fetch_smoke_evidence_v1.md`
- `docs/05_data_plane/qa_fetch_probe_v3/**`
- `docs/08_phases/00_skeleton/phase_49_qa_fetch_probe_evidence_pipeline_baseline_g29.md`
- `docs/12_workflows/skeleton_ssot_v1.yaml`
- `artifacts/subagent_control/phase_49/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停（仅 G29 exception 白名单范围内放行）。
- Subagent 禁止修改 `docs/12_workflows/skeleton_ssot_v1.yaml`；该文件仅允许主控在全部验收完成后写回。

## 5) Subagent Control Packet
- `phase_id`: `phase_49`
- `packet_root`: `artifacts/subagent_control/phase_49/`
- `evidence_policy`: `hardened`

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_qa_fetch_probe.py tests/test_qa_fetch_registry_json.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_49`

## 7) 预期产物（Artifacts）
- `scripts/run_qa_fetch_probe_v3.py`
- `src/quant_eam/qa_fetch/probe.py`
- `tests/test_qa_fetch_probe.py`
- `docs/05_data_plane/qa_fetch_smoke_evidence_v1.md`
- `docs/05_data_plane/qa_fetch_probe_v3/**`
- `artifacts/subagent_control/phase_49/task_card.yaml`
- `artifacts/subagent_control/phase_49/executor_report.yaml`
- `artifacts/subagent_control/phase_49/validator_report.yaml`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-11
- End Date: 2026-02-11
- Notes:
  - Published by orchestrator before subagent execution.
  - Task card uses `evidence_policy: hardened` and G29 exception-scoped allowed paths.
  - Phase-49 baseline artifacts under G29 expected scope were verified in-place by codex cli subagent with scoped packet evidence.
  - Acceptance passed:
    - `docker compose run --rm api pytest -q tests/test_qa_fetch_probe.py tests/test_qa_fetch_registry_json.py`
    - `python3 scripts/check_docs_tree.py`
    - `python3 scripts/check_subagent_packet.py --phase-id phase_49`
  - Packet pre-writeback validation passed before SSOT mutation.
  - SSOT writeback completed by orchestrator only: `G29.status_now=implemented`.
