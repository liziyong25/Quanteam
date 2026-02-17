# Subagent Control Packet v1

## Purpose

Provide a machine-checkable control packet so Orchestrator can enforce:

- task is delegated to Codex CLI subagent
- subagent stayed within allowed paths
- acceptance commands were executed
- hardened mode cross-checks real workspace/evidence logs (anti-self-report)
- validator gate is explicit and auditable

Packet root:

- `artifacts/subagent_control/<phase_id>/`

Evidence modes:

- `legacy` (default): validates against packet self-report fields
- `hardened`: also requires before/after workspace snapshots and acceptance command run logs

## Required Files

1. `task_card.yaml`
2. `executor_report.yaml`
3. `validator_report.yaml`

When `evidence_policy: hardened`, these files are also required:

4. `workspace_before.json`
5. `workspace_after.json`
6. `acceptance_run_log.jsonl`

## File Schemas (lightweight, YAML)

### task_card.yaml

Required fields:

- `schema_version: subagent_task_card_v1`
- `phase_id: <phase_id>`
- `goal_ids: [Gxx, ...]`
- `executor_required: codex_cli_subagent`
- `evidence_policy: legacy|hardened` (default `legacy` when omitted)
- `evidence_files:` (required when hardened)
  - `workspace_before`
  - `workspace_after`
  - `acceptance_log`
- `external_noise_paths: [ ... ]` (optional)
- `allowed_paths: [ ... ]`
- `acceptance_commands: [ ... ]`
- `required_skills: [ ... ]`
- `skill_enforcement_mode: warn|enforce`
- `reasoning_tier: medium|high|super_high`
- `reasoning_profile: {model, timeout_sec, retry}`
- `published_at`

### executor_report.yaml

Required fields:

- `schema_version: subagent_executor_report_v1`
- `phase_id: <phase_id>`
- `executor.role: codex_cli_subagent`
- `executor.runtime: codex_cli`
- `status: completed|failed`
- `changed_files: [ ... ]`
- `commands_run: [ ... ]`
- `skills_required: [ ... ]`
- `skills_used: [ ... ]`
- `skill_usage_evidence: [ ... ]`
- `reasoning_tier`
- `reasoning_runtime: {model, timeout_sec, retry, attempt}`
- `reported_at`

Optional (recommended in hardened mode):

- `evidence_summary:`
  - `workspace_before`
  - `workspace_after`
  - `acceptance_log`

### validator_report.yaml

Required fields:

- `schema_version: subagent_validator_report_v1`
- `phase_id: <phase_id>`
- `validator.role: orchestrator_codex`
- `status: pass|fail`
- `checks:`
  - `task_card_published`
  - `executor_is_codex_cli`
  - `codex_invoked`
  - `changed_files_non_empty`
  - `changed_files_within_allowed_paths`
  - `allowed_paths_only`
  - `acceptance_commands_executed`
  - `ssot_updated`
  - `skills_declared`
  - `skills_available`
  - `skills_invoked`
  - `reasoning_tier_applied`
- `reported_at`
- `milestone_eval` (optional):
  - `milestone_id`
  - `cluster_id`
  - `gate_ok`
  - `push_mode`
  - `recorded_at`

## Validation Command

```bash
python3 scripts/check_subagent_packet.py --phase-id <phase_id>
```

Default packet root:

- `artifacts/subagent_control`

## Additional Task Card Fields

- `subagent.execution_mode`: `codex_exec|acceptance_only`
- `subagent.codex_args`: argv list for codex execution
- `subagent.prompt_file`: prompt path passed to subagent
- `allow_noop`: boolean, defaults to `false`; when `true`, changed_files may be empty
- `required_skills`: skills that must be applied in this phase
- `skill_registry_snapshot`: mapping `skill_id -> skill_path`
- `skill_enforcement_mode`: `warn|enforce`
- `reasoning_tier`: `medium|high|super_high`
- `reasoning_profile`: codex runtime knobs (`model`, `timeout_sec`, `retry`)

## Hardened Evidence Format

### `workspace_before.json` / `workspace_after.json`

JSON object:

- `schema_version: subagent_workspace_snapshot_v1`
- `captured_at`
- `files: { "<repo_relative_path>": "<sha256>" }`

### `acceptance_run_log.jsonl`

One JSON object per line. Required fields per row:

- `command`
- `exit_code`
- `started_at`
- `ended_at`

Optional:

- `stdout_tail`

## Hardened Validation Rules

When `evidence_policy: hardened`, checker must enforce:

1. all required evidence files exist and are parseable
2. compute real change set from before/after snapshots:
   - `actual_changed = {path | before_hash != after_hash or only exists on one side}`
   - ignore ephemeral tool cache paths (`.pytest_cache/**`, `.ruff_cache/**`, `.mypy_cache/**`, `**/__pycache__/**`)
   - ignore any task-scoped external noise globs from `task_card.external_noise_paths` (for noisy external workspace drift)
3. compare non-packet changes:
   - `actual_non_packet == executor_report.changed_files(non_packet)`
4. each path in `actual_non_packet` must match `allowed_paths`
5. every `task_card.acceptance_commands` command has a successful (`exit_code=0`) entry in `acceptance_run_log.jsonl`

## Gate Rule

Orchestrator must treat a phase as **not accepted** unless:

1. packet exists and passes `check_subagent_packet.py`
2. docs/progress updates are present
3. UI black-box checks for the targeted SSOT goals are satisfied
