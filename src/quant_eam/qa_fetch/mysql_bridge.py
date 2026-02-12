from __future__ import annotations

import os
from typing import Callable


def _ensure_mysql_env_defaults() -> None:
    defaults = {
        "DB_NAME": "test2",
        "DB_NAME_TEST2": "test2",
        "DB_USER": "root",
        "DB_PASSWORD": "liziyong25",
        "DB_HOST": "192.168.31.241",
        "DB_PORT": "3306",
    }
    for key, value in defaults.items():
        os.environ.setdefault(key, value)


def resolve_mysql_fetch_callable(func_name: str) -> Callable:
    _ensure_mysql_env_defaults()
    from .providers.function_impl import resolve_mysql_fetch_callable as _resolve_impl

    return _resolve_impl(func_name)
