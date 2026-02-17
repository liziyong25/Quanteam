# Phase Fetch G77: Fetch DataAccessFacade Enforcement and No-Direct-Import Guard

## 1) Goal
Route agent-side fetch execution through qa_fetch facade and add regression guards against direct runtime/provider execution imports.

## 2) Requirements
- MUST ensure demo/backtest fetch execution calls are imported from `quant_eam.qa_fetch.facade`.
- MUST add facade dispatch helper for request-shaped fetch execution.
- MUST add tests that fail if agent fetch path imports runtime execution calls directly.
- MUST NOT modify `contracts/**`, `policies/**`, or holdout visibility scope.

## 3) Architecture & Interfaces
- Inputs:
  - `docs/05_data_plane/qa_fetch_dataaccess_facade_boundary_v1.md`
  - `src/quant_eam/agents/demo_agent.py`
  - `src/quant_eam/agents/backtest_agent.py`
- Outputs:
  - `src/quant_eam/qa_fetch/facade.py`
  - agent import-path enforcement
  - guard regression tests

## 4) Out-of-scope
- Provider/runtime algorithm changes.
- Contract schema changes.
- UI route changes.

## 5) DoD
- `python3 scripts/check_docs_tree.py`
- `docker compose run --rm api pytest -q tests/test_qa_fetch_agent_integration.py tests/test_qa_fetch_autosymbols_planner_phase75.py tests/test_qa_fetch_dataaccess_facade_phase77.py`

## 6) Implementation Plan
### 6.1 Execution Strategy
- Add `qa_fetch.facade` as thin runtime wrapper exposing `execute_fetch_by_name`, `execute_fetch_by_intent`, and request-shaped dispatch helper.
- Switch demo/backtest agents to import execution calls from facade module.
- Add guard tests verifying:
  - facade dispatch for function/intent request shapes;
  - agent modules import facade execution calls and do not import runtime execution calls directly.

### 6.2 Controller Execution Record
- Published packet task card: `artifacts/subagent_control/G77/task_card.yaml`.
- Added facade module:
  - `src/quant_eam/qa_fetch/facade.py`
- Updated agent fetch import boundaries:
  - `src/quant_eam/agents/demo_agent.py`
  - `src/quant_eam/agents/backtest_agent.py`
- Added guard tests:
  - `tests/test_qa_fetch_dataaccess_facade_phase77.py`

### 6.3 Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `docker compose run --rm api pytest -q tests/test_qa_fetch_agent_integration.py tests/test_qa_fetch_autosymbols_planner_phase75.py tests/test_qa_fetch_dataaccess_facade_phase77.py` passed.
- `python3 scripts/check_subagent_packet.py --phase-id G77` passed via packet finish lifecycle.
