# Phase-50: QA Fetch Registry Read-Only UI Explorer (G30)

## 1) 目标（Goal）
- 完成 G30：交付 `/ui/qa-fetch` 只读浏览页，集中展示 qa_fetch registry / resolver / probe 证据，支持黑盒审阅且不需要阅读源码。

## 2) 背景（Background）
- Whole View Framework 要求 UI 可直接审阅治理证据，且读取路径只依赖 artifacts/contracts 侧数据。
- G29 已完成 probe evidence 基线；G30 负责在 UI 平面给出只读可视化入口，保持治理边界不变。

## 3) 范围（Scope）
### In Scope
- 新增 `/ui/qa-fetch` 只读路由与模板渲染。
- 呈现 qa_fetch registry / resolver / probe 产物的摘要信息与路径引用。
- 增补 G30 回归测试覆盖页面可访问性与只读语义。

### Out of Scope
- 修改 `contracts/**`。
- 修改 `policies/**`。
- 扩展 holdout 可见性。
- 增加写入型接口或修改非 G30 范围路由行为。

## 4) 任务卡（Task Card）
### Single Deliverable
- `G30` from `planned` to `implemented`.

### Allowed Paths
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/**`
- `src/quant_eam/ui/static/**`
- `tests/test_ui_mvp.py`
- `tests/test_qa_fetch_ui_phase30.py`
- `docs/05_data_plane/qa_fetch_*.md`
- `docs/08_phases/phase_50_qa_fetch_registry_readonly_ui_explorer_g30.md`
- `docs/12_workflows/agents_ui_ssot_v1.yaml`
- `artifacts/subagent_control/phase_50/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停（仅 G30 exception 白名单范围内放行）。
- Subagent 禁止修改 `docs/12_workflows/agents_ui_ssot_v1.yaml`；仅主控在全部验收通过后回写 `G30.status_now=implemented`。

## 5) Subagent Control Packet
- `phase_id`: `phase_50`
- `packet_root`: `artifacts/subagent_control/phase_50/`
- `evidence_policy`: `hardened`

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_qa_fetch_ui_phase30.py tests/test_ui_mvp.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_50`

## 7) 预期产物（Artifacts）
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/qa_fetch.html`
- `src/quant_eam/ui/static/**`
- `tests/test_ui_mvp.py`
- `tests/test_qa_fetch_ui_phase30.py`
- `docs/05_data_plane/qa_fetch_*.md`
- `artifacts/subagent_control/phase_50/task_card.yaml`
- `artifacts/subagent_control/phase_50/executor_report.yaml`
- `artifacts/subagent_control/phase_50/validator_report.yaml`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-11
- End Date: 2026-02-11
- Notes:
  - Published by orchestrator before subagent execution.
  - Task card enforces `evidence_policy: hardened` and G30 exception-scoped allowed paths.
  - Codex CLI subagent implemented `/ui/qa-fetch` read-only explorer route, template, and phase-30 UI tests in scoped paths.
  - Hardened packet tracked one non-scope workspace drift via `external_noise_paths`:
    - `notebooks/qa_fetch_manual_params_v3.ipynb`
  - Acceptance passed:
    - `docker compose run --rm api pytest -q tests/test_qa_fetch_ui_phase30.py tests/test_ui_mvp.py`
    - `python3 scripts/check_docs_tree.py`
    - `python3 scripts/check_subagent_packet.py --phase-id phase_50`
  - SSOT writeback completed by orchestrator only: `G30.status_now=implemented`.
