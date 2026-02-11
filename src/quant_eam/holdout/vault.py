from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from quant_eam.backtest.vectorbt_adapter_mvp import BacktestInvalid, BacktestResult, run_adapter
from quant_eam.gates.util import Segment, query_prices_df


@dataclass(frozen=True)
class HoldoutResult:
    passed: bool
    summary: str
    metrics_minimal: dict[str, Any]


class HoldoutInvalid(ValueError):
    pass


def evaluate_holdout_minimal(
    *,
    data_root: Path | None,
    snapshot_id: str,
    dataset_id: str,
    symbols: list[str],
    seg: Segment,
    adapter_id: str,
    lag_bars: int,
    execution_policy: dict[str, Any],
    cost_policy: dict[str, Any],
    params: dict[str, Any] | None = None,
) -> HoldoutResult:
    """Run holdout evaluation but return only pass/fail + minimal summary (no curves/trades output)."""
    params = params or {}
    prices, _stats = query_prices_df(
        data_root=data_root,
        snapshot_id=snapshot_id,
        symbols=symbols,
        seg=seg,
        dataset_id=dataset_id,
    )
    try:
        bt: BacktestResult = run_adapter(
            adapter_id=adapter_id,
            prices=prices,
            lag_bars=lag_bars,
            execution_policy=deepcopy(execution_policy),
            cost_policy=deepcopy(cost_policy),
        )
    except BacktestInvalid as e:
        raise HoldoutInvalid(str(e)) from e

    tr = bt.stats.get("total_return")
    try:
        tr_f = float(tr) if tr is not None else 0.0
    except Exception:
        tr_f = 0.0

    # Minimal pass/fail rule: configurable via gate params.
    # Default is permissive (pass) to avoid accidental leakage-driven optimization pressure in MVP.
    min_total_return = params.get("min_total_return")
    if min_total_return is None:
        passed = True
        summary = "holdout evaluated (minimal output); no threshold configured"
    else:
        try:
            thr = float(min_total_return)
        except Exception as e:
            raise HoldoutInvalid("min_total_return must be a number") from e
        passed = tr_f >= thr
        summary = f"holdout total_return={tr_f:.6f} threshold={thr:.6f}"

    metrics_minimal: dict[str, Any] = {
        "total_return": tr_f,
        "trade_count": int(bt.stats.get("trade_count") or 0),
        "lag_bars": int(lag_bars),
        # Do not include per-bar curve or trades. Do not include sharpe/max_dd by default.
    }
    return HoldoutResult(passed=passed, summary=summary, metrics_minimal=metrics_minimal)

