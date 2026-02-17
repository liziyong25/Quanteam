# Phase G166: Requirement Gap Closure (QF-077)

## Goal
- Close requirement gap `QF-077` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:134`.

## Requirements
- Requirement ID: QF-077
- Owner Track: impl_fetchdata
- Clause: 每一步必须落 step evidence（可审计）。

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
1. Runtime requirement anchor:
   - Add a QF-077 clause anchor constant in `src/quant_eam/qa_fetch/runtime.py`:
     `AUTO_SYMBOLS_STEP_EVIDENCE_RULE = "emit_step_evidence_for_each_planner_step"`.
2. Regression coverage:
   - Add `tests/test_qa_fetch_runtime.py::test_runtime_auto_symbols_step_evidence_rule_anchor_matches_qf_077_clause`.
   - Strengthen auto-symbol planner evidence tests to assert each planner step emits
     `request_path`, `result_meta_path`, and `preview_path` artifacts, with deterministic
     step filename templates.
3. SSOT alignment:
   - Mark `G166`, `QF-077`, and `CL_FETCH_166` as `implemented` in
     `docs/12_workflows/skeleton_ssot_v1.yaml`.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py` passed (`85 passed`).
- `rg -n "G166|QF-077" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
