from __future__ import annotations

from typing import Any


SOURCE_MONGO = "mongo_fetch"
SOURCE_MYSQL = "mysql_fetch"

_SOURCE_ALIASES = {
    SOURCE_MONGO: SOURCE_MONGO,
    SOURCE_MYSQL: SOURCE_MYSQL,
    # Legacy labels kept for one-cycle compatibility.
    "wequant": SOURCE_MONGO,
    "wbdata": SOURCE_MYSQL,
}


def normalize_source(value: Any) -> str | None:
    if value is None:
        return None
    token = str(value).strip().lower()
    if not token:
        return None
    return _SOURCE_ALIASES.get(token)


def is_mongo_source(value: Any) -> bool:
    return normalize_source(value) == SOURCE_MONGO


def is_mysql_source(value: Any) -> bool:
    return normalize_source(value) == SOURCE_MYSQL
