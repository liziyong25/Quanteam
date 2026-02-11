from __future__ import annotations

import inspect
import json
import os
import sys
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from wequant.mongo import get_db, collection_has_field, collection_has_data
import wequant.wefetch as wefetch
from .sample_codes import CANDIDATE_CODE_FIELDS


if os.getenv("WEQUANT_E2E") != "1":
    pytest.skip("WEQUANT_E2E is not set", allow_module_level=True)


logging.getLogger("pymongo").setLevel(logging.WARNING)


def _ensure_mongo():
    from pymongo import MongoClient
    from wequant.config import load_mongo_config

    cfg = load_mongo_config()
    client = MongoClient(cfg.uri, serverSelectionTimeoutMS=2000)
    try:
        client.admin.command("ping")
    except Exception as exc:
        pytest.skip(f"mongo not reachable: {exc}")


_ensure_mongo()


QA_AVAILABLE = False
QA_IMPORT_ERROR = None
qa_path = os.getenv("WEQUANT_QA_PATH")
if qa_path:
    sys.path.insert(0, qa_path)
    if qa_path.endswith("QUANTAXIS"):
        parent = os.path.dirname(qa_path)
        if parent and parent not in sys.path:
            sys.path.insert(0, parent)


def _ensure_quantaxis_namespace(path: str | None):
    if not path:
        return
    import types

    if "QUANTAXIS" in sys.modules:
        return
    pkg_dir = path if path.endswith("QUANTAXIS") else os.path.join(path, "QUANTAXIS")
    if os.path.isdir(pkg_dir):
        mod = types.ModuleType("QUANTAXIS")
        mod.__path__ = [pkg_dir]
        sys.modules["QUANTAXIS"] = mod


def _patch_pandas_qmar():
    import pandas as pd

    if getattr(pd, "_wequant_qmar_patch", False):
        return

    _orig = pd.date_range

    def _patched(*args, **kwargs):
        if kwargs.get("freq") == "Q-MAR":
            kwargs["freq"] = "QE-MAR"
        return _orig(*args, **kwargs)

    pd.date_range = _patched
    pd._wequant_qmar_patch = True
try:
    _patch_pandas_qmar()
    _ensure_quantaxis_namespace(qa_path)
    import QUANTAXIS.QAFetch.QAQuery as QAQ
    import QUANTAXIS.QAFetch.QAQuery_Advance as QAQA

    QA_AVAILABLE = True
except Exception as exc:  # pragma: no cover - environment dependent
    QA_IMPORT_ERROR = exc


FIXTURE_PATH = Path("tests") / "fixtures" / "upstream_functions.json"
FUNC_ITEMS = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _ensure_collection(db, name: str):
    if name not in db.list_collection_names():
        pytest.skip(f"collection {name} not found")
    coll = db[name]
    if not collection_has_data(coll):
        pytest.skip(f"collection {name} has no data")
    return coll


def _sample_code_field(coll) -> tuple[str | None, str | None]:
    doc = coll.find_one({}, {field: 1 for field in CANDIDATE_CODE_FIELDS})
    if not doc:
        return None, None
    for field in CANDIDATE_CODE_FIELDS:
        value = doc.get(field)
        if value not in (None, ""):
            return str(value), field
    return None, None


def _date_range_for(coll, code: str | None = None, code_field: str | None = None):
    if collection_has_field(coll, "date_stamp"):
        sort_field = "date_stamp"
        def _to_dt(doc):
            return pd.to_datetime(doc[sort_field], unit="s")
    elif collection_has_field(coll, "time_stamp"):
        sort_field = "time_stamp"
        def _to_dt(doc):
            return pd.to_datetime(doc[sort_field], unit="s")
    elif collection_has_field(coll, "datetime"):
        sort_field = "datetime"
        def _to_dt(doc):
            return pd.to_datetime(doc[sort_field])
    elif collection_has_field(coll, "date"):
        sort_field = "date"
        def _to_dt(doc):
            return pd.to_datetime(doc[sort_field])
    else:
        return None, None

    query = {}
    if code is not None:
        field = code_field or "code"
        query[field] = code

    first = coll.find_one(query, sort=[(sort_field, 1)])
    last = coll.find_one(query, sort=[(sort_field, -1)])
    if not first or not last:
        return None, None
    return _to_dt(first), _to_dt(last)


def _compare_frames(df_qa: pd.DataFrame | None, df_we: pd.DataFrame | None, tol=1e-6):
    if df_qa is None:
        assert df_we is None
        return
    assert df_we is not None
    assert set(df_qa.columns) == set(df_we.columns)
    key_candidates = [
        "date",
        "datetime",
        "updateDate",
        "dir_dcl_date",
        "report_date",
        "blockname",
        "code",
        "a_stockcode",
        "symbol",
    ]
    qa = df_qa.copy()
    we = df_we.copy()
    if any(name in key_candidates for name in qa.index.names):
        qa = qa.reset_index(drop=True)
    if any(name in key_candidates for name in we.index.names):
        we = we.reset_index(drop=True)
    key_cols = [c for c in key_candidates if c in qa.columns]
    qa = qa.sort_values(key_cols).reset_index(drop=True) if key_cols else qa.reset_index(drop=True)
    we = we.sort_values(key_cols).reset_index(drop=True) if key_cols else we.reset_index(drop=True)
    for col in key_cols:
        assert qa[col].astype(str).equals(we[col].astype(str))
    numeric_cols = [c for c in qa.columns if pd.api.types.is_numeric_dtype(qa[c])]
    for col in numeric_cols:
        assert np.allclose(qa[col].to_numpy(), we[col].to_numpy(), rtol=tol, atol=tol, equal_nan=True)
    other_cols = [c for c in qa.columns if c not in numeric_cols and c not in key_cols]
    for col in other_cols:
        assert qa[col].astype(str).equals(we[col].astype(str))


def _compare_list_of_dicts(qa_res, we_res):
    assert isinstance(qa_res, list)
    assert isinstance(we_res, list)
    assert len(qa_res) == len(we_res)
    if not qa_res:
        return
    if not isinstance(qa_res[0], dict):
        assert qa_res == we_res
        return

    candidate_keys = ["code", "symbol", "a_stockcode", "ts_code", "account_cookie", "cookie", "id"]
    key = None
    for k in candidate_keys:
        if all(k in item for item in qa_res) and all(k in item for item in we_res):
            key = k
            break

    if key:
        qa_map = {item[key]: item for item in qa_res}
        we_map = {item[key]: item for item in we_res}
        sample_keys = sorted(set(qa_map).intersection(we_map))[:5]
        for k in sample_keys:
            assert set(qa_map[k].keys()) == set(we_map[k].keys())
            for field in qa_map[k].keys():
                assert str(qa_map[k][field]) == str(we_map[k][field])
        return

    assert set(qa_res[0].keys()) == set(we_res[0].keys())


def _normalize_res(res):
    if hasattr(res, "data"):
        return res.data
    return res


def _call_with_optional(func, args, kwargs, coll=None, db=None):
    params = inspect.signature(func).parameters
    if coll is not None and "collections" in params and "collections" not in kwargs:
        kwargs["collections"] = coll
    if db is not None and "db" in params and "db" not in kwargs:
        kwargs["db"] = db
    if "format" in params and "format" not in kwargs:
        kwargs["format"] = "pd"
    return func(*args, **kwargs)


def _build_case(func_name: str, db):
    # Unimplemented or always-None behaviors
    if func_name == "QA_fetch_future_tick":
        return {"expect_exception": NotImplementedError}
    if func_name == "QA_fetch_option_day_adv":
        return {"expect_none": True}

    # Trade dates
    if func_name == "QA_fetch_trade_date":
        return {"args": (), "kwargs": {}, "compare": "list"}

    # List functions
    list_map = {
        "QA_fetch_stock_list": "stock_list",
        "QA_fetch_stock_list_adv": "stock_list",
        "QA_fetch_index_list": "index_list",
        "QA_fetch_index_list_adv": "index_list",
        "QA_fetch_future_list": "future_list",
        "QA_fetch_future_list_adv": "future_list",
        "QA_fetch_etf_list": "etf_list",
        "QA_fetch_ctp_future_list": "ctp_future_list",
    }
    if func_name in list_map:
        coll = _ensure_collection(db, list_map[func_name])
        return {"args": (), "kwargs": {}, "compare": "df", "coll": coll}

    if func_name in {"QA_fetch_cryptocurrency_list", "QA_fetch_cryptocurrency_list_adv"}:
        coll = _ensure_collection(db, "cryptocurrency_list")
        doc = coll.find_one({}, {"market": 1, "exchange": 1})
        market = None
        if doc:
            market = doc.get("market") or doc.get("exchange")
        if not market:
            pytest.skip("cryptocurrency_list missing market field")
        return {"args": (market,), "kwargs": {}, "compare": "df", "coll": coll}

    # Name lookups
    name_map = {
        "QA_fetch_stock_name": "stock_list",
        "QA_fetch_index_name": "index_list",
        "QA_fetch_etf_name": "etf_list",
    }
    if func_name in name_map:
        coll = _ensure_collection(db, name_map[func_name])
        code, _ = _sample_code_field(coll)
        if not code:
            pytest.skip(f"no code in {name_map[func_name]}")
        return {"args": (code,), "kwargs": {}, "compare": "scalar", "coll": coll}

    # Stock basic info / terminated
    if func_name == "QA_fetch_stock_basic_info_tushare":
        coll = _ensure_collection(db, "stock_info_tushare")
        return {"args": (), "kwargs": {}, "compare": "list", "coll": coll}
    if func_name == "QA_fetch_stock_terminated":
        coll = _ensure_collection(db, "stock_terminated")
        return {"args": (), "kwargs": {}, "compare": "df", "coll": coll}
    if func_name == "QA_fetch_stock_to_market_date":
        coll = _ensure_collection(db, "stock_info_tushare")
        code, _ = _sample_code_field(coll)
        if not code:
            pytest.skip("no code in stock_info_tushare")
        return {"args": (code,), "kwargs": {}, "compare": "scalar", "coll": coll}

    # HK stock day expects list for $in
    if func_name == "QA_fetch_hkstock_day":
        coll = _ensure_collection(db, "hkstock_day")
        if not collection_has_field(coll, "vol"):
            pytest.skip("hkstock_day missing vol field; upstream QA returns None")
        code, field = _sample_code_field(coll)
        if not code:
            pytest.skip("no code in hkstock_day")
        start_dt, end_dt = _date_range_for(coll, code, field)
        if not start_dt or not end_dt:
            pytest.skip("no date range in hkstock_day")
        window_end = min(start_dt + pd.Timedelta(days=60), end_dt)
        start = start_dt.strftime("%Y-%m-%d")
        end = window_end.strftime("%Y-%m-%d")
        return {"args": ([code], start, end), "kwargs": {}, "compare": "df", "coll": coll}

    # Day-based functions
    day_map = {
        "QA_fetch_stock_day": "stock_day",
        "QA_fetch_stock_day_adv": "stock_day",
        "QA_fetch_index_day": "index_day",
        "QA_fetch_index_day_adv": "index_day",
        "QA_fetch_future_day": "future_day",
        "QA_fetch_future_day_adv": "future_day",
        "QA_fetch_cryptocurrency_day": "cryptocurrency_day",
        "QA_fetch_cryptocurrency_day_adv": "cryptocurrency_day",
    }
    if func_name in day_map:
        coll = _ensure_collection(db, day_map[func_name])
        code, field = _sample_code_field(coll)
        if not code:
            pytest.skip(f"no code in {day_map[func_name]}")
        start_dt, end_dt = _date_range_for(coll, code, field)
        if not start_dt or not end_dt:
            pytest.skip(f"no date range in {day_map[func_name]}")
        window_end = min(start_dt + pd.Timedelta(days=60), end_dt)
        start = start_dt.strftime("%Y-%m-%d")
        end = window_end.strftime("%Y-%m-%d")
        return {"args": (code, start, end), "kwargs": {}, "compare": "df", "coll": coll}

    # Stock/day full
    if func_name in {"QA_fetch_stock_full", "QA_fetch_stock_day_full_adv"}:
        coll = _ensure_collection(db, "stock_day")
        start_dt, _ = _date_range_for(coll)
        if not start_dt:
            pytest.skip("no date in stock_day")
        date_str = start_dt.strftime("%Y-%m-%d")
        return {"args": (date_str,), "kwargs": {}, "compare": "df", "coll": coll}

    # Adjusted data
    if func_name == "QA_fetch_stock_adj":
        coll = _ensure_collection(db, "stock_adj")
        code, field = _sample_code_field(coll)
        if not code:
            pytest.skip("no code in stock_adj")
        start_dt, end_dt = _date_range_for(coll, code, field)
        if not start_dt or not end_dt:
            pytest.skip("no date range in stock_adj")
        window_end = min(start_dt + pd.Timedelta(days=60), end_dt)
        start = start_dt.strftime("%Y-%m-%d")
        end = window_end.strftime("%Y-%m-%d")
        return {"args": (code, start, end), "kwargs": {}, "compare": "df", "coll": coll}

    # DK data
    if func_name == "QA_fetch_dk_data":
        coll = _ensure_collection(db, "dk_data_adj")
        code, field = _sample_code_field(coll)
        if not code:
            pytest.skip("no code in dk_data_adj")
        start_dt, end_dt = _date_range_for(coll, code, field)
        if not start_dt or not end_dt:
            pytest.skip("no datetime range in dk_data_adj")
        window_end = min(start_dt + pd.Timedelta(days=1), end_dt)
        # QA_fetch_dk_data validates end with date-only format
        start = start_dt.strftime("%Y-%m-%d")
        end = window_end.strftime("%Y-%m-%d")
        if coll.find_one({"code": {"$in": [code]}, "datetime": {"$gte": start, "$lte": end}}) is None:
            pytest.skip("dk_data_adj no data for sampled code/range")
        return {"args": ([code], start, end), "kwargs": {}, "compare": "df", "coll": coll}

    # Min-based functions
    min_map = {
        "QA_fetch_stock_min": "stock_min",
        "QA_fetch_stock_min_adv": "stock_min",
        "QA_fetch_index_min": "index_min",
        "QA_fetch_index_min_adv": "index_min",
        "QA_fetch_future_min": "future_min",
        "QA_fetch_future_min_adv": "future_min",
        "QA_fetch_cryptocurrency_min": "cryptocurrency_min",
        "QA_fetch_cryptocurrency_min_adv": "cryptocurrency_min",
    }
    if func_name in min_map:
        coll = _ensure_collection(db, min_map[func_name])
        code, field = _sample_code_field(coll)
        if not code:
            pytest.skip(f"no code in {min_map[func_name]}")
        start_dt, end_dt = _date_range_for(coll, code, field)
        if not start_dt or not end_dt:
            pytest.skip(f"no datetime range in {min_map[func_name]}")
        window_end = min(start_dt + pd.Timedelta(days=1), end_dt)
        start = start_dt.strftime("%Y-%m-%d %H:%M:%S")
        end = window_end.strftime("%Y-%m-%d %H:%M:%S")
        doc = coll.find_one({field or 'code': code}) or {}
        frequence = doc.get("type", "1min")
        return {
            "args": (code, start, end),
            "kwargs": {"frequence": frequence},
            "compare": "df",
            "coll": coll,
        }

    # Transaction functions
    trans_map = {
        "QA_fetch_stock_transaction": "stock_transaction",
        "QA_fetch_stock_transaction_adv": "stock_transaction",
        "QA_fetch_index_transaction": "index_transaction",
        "QA_fetch_index_transaction_adv": "index_transaction",
    }
    if func_name in trans_map:
        coll = _ensure_collection(db, trans_map[func_name])
        code, field = _sample_code_field(coll)
        if not code:
            pytest.skip(f"no code in {trans_map[func_name]}")
        start_dt, end_dt = _date_range_for(coll, code, field)
        if not start_dt or not end_dt:
            pytest.skip(f"no datetime range in {trans_map[func_name]}")
        window_end = min(start_dt + pd.Timedelta(hours=1), end_dt)
        start = start_dt.strftime("%Y-%m-%d %H:%M:%S")
        end = window_end.strftime("%Y-%m-%d %H:%M:%S")
        doc = coll.find_one({field or 'code': code}) or {}
        frequence = doc.get("type", "tick")
        return {
            "args": (code, start, end),
            "kwargs": {"frequence": frequence},
            "compare": "df",
            "coll": coll,
        }

    # Realtime min
    if func_name == "QA_fetch_stock_realtime_min":
        coll_name = f"realtime_kline_{pd.Timestamp.today().date()}"
        coll = _ensure_collection(db, coll_name)
        if coll.estimated_document_count() > 200000:
            pytest.skip(f"{coll_name} too large for e2e")
        code, _ = _sample_code_field(coll)
        if not code:
            pytest.skip(f"no code in {coll_name}")
        doc = coll.find_one({"code": code}) or {}
        frequence = doc.get("type", "1min")
        return {
            "args": (code,),
            "kwargs": {"frequence": frequence},
            "compare": "df",
            "coll": coll,
        }

    # Realtime quotations
    if func_name in {"QA_fetch_quotation", "QA_fetch_quotations"}:
        date = pd.Timestamp.today().date()
        coll_name = f"realtime_{date}"
        coll = _ensure_collection(db, coll_name)
        if coll.estimated_document_count() > 200000:
            pytest.skip(f"{coll_name} too large for e2e")
        if func_name == "QA_fetch_quotation":
            code, _ = _sample_code_field(coll)
            if not code:
                pytest.skip(f"no code in {coll_name}")
            return {"args": (code, date), "kwargs": {}, "compare": "df", "coll": coll}
        return {"args": (date,), "kwargs": {}, "compare": "df", "coll": coll}

    # Realtime adv
    if func_name == "QA_fetch_stock_realtime_adv":
        date = pd.Timestamp.today().date()
        coll_name = f"realtime_{date}"
        coll = _ensure_collection(db, coll_name)
        if coll.estimated_document_count() > 200000:
            pytest.skip(f"{coll_name} too large for e2e")
        code, _ = _sample_code_field(coll)
        if not code:
            pytest.skip(f"no code in {coll_name}")
        return {"args": (code,), "kwargs": {"num": 1}, "compare": "df", "coll": coll}

    # CTP tick
    if func_name == "QA_fetch_ctp_tick":
        coll = _ensure_collection(db, "ctp_tick")
        code, field = _sample_code_field(coll)
        if not code:
            pytest.skip("no code in ctp_tick")
        start_dt, end_dt = _date_range_for(coll, code, field)
        if not start_dt or not end_dt:
            pytest.skip("no datetime range in ctp_tick")
        window_end = min(start_dt + pd.Timedelta(hours=1), end_dt)
        start = start_dt.strftime("%Y-%m-%d %H:%M:%S")
        end = window_end.strftime("%Y-%m-%d %H:%M:%S")
        doc = coll.find_one({field or 'code': code}) or {}
        frequence = doc.get("type", "tick")
        return {
            "args": (code, start, end, frequence),
            "kwargs": {},
            "compare": "df",
            "coll": coll,
        }

    # Stock XDXR
    if func_name == "QA_fetch_stock_xdxr":
        coll = _ensure_collection(db, "stock_xdxr")
        code, field = _sample_code_field(coll)
        if not code:
            pytest.skip("no code in stock_xdxr")
        return {"args": (code,), "kwargs": {}, "compare": "df", "coll": coll}

    # Backtest info/history
    if func_name == "QA_fetch_backtest_info":
        coll = _ensure_collection(db, "backtest_info")
        return {"args": (), "kwargs": {}, "compare": "list", "coll": coll}
    if func_name == "QA_fetch_backtest_history":
        coll = _ensure_collection(db, "backtest_history")
        return {"args": (), "kwargs": {}, "compare": "list", "coll": coll}

    # Stock block info
    if func_name == "QA_fetch_stock_block":
        coll = _ensure_collection(db, "stock_block")
        code, _ = _sample_code_field(coll)
        if not code:
            pytest.skip("no code in stock_block")
        return {"args": (code,), "kwargs": {}, "compare": "df", "coll": coll}
    if func_name == "QA_fetch_stock_block_adv":
        coll = _ensure_collection(db, "stock_block")
        code, _ = _sample_code_field(coll)
        if not code:
            pytest.skip("no code in stock_block")
        return {"args": (code,), "kwargs": {}, "compare": "df", "coll": coll}
    if func_name == "QA_fetch_stock_block_history":
        coll = _ensure_collection(db, "stock_block_history")
        code, _ = _sample_code_field(coll)
        if not code:
            pytest.skip("no code in stock_block_history")
        doc = coll.find_one({"code": code}, {"updateDate": 1}) or coll.find_one(
            {}, {"updateDate": 1}
        )
        if not doc or "updateDate" not in doc:
            pytest.skip("no updateDate in stock_block_history")
        date = str(doc["updateDate"])[0:10]
        return {"args": (code, date, date), "kwargs": {}, "compare": "df", "coll": coll}
    if func_name == "QA_fetch_stock_block_slice_history":
        coll = _ensure_collection(db, "stock_block_slice_history")
        code, _ = _sample_code_field(coll)
        if not code:
            pytest.skip("no code in stock_block_slice_history")
        return {"args": (code,), "kwargs": {}, "compare": "df", "coll": coll}

    # Stock info
    if func_name == "QA_fetch_stock_info":
        coll = _ensure_collection(db, "stock_info")
        code, _ = _sample_code_field(coll)
        if not code:
            pytest.skip("no code in stock_info")
        return {"args": (code,), "kwargs": {}, "compare": "df", "coll": coll}

    # Account/risk/user/strategy
    if func_name == "QA_fetch_account":
        coll = _ensure_collection(db, "account")
        return {"args": (), "kwargs": {}, "compare": "list", "coll": coll}
    if func_name == "QA_fetch_risk":
        coll = _ensure_collection(db, "risk")
        return {"args": (), "kwargs": {}, "compare": "list", "coll": coll}
    if func_name == "QA_fetch_user":
        coll = _ensure_collection(db, "user")
        return {"args": (), "kwargs": {}, "compare": "list", "coll": coll}
    if func_name == "QA_fetch_strategy":
        coll = _ensure_collection(db, "strategy")
        return {"args": (), "kwargs": {}, "compare": "list", "coll": coll}

    # LHB
    if func_name == "QA_fetch_lhb":
        coll = _ensure_collection(db, "lhb")
        doc = coll.find_one({}, {"date": 1})
        if not doc or "date" not in doc:
            pytest.skip("no date in lhb")
        return {"args": (doc["date"],), "kwargs": {}, "compare": "df", "coll": coll}

    # Financial report
    if func_name in {"QA_fetch_financial_report", "QA_fetch_financial_report_adv"}:
        coll = _ensure_collection(db, "financial")
        doc = coll.find_one({}, {"code": 1, "report_date": 1})
        if not doc:
            pytest.skip("no data in financial")
        code = doc.get("code")
        report_date = doc.get("report_date")
        if code is None or report_date is None:
            pytest.skip("financial missing code/report_date")
        return {"args": (code, report_date), "kwargs": {}, "compare": "df", "coll": coll}

    # Stock financial calendar
    if func_name in {"QA_fetch_stock_financial_calendar", "QA_fetch_stock_financial_calendar_adv"}:
        coll = _ensure_collection(db, "report_calendar")
        doc = coll.find_one({}, {"code": 1, "date": 1})
        if not doc:
            pytest.skip("no data in report_calendar")
        code = doc.get("code")
        date = doc.get("date")
        if code is None or date is None:
            pytest.skip("report_calendar missing code/date")
        return {"args": (code, date, date), "kwargs": {}, "compare": "df", "coll": coll}

    # Stock divyield
    if func_name in {"QA_fetch_stock_divyield", "QA_fetch_stock_divyield_adv"}:
        coll = _ensure_collection(db, "stock_divyield")
        doc = coll.find_one({}, {"a_stockcode": 1, "dir_dcl_date": 1})
        if not doc:
            pytest.skip("no data in stock_divyield")
        code = doc.get("a_stockcode")
        date = doc.get("dir_dcl_date")
        if code is None or date is None:
            pytest.skip("stock_divyield missing a_stockcode/dir_dcl_date")
        return {"args": (code, date, date), "kwargs": {}, "compare": "df", "coll": coll}

    pytest.skip(f"no case builder for {func_name}")


@pytest.mark.parametrize("item", FUNC_ITEMS, ids=[item["name"] for item in FUNC_ITEMS])
def test_wefetch_matches_quantaxis(item):
    if not QA_AVAILABLE:
        pytest.skip(f"QUANTAXIS import failed: {QA_IMPORT_ERROR}")

    func_name = item["name"]
    file_name = item["file"]
    db = get_db()

    case = _build_case(func_name, db)
    if case.get("expect_exception"):
        exc = case["expect_exception"]
        qa_func = getattr(QAQ, func_name, None) or getattr(QAQA, func_name)
        we_func = getattr(wefetch, func_name.replace("QA_", ""))
        with pytest.raises(exc):
            qa_func()
        with pytest.raises(exc):
            we_func()
        return
    if case.get("expect_none"):
        qa_func = getattr(QAQ, func_name, None) or getattr(QAQA, func_name)
        we_func = getattr(wefetch, func_name.replace("QA_", ""))
        assert qa_func(None) is None
        assert we_func(None) is None
        return

    qa_module = QAQA if file_name.endswith("QAQuery_Advance.py") else QAQ
    qa_func = getattr(qa_module, func_name)
    we_func = getattr(wefetch, func_name.replace("QA_", ""))

    args = case.get("args", ())
    kwargs = case.get("kwargs", {})
    coll = case.get("coll")

    qa_res = _call_with_optional(qa_func, args, dict(kwargs), coll=coll, db=db)
    we_res = _call_with_optional(we_func, args, dict(kwargs), coll=coll, db=db)

    qa_res = _normalize_res(qa_res)
    we_res = _normalize_res(we_res)

    compare = case.get("compare", "df")
    if compare == "df":
        _compare_frames(qa_res, we_res)
    elif compare == "list":
        _compare_list_of_dicts(qa_res, we_res)
    elif compare == "scalar":
        assert qa_res == we_res
    else:
        raise AssertionError(f"unknown compare mode {compare}")
