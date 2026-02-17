# Phase G234: Requirement Gap Closure (WV-009)

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
- Perform requirement-gap SSOT writeback only.
- Keep scope documentation-only and constrained to allowed paths.
- Anchor `WV-009` closure to the Web-UI-only interaction requirement and
  review-checkpoint evidence confirmation path.

### 2) Concrete Writeback
- Add `goal_checklist` entry `G234` in `docs/12_workflows/skeleton_ssot_v1.yaml`
  with `status_now: implemented`, `track: skeleton`, and task-scoped
  `allowed_paths`/`still_forbidden`.
- Update `requirements_trace_v1` entry `WV-009` in
  `docs/12_workflows/skeleton_ssot_v1.yaml` from `planned` to `implemented`,
  mapped to `G234` with `acceptance_verified: true`.
- Update capability cluster roll-up in `docs/12_workflows/skeleton_ssot_v1.yaml`
  so `CL_LEGACY_CORE` includes `G234`, removes closed requirement `WV-009` from
  pending requirement IDs, and sets `latest_phase_id: G234`.

### 3) Acceptance
- `python3 scripts/check_docs_tree.py`
- `rg -n "G234|WV-009" docs/12_workflows/skeleton_ssot_v1.yaml`

## Execution Record
- Date: 2026-02-14.
- Verified SSOT goal state:
  - `goal_checklist` includes `G234` with `status_now: implemented`.
- Verified SSOT requirement trace state:
  - `requirements_trace_v1` entry `WV-009` has `status_now: implemented`.
  - `requirements_trace_v1` entry `WV-009` maps to `G234`.
- Verified capability cluster roll-up:
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` includes `G234`.
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` no longer lists `WV-009` in
    pending requirement IDs.
  - `capability_clusters_v1` entry `CL_LEGACY_CORE` has `latest_phase_id: G234`.

## Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `rg -n "G234|WV-009" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
