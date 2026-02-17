# Phase G218: Requirement Gap Closure (WV-001)

## Goal
- Close requirement gap `WV-001` from `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md:1`.

## Requirements
- Requirement ID: WV-001
- Owner Track: skeleton
- Clause: Quant‑EAM Whole View Framework（v0.5‑draft / Fetch‑Integrated Mainline）

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
- Anchor `WV-001` closure to explicit SSOT goal linkage while preserving existing
  historical mapping.

### 2) Concrete Writeback
- Add `goal_checklist` entry `G218` in `docs/12_workflows/skeleton_ssot_v1.yaml`
  with `status_now: implemented`, `track: skeleton`, and task-scoped
  `allowed_paths`/`still_forbidden`.
- Update `requirements_trace_v1` entry `WV-001` in
  `docs/12_workflows/skeleton_ssot_v1.yaml` to include `G218` in
  `mapped_goal_ids` while keeping existing `G32` linkage.
- Preserve capability cluster roll-up in
  `docs/12_workflows/skeleton_ssot_v1.yaml` with `CL_LEGACY_CORE` including
  `G218` and `latest_phase_id: G218`.

### 3) Acceptance
- `python3 scripts/check_docs_tree.py`
- `rg -n "G218|WV-001" docs/12_workflows/skeleton_ssot_v1.yaml`

## Execution Record
- Date: 2026-02-14.
- Verified SSOT goal state:
  - `goal_checklist` includes `G218` with `status_now: implemented`.
- Verified SSOT requirement trace state:
  - `requirements_trace_v1` entry `WV-001` remains `status_now: implemented`.
  - `requirements_trace_v1` entry `WV-001` maps to `G32` and `G218`.
- Verified capability cluster roll-up:
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` includes `G218`.
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` has `latest_phase_id: G218`.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `rg -n "G218|WV-001" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
