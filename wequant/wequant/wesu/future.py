from __future__ import annotations

import pandas as pd
from pymongo import UpdateOne
from ..mongo import get_db
from ..utils.dates import date_stamp, ensure_date_str

def save_future_day(df: pd.DataFrame, *, upsert: bool = True, collections=None) -> int:
    if df is None or df.empty:
        return 0

    db = get_db()
    coll = collections if collections is not None else db["future_day"]
    coll.create_index([("code", 1), ("date", 1)], unique=True)
    coll.create_index([("code", 1), ("date_stamp", 1)])

    ops = []
    for row in df.to_dict("records"):
        code = str(row.get("code")).strip()
        date_val = row.get("date") or row.get("datetime")
        if not code or date_val is None:
            continue
        date_str = ensure_date_str(date_val)
        row["code"] = code
        row["date"] = date_str
        row["date_stamp"] = date_stamp(date_str)
        if "trade" not in row:
            if "volume" in row:
                row["trade"] = row["volume"]
            elif "vol" in row:
                row["trade"] = row["vol"]
        key = {"code": code, "date": date_str}
        if upsert:
            ops.append(UpdateOne(key, {"$set": row}, upsert=True))
        else:
            ops.append(UpdateOne(key, {"$setOnInsert": row}, upsert=True))

    if not ops:
        return 0
    res = coll.bulk_write(ops, ordered=False)
    return int(res.upserted_count + res.modified_count + res.matched_count)
