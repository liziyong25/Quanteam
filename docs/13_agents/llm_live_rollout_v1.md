# LLM Live Rollout v1 (Operational Protocol)

This document upgrades the Phase-26 LLM plumbing into a safe operational workflow:

- explicit rollout switches (`live`/`record`/`replay`)
- an extra human review checkpoint before live calls
- evidence-first failure handling and deterministic downgrade to replay
- UI labeling of LIVE/RECORD risk, budget, and evidence chain

## 1) Configuration (Env)

- `EAM_LLM_PROVIDER`: `mock` | `real_stub` | `real`
- `EAM_LLM_MODE`: `live` | `record` | `replay`
- `EAM_LLM_CASSETTE_DIR`: optional override (default: agent out_dir)

Real provider HTTP config:

- `EAM_LLM_REAL_BASE_URL`
- `EAM_LLM_REAL_API_KEY` (optional)
- `EAM_LLM_REAL_MODEL`
- `EAM_LLM_REAL_TIMEOUT_SECONDS`
- `EAM_LLM_REAL_RETRIES`

Safety:

- `EAM_LLM_DISABLE_NETWORK=1` hard-disables network calls by the real provider.
- Tests/CI always disable real-provider network (hard guard in provider).

## 2) Rollout Checkpoint: `llm_live_confirm`

When:

- `EAM_LLM_PROVIDER=real` AND `EAM_LLM_MODE in {live,record}`

Then the Orchestrator inserts an extra approval checkpoint:

- `WAITING_APPROVAL(step=llm_live_confirm)`

This checkpoint happens before the first agent step that could trigger a live call.

UI must show:

- provider_id / model
- job-level budget thresholds (from `llm_budget_policy`)
- best-effort estimate of remaining agent calls for this job

Only after explicit approval can the workflow proceed to call the real provider.

## 3) Cassette Recording & Replay

Cassette format:

- JSONL, append-only: `cassette.jsonl`
- lookup key: `prompt_hash` (sha256 of canonical sanitized request)

Replay requirements:

- In `replay` mode, the harness must find `prompt_hash` in the cassette.
- Missing cassette entry is INVALID and must not proceed silently.

## 4) Output Guard (Rollout Hardening)

Each agent run produces `output_guard_report.json` and it must contain:

- `prompt_version`
- `output_schema_version`
- `guard_status` and `passed`

If the guard FAILs:

- the workflow blocks at `WAITING_APPROVAL(step=agent_output_invalid)`
- UI shows findings and evidence paths

This prevents policy overrides / scripts / holdout leakage from being propagated into later steps.

## 5) Downgrade / Failure Handling

If the real provider fails (timeout/429/5xx or any provider exception):

1) harness writes `error_summary.json` (evidence-first)
2) harness attempts fallback to `replay` using an existing cassette entry
3) if cassette miss: orchestrator stops the job with:
   - `event_type=ERROR`
   - `message=STOPPED_LLM_ERROR`
   - `outputs.reason=STOPPED_LLM_ERROR`

Note: JobEvent schema currently enumerates `ERROR` but not a dedicated `STOPPED_LLM_ERROR` event type; therefore the stop reason is encoded in `message/outputs` while remaining schema-valid.

## 6) CI Policy

- CI/tests must be offline and deterministic.
- Real-provider network is hard-disabled under `pytest` execution.
- CI should use `mock` agent implementations or `replay` mode with pre-recorded cassettes.

## 7) Evidence Paths (SSOT)

Per agent run dir:

- `llm_session.json`
- `llm_calls.jsonl`
- `redaction_summary.json`
- `output_guard_report.json`
- `error_summary.json` (only on provider error / fallback attempt)

Per job:

- `jobs/<job_id>/outputs/llm/llm_usage_events.jsonl`
- `jobs/<job_id>/outputs/llm/llm_usage_report.json`

