# Phase-30: UI Idea Job Creation v1

## 1) 目标（Goal）
- Deliver SSOT goal G01: create an `idea_spec_v1` job directly from UI (`/ui`) and land on job review page.

## 2) 背景（Background）
- `POST /jobs/idea` already exists and workflow/kernel can process idea jobs deterministically.
- SSOT marks G01 as `planned`; user currently cannot submit idea jobs from UI.
- Closing this gap enables UI-first workflow entry and keeps users out of source-level/API-only operations.

## 3) 范围（Scope）
### In Scope
- Add an idea submission form on `/ui`.
- Add a UI POST route to validate form input and create job via existing jobstore/API path.
- Redirect to `/ui/jobs/<job_id>` after creation.
- Add tests for black-box UI behavior and deterministic artifacts.
- Update SSOT/phase docs after acceptance.

### Out of Scope
- Prompt Studio (`G11`) and prompt version editing.
- Trace preview K-line overlay enhancements (`G05` remaining item).
- Contract/policy schema changes.

## 4) 任务卡（Task Card）
### Single Deliverable
- `G01` from `planned` to `implemented`: UI can submit idea job and persist expected artifacts.

### Allowed Paths
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/index.html`
- `src/quant_eam/ui/static/ui.css` (only if required by form layout)
- `tests/test_ui_mvp.py` (or dedicated new UI test file)
- `docs/08_phases/00_skeleton/phase_30_ui_idea_job_creation_v1.md`
- `docs/12_workflows/skeleton_ssot_v1.yaml`

### Hard No / Stop Conditions
- Stop and ask user before:
  - Any contract change under `contracts/**`
  - Any policy behavior/version change under `policies/**`
  - Any holdout visibility expansion beyond current minimal rules
  - Cross-cutting refactor outside UI idea submission scope

## 5) 实施方案（Implementation Plan）
- UI index page renders a minimal `idea_spec_v1` form with required fields.
- UI POST endpoint:
  - enforces write auth (`EAM_WRITE_AUTH_MODE`)
  - builds `idea_spec_v1` payload deterministically from form values
  - validates payload and policy override redline
  - creates job and appends `IDEA_SUBMITTED`
  - redirects to `/ui/jobs/<job_id>`
- Tests verify:
  - form is visible on `/ui`
  - successful submission returns redirect to job detail
  - `job_spec.json` + `inputs/idea_spec.json` exist
  - latest event includes `IDEA_SUBMITTED`

### 5.1) Subagent Control Packet
- `artifacts/subagent_control/phase_30/task_card.yaml`
- `artifacts/subagent_control/phase_30/executor_report.yaml`
- `artifacts/subagent_control/phase_30/validator_report.yaml`

## 6) 验收标准（Acceptance Criteria / DoD）
### 必须可执行的验收命令
- `pytest -q tests/test_ui_mvp.py`
- `python3 scripts/check_docs_tree.py`
- `python3 scripts/check_subagent_packet.py --phase-id phase_30`

### UI 黑盒检查
- Open `/ui` and see "Create Idea Job" section.
- Submit required fields and observe redirect to `/ui/jobs/<job_id>`.
- Job page shows newly created job id and event timeline including idea submission.

### 预期产物（Artifacts）
- `jobs/<job_id>/job_spec.json`
- `jobs/<job_id>/inputs/idea_spec.json`
- `jobs/<job_id>/events.jsonl` contains `IDEA_SUBMITTED`

## 7) 文档编写（Docs Deliverables）
- This phase log file (`docs/08_phases/00_skeleton/phase_30_ui_idea_job_creation_v1.md`)
- SSOT status update (`docs/12_workflows/skeleton_ssot_v1.yaml`)

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-11
- End Date: 2026-02-11
- Notes:
  - Task card published first per subagent workflow.
  - Added `/ui` idea submission form and `/ui/jobs/idea` POST route.
  - Added UI/security tests and verified deterministic artifact/state progression.

## 9) 遗留问题（Open Issues）
- [ ] Optional UX follow-up: prefill defaults from latest snapshot catalog for faster idea submission.

## 10) 验收证据（Acceptance Evidence）
- Commands:
  - `EAM_UID=$(id -u) EAM_GID=$(id -g) docker compose run --rm api pytest -q tests/test_ui_mvp.py tests/test_write_auth_phase13r.py`
  - `python3 scripts/check_docs_tree.py`
- Results:
  - `5 passed` (targeted UI + write-auth coverage)
  - `docs tree: OK`
