# Phase-47: QA Fetch Registry Deterministic Sync Guard (G27)

## 1) 目标（Goal）
- 完成 G27：建立 qa_fetch 机器注册表的确定性同步防线，确保 `qa_fetch_registry_v1.json` 与代码生成结果可机器对账。

## 2) 背景（Background）
- Whole View Framework 要求 Data Plane 与 Contracts 输出可审计、可复放、可静态检查。
- 当前 `scripts/generate_qa_fetch_registry_json.py` 能生成注册表，但缺少“CI 可检查的 drift 守卫”语义。

## 3) 范围（Scope）
### In Scope
- 为注册表生成脚本补充同步校验模式（check-only）。
- 增加回归测试覆盖“对齐通过/漂移失败”语义。
- 更新 resolver/registry 文档中的生成与校验用法。

### Out of Scope
- 修改 `contracts/**`。
- 修改 `policies/**`。
- 修改任意 UI/API 路由行为。
- 扩展 holdout 可见性。

## 4) 任务卡（Task Card）
### Single Deliverable
- `G27` from `planned` to `implemented`.

### Allowed Paths
- `scripts/generate_qa_fetch_registry_json.py`
- `tests/test_qa_fetch_registry_json.py`
- `tests/test_qa_fetch_registry_phase27.py`
- `docs/05_data_plane/qa_fetch_resolver_registry_v1.md`
- `docs/08_phases/00_skeleton/phase_47_qa_fetch_registry_deterministic_sync_guard_g27.md`
- `docs/12_workflows/skeleton_ssot_v1.yaml`
- `artifacts/subagent_control/phase_47/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停（G27 exception 白名单范围内除外）。

## 5) Subagent Control Packet
- `phase_id`: `phase_47`
- `packet_root`: `artifacts/subagent_control/phase_47/`
- `evidence_policy`: `hardened`

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_qa_fetch_registry.py tests/test_qa_fetch_registry_json.py tests/test_qa_fetch_registry_phase27.py`
- `docker compose run --rm api python scripts/generate_qa_fetch_registry_json.py --check`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_47`

## 7) 预期产物（Artifacts）
- `scripts/generate_qa_fetch_registry_json.py`
- `tests/test_qa_fetch_registry_phase27.py`
- `docs/05_data_plane/qa_fetch_resolver_registry_v1.md`
- `artifacts/subagent_control/phase_47/task_card.yaml`
- `artifacts/subagent_control/phase_47/executor_report.yaml`
- `artifacts/subagent_control/phase_47/validator_report.yaml`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-11
- End Date: 2026-02-11
- Notes:
  - Published by orchestrator before subagent execution.
  - Subagent implementation is constrained to deterministic registry sync guard scope.
  - Added `--check` mode to `scripts/generate_qa_fetch_registry_json.py` with semantic diff (ignores `generated_at_utc`).
  - Added regression test file `tests/test_qa_fetch_registry_phase27.py` to cover in-sync pass and semantic-drift fail.
  - Updated `docs/05_data_plane/qa_fetch_resolver_registry_v1.md` with generate/check usage.
  - Acceptance passed:
    - `docker compose run --rm api pytest -q tests/test_qa_fetch_registry.py tests/test_qa_fetch_registry_json.py tests/test_qa_fetch_registry_phase27.py`
    - `docker compose run --rm api python scripts/generate_qa_fetch_registry_json.py --check`
    - `python3 scripts/check_docs_tree.py`
    - `python3 scripts/check_subagent_packet.py --phase-id phase_47`
  - SSOT writeback completed: `G27` marked implemented.
