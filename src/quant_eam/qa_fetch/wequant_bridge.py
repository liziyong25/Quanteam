from __future__ import annotations

from typing import Callable

from .mongo_bridge import resolve_mongo_fetch_callable


def resolve_wequant_callable(func_name: str) -> Callable:
    # Legacy compatibility shim.
    return resolve_mongo_fetch_callable(func_name)
