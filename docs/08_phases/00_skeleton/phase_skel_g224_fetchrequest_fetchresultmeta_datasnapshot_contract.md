# Phase G224: Requirement Gap Closure (WV-004)

## Goal
- Close requirement gap `WV-004` from `Quant‑EAM Whole View Framework.md（v0.5‑draft）.md:10`.

## Requirements
- Requirement ID: WV-004
- Owner Track: skeleton
- Clause: 引入 **FetchRequest / FetchResultMeta / DataSnapshot** 的 contract 体系（版本化）。

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
- Anchor `WV-004` closure to existing versioned data-plane contract docs
  (`docs/05_data_plane/agents_plane_data_contract_v1.md`,
  `docs/05_data_plane/data_contracts_v1.md`,
  `docs/05_data_plane/snapshot_catalog_v1.md`) without modifying `contracts/**`.

### 2) Concrete Writeback
- Add `goal_checklist` entry `G224` in `docs/12_workflows/skeleton_ssot_v1.yaml`
  with `status_now: implemented`, `track: skeleton`, and task-scoped
  `allowed_paths`/`still_forbidden`.
- Update `requirements_trace_v1` entry `WV-004` in
  `docs/12_workflows/skeleton_ssot_v1.yaml` from `planned` to `implemented`,
  mapped to `G224` with `acceptance_verified: true`.
- Update capability cluster roll-up in `docs/12_workflows/skeleton_ssot_v1.yaml`
  so `CL_LEGACY_CORE` includes `G224` and has `latest_phase_id: G224`.

### 3) Acceptance
- `python3 scripts/check_docs_tree.py`
- `rg -n "G224|WV-004" docs/12_workflows/skeleton_ssot_v1.yaml`

## Execution Record
- Date: 2026-02-14.
- Verified SSOT goal state:
  - `goal_checklist` includes `G224` with `status_now: implemented`.
- Verified SSOT requirement trace state:
  - `requirements_trace_v1` entry `WV-004` has `status_now: implemented`.
  - `requirements_trace_v1` entry `WV-004` maps to `G224`.
- Verified capability cluster roll-up:
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` includes `G224`.
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` has `latest_phase_id: G224`.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `rg -n "G224|WV-004" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
