# Phase-77: Contract First for Fetch (G57)

## Goal
- Deliver Contract First for fetch mainline integration by adding versioned fetch schemas, enforcing pre-orchestrator fetch_request validation, and failing fast before agent execution when invalid.

## Scope
- Add versioned JSON schemas for fetch request and fetch result metadata.
- Add `validate_fetch_request` (and result-meta validation helper) in contracts validation module.
- Enforce validation in orchestrator before backtest/demo agent dispatch.
- On invalid fetch_request, write a structured error artifact and stop deterministically.
- Add tests covering schema/logic validation and orchestrator fail-fast behavior.

## Out-of-scope
- Any changes under `policies/**`.
- Any holdout visibility rule changes.
- Any non-fetch feature expansion.

## Interfaces
- `contracts/fetch_request_schema_v1.json`
- `contracts/fetch_result_meta_schema_v1.json`
- `src/quant_eam/contracts/validate.py::validate_fetch_request`
- `src/quant_eam/contracts/validate.py::validate_fetch_result_meta`
- `src/quant_eam/orchestrator/workflow.py` fetch_request pre-dispatch validation gate

## Fail-fast Rule
- If fetch_request is present and invalid, orchestrator must fail before invoking `backtest_agent_v1` or `demo_agent_v1`.
- The failure must be persisted as a structured artifact under job outputs (fetch namespace) and surfaced in job events.

## DoD
- `python3 scripts/check_docs_tree.py` exits `0`.
- `pytest -q` does not increase failure count versus baseline in this environment.
- Fetch schemas exist and are covered by tests.
- Invalid fetch_request is rejected before agent execution, with structured error artifact evidence.
- Subagent packet for `phase_77` passes validator.

## Acceptance Commands
- `python3 scripts/check_docs_tree.py`
- `pytest -q`
- `python3 scripts/check_subagent_packet.py --phase-id phase_77`

## Subagent Control Packet
- `artifacts/subagent_control/phase_77/task_card.yaml`
- `artifacts/subagent_control/phase_77/workspace_before.json`
- `artifacts/subagent_control/phase_77/workspace_after.json`
- `artifacts/subagent_control/phase_77/executor_report.yaml`
- `artifacts/subagent_control/phase_77/acceptance_run_log.jsonl`
- `artifacts/subagent_control/phase_77/validator_report.yaml`

## Execution Log
- 2026-02-12: Implemented contract-first fetch schemas, validator entrypoints, orchestrator pre-dispatch fail-fast, and tests under allowed paths.
