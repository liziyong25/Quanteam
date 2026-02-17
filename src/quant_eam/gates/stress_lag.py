from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from quant_eam.backtest.vectorbt_adapter_mvp import BacktestInvalid, run_adapter
from quant_eam.gates.types import GateContext, GateEvidence, GateResult
from quant_eam.gates.util import Segment, extract_segment, extract_symbols, query_prices_df


def _baseline_lag(ctx: GateContext) -> int:
    v = ctx.metrics.get("lag_bars")
    try:
        if isinstance(v, (int, float)):
            return max(1, int(v))
    except Exception:
        pass
    params = ctx.asof_latency_policy.get("params", {})
    if isinstance(params, dict) and "trade_lag_bars_default" in params:
        try:
            return max(1, int(params["trade_lag_bars_default"]))
        except Exception:
            return 1
    return 1


def run_gate_delay_plus_1bar_v1(ctx: GateContext, params: dict[str, Any] | None) -> GateResult:
    params = params or {}
    runspec = ctx.runspec
    seg = extract_segment(runspec, "test")
    if seg is None:
        return GateResult(
            gate_id="gate_delay_plus_1bar_v1",
            gate_version="v1",
            passed=False,
            status="fail",
            metrics={"reason": "missing runspec.segments.test.{start,end,as_of}"},
            evidence=GateEvidence(artifacts=["config_snapshot.json"]),
        )

    snapshot_id = str(runspec.get("data_snapshot_id", ""))
    symbols = extract_symbols(runspec)
    adapter_id = str((runspec.get("adapter", {}) or {}).get("adapter_id", ""))

    # Data root from config snapshot (runner writes it), fallback to env default via DataCatalog(None).
    data_root_raw = (ctx.config_snapshot.get("env", {}) or {}).get("EAM_DATA_ROOT")
    data_root = Path(data_root_raw) if isinstance(data_root_raw, str) and data_root_raw.strip() else None

    prices, stats = query_prices_df(data_root=data_root, snapshot_id=snapshot_id, symbols=symbols, seg=seg)

    baseline_lag = _baseline_lag(ctx)
    stressed_lag = baseline_lag + 1

    try:
        stressed = run_adapter(
            adapter_id=adapter_id,
            prices=prices,
            lag_bars=stressed_lag,
            execution_policy=deepcopy(ctx.execution_policy),
            cost_policy=deepcopy(ctx.cost_policy),
        )
    except BacktestInvalid as e:
        return GateResult(
            gate_id="gate_delay_plus_1bar_v1",
            gate_version="v1",
            passed=False,
            status="fail",
            metrics={"error": str(e), "stressed_lag": stressed_lag},
            evidence=GateEvidence(artifacts=["config_snapshot.json", "metrics.json", "curve.csv", "trades.csv"]),
        )

    baseline_total_return = ctx.metrics.get("total_return")
    try:
        baseline_total_return_f = float(baseline_total_return)
    except Exception:
        baseline_total_return_f = 0.0

    stressed_total_return_f = float(stressed.stats.get("total_return") or 0.0)

    max_return_drop = float(params.get("max_return_drop", 0.05))
    passed = stressed_total_return_f >= (baseline_total_return_f - max_return_drop)

    metrics: dict[str, Any] = {
        "rows_before_asof": int(stats["rows_before_asof"]),
        "rows_after_asof": int(stats["rows_after_asof"]),
        "baseline_lag_bars": int(baseline_lag),
        "stressed_lag_bars": int(stressed_lag),
        "baseline_total_return": baseline_total_return_f,
        "stressed_total_return": stressed_total_return_f,
        "return_drop": float(baseline_total_return_f - stressed_total_return_f),
    }
    thresholds = {"max_return_drop": max_return_drop}

    return GateResult(
        gate_id="gate_delay_plus_1bar_v1",
        gate_version="v1",
        passed=passed,
        status="pass" if passed else "fail",
        metrics=metrics,
        thresholds=thresholds,
        evidence=GateEvidence(
            artifacts=["config_snapshot.json", "metrics.json", "curve.csv", "trades.csv"],
            notes="re-runs backtest with lag_bars+1 in-memory; compares total_return vs dossier baseline",
        ),
    )

