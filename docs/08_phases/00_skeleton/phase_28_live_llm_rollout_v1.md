# Phase-28: Live LLM Rollout v1

## 1) 目标（Goal）
- Provide an operationally safe LIVE/RECORD rollout for real LLM providers: explicit approval checkpoint, deterministic downgrade to replay, and UI evidence labeling.

## 2) 背景（Background）
- Phase-26 introduced real provider plumbing and job-level budgets.
- Phase-28 hardens the workflow so LIVE calls are not triggered accidentally, and failures are evidenced and safely downgraded without breaking determinism.

## 3) 范围（Scope）
### In Scope
- Orchestrator adds `WAITING_APPROVAL(step=llm_live_confirm)` when `EAM_LLM_PROVIDER=real` and `EAM_LLM_MODE` is `live|record`.
- Output guard report enriched with `prompt_version`, `output_schema_version`, `guard_status`; guard FAIL blocks the workflow at `WAITING_APPROVAL(step=agent_output_invalid)`.
- Harness downgrades real provider failures to cassette replay (if available) and writes `error_summary.json`.
- UI labels LIVE/RECORD risk/budget and shows the evidence chain (including guard findings preview and error_summary).
- Runbook for recording/replay and cassette promotion to fixtures.
- Offline tests (no network IO).

### Out of Scope
- Introducing a new JobEvent enum value (contract change). Stop reason is encoded using `event_type=ERROR` with `message/outputs.reason=STOPPED_LLM_ERROR`.
- Changing policies or gate semantics.

## 4) 实施方案（Implementation Plan）
- Orchestrator reads env rollout config and blocks before agent execution unless `APPROVED(step=llm_live_confirm)` exists.
- Agent harness writes evidence and enforces Output Guard; on provider exception it writes `error_summary.json` and attempts cassette replay.
- UI renders additional checkpoint context and evidence preview.

## 5) 编码内容（Code Deliverables）
- `src/quant_eam/orchestrator/workflow.py`
  - add `llm_live_confirm` approval checkpoint for LIVE/RECORD + real provider
  - block on guard FAIL (`agent_output_invalid`)
- `src/quant_eam/agents/harness.py`
  - provider error -> `error_summary.json` + fallback to replay if cassette exists
  - output guard report includes prompt/meta fields
- `src/quant_eam/agents/guards.py`
  - enrich report with prompt/meta fields
- `src/quant_eam/llm/providers/real_http.py`
  - hard-disable network under pytest and when `EAM_LLM_DISABLE_NETWORK=1`
- `src/quant_eam/api/jobs_api.py`, `src/quant_eam/api/ui_routes.py`
  - allow approve steps `llm_live_confirm` and `agent_output_invalid`
  - UI shows rollout checkpoint details and evidence previews
- `src/quant_eam/ui/templates/job.html`
  - renders LIVE/RECORD confirmation panel and guard/error evidence
- `scripts/rotate_cassettes.py` (optional helper)

## 6) 文档编写（Docs Deliverables）
- `docs/13_agents/llm_live_rollout_v1.md`
- `docs/07_runbooks/llm_recording.md`
- `docs/08_phases/00_skeleton/phase_28_live_llm_rollout_v1.md` (this file)

## 7) 验收标准（Acceptance Criteria / DoD）
### 必须可执行的验收命令
- `EAM_UID=$(id -u) EAM_GID=$(id -g) docker compose run --rm api pytest -q`
- `python3 scripts/check_docs_tree.py`

### 预期产物（Artifacts）
- When LIVE/RECORD real provider is enabled, jobs block at `WAITING_APPROVAL(step=llm_live_confirm)` and UI shows provider/model/budget estimate.
- On provider failure, `error_summary.json` is written and replay fallback is attempted.
- On output guard FAIL, job blocks at `WAITING_APPROVAL(step=agent_output_invalid)` and UI shows findings preview.

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-11
- End Date: 2026-02-11
- Notes:
  - Tests remain offline deterministic; real-provider network is disabled under pytest.

## 9) 遗留问题（Open Issues）
- [ ] Consider a future contract version for JobEvent to add a dedicated `STOPPED_LLM_ERROR` event type (requires ADR + v3 schema).

