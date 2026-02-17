"""Configuration contract for WEQUANT.

NOTE:
- Do not hardcode secrets.
- Prefer environment variables for runtime configuration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

@dataclass(frozen=True)
class MongoConfig:
    uri: str
    db_name: str

def load_mongo_config() -> MongoConfig:
    uri = os.getenv(
        "WEQUANT_MONGO_URI",
        "mongodb://192.168.31.241:27017/quantaxis",
    )
    db_name = os.getenv("WEQUANT_DB_NAME", "quantaxis")
    return MongoConfig(uri=uri, db_name=db_name)
