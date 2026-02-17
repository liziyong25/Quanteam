from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd

from quant_eam.backtest.signal_compiler import SignalCompileInvalid, compile_signal_dsl_v1

ADAPTER_ID_VECTORBT_SIGNAL_V1 = "vectorbt_signal_v1"


@dataclass(frozen=True)
class BacktestResult:
    equity_curve: pd.DataFrame  # columns: dt, equity
    trades: pd.DataFrame  # columns: entry_dt, exit_dt, pnl, qty, fees
    stats: dict[str, Any]
    # Risk evidence artifacts (Phase-27): produced by the backtest engine itself to avoid drift.
    positions: pd.DataFrame | None = None  # columns: dt, symbol, qty, close, position_value, equity
    turnover: pd.DataFrame | None = None  # columns: dt, turnover
    exposure: dict[str, Any] | None = None  # computed max observed values + metadata


class BacktestInvalid(ValueError):
    pass


def _bps_to_fraction(bps: float) -> float:
    return float(bps) / 10_000.0


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


def _apply_lag(signal: pd.Series, lag_bars: int) -> pd.Series:
    if lag_bars <= 0:
        return signal
    return signal.shift(lag_bars).fillna(False).astype(bool)


def _validate_execution_policy(execution_policy: dict[str, Any]) -> tuple[str, str]:
    params = execution_policy.get("params")
    if not isinstance(params, dict):
        raise BacktestInvalid("execution_policy.params must be an object")

    order_timing = params.get("order_timing")
    fill_price = params.get("fill_price")
    if not isinstance(order_timing, str):
        raise BacktestInvalid("execution_policy.params.order_timing must be a string")
    if fill_price is not None and not isinstance(fill_price, str):
        raise BacktestInvalid("execution_policy.params.fill_price must be a string when present")

    # MVP: support the default v1 policy combo (next_open/open) and close/close.
    supported = {("next_open", "open"), ("close", "close")}
    fp = fill_price or ("open" if order_timing == "next_open" else "close")
    if (order_timing, fp) not in supported:
        raise BacktestInvalid(
            f"unsupported execution policy option: order_timing={order_timing!r}, fill_price={fp!r}"
        )
    return order_timing, fp


def _validate_cost_policy(cost_policy: dict[str, Any]) -> tuple[float, float]:
    params = cost_policy.get("params")
    if not isinstance(params, dict):
        raise BacktestInvalid("cost_policy.params must be an object")

    commission_bps = params.get("commission_bps")
    slippage_bps = params.get("slippage_bps")
    if not isinstance(commission_bps, (int, float)):
        raise BacktestInvalid("cost_policy.params.commission_bps must be a number")
    if not isinstance(slippage_bps, (int, float)):
        raise BacktestInvalid("cost_policy.params.slippage_bps must be a number")
    return _bps_to_fraction(float(commission_bps)), _bps_to_fraction(float(slippage_bps))


def run_buy_and_hold_mvp(
    *,
    prices: pd.DataFrame,
    lag_bars: int,
    execution_policy: dict[str, Any],
    cost_policy: dict[str, Any],
) -> BacktestResult:
    """Deterministic MVP strategy: buy at first available bar, hold, exit at end.

    Lookahead protection:
    - Signals are shifted forward by lag_bars (default >= 1).
    """
    needed_cols = {"dt", "symbol", "open", "close"}
    missing = needed_cols - set(prices.columns)
    if missing:
        raise BacktestInvalid(f"missing required price columns: {sorted(missing)}")
    if lag_bars < 1:
        raise BacktestInvalid("lag_bars must be >= 1 for MVP (no-lookahead default)")

    order_timing, fill_price = _validate_execution_policy(execution_policy)
    commission_frac, slippage_frac = _validate_cost_policy(cost_policy)

    df = prices.copy()
    df["dt"] = pd.to_datetime(df["dt"])
    df["symbol"] = df["symbol"].astype(str)
    df = df.sort_values(["symbol", "dt"], kind="mergesort").reset_index(drop=True)

    # Build raw signals per symbol, then apply lag.
    entries_list: list[pd.Series] = []
    exits_list: list[pd.Series] = []
    for sym, g in df.groupby("symbol", sort=True):
        n = len(g)
        raw_entry = pd.Series([False] * n, index=g.index)
        raw_exit = pd.Series([False] * n, index=g.index)
        if n > 0:
            raw_entry.iloc[0] = True
            # Ensure after lag, the exit lands on the last bar.
            raw_exit_idx = max(0, n - 1 - lag_bars)
            raw_exit.iloc[raw_exit_idx] = True
        entries_list.append(_apply_lag(raw_entry, lag_bars))
        exits_list.append(_apply_lag(raw_exit, lag_bars))

    entries = pd.concat(entries_list).sort_index()
    exits = pd.concat(exits_list).sort_index()

    # Single-position-per-symbol simulation, equal-weight allocation across symbols at entry.
    symbols = sorted(df["symbol"].unique().tolist())
    if not symbols:
        raise BacktestInvalid("no symbols in prices")

    initial_cash = 1.0
    cash = initial_cash
    qty_by_symbol: dict[str, float] = {s: 0.0 for s in symbols}
    in_position: dict[str, bool] = {s: False for s in symbols}

    trades_rows: list[dict[str, Any]] = []
    entry_dt_by_symbol: dict[str, datetime] = {}
    entry_px_by_symbol: dict[str, float] = {}
    fees_by_symbol: dict[str, float] = {s: 0.0 for s in symbols}

    equity_rows: list[dict[str, Any]] = []
    positions_rows: list[dict[str, Any]] = []
    turnover_rows: list[dict[str, Any]] = []
    leverage_series: list[float | None] = []
    positions_count_series: list[int] = []

    def exec_price(row: pd.Series) -> float:
        if order_timing == "next_open":
            px = float(row["open"])
        elif order_timing == "close":
            px = float(row["close"])
        else:
            # Should be blocked by validation.
            raise BacktestInvalid(f"unsupported order_timing: {order_timing!r}")
        # Slippage: pay worse price on entry, better on exit handled separately.
        return px

    prev_equity: float | None = None

    # Iterate over dt; valuation uses close.
    for dt, gdt in df.groupby("dt", sort=True):
        trade_value_abs = 0.0
        # Entries: execute first, then exits, deterministic order by symbol.
        for sym in symbols:
            rows = gdt[gdt["symbol"] == sym]
            if rows.empty:
                continue
            row = rows.iloc[0]
            idx = row.name
            if bool(entries.loc[idx]) and not in_position[sym]:
                alloc = cash / max(1, sum(1 for s in symbols if not in_position[s]))
                px = exec_price(row) * (1.0 + slippage_frac)
                qty = alloc / px if px > 0 else 0.0
                notional = qty * px
                fee = notional * commission_frac
                cash -= notional + fee
                trade_value_abs += abs(notional)
                qty_by_symbol[sym] = qty
                in_position[sym] = True
                entry_dt_by_symbol[sym] = dt.to_pydatetime()
                entry_px_by_symbol[sym] = px
                fees_by_symbol[sym] += fee

        for sym in symbols:
            rows = gdt[gdt["symbol"] == sym]
            if rows.empty:
                continue
            row = rows.iloc[0]
            idx = row.name
            if bool(exits.loc[idx]) and in_position[sym]:
                px = exec_price(row) * (1.0 - slippage_frac)
                qty = qty_by_symbol[sym]
                notional = qty * px
                fee = notional * commission_frac
                cash += notional - fee
                fees_by_symbol[sym] += fee
                trade_value_abs += abs(notional)

                entry_dt = entry_dt_by_symbol.get(sym, dt.to_pydatetime())
                entry_px = float(entry_px_by_symbol.get(sym, px))
                pnl = (px - entry_px) * qty - fees_by_symbol[sym]
                trades_rows.append(
                    {
                        "symbol": sym,
                        "entry_dt": entry_dt.isoformat(),
                        "exit_dt": dt.to_pydatetime().isoformat(),
                        "pnl": float(pnl),
                        "qty": float(qty),
                        "fees": float(fees_by_symbol[sym]),
                    }
                )
                qty_by_symbol[sym] = 0.0
                in_position[sym] = False
                fees_by_symbol[sym] = 0.0

        # Mark-to-market using close price.
        net = 0.0
        gross = 0.0
        pos_count = 0
        pos_local: list[tuple[str, float, float, float]] = []  # (sym, qty, close, pv)
        for sym in symbols:
            rows = gdt[gdt["symbol"] == sym]
            if rows.empty:
                continue
            close_px = float(rows.iloc[0]["close"])
            q = float(qty_by_symbol[sym])
            pv = q * close_px
            net += pv
            gross += abs(pv)
            if abs(q) > 0.0:
                pos_count += 1
            pos_local.append((sym, q, close_px, pv))
        equity = float(cash) + float(net)
        equity_rows.append({"dt": dt.to_pydatetime().isoformat(), "equity": float(equity)})
        for sym, q, close_px, pv in pos_local:
            positions_rows.append(
                {
                    "dt": dt.to_pydatetime().isoformat(),
                    "symbol": sym,
                    "qty": float(q),
                    "close": float(close_px),
                    "position_value": float(pv),
                    "equity": float(equity),
                }
            )

        denom = prev_equity if (prev_equity is not None and prev_equity > 0.0) else float(equity or 0.0)
        turnover = (trade_value_abs / denom) if denom and denom > 0.0 else None
        turnover_rows.append({"dt": dt.to_pydatetime().isoformat(), "turnover": turnover})

        cash_mtm = float(cash)
        denom2 = gross + max(cash_mtm, 0.0)
        leverage = (gross / denom2) if denom2 > 0.0 else None
        leverage_series.append(leverage)
        positions_count_series.append(int(pos_count))
        prev_equity = float(equity)

    equity_df = pd.DataFrame(equity_rows)
    trades_df = pd.DataFrame(trades_rows)
    positions_df = pd.DataFrame(positions_rows)
    turnover_df = pd.DataFrame(turnover_rows)

    total_return = float(equity_df["equity"].iloc[-1] / initial_cash - 1.0) if not equity_df.empty else 0.0
    stats = {
        "adapter_id": ADAPTER_ID_VECTORBT_SIGNAL_V1,
        "strategy_id": "buy_and_hold_mvp",
        "lag_bars": int(lag_bars),
        "total_return": total_return,
        "max_drawdown": _max_drawdown(equity_df["equity"]) if not equity_df.empty else 0.0,
        "sharpe": _sharpe_from_equity(equity_df["equity"]) if not equity_df.empty else None,
        "trade_count": int(len(trades_df)),
        "execution": {"order_timing": order_timing, "fill_price": fill_price},
        "cost": {"commission_fraction": commission_frac, "slippage_fraction": slippage_frac},
    }

    exposure = {
        "schema_version": "backtest_exposure_v1",
        "adapter_id": ADAPTER_ID_VECTORBT_SIGNAL_V1,
        "strategy_id": "buy_and_hold_mvp",
        "dt_min": str(equity_df["dt"].iloc[0]) if not equity_df.empty else None,
        "dt_max": str(equity_df["dt"].iloc[-1]) if not equity_df.empty else None,
        "max_observed": {
            "max_leverage_observed": float(max([x for x in leverage_series if isinstance(x, (int, float))], default=0.0)),
            "max_positions_observed": int(max(positions_count_series, default=0)),
            "max_turnover_observed": float(max([x for x in turnover_df["turnover"].tolist() if isinstance(x, (int, float))], default=0.0))
            if "turnover" in turnover_df.columns
            else 0.0,
        },
    }

    return BacktestResult(
        equity_curve=equity_df,
        trades=trades_df,
        stats=stats,
        positions=positions_df,
        turnover=turnover_df,
        exposure=exposure,
    )


def run_signal_dsl_v1(
    *,
    prices: pd.DataFrame,
    signal_dsl: dict[str, Any],
    lag_bars: int,
    execution_policy: dict[str, Any],
    cost_policy: dict[str, Any],
) -> BacktestResult:
    """Execute a `signal_dsl_v1` strategy using the shared signal compiler.

    Determinism / governance:
    - lag_bars must be >= 1 (no-lookahead default)
    - costs come only from cost_policy
    - execution timing comes only from execution_policy
    """
    needed_cols = {"dt", "symbol", "open", "close"}
    missing = needed_cols - set(prices.columns)
    if missing:
        raise BacktestInvalid(f"missing required price columns: {sorted(missing)}")
    if lag_bars < 1:
        raise BacktestInvalid("lag_bars must be >= 1 for v1 (no-lookahead default)")

    order_timing, fill_price = _validate_execution_policy(execution_policy)
    commission_frac, slippage_frac = _validate_cost_policy(cost_policy)

    try:
        comp = compile_signal_dsl_v1(prices=prices, signal_dsl=signal_dsl, lag_bars=lag_bars)
    except SignalCompileInvalid as e:
        raise BacktestInvalid(str(e))

    df = prices.copy()
    df["dt"] = pd.to_datetime(df["dt"])
    df["symbol"] = df["symbol"].astype(str)
    df = df.sort_values(["symbol", "dt"], kind="mergesort").reset_index(drop=True)

    sig = comp.frame.copy()
    sig["symbol"] = sig["symbol"].astype(str)
    sig["_dt"] = pd.to_datetime(sig["dt"])
    sig = sig.sort_values(["symbol", "_dt"], kind="mergesort").reset_index(drop=True)

    if len(sig) != len(df):
        raise BacktestInvalid("compiled signals do not align with price rows")

    entries = sig["entry_lagged"].astype(bool).fillna(False)
    exits = sig["exit_lagged"].astype(bool).fillna(False)

    symbols = sorted(df["symbol"].unique().tolist())
    if not symbols:
        raise BacktestInvalid("no symbols in prices")

    initial_cash = 1.0
    cash = initial_cash
    qty_by_symbol: dict[str, float] = {s: 0.0 for s in symbols}
    in_position: dict[str, bool] = {s: False for s in symbols}

    trades_rows: list[dict[str, Any]] = []
    entry_dt_by_symbol: dict[str, datetime] = {}
    entry_px_by_symbol: dict[str, float] = {}
    fees_by_symbol: dict[str, float] = {s: 0.0 for s in symbols}

    equity_rows: list[dict[str, Any]] = []
    positions_rows: list[dict[str, Any]] = []
    turnover_rows: list[dict[str, Any]] = []
    leverage_series: list[float | None] = []
    positions_count_series: list[int] = []

    def exec_price(row: pd.Series) -> float:
        if order_timing == "next_open":
            return float(row["open"])
        if order_timing == "close":
            return float(row["close"])
        raise BacktestInvalid(f"unsupported order_timing: {order_timing!r}")

    prev_equity: float | None = None
    for dt, gdt in df.groupby("dt", sort=True):
        trade_value_abs = 0.0
        for sym in symbols:
            rows = gdt[gdt["symbol"] == sym]
            if rows.empty:
                continue
            row = rows.iloc[0]
            idx = row.name
            if bool(entries.loc[idx]) and not in_position[sym]:
                alloc = cash / max(1, sum(1 for s in symbols if not in_position[s]))
                px = exec_price(row) * (1.0 + slippage_frac)
                qty = alloc / px if px > 0 else 0.0
                notional = qty * px
                fee = notional * commission_frac
                cash -= notional + fee
                trade_value_abs += abs(notional)
                qty_by_symbol[sym] = qty
                in_position[sym] = True
                entry_dt_by_symbol[sym] = dt.to_pydatetime()
                entry_px_by_symbol[sym] = px
                fees_by_symbol[sym] += fee

        for sym in symbols:
            rows = gdt[gdt["symbol"] == sym]
            if rows.empty:
                continue
            row = rows.iloc[0]
            idx = row.name
            if bool(exits.loc[idx]) and in_position[sym]:
                px = exec_price(row) * (1.0 - slippage_frac)
                qty = qty_by_symbol[sym]
                notional = qty * px
                fee = notional * commission_frac
                cash += notional - fee
                fees_by_symbol[sym] += fee
                trade_value_abs += abs(notional)

                entry_dt = entry_dt_by_symbol.get(sym, dt.to_pydatetime())
                entry_px = float(entry_px_by_symbol.get(sym, px))
                pnl = (px - entry_px) * qty - fees_by_symbol[sym]
                trades_rows.append(
                    {
                        "symbol": sym,
                        "entry_dt": entry_dt.isoformat(),
                        "exit_dt": dt.to_pydatetime().isoformat(),
                        "pnl": float(pnl),
                        "qty": float(qty),
                        "fees": float(fees_by_symbol[sym]),
                    }
                )
                qty_by_symbol[sym] = 0.0
                in_position[sym] = False
                fees_by_symbol[sym] = 0.0

        net = 0.0
        gross = 0.0
        pos_count = 0
        pos_local: list[tuple[str, float, float, float]] = []
        for sym in symbols:
            rows = gdt[gdt["symbol"] == sym]
            if rows.empty:
                continue
            close_px = float(rows.iloc[0]["close"])
            q = float(qty_by_symbol[sym])
            pv = q * close_px
            net += pv
            gross += abs(pv)
            if abs(q) > 0.0:
                pos_count += 1
            pos_local.append((sym, q, close_px, pv))
        equity = float(cash) + float(net)
        equity_rows.append({"dt": dt.to_pydatetime().isoformat(), "equity": float(equity)})
        for sym, q, close_px, pv in pos_local:
            positions_rows.append(
                {
                    "dt": dt.to_pydatetime().isoformat(),
                    "symbol": sym,
                    "qty": float(q),
                    "close": float(close_px),
                    "position_value": float(pv),
                    "equity": float(equity),
                }
            )

        denom = prev_equity if (prev_equity is not None and prev_equity > 0.0) else float(equity or 0.0)
        turnover = (trade_value_abs / denom) if denom and denom > 0.0 else None
        turnover_rows.append({"dt": dt.to_pydatetime().isoformat(), "turnover": turnover})

        cash_mtm = float(cash)
        denom2 = gross + max(cash_mtm, 0.0)
        leverage = (gross / denom2) if denom2 > 0.0 else None
        leverage_series.append(leverage)
        positions_count_series.append(int(pos_count))
        prev_equity = float(equity)

    equity_df = pd.DataFrame(equity_rows)
    trades_df = pd.DataFrame(trades_rows)
    positions_df = pd.DataFrame(positions_rows)
    turnover_df = pd.DataFrame(turnover_rows)

    total_return = float(equity_df["equity"].iloc[-1] / initial_cash - 1.0) if not equity_df.empty else 0.0

    strategy_id = "signal_dsl_v1"
    ext = signal_dsl.get("extensions") if isinstance(signal_dsl.get("extensions"), dict) else {}
    if isinstance(ext, dict) and isinstance(ext.get("strategy_id"), str) and ext.get("strategy_id"):
        strategy_id = str(ext["strategy_id"])

    stats = {
        "adapter_id": ADAPTER_ID_VECTORBT_SIGNAL_V1,
        "strategy_id": strategy_id,
        "lag_bars": int(lag_bars),
        "total_return": total_return,
        "max_drawdown": _max_drawdown(equity_df["equity"]) if not equity_df.empty else 0.0,
        "sharpe": _sharpe_from_equity(equity_df["equity"]) if not equity_df.empty else None,
        "trade_count": int(len(trades_df)),
        "execution": {"order_timing": order_timing, "fill_price": fill_price},
        "cost": {"commission_fraction": commission_frac, "slippage_fraction": slippage_frac},
        "dsl_fingerprint": comp.dsl_fingerprint,
        "signals_fingerprint": comp.signals_fingerprint,
    }

    exposure = {
        "schema_version": "backtest_exposure_v1",
        "adapter_id": ADAPTER_ID_VECTORBT_SIGNAL_V1,
        "strategy_id": strategy_id,
        "dt_min": str(equity_df["dt"].iloc[0]) if not equity_df.empty else None,
        "dt_max": str(equity_df["dt"].iloc[-1]) if not equity_df.empty else None,
        "max_observed": {
            "max_leverage_observed": float(max([x for x in leverage_series if isinstance(x, (int, float))], default=0.0)),
            "max_positions_observed": int(max(positions_count_series, default=0)),
            "max_turnover_observed": float(max([x for x in turnover_df["turnover"].tolist() if isinstance(x, (int, float))], default=0.0))
            if "turnover" in turnover_df.columns
            else 0.0,
        },
    }

    return BacktestResult(
        equity_curve=equity_df,
        trades=trades_df,
        stats=stats,
        positions=positions_df,
        turnover=turnover_df,
        exposure=exposure,
    )


def run_adapter(
    *,
    adapter_id: str,
    prices: pd.DataFrame,
    lag_bars: int,
    execution_policy: dict[str, Any],
    cost_policy: dict[str, Any],
    signal_dsl: dict[str, Any] | None = None,
) -> BacktestResult:
    if adapter_id != ADAPTER_ID_VECTORBT_SIGNAL_V1:
        raise BacktestInvalid(f"unsupported adapter_id: {adapter_id!r}")

    # Try vectorbt if available; fallback to deterministic minimal engine.
    try:
        import vectorbt as _vbt  # noqa: F401
        # For Phase-04 MVP, we keep the deterministic fallback as the reference behavior.
        # Vectorbt integration can be enabled in a later phase without changing the adapter_id surface.
    except Exception:
        pass

    if isinstance(signal_dsl, dict):
        return run_signal_dsl_v1(
            prices=prices,
            signal_dsl=signal_dsl,
            lag_bars=lag_bars,
            execution_policy=execution_policy,
            cost_policy=cost_policy,
        )

    return run_buy_and_hold_mvp(prices=prices, lag_bars=lag_bars, execution_policy=execution_policy, cost_policy=cost_policy)
