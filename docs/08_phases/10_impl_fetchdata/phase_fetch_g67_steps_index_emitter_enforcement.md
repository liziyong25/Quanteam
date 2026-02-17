# Phase Fetch G67: Steps Index Emitter Enforcement

## 1) Goal
Implement deterministic `fetch_steps_index.json` emission for fetch evidence bundles.

## 2) Requirements
- MUST emit one-step index for current single-step runtime fetch execution.
- MUST reference existing quartet evidence paths.
- MUST keep output deterministic and machine-readable.
- MUST NOT modify `contracts/**`, `policies/**`, or holdout visibility scope.

## 3) Architecture & Interfaces
- Inputs:
  - `docs/05_data_plane/qa_fetch_steps_index_contract_v1.md`
  - `src/quant_eam/qa_fetch/runtime.py`
- Outputs:
  - runtime evidence emission update
  - regression coverage in `tests/test_qa_fetch_runtime.py`

## 4) Out-of-scope
- Provider-side query logic changes.
- Multi-step planner orchestration refactor.
- UI behavior changes.

## 5) DoD
- `python3 scripts/check_docs_tree.py`
- `docker compose run --rm api pytest -q tests/test_qa_fetch_runtime.py`

## 6) Implementation Plan
### 6.1 Execution Strategy
- Extend runtime evidence writer to emit deterministic `fetch_steps_index.json`.
- Keep implementation confined to runtime writer and unit tests.

### 6.2 Controller Execution Record
- Updated `src/quant_eam/qa_fetch/runtime.py`:
  - emit `fetch_steps_index.json` with schema/version and ordered step entries.
  - include `fetch_steps_index_path` in return mapping.
- Added/updated coverage in `tests/test_qa_fetch_runtime.py` for success/failure step index semantics.

### 6.3 Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `docker compose run --rm api pytest -q tests/test_qa_fetch_runtime.py` passed.
