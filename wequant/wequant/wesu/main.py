from __future__ import annotations

from typing import Any

from ..mongo import get_db
from . import save_tdx, save_tdx_parallelism


def _get_client(client=None):
    return get_db() if client is None else client


def select_save_engine(engine: Any, *, paralleled: bool = False):
    """
    QUANTAXIS-compatible engine selector.

    - engine can be a string (e.g. 'tdx') or a module-like object providing
      QA_SU_save_* functions.
    """
    if not isinstance(engine, str):
        return engine

    if engine in ["tdx"]:
        return save_tdx_parallelism if paralleled else save_tdx

    raise NotImplementedError(f"unsupported save engine: {engine!r}")


def QA_SU_save_stock_list(engine: Any = "tdx", client=None, ui_log=None, ui_progress=None):
    eng = select_save_engine(engine, paralleled=False)
    return eng.QA_SU_save_stock_list(client=_get_client(client), ui_log=ui_log, ui_progress=ui_progress)


def QA_SU_save_future_list(engine: Any = "tdx", client=None, ui_log=None, ui_progress=None):
    eng = select_save_engine(engine, paralleled=False)
    return eng.QA_SU_save_future_list(client=_get_client(client), ui_log=ui_log, ui_progress=ui_progress)


def QA_SU_save_etf_list(engine: Any = "tdx", client=None, ui_log=None, ui_progress=None):
    eng = select_save_engine(engine, paralleled=False)
    return eng.QA_SU_save_etf_list(client=_get_client(client), ui_log=ui_log, ui_progress=ui_progress)


def QA_SU_save_index_list(engine: Any = "tdx", client=None, ui_log=None, ui_progress=None):
    eng = select_save_engine(engine, paralleled=False)
    return eng.QA_SU_save_index_list(client=_get_client(client), ui_log=ui_log, ui_progress=ui_progress)


def QA_SU_save_single_stock_day(
    code,
    engine: Any = "tdx",
    client=None,
    paralleled: bool = False,
    ui_log=None,
):
    eng = select_save_engine(engine, paralleled=paralleled)
    return eng.QA_SU_save_single_stock_day(code=code, client=_get_client(client), ui_log=ui_log)


def QA_SU_save_stock_day(
    engine: Any = "tdx",
    client=None,
    paralleled: bool = False,
    ui_log=None,
    ui_progress=None,
):
    eng = select_save_engine(engine, paralleled=paralleled)
    return eng.QA_SU_save_stock_day(client=_get_client(client), ui_log=ui_log, ui_progress=ui_progress)


def QA_SU_save_stock_min(
    engine: Any = "tdx",
    client=None,
    paralleled: bool = False,
    ui_log=None,
    ui_progress=None,
):
    eng = select_save_engine(engine, paralleled=paralleled)
    return eng.QA_SU_save_stock_min(client=_get_client(client), ui_log=ui_log, ui_progress=ui_progress)


def QA_SU_save_single_future_day(
    code,
    engine: Any = "tdx",
    client=None,
    paralleled: bool = False,
    ui_log=None,
):
    eng = select_save_engine(engine, paralleled=paralleled)
    return eng.QA_SU_save_single_future_day(code=code, client=_get_client(client), ui_log=ui_log)


def QA_SU_save_future_day(
    engine: Any = "tdx",
    client=None,
    paralleled: bool = False,
    ui_log=None,
    ui_progress=None,
):
    eng = select_save_engine(engine, paralleled=paralleled)
    return eng.QA_SU_save_future_day(client=_get_client(client), ui_log=ui_log, ui_progress=ui_progress)


def QA_SU_save_future_min(
    engine: Any = "tdx",
    client=None,
    paralleled: bool = False,
    ui_log=None,
    ui_progress=None,
):
    eng = select_save_engine(engine, paralleled=paralleled)
    return eng.QA_SU_save_future_min(client=_get_client(client), ui_log=ui_log, ui_progress=ui_progress)


def QA_SU_save_future_day_all(engine: Any = "tdx", client=None, ui_log=None, ui_progress=None):
    eng = select_save_engine(engine, paralleled=False)
    return eng.QA_SU_save_future_day_all(client=_get_client(client), ui_log=ui_log, ui_progress=ui_progress)


def QA_SU_save_single_etf_day(
    code,
    engine: Any = "tdx",
    client=None,
    paralleled: bool = False,
    ui_log=None,
):
    eng = select_save_engine(engine, paralleled=paralleled)
    return eng.QA_SU_save_single_etf_day(code=code, client=_get_client(client), ui_log=ui_log)


def QA_SU_save_etf_day(
    engine: Any = "tdx",
    client=None,
    paralleled: bool = False,
    ui_log=None,
    ui_progress=None,
):
    eng = select_save_engine(engine, paralleled=paralleled)
    return eng.QA_SU_save_etf_day(client=_get_client(client), ui_log=ui_log, ui_progress=ui_progress)


def QA_SU_save_etf_min(
    engine: Any = "tdx",
    client=None,
    paralleled: bool = False,
    ui_log=None,
    ui_progress=None,
):
    eng = select_save_engine(engine, paralleled=paralleled)
    return eng.QA_SU_save_etf_min(client=_get_client(client), ui_log=ui_log, ui_progress=ui_progress)


def QA_SU_save_index_day(
    engine: Any = "tdx",
    client=None,
    paralleled: bool = False,
    ui_log=None,
    ui_progress=None,
):
    eng = select_save_engine(engine, paralleled=paralleled)
    return eng.QA_SU_save_index_day(client=_get_client(client), ui_log=ui_log, ui_progress=ui_progress)


def QA_SU_save_index_min(
    engine: Any = "tdx",
    client=None,
    paralleled: bool = False,
    ui_log=None,
    ui_progress=None,
):
    eng = select_save_engine(engine, paralleled=paralleled)
    return eng.QA_SU_save_index_min(client=_get_client(client), ui_log=ui_log, ui_progress=ui_progress)


def QA_SU_save_stock_xdxr(engine: Any = "tdx", client=None, ui_log=None, ui_progress=None):
    eng = select_save_engine(engine, paralleled=False)
    return eng.QA_SU_save_stock_xdxr(client=_get_client(client), ui_log=ui_log, ui_progress=ui_progress)
