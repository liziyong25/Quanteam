# Agents Harness v1 (MVP)

## Purpose
Provide a deterministic, auditable harness to run agents as **tools**, not arbiters.

Agents:
- can **propose** (IdeaSpec -> Blueprint draft)
- can **summarize** (Dossier + GateResults -> report artifacts)
- must not decide PASS/FAIL, must not modify policies, must not bypass kernel components.

## Inputs/Outputs Are Contracts
- IdeaSpec: `contracts/idea_spec_schema_v1.json`
- Blueprint: `contracts/blueprint_schema_v1.json`
- AgentRun audit record: `contracts/agent_run_schema_v1.json`

## Determinism / Offline
- Tests use `provider="mock"` only (no network I/O).
- `agent_run.json` records input path + sha256, plus output paths.

## Artifact Layout
Agent outputs live under:
- Job outputs (IntentAgent): `${EAM_JOB_ROOT}/<job_id>/outputs/agents/intent/*`
- Dossier reports (ReportAgent): `${EAM_ARTIFACT_ROOT}/dossiers/<run_id>/reports/agent/*`

