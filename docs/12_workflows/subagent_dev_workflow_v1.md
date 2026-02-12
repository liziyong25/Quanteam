# Subagent Dev Workflow v1

## Purpose

Define how development runs in subagent mode with minimal user intervention:

- User approves goals and final UI outcomes.
- Orchestrator Codex plans and controls progress.
- Executor subagents implement scoped tasks.
- Validator subagent verifies acceptance evidence.

This workflow is driven by:

- `docs/12_workflows/agents_ui_ssot_v1.yaml`
- `docs/08_phases/*.md`
- `docs/12_workflows/subagent_control_packet_v1.md`
- repository state (code/tests/contracts/policies)

## Persistent Policies (No Per-turn Reminder Needed)

The following policies are long-term defaults and do not require repeating in every chat:

1. G11 Prompt Studio exception is pre-authorized within strict scope.

- Source of truth: `autopilot_stop_condition_exceptions_v1` in `docs/12_workflows/agents_ui_ssot_v1.yaml`
- Meaning: `Any API schema or route behavior change` stop condition is waived only for G11 and only for `/ui/prompts` scoped work.
- Redlines still apply: no edits under `contracts/**` or `policies/**`, no holdout visibility expansion.

2. G15 governance hardening is mandatory for unattended mode.

- Goal: eliminate self-report-only packet validation risk.
- Required direction: validate `changed_files` against actual git diff and validate acceptance commands against executable logs.
- Orchestrator should prioritize and complete G15 before expanding unattended feature development.

## Roles

1. Orchestrator Codex

- Reads SSOT and repository status.
- Selects the next task with the highest priority and satisfied dependencies.
- Issues one scoped Task Card.
- Blocks/halts when redlines are hit.
- Updates phase and workflow documentation.

2. Executor Subagent

- Implements only within allowed paths in the Task Card.
- Produces code, tests, and docs updates.
- Writes deterministic artifacts/evidence references.

3. Validator Subagent

- Runs acceptance commands.
- Verifies UI and artifact checks in SSOT.
- Produces pass/fail report with reasons.

4. User

- Does not monitor code-level process.
- Reviews final black-box UI outcomes and accepts/rejects.

## Lifecycle

### 1) Publish Task

Task input sources:

- SSOT goals/checkpoints in `docs/12_workflows/agents_ui_ssot_v1.yaml`
- Current phase logs in `docs/08_phases/`
- Current implementation gaps in code/tests

Task Card must include:

- Goal (single deliverable scope)
- Allowed paths
- Hard no / stop conditions
- Acceptance commands
- UI black-box checks
- Required docs updates

In addition, Orchestrator must create control packet:

- `artifacts/subagent_control/<phase_id>/task_card.yaml`

### 2) Execute Task

Executor rules:

- Keep changes minimal and scoped.
- Preserve append-only behavior and governance boundaries.
- No hidden side effects.
- Use deterministic outputs/replay-compatible evidence.
- Write executor packet:
  - `artifacts/subagent_control/<phase_id>/executor_report.yaml`
  - `executor.role=codex_cli_subagent`
  - `executor.runtime=codex_cli`

### 3) Validate Task

Validator checks:

- `pytest -q`
- linters/format checks as applicable
- `python3 scripts/check_docs_tree.py`
- API/UI smoke checks
- SSOT goal check entries touched by this task
- validate subagent packet:
  - `python3 scripts/check_subagent_packet.py --phase-id <phase_id>`

Validation output:

- PASS: all required checks satisfied
- FAIL: explicit failing checks + blocking reasons + suggested next patch

Validator must write:

- `artifacts/subagent_control/<phase_id>/validator_report.yaml`

### 4) Record Evidence

Minimum records per completed task:

- Phase log update in `docs/08_phases/phase_XX_*.md` (or patch log section)
- Workflow note update in `docs/12_workflows/subagent_dev_workflow_v1.md` if process changed
- SSOT progress/status update in `docs/12_workflows/agents_ui_ssot_v1.yaml`
- File change summary and acceptance evidence in final report
- Subagent packet must pass:
  - `python3 scripts/check_subagent_packet.py --phase-id <phase_id>`

### 5) User Acceptance

User reviews only:

- Required UI interactions
- Final visible behavior (black-box)
- Summary of acceptance evidence

If accepted, Orchestrator advances to next task automatically.

## Stop Conditions

Orchestrator must stop and request user decision if any of the following is required:

- Unless an explicit exception is defined in SSOT (`autopilot_stop_condition_exceptions_v1`) for the selected goal.

- Breaking changes to contracts
- Policy changes without approved versioning plan
- Holdout visibility expansion beyond minimal summary
- Non-deterministic behavior in tests/CI
- Cross-cutting refactors outside approved task scope
- Missing/invalid subagent packet
- Executor report role/runtime not equal to `codex_cli_subagent` / `codex_cli`

## Interaction Contract (User <-> Orchestrator)

User provides:

- Goal preference and final acceptance feedback

Orchestrator provides:

- Current progress snapshot
- Next Task Card
- Acceptance evidence package
- Updated documentation pointers

This keeps user involvement at the product level, not code-level monitoring.
