# Phase Fetch G62: Probe Evidence Quartet Enforcement

## 1) Goal
Implement fetch probe/runtime enforcement for the evidence quartet so fetch runs always produce contract-aligned auditable artifacts for review.

## 2) Requirements
- MUST enforce quartet evidence outputs and deterministic missing-field failure semantics.
- MUST keep probe/runtime evidence paths stable for machine checks.
- MUST preserve intent-priority semantics for planning metadata.
- SHOULD keep backward compatibility for existing probe summary consumers.

## 3) Architecture & Interfaces
- Inputs:
  - Runtime/probe execution outputs under `jobs/<job_id>/outputs/fetch/`
  - `src/quant_eam/qa_fetch/probe.py`
  - `scripts/run_qa_fetch_probe_v3.py`
- Outputs:
  - Enforced quartet evidence behavior with regression tests
  - `docs/08_phases/10_impl_fetchdata/phase_fetch_g62_probe_evidence_quartet_enforcement.md`
- Dependencies:
  - `G59` (planned skeleton evidence spec freeze)
- Immutable constraints:
  - Append-only evidence policy, no policy mutation, no direct gate arbitration in agent/probe flow.

## 4) Out-of-scope
- New review UI pages.
- Fetch provider feature expansion.
- Non-fetch orchestration refactors.

## 5) DoD
- Executable commands:
  - `python3 scripts/check_docs_tree.py`
  - `docker compose run --rm api pytest -q tests/test_qa_fetch_probe.py tests/test_qa_fetch_registry_json.py`
- Expected artifacts:
  - `docs/08_phases/10_impl_fetchdata/phase_fetch_g62_probe_evidence_quartet_enforcement.md`
  - `artifacts/subagent_control/G62/task_card.yaml`
  - `artifacts/subagent_control/G62/workspace_before.json`

## 6) Implementation Plan
TBD by controller at execution time (implementation details decided during execution, not in spec).
