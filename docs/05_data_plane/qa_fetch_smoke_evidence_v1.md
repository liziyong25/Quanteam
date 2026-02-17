# QA Fetch Smoke Evidence v1

## Scope

- Baseline: `docs/05_data_plane/qa_fetch_function_baseline_v1.md`
- Notebook params source: `notebooks/qa_fetch_manual_params_v3.ipynb`
- Window profile: `docs/05_data_plane/qa_fetch_smoke_window_profile_v1.json`
- Timeout policy: smoke mode uses `30s` per function.

## Frozen Evidence Quartet (G59)

Canonical per-attempt evidence artifacts are frozen as:

- `fetch_request.json`: normalized request payload (intent/function wrapper + policy)
- `fetch_result_meta.json`: deterministic runtime summary (`status/reason/source/source_internal/engine/provider_id/provider_internal/resolved_function/public_function/row_count/columns/dtypes/final_kwargs/mode`)
- `fetch_preview.csv`: preview output for review checkpoints
- `fetch_error.json`: required only when `status in {blocked_source_missing, error_runtime}`

Governance rules:

- Paths and filenames above are append-only and must remain stable for runtime/probe validators.
- Success paths must not emit placeholder `fetch_error.json`.
- Failure paths must emit machine-readable `fetch_error.json` with runtime classification fields.

## Execution Command

```bash
python3 scripts/run_qa_fetch_probe_from_notebook.py \
  --notebook notebooks/qa_fetch_manual_params_v3.ipynb \
  --matrix docs/05_data_plane/qa_fetch_function_baseline_v1.md \
  --window-profile docs/05_data_plane/qa_fetch_smoke_window_profile_v1.json \
  --out-dir docs/05_data_plane/qa_fetch_probe_v3
```

## Evidence Files

- `docs/05_data_plane/qa_fetch_probe_v3/probe_results_v3_notebook_params.json`
- `docs/05_data_plane/qa_fetch_probe_v3/probe_results_v3_notebook_params.csv`
- `docs/05_data_plane/qa_fetch_probe_v3/probe_summary_v3_notebook_params.json`
- `docs/05_data_plane/qa_fetch_probe_v3/candidate_pass_has_data_notebook_params.txt`
- `docs/05_data_plane/qa_fetch_probe_v3/candidate_pass_has_data_or_empty_notebook_params.txt`

## Baseline Result

- Total functions: `71`
- Engine split: `mongo=48`, `mysql=23`
- Status counts:
  - `pass_has_data=52`
  - `pass_empty=19`
  - `blocked_source_missing=0`
  - `error_runtime=0`
- Acceptance: `pass_has_data + pass_empty = 71` (full baseline coverage)

## Runtime Note

- `30s` timeout is only a smoke verification rule.
- `research/backtest` mode is allowed to run without default timeout in `qa_fetch.runtime`.
