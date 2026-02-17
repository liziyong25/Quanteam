from __future__ import annotations

from typing import Iterable, Optional, Union
import numpy as np
import pandas as pd

from ..mongo import get_db, collection_has_field
from ..utils.codes import code_to_list
from ..utils.dates import date_stamp, date_valid, ensure_date_str
from ..utils.transform import to_json_records_from_pandas

def fetch_future_day(
    codes: Union[str, Iterable[str]],
    start: str,
    end: str,
    *,
    fields: Optional[list[str]] = None,
    format: str = "pd",
    collections=None,
) -> pd.DataFrame | list | np.ndarray | None:
    """Fetch future daily bars from MongoDB (QUANTAXIS-compatible)."""
    db = get_db()
    coll = collections if collections is not None else db["future_day"]
    start_str = ensure_date_str(start)
    end_str = ensure_date_str(end)
    if not date_valid(end_str):
        print(f"WEFetch error: invalid date range start={start_str} end={end_str}")
        return None

    code_list = code_to_list(codes, auto_fill=False)
    query = {"code": {"$in": code_list}}
    if collection_has_field(coll, "date_stamp"):
        query["date_stamp"] = {"$lte": date_stamp(end_str), "$gte": date_stamp(start_str)}
    else:
        query["date"] = {"$lte": end_str, "$gte": start_str}

    proj = None
    if fields:
        base_fields = set(fields) | {"code", "date", "open", "high", "low", "close", "position", "price", "trade"}
        proj = {k: 1 for k in base_fields}

    rows = list(coll.find(query, proj or {"_id": 0}, batch_size=10000))
    if not rows:
        return None

    res = pd.DataFrame([item for item in rows])
    if "_id" in res.columns:
        res = res.drop(columns=["_id"])

    if "date" in res.columns:
        res["date"] = pd.to_datetime(res["date"])
    elif "date_stamp" in res.columns:
        res["date"] = pd.to_datetime(res["date_stamp"], unit="s")
    else:
        return None

    if "trade" not in res.columns:
        if "volume" in res.columns:
            res["trade"] = res["volume"]
        elif "vol" in res.columns:
            res["trade"] = res["vol"]

    try:
        res = res.drop_duplicates()
        res = res.set_index("date", drop=False)
        ordered = ["code", "open", "high", "low", "close", "position", "price", "trade", "date"]
        res = res.loc[:, [c for c in ordered if c in res.columns]]
    except Exception:
        return None

    fmt = format.lower()
    if fmt in ["p", "pandas", "pd"]:
        return res
    if fmt in ["json", "dict"]:
        return to_json_records_from_pandas(res)
    if fmt in ["n", "numpy"]:
        return np.asarray(res)
    if fmt in ["l", "list"]:
        return np.asarray(res).tolist()
    print(f"WEFetch error: unsupported format={format}")
    return None
