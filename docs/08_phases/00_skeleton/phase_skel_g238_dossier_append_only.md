# Phase G238: Requirement Gap Closure (WV-011)

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
- Perform requirement-gap SSOT writeback only.
- Keep scope documentation-only and constrained to allowed paths.
- Anchor `WV-011` closure to append-only Dossier evidence production for
  backtest/diagnostics outputs.

### 2) Concrete Writeback
- Add `goal_checklist` entry `G238` in `docs/12_workflows/skeleton_ssot_v1.yaml`
  with `status_now: implemented`, `track: skeleton`, and task-scoped
  `allowed_paths`/`still_forbidden`.
- Update `requirements_trace_v1` entry `WV-011` in
  `docs/12_workflows/skeleton_ssot_v1.yaml` from `planned` to `implemented`,
  mapped to `G238` with `acceptance_verified: true`.
- Update capability cluster roll-up in `docs/12_workflows/skeleton_ssot_v1.yaml`
  so `CL_LEGACY_CORE` includes `G238`, removes closed requirement `WV-011` from
  pending requirement IDs, and sets `latest_phase_id: G238`.

### 3) Acceptance
- `python3 scripts/check_docs_tree.py`
- `rg -n "G238|WV-011" docs/12_workflows/skeleton_ssot_v1.yaml`

## Execution Record
- Date: 2026-02-14.
- Verified SSOT goal state:
  - `goal_checklist` includes `G238` with `status_now: implemented`.
- Verified SSOT requirement trace state:
  - `requirements_trace_v1` entry `WV-011` has `status_now: implemented`.
  - `requirements_trace_v1` entry `WV-011` maps to `G238`.
- Verified capability cluster roll-up:
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` includes `G238`.
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` no longer lists `WV-011` in
    pending requirement IDs.
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` has `latest_phase_id: G238`.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `rg -n "G238|WV-011" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
