from __future__ import annotations

import pandas as pd
from pymongo import UpdateOne
from ..mongo import get_db
from ..utils.codes import normalize_stock_code

def _save_list(df: pd.DataFrame, collection_name: str, *, upsert: bool, normalize) -> int:
    if df is None or df.empty:
        return 0
    db = get_db()
    coll = db[collection_name]
    coll.create_index([("code", 1)], unique=True)

    ops = []
    for row in df.to_dict("records"):
        raw_code = row.get("code") or row.get("symbol") or row.get("ts_code")
        if raw_code is None:
            continue
        code = normalize(raw_code) if normalize else str(raw_code).strip()
        row["code"] = code
        key = {"code": code}
        if upsert:
            ops.append(UpdateOne(key, {"$set": row}, upsert=True))
        else:
            ops.append(UpdateOne(key, {"$setOnInsert": row}, upsert=True))
    if not ops:
        return 0
    res = coll.bulk_write(ops, ordered=False)
    return int(res.upserted_count + res.modified_count + res.matched_count)

def save_stock_list(df: pd.DataFrame, *, upsert: bool = True) -> int:
    return _save_list(df, "stock_list", upsert=upsert, normalize=normalize_stock_code)

def save_etf_list(df: pd.DataFrame, *, upsert: bool = True) -> int:
    return _save_list(df, "etf_list", upsert=upsert, normalize=normalize_stock_code)

def save_future_list(df: pd.DataFrame, *, upsert: bool = True) -> int:
    return _save_list(df, "future_list", upsert=upsert, normalize=None)
