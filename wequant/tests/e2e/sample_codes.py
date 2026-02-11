from __future__ import annotations

import os
import random
from typing import Iterable, List

from wequant.mongo import get_db, collection_has_data

CANDIDATE_CODE_FIELDS = ["code", "ts_code", "symbol", "stock_code", "future_code", "etf_code"]


def _detect_code_field(docs: Iterable[dict]) -> str:
    counts = {field: 0 for field in CANDIDATE_CODE_FIELDS}
    for doc in docs:
        for field in CANDIDATE_CODE_FIELDS:
            if field in doc and doc[field] not in (None, ""):
                counts[field] += 1
    best = max(counts.items(), key=lambda kv: kv[1])
    return best[0] if best[1] > 0 else "code"


def _list_collection_for(asset_type: str) -> str:
    if asset_type == "stock":
        return "stock_list"
    if asset_type == "future":
        return "future_list"
    if asset_type == "etf":
        return "etf_list"
    if asset_type == "index":
        return "index_list"
    if asset_type == "crypto":
        return "cryptocurrency_list"
    raise ValueError(f"unsupported asset_type: {asset_type}")


def _day_collection_for(asset_type: str) -> str:
    if asset_type == "stock":
        return "stock_day"
    if asset_type == "future":
        return "future_day"
    if asset_type == "etf":
        return "index_day"
    if asset_type == "index":
        return "index_day"
    if asset_type == "crypto":
        return "cryptocurrency_day"
    raise ValueError(f"unsupported asset_type: {asset_type}")


def sample_codes(asset_type: str, sample_size: int = 3, seed: int = 20250101) -> List[str]:
    """Sample codes from list collection with data present in day collection."""
    sample_size = int(os.getenv("WEQUANT_E2E_SAMPLE_SIZE", sample_size))
    seed = int(os.getenv("WEQUANT_E2E_SEED", seed))

    db = get_db()
    list_coll = db[_list_collection_for(asset_type)]
    day_coll_name = _day_collection_for(asset_type)

    # ETF fallback: index_day is preferred, fallback to stock_day/etf_day
    if asset_type == "etf":
        if day_coll_name not in db.list_collection_names() or not collection_has_data(db[day_coll_name]):
            if "stock_day" in db.list_collection_names() and collection_has_data(db["stock_day"]):
                day_coll_name = "stock_day"
            elif "etf_day" in db.list_collection_names():
                day_coll_name = "etf_day"
        else:
            etf_code_doc = db["etf_list"].find_one({}, {"code": 1})
            if etf_code_doc and "code" in etf_code_doc:
                if "stock_day" in db.list_collection_names() and db["stock_day"].find_one({"code": etf_code_doc["code"]}, {"_id": 1}):
                    day_coll_name = "stock_day"

    day_coll = db[day_coll_name]

    list_docs = list(list_coll.find({}, {field: 1 for field in CANDIDATE_CODE_FIELDS}).limit(200))
    if not list_docs:
        return []
    list_code_field = _detect_code_field(list_docs)
    codes = [doc.get(list_code_field) for doc in list_docs if doc.get(list_code_field)]
    codes = [str(c).strip() for c in codes if str(c).strip()]

    # Detect code field in day collection
    day_docs = list(day_coll.find({}, {field: 1 for field in CANDIDATE_CODE_FIELDS}).limit(50))
    day_code_field = _detect_code_field(day_docs) if day_docs else "code"

    valid = []
    for code in codes:
        if day_coll.find_one({day_code_field: code}, {"_id": 1}) is not None:
            valid.append(code)

    if not valid:
        return []
    rng = random.Random(seed)
    if len(valid) <= sample_size:
        return valid
    return rng.sample(valid, sample_size)
