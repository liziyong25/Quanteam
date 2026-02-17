# Phase G120: Requirement Gap Closure (WV-020)

## Goal
- Close requirement gap `WV-020` from `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md:39`.

## Requirements
- Requirement ID: WV-020
- Owner Track: skeleton
- Clause: PASS/FAIL/入库晋升必须引用 Dossier artifacts；纯文本意见无效。

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
- Anchor WV-020 closure to existing SSOT semantics: PASS/FAIL/promotion decisions
  are valid only when grounded in dossier artifacts, not free-text opinions.

### 2) Concrete Writeback
- Add `goal_checklist` entry `G120` in `docs/12_workflows/skeleton_ssot_v1.yaml`
  with `status_now: implemented`.
- Update `requirements_trace_v1` entry `WV-020` in `docs/12_workflows/skeleton_ssot_v1.yaml`
  from `planned` to `implemented`, and map it to `G120`.
- Update capability cluster roll-up in `docs/12_workflows/skeleton_ssot_v1.yaml`
  so `CL_LEGACY_CORE` includes `G120` and points `latest_phase_id` to `G120`.

### 3) Acceptance
- `python3 scripts/check_docs_tree.py`
- `rg -n "G120|WV-020" docs/12_workflows/skeleton_ssot_v1.yaml`

## Execution Record
- Date: 2026-02-14.
- Verified SSOT goal state:
  - `goal_checklist` includes `G120` with `status_now: implemented`.
- Verified SSOT requirement trace state:
  - `requirements_trace_v1` entry `WV-020` has `status_now: implemented`.
  - `requirements_trace_v1` entry `WV-020` maps to `G120`.
- Verified capability cluster roll-up:
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` includes `G120`.
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` has `latest_phase_id: G120`.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `rg -n "G120|WV-020" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
- Revalidated on 2026-02-14 in codex_cli_subagent rerun; grep anchors include:
  `3085:- id: G120`, `5315:- req_id: WV-020`, and `10230:  latest_phase_id: G120`.
