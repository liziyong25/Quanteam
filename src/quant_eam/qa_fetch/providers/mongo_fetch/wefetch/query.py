from __future__ import annotations

import datetime
import re
from typing import Any

import numpy as np
import pandas as pd
from pandas import DataFrame

from ..mongo import get_db, collection_has_field
from ..utils.codes import code_to_list
from ..utils.dates import (
    date_stamp,
    time_stamp,
    date_valid,
    ensure_date_str,
    date_str2int,
    date_int2str,
)
from ..utils.transform import to_json_records_from_pandas
from ..utils.trade_dates import trade_date_sse
from ..utils.financial_mean import financial_dict


def _get_collection(name: str, collections):
    if collections is None:
        return get_db()[name]
    return collections


def _format_result(df: pd.DataFrame | None, format: str):
    if df is None:
        return None
    fmt = format.lower()
    if fmt in ["p", "pandas", "pd"]:
        return df
    if fmt in ["json", "dict"]:
        return to_json_records_from_pandas(df)
    if fmt in ["n", "numpy"]:
        return np.asarray(df)
    if fmt in ["l", "list"]:
        return np.asarray(df).tolist()
    print(
        f"WEFetch error: format {format} is not supported; "
        "expected pd/json/numpy/list"
    )
    return None


# === QAQuery functions ===


def fetch_stock_day(code, start, end, format="numpy", frequence="day", collections=None):
    from .stock import fetch_stock_day as _impl

    return _impl(code, start, end, format=format, collections=collections)


def fetch_hkstock_day(code, start, end, format="numpy", frequence="day", collections=None):
    start = str(start)[0:10]
    end = str(end)[0:10]
    collections = _get_collection("hkstock_day", collections)
    if not date_valid(end):
        print(
            f"WEFetch error fetch_hkstock_day invalid date start={start} end={end}"
        )
        return None
    if isinstance(code, str):
        code = [code]

    cursor = collections.find(
        {
            "code": {"$in": code},
            "date_stamp": {"$lte": date_stamp(end), "$gte": date_stamp(start)},
        },
        {"_id": 0},
        batch_size=10000,
    )
    res = pd.DataFrame([item for item in cursor])
    try:
        res = (
            res.assign(date=pd.to_datetime(res.date))
            .drop_duplicates(["date", "code"])
            .query("amount>1")
            .set_index("date", drop=False)
        )
        res = res.loc[
            :, ["code", "open", "high", "low", "close", "trade", "amount", "date"]
        ]
    except Exception:
        res = None
    return _format_result(res, format)


def fetch_dk_data(code, start, end, format="numpy", frequence="day", collections=None):
    collections = _get_collection("dk_data", collections)
    if not date_valid(end):
        return None

    if isinstance(code, str):
        code = [code]

    # DK data in some deployments stores `datetime` as YYYYMMDD; normalize the query bounds
    # so callers can use YYYY-MM-DD consistently.
    start_q = start
    end_q = end
    sample = collections.find_one({}, {"datetime": 1})
    sample_dt = None if not sample else sample.get("datetime")
    if isinstance(sample_dt, int):
        sample_dt = str(sample_dt)
    if isinstance(sample_dt, str) and len(sample_dt) == 8 and sample_dt.isdigit():
        start_q = str(date_str2int(str(start)[0:10]))
        end_q = str(date_str2int(str(end)[0:10]))

    cursor = collections.find(
        {"code": {"$in": code}, "datetime": {"$lte": end_q, "$gte": start_q}},
        {"_id": 0},
        batch_size=10000,
    )
    res = pd.DataFrame([item for item in cursor])
    if res.empty:
        return None
    res = (
        res.assign(date=pd.to_datetime(res["datetime"]))
        .drop_duplicates(["date", "code"], keep="last")
        .sort_values("date")
    )
    return _format_result(res, format)


def _fetch_dk_by_trade_date(
    collection_name: str,
    code,
    start,
    end,
    *,
    code_field: str = "code",
    code_values=None,
    fields: list[str] | None = None,
    format: str = "pd",
    collections=None,
):
    """Generic fetch for DK-like tables stored with trade_date='YYYYMMDD'."""

    coll = _get_collection(collection_name, collections)

    start_str = ensure_date_str(start)
    end_str = ensure_date_str(end)
    if not date_valid(end_str):
        return None

    start_q = str(date_str2int(start_str))
    end_q = str(date_str2int(end_str))

    if code_values is None:
        if isinstance(code, str):
            code_values = [code]
        else:
            code_values = list(code) if code is not None else []

    query = {code_field: {"$in": code_values}, "trade_date": {"$lte": end_q, "$gte": start_q}}

    proj = None
    if fields:
        base_fields = set(fields) | {"trade_date", "datetime", "code", "base_code", "type", "R_value", "L_value"}
        proj = {k: 1 for k in base_fields}

    rows = list(coll.find(query, proj or {"_id": 0}, batch_size=10000))
    if not rows:
        return None

    res = pd.DataFrame([item for item in rows])
    if "_id" in res.columns:
        res = res.drop(columns=["_id"])

    if "trade_date" in res.columns:
        res["date"] = pd.to_datetime(res["trade_date"])
        res = res.drop_duplicates(["date", "code"], keep="last").sort_values("date")
    return _format_result(res, format)


def fetch_stock_dk(code, start, end, format="numpy", frequence="day", collections=None):
    codes = code_to_list(code, auto_fill=True)
    return _fetch_dk_by_trade_date(
        "stock_dk",
        code,
        start,
        end,
        code_field="base_code",
        code_values=codes,
        format=format,
        collections=collections,
    )


def fetch_etf_dk(code, start, end, format="numpy", frequence="day", collections=None):
    codes = code_to_list(code, auto_fill=True)
    return _fetch_dk_by_trade_date(
        "etf_dk",
        code,
        start,
        end,
        code_field="base_code",
        code_values=codes,
        format=format,
        collections=collections,
    )


def fetch_index_dk(code, start, end, format="numpy", frequence="day", collections=None):
    codes = code_to_list(code, auto_fill=True)
    return _fetch_dk_by_trade_date(
        "index_dk",
        code,
        start,
        end,
        code_field="base_code",
        code_values=codes,
        format=format,
        collections=collections,
    )


def fetch_lof_dk(code, start, end, format="numpy", frequence="day", collections=None):
    codes = code_to_list(code, auto_fill=True)
    return _fetch_dk_by_trade_date(
        "lof_dk",
        code,
        start,
        end,
        code_field="base_code",
        code_values=codes,
        format=format,
        collections=collections,
    )


def fetch_reits_dk(code, start, end, format="numpy", frequence="day", collections=None):
    codes = code_to_list(code, auto_fill=True)
    return _fetch_dk_by_trade_date(
        "reits_dk",
        code,
        start,
        end,
        code_field="base_code",
        code_values=codes,
        format=format,
        collections=collections,
    )


def fetch_future_dk(code, start, end, format="numpy", frequence="day", collections=None):
    if isinstance(code, str):
        codes = [code.strip().upper()]
    else:
        codes = [str(x).strip().upper() for x in (list(code) if code is not None else [])]
    return _fetch_dk_by_trade_date(
        "future_dk",
        code,
        start,
        end,
        code_field="code",
        code_values=codes,
        format=format,
        collections=collections,
    )


def fetch_hkstock_dk(code, start, end, format="numpy", frequence="day", collections=None):
    if isinstance(code, str):
        codes_in = [code]
    else:
        codes_in = list(code) if code is not None else []

    codes: list[str] = []
    for c in codes_in:
        s = str(c).strip()
        s = re.sub(r"\.0$", "", s)
        if s.isdigit() and len(s) < 5:
            s = s.zfill(5)
        codes.append(s)

    return _fetch_dk_by_trade_date(
        "hkstock_dk",
        code,
        start,
        end,
        code_field="code",
        code_values=codes,
        format=format,
        collections=collections,
    )


def fetch_get_hkstock_list(package=None):
    """Best-effort HK stock list for notebooks and legacy QA demos.

    QUANTAXIS provides QA_fetch_get_hkstock_list via QATdx. In WEQUANT we avoid
    network dependency and derive the list from local MongoDB:
    - Prefer DK data codes that look like HK tickers (5-digit numeric strings)
    - Fallback to distinct codes from hkstock_day
    """

    db = get_db()
    # Prefer codes already present in hkstock_dk (DK global -> HK stock)
    if "hkstock_dk" in db.list_collection_names():
        codes = db["hkstock_dk"].distinct("code")
        hk_codes = sorted(
            {
                str(c)
                for c in codes
                if c is not None and isinstance(c, (str, int)) and str(c).isdigit() and len(str(c)) == 5
            }
        )
        if hk_codes:
            return pd.DataFrame({"code": hk_codes, "name": hk_codes}).set_index("code", drop=False)
    # Prefer codes already present in dk_data (ensures downstream dk fetches have data)
    if "dk_data" in db.list_collection_names():
        codes = db["dk_data"].distinct("code")
        hk_codes = sorted(
            {
                str(c)
                for c in codes
                if c is not None and isinstance(c, (str, int)) and str(c).isdigit() and len(str(c)) == 5
            }
        )
        if hk_codes:
            return pd.DataFrame({"code": hk_codes, "name": hk_codes}).set_index(
                "code", drop=False
            )
    if "hkstock_day" in db.list_collection_names():
        codes = sorted({str(c) for c in db["hkstock_day"].distinct("code") if c is not None})
        if codes:
            return pd.DataFrame({"code": codes, "name": codes}).set_index("code", drop=False)
    return pd.DataFrame(columns=["code", "name"]).set_index("code", drop=False)


def fetch_stock_adj(code, start, end, format="pd", collections=None):
    from .adj import fetch_stock_adj as _impl

    return _impl(code, start, end, format=format, collections=collections)


def fetch_stock_realtime_min(
    code, format="numpy", frequence="1min", collections=None
):
    collections = collections or _get_collection(
        f"realtime_kline_{datetime.date.today()}", None
    )
    if code is not None:
        code = code_to_list(code)
        items = [
            item
            for item in collections.find(
                {"code": {"$in": code}, "type": frequence}
            )
        ]
        if not items:
            print(
                f"WEFetch error fetch_stock_realtime_min code={code} collection={collections.name} return None"
            )
        data = pd.DataFrame(items)
        return data
    return None


def fetch_stock_min(
    code,
    start,
    end,
    format="numpy",
    frequence="1min",
    collections=None,
):
    if frequence in ["1min", "1m"]:
        frequence = "1min"
    elif frequence in ["5min", "5m"]:
        frequence = "5min"
    elif frequence in ["15min", "15m"]:
        frequence = "15min"
    elif frequence in ["30min", "30m"]:
        frequence = "30min"
    elif frequence in ["60min", "60m"]:
        frequence = "60min"
    else:
        print(
            f"WEFetch error fetch_stock_min frequence={frequence} not supported"
        )

    code = code_to_list(code)
    collections = _get_collection("stock_min", collections)
    cursor = collections.find(
        {
            "code": {"$in": code},
            "time_stamp": {"$gte": time_stamp(start), "$lte": time_stamp(end)},
            "type": frequence,
        },
        {"_id": 0},
        batch_size=10000,
    )
    res = pd.DataFrame([item for item in cursor])
    try:
        res = (
            res.assign(volume=res.vol, datetime=pd.to_datetime(res.datetime))
            .query("volume>1")
            .drop_duplicates(["datetime", "code"])
            .set_index("datetime", drop=False)
        )
    except Exception:
        res = None
    return _format_result(res, format)


def fetch_stock_transaction(
    code, start, end, format="numpy", frequence="tick", collections=None
):
    if frequence not in ["tick", "TICK", "transaction"]:
        print(
            f"WEFetch error fetch_stock_transaction frequence={frequence} not supported"
        )
    code = code_to_list(code)
    collections = _get_collection("stock_transaction", collections)
    cursor = collections.find(
        {
            "code": {"$in": code},
            "time_stamp": {"$gte": time_stamp(start), "$lte": time_stamp(end)},
            "type": frequence,
        },
        {"_id": 0},
        batch_size=10000,
    )
    res = pd.DataFrame([item for item in cursor])
    try:
        res = (
            res.assign(volume=res.vol, datetime=pd.to_datetime(res.datetime))
            .query("volume>1")
            .drop_duplicates(["datetime", "code"])
            .set_index("datetime", drop=False)
        )
    except Exception:
        res = None
    return _format_result(res, format)


def fetch_index_transaction(
    code, start, end, format="numpy", frequence="tick", collections=None
):
    if frequence not in ["tick", "TICK", "transaction"]:
        print(
            f"WEFetch error fetch_index_transaction frequence={frequence} not supported"
        )
    code = code_to_list(code)
    collections = _get_collection("index_transaction", collections)
    cursor = collections.find(
        {
            "code": {"$in": code},
            "time_stamp": {"$gte": time_stamp(start), "$lte": time_stamp(end)},
            "type": frequence,
        },
        {"_id": 0},
        batch_size=10000,
    )
    res = pd.DataFrame([item for item in cursor])
    try:
        res = (
            res.assign(volume=res.vol, datetime=pd.to_datetime(res.datetime))
            .query("volume>1")
            .drop_duplicates(["datetime", "code"])
            .set_index("datetime", drop=False)
        )
    except Exception:
        res = None
    return _format_result(res, format)


def fetch_trade_date():
    return trade_date_sse


def fetch_stock_list(collections=None):
    from .lists import fetch_stock_list as _impl

    return _impl() if collections is None else pd.DataFrame(
        [item for item in collections.find()]
    ).drop("_id", axis=1, inplace=False).set_index("code", drop=False)


def fetch_etf_list(collections=None):
    from .lists import fetch_etf_list as _impl

    return _impl() if collections is None else pd.DataFrame(
        [item for item in collections.find()]
    ).drop("_id", axis=1, inplace=False).set_index("code", drop=False)


def fetch_index_list(collections=None):
    collections = _get_collection("index_list", collections)
    return (
        pd.DataFrame([item for item in collections.find()])
        .drop("_id", axis=1, inplace=False)
        .set_index("code", drop=False)
    )


def fetch_stock_terminated(collections=None):
    collections = _get_collection("stock_terminated", collections)
    return (
        pd.DataFrame([item for item in collections.find()])
        .drop("_id", axis=1, inplace=False)
        .set_index("code", drop=False)
    )


def fetch_stock_basic_info_tushare(collections=None):
    collections = _get_collection("stock_info_tushare", collections)
    return [item for item in collections.find()]


def fetch_stock_to_market_date(stock_code):
    items = fetch_stock_basic_info_tushare()
    for row in items:
        if row.get("code") == stock_code:
            return row.get("timeToMarket")
    return None


def fetch_stock_full(date, format="numpy", collections=None):
    date_str = str(date)[0:10]
    collections = _get_collection("stock_day", collections)
    if not date_valid(date_str):
        print(f"WEFetch error fetch_stock_full invalid date={date_str}")
        return None
    if collection_has_field(collections, "date_stamp"):
        cursor = collections.find({"date_stamp": date_stamp(date_str)}, batch_size=10000)
    else:
        cursor = collections.find({"date": date_str}, batch_size=10000)
    _data = []
    for item in cursor:
        _data.append(
            [
                str(item["code"]),
                float(item["open"]),
                float(item["high"]),
                float(item["low"]),
                float(item["close"]),
                float(item.get("vol", item.get("volume", 0))),
                item["date"],
            ]
        )
    if format in ["n", "N", "numpy"]:
        return np.asarray(_data)
    if format in ["list", "l", "L"]:
        return _data
    if format in ["P", "p", "pandas", "pd"]:
        df = DataFrame(
            _data,
            columns=["code", "open", "high", "low", "close", "volume", "date"],
        )
        df["date"] = pd.to_datetime(df["date"])
        return df.set_index("date", drop=False)
    print(f"WEFetch error fetch_stock_full format={format} not supported")
    return None


def fetch_index_day(code, start, end, format="numpy", collections=None):
    start = str(start)[0:10]
    end = str(end)[0:10]
    code = code_to_list(code)
    collections = _get_collection("index_day", collections)
    if not date_valid(end):
        print(
            f"WEFetch error fetch_index_day invalid date start={start} end={end}"
        )
        return None
    cursor = collections.find(
        {
            "code": {"$in": code},
            "date_stamp": {"$lte": date_stamp(end), "$gte": date_stamp(start)},
        },
        {"_id": 0},
        batch_size=10000,
    )
    res = pd.DataFrame([item for item in cursor])
    try:
        res = (
            res.assign(volume=res.vol, date=pd.to_datetime(res.date))
            .drop_duplicates(["date", "code"])
            .set_index("date", drop=False)
        )
    except Exception:
        res = None
    return _format_result(res, format)


def fetch_index_min(
    code, start, end, format="numpy", frequence="1min", collections=None
):
    if frequence in ["1min", "1m"]:
        frequence = "1min"
    elif frequence in ["5min", "5m"]:
        frequence = "5min"
    elif frequence in ["15min", "15m"]:
        frequence = "15min"
    elif frequence in ["30min", "30m"]:
        frequence = "30min"
    elif frequence in ["60min", "60m"]:
        frequence = "60min"
    else:
        print(
            f"WEFetch error fetch_index_min frequence={frequence} not supported"
        )

    code = code_to_list(code)
    collections = _get_collection("index_min", collections)
    cursor = collections.find(
        {
            "code": {"$in": code},
            "time_stamp": {"$gte": time_stamp(start), "$lte": time_stamp(end)},
            "type": frequence,
        },
        {"_id": 0},
        batch_size=10000,
    )
    res = pd.DataFrame([item for item in cursor])
    try:
        res = (
            res.assign(volume=res.vol, datetime=pd.to_datetime(res.datetime))
            .drop_duplicates(["datetime", "code"])
            .set_index("datetime", drop=False)
        )
    except Exception:
        res = None
    return _format_result(res, format)


def fetch_future_day(code, start, end, format="numpy", collections=None):
    from .future import fetch_future_day as _impl

    return _impl(code, start, end, format=format, collections=collections)


def fetch_future_min(
    code, start, end, format="numpy", frequence="1min", collections=None
):
    if frequence in ["1min", "1m"]:
        frequence = "1min"
    elif frequence in ["5min", "5m"]:
        frequence = "5min"
    elif frequence in ["15min", "15m"]:
        frequence = "15min"
    elif frequence in ["30min", "30m"]:
        frequence = "30min"
    elif frequence in ["60min", "60m"]:
        frequence = "60min"

    code = code_to_list(code, auto_fill=False)
    collections = _get_collection("future_min", collections)
    cursor = collections.find(
        {
            "code": {"$in": code},
            "time_stamp": {"$gte": time_stamp(start), "$lte": time_stamp(end)},
            "type": frequence,
        },
        batch_size=10000,
    )
    if format in ["dict", "json"]:
        return [data for data in cursor]
    _data = []
    for item in cursor:
        _data.append(
            [
                str(item["code"]),
                float(item["open"]),
                float(item["high"]),
                float(item["low"]),
                float(item["close"]),
                float(item.get("position", 0)),
                float(item.get("price", 0)),
                float(item.get("trade", item.get("volume", 0))),
                item["datetime"],
                item["tradetime"],
                item["time_stamp"],
                item["date"],
                item["type"],
            ]
        )
    df = DataFrame(
        _data,
        columns=[
            "code",
            "open",
            "high",
            "low",
            "close",
            "position",
            "price",
            "trade",
            "datetime",
            "tradetime",
            "time_stamp",
            "date",
            "type",
        ],
    )
    df = (
        df.assign(datetime=pd.to_datetime(df["datetime"]))
        .drop_duplicates(["datetime", "code"])
        .set_index("datetime", drop=False)
    )
    if format in ["numpy", "np", "n"]:
        return np.asarray(df)
    if format in ["list", "l", "L"]:
        return np.asarray(df).tolist()
    if format in ["P", "p", "pandas", "pd"]:
        return df
    return None


def fetch_future_list(collections=None):
    from .lists import fetch_future_list as _impl

    return _impl() if collections is None else pd.DataFrame(
        [item for item in collections.find()]
    ).drop("_id", axis=1, inplace=False).set_index("code", drop=False)


def fetch_ctp_future_list(collections=None):
    collections = _get_collection("ctp_future_list", collections)
    return (
        pd.DataFrame([item for item in collections.find()])
        .drop("_id", axis=1, inplace=False)
        .set_index("code", drop=False)
    )


def fetch_future_tick():
    raise NotImplementedError


def fetch_ctp_tick(code, start, end, frequence, format="pd", collections=None):
    collections = _get_collection("ctp_tick", collections)
    code = code_to_list(code, auto_fill=False)
    cursor = collections.find(
        {
            "InstrumentID": {"$in": code},
            "time_stamp": {"$gte": time_stamp(start), "$lte": time_stamp(end)},
        }
    )
    data = pd.DataFrame([item for item in cursor])
    if data is None or data.empty:
        return None
    data["datetime"] = pd.to_datetime(
        data["date"].astype(str) + " " + data["time"].astype(str)
    )
    return data.set_index("datetime", drop=False)


def fetch_stock_xdxr(code, format="pd", collections=None):
    collections = _get_collection("stock_xdxr", collections)
    code = code_to_list(code)
    data = (
        pd.DataFrame(
            [
                item
                for item in collections.find({"code": {"$in": code}}, batch_size=10000)
            ]
        )
        .drop(["_id"], axis=1)
    )
    data["date"] = pd.to_datetime(data["date"])
    return data.set_index("date", drop=False)


def fetch_backtest_info(
    user=None, account_cookie=None, strategy=None, stock_list=None, collections=None
):
    collections = _get_collection("backtest_info", collections)
    query = to_json_records_from_pandas(
        pd.DataFrame(
            [user, account_cookie, strategy, stock_list],
            index=["user", "account_cookie", "strategy", "stock_list"],
        )
        .dropna()
        .T
    )[0]
    return to_json_records_from_pandas(
        pd.DataFrame([item for item in collections.find(query)]).drop(["_id"], axis=1)
    )


def fetch_backtest_history(cookie=None, collections=None):
    collections = _get_collection("backtest_history", collections)
    query = to_json_records_from_pandas(
        pd.DataFrame([cookie], index=["cookie"]).dropna().T
    )[0]
    return to_json_records_from_pandas(
        pd.DataFrame([item for item in collections.find(query)]).drop(["_id"], axis=1)
    )


def fetch_stock_block(code=None, format="pd", collections=None):
    collections = _get_collection("stock_block", collections)
    if code is not None:
        code = code_to_list(code)
        data = (
            pd.DataFrame(
                [
                    item
                    for item in collections.find({"code": {"$in": code}}, batch_size=10000)
                ]
            )
            .drop(["_id"], axis=1)
        )
        return data.set_index("code", drop=False)
    data = pd.DataFrame([item for item in collections.find()]).drop(["_id"], axis=1)
    return data.set_index("code", drop=False)


def fetch_stock_block_history(
    code=None, start="2000-01-01", end="2025-01-01", format="pd", collections=None
):
    collections = _get_collection("stock_block_history", collections)
    if code is not None:
        code = code_to_list(code)
        data = pd.DataFrame(
            [
                item
                for item in collections.find(
                    {"code": {"$in": code}, "updateDate": {"$lte": end, "$gte": start}},
                    batch_size=10000,
                )
            ]
        ).drop(["_id"], axis=1)
        return data.set_index("code", drop=False)
    data = pd.DataFrame(
        [item for item in collections.find({"updateDate": {"$lte": end, "$gte": start}})]
    ).drop(["_id"], axis=1)
    return data.set_index("code", drop=False)


def fetch_stock_block_slice_history(code=None, format="pd", collections=None):
    collections = _get_collection("stock_block_slice_history", collections)
    if code is not None:
        code = code_to_list(code)
        data = pd.DataFrame(
            [
                item
                for item in collections.find({"code": {"$in": code}}, batch_size=10000)
            ]
        ).drop(["_id"], axis=1)
        return data.set_index("code", drop=False)
    data = pd.DataFrame([item for item in collections.find()]).drop(["_id"], axis=1)
    return data.set_index("code", drop=False)


def fetch_stock_info(code, format="pd", collections=None):
    collections = _get_collection("stock_info", collections)
    code = code_to_list(code)
    try:
        data = pd.DataFrame(
            [
                item
                for item in collections.find(
                    {"code": {"$in": code}}, {"_id": 0}, batch_size=10000
                )
            ]
        )
        return data.set_index("code", drop=False)
    except Exception as e:
        print(e)
        return None


def fetch_stock_name(code, collections=None):
    collections = _get_collection("stock_list", collections)
    if isinstance(code, str):
        try:
            res = collections.find_one({"code": code})
            return res["name"]
        except Exception as e:
            if res is None:
                print("WEFetch error: stock_list collection is empty")
            print(e)
            return code
    if isinstance(code, list):
        code = code_to_list(code)
        data = pd.DataFrame(
            [
                item
                for item in collections.find(
                    {"code": {"$in": code}}, {"_id": 0}, batch_size=10000
                )
            ]
        )
        return data.set_index("code", drop=False)


def fetch_index_name(code, collections=None):
    collections = _get_collection("index_list", collections)
    if isinstance(code, str):
        try:
            return collections.find_one({"code": code})["name"]
        except Exception as e:
            print(e)
            return code
    if isinstance(code, list):
        code = code_to_list(code)
        data = pd.DataFrame(
            [
                item
                for item in collections.find(
                    {"code": {"$in": code}}, {"_id": 0}, batch_size=10000
                )
            ]
        )
        return data.set_index("code", drop=False)


def fetch_etf_name(code, collections=None):
    collections = _get_collection("etf_list", collections)
    if isinstance(code, str):
        try:
            return collections.find_one({"code": code})["name"]
        except Exception as e:
            print(e)
            return code
    if isinstance(code, list):
        code = code_to_list(code)
        data = pd.DataFrame(
            [
                item
                for item in collections.find(
                    {"code": {"$in": code}}, {"_id": 0}, batch_size=10000
                )
            ]
        )
        return data.set_index("code", drop=False)


def fetch_quotation(code, date=datetime.date.today(), db=None):
    db = get_db() if db is None else db
    try:
        collections = db.get_collection(f"realtime_{date}")
        data = pd.DataFrame(
            [
                item
                for item in collections.find(
                    {"code": code}, {"_id": 0}, batch_size=10000
                )
            ]
        )
        return (
            data.assign(
                date=pd.to_datetime(data.datetime.apply(lambda x: str(x)[0:10])),
                datetime=pd.to_datetime(data.datetime),
            )
            .set_index("datetime", drop=False)
            .sort_index()
        )
    except Exception as e:
        raise e


def fetch_quotations(date=datetime.date.today(), db=None):
    db = get_db() if db is None else db
    try:
        collections = db.get_collection(f"realtime_{date}")
        data = pd.DataFrame(
            [item for item in collections.find({}, {"_id": 0}, batch_size=10000)]
        )
        return (
            data.assign(
                date=pd.to_datetime(data.datetime.apply(lambda x: str(x)[0:10]))
            )
            .assign(datetime=pd.to_datetime(data.datetime))
            .set_index(["datetime", "code"], drop=False)
            .sort_index()
        )
    except Exception as e:
        raise e


def fetch_account(message: dict = {}, db=None):
    db = get_db() if db is None else db
    collection = db.account
    return [res for res in collection.find(message, {"_id": 0})]


def fetch_risk(message: dict = {}, params: dict | None = None, db=None):
    db = get_db() if db is None else db
    params = params or {
        "_id": 0,
        "assets": 0,
        "timeindex": 0,
        "totaltimeindex": 0,
        "benchmark_assets": 0,
        "month_profit": 0,
    }
    collection = db.risk
    return [res for res in collection.find(message, params)]


def fetch_user(user_cookie, db=None):
    db = get_db() if db is None else db
    collection = db.account
    return [
        res for res in collection.find({"user_cookie": user_cookie}, {"_id": 0})
    ]


def fetch_strategy(message: dict = {}, db=None):
    db = get_db() if db is None else db
    collection = db.strategy
    return [res for res in collection.find(message, {"_id": 0})]


def fetch_lhb(date, db=None):
    db = get_db() if db is None else db
    try:
        collections = db.lhb
        return (
            pd.DataFrame([item for item in collections.find({"date": date}, {"_id": 0})])
            .set_index("code", drop=False)
            .sort_index()
        )
    except Exception as e:
        raise e


def fetch_financial_report(code, report_date, ltype="EN", db=None):
    db = get_db() if db is None else db
    if isinstance(code, str):
        code = [code]
    if isinstance(report_date, str):
        report_date = [date_str2int(report_date)]
    elif isinstance(report_date, int):
        report_date = [report_date]
    elif isinstance(report_date, list):
        report_date = [date_str2int(item) for item in report_date]

    collection = db.financial
    num_columns = [item[:3] for item in list(financial_dict.keys())]
    CH_columns = [item[3:] for item in list(financial_dict.keys())]
    EN_columns = list(financial_dict.values())

    try:
        if code is not None and report_date is not None:
            data = [
                item
                for item in collection.find(
                    {"code": {"$in": code}, "report_date": {"$in": report_date}},
                    {"_id": 0},
                    batch_size=10000,
                )
            ]
        elif code is None and report_date is not None:
            data = [
                item
                for item in collection.find(
                    {"report_date": {"$in": report_date}},
                    {"_id": 0},
                    batch_size=10000,
                )
            ]
        elif code is not None and report_date is None:
            data = [
                item
                for item in collection.find(
                    {"code": {"$in": code}}, {"_id": 0}, batch_size=10000
                )
            ]
        else:
            data = [item for item in collection.find({}, {"_id": 0})]

        if len(data) > 0:
            res_pd = pd.DataFrame(data)
            if ltype in ["CH", "CN"]:
                cndict = dict(zip(num_columns, CH_columns))
                cndict["code"] = "code"
                cndict["report_date"] = "report_date"
                res_pd.columns = res_pd.columns.map(lambda x: cndict[x])
            elif ltype == "EN":
                endict = dict(zip(num_columns, EN_columns))
                endict["code"] = "code"
                endict["report_date"] = "report_date"
                res_pd.columns = res_pd.columns.map(lambda x: endict[x])

            if res_pd.report_date.dtype == np.int64:
                res_pd.report_date = pd.to_datetime(
                    res_pd.report_date.apply(date_int2str)
                )
            else:
                res_pd.report_date = pd.to_datetime(res_pd.report_date)
            return res_pd.replace(-4.039810335e34, np.nan).set_index(
                ["report_date", "code"], drop=False
            )
        return None
    except Exception as e:
        raise e


def fetch_stock_financial_calendar(
    code, start, end=None, format="pd", collections=None
):
    code = code_to_list(code)
    collections = _get_collection("report_calendar", collections)
    if not date_valid(end):
        print(
            f"WEFetch error fetch_stock_financial_calendar invalid date start={start} end={end}"
        )
        return None
    cursor = collections.find(
        {"code": {"$in": code}, "real_date": {"$lte": end, "$gte": start}},
        {"_id": 0},
        batch_size=10000,
    )
    res = pd.DataFrame([item for item in cursor])
    try:
        res = res.drop_duplicates(["report_date", "code"])
        res = res.loc[
            :,
            [
                "code",
                "name",
                "pre_date",
                "first_date",
                "second_date",
                "third_date",
                "real_date",
                "codes",
                "report_date",
                "crawl_date",
            ],
        ]
    except Exception:
        res = None
    return _format_result(res, format)


def fetch_stock_divyield(code, start, end=None, format="pd", collections=None):
    code = code_to_list(code)
    collections = _get_collection("stock_divyield", collections)
    if not date_valid(end):
        print(
            f"WEFetch error fetch_stock_divyield invalid date start={start} end={end}"
        )
        return None
    cursor = collections.find(
        {"a_stockcode": {"$in": code}, "dir_dcl_date": {"$lte": end, "$gte": start}},
        {"_id": 0},
        batch_size=10000,
    )
    res = pd.DataFrame([item for item in cursor])
    try:
        res = res.drop_duplicates(["dir_dcl_date", "a_stockcode"])
        res = res.loc[
            :,
            [
                "a_stockcode",
                "a_stocksname",
                "div_info",
                "div_type_code",
                "bonus_shr",
                "cash_bt",
                "cap_shr",
                "epsp",
                "ps_cr",
                "ps_up",
                "reg_date",
                "dir_dcl_date",
                "a_stockcode1",
                "ex_divi_date",
                "prg",
            ],
        ]
    except Exception:
        res = None
    return _format_result(res, format)


def fetch_cryptocurrency_list(market=None, collections=None):
    collections = _get_collection("cryptocurrency_list", collections)
    if market is None:
        cryptocurrency_list = pd.DataFrame([item for item in collections.find({})])
        if len(cryptocurrency_list) > 0:
            return cryptocurrency_list.drop("_id", axis=1, inplace=False).set_index(
                "symbol", drop=False
            )
        return pd.DataFrame(
            columns=[
                "symbol",
                "name",
                "market",
                "state",
                "category",
                "base_currency",
                "quote_currency",
                "price_precision",
                "desc",
            ]
        )
    cryptocurrency_list = pd.DataFrame(
        [item for item in collections.find({"market": market})]
    )
    if len(cryptocurrency_list) > 0:
        return cryptocurrency_list.drop("_id", axis=1, inplace=False).set_index(
            "symbol", drop=False
        )
    return pd.DataFrame(
        columns=[
            "symbol",
            "name",
            "market",
            "state",
            "category",
            "base_currency",
            "quote_currency",
            "price_precision",
            "desc",
        ]
    )


def fetch_cryptocurrency_day(code, start, end, format="numpy", collections=None):
    start = str(start)[0:10]
    end = str(end)[0:10]
    code = code_to_list(code, auto_fill=False)
    collections = _get_collection("cryptocurrency_day", collections)
    if date_valid(end):
        cursor = collections.find(
            {
                "symbol": {"$in": code},
                "date_stamp": {"$lte": date_stamp(end), "$gte": date_stamp(start)},
            },
            {"_id": 0},
            batch_size=10000,
        )
        if format in ["dict", "json"]:
            return [data for data in cursor]
        _data = []
        for item in cursor:
            _data.append(
                [
                    str(item["symbol"]),
                    float(item["open"]),
                    float(item["high"]),
                    float(item["low"]),
                    float(item["close"]),
                    float(item["volume"]),
                    float(item["trade"]),
                    float(item["amount"]),
                    item["date"],
                ]
            )
        if format in ["n", "N", "numpy"]:
            return np.asarray(_data)
        if format in ["list", "l", "L"]:
            return _data
        if format in ["P", "p", "pandas", "pd"]:
            df = DataFrame(
                _data,
                columns=[
                    "code",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "trade",
                    "amount",
                    "date",
                ],
            ).drop_duplicates(["date", "code"])
            df["date"] = pd.to_datetime(df["date"])
            return df.set_index("date", drop=False)
        print(
            f"WEFetch error fetch_cryptocurrency_day format={format} not supported"
        )
    else:
        print("WEFetch error fetch_cryptocurrency_day invalid date")


def fetch_cryptocurrency_min(
    code, start, end, format="numpy", frequence="1min", collections=None
):
    if frequence in ["1min", "1m"]:
        frequence = "1min"
    elif frequence in ["5min", "5m"]:
        frequence = "5min"
    elif frequence in ["15min", "15m"]:
        frequence = "15min"
    elif frequence in ["30min", "30m"]:
        frequence = "30min"
    elif frequence in ["60min", "60m"]:
        frequence = "60min"

    code = code_to_list(code, auto_fill=False)
    collections = _get_collection("cryptocurrency_min", collections)
    cursor = collections.find(
        {
            "symbol": {"$in": code},
            "time_stamp": {"$gte": time_stamp(start), "$lte": time_stamp(end)},
            "type": frequence,
        },
        batch_size=10000,
    )
    if format in ["dict", "json"]:
        return [data for data in cursor]
    _data = []
    for item in cursor:
        _data.append(
            [
                str(item["symbol"]),
                float(item["open"]) if item["open"] is not None else item["open"],
                float(item["high"]) if item["high"] is not None else item["high"],
                float(item["low"]) if item["low"] is not None else item["low"],
                float(item["close"]) if item["close"] is not None else item["close"],
                float(item["volume"]) if item["volume"] is not None else item["volume"],
                float(item["trade"]) if item["trade"] is not None else item["trade"],
                float(item["amount"]) if item["amount"] is not None else item["amount"],
                item["time_stamp"],
                item["date"],
                item["datetime"],
                item["type"],
            ]
        )
    df = DataFrame(
        _data,
        columns=[
            "code",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "trade",
            "amount",
            "time_stamp",
            "date",
            "datetime",
            "type",
        ],
    )
    df = (
        df.assign(datetime=pd.to_datetime(df["datetime"]))
        .drop_duplicates(["datetime", "code"])
        .set_index("datetime", drop=False)
    )
    if format in ["numpy", "np", "n"]:
        return np.asarray(df)
    if format in ["list", "l", "L"]:
        return np.asarray(df).tolist()
    if format in ["P", "p", "pandas", "pd"]:
        return df
    return None


# QA_ prefixed aliases for compatibility
QA_fetch_stock_day = fetch_stock_day
QA_fetch_hkstock_day = fetch_hkstock_day
QA_fetch_dk_data = fetch_dk_data
QA_fetch_stock_dk = fetch_stock_dk
QA_fetch_etf_dk = fetch_etf_dk
QA_fetch_index_dk = fetch_index_dk
QA_fetch_lof_dk = fetch_lof_dk
QA_fetch_reits_dk = fetch_reits_dk
QA_fetch_future_dk = fetch_future_dk
QA_fetch_hkstock_dk = fetch_hkstock_dk
QA_fetch_stock_adj = fetch_stock_adj
QA_fetch_stock_realtime_min = fetch_stock_realtime_min
QA_fetch_stock_min = fetch_stock_min
QA_fetch_stock_transaction = fetch_stock_transaction
QA_fetch_index_transaction = fetch_index_transaction
QA_fetch_trade_date = fetch_trade_date
QA_fetch_stock_list = fetch_stock_list
QA_fetch_etf_list = fetch_etf_list
QA_fetch_index_list = fetch_index_list
QA_fetch_stock_terminated = fetch_stock_terminated
QA_fetch_stock_basic_info_tushare = fetch_stock_basic_info_tushare
QA_fetch_stock_to_market_date = fetch_stock_to_market_date
QA_fetch_stock_full = fetch_stock_full
QA_fetch_index_day = fetch_index_day
QA_fetch_index_min = fetch_index_min
QA_fetch_future_day = fetch_future_day
QA_fetch_future_min = fetch_future_min
QA_fetch_future_list = fetch_future_list
QA_fetch_ctp_future_list = fetch_ctp_future_list
QA_fetch_future_tick = fetch_future_tick
QA_fetch_ctp_tick = fetch_ctp_tick
QA_fetch_stock_xdxr = fetch_stock_xdxr
QA_fetch_backtest_info = fetch_backtest_info
QA_fetch_backtest_history = fetch_backtest_history
QA_fetch_stock_block = fetch_stock_block
QA_fetch_stock_block_history = fetch_stock_block_history
QA_fetch_stock_block_slice_history = fetch_stock_block_slice_history
QA_fetch_stock_info = fetch_stock_info
QA_fetch_stock_name = fetch_stock_name
QA_fetch_index_name = fetch_index_name
QA_fetch_etf_name = fetch_etf_name
QA_fetch_quotation = fetch_quotation
QA_fetch_quotations = fetch_quotations
QA_fetch_account = fetch_account
QA_fetch_risk = fetch_risk
QA_fetch_user = fetch_user
QA_fetch_strategy = fetch_strategy
QA_fetch_lhb = fetch_lhb
QA_fetch_financial_report = fetch_financial_report
QA_fetch_stock_financial_calendar = fetch_stock_financial_calendar
QA_fetch_stock_divyield = fetch_stock_divyield
QA_fetch_cryptocurrency_list = fetch_cryptocurrency_list
QA_fetch_cryptocurrency_day = fetch_cryptocurrency_day
QA_fetch_cryptocurrency_min = fetch_cryptocurrency_min
