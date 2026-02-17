# Phase Fetch G69: Golden Queries Runner Smoke

## 1) Goal
Implement deterministic golden-query smoke runner and regression test coverage.

## 2) Requirements
- MUST load manifest requests and compute stable canonical request hashes.
- MUST write summary output with deterministic ordering.
- MUST provide test coverage for hash stability and summary output structure.
- MUST NOT modify `contracts/**`, `policies/**`, or holdout visibility scope.

## 3) Architecture & Interfaces
- Inputs:
  - `docs/05_data_plane/qa_fetch_golden_queries_v1.md`
  - `scripts/run_qa_fetch_golden_queries.py`
- Outputs:
  - runner script
  - `tests/test_qa_fetch_golden_queries.py`

## 4) Out-of-scope
- Live provider/network fetch execution.
- Orchestrator route/state transitions.
- UI presentation changes.

## 5) DoD
- `python3 scripts/check_docs_tree.py`
- `docker compose run --rm api pytest -q tests/test_qa_fetch_golden_queries.py`

## 6) Implementation Plan
### 6.1 Execution Strategy
- Build deterministic manifest validator and request-hash summary generator.
- Validate behavior via focused unit tests without requiring live provider access.

### 6.2 Controller Execution Record
- Added `scripts/run_qa_fetch_golden_queries.py`:
  - validates manifest schema/query shape/duplicate IDs.
  - computes canonical request hash per `query_id`.
  - writes deterministic summary JSON.
- Added `tests/test_qa_fetch_golden_queries.py`:
  - verifies deterministic hash summary output.
  - verifies duplicate `query_id` is rejected with non-zero exit.

### 6.3 Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `docker compose run --rm api pytest -q tests/test_qa_fetch_golden_queries.py` passed.
