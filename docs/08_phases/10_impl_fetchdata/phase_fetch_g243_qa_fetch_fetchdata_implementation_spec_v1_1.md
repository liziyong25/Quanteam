# Phase G243: Requirement Gap Closure (QF-013)

## Goal
- Close requirement gap `QF-013` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:28`.

## Requirements
- Requirement ID: QF-013
- Owner Track: impl_fetchdata
- Clause: QA‑Fetch FetchData Implementation Spec (v1) / 1. 现有事实基线（必须保持可回归）

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
### 1) Runtime QF-013 baseline anchor
- Bind runtime to requirement anchor `QF-013` with deterministic constants:
  - requirement id,
  - source document,
  - clause text `QA‑Fetch FetchData Implementation Spec (v1) / 1. 现有事实基线（必须保持可回归）`.
- Keep baseline enforcement deterministic and regressive by relying on existing runtime contracts:
  - function registry baseline count + engine split checks,
  - probe summary baseline pass_has_data/pass_empty/callable-coverage checks,
  - runtime blocked behavior for functions outside baseline.

### 2) Regression test coverage
- Extend `tests/test_qa_fetch_runtime.py` with a dedicated `QF-013` anchor assertion test that verifies:
  - runtime anchor constants (`id/source/clause`),
  - baseline invariant constants (`engine split`, `function count`, `pass_has_data`, `pass_empty`).

### 3) SSOT writeback
- Update `docs/12_workflows/skeleton_ssot_v1.yaml`:
  - goal `G243` status `planned -> implemented`,
  - requirement `QF-013` status `planned -> implemented`,
  - capability cluster `CL_FETCH_243` status `partial -> implemented`.

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
- `rg -n "G243|QF-013" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
