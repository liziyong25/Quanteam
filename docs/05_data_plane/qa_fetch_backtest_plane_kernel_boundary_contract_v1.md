# QA Fetch Backtest Plane Kernel Boundary Contract v1

## Purpose

Close `QF-010` as an executable boundary: `qa_fetch` runtime is a Data Plane fetch executor only, not a strategy/backtest kernel executor.

## Boundary Rule

- `qa_fetch.runtime.execute_fetch_by_intent(...)` MUST only execute fetch payloads (intent/function + kwargs/policy).
- Strategy-logic generation and backtest-engine execution MUST stay in Backtest Plane / Deterministic Kernel components.

## Runtime Guard

`qa_fetch` runtime MUST reject payloads when any of the following fields appear with non-null values in:
- `fetch_request`
- `fetch_request.intent`
- `fetch_request.kwargs`
- `intent.extra_kwargs`

Blocked fields:
- `strategy_spec`
- `signal_dsl`
- `variable_dictionary`
- `calc_trace_plan`
- `runspec`
- `run_spec`
- `backtest_engine`
- `engine_contract`

## Failure Contract

- Guard failure raises `ValueError`.
- Error message MUST identify the payload location and blocked field list.
- No fetch execution should start after guard failure.

## Compatibility

- Existing valid fetch requests remain unchanged.
- This guard is additive and deterministic.
