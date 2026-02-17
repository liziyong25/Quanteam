# Phase Fetch G79: Fetch Structural Sanity Checks Emitter and Runtime Guard

## 1) Goal
Implement deterministic structural sanity check summaries in fetch runtime evidence metadata.

## 2) Requirements
- MUST emit `sanity_checks` in fetch result meta for canonical and step-level meta files.
- MUST include monotonic timestamp check, duplicate timestamp count, and missing ratio by preview column.
- MUST remain additive and backward-compatible with existing status semantics.
- MUST NOT modify `contracts/**`, `policies/**`, or holdout visibility scope.

## 3) Architecture & Interfaces
- Inputs:
  - `docs/05_data_plane/qa_fetch_sanity_checks_contract_v1.md`
  - `src/quant_eam/qa_fetch/runtime.py`
- Outputs:
  - runtime meta enrichment with deterministic sanity summary
  - regression tests in `tests/test_qa_fetch_runtime.py`

## 4) Out-of-scope
- Provider fetch behavior changes.
- Policy or gate logic updates.
- UI rendering changes.

## 5) DoD
- `python3 scripts/check_docs_tree.py`
- `docker compose run --rm api pytest -q tests/test_qa_fetch_runtime.py`

## 6) Implementation Plan
### 6.1 Execution Strategy
- Extend runtime meta-builder to attach preview-based sanity summary under `sanity_checks`.
- Keep computation deterministic and tolerant of absent timestamp fields.
- Add focused runtime tests for sanity summary shape and values.

### 6.2 Controller Execution Record
- Published packet task card: `artifacts/subagent_control/G79/task_card.yaml`.
- Updated `src/quant_eam/qa_fetch/runtime.py` with sanity summary generation.
- Added runtime regression assertions in `tests/test_qa_fetch_runtime.py`.

### 6.3 Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `docker compose run --rm api pytest -q tests/test_qa_fetch_runtime.py` passed.
- `python3 scripts/check_subagent_packet.py --phase-id G79` passed via packet finish lifecycle.
