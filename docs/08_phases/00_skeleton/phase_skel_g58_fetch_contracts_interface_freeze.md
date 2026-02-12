# Phase Skeleton G58: QA Fetch Contracts Interface Freeze

## 1) Goal
Define and freeze the fetch contracts boundary for `fetch_request`/`intent` and fetch evidence metadata so later implementation phases can execute without changing contract semantics.

## 2) Requirements
- MUST keep deterministic arbitration boundary: only GateRunner decides PASS/FAIL; fetch is evidence input only.
- MUST enforce contract-first governance for fetch request/response metadata, with explicit schema versioning and validation entrypoints.
- MUST keep agents on runtime/facade boundary; agents SHOULD express data need via intent semantics rather than provider-specific calls.
- SHOULD preserve policy read-only and holdout isolation constraints.

## 3) Architecture & Interfaces
- Inputs:
  - `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md`
  - `docs/05_data_plane/qa_fetch_registry_v1.json`
  - `docs/05_data_plane/qa_fetch_resolver_registry_v1.md`
- Outputs:
  - `docs/08_phases/00_skeleton/phase_skel_g58_fetch_contracts_interface_freeze.md`
  - SSOT goal entry for G58 with frozen interface constraints
- Dependencies:
  - `G57` (implemented) as current contract-first baseline
- Immutable constraints:
  - No policy mutation, no holdout visibility expansion, no agent-side provider direct access.

## 4) Out-of-scope
- Runtime code changes under `src/**`.
- Contract JSON schema implementation edits.
- UI route/template implementation.

## 5) DoD
- Executable commands:
  - `python3 scripts/check_docs_tree.py`
  - `rg -n "G58|phase_skel_g58|track: skeleton" docs/12_workflows/skeleton_ssot_v1.yaml`
- Expected artifacts:
  - `docs/08_phases/00_skeleton/phase_skel_g58_fetch_contracts_interface_freeze.md`
  - `docs/12_workflows/skeleton_ssot_v1.yaml`

## 6) Implementation Plan
TBD by controller at execution time (implementation details decided during execution, not in spec).
