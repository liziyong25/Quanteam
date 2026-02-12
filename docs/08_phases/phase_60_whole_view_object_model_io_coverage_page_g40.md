# Phase-60: Whole View Object Model I/O Coverage Page (G40)

## 1) 目标（Goal）
- 完成 G40：交付 `/ui/object-model` 只读页面，展示 Whole View section 4 的核心对象模型与 I/O 治理证据。

## 2) 背景（Background）
- Whole View section 4 定义了 IdeaSpec/Blueprint/RunSpec/Dossier/GateResults/Experience Card 的系统 I/O 语义。
- 无人值守流程需要将对象模型边界可视化为只读证据，支持不看源码的治理审阅。

## 3) 范围（Scope）
### In Scope
- 新增 `/ui/object-model` 只读路由和模板渲染。
- 从 Whole View + Playbook 提取对象模型条目并映射当前 SSOT 相关证据。
- 增补 G40 回归测试覆盖可访问性、只读语义与关键对象字段展示。

### Out of Scope
- 修改 `contracts/**`。
- 修改 `policies/**`。
- 扩展 holdout 可见性。
- 新增写接口或修改非 G40 范围路由行为。

## 4) 任务卡（Task Card）
### Single Deliverable
- `G40` from `planned` to `implemented`.

### Allowed Paths
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/**`
- `src/quant_eam/ui/static/**`
- `tests/test_ui_mvp.py`
- `tests/test_ui_object_model_phase40.py`
- `docs/08_phases/phase_60_*.md`
- `docs/12_workflows/agents_ui_ssot_v1.yaml`
- `artifacts/subagent_control/phase_60/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停（仅 G40 exception 白名单范围内放行）。
- Subagent 禁止修改 `docs/12_workflows/agents_ui_ssot_v1.yaml`；仅主控在全部验收通过后回写 `G40.status_now=implemented`。

## 5) Subagent Control Packet
- `phase_id`: `phase_60`
- `packet_root`: `artifacts/subagent_control/phase_60/`
- `evidence_policy`: `hardened`

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_ui_object_model_phase40.py tests/test_ui_mvp.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_60`

## 7) 预期产物（Artifacts）
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/object_model.html`
- `tests/test_ui_object_model_phase40.py`
- `tests/test_ui_mvp.py`
- `artifacts/subagent_control/phase_60/task_card.yaml`
- `artifacts/subagent_control/phase_60/executor_report.yaml`
- `artifacts/subagent_control/phase_60/validator_report.yaml`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-12
- End Date: 2026-02-12
- Notes:
  - Published by orchestrator before subagent execution.
  - Task card enforces hardened evidence and G40 exception-scoped allowed paths.
  - Subagent implemented `GET/HEAD`-only route `/ui/object-model` in `src/quant_eam/api/ui_routes.py`, with read-only template `src/quant_eam/ui/templates/object_model.html`.
  - Evidence rendering is sourced from:
    - `docs/00_overview/Quant‑EAM Whole View Framework.md` section `4. 核心对象模型（系统只认这些 I/O）`
    - `docs/00_overview/Quant‑EAM Implementation Phases Playbook.md` section `3. Phase 列表（推荐施工顺序）`
    - `docs/12_workflows/agents_ui_ssot_v1.yaml` entries `goal_checklist(G40)` / `phase_dispatch_plan_v2` / `g40_object_model_ui_scope`
  - Added regression coverage in `tests/test_ui_object_model_phase40.py` and extended `tests/test_ui_mvp.py` smoke checks for `/ui/object-model`.
  - Governance boundary preserved on page render: `GET/HEAD only`, `no write actions`, `no holdout expansion`, and no write controls exposed.
  - Acceptance executed and passed:
    - `docker compose run --rm api pytest -q tests/test_ui_object_model_phase40.py tests/test_ui_mvp.py`
    - `python3 scripts/check_docs_tree.py`
    - `python3 scripts/check_subagent_packet.py --phase-id phase_60`
  - Orchestrator reran acceptance + packet validation, then completed SSOT writeback: `G40.status_now=implemented`.
