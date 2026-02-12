# Phase Impl G65: Fetch Preflight Dispatch Packet Smoke

## Goal
- Create an impl-fetchdata planned goal with dependency-ready, disjoint allowed_paths for dry-run dispatch.

## Requirements
- Must depend on an implemented impl_fetchdata baseline goal.
- Must keep scope limited to preflight dispatch and packet smoke checks.
- Must avoid business behavior changes.

## Architecture
- Use existing check_docs_tree and subagent packet validation flow.
- Keep allowed_paths disjoint from selected skeleton goal.
- Preserve deterministic evidence outputs.

## DoD
- python3 scripts/check_docs_tree.py passes.
- rg -n "G65|phase_fetch_g65|track: impl_fetchdata" docs/12_workflows/skeleton_ssot_v1.yaml passes.
- Implementation Plan section is fixed to TBD text.

## Implementation Plan
TBD by controller at execution time.
