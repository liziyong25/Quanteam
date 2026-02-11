from __future__ import annotations

from typing import Iterable, Optional, Union
import numpy as np
import pandas as pd

from ..mongo import get_db
from ..utils.codes import code_to_list
from ..utils.dates import date_valid, ensure_date_str
from ..utils.transform import to_json_records_from_pandas

def fetch_stock_adj(
    codes: Union[str, Iterable[str]],
    start: str,
    end: str,
    *,
    fields: Optional[list[str]] = None,
    format: str = "pd",
    collections=None,
) -> pd.DataFrame | list | np.ndarray | None:
    """Fetch stock adjustment factors (QUANTAXIS-compatible)."""
    db = get_db()
    coll = collections if collections is not None else db["stock_adj"]
    start_str = ensure_date_str(start)
    end_str = ensure_date_str(end)
    if not date_valid(end_str):
        print(f"WEFetch error: invalid date range start={start_str} end={end_str}")
        return None

    code_list = code_to_list(codes, auto_fill=True)
    query = {"code": {"$in": code_list}, "date": {"$lte": end_str, "$gte": start_str}}
    proj = None
    if fields:
        base_fields = set(fields) | {"code", "date", "adj"}
        proj = {k: 1 for k in base_fields}

    rows = list(coll.find(query, proj or {"_id": 0}, batch_size=10000))
    if not rows:
        return None

    res = pd.DataFrame([item for item in rows])
    if "_id" in res.columns:
        res = res.drop(columns=["_id"])
    if "date" not in res.columns:
        return None
    res["date"] = pd.to_datetime(res["date"])
    res = res.set_index("date", drop=False)

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
