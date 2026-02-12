# Phase-74: Playbook Construction Sequence Recommendation Evidence Page (G54)

## 1) 目标（Goal）
- 完成 G54：交付 `/ui/playbook-sequence` 只读页面，展示《Quant‑EAM Implementation Phases Playbook》section 5 的施工顺序建议证据。

## 2) 背景（Background）
- Playbook section 5 给出了最快形成可用系统的施工优先级（闭环优先、agents 后置），是无人值守调度的关键规划依据。
- 该建议需要在 UI 中只读可审阅，确保主控滚动规划遵循同一顺序逻辑。

## 3) 范围（Scope）
### In Scope
- 新增 `/ui/playbook-sequence` 只读路由与模板渲染。
- 从 `Quant‑EAM Implementation Phases Playbook.md` section 5 提取施工顺序建议与优先级理由证据。
- 增补 G54 回归测试覆盖只读语义、顺序建议展示与可访问性。

### Out of Scope
- 修改 `contracts/**`。
- 修改 `policies/**`。
- 扩展 holdout 可见性。
- 新增写接口或修改非 G54 范围路由行为。

## 4) 任务卡（Task Card）
### Single Deliverable
- `G54` from `planned` to `implemented`.

### Allowed Paths
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/**`
- `src/quant_eam/ui/static/**`
- `tests/test_ui_mvp.py`
- `tests/test_ui_playbook_sequence_phase54.py`
- `docs/08_phases/phase_74_*.md`
- `docs/12_workflows/agents_ui_ssot_v1.yaml`
- `artifacts/subagent_control/phase_74/**`

### Stop Conditions
- 触发 `autopilot_stop_conditions_v1` 任一项即暂停（仅 G54 exception 白名单范围内放行）。
- Subagent 禁止修改 `docs/12_workflows/agents_ui_ssot_v1.yaml`；仅主控在全部验收通过后回写 `G54.status_now=implemented`。

## 5) Subagent Control Packet
- `phase_id`: `phase_74`
- `packet_root`: `artifacts/subagent_control/phase_74/`
- `evidence_policy`: `hardened`

## 6) 验收标准（Acceptance Criteria / DoD）
- `docker compose run --rm api pytest -q tests/test_ui_playbook_sequence_phase54.py tests/test_ui_mvp.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_74`

## 7) 预期产物（Artifacts）
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/playbook_sequence.html`
- `tests/test_ui_playbook_sequence_phase54.py`
- `tests/test_ui_mvp.py`
- `artifacts/subagent_control/phase_74/task_card.yaml`
- `artifacts/subagent_control/phase_74/executor_report.yaml`
- `artifacts/subagent_control/phase_74/validator_report.yaml`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-12
- End Date: 2026-02-12
- Notes:
  - Published by orchestrator before subagent execution.
  - Task card enforces hardened evidence and G54 exception-scoped allowed paths.
  - Implemented `/ui/playbook-sequence` as a read-only evidence page with section-5-only extraction from `Quant‑EAM Implementation Phases Playbook.md` (recommended Phase‑0→6 closure path, loop-first rationale, and agents-automation-after-closure note).
  - Added/updated regression coverage: `tests/test_ui_playbook_sequence_phase54.py` and `tests/test_ui_mvp.py` for route availability, section-5 evidence rendering, and no-write semantics.
  - Acceptance outcome: required pytest/docs/packet commands passed.
  - Subagent packet remains pre-writeback: `validator_report.checks[name=ssot_updated].pass=false`; SSOT writeback remains orchestrator-owned.
  - Orchestrator finalized writeback: `docs/12_workflows/agents_ui_ssot_v1.yaml` updated to `G54.status_now=implemented`; `validator_report.yaml` promoted to final pass state.
