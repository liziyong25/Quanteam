from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from quant_eam.backtest.vectorbt_adapter_mvp import BacktestInvalid, BacktestResult


ADAPTER_ID_CURVE_COMPOSER_V1 = "curve_composer_v1"


def _sharpe_from_equity(equity: pd.Series, periods_per_year: int = 252) -> float | None:
    if len(equity) < 3:
        return None
    r = equity.pct_change().dropna()
    if r.empty:
        return None
    mu = float(r.mean())
    sigma = float(r.std(ddof=1))
    if sigma == 0.0:
        return None
    return (mu / sigma) * math.sqrt(periods_per_year)


def _max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    peak = equity.cummax()
    dd = (equity / peak) - 1.0
    return float(dd.min())


def _load_curve_csv(path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise BacktestInvalid(f"missing curve.csv: {path.as_posix()}")
    df = pd.read_csv(path)
    if "dt" not in df.columns or "equity" not in df.columns:
        raise BacktestInvalid("curve.csv must have columns: dt,equity")
    df = df[["dt", "equity"]].copy()
    df["dt"] = pd.to_datetime(df["dt"], errors="coerce")
    if df["dt"].isna().any():
        raise BacktestInvalid("curve.csv has invalid dt values")
    df["equity"] = pd.to_numeric(df["equity"], errors="coerce")
    if df["equity"].isna().any():
        raise BacktestInvalid("curve.csv has invalid equity values")
    df = df.sort_values(["dt"], kind="mergesort").drop_duplicates(subset=["dt"], keep="last").reset_index(drop=True)
    if df.empty:
        raise BacktestInvalid("curve.csv has 0 rows after parsing")
    return df


@dataclass(frozen=True)
class CurveComposerStats:
    aligned_rows: int
    dt_start: str
    dt_end: str
    original_points: list[int]


def compose_curves(
    *,
    dossier_dirs: list[Path],
    weights: list[float],
    align: str = "intersection",
    base_equity: float = 1.0,
) -> tuple[BacktestResult, CurveComposerStats]:
    """Compose component equity curves into a portfolio curve.

    MVP rules:
    - Read each component's `curve.csv` (dt,equity).
    - Align on dt by intersection (default).
    - Compute per-component returns on the aligned dt grid.
    - Compose returns = sum_i w_i * r_i, then rebuild composed equity from base_equity.
    """
    if align != "intersection":
        raise BacktestInvalid(f"unsupported align rule: {align!r} (only 'intersection' supported in v1)")
    if len(dossier_dirs) != len(weights) or not dossier_dirs:
        raise BacktestInvalid("dossier_dirs and weights must have same non-zero length")
    if base_equity <= 0:
        raise BacktestInvalid("base_equity must be > 0")

    # Normalize weights deterministically.
    w = [float(x) for x in weights]
    s = float(sum(w))
    if s <= 0:
        raise BacktestInvalid("weights sum must be > 0")
    w = [x / s for x in w]

    curves: list[pd.DataFrame] = []
    dt_sets: list[set[pd.Timestamp]] = []
    original_points: list[int] = []
    for d in dossier_dirs:
        cdf = _load_curve_csv(Path(d) / "curve.csv")
        curves.append(cdf)
        original_points.append(int(len(cdf)))
        dt_sets.append(set(cdf["dt"].tolist()))

    common = set.intersection(*dt_sets) if dt_sets else set()
    if not common:
        raise BacktestInvalid("no common dt intersection across component curves")
    dt_common = sorted(common)

    # Build aligned equity matrix.
    eq_cols: list[pd.Series] = []
    for df in curves:
        aligned = df[df["dt"].isin(dt_common)].set_index("dt").reindex(dt_common)
        if aligned["equity"].isna().any():
            # Should not happen under intersection, but keep error explicit.
            raise BacktestInvalid("alignment produced NaN equity values")
        eq_cols.append(aligned["equity"].astype(float))

    # Per-component returns on the aligned grid.
    # Return at dt_common[k] refers to change from dt_common[k-1] -> dt_common[k].
    rets = [col.pct_change().fillna(0.0) for col in eq_cols]
    # Compose returns.
    comp_ret = rets[0] * 0.0
    for wi, ri in zip(w, rets, strict=True):
        comp_ret = comp_ret + (ri * wi)

    # Rebuild equity from composed returns, anchored at base_equity on dt_common[0].
    equity = [float(base_equity)]
    for k in range(1, len(dt_common)):
        equity.append(equity[-1] * (1.0 + float(comp_ret.iloc[k])))

    curve_df = pd.DataFrame({"dt": [t.isoformat() for t in dt_common], "equity": equity})

    total_return = float(equity[-1] / base_equity - 1.0) if equity else 0.0
    stats: dict[str, Any] = {
        "adapter_id": ADAPTER_ID_CURVE_COMPOSER_V1,
        "strategy_id": "curve_level_sleeve_mvp",
        "align": align,
        "base_equity": float(base_equity),
        "total_return": float(total_return),
        "max_drawdown": _max_drawdown(curve_df["equity"]),
        "sharpe": _sharpe_from_equity(curve_df["equity"]),
        "trade_count": 0,
    }

    trades_df = pd.DataFrame(columns=["symbol", "entry_dt", "exit_dt", "pnl", "qty", "fees"])
    out = BacktestResult(equity_curve=curve_df, trades=trades_df, stats=stats)
    cc = CurveComposerStats(
        aligned_rows=int(len(dt_common)),
        dt_start=str(dt_common[0].date().isoformat()),
        dt_end=str(dt_common[-1].date().isoformat()),
        original_points=original_points,
    )
    return out, cc
