# Phase-52: Whole View Governance Checklist Read-Only Page (G32)

## 1) 目标（Goal）
- 完成 G32：交付 `/ui/governance-checks` 只读页面，集中展示 Whole View 无漂移治理清单与最小终验命令，支持黑盒审阅。

## 2) 背景（Background）
- Whole View 自动推进要求将治理检查项可视化到 UI，避免依赖源码阅读。
- G31 已补齐 run gate detail 审阅入口；G32 负责把 SSOT + Whole View 规划文档中的治理清单固化为只读 UI 证据页。

## 3) 范围（Scope）
### In Scope
- 新增 `/ui/governance-checks` 只读路由和模板渲染。
- 从 SSOT 与 Whole View 规划文档读取并展示治理检查项、完成状态、依赖关系、最小终验命令。
- 增补 G32 回归测试覆盖页面可访问性、只读语义、关键治理字段呈现。

### Out of Scope
- 修改 `contracts/**`。
- 修改 `policies/**`。
- 扩展 holdout 可见性。
- 增加写接口或修改非 G32 范围路由行为。

## 4) 任务卡（Task Card）
### Single Deliverable
- `G32` from `planned` to `implemented`.

### Allowed Paths
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/**`
- `src/quant_eam/ui/static/**`
- `tests/test_ui_mvp.py`
- `tests/test_ui_governance_checks_phase32.py`
- `docs/08_phases/00_skeleton/phase_52_*.md`
- `docs/12_workflows/skeleton_ssot_v1.yaml`
- `artifacts/subagent_control/phase_52/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停（仅 G32 exception 白名单范围内放行）。
- Subagent 禁止修改 `docs/12_workflows/skeleton_ssot_v1.yaml`；仅主控在全部验收通过后回写 `G32.status_now=implemented`。

## 5) Subagent Control Packet
- `phase_id`: `phase_52`
- `packet_root`: `artifacts/subagent_control/phase_52/`
- `evidence_policy`: `hardened`

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_ui_governance_checks_phase32.py tests/test_ui_mvp.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_52`

## 7) 预期产物（Artifacts）
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/governance_checks.html`
- `tests/test_ui_governance_checks_phase32.py`
- `tests/test_ui_mvp.py`
- `artifacts/subagent_control/phase_52/task_card.yaml`
- `artifacts/subagent_control/phase_52/executor_report.yaml`
- `artifacts/subagent_control/phase_52/validator_report.yaml`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-11
- End Date: 2026-02-11
- Notes:
  - Published by orchestrator before subagent execution.
  - Task card enforces hardened evidence and G32 exception-scoped allowed paths.
  - Added read-only route/template: `/ui/governance-checks` (`GET/HEAD` only) with no write actions.
  - Checklist content is loaded from:
    - `docs/12_workflows/skeleton_ssot_v1.yaml`
    - `docs/00_overview/Quant‑EAM Whole View Framework.md`
    - `docs/00_overview/Quant‑EAM Implementation Phases Playbook.md`
  - Added regression coverage:
    - `tests/test_ui_governance_checks_phase32.py`
    - `tests/test_ui_mvp.py` (governance-checks smoke assertion)
  - Acceptance passed:
    - `docker compose run --rm api pytest -q tests/test_ui_governance_checks_phase32.py tests/test_ui_mvp.py`
    - `python3 scripts/check_docs_tree.py`
    - `python3 scripts/check_subagent_packet.py --phase-id phase_52`
  - SSOT writeback completed by orchestrator only: `G32.status_now=implemented`.
