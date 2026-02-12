from __future__ import annotations

from typing import Any

from .function_impl import resolve_mongo_fetch_callable
from .mongo_fetch.mongo import get_db


def get_mongo_db():
    return get_db()


def execute_fetch(name: str, *args: Any, **kwargs: Any) -> Any:
    fn = resolve_mongo_fetch_callable(name)
    return fn(*args, **kwargs)
