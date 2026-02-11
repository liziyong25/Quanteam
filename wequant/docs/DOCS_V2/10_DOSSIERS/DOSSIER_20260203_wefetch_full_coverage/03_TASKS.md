---
title: WEFetch Full Coverage - Tasks
kind: dossier
component: data_layer
topics: [tasks, coverage, qaquery]
status: draft
created: 2026-02-03
updated: 2026-02-03
source_paths: []
related_modules: []
related_tables: []
keywords: [tasks, e2e, notebook]
---

# Tasks & PASS Criteria
## Task List
- ?? `QAQuery.py` + `QAQuery_Advance.py` ?????`fetch_*` + `QA_` ????
- e2e ???`tests/e2e/test_wefetch_full_e2e.py`???/????? skip??
- Notebook ???`wequant/test/test_fetch.ipynb` ???? cell?
- ??????`KB_data_layer_function_mapping.md`?

## PASS Criteria
- ???????coverage + notebook ????
- e2e ? `WEQUANT_E2E=1` ???????? skip?

## Function Inventory (SSOT)
| old_path | old_function | line | new_function | new_path |
|---|---|---:|---|---|
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_stock_day | 56 | fetch_stock_day | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_hkstock_day | 144 | fetch_hkstock_day | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_dk_data | 232 | fetch_dk_data | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_stock_adj | 268 | fetch_stock_adj | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_stock_realtime_min | 307 | fetch_stock_realtime_min | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_stock_min | 338 | fetch_stock_min | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_stock_transaction | 415 | fetch_stock_transaction | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_index_transaction | 482 | fetch_index_transaction | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_trade_date | 549 | fetch_trade_date | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_stock_list | 554 | fetch_stock_list | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_etf_list | 567 | fetch_etf_list | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_index_list | 580 | fetch_index_list | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_stock_terminated | 592 | fetch_stock_terminated | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_stock_basic_info_tushare | 605 | fetch_stock_basic_info_tushare | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_stock_to_market_date | 645 | fetch_stock_to_market_date | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_stock_full | 657 | fetch_stock_full | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_index_day | 710 | fetch_index_day | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_index_min | 774 | fetch_index_min | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_future_day | 844 | fetch_future_day | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_future_min | 922 | fetch_future_min | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_future_list | 1016 | fetch_future_list | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_ctp_future_list | 1028 | fetch_ctp_future_list | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_future_tick | 1039 | fetch_future_tick | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_ctp_tick | 1043 | fetch_ctp_tick | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_stock_xdxr | 1112 | fetch_stock_xdxr | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_backtest_info | 1129 | fetch_backtest_info | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_backtest_history | 1162 | fetch_backtest_history | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_stock_block | 1181 | fetch_stock_block | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_stock_block_history | 1206 | fetch_stock_block_history | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_stock_block_slice_history | 1247 | fetch_stock_block_slice_history | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_stock_info | 1277 | fetch_stock_info | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_stock_name | 1297 | fetch_stock_name | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_index_name | 1326 | fetch_index_name | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_etf_name | 1352 | fetch_etf_name | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_quotation | 1378 | fetch_quotation | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_quotations | 1396 | fetch_quotations | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_account | 1418 | fetch_account | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_risk | 1434 | fetch_risk | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_user | 1461 | fetch_user | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_strategy | 1482 | fetch_strategy | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_lhb | 1498 | fetch_lhb | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_financial_report | 1617 | fetch_financial_report | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_stock_financial_calendar | 1724 | fetch_stock_financial_calendar | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_stock_divyield | 1795 | fetch_stock_divyield | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_cryptocurrency_list | 1871 | fetch_cryptocurrency_list | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_cryptocurrency_day | 1934 | fetch_cryptocurrency_day | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery.py | QA_fetch_cryptocurrency_min | 2016 | fetch_cryptocurrency_min | wequant/wefetch/query.py |
| QUANTAXIS/QAFetch/QAQuery_Advance.py | QA_fetch_option_day_adv | 94 | fetch_option_day_adv | wequant/wefetch/query_advance.py |
| QUANTAXIS/QAFetch/QAQuery_Advance.py | QA_fetch_stock_day_adv | 108 | fetch_stock_day_adv | wequant/wefetch/query_advance.py |
| QUANTAXIS/QAFetch/QAQuery_Advance.py | QA_fetch_stock_min_adv | 152 | fetch_stock_min_adv | wequant/wefetch/query_advance.py |
| QUANTAXIS/QAFetch/QAQuery_Advance.py | QA_fetch_stock_day_full_adv | 227 | fetch_stock_day_full_adv | wequant/wefetch/query_advance.py |
| QUANTAXIS/QAFetch/QAQuery_Advance.py | QA_fetch_index_day_adv | 248 | fetch_index_day_adv | wequant/wefetch/query_advance.py |
| QUANTAXIS/QAFetch/QAQuery_Advance.py | QA_fetch_index_min_adv | 289 | fetch_index_min_adv | wequant/wefetch/query_advance.py |
| QUANTAXIS/QAFetch/QAQuery_Advance.py | QA_fetch_stock_transaction_adv | 353 | fetch_stock_transaction_adv | wequant/wefetch/query_advance.py |
| QUANTAXIS/QAFetch/QAQuery_Advance.py | QA_fetch_index_transaction_adv | 420 | fetch_index_transaction_adv | wequant/wefetch/query_advance.py |
| QUANTAXIS/QAFetch/QAQuery_Advance.py | QA_fetch_stock_list_adv | 486 | fetch_stock_list_adv | wequant/wefetch/query_advance.py |
| QUANTAXIS/QAFetch/QAQuery_Advance.py | QA_fetch_index_list_adv | 501 | fetch_index_list_adv | wequant/wefetch/query_advance.py |
| QUANTAXIS/QAFetch/QAQuery_Advance.py | QA_fetch_future_day_adv | 516 | fetch_future_day_adv | wequant/wefetch/query_advance.py |
| QUANTAXIS/QAFetch/QAQuery_Advance.py | QA_fetch_future_min_adv | 556 | fetch_future_min_adv | wequant/wefetch/query_advance.py |
| QUANTAXIS/QAFetch/QAQuery_Advance.py | QA_fetch_future_list_adv | 626 | fetch_future_list_adv | wequant/wefetch/query_advance.py |
| QUANTAXIS/QAFetch/QAQuery_Advance.py | QA_fetch_stock_block_adv | 641 | fetch_stock_block_adv | wequant/wefetch/query_advance.py |
| QUANTAXIS/QAFetch/QAQuery_Advance.py | QA_fetch_stock_realtime_adv | 704 | fetch_stock_realtime_adv | wequant/wefetch/query_advance.py |
| QUANTAXIS/QAFetch/QAQuery_Advance.py | QA_fetch_financial_report_adv | 762 | fetch_financial_report_adv | wequant/wefetch/query_advance.py |
| QUANTAXIS/QAFetch/QAQuery_Advance.py | QA_fetch_stock_financial_calendar_adv | 827 | fetch_stock_financial_calendar_adv | wequant/wefetch/query_advance.py |
| QUANTAXIS/QAFetch/QAQuery_Advance.py | QA_fetch_stock_divyield_adv | 868 | fetch_stock_divyield_adv | wequant/wefetch/query_advance.py |
| QUANTAXIS/QAFetch/QAQuery_Advance.py | QA_fetch_cryptocurrency_day_adv | 907 | fetch_cryptocurrency_day_adv | wequant/wefetch/query_advance.py |
| QUANTAXIS/QAFetch/QAQuery_Advance.py | QA_fetch_cryptocurrency_min_adv | 944 | fetch_cryptocurrency_min_adv | wequant/wefetch/query_advance.py |
| QUANTAXIS/QAFetch/QAQuery_Advance.py | QA_fetch_cryptocurrency_list_adv | 1014 | fetch_cryptocurrency_list_adv | wequant/wefetch/query_advance.py |
