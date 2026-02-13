# Phase Fetch G81: Fetch AsOf Availability Summary Runtime Emitter

## 1) Goal
Emit deterministic `as_of` and preview-level `available_at` availability summary in fetch result metadata.

## 2) Requirements
- MUST add `as_of` and `availability_summary` to fetch meta docs.
- MUST keep rule label fixed as `available_at<=as_of`.
- MUST compute summary deterministically from request+preview only.
- MUST NOT modify `contracts/**`, `policies/**`, or holdout visibility scope.

## 3) Architecture & Interfaces
- Inputs:
  - `docs/05_data_plane/qa_fetch_asof_availability_summary_contract_v1.md`
  - `src/quant_eam/qa_fetch/runtime.py`
- Outputs:
  - runtime meta enrichment
  - regression coverage in `tests/test_qa_fetch_runtime.py`

## 4) Out-of-scope
- DataCatalog/policy/gate changes.
- Provider-side query behavior changes.
- UI rendering updates.

## 5) DoD
- `python3 scripts/check_docs_tree.py`
- `docker compose run --rm api pytest -q tests/test_qa_fetch_runtime.py`

## 6) Implementation Plan
### 6.1 Execution Strategy
- Extend runtime meta builder with:
  - normalized `as_of` extraction from request payload;
  - preview-based `available_at` summary and violation count against `as_of`.
- Keep parser tolerant: invalid/absent timestamps never fail runtime.
- Add unit tests for:
  - valid `as_of` + available_at rows with violation counting;
  - no-as_of/no-available_at fallback semantics.

### 6.2 Controller Execution Record
- Published packet task card: `artifacts/subagent_control/G81/task_card.yaml`.
- Updated runtime metadata builder in `src/quant_eam/qa_fetch/runtime.py`.
- Added runtime regression assertions in `tests/test_qa_fetch_runtime.py`.

### 6.3 Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `docker compose run --rm api pytest -q tests/test_qa_fetch_runtime.py` passed.
- `python3 scripts/check_subagent_packet.py --phase-id G81` passed via packet finish lifecycle.
