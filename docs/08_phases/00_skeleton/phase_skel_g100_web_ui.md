# Phase G100: Requirement Gap Closure (WV-009)

## Goal
- Close requirement gap `WV-009` from `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md:21`.

## Requirements
- Requirement ID: WV-009
- Owner Track: skeleton
- Clause: 用户只在 **Web UI** 输入想法与约束，并在多个审阅点确认证据（不看源码）。

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
- Anchor WV-009 closure to existing UI-first governance semantics in SSOT (`intent`,
  `dossier_is_ui_ssot`, and requirement trace linkage), without touching contracts/policies/runtime
  code.

### 2) Concrete Writeback
- Add `goal_checklist` entry `G100` in `docs/12_workflows/skeleton_ssot_v1.yaml` with
  `status_now: implemented`.
- Update `requirements_trace_v1` entry `WV-009` in `docs/12_workflows/skeleton_ssot_v1.yaml`
  from `planned` to `implemented`, and map it to `G100`.
- Update capability cluster roll-up in `docs/12_workflows/skeleton_ssot_v1.yaml` so
  `CL_LEGACY_CORE` includes `G100` and points `latest_phase_id` to `G100`.

### 3) Acceptance
- `python3 scripts/check_docs_tree.py`
- `rg -n "G100|WV-009" docs/12_workflows/skeleton_ssot_v1.yaml`

## Execution Record
- Date: 2026-02-13.
- Verified SSOT goal state:
  - `goal_checklist` includes `G100` with `status_now: implemented`.
- Verified SSOT requirement trace state:
  - `requirements_trace_v1` entry `WV-009` has `status_now: implemented`.
  - `requirements_trace_v1` entry `WV-009` maps to `G100`.
- Verified capability cluster roll-up:
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` includes `G100`.
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` has `latest_phase_id: G100`.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `rg -n "G100|WV-009" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
