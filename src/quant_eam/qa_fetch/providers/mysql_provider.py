from __future__ import annotations

from typing import Any

from .function_impl import resolve_mysql_fetch_callable
from .mysql_fetch.utils import DATABASE_TEST2


def get_mysql_engine():
    return DATABASE_TEST2


def execute_fetch(name: str, *args: Any, **kwargs: Any) -> Any:
    fn = resolve_mysql_fetch_callable(name)
    return fn(*args, **kwargs)
