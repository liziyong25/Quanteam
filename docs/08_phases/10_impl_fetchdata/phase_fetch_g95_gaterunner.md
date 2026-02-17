# Phase G95: Requirement Gap Closure (QF-011)

## Goal
- Close requirement gap `QF-011` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:23`.

## Requirements
- Requirement ID: QF-011
- Owner Track: impl_fetchdata
- Clause: 策略是否有效的裁决（只允许 GateRunner 裁决）；

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
### Execution Strategy
- Keep fetch execution semantics unchanged for valid requests.
- Add a deterministic boundary guard that rejects GateRunner-only arbitration fields from `qa_fetch` payloads.
- Lock boundary behavior with focused runtime tests and SSOT requirement writeback.

### Concrete Changes
- Added GateRunner arbitration boundary contract:
  - `docs/05_data_plane/qa_fetch_gaterunner_arbitration_boundary_contract_v1.md`
- Updated runtime boundary enforcement:
  - `src/quant_eam/qa_fetch/runtime.py`
  - Added GateRunner-only arbitration field guard in shared boundary enforcement path.
- Added runtime regression tests:
  - `tests/test_qa_fetch_runtime.py`
  - Added assertions that arbitration fields fail fast with `ValueError` in `fetch_request` and `fetch_request.kwargs`.
- Updated SSOT status writeback:
  - `docs/12_workflows/skeleton_ssot_v1.yaml`
  - `G95` and `QF-011` marked implemented.
  - `CL_FETCH_095` marked implemented.
  - `QF-011` requirement trace maps to `G95` under `CL_FETCH_095`.

### Acceptance Record
- `python3 scripts/check_docs_tree.py`
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
- `rg -n "G95|QF-011" docs/12_workflows/skeleton_ssot_v1.yaml`
