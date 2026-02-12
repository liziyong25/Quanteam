from __future__ import annotations

from datetime import date

import pandas as pd
from sqlalchemy import text

from .utils import DATABASE_TEST2


def _normalize_date_to_date(value, *, name: str) -> date | None:
    if value is None or value == "":
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    if parsed is pd.NaT:
        raise ValueError(f"{name} is not a valid date string: {value!r}")
    if parsed.tzinfo is not None:
        parsed = parsed.tz_convert(None)
    return parsed.date()


def fetch_wb_report_daily_inc_bond(
    symbol="all",
    start: str | None = None,
    end: str | None = None,
    engine=DATABASE_TEST2,
):
    """
    Fetch daily incremental bond report cache from wb_report_daily_inc_bond (test2).

    Signature (contract):
    - symbol: "all" | str | list[str]
    - start/end: "YYYY-MM-DD"
    - engine: sqlalchemy engine (default DATABASE_TEST2)
    """
    target_engine = engine or DATABASE_TEST2
    start_date = _normalize_date_to_date(start, name="start")
    end_date = _normalize_date_to_date(end, name="end")

    filters: list[str] = []
    params: dict[str, object] = {}

    if start_date is not None:
        filters.append("trade_date >= :start_date")
        params["start_date"] = start_date
    if end_date is not None:
        filters.append("trade_date <= :end_date")
        params["end_date"] = end_date

    if symbol != "all":
        if isinstance(symbol, str):
            symbols_list = [symbol]
        else:
            symbols_list = list(symbol)
        if not symbols_list:
            return pd.DataFrame()
        placeholders = ", ".join([f":symbol_{i}" for i in range(len(symbols_list))])
        filters.append(f"symbol IN ({placeholders})")
        params.update({f"symbol_{i}": s for i, s in enumerate(symbols_list)})

    where_clause = " AND ".join(filters) if filters else "1=1"
    sql_query = text(f"SELECT * FROM wb_report_daily_inc_bond WHERE {where_clause}")
    df = pd.read_sql_query(sql_query, target_engine, params=params)
    if df.empty:
        return df

    if "trade_date" in df.columns:
        df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
    sort_cols = [c for c in ["trade_date", "symbol"] if c in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols)
    return df.drop_duplicates()

