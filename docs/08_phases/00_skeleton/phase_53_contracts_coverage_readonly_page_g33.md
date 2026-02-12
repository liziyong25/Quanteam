# Phase-53: Contracts Coverage Read-Only Page (G33)

## 1) 目标（Goal）
- 完成 G33：交付 `/ui/contracts-coverage` 只读页面，展示 Whole View 所需 contracts 覆盖情况与证据路径，支持黑盒治理审阅。

## 2) 背景（Background）
- Whole View Framework 第 5.1 节定义了必须落地的 contracts；需要在 UI 直接可见其覆盖状态。
- 为维持“用户不看源码”的审阅体验，contracts 侧应通过只读证据页呈现，不引入写入行为。

## 3) 范围（Scope）
### In Scope
- 新增 `/ui/contracts-coverage` 只读路由和模板渲染。
- 基于 `docs/00_overview/Quant‑EAM Whole View Framework.md` 提取 required contracts，并映射本仓库 contracts 路径存在性。
- 增补 G33 回归测试覆盖可访问性、只读语义与关键字段展示。

### Out of Scope
- 修改 `contracts/**`。
- 修改 `policies/**`。
- 扩展 holdout 可见性。
- 新增写接口或修改非 G33 范围路由行为。

## 4) 任务卡（Task Card）
### Single Deliverable
- `G33` from `planned` to `implemented`.

### Allowed Paths
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/**`
- `src/quant_eam/ui/static/**`
- `tests/test_ui_mvp.py`
- `tests/test_ui_contracts_coverage_phase33.py`
- `docs/08_phases/00_skeleton/phase_53_*.md`
- `docs/12_workflows/skeleton_ssot_v1.yaml`
- `artifacts/subagent_control/phase_53/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停（仅 G33 exception 白名单范围内放行）。
- Subagent 禁止修改 `docs/12_workflows/skeleton_ssot_v1.yaml`；仅主控在全部验收通过后回写 `G33.status_now=implemented`。

## 5) Subagent Control Packet
- `phase_id`: `phase_53`
- `packet_root`: `artifacts/subagent_control/phase_53/`
- `evidence_policy`: `hardened`

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_ui_contracts_coverage_phase33.py tests/test_ui_mvp.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_53`

## 7) 预期产物（Artifacts）
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/contracts_coverage.html`
- `tests/test_ui_contracts_coverage_phase33.py`
- `tests/test_ui_mvp.py`
- `artifacts/subagent_control/phase_53/task_card.yaml`
- `artifacts/subagent_control/phase_53/executor_report.yaml`
- `artifacts/subagent_control/phase_53/validator_report.yaml`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-12
- End Date: 2026-02-12
- Notes:
  - Published by orchestrator before subagent execution.
  - Task card enforces hardened evidence and G33 exception-scoped allowed paths.
  - Added read-only route/template: `/ui/contracts-coverage` (`GET/HEAD` only) with no write actions.
  - Required contracts are sourced from Whole View section `5.1 必须落地的 Contracts（v1）` in:
    - `docs/00_overview/Quant‑EAM Whole View Framework.md`
  - Page renders on-disk coverage evidence per required contract:
    - `contracts/<required_contract_file>`
    - presence status + `sha256` digest
  - Added regression coverage:
    - `tests/test_ui_contracts_coverage_phase33.py`
    - `tests/test_ui_mvp.py` (`/ui/contracts-coverage` smoke assertion)
  - Acceptance passed:
    - `docker compose run --rm api pytest -q tests/test_ui_contracts_coverage_phase33.py tests/test_ui_mvp.py`
    - `python3 scripts/check_docs_tree.py`
    - `python3 scripts/check_subagent_packet.py --phase-id phase_53`
  - SSOT writeback completed by orchestrator only: `G33.status_now=implemented`.
