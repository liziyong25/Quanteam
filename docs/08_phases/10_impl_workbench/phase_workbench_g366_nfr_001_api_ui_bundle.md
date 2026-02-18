# Phase G366: Requirement Gap Closure (WB-022/WB-023/WB-024/WB-025)

## Goal
- Close requirement gap bundle `WB-022/WB-023/WB-024/WB-025` from `docs/00_overview/workbench_ui_productization_v1.md:74`.

## Requirements
- Requirement IDs: WB-022/WB-023/WB-024/WB-025
- Owner Track: impl_workbench
- Clause[WB-022]: NFR-001 不破坏现有 API/UI 行为。
- Clause[WB-023]: NFR-002 兼容现有 job/event append-only 语义。
- Clause[WB-024]: NFR-003 对外结果可在单页及时刷新（轮询或 SSE）。
- Clause[WB-025]: NFR-004 对同一会话动作幂等（重复点击不会破坏状态）。

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.
- Bundling criterion: same owner track + same source document + same parent requirement + near-adjacent source lines.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Dependency Validation (G358)
- Confirm `G358` is `implemented` in `docs/12_workflows/skeleton_ssot_v1.yaml` and treat its API/UI contract as frozen baseline.
- Keep existing contract surface unchanged for MVP and workbench routes:
  - `WORKBENCH_ROUTE_INTERFACE_V43`
  - `WORKBENCH_ENDPOINT_SCHEMA_VERSIONS`
  - `/ui/jobs/idea` create flow and traversal guard behavior covered by targeted pytest.

## Scope Guard
- This phase closes only `WB-022/WB-023/WB-024/WB-025`.
- Do not modify `contracts/**`, `policies/**`, or expand Holdout visibility.
- Keep workbench behavior additive and backward compatible; no route removals or response-shape breaks.

## Implementation Plan
1. Baseline/freeze validation:
   - Run MVP targeted regression before and after changes to ensure NFR-001 compatibility.
   - Keep route inventory and schema version constants stable.
2. NFR-002 + NFR-004 implementation:
   - Preserve append-only `events.jsonl` semantics.
   - Add same-session action idempotency replay guards for mutable workbench actions (continue/fetch-probe/draft apply/rollback/rerun) keyed by `idempotency_key`.
3. NFR-003 implementation:
   - Keep polling/SSE API contract unchanged.
   - Add single-page timely refresh on `/ui/workbench/{session_id}` via lightweight event polling and page refresh on new events.
4. Verification/tests:
   - Add focused regression tests for idempotency replay + append-only event count stability and polling response shape.
5. SSOT + evidence writeback:
   - Add `G366` goal metadata in SSOT and map `WB-022..WB-025` to `implemented`.
   - Record acceptance command outputs and packet evidence under `artifacts/subagent_control/G366/`.
