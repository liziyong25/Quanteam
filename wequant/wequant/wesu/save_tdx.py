from __future__ import annotations

import datetime
import importlib
import os
import sys
from typing import Iterable

import pandas as pd
import pymongo

from ..mongo import get_db
from ..utils.trade_dates import trade_date_sse
from ..utils.qa_compat import (
    QA_util_log_info,
    QA_util_to_json_from_pandas,
    QA_util_get_next_day,
    QA_util_get_real_date,
)


def _get_client(client=None):
    return get_db() if client is None else client


def _require_qatdx():
    # QUANTAXIS is not fully compatible with pandas>=2.2 because it uses the
    # deprecated 'Q-MAR' frequency. Patch pandas so QUANTAXIS import works in
    # our py3.11 environment.
    if not getattr(pd, "_wequant_qmar_patch", False):
        _orig = pd.date_range

        def _patched(*args, **kwargs):
            if kwargs.get("freq") == "Q-MAR":
                kwargs["freq"] = "QE-MAR"
            return _orig(*args, **kwargs)

        pd.date_range = _patched
        pd._wequant_qmar_patch = True

    # Prefer the local upstream source tree (works offline and avoids importing
    # the pip-installed QUANTAXIS package, which is not py3.11-compatible).
    qa_path = os.getenv("WEQUANT_QA_PATH") or (
        r"D:\WEQUANT1\QUANTAXIS" if os.path.isdir(r"D:\WEQUANT1\QUANTAXIS") else None
    )
    if qa_path:
        sys.path.insert(0, qa_path)
        if qa_path.endswith("QUANTAXIS"):
            parent = os.path.dirname(qa_path)
            if parent and parent not in sys.path:
                sys.path.insert(0, parent)
        if "QUANTAXIS" not in sys.modules:
            pkg_dir = qa_path if qa_path.endswith("QUANTAXIS") else os.path.join(qa_path, "QUANTAXIS")
            if os.path.isdir(pkg_dir):
                import types

                mod = types.ModuleType("QUANTAXIS")
                mod.__path__ = [pkg_dir]
                sys.modules["QUANTAXIS"] = mod
    try:
        qatdx = importlib.import_module("QUANTAXIS.QAFetch.QATdx")
    except Exception as exc:  # pragma: no cover - env dependent
        raise ImportError(
            "QUANTAXIS QATdx not available; set WEQUANT_QA_PATH to QUANTAXIS root or its parent"
        ) from exc
    return qatdx


def now_time() -> str:
    """Match QASU now_time logic using trade_date_sse."""
    today = datetime.date.today()
    if datetime.datetime.now().hour < 15:
        real = QA_util_get_real_date(
            str(today - datetime.timedelta(days=1)), trade_date_sse, -1
        )
        return f"{real} 17:00:00"
    real = QA_util_get_real_date(str(today), trade_date_sse, -1)
    return f"{real} 15:00:00"


def _latest_date(coll, code: str):
    doc = coll.find_one({"code": code}, sort=[("date", -1)])
    return doc.get("date") if doc else None


def _safe_insert_many(coll, records: list[dict]) -> int:
    if not records:
        return 0
    try:
        res = coll.insert_many(records, ordered=False)
        return len(res.inserted_ids)
    except pymongo.errors.BulkWriteError as exc:  # pragma: no cover - env dependent
        details = getattr(exc, "details", None) or {}
        return int(details.get("nInserted", 0))


def QA_SU_save_stock_list(client=None, ui_log=None, ui_progress=None):
    client = _get_client(client)
    coll = client.stock_list
    coll.create_index("code")
    QA_util_log_info("save stock_list", ui_log)
    try:
        qatdx = _require_qatdx()
        df = qatdx.QA_fetch_get_stock_list()
        records = QA_util_to_json_from_pandas(df)
        if records:
            # Offline-safe: only drop when new data is available.
            client.drop_collection("stock_list")
            coll = client.stock_list
            coll.create_index("code")
            res = coll.insert_many(records)
            return len(res.inserted_ids)
    except Exception as exc:  # pragma: no cover - env dependent
        QA_util_log_info(exc, ui_log=ui_log)
    return int(coll.count_documents({}))


def QA_SU_save_index_list(client=None, ui_log=None, ui_progress=None):
    client = _get_client(client)
    coll = client.index_list
    coll.create_index("code", unique=True)
    QA_util_log_info("save index_list", ui_log)
    try:
        qatdx = _require_qatdx()
        df = qatdx.QA_fetch_get_index_list()
        records = QA_util_to_json_from_pandas(df)
        return _safe_insert_many(coll, records)
    except Exception as exc:  # pragma: no cover - env dependent
        QA_util_log_info(exc, ui_log=ui_log)
        return 0


def QA_SU_save_future_list(client=None, ui_log=None, ui_progress=None):
    client = _get_client(client)
    coll = client.future_list
    coll.create_index("code", unique=True)
    QA_util_log_info("save future_list", ui_log)
    try:
        qatdx = _require_qatdx()
        df = qatdx.QA_fetch_get_future_list()
        records = QA_util_to_json_from_pandas(df)
        return _safe_insert_many(coll, records)
    except Exception as exc:  # pragma: no cover - env dependent
        QA_util_log_info(exc, ui_log=ui_log)
        return 0


def QA_SU_save_etf_list(client=None, ui_log=None, ui_progress=None):
    client = _get_client(client)
    coll = client.etf_list
    coll.create_index("code")
    QA_util_log_info("save etf_list", ui_log)
    try:
        qatdx = _require_qatdx()
        df = qatdx.QA_fetch_get_stock_list(type_="etf")
        records = QA_util_to_json_from_pandas(df)
        if records:
            client.drop_collection("etf_list")
            coll = client.etf_list
            coll.create_index("code")
            res = coll.insert_many(records)
            return len(res.inserted_ids)
    except Exception as exc:  # pragma: no cover - env dependent
        QA_util_log_info(exc, ui_log=ui_log)
    return int(coll.count_documents({}))


def QA_SU_save_single_stock_day(code: str, client=None, ui_log=None):
    qatdx = _require_qatdx()
    client = _get_client(client)
    coll = client.stock_day
    coll.create_index([("code", pymongo.ASCENDING), ("date_stamp", pymongo.ASCENDING)])

    code = str(code)[0:6]
    end_date = str(now_time())[0:10]
    last_date = _latest_date(coll, code)
    start_date = QA_util_get_next_day(last_date) if last_date else "1990-01-01"

    QA_util_log_info(
        f"UPDATE_STOCK_DAY Trying updating {code} from {start_date} to {end_date}",
        ui_log,
    )
    if start_date != end_date:
        try:
            data = qatdx.QA_fetch_get_stock_day(code, start_date, end_date, "00")
            if data is not None and len(data) > 0:
                coll.insert_many(QA_util_to_json_from_pandas(data), ordered=False)
        except Exception as exc:  # pragma: no cover - env dependent
            QA_util_log_info(exc, ui_log=ui_log)


def QA_SU_save_stock_day(client=None, ui_log=None, ui_progress=None):
    qatdx = _require_qatdx()
    client = _get_client(client)
    stock_list = qatdx.QA_fetch_get_stock_list().code.unique().tolist()
    for code in stock_list:
        QA_SU_save_single_stock_day(code, client=client, ui_log=ui_log)


def QA_SU_save_single_future_day(code: str, client=None, ui_log=None):
    qatdx = _require_qatdx()
    client = _get_client(client)
    coll = client.future_day
    coll.create_index([("code", pymongo.ASCENDING), ("date_stamp", pymongo.ASCENDING)])

    code = str(code)
    end_date = str(now_time())[0:10]
    # QA's single future-day saver targets continuous contracts like *L8/*L9
    # and uses code[:4] for collection lookup.
    code_key = code[0:4]
    last_date = _latest_date(coll, code_key)
    start_date = QA_util_get_next_day(last_date) if last_date else "2001-01-01"

    QA_util_log_info(
        f"UPDATE_FUTURE_DAY Trying updating {code} from {start_date} to {end_date}",
        ui_log,
    )
    if start_date != end_date:
        try:
            data = qatdx.QA_fetch_get_future_day(code, start_date, end_date)
            if data is not None and len(data) > 0:
                coll.insert_many(QA_util_to_json_from_pandas(data), ordered=False)
        except Exception as exc:  # pragma: no cover - env dependent
            QA_util_log_info(exc, ui_log=ui_log)


def QA_SU_save_future_day(client=None, ui_log=None, ui_progress=None):
    qatdx = _require_qatdx()
    client = _get_client(client)
    future_list = [
        item
        for item in qatdx.QA_fetch_get_future_list().code.unique().tolist()
        if str(item)[-2:] in ["L8", "L9"]
    ]
    for code in future_list:
        QA_SU_save_single_future_day(code, client=client, ui_log=ui_log)


def QA_SU_save_future_day_all(client=None, ui_log=None, ui_progress=None):
    """Save *all* future day data (including single-month contracts).

    This mirrors QUANTAXIS.QASU.save_tdx.QA_SU_save_future_day_all.
    """
    qatdx = _require_qatdx()
    client = _get_client(client)
    coll = client.future_day
    coll.create_index([("code", pymongo.ASCENDING), ("date_stamp", pymongo.ASCENDING)])

    future_list = qatdx.QA_fetch_get_future_list().code.unique().tolist()
    end_date = str(now_time())[0:10]
    for code in future_list:
        code = str(code)
        code_key = code[0:6]

        last_date = _latest_date(coll, code_key)
        start_date = QA_util_get_next_day(last_date) if last_date else "2001-01-01"

        QA_util_log_info(
            f"UPDATE_FUTURE_DAY_ALL Trying updating {code} from {start_date} to {end_date}",
            ui_log,
        )
        if start_date != end_date:
            try:
                data = qatdx.QA_fetch_get_future_day(code, start_date, end_date)
                if data is not None and len(data) > 0:
                    coll.insert_many(QA_util_to_json_from_pandas(data), ordered=False)
            except Exception as exc:  # pragma: no cover - env dependent
                QA_util_log_info(exc, ui_log=ui_log)


def QA_SU_save_single_etf_day(code: str, client=None, ui_log=None):
    qatdx = _require_qatdx()
    client = _get_client(client)
    coll = client.index_day
    coll.create_index([("code", pymongo.ASCENDING), ("date_stamp", pymongo.ASCENDING)])

    code = str(code)[0:6]
    end_date = str(now_time())[0:10]
    last_date = _latest_date(coll, code)
    start_date = QA_util_get_next_day(last_date) if last_date else "1990-01-01"

    QA_util_log_info(
        f"UPDATE_ETF_DAY Trying updating {code} from {start_date} to {end_date}",
        ui_log,
    )
    if start_date != end_date:
        try:
            data = qatdx.QA_fetch_get_index_day(code, start_date, end_date)
            if data is not None and len(data) > 0:
                coll.insert_many(QA_util_to_json_from_pandas(data), ordered=False)
        except Exception as exc:  # pragma: no cover - env dependent
            QA_util_log_info(exc, ui_log=ui_log)


def QA_SU_save_etf_day(client=None, ui_log=None, ui_progress=None):
    qatdx = _require_qatdx()
    client = _get_client(client)
    etf_list = qatdx.QA_fetch_get_stock_list("etf").code.unique().tolist()
    for code in etf_list:
        QA_SU_save_single_etf_day(code, client=client, ui_log=ui_log)


def QA_SU_save_single_index_day(code: str, client=None, ui_log=None):
    qatdx = _require_qatdx()
    client = _get_client(client)
    coll = client.index_day
    coll.create_index([("code", pymongo.ASCENDING), ("date_stamp", pymongo.ASCENDING)])

    code = str(code)[0:6]
    end_date = str(now_time())[0:10]
    last_date = _latest_date(coll, code)
    if last_date:
        start_date = QA_util_get_next_day(last_date)
        if start_date == end_date:
            return
    else:
        start_date = "1990-01-01"

    QA_util_log_info(
        f"UPDATE_INDEX_DAY Trying updating {code} from {start_date} to {end_date}",
        ui_log,
    )
    if start_date != end_date:
        try:
            data = qatdx.QA_fetch_get_index_day(code, start_date, end_date)
            if data is not None and len(data) > 0:
                coll.insert_many(QA_util_to_json_from_pandas(data), ordered=False)
        except Exception as exc:  # pragma: no cover - env dependent
            QA_util_log_info(exc, ui_log=ui_log)


def QA_SU_save_index_day(client=None, ui_log=None, ui_progress=None):
    qatdx = _require_qatdx()
    client = _get_client(client)
    index_list = qatdx.QA_fetch_get_stock_list("index")
    if index_list is None or getattr(index_list, "empty", False):
        return 0
    for code in index_list.code.unique().tolist():
        QA_SU_save_single_index_day(code, client=client, ui_log=ui_log)
    return 0


def _update_min_series(coll, fetcher, code: str, ui_log=None):
    end_time = str(now_time())[0:19]
    for freq in ["1min", "5min", "15min", "30min", "60min"]:
        query = {"code": str(code)[0:6], "type": freq}
        last = coll.find_one(query, sort=[("time_stamp", pymongo.DESCENDING)])
        if last is None:
            last = coll.find_one(query, sort=[("datetime", pymongo.DESCENDING)])
        if last is not None and last.get("datetime"):
            start_time = str(last["datetime"])
            if start_time == end_time:
                continue
            QA_util_log_info(
                f"UPDATE_MIN {code} {freq} from {start_time} to {end_time}", ui_log
            )
            try:
                data = fetcher(str(code), start_time, end_time, freq)
                if data is not None and len(data) > 1:
                    _safe_insert_many(coll, QA_util_to_json_from_pandas(data)[1::])
            except Exception as exc:  # pragma: no cover - env dependent
                QA_util_log_info(exc, ui_log=ui_log)
        else:
            start_time = "2015-01-01"
            QA_util_log_info(
                f"INIT_MIN {code} {freq} from {start_time} to {end_time}", ui_log
            )
            try:
                data = fetcher(str(code), start_time, end_time, freq)
                if data is not None and len(data) > 1:
                    _safe_insert_many(coll, QA_util_to_json_from_pandas(data))
            except Exception as exc:  # pragma: no cover - env dependent
                QA_util_log_info(exc, ui_log=ui_log)


def QA_SU_save_stock_min(client=None, ui_log=None, ui_progress=None):
    qatdx = _require_qatdx()
    client = _get_client(client)
    coll = client.stock_min
    coll.create_index([("code", pymongo.ASCENDING), ("time_stamp", pymongo.ASCENDING), ("date_stamp", pymongo.ASCENDING)])

    stock_list = qatdx.QA_fetch_get_stock_list().code.unique().tolist()
    for code in stock_list:
        _update_min_series(coll, qatdx.QA_fetch_get_stock_min, code, ui_log=ui_log)
    return 0


def QA_SU_save_index_min(client=None, ui_log=None, ui_progress=None):
    qatdx = _require_qatdx()
    client = _get_client(client)
    coll = client.index_min
    coll.create_index([("code", pymongo.ASCENDING), ("time_stamp", pymongo.ASCENDING), ("date_stamp", pymongo.ASCENDING)])

    index_list = qatdx.QA_fetch_get_stock_list("index")
    if index_list is None or getattr(index_list, "empty", False):
        return 0
    for code in index_list.code.unique().tolist():
        _update_min_series(coll, qatdx.QA_fetch_get_index_min, code, ui_log=ui_log)
    return 0


def QA_SU_save_etf_min(client=None, ui_log=None, ui_progress=None):
    # QUANTAXIS stores ETF min in index_min
    qatdx = _require_qatdx()
    client = _get_client(client)
    coll = client.index_min
    coll.create_index([("code", pymongo.ASCENDING), ("time_stamp", pymongo.ASCENDING), ("date_stamp", pymongo.ASCENDING)])

    etf_list = qatdx.QA_fetch_get_stock_list("etf")
    if etf_list is None or getattr(etf_list, "empty", False):
        return 0
    for code in etf_list.code.unique().tolist():
        _update_min_series(coll, qatdx.QA_fetch_get_index_min, code, ui_log=ui_log)
    return 0


def QA_SU_save_future_min(client=None, ui_log=None, ui_progress=None):
    qatdx = _require_qatdx()
    client = _get_client(client)
    coll = client.future_min
    coll.create_index([("code", pymongo.ASCENDING), ("time_stamp", pymongo.ASCENDING), ("date_stamp", pymongo.ASCENDING)])

    future_list = [
        item
        for item in qatdx.QA_fetch_get_future_list().code.unique().tolist()
        if str(item)[-2:] in ["L8", "L9"]
    ]
    for code in future_list:
        _update_min_series(coll, qatdx.QA_fetch_get_future_min, code, ui_log=ui_log)
    return 0


def QA_SU_save_stock_xdxr(client=None, ui_log=None, ui_progress=None):
    """Save stock_xdxr (and ensure stock_adj indexes exist).

    Offline-safe: will not delete existing collections unless new data is fetched.
    """
    client = _get_client(client)
    coll_xdxr = client.stock_xdxr
    coll_xdxr.create_index([("code", pymongo.ASCENDING), ("date", pymongo.ASCENDING)], unique=True)
    coll_adj = client.stock_adj
    coll_adj.create_index([("code", pymongo.ASCENDING), ("date", pymongo.ASCENDING)], unique=True)

    # If we can't reach QATdx (offline), keep existing data.
    try:
        qatdx = _require_qatdx()
    except Exception as exc:  # pragma: no cover - env dependent
        QA_util_log_info(exc, ui_log=ui_log)
        return 0

    stock_list = qatdx.QA_fetch_get_stock_list().code.unique().tolist()
    for code in stock_list:
        try:
            xdxr = qatdx.QA_fetch_get_stock_xdxr(str(code))
            records = QA_util_to_json_from_pandas(xdxr)
            if records:
                _safe_insert_many(coll_xdxr, records)
        except Exception as exc:  # pragma: no cover - env dependent
            QA_util_log_info(exc, ui_log=ui_log)
    return 0

def QA_SU_save_stock_min(*_args, **_kwargs):
    raise NotImplementedError


def QA_SU_save_future_min(*_args, **_kwargs):
    raise NotImplementedError


def QA_SU_save_etf_min(*_args, **_kwargs):
    raise NotImplementedError
