# LLM Budget Policy v1 (`llm_budget_policy_v1`)

Asset: `policies/llm_budget_policy_v1.yaml`

## Purpose

- Producer: governance / repo owner (frozen policy asset).
- Consumer: Agents harness + Orchestrator.

This policy sets **job-level** resource limits for LLM usage and defines stop conditions. It does not change strategy validity and must not be overridden by agents.

## Key Fields

Top-level:
- `policy_id`: e.g. `llm_budget_policy_v1_default`
- `policy_version`: must be `"v1"`
- `params`: budget thresholds

`params` (v1):
- `max_calls_per_job` (int >= 0)
- `max_prompt_chars_per_job` (int >= 0)
- `max_response_chars_per_job` (int >= 0)
- `max_wall_seconds_per_job` (int >= 0)
- `max_calls_per_agent_run` (optional int >= 0)

## Enforcement

- **Harness enforce**: before an LLM call, checks remaining budget; if exceeded, records usage event and returns a budget stop artifact (no further steps).
- **Orchestrator enforce**: if a job is budget-stopped, writes `STOPPED_BUDGET` event and prevents further job advancement (no bypass).
- **Evidence**: usage is recorded append-only under `jobs/<job_id>/outputs/llm/`.

## Forbidden

- Agents must not inline or override these params in any JSON outputs.
- UI is read-only and must not alter budgets or usage evidence.

