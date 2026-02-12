# QA Fetch Unified Contract v1

This contract defines the unified fetch entrypoint for dual data backends:

- `wequant` (MongoDB; stock/future/ETF/index/DK/QA-compatible fetch APIs)
- `WBData` (MySQL; bond-domain fetch APIs)

## Entrypoint

- Python module: `quant_eam.qa_fetch`
- Runtime exported naming (current compatibility layer): `qa_fetch_*` + legacy aliases
- Review matrix target naming: `fetch_*` (lowercase `snake_case`)

## Naming Convention (Draft v3)

For unified fetch naming in matrix/docs:

- Base pattern: `fetch_<asset>_<freq>[_<venue>]`
- `asset`: `bond`, `stock`, `hkstock`, `future`, `etf`, `index`
- `freq` (market data): `day`, `min`, `transaction`, `dk`
- `venue` is optional and MUST be at the end (suffix style)
  - preferred: `fetch_bond_day_cfets`
  - avoid prefix style for new names: `fetch_cfets_bond_day`

### ADV rule

- `_adv` is only retained for market-data frequencies: `day|min|transaction|dk`
- Non-market `*_adv` names (for example `*_list_adv`, `*_block_adv`) should be dropped or normalized to non-adv names
- In wequant semantics:
  - `fetch_stock_day` => raw bars
  - `fetch_stock_day_adv` => QADataStruct wrapper (supports `.to_qfq()` / `.to_hfq()`)

### Source default

- If caller does not specify a source/venue, use the generic function (for example `fetch_bond_day`)
- Do NOT auto-switch to venue-specific function (for example `fetch_bond_day_cfets`) unless explicitly requested

## LLM/Backtest Call Contract

To reduce ambiguity for agents and backtest steps:

- default adjustment policy: `adjust=raw`
- optional: `adjust=qfq` or `adjust=hfq`
- recommended request contract for market data:
  - `symbol`, `start`, `end`, `freq`
  - `adjust` in `{raw,qfq,hfq}`
  - optional `venue` (only when a venue-specific dataset is required)

Suggested behavior:

1. If `adjust=raw`, call raw function directly (for example `fetch_stock_day`).
2. If `adjust=qfq|hfq` and `*_adv` exists for that market-data freq, call `*_adv` then convert (`to_qfq()` / `to_hfq()`).
3. If venue is not specified, call generic name (`fetch_bond_day`) instead of venue-specific (`fetch_bond_day_cfets`).

## Collision Rule

If both backends expose the same normalized function name:

- `wequant` keeps the canonical `qa_fetch_*` name
- `WBData` keeps a prefixed alias: `wb_fetch_*`

Known collisions in v1:

- `fetch_future_day`
- `fetch_future_list`
- `fetch_future_min`

## Compatibility Layer

Migration phase keeps aliases to avoid breaking callers:

- legacy `fetch_*` aliases remain available in `quant_eam.qa_fetch`
- legacy `QA_fetch_*` aliases for wequant remain available
- WBData-prefixed aliases are always exported (`wb_fetch_*`)

## Review Matrix

The rename freeze baseline is generated at:

- `docs/05_data_plane/archive/_draft_qa_fetch_rename_matrix_v1.md`
- `docs/05_data_plane/archive/_draft_qa_fetch_rename_matrix_v2.md`
- `docs/05_data_plane/_draft_qa_fetch_rename_matrix_v3.md`
- machine registry: `docs/05_data_plane/qa_fetch_registry_v1.json`

It is generated from source files (no manual editing expected) via:

```bash
python3 scripts/generate_qa_fetch_rename_matrix.py
python3 scripts/generate_qa_fetch_registry_json.py
```

## Resolver API

- module: `quant_eam.qa_fetch.resolver`
- deterministic selector:
  - `resolve_fetch(asset, freq, venue=None, adjust=\"raw\")`
  - `fetch_market_data(asset, freq, symbols, start, end, venue=None, adjust=\"raw\")`
- machine registry payload:
  - `qa_fetch_registry_payload(include_drop=False)`

## Migration Stages

1. Review draft matrix and set each row status (`accepted` / `modify` / `drop`)
2. Keep compatibility aliases while dual-DB smoke checks run
3. Cut over old aliases only after approval and validation
