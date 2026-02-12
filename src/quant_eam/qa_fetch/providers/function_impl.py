from __future__ import annotations

import datetime as _dt
from typing import Any, Callable

import pandas as pd

from .mongo_fetch.mongo import get_db as _get_mongo_db
from .mongo_fetch.wefetch import query as _wq_query
from .mongo_fetch.wefetch import query_advance as _wq_query_adv
from .mysql_fetch import bond_fetch as _wb_bond
from .mysql_fetch import report_fetch as _wb_report


def _empty_df(columns: list[str] | None = None) -> pd.DataFrame:
    return pd.DataFrame(columns=columns or [])


def _looks_like_missing_source_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    markers = (
        "unknown table",
        "doesn't exist",
        "does not exist",
        "no such table",
        "can't connect to mysql",
        "connection refused",
        "notimplemented",
        "not implemented",
        "collection",
        "no module named",
    )
    return any(marker in msg for marker in markers)


def fetch_bond_min(symbol, start, end, engine=_wb_bond.DATABASE_TEST2):
    try:
        return _wb_bond.fetch_bond_min(symbol=symbol, start=start, end=end, engine=engine)
    except Exception as exc:  # noqa: BLE001
        if not _looks_like_missing_source_error(exc):
            raise
        try:
            day = _wb_bond.fetch_bond_day(symbol=symbol, start=start, end=end, engine=engine)
        except Exception:  # noqa: BLE001
            return _empty_df(["symbol", "trade_date"])
        if day is None or getattr(day, "empty", True):
            return _empty_df(["symbol", "trade_date"])
        out = day.copy()
        if "trade_date" in out.columns:
            out["trade_date"] = pd.to_datetime(out["trade_date"], errors="coerce")
        out["source_lineage"] = "fallback:fetch_bond_day"
        return out


def fetch_cfets_repo_item(start, end, engine=_wb_bond.DATABASE_TEST2):
    try:
        return _wb_bond.fetch_cfets_repo_item(start=start, end=end, engine=engine)
    except Exception as exc:  # noqa: BLE001
        if not _looks_like_missing_source_error(exc):
            raise
        frames: list[pd.DataFrame] = []
        for fn in (
            _wb_bond.fetch_cfets_repo_buyback_item,
            _wb_bond.fetch_cfets_repo_buyout_item,
            _wb_bond.fetch_cfets_repo_side,
        ):
            try:
                df = fn(start=start, end=end, engine=engine)
            except Exception:  # noqa: BLE001
                continue
            if isinstance(df, pd.DataFrame) and not df.empty:
                frames.append(df)
        if not frames:
            return _empty_df(["trade_date"])
        out = pd.concat(frames, ignore_index=True).drop_duplicates()
        if "trade_date" in out.columns:
            out["trade_date"] = pd.to_datetime(out["trade_date"], errors="coerce")
            out = out.sort_values("trade_date")
        out["source_lineage"] = "fallback:repo_buyback+repo_buyout+repo_side"
        return out


def fetch_clean_quote(symbol, start, end, vaild_type="vaild", engine=_wb_bond.DATABASE_TEST2):
    try:
        return _wb_bond.fetch_clean_quote(
            symbol=symbol,
            start=start,
            end=end,
            vaild_type=vaild_type,
            engine=engine,
        )
    except Exception as exc:  # noqa: BLE001
        if not _looks_like_missing_source_error(exc):
            raise
        try:
            bid = _wb_bond.fetch_realtime_bid(symbol=symbol, vaild_type=vaild_type, engine=engine)
        except Exception:  # noqa: BLE001
            return _empty_df(["symbol", "trade_date"])
        if bid is None or getattr(bid, "empty", True):
            return _empty_df(["symbol", "trade_date"])
        out = bid.copy()
        if "trade_date" not in out.columns:
            if "transact_time" in out.columns:
                out["trade_date"] = pd.to_datetime(out["transact_time"], errors="coerce")
            elif "create_time" in out.columns:
                out["trade_date"] = pd.to_datetime(out["create_time"], errors="coerce")
        if "trade_date" in out.columns:
            out["trade_date"] = pd.to_datetime(out["trade_date"], errors="coerce")
            start_dt = pd.to_datetime(start, errors="coerce")
            end_dt = pd.to_datetime(end, errors="coerce")
            mask = pd.Series(True, index=out.index)
            if pd.notna(start_dt):
                mask = mask & (out["trade_date"] >= start_dt)
            if pd.notna(end_dt):
                mask = mask & (out["trade_date"] <= end_dt + pd.Timedelta(days=1))
            out = out.loc[mask]
            out = out.sort_values("trade_date")
        out["source_lineage"] = "fallback:realtime_bid"
        return out


def fetch_realtime_min(symbol, engine=_wb_bond.DATABASE_TEST2):
    try:
        return _wb_bond.fetch_realtime_min(symbol=symbol, engine=engine)
    except Exception as exc:  # noqa: BLE001
        if not _looks_like_missing_source_error(exc):
            raise
        try:
            trade = _wb_bond.fetch_realtime_transaction(symbol=symbol, engine=engine)
        except Exception:  # noqa: BLE001
            trade = None
        if isinstance(trade, pd.DataFrame) and not trade.empty:
            out = trade.copy()
            ts_col = "transact_time" if "transact_time" in out.columns else "create_time"
            if ts_col in out.columns:
                out["trade_date"] = pd.to_datetime(out[ts_col], errors="coerce").dt.floor("min")
            if "trade_date" in out.columns and "symbol" in out.columns:
                agg_cols = {}
                for col in ("price", "yield", "net_price"):
                    if col in out.columns:
                        agg_cols[col] = "last"
                if "amount" in out.columns:
                    agg_cols["amount"] = "sum"
                if "trade_volume" in out.columns:
                    agg_cols["trade_volume"] = "sum"
                if agg_cols:
                    out = (
                        out.groupby(["symbol", "trade_date"], as_index=False)
                        .agg(agg_cols)
                        .sort_values("trade_date")
                    )
            out["source_lineage"] = "fallback:realtime_trade->minute"
            return out

        try:
            bid = _wb_bond.fetch_realtime_bid(symbol=symbol, engine=engine)
        except Exception:  # noqa: BLE001
            return _empty_df(["symbol", "trade_date"])
        if bid is None or getattr(bid, "empty", True):
            return _empty_df(["symbol", "trade_date"])
        out = bid.copy()
        if "trade_date" not in out.columns:
            if "transact_time" in out.columns:
                out["trade_date"] = pd.to_datetime(out["transact_time"], errors="coerce").dt.floor("min")
            elif "create_time" in out.columns:
                out["trade_date"] = pd.to_datetime(out["create_time"], errors="coerce").dt.floor("min")
        out["source_lineage"] = "fallback:realtime_bid"
        return out


def fetch_future_tick(*args: Any, **kwargs: Any):
    try:
        return _wq_query.fetch_future_tick(*args, **kwargs)
    except Exception:  # noqa: BLE001
        return _empty_df(["code", "datetime", "price", "volume", "source_lineage"])


def fetch_quotation(code, date=_dt.date.today(), db=None):
    try:
        out = _wq_query.fetch_quotation(code, date=date, db=db)
        if out is not None:
            return out
    except Exception:  # noqa: BLE001
        pass

    database = _get_mongo_db() if db is None else db
    coll = database["realtime_quotation"]
    code_list = [code] if isinstance(code, str) else list(code)
    rows = list(coll.find({"code": {"$in": code_list}}, {"_id": 0}).limit(5000))
    if not rows:
        return _empty_df(["code", "datetime", "price"])
    df = pd.DataFrame(rows)
    if "datetime" in df.columns:
        df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    elif "date" in df.columns and "time" in df.columns:
        df["datetime"] = pd.to_datetime(
            df["date"].astype(str) + " " + df["time"].astype(str),
            errors="coerce",
        )
    return df.sort_values("datetime") if "datetime" in df.columns else df


def fetch_quotations(date=_dt.date.today(), db=None):
    try:
        out = _wq_query.fetch_quotations(date=date, db=db)
        if out is not None:
            return out
    except Exception:  # noqa: BLE001
        pass

    database = _get_mongo_db() if db is None else db
    coll = database["realtime_quotation"]
    rows = list(coll.find({}, {"_id": 0}).limit(20000))
    if not rows:
        return _empty_df(["code", "datetime", "price"])
    df = pd.DataFrame(rows)
    if "datetime" in df.columns:
        df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
        df = df.sort_values("datetime")
    return df


def _load_fetch_map(module: Any) -> dict[str, Callable]:
    out: dict[str, Callable] = {}
    for name in dir(module):
        if not name.startswith("fetch_"):
            continue
        fn = getattr(module, name, None)
        if callable(fn):
            out[name] = fn
    return out


_WBDATA_FUNCTIONS: dict[str, Callable] = {}
_WBDATA_FUNCTIONS.update(_load_fetch_map(_wb_bond))
_WBDATA_FUNCTIONS.update(_load_fetch_map(_wb_report))
_WBDATA_FUNCTIONS.update(
    {
        "fetch_bond_min": fetch_bond_min,
        "fetch_cfets_repo_item": fetch_cfets_repo_item,
        "fetch_clean_quote": fetch_clean_quote,
        "fetch_realtime_min": fetch_realtime_min,
    }
)

_WEQUANT_FUNCTIONS: dict[str, Callable] = {}
_WEQUANT_FUNCTIONS.update(_load_fetch_map(_wq_query))
_WEQUANT_FUNCTIONS.update(_load_fetch_map(_wq_query_adv))
_WEQUANT_FUNCTIONS.update(
    {
        "fetch_future_tick": fetch_future_tick,
        "fetch_quotation": fetch_quotation,
        "fetch_quotations": fetch_quotations,
    }
)


def resolve_mysql_fetch_callable(func_name: str) -> Callable:
    fn = _WBDATA_FUNCTIONS.get(func_name)
    if callable(fn):
        return fn
    raise AttributeError(f"wbdata callable not found: {func_name}")


def resolve_mongo_fetch_callable(func_name: str) -> Callable:
    fn = _WEQUANT_FUNCTIONS.get(func_name)
    if callable(fn):
        return fn
    raise AttributeError(f"wequant callable not found: {func_name}")


# One-cycle compatibility aliases.
def resolve_wbdata_local_callable(func_name: str) -> Callable:
    return resolve_mysql_fetch_callable(func_name)


def resolve_wequant_local_callable(func_name: str) -> Callable:
    return resolve_mongo_fetch_callable(func_name)
