# Agents Plane Data Contract v1

## Goal

Define a stable data contract for `6.4 Agents Plane` so agents consume data by dataset/query semantics first, not by hardcoded legacy module paths.

Selection order for agent runtime:

1. Prefer `query_dataset(...)` on `DataCatalog`.
2. Fallback to `qa_fetch.runtime` only when dataset mapping is missing or function-level behavior is explicitly required.

## Primary Query API

- Module: `src/quant_eam/datacatalog/catalog.py`
- API:
  - `query_dataset(snapshot_id, dataset_id, filters, as_of, fields=None, adjust='raw')`
  - `query_ohlcv(...)` remains as compatibility wrapper.

## Runtime Fetch API

- Module: `src/quant_eam/qa_fetch/runtime.py`
- APIs:
  - `execute_fetch_by_intent(...)`
  - `execute_fetch_by_name(...)`
- Baseline gating:
  - canonical function must exist in `qa_fetch_function_registry_v1.json`
  - outside-baseline call returns `blocked_source_missing` with reason `not_in_baseline`
- Parameter precedence:
  - `LLM kwargs` > `window profile` > `function defaults`

## Registries

- Function registry: `docs/05_data_plane/qa_fetch_function_registry_v1.json`
  - 71 active functions (frozen baseline)
  - function key is canonical `fetch_*`; runtime dispatches through `target_name`
  - external routing semantics: `source=fetch`, `provider=fetch`
  - internal routing metadata: `engine`, `source_internal`, `provider_internal`
  - default smoke timeout and default kwargs
- Dataset registry: `docs/05_data_plane/qa_dataset_registry_v1.json`
  - dataset-level keys/time column/as_of rule/adjust support
  - function to dataset mapping

## As-Of Rules

- Market-like datasets (`*_day`, `*_min`, `*_transaction`, `*_tick`, `*_dk`, `ohlcv*`):
  - enforce `available_at <= as_of` when `available_at` exists
- Reference-like datasets:
  - `snapshot_effective_time` strategy
- Query result always returns `as_of_applied` metadata.
- Agent prompts must carry explicit `as_of` for reproducibility.

## Adjust Rules

- External contract: `adjust=raw|qfq|hfq`
- Default: `raw`
- Runtime resolver maps `qfq/hfq` to corresponding `*_adv` fetch functions when available.
- If `adjust` is omitted, runtime must use `raw`.

## Standard Result Shape

`query_dataset` result fields:

- `schema_version`
- `dataset_id`
- `snapshot_id`
- `adjust`
- `rows`
- `row_count`
- `columns`
- `dtypes`
- `as_of_applied`
- `source_lineage`
- `warnings`
- `errors`

## Agent Evidence Outputs

Per job:

- `jobs/<job_id>/outputs/fetch/fetch_request.json`
- `jobs/<job_id>/outputs/fetch/fetch_result_meta.json`
- `jobs/<job_id>/outputs/fetch/fetch_preview.csv`
- `jobs/<job_id>/outputs/fetch/fetch_error.json` (on failure)

These files are the canonical fetch evidence for replay/review.

Evidence metadata conventions:

- `source`: always `fetch` (external contract)
- `engine`: `mongo|mysql`
- `source_internal` / `provider_internal`: optional internal tracing fields for replay and debugging
