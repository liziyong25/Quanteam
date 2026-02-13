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
### 1. Scope Lock
- Keep this goal focused on dispatch/packet smoke for impl track readiness.
- Do not introduce business/runtime behavior change in fetch execution code.

### 2. Execution Record
- Reused existing hardened packet workflow (`task_card -> executor_report -> validator_report -> check_subagent_packet`).
- Verified acceptance command set remains docs/SSOT based and deterministic.
- Kept allowed_paths disjoint from skeleton preflight guard scope.

### 3. Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `rg -n "G65|phase_fetch_g65|track: impl_fetchdata" docs/12_workflows/skeleton_ssot_v1.yaml` passed.
