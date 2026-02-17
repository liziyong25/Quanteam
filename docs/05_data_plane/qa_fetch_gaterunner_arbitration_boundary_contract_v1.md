# QA Fetch GateRunner Arbitration Boundary Contract v1

## Purpose

Close `QF-011` as an executable boundary: `qa_fetch` runtime is a fetch executor and evidence emitter, not a strategy-validity arbiter.

## Boundary Rule

- `qa_fetch.runtime.execute_fetch_by_intent(...)` and `qa_fetch.runtime.execute_fetch_by_name(...)` MUST NOT execute or accept strategy-validity verdict payloads.
- PASS/FAIL strategy validity arbitration MUST remain GateRunner-only.

## Runtime Guard

`qa_fetch` runtime MUST reject payloads when any of the following fields appear with non-null values in:
- `fetch_request`
- `fetch_request.intent`
- `fetch_request.kwargs`
- `intent.extra_kwargs`

Blocked GateRunner-only arbitration fields:
- `strategy_verdict`
- `strategy_validity`
- `strategy_is_valid`
- `strategy_valid`
- `gate_verdict`
- `gate_result`
- `gate_results`
- `gate_status`
- `gate_pass_fail`

## Failure Contract

- Guard failure raises `ValueError`.
- Error message MUST identify payload location and blocked field list.
- Fetch execution MUST NOT start after guard failure.

## Compatibility

- Existing valid fetch requests remain unchanged.
- This guard is additive and deterministic.
