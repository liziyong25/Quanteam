# QA Fetch Resolver & Registry v1

This document defines the machine-readable selector layer for data fetch functions.

## Goal

- Stop agents from guessing function names.
- Resolve data requests deterministically from structured intent:
  - `asset`, `freq`, `venue`, `adjust`

## Runtime API

- Module: `quant_eam.qa_fetch.resolver`
- Main APIs:
  - `resolve_fetch(asset, freq, venue=None, adjust="raw")`
  - `fetch_market_data(asset, freq, symbols, start, end, venue=None, adjust="raw")`
  - `qa_fetch_registry_payload(include_drop=False)`

## Resolution Rules

- Naming baseline: `fetch_<asset>_<freq>[_<venue>]`
- `venue` suffix is optional; default is generic source (no venue suffix).
- `adjust`:
  - default: `raw`
  - supported values: `raw|qfq|hfq`
  - `qfq|hfq` requires an available `*_adv` mapping for the requested market-data key.

## Runtime Contract Hardening (G28)

- `resolve_fetch` now enforces deterministic runtime validation for selector fields:
  - `asset`, `freq`, `adjust` must be string inputs and normalize via `snake_case` after trim.
  - blank `adjust` normalizes to `raw`; blank `venue` normalizes to `None`.
  - non-string selector inputs fail with stable type-based errors (no object-memory-address noise).
- `fetch_market_data` now validates runtime call inputs before backend dispatch:
  - `symbols` must be a non-empty `str` or non-empty `list[str]`/`tuple[str]` (items trimmed and validated).
  - `start`, `end`, `format` must be non-empty strings (trimmed).
  - invalid runtime inputs fail deterministically in resolver layer instead of leaking backend-specific errors.

## Review Checkpoint Contract Freeze (G60)

Frozen review-checkpoint semantics for fetch planning:

- Priority: `intent` semantics are reviewed before any concrete function mapping.
- List-to-day planning requirement:
  - when `symbols` are absent and auto-expansion is enabled, planning must explicitly encode `list -> sample(optional) -> day` expectation.
  - checkpoint evidence must preserve this path as auditable planner intent (no hidden provider fallback semantics).
- Read-only review scope:
  - checkpoint contract documents what runtime/probe must emit;
  - it does not grant write/mutation controls in review UI surfaces.

## Artifacts

- Function baseline: `docs/05_data_plane/qa_fetch_function_baseline_v1.md`
- Machine registry JSON: `docs/05_data_plane/qa_fetch_registry_v1.json`
- Function registry JSON: `docs/05_data_plane/qa_fetch_function_registry_v1.json`
- Dataset registry JSON: `docs/05_data_plane/qa_dataset_registry_v1.json`
- Agents data contract: `docs/05_data_plane/agents_plane_data_contract_v1.md`
- Runtime gating:
  - `execute_fetch_by_name(...)` resolves only canonical functions listed in function registry.
  - functions outside the frozen baseline return `blocked_source_missing` with reason `not_in_baseline`.
- Provider naming:
  - external contract: `source=fetch`, `provider_id=fetch`
  - engine routing: `engine=mongo|mysql`
  - internal tracing: `source_internal` / `provider_internal` (e.g. `mongo_fetch`, `mysql_fetch`)
- Generator scripts:
  - `python3 scripts/generate_qa_fetch_rename_matrix.py`
  - `python3 scripts/generate_qa_fetch_registry_json.py`
  - `python3 scripts/generate_qa_fetch_registry_json.py --check`

`generate_qa_fetch_registry_json.py --check` validates that the checked-in registry JSON is semantically in sync with the generated payload.  
Comparison ignores `generated_at_utc` and returns non-zero when semantic drift is detected.

## Notebook Evidence

- Smoke notebook: `notebooks/qa_fetch_smoke_v1.ipynb`
- Template notebook: `notebooks/qa_fetch_template_v1.ipynb`

Both notebooks print:

- `head()`
- `columns`
- `dtypes`
- `len`

for each query attempt.
