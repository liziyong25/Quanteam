# Phase Fetch G75: Auto-Symbols Multi-Step Planner Execution

## 1) Goal
Implement deterministic `auto_symbols` list-sample-day planner execution and append-only multi-step fetch evidence emission.

## 2) Requirements
- MUST trigger planner when `auto_symbols=true` and explicit symbols are missing.
- MUST emit step evidence for list/sample/day sequence.
- MUST preserve canonical fetch quartet for final day step.
- MUST NOT modify `contracts/**`, `policies/**`, or holdout visibility scope.

## 3) Architecture & Interfaces
- Inputs:
  - `docs/05_data_plane/qa_fetch_autosymbols_planner_contract_v1.md`
  - `src/quant_eam/agents/demo_agent.py`
  - `src/quant_eam/agents/backtest_agent.py`
  - `src/quant_eam/qa_fetch/runtime.py`
- Outputs:
  - deterministic planner execution path
  - append-only multi-step fetch evidence
  - regression tests

## 4) Out-of-scope
- New contracts or policy changes.
- Holdout behavior expansion.
- Non-fetch workflow rewrites.

## 5) DoD
- `python3 scripts/check_docs_tree.py`
- `docker compose run --rm api pytest -q tests/test_qa_fetch_runtime.py tests/test_qa_fetch_agent_integration.py tests/test_qa_fetch_autosymbols_planner_phase75.py`

## 6) Implementation Plan
### 6.1 Execution Strategy
- Extend `demo_agent`/`backtest_agent` fetch execution with deterministic auto-symbol planner:
  - trigger only when `auto_symbols=true` and explicit symbols are missing;
  - execute three ordered steps: `list` -> `sample` -> `day`;
  - preserve runtime fallback semantics on step failure.
- Extend runtime evidence writing to consume planner step records and map canonical fetch quartet to final (`day`) step outputs.
- Add regression tests for:
  - multi-step evidence canonical mapping;
  - demo/backtest planner success and failure paths.

### 6.2 Controller Execution Record
- Updated planner execution and evidence wiring in:
  - `src/quant_eam/agents/demo_agent.py`
  - `src/quant_eam/agents/backtest_agent.py`
- Runtime evidence writer already supports step-record emission and final-step canonical mapping; added multi-step regression assertion in:
  - `tests/test_qa_fetch_runtime.py`
- Added dedicated planner tests:
  - `tests/test_qa_fetch_autosymbols_planner_phase75.py`

### 6.3 Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `docker compose run --rm api pytest -q tests/test_qa_fetch_runtime.py tests/test_qa_fetch_agent_integration.py tests/test_qa_fetch_autosymbols_planner_phase75.py` passed (`15 passed`).
- `python3 scripts/check_subagent_packet.py --phase-id G75` passed via packet finish lifecycle.
