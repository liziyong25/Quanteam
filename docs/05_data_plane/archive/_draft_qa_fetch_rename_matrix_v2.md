# QA Fetch Rename Matrix (Draft v2)

This document is auto-generated for review before bulk rename.

## Summary
- wequant functions: `48`
- WBData functions: `23`
- collisions: `0`
- collision rule: `wequant` keeps canonical `fetch_*`; WBData keeps `wb_fetch_*` alias

## Review Status Values
- `accepted`: use proposed name as-is
- `modify`: rename manually
- `drop`: exclude from unified qa_fetch API

## Matrix

| source | old_name | proposed_name | domain | collision | keep_alias | status | notes |
|---|---|---|---|---|---|---|---|
| wbdata | `fetch_bond_date_list` | `fetch_bond_date_list` | bond | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mysql_fetch/bond_fetch.py` |
| wbdata | `fetch_bond_day` | `fetch_bond_day` | bond | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mysql_fetch/bond_fetch.py` |
| wbdata | `fetch_bond_industry_settlement` | `fetch_bond_industry_settlement` | bond | no | yes | review | semantic frozen as `fetch_bond_industry_settlement`; source=`src/quant_eam/qa_fetch/providers/mysql_fetch/bond_fetch.py` |
| wbdata | `fetch_bondInformation` | `fetch_bond_information` | bond | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mysql_fetch/bond_fetch.py` |
| wbdata | `fetch_bond_min` | `fetch_bond_min` | bond | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mysql_fetch/bond_fetch.py` |
| wbdata | `fetch_cfets_bond_amount` | `fetch_bond_amount_cfets` | bond | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mysql_fetch/bond_fetch.py` |
| wbdata | `fetch_cfets_credit_item` | `fetch_credit_item_cfets` | bond | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mysql_fetch/bond_fetch.py` |
| wbdata | `fetch_cfets_credit_side` | `fetch_credit_side_cfets` | bond | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mysql_fetch/bond_fetch.py` |
| wbdata | `fetch_cfets_dfz_bond_day` | `fetch_dfz_bond_day_cfets` | bond | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mysql_fetch/bond_fetch.py` |
| wbdata | `fetch_cfets_repo_buyback_item` | `fetch_repo_buyback_item_cfets` | bond | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mysql_fetch/bond_fetch.py` |
| wbdata | `fetch_cfets_repo_buyout_item` | `fetch_repo_buyout_item_cfets` | bond | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mysql_fetch/bond_fetch.py` |
| wbdata | `fetch_cfets_repo_item` | `fetch_repo_item_cfets` | bond | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mysql_fetch/bond_fetch.py` |
| wbdata | `fetch_cfets_repo_side` | `fetch_repo_side_cfets` | bond | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mysql_fetch/bond_fetch.py` |
| wbdata | `fetch_clean_quote` | `fetch_bond_quote` | bond | no | yes | review | canonical rename -> `fetch_bond_quote`; source=`src/quant_eam/qa_fetch/providers/mysql_fetch/bond_fetch.py` |
| wbdata | `fetch_clean_transaction` | `fetch_bond_transaction` | bond | no | yes | review | canonical rename -> `fetch_bond_transaction`; source=`src/quant_eam/qa_fetch/providers/mysql_fetch/bond_fetch.py` |
| wbdata | `fetch_realtime_bid` | `fetch_bond_quote_realtime` | bond | no | yes | review | canonical rename -> `fetch_bond_quote_realtime`; source=`src/quant_eam/qa_fetch/providers/mysql_fetch/bond_fetch.py` |
| wbdata | `fetch_realtime_transaction` | `fetch_bond_transaction_realtime` | bond | no | yes | review | canonical rename -> `fetch_bond_transaction_realtime`; source=`src/quant_eam/qa_fetch/providers/mysql_fetch/bond_fetch.py` |
| wbdata | `fetch_settlement_bond_day` | `fetch_bond_day_cfets` | bond | no | yes | review | canonical rename -> `fetch_bond_day_cfets`; source=`src/quant_eam/qa_fetch/providers/mysql_fetch/bond_fetch.py` |
| wbdata | `fetch_wind_indicators` | `fetch_wind_indicators` | bond | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mysql_fetch/bond_fetch.py` |
| wbdata | `fetch_yc_valuation` | `fetch_yc_valuation` | bond | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mysql_fetch/bond_fetch.py` |
| wbdata | `fetch_zz_bond_valuation` | `fetch_bond_valuation_zz` | bond | no | yes | review | canonical rename -> `fetch_bond_valuation_zz`; source=`src/quant_eam/qa_fetch/providers/mysql_fetch/bond_fetch.py` |
| wbdata | `fetch_zz_index` | `fetch_zz_index` | index | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mysql_fetch/bond_fetch.py` |
| wbdata | `fetch_zz_valuation` | `fetch_zz_valuation` | bond | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mysql_fetch/bond_fetch.py` |
| wequant | `fetch_ctp_future_list` | `fetch_ctp_future_list` | future | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |
| wequant | `fetch_ctp_tick` | `fetch_future_transaction_ctp` | future | no | yes | review | canonical rename -> `fetch_future_transaction_ctp`; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |
| wequant | `fetch_dk_data` | `fetch_dk_data` | dk | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |
| wequant | `fetch_etf_dk` | `fetch_etf_dk` | dk | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |
| wequant | `fetch_etf_list` | `fetch_etf_list` | etf | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |
| wequant | `fetch_etf_name` | `fetch_etf_name` | etf | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |
| wequant | `fetch_financial_report` | `fetch_financial_report` | bond | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |
| wequant | `fetch_future_day` | `fetch_future_day` | future | no | yes | review | wequant priority for fetch_* (collision with wbdata); source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |
| wequant | `fetch_future_dk` | `fetch_future_dk` | dk | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |
| wequant | `fetch_future_list` | `fetch_future_list` | future | no | yes | review | wequant priority for fetch_* (collision with wbdata); source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |
| wequant | `fetch_future_min` | `fetch_future_min` | future | no | yes | review | wequant priority for fetch_* (collision with wbdata); source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |
| wequant | `fetch_future_tick` | `fetch_future_tick` | future | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |
| wequant | `fetch_get_hkstock_list` | `fetch_get_hkstock_list` | stock | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |
| wequant | `fetch_hkstock_day` | `fetch_hkstock_day` | stock | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |
| wequant | `fetch_hkstock_dk` | `fetch_hkstock_dk` | dk | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |
| wequant | `fetch_index_day` | `fetch_index_day` | index | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |
| wequant | `fetch_index_day_adv` | `fetch_index_day_adv` | index | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query_advance.py` |
| wequant | `fetch_index_dk` | `fetch_index_dk` | dk | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |
| wequant | `fetch_index_list` | `fetch_index_list` | index | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |
| wequant | `fetch_index_min` | `fetch_index_min` | index | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |
| wequant | `fetch_index_name` | `fetch_index_name` | index | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |
| wequant | `fetch_index_transaction` | `fetch_index_transaction` | index | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |
| wequant | `fetch_index_transaction_adv` | `fetch_index_transaction_adv` | index | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query_advance.py` |
| wequant | `fetch_lof_dk` | `fetch_lof_dk` | dk | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |
| wequant | `fetch_reits_dk` | `fetch_reits_dk` | dk | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |
| wequant | `fetch_stock_adj` | `fetch_stock_adj` | stock | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |
| wequant | `fetch_stock_block` | `fetch_stock_block` | stock | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |
| wequant | `fetch_stock_block_history` | `fetch_stock_block_history` | stock | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |
| wequant | `fetch_stock_block_slice_history` | `fetch_stock_block_slice_history` | stock | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |
| wequant | `fetch_stock_day` | `fetch_stock_day` | stock | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |
| wequant | `fetch_stock_day_adv` | `fetch_stock_day_adv` | stock | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query_advance.py` |
| wequant | `fetch_stock_divyield` | `fetch_stock_divyield` | stock | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |
| wequant | `fetch_stock_dk` | `fetch_stock_dk` | dk | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |
| wequant | `fetch_stock_dk_adv` | `fetch_stock_dk_adv` | dk | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query_advance.py` |
| wequant | `fetch_stock_financial_calendar` | `fetch_stock_financial_calendar` | stock | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |
| wequant | `fetch_stock_full` | `fetch_stock_full` | stock | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |
| wequant | `fetch_stock_info` | `fetch_stock_info` | stock | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |
| wequant | `fetch_stock_list` | `fetch_stock_list` | stock | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |
| wequant | `fetch_stock_min` | `fetch_stock_min` | stock | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |
| wequant | `fetch_stock_min_adv` | `fetch_stock_min_adv` | stock | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query_advance.py` |
| wequant | `fetch_stock_name` | `fetch_stock_name` | stock | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |
| wequant | `fetch_stock_realtime_min` | `fetch_stock_realtime_min` | bond | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |
| wequant | `fetch_stock_terminated` | `fetch_stock_terminated` | stock | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |
| wequant | `fetch_stock_to_market_date` | `fetch_stock_to_market_date` | stock | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |
| wequant | `fetch_stock_transaction` | `fetch_stock_transaction` | stock | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |
| wequant | `fetch_stock_transaction_adv` | `fetch_stock_transaction_adv` | stock | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query_advance.py` |
| wequant | `fetch_stock_xdxr` | `fetch_stock_xdxr` | stock | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |
| wequant | `fetch_trade_date` | `fetch_trade_date` | generic | no | yes | review | standard mapping; source=`src/quant_eam/qa_fetch/providers/mongo_fetch/wefetch/query.py` |

## Deprecation Plan (Migration Phase)
- keep old names as aliases until dual-DB smoke + notebook validation are stable
- after approval, remove old aliases in final cutover

