# Phase G220: Requirement Gap Closure (WV-002)

## Goal
- Close requirement gap `WV-002` from `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md:8`.

## Requirements
- Requirement ID: WV-002
- Owner Track: skeleton
- Clause: Quant‑EAM Whole View Framework（v0.5‑draft / Fetch‑Integrated Mainline） / CHANGELOG（v0.4 → v0.5 的核心变化）

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
### 1) Execution Strategy
- Perform requirement-gap SSOT writeback only.
- Keep scope documentation-only and constrained to allowed paths.
- Anchor `WV-002` closure to explicit SSOT goal linkage while preserving existing
  requirement dependency ordering.

### 2) Concrete Writeback
- Add `goal_checklist` entry `G220` in `docs/12_workflows/skeleton_ssot_v1.yaml`
  with `status_now: implemented`, `track: skeleton`, and task-scoped
  `allowed_paths`/`still_forbidden`.
- Update `requirements_trace_v1` entry `WV-002` in
  `docs/12_workflows/skeleton_ssot_v1.yaml` from `planned` to `implemented`,
  mapped to `G220` with `acceptance_verified: true`.
- Preserve capability cluster roll-up in
  `docs/12_workflows/skeleton_ssot_v1.yaml` with `CL_LEGACY_CORE` including
  `G220` and `latest_phase_id: G220`.

### 3) Acceptance
- `python3 scripts/check_docs_tree.py`
- `rg -n "G220|WV-002" docs/12_workflows/skeleton_ssot_v1.yaml`

## Execution Record
- Date: 2026-02-14.
- Verified SSOT goal state:
  - `goal_checklist` includes `G220` with `status_now: implemented`.
- Verified SSOT requirement trace state:
  - `requirements_trace_v1` entry `WV-002` has `status_now: implemented`.
  - `requirements_trace_v1` entry `WV-002` maps to `G220`.
- Verified capability cluster roll-up:
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` includes `G220`.
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` has `latest_phase_id: G220`.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `rg -n "G220|WV-002" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
