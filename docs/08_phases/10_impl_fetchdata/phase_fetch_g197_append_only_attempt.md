# Phase G197: Requirement Gap Closure (QF-103)

## Goal
- Close requirement gap `QF-103` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:178`.

## Requirements
- Requirement ID: QF-103
- Owner Track: impl_fetchdata
- Clause: 证据必须 append-only（保留历史 attempt）

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
- Enforce append-only evidence attempts in `src/quant_eam/qa_fetch/runtime.py`.
- Add deterministic tests in `tests/test_qa_fetch_runtime.py` for attempt-history retention.
- Update SSOT statuses for `G197` / `QF-103` in `docs/12_workflows/skeleton_ssot_v1.yaml`.

## Execution Notes (2026-02-14)
- `write_fetch_evidence` now writes each run into `attempt_{attempt_index:06d}` and preserves prior attempts.
- Canonical top-level evidence files remain the latest-attempt pointers for backward compatibility.
- `fetch_attempts_index.json` is maintained as append-only history index with attempt metadata.
- Runtime tests now assert QF-103 anchors and verify two consecutive writes keep both attempt bundles.
