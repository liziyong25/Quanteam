from __future__ import annotations

import datetime as _dt
import time as _time
import pandas as pd

from .trade_dates import trade_date_sse

def to_timestamp(x) -> pd.Timestamp:
    """Parse input into normalized (00:00:00) Timestamp."""
    ts = pd.to_datetime(x)
    return ts.normalize()

def date_str(ts: pd.Timestamp) -> str:
    return ts.strftime("%Y-%m-%d")

def date_valid(date_str_value: str) -> bool:
    try:
        _time.strptime(str(date_str_value)[0:10], "%Y-%m-%d")
        return True
    except Exception:
        return False

def date_str2int(date_str_value: str | int) -> int:
    if isinstance(date_str_value, int):
        return date_str_value
    return int(str(date_str_value).replace("-", ""))

def date_int2str(int_date: int | str) -> str:
    s = str(int_date)
    if len(s) == 8:
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    return s

def date_stamp(date_value) -> float:
    """Convert date string to unix timestamp (seconds) for date_stamp."""
    datestr = pd.Timestamp(date_value).strftime("%Y-%m-%d")
    return _time.mktime(_time.strptime(datestr, "%Y-%m-%d"))

def time_stamp(time_value) -> float:
    """Convert datetime string to unix timestamp (seconds)."""
    s = str(time_value)
    if len(s) == 10:
        return _time.mktime(_time.strptime(s, "%Y-%m-%d"))
    if len(s) == 16:
        return _time.mktime(_time.strptime(s, "%Y-%m-%d %H:%M"))
    return _time.mktime(_time.strptime(s[0:19], "%Y-%m-%d %H:%M:%S"))

def ensure_date_str(value) -> str:
    """Normalize date-like input to YYYY-MM-DD string."""
    return pd.Timestamp(value).strftime("%Y-%m-%d")

def datetime_to_strdate(dt: _dt.datetime) -> str:
    return f"{dt.year:04d}-{dt.month:02d}-{dt.day:02d}"

def add_months(dt: _dt.datetime, months: int) -> _dt.datetime:
    month = dt.month - 1 + months
    year = dt.year + month // 12
    month = month % 12 + 1
    day = min(dt.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
                       31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return _dt.datetime(year, month, day)

def get_between_quarter(start: str, end: str):
    """Generate quarter boundaries between start and end (inclusive)."""
    start_dt = pd.Timestamp(start).to_pydatetime()
    end_dt = pd.Timestamp(end).to_pydatetime()
    quarters = pd.period_range(start=start_dt, end=end_dt, freq="Q")
    return {str(q): str(q.end_time.date()) for q in quarters}


def get_next_day(date: str, n: int = 1) -> str:
    """Return the next trading day in trade_date_sse."""
    date = str(date)[0:10]
    if date in trade_date_sse:
        idx = trade_date_sse.index(date)
        idx = min(idx + n, len(trade_date_sse) - 1)
        return trade_date_sse[idx]
    for d in trade_date_sse:
        if d > date:
            return d
    return trade_date_sse[-1]


def get_real_date(date: str, trade_list: list[str] | None = None, towards: int = -1) -> str:
    """Find nearest real trade date in trade_list (default trade_date_sse)."""
    trade_list = trade_date_sse if trade_list is None else trade_list
    date = str(date)[0:10]
    if date in trade_list:
        return date
    dt = pd.Timestamp(date)
    step = 1 if towards == 1 else -1
    for _ in range(4000):
        dt = dt + pd.Timedelta(days=step)
        d = dt.strftime("%Y-%m-%d")
        if d in trade_list:
            return d
    return date

# QAUtil.QADate month_data equivalent (pandas >=2 uses QE-* aliases)
try:
    month_data = pd.date_range("1/1/1996", "12/31/2023", freq="Q-MAR").astype(str).tolist()
except ValueError:
    month_data = pd.date_range("1/1/1996", "12/31/2023", freq="QE-MAR").astype(str).tolist()
