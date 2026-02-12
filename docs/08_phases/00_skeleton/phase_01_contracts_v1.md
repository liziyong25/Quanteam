# Phase-01: Contracts v1 (Cross-Module I/O Baseline)

## 1) 目标（Goal）

- Land v1 versioned contracts (schemas + examples) as the SSOT for cross-module I/O.
- Provide a local validator CLI and unit tests to enforce contracts correctness without any runtime network dependency.

## 2) 背景（Background）

Without contracts SSOT, modules drift:

- Agents emit ad-hoc payloads that cannot be replayed.
- Kernel/Runner/UI disagree on artifact names and required fields.
- PASS/FAIL/Registry decisions become non-auditable (no evidence chain to dossier artifacts).

## 3) 范围（Scope）

### In Scope

- `contracts/*.json` (draft 2020-12) for: Blueprint, Signal DSL, Variable Dictionary, Calc Trace Plan, RunSpec, Dossier Manifest
- `contracts/examples/*_{ok,bad}.json` for each schema
- Python validator: `python -m quant_eam.contracts.validate <json_path>`
- Unit tests validating all examples
- Docs: `docs/03_contracts/*` + index

### Out of Scope

- No compiler/runner/kernel/gates/UI implementation
- No policies content (policies are referenced by id only)
- No strategy effectiveness evaluation (contracts define structure only)

## 4) 实施方案（Implementation Plan）

- Use JSON Schema draft 2020-12 with discriminators (`schema_version` / `dsl_version` const).
- Use `$id` for each schema and local registry-based `$ref` resolution to avoid network fetches.
- Enforce hard boundaries in schema where possible:
  - cost_model must be a policy reference (`ref_policy=true`)
  - dossier manifest is append-only (`append_only=true`)
  - signal variables must have `alignment.lag_bars >= 1`

## 5) 编码内容（Code Deliverables）

- Schemas: `contracts/*.json`
- Examples: `contracts/examples/*.json`
- Validator: `src/quant_eam/contracts/validate.py`
- Tests: `tests/test_contracts_validate.py`

## 6) 文档编写（Docs Deliverables）

- Index: `docs/03_contracts/contracts_index.md`
- Per-contract docs:
  - `docs/03_contracts/blueprint_v1.md`
  - `docs/03_contracts/signal_dsl_v1.md`
  - `docs/03_contracts/variable_dictionary_v1.md`
  - `docs/03_contracts/calc_trace_plan_v1.md`
  - `docs/03_contracts/run_spec_v1.md`
  - `docs/03_contracts/dossier_v1.md`

## 7) 验收标准（Acceptance Criteria / DoD）

### 必须可执行的验收命令

- Build (no `up` required):
  - `docker compose build api worker`
- Tests:
  - `docker compose run --rm api pytest -q tests`
- Contract validation:
  - `docker compose run --rm api python -m quant_eam.contracts.validate contracts/examples/blueprint_ok.json`
  - `docker compose run --rm api python -m quant_eam.contracts.validate contracts/examples/run_spec_ok.json`
  - `docker compose run --rm api python -m quant_eam.contracts.validate contracts/examples/dossier_ok.json`
  - `docker compose run --rm api python -m quant_eam.contracts.validate contracts/examples/blueprint_bad.json` (exit != 0)
  - `docker compose run --rm api python -m quant_eam.contracts.validate contracts/examples/signal_dsl_bad.json` (exit != 0)

### 预期产物（Artifacts）

- Contracts JSON files under `contracts/`
- Examples under `contracts/examples/`

## 8) 完成记录（Execution Log）

- Start Date: 2026-02-09 (Asia/Taipei)
- End Date: 2026-02-09 (Asia/Taipei)
- PR/Commit: unknown (repo is not a git repository; `git rev-parse --short HEAD` fails)
- Notes:
  - Added v1 schemas + ok/bad examples
  - Added validator CLI and tests enforcing example validity
  - Added docs/03_contracts index + per-contract pages
  - Hardening Patch (no rework):
    - Added optional top-level `extensions` to all v1 contracts for forward compatibility (without loosening core discriminators)
    - Centralized Expression AST as a single truth (`contracts/defs/expression_ast_v1.json`) and referenced via local `$ref`
    - Improved validator selection/error UX (missing discriminator = exit 1; json pointer paths in errors)
    - Added extra bad examples + tests covering selection logic and `$ref` resolution
    - Pinned pytest discovery to `tests/` via `pyproject.toml` so `pytest -q` does not collect unrelated subtree tests

## 9) 遗留问题（Open Issues）

- [ ] Add schema semantic checks beyond JSON Schema (cross-reference validation) in a future phase (compiler-side).

## 10) Codex Prompt Footer

Append `docs/_snippets/codex_phase_footer.md` to the phase task card prompt for consistency.
