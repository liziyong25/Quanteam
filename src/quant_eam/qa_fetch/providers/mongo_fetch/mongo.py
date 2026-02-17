"""MongoDB connection helpers."""

from __future__ import annotations

from pymongo import MongoClient
from .config import load_mongo_config

def get_client() -> MongoClient:
    cfg = load_mongo_config()
    return MongoClient(cfg.uri)

def get_db():
    cfg = load_mongo_config()
    return get_client()[cfg.db_name]

def collection_has_field(coll, field: str) -> bool:
    try:
        doc = coll.find_one({field: {"$exists": True}}, {field: 1})
        return bool(doc) and field in doc
    except Exception:
        return False

def collection_has_data(coll) -> bool:
    try:
        return coll.find_one({}, {"_id": 1}) is not None
    except Exception:
        return False
