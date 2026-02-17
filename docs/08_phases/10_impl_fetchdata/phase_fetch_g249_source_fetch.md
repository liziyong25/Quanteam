# Phase G249: Requirement Gap Closure (QF-016)

## Goal
- Close requirement gap `QF-016` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:32`.

## Requirements
- Requirement ID: QF-016
- Owner Track: impl_fetchdata
- Clause: 对外语义：`source=fetch`

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
### 1) Runtime QF-016 semantic-source anchor
- Bind runtime to requirement anchor `QF-016` with deterministic constants:
  - requirement id,
  - source document,
  - clause text `对外语义：\`source=fetch\``,
  - semantic source value `fetch`.

### 2) Runtime registry contract enforcement
- Enforce function-registry row contract for active fetch mappings:
  - `source` must equal semantic value `fetch`,
  - internal routing remains validated by `source_internal`/`provider_internal` vs `engine`.

### 3) Regression test coverage
- Extend `tests/test_qa_fetch_runtime.py` with:
  - a `QF-016` anchor assertion test,
  - a registry negative test rejecting non-`fetch` external `source` semantics.

### 4) SSOT writeback
- Update `docs/12_workflows/skeleton_ssot_v1.yaml`:
  - goal `G249` status `planned -> implemented`,
  - requirement `QF-016` status `planned -> implemented`,
  - capability cluster `CL_FETCH_249` status `partial -> implemented`.

## Execution Record
- Date: 2026-02-14
- Runtime changes:
  - `src/quant_eam/qa_fetch/runtime.py`
- Test changes:
  - `tests/test_qa_fetch_runtime.py`
- SSOT changes:
  - `docs/12_workflows/skeleton_ssot_v1.yaml`

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py` passed.
- `rg -n "G249|QF-016" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
