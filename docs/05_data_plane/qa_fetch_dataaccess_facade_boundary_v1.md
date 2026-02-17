# QA Fetch DataAccessFacade Boundary Contract v1

## Purpose

Freeze the single data access channel for agent-side fetch execution: agents MUST call the qa_fetch facade entry points instead of runtime internals or provider modules.

## Boundary Rule

- Allowed agent-facing fetch entry points:
  - `quant_eam.qa_fetch.facade.execute_fetch_request(...)`
  - `quant_eam.qa_fetch.facade.execute_fetch_by_name(...)`
  - `quant_eam.qa_fetch.facade.execute_fetch_by_intent(...)`
- Agent fetch flows MAY keep planner logic (`list -> sample -> day`) in agent layer, but each executable fetch step MUST go through facade entry points.

## Forbidden Access Paths

- Direct agent imports from `quant_eam.qa_fetch.runtime` for execution calls.
- Direct agent imports from provider modules (including `mongo_fetch/mysql_fetch` implementations).
- Any direct DB/provider calls from agent code path.

## Audit/Guard Requirements

- Repository MUST include guard tests that fail when agent fetch path imports runtime/provider execution directly.
- Existing fetch evidence behavior (quartet + steps index) MUST remain unchanged by facade routing.

## Compatibility

- Facade APIs are thin wrappers over current runtime APIs.
- Existing runtime behavior and fetch evidence contracts remain source-of-truth.
