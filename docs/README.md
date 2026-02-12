# Quant-EAM Docs (SSOT)

`docs/` is the Single Source of Truth (SSOT) for project scope, governance, protocols, and phase execution logs.

Canonical entry file is `docs/README.md`. Do not add a second docs entry (e.g. another readme) that can drift.

## Navigation

- Overview: `00_overview.md`
- Governance (non-negotiables + repo rules + change mgmt): `01_governance.md`
- Protocols Index (contracts/policies/dossier/agents/diagnostics/holdout): `02_protocols.md`
- Contracts (schemas + examples): `03_contracts/contracts_index.md`
- Policies (frozen YAML governance inputs): `04_policies/policies_index.md`
- Data plane (snapshots + as_of time-travel): `05_data_plane/data_plane_mvp.md`
- WeQuant adapter ingest (DataLake snapshot writer): `05_data_plane/wequant_adapter_ingest.md`
- Agents Plane data contract (query_dataset + qa_fetch runtime): `05_data_plane/agents_plane_data_contract_v1.md`
- Resolver + machine registry for fetch selection: `05_data_plane/qa_fetch_resolver_registry_v1.md`
- Resolver smoke evidence: `05_data_plane/qa_fetch_smoke_evidence_v1.md`
- Backtest plane (runner + dossier): `06_backtest_plane/backtest_index.md`
- Compiler (blueprint -> runspec): `07_compiler/compiler_index.md`
- Gates (gaterunner + holdout): `08_gates/gates_index.md`
- Registry (trial log + experience cards): `09_registry/registry_index.md`
- UI (read-only review console): `10_ui/ui_mvp.md`
- Composer (compose experience cards into a portfolio run): `11_composer/composer_index.md`
- Workflows:
  - Orchestrator v1: `12_workflows/orchestrator_v1.md`
  - Param Sweep v1: `12_workflows/param_sweep_v1.md`
  - Agents UI SSOT v1: `12_workflows/agents_ui_ssot_v1.yaml`
  - Subagent Dev Workflow v1: `12_workflows/subagent_dev_workflow_v1.md`
  - Subagent Control Packet v1: `12_workflows/subagent_control_packet_v1.md`
- Runbooks:
  - Local dev (Linux + Docker + /data/quanteam): `07_runbooks/local_dev.md`
  - Troubleshooting: `07_runbooks/troubleshooting.md`
- Phases:
  - Template: `08_phases/phase_template.md`
  - Phase-00A execution log: `08_phases/phase_00a_repo_bootstrap.md`
  - Phase-00D execution log: `08_phases/phase_00d_docs_governance.md`
  - Phase-06 execution log: `08_phases/phase_06_gaterunner_holdout_v1.md`
  - Phase-07 execution log: `08_phases/phase_07_registry_v1.md`
  - Phase-08 execution log: `08_phases/phase_08_ui_mvp.md`
  - Phase-09 execution log: `08_phases/phase_09_composer_mvp.md`
- ADRs (architecture decisions): `09_adr/`
- Codex prompt footer snippet (append to every phase task card): `_snippets/codex_phase_footer.md`

## Update Rules (Executable)

- Every phase must add or update its phase log: `08_phases/phase_XX_*.md`.
- If a change affects boundary/protocol of `contracts/`, `policies/`, `dossier/`, `gates/`, `holdout`, or determinism, you must add an ADR in `09_adr/` and reference it from the phase log.
- Dossiers are append-only. If a change would rewrite past runs, it is blocked unless approved by ADR and accompanied by a migration plan.

## Checks

- Run docs existence gate:
  - `make docs-check`
  - or `python3 scripts/check_docs_tree.py`
