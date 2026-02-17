from __future__ import annotations

import importlib
import os
from functools import lru_cache
from types import ModuleType
from typing import Callable


def _ensure_mongo_env_defaults() -> None:
    defaults = {
        "WEQUANT_MONGO_URI": "mongodb://192.168.31.241:27017/quantaxis",
        "WEQUANT_DB_NAME": "quantaxis",
        "MONGO_URI": "mongodb://192.168.31.241:27017/quantaxis",
        "MONGO_DB_NAME": "quantaxis",
    }
    for key, value in defaults.items():
        os.environ.setdefault(key, value)


@lru_cache(maxsize=1)
def _load_mongo_fetch_module() -> ModuleType:
    _ensure_mongo_env_defaults()
    return importlib.import_module("quant_eam.qa_fetch.providers.mongo_fetch.wefetch")


def _resolve_from(module_name: str, func_name: str) -> Callable:
    mod = importlib.import_module(module_name)
    fn = getattr(mod, func_name, None)
    if callable(fn):
        return fn
    raise AttributeError(f"callable not found: {module_name}.{func_name}")


def resolve_mongo_fetch_callable(func_name: str) -> Callable:
    _ensure_mongo_env_defaults()
    try:
        from .providers.function_impl import resolve_mongo_fetch_callable as _resolve_impl

        return _resolve_impl(func_name)
    except Exception:
        pass

    mod = _load_mongo_fetch_module()
    fn = getattr(mod, func_name, None)
    if callable(fn):
        return fn

    for mod_name in (
        "quant_eam.qa_fetch.providers.mongo_fetch.wefetch.query",
        "quant_eam.qa_fetch.providers.mongo_fetch.wefetch.query_advance",
    ):
        try:
            return _resolve_from(mod_name, func_name)
        except Exception:
            continue
    raise AttributeError(f"mongo_fetch callable not found: {func_name}")
