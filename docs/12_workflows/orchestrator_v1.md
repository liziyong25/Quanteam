# Orchestrator v1 (Workflow Plumbing)

## Purpose
Provide a deterministic, auditable workflow layer (JobStore + Orchestrator + Worker executor + API/UI checkpoint) to run:

`blueprint -> compile -> (WAITING_APPROVAL) -> run -> gates -> registry`

Idea-driven workflow (with agents + extra checkpoints) is also supported:

`idea -> intent -> (approve blueprint) -> strategy_spec -> (approve strategy_spec) -> compile -> (approve runspec) -> trace_preview -> (approve trace_preview) -> run -> gates -> registry -> report`

This layer **does not** implement strategy logic, gate algorithms, or any agent/LLM behavior. It only wires existing kernel components together.

## SSOT / Governance Alignment
- Contracts are the only I/O SSOT: Blueprint/RunSpec/Dossier/GateResults/etc must validate against `contracts/**`.
- Policies are **read-only**:
  - `policy_bundle_path` is input convenience only (used to resolve the bundle asset).
  - Canonical reference is `policy_bundle_id` (written into `job_spec.json` / `idea_spec.json`), plus `outputs/policy_bundle_ref.json` contains the bundle sha256 for audit.
  - `extensions` are metadata only and must not be used to inline/override any policy params.
- Arbitration is not done here: this workflow writes artifacts; PASS/FAIL comes from GateRunner + evidence.

## Storage Layout (append-only)
Root: `EAM_JOB_ROOT` (default: `${EAM_ARTIFACT_ROOT}/jobs`)

```
${EAM_JOB_ROOT}/<job_id>/
  job_spec.json            # immutable (deterministic)
  inputs/blueprint.json    # derived from job_spec (immutable)
  inputs/idea_spec.json    # for idea jobs (immutable)
  events.jsonl             # append-only
  outputs/
    policy_bundle_ref.json # bundle_id + sha256 evidence (derived from policy_bundle_path)
    runspec.json           # compiler output
    agents/                # agent outputs (deterministic)
    trace_preview/         # calc trace preview artifacts (deterministic)
    outputs.json           # rebuildable index (references only)
  logs/                    # optional
```

Deterministic id:
- `job_id = sha256(canonical(job_spec.json))[:12]`

Append-only rules:
- `events.jsonl` is append-only
- `job_spec.json` and `inputs/blueprint.json` are treated as immutable once created
- `outputs/outputs.json` is a rebuildable cache (references only)

## State Machine (minimal)
Events are appended; effective state is derived from them.

States (v1):
- `BLUEPRINT_SUBMITTED`
- `IDEA_SUBMITTED`
- `BLUEPRINT_PROPOSED`
- `STRATEGY_SPEC_PROPOSED`
- `RUNSPEC_COMPILED`
- `TRACE_PREVIEW_COMPLETED`
- `WAITING_APPROVAL` (checkpoint; step-based)
- `APPROVED` (step-based)
- `RUN_COMPLETED`
- `GATES_COMPLETED`
- `REGISTRY_UPDATED`
- `REPORT_COMPLETED`
- `DONE`
- `ERROR` (terminal until operator intervention)

Stop/budget evidence:

- When budget/stop rules prevent further actions (spawn/proposals), a `STOPPED_BUDGET` event is appended with:
  - `reason` (which limit was hit)
  - `limit` and current counters (evidence for audit/replay)

Checkpoint rule:
- For each review step, the workflow **must stop** at `WAITING_APPROVAL(step=...)` until an `APPROVED(step=...)` event is appended.

Approval steps used in v1:
- `blueprint`
- `strategy_spec`
- `runspec`
- `trace_preview`
 - `improvements`

## Lineage (Spawned Jobs)

Spawned jobs record minimal lineage metadata under `job_spec.extensions.lineage`:

- `root_job_id`: lineage root (defaults to self for root jobs)
- `parent_job_id`: the spawning job id
- `generation`: depth from root (root is `0`)
- `iteration`: backward-compatible alias of `generation` (legacy field used by Phase-13 code)

Budget policies apply using this lineage metadata (see `docs/16_budget_stop/budget_policy_v1.md`).

## JobEvent Contract Evolution

- Old jobs may contain `job_event_v1` events (replayable).
- Current writer emits `job_event_v2` (adds `STOPPED_BUDGET` and clarifies governance).
- See ADR: `docs/09_adr/0003_job_event_contract_evolution.md`

## API/UI Checkpoints
JSON API:
- `POST /jobs/blueprint` (body: blueprint JSON; required query `snapshot_id`)
- `POST /jobs/idea` (body: idea_spec JSON)
- `POST /jobs/{job_id}/approve?step=...` (append-only APPROVED event)
- `GET /jobs`, `GET /jobs/{job_id}`

UI:
- `/ui/jobs` list
- `/ui/jobs/{job_id}` timeline + approve button (writes a job event only)

Security:
- `job_id` allowlist validation
- job files read/write restricted to `EAM_JOB_ROOT` (no traversal)
- Optional write auth (LAN hardening, default off):
  - `EAM_WRITE_AUTH_MODE=off|basic`
  - `EAM_WRITE_AUTH_USER` / `EAM_WRITE_AUTH_PASS`
  - When enabled, write endpoints (`/jobs/idea`, `/jobs/*/approve`, `/jobs/*/spawn`, and UI POST helpers) require HTTP Basic Auth.

## Worker Executor
CLI:
- `python -m quant_eam.worker.main --run-jobs --once`

Behavior:
- scan jobs (deterministic order)
- advance each job until blocked (`WAITING_APPROVAL`) or terminal (`DONE`/`ERROR`)
- no network I/O

## Phase-21: Segment Review (Evaluation Protocol v1)

When the compiled RunSpec contains `runspec.segments.list` (walk-forward or multi-segment evaluation), the Runner writes segment evidence under a single dossier:

- `dossiers/<run_id>/segments/<segment_id>/metrics.json`
- `dossiers/<run_id>/segments/<segment_id>/curve.csv` (non-holdout only)
- `dossiers/<run_id>/segments/<segment_id>/trades.csv` (non-holdout only)
- `dossiers/<run_id>/segments_summary.json`

UI `/ui/runs/{run_id}` exposes a segment selector. Holdout segment view is minimal-only and must not render curve/trades details.
