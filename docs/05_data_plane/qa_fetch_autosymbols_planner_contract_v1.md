# QA Fetch Auto-Symbols Planner Contract v1

## Purpose

Freeze deterministic planner semantics for `auto_symbols=true` requests with missing symbols.

## Trigger

- Request has `auto_symbols=true` (top-level or `intent.auto_symbols=true`).
- Explicit symbols are absent.

## Required Planner Path

Planner MUST emit ordered append-only steps:

1. `list` step:
   - resolve candidate universe via list-capable fetch function
2. `sample` step:
   - deterministic sample from list candidates (default method: stable-first-n)
3. `day` step:
   - execute final day-level fetch request with sampled symbols

## Evidence Contract

- `fetch_steps_index.json` MUST contain exactly one entry per planner step in order.
- Canonical quartet files (`fetch_request/result_meta/preview/error`) MUST map to final (`day`) step outputs.
- Step files use stable names:
  - `step_001_*` for list
  - `step_002_*` for sample
  - `step_003_*` for day

## Failure Behavior

- Any planner-step failure must still emit corresponding step request/meta and optional error evidence.
- Final status must preserve deterministic runtime semantics (`pass_*`/`blocked_*`/`error_runtime`).

## Governance

- Contract freeze is documentation-only in skeleton track.
- Runtime/agent implementation is handled by impl track goals.
