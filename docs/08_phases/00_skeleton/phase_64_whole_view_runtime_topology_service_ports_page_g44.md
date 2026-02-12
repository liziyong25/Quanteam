# Phase-64: Whole View Runtime Topology and Service Ports Page (G44)

## 1) 目标（Goal）
- 完成 G44：交付 `/ui/runtime-topology` 只读页面，展示 Whole View section 9 运行拓扑、服务端口与关键运行命令治理证据。

## 2) 背景（Background）
- Whole View section 9 定义了仓库模块、运行形态与服务接口的整体拓扑。
- 无人值守流程需要将运行拓扑与端口/命令信息固化为只读证据，降低运维认知偏差。

## 3) 范围（Scope）
### In Scope
- 新增 `/ui/runtime-topology` 只读路由与模板渲染。
- 从 Whole View section 9 与 Playbook section 1/3 提取运行拓扑证据。
- 增补 G44 回归测试覆盖只读语义、关键字段展示与可访问性。

### Out of Scope
- 修改 `contracts/**`。
- 修改 `policies/**`。
- 扩展 holdout 可见性。
- 新增写接口或修改非 G44 范围路由行为。

## 4) 任务卡（Task Card）
### Single Deliverable
- `G44` from `planned` to `implemented`.

### Allowed Paths
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/**`
- `src/quant_eam/ui/static/**`
- `tests/test_ui_mvp.py`
- `tests/test_ui_runtime_topology_phase44.py`
- `docs/08_phases/00_skeleton/phase_64_*.md`
- `docs/12_workflows/skeleton_ssot_v1.yaml`
- `artifacts/subagent_control/phase_64/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停（仅 G44 exception 白名单范围内放行）。
- Subagent 禁止修改 `docs/12_workflows/skeleton_ssot_v1.yaml`；仅主控在全部验收通过后回写 `G44.status_now=implemented`。

## 5) Subagent Control Packet
- `phase_id`: `phase_64`
- `packet_root`: `artifacts/subagent_control/phase_64/`
- `evidence_policy`: `hardened`

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_ui_runtime_topology_phase44.py tests/test_ui_mvp.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_64`

## 7) 预期产物（Artifacts）
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/runtime_topology.html`
- `tests/test_ui_runtime_topology_phase44.py`
- `tests/test_ui_mvp.py`
- `artifacts/subagent_control/phase_64/task_card.yaml`
- `artifacts/subagent_control/phase_64/executor_report.yaml`
- `artifacts/subagent_control/phase_64/validator_report.yaml`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-12
- End Date: 2026-02-12
- Notes:
  - Published by orchestrator before subagent execution.
  - Task card enforces hardened evidence and G44 exception-scoped allowed paths.
  - Implemented G44 in scope: added `/ui/runtime-topology` GET/HEAD route, `src/quant_eam/ui/templates/runtime_topology.html`, `tests/test_ui_runtime_topology_phase44.py`, and `tests/test_ui_mvp.py` coverage update.
  - Acceptance outcome: `docker compose run --rm api pytest -q tests/test_ui_runtime_topology_phase44.py tests/test_ui_mvp.py` passed.
  - Acceptance outcome: `python3 scripts/check_docs_tree.py` passed.
  - Acceptance outcome: `python3 scripts/check_subagent_packet.py --phase-id phase_64` passed.
  - Orchestrator writeback completed: `docs/12_workflows/skeleton_ssot_v1.yaml` updated with `G44.status_now=implemented`; validator finalized to `status=pass`.
