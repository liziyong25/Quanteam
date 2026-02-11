from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Protocol

import pandas as pd


class WequantClientProtocol(Protocol):
    def fetch_ohlcv(
        self,
        *,
        symbols: list[str],
        start: str,
        end: str,
        frequency: str,
        fields: list[str],
        **kwargs: Any,
    ) -> pd.DataFrame: ...


class RealWequantClient:
    def __init__(self) -> None:
        try:
            import wequant  # type: ignore  # noqa: F401
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(
                "wequant is not installed/available in this environment. "
                "Run with --client fake for offline demo/tests."
            ) from e

    def fetch_ohlcv(
        self,
        *,
        symbols: list[str],
        start: str,
        end: str,
        frequency: str,
        fields: list[str],
        **kwargs: Any,
    ) -> pd.DataFrame:
        # Placeholder integration point.
        # Real implementation will call the vendor SDK and return a normalized DataFrame.
        raise NotImplementedError("RealWequantClient integration is not implemented in Phase-03B MVP.")


@dataclass(frozen=True)
class FakeScenario:
    include_available_at: bool = False
    bad_available_at: bool = False
    include_duplicates: bool = False


class FakeWequantClient:
    """Deterministic offline client for tests and demo (`--client fake`)."""

    def __init__(self, scenario: FakeScenario | None = None) -> None:
        self.scenario = scenario or FakeScenario()

    def fetch_ohlcv(
        self,
        *,
        symbols: list[str],
        start: str,
        end: str,
        frequency: str,
        fields: list[str],
        **kwargs: Any,
    ) -> pd.DataFrame:
        # Deterministic, no RNG: values are pure functions of (symbol, dt index).
        # Use dt as date string (YYYY-MM-DD) to match Phase-03 daily conventions.
        dt_list = []
        s_dt = datetime.fromisoformat(start)
        e_dt = datetime.fromisoformat(end)
        cur = s_dt
        while cur <= e_dt:
            dt_list.append(cur.date().isoformat())
            cur = cur + timedelta(days=1)

        rows: list[dict[str, Any]] = []
        for si, sym in enumerate(symbols):
            for di, dt in enumerate(dt_list):
                base = 100.0 + si * 10.0 + di * 0.1
                row: dict[str, Any] = {
                    "symbol": sym,
                    "dt": dt,
                    "open": base,
                    "high": base + 1.0,
                    "low": base - 1.0,
                    "close": base + 0.5,
                    "volume": 1000 + di,
                }
                if self.scenario.include_available_at:
                    # Valid available_at should be >= bar close; use 16:00+08:00.
                    row["available_at"] = f"{dt}T16:00:00+08:00"
                    if self.scenario.bad_available_at:
                        row["available_at"] = f"{dt}T00:00:00+08:00"  # invalid vs bar close anchor
                rows.append(row)

                if self.scenario.include_duplicates and di == 0:
                    rows.append(dict(row))  # duplicate symbol+dt

        df = pd.DataFrame.from_records(rows)
        return df

