from __future__ import annotations

import os
import pandas as pd
from ..mongo import get_db, collection_has_data
from .stock import save_stock_day

def _select_etf_day_collection(db):
    prefer = os.getenv("WEQUANT_ETF_DAY_COLLECTION")
    if prefer:
        return db[prefer]
    if "etf_day" not in db.list_collection_names():
        return db["stock_day"]
    if not collection_has_data(db["etf_day"]):
        return db["stock_day"]
    etf_code_doc = db["etf_list"].find_one({}, {"code": 1})
    if etf_code_doc and "code" in etf_code_doc:
        if db["stock_day"].find_one({"code": etf_code_doc["code"]}, {"_id": 1}):
            return db["stock_day"]
    return db["etf_day"]

def save_etf_day(df: pd.DataFrame, *, upsert: bool = True) -> int:
    """Save ETF daily bars (defaults to stock_day if etf_day is absent)."""
    db = get_db()
    coll = _select_etf_day_collection(db)
    return save_stock_day(df, upsert=upsert, collections=coll)
