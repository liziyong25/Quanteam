# Phase-04: Backtest + Runner + Dossier MVP

## 1) 目标（Goal）

- Build a deterministic Runner that consumes RunSpec v1 + snapshot + policy_bundle.
- Provide a `vectorbt_signal_v1` adapter surface (MVP) with a fixed buy-and-hold strategy and mandatory lag.
- Write an append-only Dossier evidence bundle whose manifest validates against `dossier_schema_v1`.

## 2) 范围（Scope）

### In Scope

- `src/quant_eam/backtest/**` (adapter + MVP engine)
- `src/quant_eam/runner/**` (runner CLI)
- `src/quant_eam/dossier/**` (append-only writer)
- Offline tests (tmp_path, no network IO)
- Docs for backtest plane + phase log

### Out of Scope

- No compiler (blueprint -> runspec)
- No DSL interpreter
- No gates/holdout/registry
- No agents/LLM

## 3) 实施方案（Implementation Plan）

- Runner validates RunSpec using contracts validator (must pass v1 schema).
- Policies are loaded read-only via `policy_bundle_v1.yaml` and recorded (sha256) into config snapshot.
- Data is fetched only via DataCatalog (enforces `available_at <= as_of`).
- Adapter runs `buy_and_hold_mvp` with `lag_bars >= 1` (from asof_latency_policy default).
- Dossier writer writes to a temp dir and then atomically renames to final `<run_id>` directory (append-only).

## 4) 交付物（Deliverables）

- Backtest: `src/quant_eam/backtest/vectorbt_adapter_mvp.py`
- Runner CLI: `src/quant_eam/runner/run.py`
- Dossier writer: `src/quant_eam/dossier/writer.py`
- Docs: `docs/06_backtest_plane/*`

## 5) 验收（Acceptance / DoD）

- Build:
  - `docker compose build api worker`
- Tests:
  - `docker compose run --rm api pytest -q`
- Demo run:
  - `docker compose run --rm api python -m quant_eam.runner.run --demo --policy-bundle policies/policy_bundle_v1.yaml`
- Docs gate:
  - `python3 scripts/check_docs_tree.py`

## 6) 完成记录（Execution Log）

- Start Date: 2026-02-09 (Asia/Taipei)
- End Date: 2026-02-09 (Asia/Taipei)
- PR/Commit: unknown (repo is not a git repository; `git rev-parse --short HEAD` fails)
- Notes:
  - Deterministic runner with append-only dossier output and contract-validated dossier manifest
  - Policy-only cost/execution wiring (no strategy overrides)
  - Time-travel data access via DataCatalog with enforced `available_at <= as_of`

## 7) Codex Prompt Footer

Append `docs/_snippets/codex_phase_footer.md` to the phase task card prompt for consistency.

