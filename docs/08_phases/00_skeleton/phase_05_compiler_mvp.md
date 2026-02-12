# Phase-05: Compiler MVP (Blueprint -> RunSpec -> Runner)

## 1) 目标（Goal）

- Build a deterministic compiler that compiles Blueprint/DSL (contracts v1) into RunSpec (contracts v1).
- Ensure end-to-end works: compile -> runner -> dossier (dossier_schema_v1 validation passes).

## 2) 范围（Scope）

### In Scope

- `src/quant_eam/compiler/**`
- Compiler unit tests + e2e compile->run->dossier tests (offline)
- Docs under `docs/07_compiler/` + this phase log

### Out of Scope

- No gates/holdout/registry
- No agents/LLM
- No full DSL interpreter (demo buy&hold blueprint only)

## 3) 交付物（Deliverables）

- CLI: `python -m quant_eam.compiler.compile ...`
- Demo blueprint example in `contracts/examples/`

## 4) 验收（Acceptance / DoD）

- Build:
  - `docker compose build api worker`
- Tests:
  - `docker compose run --rm api pytest -q`
- Demo compile:
  - `docker compose run --rm api python -m quant_eam.compiler.compile --blueprint contracts/examples/blueprint_buyhold_demo_ok.json --snapshot-id demo_snap_001 --out /tmp/runspec_demo.json --policy-bundle policies/policy_bundle_v1.yaml`
- Docs gate:
  - `python3 scripts/check_docs_tree.py`

## 5) 完成记录（Execution Log）

- Start Date: 2026-02-09 (Asia/Taipei)
- End Date: 2026-02-09 (Asia/Taipei)
- PR/Commit: unknown (repo is not a git repository; `git rev-parse --short HEAD` fails)
- Notes:
  - Compiler validates Blueprint v1 and enforces policy_bundle_id immutability
  - Emits canonical RunSpec v1 (schema-validated) with deterministic blueprint_hash
  - E2E test covers compile->runner->dossier (dossier manifest schema validation)

## 6) Codex Prompt Footer

Append `docs/_snippets/codex_phase_footer.md` to the phase task card prompt for consistency.

