# Phase Fetch G71: Fetch Contract Schema Upgrade and Alignment

## 1) Goal
Upgrade fetch request/result-meta contracts and align runtime/validator/test behavior within the authorized fetch-contract window.

## 2) Requirements
- MUST evolve only fetch contract schemas under:
  - `contracts/fetch_request_schema_v1.json`
  - `contracts/fetch_result_meta_schema_v1.json`
- MUST keep runtime evidence and validator behavior aligned with updated schema semantics.
- MUST add/adjust regression tests to cover new schema semantics.

## 3) Architecture & Interfaces
- Inputs:
  - `contracts/fetch_request_schema_v1.json`
  - `contracts/fetch_result_meta_schema_v1.json`
  - `src/quant_eam/contracts/validate.py`
  - `src/quant_eam/qa_fetch/runtime.py`
- Outputs:
  - upgraded fetch contract constraints and aligned runtime/test evidence

## 4) Out-of-scope
- Non-fetch contracts.
- Any policy changes.
- Holdout visibility behavior changes.

## 5) DoD
- `python3 scripts/check_docs_tree.py`
- `docker compose run --rm api pytest -q tests/test_fetch_contracts_phase77.py tests/test_qa_fetch_runtime.py tests/test_orchestrator_fetch_failfast_phase77.py`

## 6) Implementation Plan
### 6.1 Contract Upgrade Scope
- Updated `contracts/fetch_request_schema_v1.json`:
  - added `demo` mode compatibility;
  - expanded intent-first fields (`universe`, `fields`, `dataset_hint`, `sample`, `intent.auto_symbols`);
  - allowed `policy.on_no_data=retry`;
  - enforced `function` and `intent` mutual exclusion at schema level.
- Updated `contracts/fetch_result_meta_schema_v1.json`:
  - added deterministic metadata requirements: `selected_function`, `col_count`, `request_hash`, `probe_status`, `warnings`;
  - added optional observability fields: `coverage`, `min_ts`, `max_ts`;
  - added `demo` mode compatibility.

### 6.2 Runtime/Validator Alignment
- Updated `src/quant_eam/contracts/validate.py`:
  - added logical guardrails for `function` vs `intent` exclusivity;
  - added top-level vs intent-scoped `auto_symbols` conflict validation;
  - preserved fail-fast behavior for symbols/date ordering checks.
- Updated `src/quant_eam/qa_fetch/runtime.py`:
  - enriched `fetch_result_meta.json` with request hash, selected function alias, column count, probe status, warnings, coverage summary, and preview time bounds.

### 6.3 Regression Coverage
- Updated `tests/test_fetch_contracts_phase77.py` for new request/meta schema behaviors.
- Updated `tests/test_qa_fetch_runtime.py` to assert enriched metadata emission from `write_fetch_evidence`.

### 6.4 Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `docker compose run --rm api pytest -q tests/test_fetch_contracts_phase77.py tests/test_qa_fetch_runtime.py tests/test_orchestrator_fetch_failfast_phase77.py` passed (`20 passed`).
- `python3 scripts/check_subagent_packet.py --phase-id G71` passed via packet runner finish lifecycle.
- Retry record: first finish attempt failed due assertion mismatch in new mutual-exclusion error text; fixed test expectation and second attempt passed (1 retry used, <=2 limit).
