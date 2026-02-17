# Phase Skeleton G70: Fetch Schema Contract Window Activation

## 1) Goal
Activate and freeze the fetch-contract exception window scope for unattended rolling execution so fetch schema evolution can proceed without expanding non-fetch contract boundaries.

## 2) Requirements
- MUST formalize the allowed fetch contract file scope and redlines in SSOT/workflow governance docs.
- MUST keep exception strictly bounded to fetch contract schemas.
- MUST keep all non-fetch `contracts/**` and all `policies/**` paths forbidden.

## 3) Architecture & Interfaces
- Inputs:
  - `docs/12_workflows/skeleton_ssot_v1.yaml`
  - `docs/12_workflows/subagent_dev_workflow_v1.md`
- Outputs:
  - governance exception window documented and active for subsequent goals

## 4) Out-of-scope
- Runtime validator behavior changes.
- Orchestrator route/state changes.
- Policy bundle changes.

## 5) DoD
- `python3 scripts/check_docs_tree.py`
- `rg -n "G70|fetch_contract_schema_scope|fetch_request_schema_v1|fetch_result_meta_schema_v1" docs/12_workflows/skeleton_ssot_v1.yaml docs/12_workflows/subagent_dev_workflow_v1.md`

## 6) Implementation Plan
### 6.1 Treaty Activation Changes
- Updated `docs/12_workflows/subagent_dev_workflow_v1.md` to persist a fetch-only contract schema exception window for unattended mode.
- Updated `docs/12_workflows/skeleton_ssot_v1.yaml` with:
  - explicit fetch-contract window enforcement guardrails under `ssot_enforcement_rules`;
  - reusable exception template `fetch_contract_schema_scope` under `whole_view_autopilot_v1.stop_condition_exception_templates`;
  - goal-scoped exceptions for `G70` and `G71` under `autopilot_stop_condition_exceptions_v1`.

### 6.2 Controller Execution Record
- Published packet task card: `artifacts/subagent_control/G70/task_card.yaml`.
- Dispatched unattended subagent lifecycle for `G70` with strict redlines:
  - forbidden: `policies/**`, holdout visibility expansion;
  - no runtime or fetch payload mutations in this governance-only goal.

### 6.3 Acceptance Record
- `python3 scripts/check_docs_tree.py` passed.
- `rg -n "G70|fetch_contract_schema_scope|fetch_request_schema_v1|fetch_result_meta_schema_v1" docs/12_workflows/skeleton_ssot_v1.yaml docs/12_workflows/subagent_dev_workflow_v1.md` passed.
- `python3 scripts/check_subagent_packet.py --phase-id G70` passed via packet runner finish lifecycle.
