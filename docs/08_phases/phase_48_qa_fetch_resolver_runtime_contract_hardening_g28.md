# Phase-48: QA Fetch Resolver Runtime Contract Hardening (G28)

## 1) 目标（Goal）
- 完成 G28：强化 qa_fetch resolver/fetch 运行时契约，使 asset/freq/venue/adjust 与输入参数语义在错误路径和成功路径都保持确定性与可审计。

## 2) 背景（Background）
- Whole View Framework 要求 Data Plane 运行行为可复放、可解释、可测试。
- 当前 resolver 主路径可用，但对输入参数边界和错误语义的约束仍偏弱，缺少面向运行时契约的回归防线。

## 3) 范围（Scope）
### In Scope
- 强化 `resolve_fetch`/`fetch_market_data` 的运行时输入校验与错误语义。
- 增补 resolver/export 相关回归测试，覆盖边界输入和确定性行为。
- 更新 resolver 文档中的运行时契约说明。

### Out of Scope
- 修改 `contracts/**`。
- 修改 `policies/**`。
- 修改非 qa_fetch 相关 API/UI 路由行为。
- 扩展 holdout 可见性。

## 4) 任务卡（Task Card）
### Single Deliverable
- `G28` from `planned` to `implemented`.

### Allowed Paths
- `src/quant_eam/qa_fetch/resolver.py`
- `src/quant_eam/qa_fetch/__init__.py`
- `tests/test_qa_fetch_resolver.py`
- `tests/test_qa_fetch_exports.py`
- `docs/05_data_plane/qa_fetch_resolver_registry_v1.md`
- `docs/08_phases/phase_48_qa_fetch_resolver_runtime_contract_hardening_g28.md`
- `docs/12_workflows/agents_ui_ssot_v1.yaml`
- `artifacts/subagent_control/phase_48/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停（G28 exception 白名单范围内除外）。

## 5) Subagent Control Packet
- `phase_id`: `phase_48`
- `packet_root`: `artifacts/subagent_control/phase_48/`
- `evidence_policy`: `hardened`

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_qa_fetch_resolver.py tests/test_qa_fetch_exports.py tests/test_ui_mvp.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_48`

## 7) 预期产物（Artifacts）
- `src/quant_eam/qa_fetch/resolver.py`
- `tests/test_qa_fetch_resolver.py`
- `tests/test_qa_fetch_exports.py`
- `docs/05_data_plane/qa_fetch_resolver_registry_v1.md`
- `artifacts/subagent_control/phase_48/task_card.yaml`
- `artifacts/subagent_control/phase_48/executor_report.yaml`
- `artifacts/subagent_control/phase_48/validator_report.yaml`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-11
- End Date: 2026-02-11
- Notes:
  - Published by orchestrator before subagent execution.
  - Subagent implementation must stay within phase_48 runtime-contract hardening scope.
  - Hardened resolver runtime input validation for selector fields and fetch call inputs with deterministic errors.
  - Added regression coverage in `tests/test_qa_fetch_resolver.py` and `tests/test_qa_fetch_exports.py`.
  - Updated runtime-contract notes in `docs/05_data_plane/qa_fetch_resolver_registry_v1.md`.
  - Acceptance passed:
    - `docker compose run --rm api pytest -q tests/test_qa_fetch_resolver.py tests/test_qa_fetch_exports.py tests/test_ui_mvp.py`
    - `python3 scripts/check_docs_tree.py`
    - `python3 scripts/check_subagent_packet.py --phase-id phase_48`
  - SSOT writeback completed: `G28` marked implemented.
