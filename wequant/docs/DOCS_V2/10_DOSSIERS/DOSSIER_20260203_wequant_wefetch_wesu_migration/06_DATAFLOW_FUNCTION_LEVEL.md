---
title: WEFetch/WESU Migration - Dataflow Function Level
kind: dossier
component: data_layer
topics: [dataflow, mongodb, functions]
status: draft
created: 2026-02-03
updated: 2026-02-03
source_paths: []
related_modules:
  - wequant/wefetch/stock.py
  - wequant/wefetch/future.py
  - wequant/wefetch/etf.py
  - wequant/wefetch/adj.py
  - wequant/wesu/stock.py
  - wequant/wesu/future.py
  - wequant/wesu/etf.py
  - wequant/wesu/adj.py
related_tables:
  - stock_day
  - future_day
  - stock_adj
keywords: [dataflow, e2e, mongodb]
---

# 06_DATAFLOW_FUNCTION_LEVEL
## Part 1 - Module-level (mermaid)
```mermaid
graph TD
    Client[Strategy/Research] --> WEFetch[wequant.wefetch]
    Client --> WESU[wequant.wesu]
    CLI[wequant CLI] --> WEFetch
    CLI --> WESU
    WEFetch --> Mongo[(MongoDB)]
    WESU --> Mongo
```

## Part 2 - Function-level flows
WEFetch:
- `fetch_stock_day(codes,start,end)`:
  - input: codes + date range
  - query: `stock_day` by `date_stamp` or `date`
  - output: DataFrame with `volume=vol`, index `date`
- `fetch_future_day(codes,start,end)`:
  - input: codes + date range
  - query: `future_day`
  - output: DataFrame with `trade` and index `date`
- `fetch_etf_day(codes,start,end)`:
  - input: ETF codes
  - query: `stock_day` (default) or `etf_day`
  - output: DataFrame aligned with stock day schema
- `fetch_stock_adj(codes,start,end)`:
  - query: `stock_adj`
  - output: DataFrame indexed by `date`
- `fetch_*_list()`:
  - query: list collections
  - output: DataFrame indexed by `code`

WESU:
- `save_stock_day(df)`:
  - normalize `code`, `date`, `date_stamp`, `vol`
  - bulk upsert to `stock_day`
- `save_future_day(df)`:
  - normalize `date`, `date_stamp`, `trade`
  - bulk upsert to `future_day`
- `save_etf_day(df)`:
  - writes to `stock_day` (default) or `etf_day`
- `save_stock_adj(df)`:
  - normalize `code`, `date`
  - bulk upsert to `stock_adj`

## Part 3 - Minimal pairing table
| DB | Job | Library | Consumer |
|---|---|---|---|
| MongoDB | wequant CLI / pytest e2e | wequant.wefetch / wequant.wesu | notebooks / strategy |

## Evidence (run-backed)
Command:
```
conda run -n wequant wequant smoke-fetch --type stock --code 000001 --start 2024-01-01 --end 2024-01-31
```
Output (excerpt):
```
rows=22
```
