from __future__ import annotations

import pandas as pd
from ..mongo import get_db

def _fetch_list(collection_name: str) -> pd.DataFrame:
    db = get_db()
    rows = list(db[collection_name].find({}, {"_id": 0}))
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    if "code" in df.columns:
        df = df.set_index("code", drop=False)
    return df

def fetch_stock_list() -> pd.DataFrame:
    return _fetch_list("stock_list")

def fetch_etf_list() -> pd.DataFrame:
    return _fetch_list("etf_list")

def fetch_future_list() -> pd.DataFrame:
    return _fetch_list("future_list")
