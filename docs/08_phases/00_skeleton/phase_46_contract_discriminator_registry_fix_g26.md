# Phase-46: Contract Discriminator Registry Fix (G26)

## 1) 目标（Goal）
- 完成 G26：修复 `contracts.validate` 的 discriminator registry 映射，使 `diagnostic_spec_v1` 与 `gate_spec_v1` 可通过 `schema_version` 自动识别并校验通过。

## 2) 背景（Background）
- 当前 `contracts/examples/diagnostic_spec_ok.json` 与 `contracts/examples/gate_spec_ok.json` 已存在，但 `SCHEMA_VERSION_TO_FILE` 尚未纳入对应映射，导致只能依赖 forced schema 校验。
- 该缺口会影响 contracts examples 的一致性与自动化治理可信度。

## 3) 范围（Scope）
### In Scope
- 更新 `src/quant_eam/contracts/validate.py` 的 `SCHEMA_VERSION_TO_FILE`。
- 增加/更新测试，覆盖 discriminator 成功路径与 unknown schema 失败路径。
- 发布并验证 phase_46 subagent control packet。

### Out of Scope
- 修改 `policies/**`。
- 修改 holdout 可见性规则。
- 修改无关 API/route 行为。

## 4) 任务卡（Task Card）
### Single Deliverable
- `G26` from `planned` to `implemented`.

### Allowed Paths
- `src/quant_eam/contracts/validate.py`
- `contracts/examples/**`
- `tests/test_contracts_examples.py`
- `tests/test_contracts_registry_phase26.py`
- `docs/08_phases/00_skeleton/phase_46_contract_discriminator_registry_fix_g26.md`
- `docs/12_workflows/skeleton_ssot_v1.yaml`
- `artifacts/subagent_control/phase_46/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停（G26 exception 白名单范围内除外）。

## 5) Subagent Control Packet
- `phase_id`: `phase_46`
- `packet_root`: `artifacts/subagent_control/phase_46/`
- `evidence_policy`: `hardened`

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_contracts_examples.py tests/test_contracts_registry_phase26.py tests/test_ui_mvp.py`
- `docker compose run --rm api python -m quant_eam.contracts.validate contracts/examples/diagnostic_spec_ok.json`
- `docker compose run --rm api python -m quant_eam.contracts.validate contracts/examples/gate_spec_ok.json`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_46`

## 7) 预期产物（Artifacts）
- `src/quant_eam/contracts/validate.py`
- `tests/test_contracts_examples.py`
- `tests/test_contracts_registry_phase26.py`
- `artifacts/subagent_control/phase_46/task_card.yaml`
- `artifacts/subagent_control/phase_46/executor_report.yaml`
- `artifacts/subagent_control/phase_46/validator_report.yaml`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-11
- End Date: 2026-02-11
- Notes:
  - Published by orchestrator before subagent execution.
  - Subagent must implement contract discriminator registry fix within allowed paths only.
  - Subagent implemented `SCHEMA_VERSION_TO_FILE` mapping for `diagnostic_spec_v1` and `gate_spec_v1`.
  - Added regression file `tests/test_contracts_registry_phase26.py` covering discriminator pass path and unknown schema failure path.
  - Acceptance passed:
    - `docker compose run --rm api pytest -q tests/test_contracts_examples.py tests/test_contracts_registry_phase26.py tests/test_ui_mvp.py`
    - `docker compose run --rm api python -m quant_eam.contracts.validate contracts/examples/diagnostic_spec_ok.json`
    - `docker compose run --rm api python -m quant_eam.contracts.validate contracts/examples/gate_spec_ok.json`
    - `python3 scripts/check_docs_tree.py`
    - `python3 scripts/check_subagent_packet.py --phase-id phase_46`
  - SSOT writeback completed: `G26` marked implemented; `G22` notes annotated with phase_46 registry-gap fix.
