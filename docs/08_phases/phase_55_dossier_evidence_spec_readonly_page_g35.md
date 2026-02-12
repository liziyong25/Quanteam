# Phase-55: Dossier Evidence Spec Read-Only Page (G35)

## 1) 目标（Goal）
- 完成 G35：交付 `/ui/dossier-evidence` 只读页面，展示 Whole View dossier 结构要求与当前 artifacts/dossiers 证据索引。

## 2) 背景（Background）
- Whole View Framework 第 4.4 节定义 dossier 证据包目录与关键文件。
- 无人值守治理需要通过 UI 验证 dossier 证据是否可见、可追溯、可审阅。

## 3) 范围（Scope）
### In Scope
- 新增 `/ui/dossier-evidence` 只读路由和模板渲染。
- 从 `docs/00_overview/Quant‑EAM Whole View Framework.md` 提取 dossier 结构条目并展示。
- 汇总 `artifacts/dossiers/*` 的 run 级证据文件覆盖概览（只读）。
- 增补 G35 回归测试覆盖可访问性、只读语义与关键字段展示。

### Out of Scope
- 修改 `contracts/**`。
- 修改 `policies/**`。
- 扩展 holdout 可见性。
- 新增写接口或修改非 G35 范围路由行为。

## 4) 任务卡（Task Card）
### Single Deliverable
- `G35` from `planned` to `implemented`.

### Allowed Paths
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/**`
- `src/quant_eam/ui/static/**`
- `tests/test_ui_mvp.py`
- `tests/test_ui_dossier_evidence_phase35.py`
- `docs/08_phases/phase_55_*.md`
- `docs/12_workflows/agents_ui_ssot_v1.yaml`
- `artifacts/subagent_control/phase_55/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停（仅 G35 exception 白名单范围内放行）。
- Subagent 禁止修改 `docs/12_workflows/agents_ui_ssot_v1.yaml`；仅主控在全部验收通过后回写 `G35.status_now=implemented`。

## 5) Subagent Control Packet
- `phase_id`: `phase_55`
- `packet_root`: `artifacts/subagent_control/phase_55/`
- `evidence_policy`: `hardened`

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_ui_dossier_evidence_phase35.py tests/test_ui_mvp.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_55`

## 7) 预期产物（Artifacts）
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/dossier_evidence.html`
- `tests/test_ui_dossier_evidence_phase35.py`
- `tests/test_ui_mvp.py`
- `artifacts/subagent_control/phase_55/task_card.yaml`
- `artifacts/subagent_control/phase_55/executor_report.yaml`
- `artifacts/subagent_control/phase_55/validator_report.yaml`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-12
- End Date: 2026-02-12
- Notes:
  - Published by orchestrator before subagent execution.
  - Task card enforces hardened evidence and G35 exception-scoped allowed paths.
  - Implemented `GET/HEAD`-only route: `/ui/dossier-evidence` in `src/quant_eam/api/ui_routes.py`.
  - Added Whole View section `4.4 Dossier` extractor + run-level dossier evidence index context rendering.
  - Added read-only template evidence view: `src/quant_eam/ui/templates/dossier_evidence.html`.
  - Updated navigation in `src/quant_eam/ui/templates/base.html` to expose the new G35 page.
  - Added G35 regression tests: `tests/test_ui_dossier_evidence_phase35.py`; expanded smoke coverage in `tests/test_ui_mvp.py`.
  - Acceptance passed:
    - `docker compose run --rm api pytest -q tests/test_ui_dossier_evidence_phase35.py tests/test_ui_mvp.py` => PASS (`6 passed`).
    - `python3 scripts/check_docs_tree.py` => PASS (`docs tree: OK`).
    - `python3 scripts/check_subagent_packet.py --phase-id phase_55` => PASS (recorded with bootstrap marker row + real packet check row).
  - SSOT writeback completed by orchestrator only: `G35.status_now=implemented`.
