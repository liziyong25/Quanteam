# Phase G179: Requirement Gap Closure (QF-088)

## Goal
- Close requirement gap `QF-088` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:151`.

## Requirements
- Requirement ID: QF-088
- Owner Track: impl_fetchdata
- Clause: 任何缺失 fetch evidence / snapshot manifest 的 run 必须 gate fail（不可默默跳过）。

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
### 1) Runtime gate requirement execution
- Add explicit QF-088 runtime anchor:
  - `src/quant_eam/qa_fetch/runtime.py::FETCH_EVIDENCE_SNAPSHOT_MANIFEST_GATE_FAIL_RULE`
- Add deterministic run-gate helper and enforcement entrypoint:
  - `evaluate_fetch_evidence_snapshot_manifest_gate(...)`
  - `enforce_fetch_evidence_snapshot_manifest_gate(...)`
- Gate semantics:
  - Missing required fetch evidence files (`fetch_request.json`, `fetch_result_meta.json`,
    `fetch_preview.csv`, `fetch_steps_index.json`) yields `gate_status=fail`.
  - Missing snapshot manifest yields `gate_status=fail`.
  - Enforcement path raises explicit `ValueError` instead of silently skipping.

### 2) Regression coverage
- Add focused runtime tests:
  - `test_runtime_fetch_evidence_snapshot_manifest_gate_fail_rule_anchor_matches_qf_088_clause`
  - `test_evaluate_fetch_evidence_snapshot_manifest_gate_passes_with_all_artifacts`
  - `test_enforce_fetch_evidence_snapshot_manifest_gate_fails_when_artifacts_missing`

### 3) SSOT writeback
- Mark `G179` as `implemented`.
- Mark `QF-088` as `implemented`.
- Mark `CL_FETCH_179` as `implemented`.
- Mark all interface mapping entries with `impl_requirement_id: QF-088` as `implemented`.

## Execution Record
- Date: 2026-02-14.
- Scope outcome:
  - QF-088 now has explicit runtime gate-fail semantics with deterministic verdict output.
  - Missing fetch evidence or missing snapshot manifest no longer has a silent path when gate enforcement is invoked.
  - SSOT status writeback records `G179`/`QF-088`/`CL_FETCH_179` as implemented.
