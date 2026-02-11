# ReportAgent v1 (Dossier + GateResults -> Report Artifacts)

## Boundary
ReportAgent is a deterministic summarizer:
- It must reference existing artifacts (metrics/curve/trades/gate_results) by path and field.
- It must not invent conclusions or arbitrate PASS/FAIL.
- It must not leak holdout internals beyond the minimal summary in `gate_results.json`.

## Input
Anchor input: `dossier_manifest.json` (path hashed in agent_run.json).

## Output
Written under dossier reports:
`$EAM_ARTIFACT_ROOT/dossiers/<run_id>/reports/agent/`
- `report_agent.md` (human readable; references artifacts)
- `report_summary.json` (machine readable summary)
- `agent_run.json` (audit record, `agent_run_v1`)

