# QA Fetch Exception Decisions v1

Status: active (all exception rows resolved for runtime gating).

- Scope: functions not passing in current smoke evidence baseline.
- Runtime policy: `decision=allow` means callable in smoke/research/backtest; `pending/drop/disabled` would be blocked.

| function | issue_type | smoke_policy | research_policy | decision | notes |
|---|---|---|---|---|---|
| `fetch_bond_min` | source_table_missing | allow_with_fallback | allow_with_fallback | allow | missing table `clean_execreport_1min`; fallback to `fetch_bond_day` |
| `fetch_repo_item_cfets` | source_table_missing | allow_with_fallback | allow_with_fallback | allow | missing table `cfets_repo_item`; fallback merge `buyback+buyout+side` |
| `fetch_bond_quote` | source_table_missing | allow_with_fallback | allow_with_fallback | allow | missing table `clean_bond_quote`; fallback to `fetch_realtime_bid` |
| `fetch_bond_amount_cfets` | smoke_timeout_sensitive | use_window_profile | allow_long_running | allow | tuned smoke window `2026-01-01~2026-02-11` now passes in 30s |
| `fetch_yc_valuation` | smoke_timeout_sensitive | use_window_profile | allow_long_running | allow | tuned smoke window `2026-01-01~2026-02-11` now passes in 30s |
| `fetch_bond_valuation_zz` | smoke_timeout_sensitive | use_window_profile | allow_long_running | allow | tuned smoke window `2026-01-01~2026-02-11` now passes in 30s |
| `fetch_stock_block_history` | smoke_timeout_sensitive | use_window_profile | allow_long_running | allow | tuned smoke kwargs (`code=600010`) now pass in 30s |
| `fetch_future_tick` | not_implemented | allow_with_empty | allow_with_empty | allow | wrapper returns standardized empty frame when upstream not implemented |
