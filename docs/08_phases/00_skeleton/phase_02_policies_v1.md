# Phase-02: Policies v1 (Frozen Governance Inputs)

## 1) 目标（Goal）

- Land v1 frozen policy assets (YAML) as governed inputs to Kernel/Runner/UI.
- Provide deterministic Python loader/validator CLI + unit tests (no network IO).
- Document semantics under `docs/04_policies/`.

## 2) 背景（Background）

Without frozen policies SSOT:

- Strategies/modules drift by inlining costs/execution/risk assumptions.
- Kernel cannot enforce governance boundaries deterministically.
- UI/review cannot audit what rules were applied.

## 3) 范围（Scope）

### In Scope

- `policies/*_v1.yaml` (frozen assets) + optional `policies/examples/*_bad.yaml`
- `python -m quant_eam.policies.validate ...`
- Tests validating OK/BAD cases
- Docs under `docs/04_policies/`

### Out of Scope

- No Kernel/Runner/GateRunner implementation
- No gate algorithms (only declared gate suite structure)
- No policies content beyond v1 minimal surface

## 4) 实施方案（Implementation Plan）

- Policies are YAML with discriminator fields:
  - `policy_id` + `policy_version: "v1"` for individual policies
  - `policy_bundle_id` + `policy_version: "v1"` for bundles
- Bundle validates referential integrity against `policies/*.yaml` and forbids inline overrides.
- Validator outputs paths for failures, and is deterministic (filesystem only, no network).

## 5) 交付物（Deliverables）

- Policies:
  - `policies/execution_policy_v1.yaml`
  - `policies/cost_policy_v1.yaml`
  - `policies/asof_latency_policy_v1.yaml`
  - `policies/risk_policy_v1.yaml`
  - `policies/gate_suite_v1.yaml`
  - `policies/policy_bundle_v1.yaml`
- Tooling:
  - `src/quant_eam/policies/load.py`
  - `src/quant_eam/policies/validate.py`
- Docs:
  - `docs/04_policies/*`

## 6) 验收标准（Acceptance / DoD）

- Build:
  - `docker compose build api worker`
- Tests:
  - `EAM_UID=$(id -u) EAM_GID=$(id -g) docker compose run --rm api pytest -q`
- Validate:
  - `docker compose run --rm api python -m quant_eam.policies.validate policies/policy_bundle_v1.yaml` (OK)
  - `docker compose run --rm api python -m quant_eam.policies.validate policies/examples/policy_bundle_missing_ref_bad.yaml` (exit=2)
- Docs existence gate:
  - `python3 scripts/check_docs_tree.py`

## 7) 完成记录（Execution Log）

- Start Date: 2026-02-09 (Asia/Taipei)
- End Date: 2026-02-09 (Asia/Taipei)
- PR/Commit: unknown (repo is not a git repository; `git rev-parse --short HEAD` fails)
- Notes:
  - Added v1 frozen policy assets and a bundle as the single handle (`policy_bundle_id`)
  - Added deterministic YAML validator (referential integrity + no inline overrides)
  - Added docs/04_policies pages and tests (OK/BAD + duplicate policy_id via temp dir)
  - Hardening Patch (Phase-02B, no rework):
    - Added policy lock manifest (`policies/policy_lock_v1.json`) generation via `--write-lock` and bundle-time lock verification (anti-tamper + replay)
    - Added directory validation (`python -m quant_eam.policies.validate policies/`) with OK/INVALID summary
    - Added BAD examples for `asof_rule` and holdout output semantics, plus tests

## 8) Codex Prompt Footer

Append `docs/_snippets/codex_phase_footer.md` to the phase task card prompt for consistency.
