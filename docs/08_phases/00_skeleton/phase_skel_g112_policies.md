# Phase G112: Requirement Gap Closure (WV-015)

## Goal
- Close requirement gap `WV-015` from `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md:32`.

## Requirements
- Requirement ID: WV-015
- Owner Track: skeleton
- Clause: **Policies 只读**

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
- Perform requirement-gap writeback only.
- Keep scope documentation-only and limited to allowed paths.
- Anchor WV-015 closure to existing governance semantics already represented in SSOT:
  policies are read-only and runtime planning references policy IDs without mutating
  policy sources.

### 2) Concrete Writeback
- Add `goal_checklist` entry `G112` in `docs/12_workflows/skeleton_ssot_v1.yaml` with
  `status_now: implemented`.
- Update `requirements_trace_v1` entry `WV-015` in `docs/12_workflows/skeleton_ssot_v1.yaml`
  from `planned` to `implemented`, and map it to `G112`.
- Update capability cluster roll-up in `docs/12_workflows/skeleton_ssot_v1.yaml` so
  `CL_LEGACY_CORE` includes `G112` and points `latest_phase_id` to `G112`.

### 3) Acceptance
- `python3 scripts/check_docs_tree.py`
- `rg -n "G112|WV-015" docs/12_workflows/skeleton_ssot_v1.yaml`

## Execution Record
- Date: 2026-02-13.
- Verified SSOT goal state:
  - `goal_checklist` includes `G112` with `status_now: implemented`.
- Verified SSOT requirement trace state:
  - `requirements_trace_v1` entry `WV-015` has `status_now: implemented`.
  - `requirements_trace_v1` entry `WV-015` maps to `G112`.
- Verified capability cluster roll-up:
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` includes `G112`.
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` has `latest_phase_id: G112`.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `rg -n "G112|WV-015" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
