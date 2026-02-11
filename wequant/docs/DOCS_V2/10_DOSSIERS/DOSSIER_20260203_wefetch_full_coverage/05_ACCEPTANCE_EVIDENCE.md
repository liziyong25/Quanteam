---
title: WEFetch Full Coverage - Acceptance Evidence
kind: dossier
component: data_layer
topics: [evidence, pytest, notebook]
status: draft
created: 2026-02-03
updated: 2026-02-03
source_paths: []
related_modules: []
related_tables: []
keywords: [e2e, evidence]
---

# Acceptance Evidence (Run-backed)
## Environment
- `conda run -n wequant python -c "import sys; print(sys.version)"`
- `conda run -n wequant python -c "import wequant; print('wequant import ok')"`
```text
3.11.14 | packaged by Anaconda, Inc. | (main, Oct 21 2025, 18:30:03) [MSC v.1929 64 bit (AMD64)]
wequant import ok
```

## Tests
- `conda run -n wequant pytest -q`
- `$env:WEQUANT_QA_PATH='<QUANTAXIS_ROOT>'; $env:WEQUANT_E2E='1'; conda run -n wequant pytest -q -rs`
```text
........................................................................ [ 96%]
...                                                                      [100%]
```
```text
.....sssssss.ss.s.ss....sss........s.sss......sssssssssssss......ss..... [ 46%]
ssssssss................................................................ [ 92%]
...........                                                              [100%]
=========================== short test summary info ===========================
SKIPPED [7] tests/e2e/test_save_e2e.py:45: WEQUANT_DB_NAME is not set to a test database
SKIPPED [1] tests/e2e/test_wefetch_full_e2e.py:298: hkstock_day missing vol field; upstream QA returns None
SKIPPED [1] tests/e2e/test_wefetch_full_e2e.py:371: dk_data_adj no data for sampled code/range
SKIPPED [1] tests/e2e/test_wefetch_full_e2e.py:98: collection realtime_kline_2026-02-03 not found
SKIPPED [2] tests/e2e/test_wefetch_full_e2e.py:98: collection stock_transaction not found
SKIPPED [2] tests/e2e/test_wefetch_full_e2e.py:98: collection index_transaction not found
SKIPPED [1] tests/e2e/test_wefetch_full_e2e.py:98: collection stock_terminated not found
SKIPPED [2] tests/e2e/test_wefetch_full_e2e.py:98: collection stock_info_tushare not found
SKIPPED [1] tests/e2e/test_wefetch_full_e2e.py:98: collection ctp_tick not found
SKIPPED [1] tests/e2e/test_wefetch_full_e2e.py:98: collection backtest_info not found
SKIPPED [1] tests/e2e/test_wefetch_full_e2e.py:98: collection backtest_history not found
SKIPPED [2] tests/e2e/test_wefetch_full_e2e.py:101: collection stock_block has no data
SKIPPED [3] tests/e2e/test_wefetch_full_e2e.py:98: collection realtime_2026-02-03 not found
SKIPPED [1] tests/e2e/test_wefetch_full_e2e.py:98: collection account not found
SKIPPED [1] tests/e2e/test_wefetch_full_e2e.py:98: collection risk not found
SKIPPED [1] tests/e2e/test_wefetch_full_e2e.py:98: collection user not found
SKIPPED [1] tests/e2e/test_wefetch_full_e2e.py:98: collection strategy not found
SKIPPED [1] tests/e2e/test_wefetch_full_e2e.py:98: collection lhb not found
SKIPPED [2] tests/e2e/test_wefetch_full_e2e.py:98: collection financial not found
SKIPPED [2] tests/e2e/test_wefetch_full_e2e.py:98: collection report_calendar not found
SKIPPED [2] tests/e2e/test_wefetch_full_e2e.py:98: collection stock_divyield not found
SKIPPED [2] tests/e2e/test_wefetch_full_e2e.py:98: collection cryptocurrency_list not found
SKIPPED [2] tests/e2e/test_wefetch_full_e2e.py:98: collection cryptocurrency_day not found
SKIPPED [2] tests/e2e/test_wefetch_full_e2e.py:98: collection cryptocurrency_min not found
```

## CLI
- `$env:WEQUANT_DB_NAME='wequant_e2e'; conda run -n wequant wequant init-indexes`
```text
indexes=ok
```

## Notebook
- ??????? `tests/fixtures/upstream_functions.json` ???? cell notebook
- ???`wequant/test/test_fetch.ipynb`
