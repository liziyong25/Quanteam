# Phase G104: Requirement Gap Closure (WV-011)

## Goal
- Close requirement gap `WV-011` from `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md:23`.

## Requirements
- Requirement ID: WV-011
- Owner Track: skeleton
- Clause: 回测/诊断产出 **证据包（Dossier，append‑only）**。

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
- Anchor WV-011 closure to existing dossier append-only governance semantics in SSOT
  (`dossier_is_ui_ssot`, `append_only_everywhere`, and requirement trace linkage),
  without touching contracts/policies/runtime code.

### 2) Concrete Writeback
- Add `goal_checklist` entry `G104` in `docs/12_workflows/skeleton_ssot_v1.yaml` with
  `status_now: implemented`.
- Update `requirements_trace_v1` entry `WV-011` in `docs/12_workflows/skeleton_ssot_v1.yaml`
  from `planned` to `implemented`, and map it to `G104`.
- Update capability cluster roll-up in `docs/12_workflows/skeleton_ssot_v1.yaml` so
  `CL_LEGACY_CORE` includes `G104` and points `latest_phase_id` to `G104`.

### 3) Acceptance
- `python3 scripts/check_docs_tree.py`
- `rg -n "G104|WV-011" docs/12_workflows/skeleton_ssot_v1.yaml`

## Execution Record
- Date: 2026-02-13.
- Verified SSOT goal state:
  - `goal_checklist` includes `G104` with `status_now: implemented`.
- Verified SSOT requirement trace state:
  - `requirements_trace_v1` entry `WV-011` has `status_now: implemented`.
  - `requirements_trace_v1` entry `WV-011` maps to `G104`.
- Verified capability cluster roll-up:
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` includes `G104`.
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` has `latest_phase_id: G104`.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `rg -n "G104|WV-011" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
