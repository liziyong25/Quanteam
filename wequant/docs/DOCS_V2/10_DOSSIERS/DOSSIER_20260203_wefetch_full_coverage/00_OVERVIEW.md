---
title: WEFetch Full Coverage - Overview (SSOT)
kind: dossier
component: data_layer
topics: [data_layer, wefetch, quantaxis, qaquery]
status: draft
created: 2026-02-03
updated: 2026-02-03
source_paths:
  - wequant/wefetch/query.py
  - wequant/wefetch/query_advance.py
  - wequant/wefetch/__init__.py
related_modules:
  - wequant/datastruct
  - wequant/utils
related_tables: []
keywords: [WEFetch, QAQuery, QAQuery_Advance, mapping, e2e]
---

# WEFetch Full Coverage SSOT
## Final
- ??????? QUANTAXIS ? `QAFetch/QAQuery.py` ? `QAFetch/QAQuery_Advance.py` ???????? `wequant.wefetch.fetch_*`??? `QA_` ????????
- ???`wequant/wefetch/query.py` + `wequant/wefetch/query_advance.py` + `wequant/wefetch/__init__.py`?
- ?????? e2e ??????/??? skip????? notebook ?????

## Contracts
- Fetch API: `docs/DOCS_V2/20_KB/data_layer/KB_data_layer_fetch_api_contract.md`
- Function Mapping: `docs/DOCS_V2/20_KB/data_layer/KB_data_layer_function_mapping.md`
- ENV: ? Dossier `02_ENV_CONTRACT.md`

## Decisions
- ?? `collections`/`db` ??? `None`??????? `wequant.mongo.get_db()` ??????? import ??????
- crypto ?? `symbol` ??????????? `code` ?????? collection ?????
- ETF day defaults to `index_day` (align with QASU save); override via `WEQUANT_ETF_DAY_COLLECTION`.

## Verification Order
1) `conda run -n wequant python -c "import wequant"`
2) `conda run -n wequant pytest -q`
3) `WEQUANT_E2E=1` ??? `tests/e2e/test_wefetch_full_e2e.py`
4) `wequant/test/test_fetch.ipynb` ??????????

## Rollback
- ????? WEFetch ???? `wequant/wefetch` ??? `__init__.py` ???
