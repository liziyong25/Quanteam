# LLM Cassette Recording + Replay Runbook v1

This runbook describes how to safely use `live` / `record` / `replay` modes in production-like workflows, while keeping CI/tests offline and deterministic.

## Core Rules (Non-Negotiables)

- CI/tests must never perform network IO. CI runs in deterministic offline mode (use `mock` or `replay`).
- LLM inputs must be sanitized (no `holdout`, `vault`, `secret`, `token`, `auth` keys).
- Holdout must not be sent to the LLM.
- All LLM-related evidence is append-only and stored under job outputs / agent run dirs.

## Modes

- `EAM_LLM_MODE=live`: call provider (no cassette write).
- `EAM_LLM_MODE=record`: call provider and append a call record into `cassette.jsonl`.
- `EAM_LLM_MODE=replay`: never call provider; must find `prompt_hash` in `cassette.jsonl` or fail (INVALID).

Provider selection:

- `EAM_LLM_PROVIDER=mock`: deterministic agent implementations (no external model).
- `EAM_LLM_PROVIDER=real`: HTTP provider (`RealHTTPProvider`) (network).

## Safe Recording Procedure (Local Only)

1) Start from a clean artifact root:

```bash
export EAM_ARTIFACT_ROOT=/tmp/eam_artifacts
export EAM_JOB_ROOT=$EAM_ARTIFACT_ROOT/jobs
export SOURCE_DATE_EPOCH=1700000000
```

2) Enable real provider + record mode:

```bash
export EAM_LLM_PROVIDER=real
export EAM_LLM_MODE=record
export EAM_LLM_REAL_BASE_URL=http://<your-llm-gateway>
export EAM_LLM_REAL_MODEL=<model-id>
export EAM_LLM_REAL_TIMEOUT_SECONDS=30
export EAM_LLM_REAL_RETRIES=2
```

3) Run the worker once and approve the **extra Phase-28 checkpoint**:

- The workflow will stop at `WAITING_APPROVAL(step=llm_live_confirm)` first.
- Approve it explicitly via UI or API:

```bash
curl -s -X POST "http://localhost:8002/jobs/<job_id>/approve?step=llm_live_confirm"
```

4) Let the job proceed through agent steps. Each agent writes evidence under:

- `jobs/<job_id>/outputs/agents/<step>/llm_session.json`
- `jobs/<job_id>/outputs/agents/<step>/llm_calls.jsonl`
- `jobs/<job_id>/outputs/agents/<step>/cassette.jsonl` (only when `record`)
- `jobs/<job_id>/outputs/agents/<step>/redaction_summary.json`
- `jobs/<job_id>/outputs/agents/<step>/output_guard_report.json`

5) Review evidence before committing any cassette:

- `redaction_summary.json`: verify sensitive keys removed and truncation is reasonable.
- `output_guard_report.json`: must be PASS for rollout; FAIL blocks the workflow.
- `llm_calls.jsonl`: verify request/response shapes and policy boundaries.

## Promote a Cassette Into Fixtures (Optional)

When you want to freeze a recorded behavior for offline regression:

1) Copy the cassette to a fixture directory:

```bash
python3 scripts/rotate_cassettes.py \\
  --from jobs/<job_id>/outputs/agents/intent/cassette.jsonl \\
  --agent intent_agent_v1 \\
  --case my_case
```

2) Update regression fixtures:

- For deterministic agents that already have `expected_output.json`, update it if the promptpack/output schema changed intentionally.
- CI should still run with `mock` or `replay` only.

Run:

```bash
python -m quant_eam.agents.regression --agent intent_agent_v1 --cases tests/fixtures/agents/intent_agent_v1
```

## Replay / Downgrade Procedure (Production Safety)

If the real provider fails (timeout/429/5xx), the harness will:

- write `error_summary.json`
- attempt fallback to `replay` using an existing cassette entry for the same `prompt_hash`
- if cassette is missing: stop the job with `ERROR` event annotated as `STOPPED_LLM_ERROR`

To force replay (no network):

```bash
export EAM_LLM_MODE=replay
export EAM_LLM_PROVIDER=real   # ok: replay must not call the network
```

To hard-disable network even in dev:

```bash
export EAM_LLM_DISABLE_NETWORK=1
```

