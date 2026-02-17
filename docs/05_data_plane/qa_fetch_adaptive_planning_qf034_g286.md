# QA Fetch Adaptive Planning (G286 / QF-034)

## Traceability
- Goal ID: `G286`
- Requirement ID: `QF-034`
- Source clause: `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:65`
- Dependency baseline: `G283` (`QF-033`) must be implemented first.

## G283 Interface Freeze
G286 keeps the G283 runtime interfaces unchanged:
- `execute_fetch_by_intent(...)`
- `execute_fetch_by_name(...)`
- `load_function_registry(...)`
- `load_smoke_window_profile(...)`
- Golden query drift contract fields in `fetch_result_meta` remain unchanged.

The adaptive logic is implemented as internal execution planning inside
`execute_fetch_by_name(...)` and does not change external call signatures.

## Adaptive Planning Rules (Deterministic)
The runtime applies adaptive planning only when adaptive profile fields are present
for the target function in `qa_fetch_smoke_window_profile_v1.json`.

### Source choice and fallback
- Primary source is resolved from function registry metadata.
- Optional profile key `adaptive_source_order` allows explicit source order.
- Optional profile key `enable_source_fallback=true` appends alternate engine
  probes (`mongo_fetch`, `mysql_fetch`) in deterministic order.
- Fallback to next source is allowed for:
  - `blocked_source_missing`
  - `pass_empty` when `policy.on_no_data != error`

### Query window adaptation
- Optional profile key `adaptive_window_lookback_days` defines end-aligned
  fallback windows.
- Runtime keeps the original window first, then appends narrower windows
  deterministically.
- Adapted windows are only generated when both `start` and `end` are parseable.

### Terminal semantics
- `pass_has_data`: returns immediately.
- `pass_empty`: may continue to next adaptive candidate unless
  `policy.on_no_data=error`.
- `error_runtime`: terminal unless classification allows adaptive continuation.

## Evidence and audit
When adaptive planning produces multiple candidates, request evidence includes an
`adaptive_plan` section with source/window candidates and rule identifiers.
This keeps fallback behavior reviewable without changing existing evidence bundle
paths.
