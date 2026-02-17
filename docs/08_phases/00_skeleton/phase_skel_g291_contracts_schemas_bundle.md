# Phase G291: Requirement Gap Closure (WV-045/WV-046/WV-047/WV-048/WV-049/WV-050)

## Goal
- Close requirement gap bundle `WV-045/WV-046/WV-047/WV-048/WV-049/WV-050` from `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md:226`.
- Freeze `G289` interface assumptions (`WV-044` implemented baseline) before closing `WV-045`..`WV-050`.

## Requirements
- Requirement IDs: WV-045/WV-046/WV-047/WV-048/WV-049/WV-050
- Owner Track: skeleton
- Clause[WV-045]: contracts（schemas + 校验）
- Clause[WV-046]: compiler（Blueprint → RunSpec；注入预算；合规校验）
- Clause[WV-047]: runner（执行回测，写 Dossier）
- Clause[WV-048]: gate_runner（执行 gates，写 GateResults）
- Clause[WV-049]: holdout_vault（锁箱隔离）
- Clause[WV-050]: dossier_builder（图/表/报告生成，append-only）
- Reference: docs/05_data_plane/wv045_wv050_kernel_bundle_v1.md
- Reference: docs/05_data_plane/wv045_wv050_kernel_bundle_fixtures_v1.json

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.
- Bundling criterion: same owner track + same source document + same parent requirement + near-adjacent source lines.
- Dependency frozen from `G289`:
  - `WV-044` remains implemented before `WV-045`..`WV-050` writeback.
  - Deterministic kernel boundary remains `Blueprint -> RunSpec -> Dossier -> GateResults`.
  - Holdout output remains restricted to summary-only visibility.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.
- `WV-045`..`WV-050` all map to `G291` in `requirements_trace_v1`.
- `CL_LEGACY_CORE` rollup `latest_phase_id` advances to `G291`.

## Implementation Plan
TBD by controller at execution time.
