# LLM Budget + Job-Level Usage Evidence v1

This document defines how the Agents Plane records LLM usage and enforces job-level budgets deterministically.

## 1) Budget Policy (Governance Input)

Asset:
- `policies/llm_budget_policy_v1.yaml`

Semantics:
- Budget is **job-scoped**, not per-run.
- Policies are read-only: agents/modules must not inline/override budget params.

## 2) Evidence Paths (Append-only)

For each job:
- `jobs/<job_id>/outputs/llm/llm_usage_events.jsonl` (append-only)
- `jobs/<job_id>/outputs/llm/llm_usage_report.json` (aggregate summary, rebuildable from events)

Each agent run also writes (per agent out_dir):
- `llm_session.json`
- `llm_calls.jsonl`
- `redaction_summary.json`
- `output_guard_report.json`

## 3) Enforce Points

- Harness enforce (pre-call):
  - checks the job totals + would-be delta against policy limits
  - if exceeded, records a usage event with `would_exceed=true` and stops agent execution
- Orchestrator enforce:
  - if job is budget-stopped (or totals exceed), writes `STOPPED_BUDGET` and prevents further advancement

## 4) Stop Reasons (Examples)

- `exceeded_max_calls_per_job`
- `exceeded_max_prompt_chars_per_job`
- `exceeded_max_response_chars_per_job`
- `exceeded_max_wall_seconds_per_job`

UI must display:
- budget thresholds
- totals + by-agent breakdown
- stop reason (if stopped)

