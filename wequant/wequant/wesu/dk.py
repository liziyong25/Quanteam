from __future__ import annotations

import re

import pandas as pd
from pymongo import UpdateOne

from ..mongo import get_db


_DATE_YYYYMMDD_RE = re.compile(r"^\d{8}$")


def _normalize_dk_datetime(value) -> str:
    """Normalize dk_data datetime to YYYYMMDD string.

    Existing workspaces may store dk_data.datetime as either:
    - "YYYYMMDD" (string or int)
    - "YYYY-MM-DD" (string)
    - datetime-like objects
    """

    if value is None:
        return ""
    if isinstance(value, (int, float)) and not pd.isna(value):
        s = str(int(value))
        return s if _DATE_YYYYMMDD_RE.match(s) else s

    s = str(value).strip()
    if _DATE_YYYYMMDD_RE.match(s):
        return s
    if len(s) >= 10 and s[4] in "-/" and s[7] in "-/":
        return s[:10].replace("-", "").replace("/", "")
    try:
        return pd.Timestamp(value).strftime("%Y%m%d")
    except Exception:
        return s


def save_dk_data(
    df: pd.DataFrame,
    *,
    upsert: bool = True,
    collection_name: str = "dk_data",
    code_field: str = "code",
    datetime_field: str = "datetime",
    collections=None,
) -> int:
    """Idempotent save for dk_data (custom DK dataset used in notebooks).

    Key: (code, datetime). Uses bulk upsert to avoid duplicates.
    """

    if df is None or df.empty:
        return 0

    db = get_db()
    coll = collections if collections is not None else db[collection_name]

    # Keep indexes non-unique to avoid breaking existing DBs with legacy duplicates.
    coll.create_index([("code", 1)])
    coll.create_index([("datetime", 1)])
    coll.create_index([("code", 1), ("datetime", 1)])

    ops: list[UpdateOne] = []
    for row in df.to_dict("records"):
        code = row.get(code_field)
        dt = row.get(datetime_field) or row.get("date")
        if code is None or dt is None:
            continue
        code_s = str(code).strip()
        dt_s = _normalize_dk_datetime(dt)
        if not code_s or not dt_s:
            continue
        row["code"] = code_s
        row["datetime"] = dt_s
        key = {"code": code_s, "datetime": dt_s}
        if upsert:
            ops.append(UpdateOne(key, {"$set": row}, upsert=True))
        else:
            ops.append(UpdateOne(key, {"$setOnInsert": row}, upsert=True))

    if not ops:
        return 0

    res = coll.bulk_write(ops, ordered=False)
    return int(res.upserted_count + res.modified_count + res.matched_count)

