# Phase-10: Workflow Orchestrator v1 + Review Checkpoints

## 1) 目标（Goal）
- 新增确定性的工作流编排层：JobStore + Orchestrator + Worker 执行器 + API/UI 审阅点（Approve checkpoint）。

## 2) 背景（Background）
- 没有 workflow 层时，compile/run/gates/registry 的执行顺序与审阅点容易漂移，且缺少可审计的 append-only 事件链。
- 本 Phase 将链路固定为：`blueprint -> compile -> (WAITING_APPROVAL) -> run -> gates -> registry`，并提供最小 API/UI 入口。

## 3) 范围（Scope）
### In Scope
- JobStore（文件式、append-only events）
- Orchestrator（确定性推进逻辑 + 审阅 checkpoint）
- Worker 新增 `--run-jobs --once`
- API: `/jobs/*` JSON endpoints
- UI: `/ui/jobs` 与 job detail + approve 按钮
- Contracts：新增 job_spec/job_event schema（用于工具/审计一致口径）

### Out of Scope
- 不实现 Agents/LLM
- 不实现参数搜索/budget
- 不修改 compiler/runner/gaterunner/registry 的核心逻辑（只复用其现有入口）

## 4) 实施方案（Implementation Plan）
- job_id = sha256(canonical job_spec)[:12]
- 事件溯源：`events.jsonl` append-only；状态由事件推导
- compile 成功后强制停在 WAITING_APPROVAL，直到 `APPROVED` event
- APPROVED 后一次 worker pass 可推进至 DONE（run->gates->registry）
- path traversal 防护：job_id allowlist，限制读写在 `EAM_JOB_ROOT`

## 5) 编码内容（Code Deliverables）
- 修改目录范围：`src/quant_eam/orchestrator/**`, `src/quant_eam/jobstore/**`, `src/quant_eam/worker/**`, `src/quant_eam/api/**`, `src/quant_eam/ui/templates/**`, `contracts/**`, `tests/**`, `docs/**`, `scripts/check_docs_tree.py`
- 新增/修改文件（核心）：
  - `src/quant_eam/jobstore/store.py`
  - `src/quant_eam/orchestrator/workflow.py`
  - `src/quant_eam/worker/main.py`（新增 `--run-jobs`）
  - `src/quant_eam/api/jobs_api.py`
  - `src/quant_eam/ui/templates/jobs.html`, `src/quant_eam/ui/templates/job.html`
  - `contracts/job_spec_schema_v1.json`, `contracts/job_event_schema_v1.json`
  - `tests/test_orchestrator_phase10_e2e.py`

## 6) 文档编写（Docs Deliverables）
- `docs/12_workflows/orchestrator_v1.md`
- 本 phase log（本文件）

## 7) 验收标准（Acceptance Criteria / DoD）
- `docker compose build api worker`
- `EAM_UID=$(id -u) EAM_GID=$(id -g) docker compose run --rm api pytest -q`
- demo（离线、两段推进）：
  - `docker compose run --rm api python -m quant_eam.data_lake.demo_ingest --snapshot-id demo_snap_job_001`
  - `docker compose run --rm api bash -lc 'python - <<\"PY\"\nimport json\nfrom pathlib import Path\nimport requests\nPY'`（或用 curl / API client 提交 blueprint 后 worker 推进）

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-10 (Asia/Taipei)
- End Date: 2026-02-10 (Asia/Taipei)
- PR/Commit: unknown (git not detected in this workspace)
- Notes:
  - Added JobStore (append-only) + Orchestrator checkpoint (WAITING_APPROVAL).
  - Added `/jobs/*` JSON API and `/ui/jobs` review pages.
  - Worker supports `--run-jobs --once` to advance deterministically.

## 9) 遗留问题（Open Issues）
- [ ] API submit currently requires `snapshot_id` as query param (or env default). Future UX may add a separate JobSpec submit endpoint.

## 10) Codex Prompt Footer

Append `docs/_snippets/codex_phase_footer.md`.

