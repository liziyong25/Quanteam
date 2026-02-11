from __future__ import annotations

import os
import sys
import logging
import pandas as pd
import numpy as np
import pytest

from wequant.mongo import get_db, collection_has_field
from wequant.wefetch import (
    fetch_stock_day,
    fetch_future_day,
    fetch_etf_day,
    fetch_stock_adj,
    fetch_stock_list,
    fetch_future_list,
    fetch_etf_list,
)
from wequant.wefetch.etf import _select_etf_day_collection
from .sample_codes import sample_codes


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
    from QUANTAXIS.QAFetch.QAQuery import (
        QA_fetch_stock_day,
        QA_fetch_index_day,
        QA_fetch_future_day,
        QA_fetch_stock_adj,
        QA_fetch_stock_list,
        QA_fetch_future_list,
        QA_fetch_etf_list,
    )

    QA_AVAILABLE = True
except Exception as exc:  # pragma: no cover - environment dependent
    QA_IMPORT_ERROR = exc


def _to_datestr(value) -> str:
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def _date_range_for(coll, code: str):
    if collection_has_field(coll, "date_stamp"):
        first = coll.find_one({"code": code}, sort=[("date_stamp", 1)])
        last = coll.find_one({"code": code}, sort=[("date_stamp", -1)])
    else:
        first = coll.find_one({"code": code}, sort=[("date", 1)])
        last = coll.find_one({"code": code}, sort=[("date", -1)])
    if not first or not last:
        return None, None
    start = _to_datestr(first.get("date") or pd.to_datetime(first["date_stamp"], unit="s"))
    end = _to_datestr(last.get("date") or pd.to_datetime(last["date_stamp"], unit="s"))
    return start, end


def _compare_frames(df_qa: pd.DataFrame | None, df_we: pd.DataFrame | None, tol=1e-6):
    if df_qa is None:
        assert df_we is None
        return
    assert df_we is not None
    assert set(df_qa.columns) == set(df_we.columns)
    qa = df_qa.copy()
    we = df_we.copy()
    if "date" in qa.index.names:
        qa = qa.reset_index(drop=True)
    if "date" in we.index.names:
        we = we.reset_index(drop=True)
    key_cols = [c for c in ["date", "code"] if c in qa.columns]
    qa = qa.sort_values(key_cols).reset_index(drop=True) if key_cols else qa.reset_index(drop=True)
    we = we.sort_values(key_cols).reset_index(drop=True) if key_cols else we.reset_index(drop=True)
    for col in key_cols:
        assert qa[col].equals(we[col])
    numeric_cols = [c for c in qa.columns if pd.api.types.is_numeric_dtype(qa[c])]
    for col in numeric_cols:
        assert np.allclose(qa[col].to_numpy(), we[col].to_numpy(), rtol=tol, atol=tol, equal_nan=True)
    other_cols = [c for c in qa.columns if c not in numeric_cols and c not in key_cols]
    for col in other_cols:
        assert qa[col].astype(str).equals(we[col].astype(str))


@pytest.mark.parametrize("asset_type", ["stock", "future", "etf"])
def test_fetch_day_matches_quantaxis(asset_type):
    if not QA_AVAILABLE:
        pytest.skip(f"QUANTAXIS import failed: {QA_IMPORT_ERROR}")

    codes = sample_codes(asset_type)
    if not codes:
        pytest.skip(f"no sample codes for {asset_type}")

    db = get_db()
    if asset_type == "stock":
        coll = db["stock_day"]
        qa_func = QA_fetch_stock_day
        we_func = fetch_stock_day
    elif asset_type == "future":
        coll = db["future_day"]
        qa_func = QA_fetch_future_day
        we_func = fetch_future_day
    else:
        coll = _select_etf_day_collection(db)
        qa_func = QA_fetch_index_day if coll.name == "index_day" else QA_fetch_stock_day
        we_func = fetch_etf_day

    for code in codes:
        start, end = _date_range_for(coll, code)
        if not start or not end:
            continue
        df_qa = qa_func(code, start, end, format="pd")
        df_we = we_func(code, start, end, format="pd")
        _compare_frames(df_qa, df_we)


def test_fetch_adj_matches_quantaxis():
    if not QA_AVAILABLE:
        pytest.skip(f"QUANTAXIS import failed: {QA_IMPORT_ERROR}")

    codes = sample_codes("stock")
    if not codes:
        pytest.skip("no sample stock codes")
    code = codes[0]
    db = get_db()
    coll = db["stock_adj"]
    start, end = _date_range_for(coll, code)
    if not start or not end:
        pytest.skip("no stock_adj data")
    df_qa = QA_fetch_stock_adj(code, start, end, format="pd")
    df_we = fetch_stock_adj(code, start, end, format="pd")
    _compare_frames(df_qa, df_we)


def test_fetch_lists_match_quantaxis():
    if not QA_AVAILABLE:
        pytest.skip(f"QUANTAXIS import failed: {QA_IMPORT_ERROR}")

    qa_stock = QA_fetch_stock_list()
    we_stock = fetch_stock_list()
    assert set(qa_stock.columns) == set(we_stock.columns)

    qa_future = QA_fetch_future_list()
    we_future = fetch_future_list()
    assert set(qa_future.columns) == set(we_future.columns)

    qa_etf = QA_fetch_etf_list()
    we_etf = fetch_etf_list()
    assert set(qa_etf.columns) == set(we_etf.columns)
