from __future__ import annotations

import os
from typing import Iterable, Optional, Union

from ..mongo import get_db, collection_has_data
from .stock import fetch_stock_day

def _select_etf_day_collection(db):
    prefer = os.getenv("WEQUANT_ETF_DAY_COLLECTION")
    if prefer:
        return db[prefer]
    # QUANTAXIS: ETF day typically stored in index_day
    if "index_day" in db.list_collection_names() and collection_has_data(db["index_day"]):
        return db["index_day"]
    # fallback: stock_day may include ETF codes
    if "stock_day" in db.list_collection_names() and collection_has_data(db["stock_day"]):
        etf_code_doc = db["etf_list"].find_one({}, {"code": 1})
        if etf_code_doc and "code" in etf_code_doc:
            if db["stock_day"].find_one({"code": etf_code_doc["code"]}, {"_id": 1}):
                return db["stock_day"]
        return db["stock_day"]
    # last resort: etf_day if present
    if "etf_day" in db.list_collection_names():
        return db["etf_day"]
    return db["index_day"]

def fetch_etf_day(
    codes: Union[str, Iterable[str]],
    start: str,
    end: str,
    *,
    fields: Optional[list[str]] = None,
    adjust: str = "none",
    format: str = "pd",
) -> pd.DataFrame | list | None:
    """Fetch ETF daily bars (defaults to stock_day if etf_day is absent)."""
    db = get_db()
    coll = _select_etf_day_collection(db)
    if coll.name == "index_day":
        from .query import fetch_index_day

        return fetch_index_day(
            codes,
            start,
            end,
            format=format,
            collections=coll,
        )
    return fetch_stock_day(
        codes,
        start,
        end,
        fields=fields,
        adjust=adjust,
        format=format,
        collections=coll,
    )
