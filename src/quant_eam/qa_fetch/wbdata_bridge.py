from __future__ import annotations

from typing import Callable

from .mysql_bridge import resolve_mysql_fetch_callable


def resolve_wbdata_callable(func_name: str) -> Callable:
    # Legacy compatibility shim.
    return resolve_mysql_fetch_callable(func_name)
