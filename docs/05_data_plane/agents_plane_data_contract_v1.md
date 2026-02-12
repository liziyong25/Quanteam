# Agents Plane Data Contract v1

## Goal

Define a stable data contract for `6.4 Agents Plane` so agents consume data by dataset/query semantics first, not by hardcoded legacy module paths.

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
- Parameter precedence:
  - `LLM kwargs` > `window profile` > `function defaults`

## Registries

- Function registry: `docs/05_data_plane/qa_fetch_function_registry_v1.json`
  - 77 active functions (v3 matrix baseline)
  - source/provider/module metadata
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

## Adjust Rules

- External contract: `adjust=raw|qfq|hfq`
- Default: `raw`
- Runtime resolver maps `qfq/hfq` to corresponding `*_adv` fetch functions when available.

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

