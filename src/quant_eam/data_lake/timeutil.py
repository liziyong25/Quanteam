from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

_TZ_TAIPEI = timezone(timedelta(hours=8))


@dataclass(frozen=True)
class ParsedDT:
    raw: str
    dt: datetime


def taipei_tz() -> timezone:
    # Use fixed offset to avoid relying on system tzdata inside slim containers.
    return _TZ_TAIPEI


def parse_iso_datetime(value: str) -> datetime:
    """Parse an ISO 8601 datetime string. If tz-naive, assume Asia/Taipei (+08:00)."""
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=taipei_tz())
    return dt


def parse_daily_dt(value: Any, *, bar_close_hour: int = 16) -> ParsedDT:
    """Parse dt for ohlcv_1d.

    - If value is YYYY-MM-DD: interpret as local trading day, anchored at bar_close_hour:00:00 (+08:00).
    - Else: parse as ISO datetime; if tz-naive, assume +08:00.
    """
    if isinstance(value, datetime):
        dt = value if value.tzinfo is not None else value.replace(tzinfo=taipei_tz())
        return ParsedDT(raw=value.isoformat(), dt=dt)

    if not isinstance(value, str):
        raise ValueError(f"dt must be str or datetime (got {type(value).__name__})")

    s = value.strip()
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        # YYYY-MM-DD
        y = int(s[0:4])
        m = int(s[5:7])
        d = int(s[8:10])
        dt = datetime(y, m, d, bar_close_hour, 0, 0, tzinfo=taipei_tz())
        return ParsedDT(raw=s, dt=dt)

    dt = parse_iso_datetime(s)
    return ParsedDT(raw=s, dt=dt)


def to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=taipei_tz())
    return dt.isoformat()

