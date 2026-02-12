# Phase Fetch G61: Intent Runtime Contract Alignment

## 1) Goal
Implement intent-first fetch request alignment in runtime orchestration so fetch execution remains deterministic, contract-validated, and evidence-producing.

## 2) Requirements
- MUST route agent fetch demand through runtime/facade entrypoints; no direct provider invocation from agent workflows.
- MUST validate intent-form `fetch_request` against frozen contracts before execution.
- MUST preserve deterministic error semantics and auditable failure artifacts.
- SHOULD maintain compatibility with existing registry/resolver mapping behavior.

## 3) Architecture & Interfaces
- Inputs:
  - `fetch_request.intent` payloads from orchestrator/job context
  - `src/quant_eam/qa_fetch/runtime.py`
  - `src/quant_eam/qa_fetch/resolver.py`
  - `src/quant_eam/qa_fetch/registry.py`
- Outputs:
  - Runtime-aligned fetch execution behavior and test evidence under `tests/test_qa_fetch_runtime*.py`
  - `docs/08_phases/10_impl_fetchdata/phase_fetch_g61_intent_runtime_contract_alignment.md`
- Dependencies:
  - `G27` (implemented skeleton freeze: deterministic registry/runtime sync)
- Immutable constraints:
  - Policies remain read-only; holdout boundaries unchanged; PASS/FAIL arbitration remains GateRunner-only.

## 4) Out-of-scope
- UI rendering or route additions.
- Policy/contract governance rewrites.
- New data-provider integration.

## 5) DoD
- Executable commands:
  - `python3 scripts/check_docs_tree.py`
  - `docker compose run --rm api pytest -q tests/test_qa_fetch_runtime*.py tests/test_qa_fetch_resolver.py`
- Expected artifacts:
  - `docs/08_phases/10_impl_fetchdata/phase_fetch_g61_intent_runtime_contract_alignment.md`
  - `artifacts/subagent_control/G61/task_card.yaml`
  - `artifacts/subagent_control/G61/workspace_before.json`

## 6) Implementation Plan
TBD by controller at execution time (implementation details decided during execution, not in spec).
