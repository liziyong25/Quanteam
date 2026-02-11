# Backtest Plane (Phase-04 MVP)

This phase lands a minimal, deterministic backtest plane:

- Runner validates RunSpec + loads policies (read-only)
- Data is accessed only via DataCatalog (time-travel `as_of` enforced)
- Backtest adapter runs a fixed MVP strategy (buy-and-hold) with mandatory lag
- Outputs are written into an append-only Dossier evidence bundle

No gates, no agents, no holdout arbitration in this phase.

## Navigation

- Vectorbt adapter MVP: `vectorbt_adapter_mvp.md`
- Runner + Dossier MVP: `runner_and_dossier_mvp.md`
- Attribution + Diagnostics v1: `attribution_v1.md`
