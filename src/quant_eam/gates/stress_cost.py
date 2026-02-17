from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from quant_eam.backtest.vectorbt_adapter_mvp import BacktestInvalid, run_adapter
from quant_eam.gates.types import GateContext, GateEvidence, GateResult
from quant_eam.gates.util import extract_segment, extract_symbols, query_prices_df


def _mul_cost_bps(cost_policy: dict[str, Any], factor: float) -> dict[str, Any]:
    out = deepcopy(cost_policy)
    params = out.get("params")
    if not isinstance(params, dict):
        params = {}
        out["params"] = params
    for k in ("commission_bps", "slippage_bps"):
        v = params.get(k)
        if isinstance(v, (int, float)):
            params[k] = float(v) * float(factor)
    return out


def run_gate_cost_x2_v1(ctx: GateContext, params: dict[str, Any] | None) -> GateResult:
    params = params or {}
    runspec = ctx.runspec
    seg = extract_segment(runspec, "test")
    if seg is None:
        return GateResult(
            gate_id="gate_cost_x2_v1",
            gate_version="v1",
            passed=False,
            status="fail",
            metrics={"reason": "missing runspec.segments.test.{start,end,as_of}"},
            evidence=GateEvidence(artifacts=["config_snapshot.json"]),
        )

    snapshot_id = str(runspec.get("data_snapshot_id", ""))
    symbols = extract_symbols(runspec)
    adapter_id = str((runspec.get("adapter", {}) or {}).get("adapter_id", ""))

    data_root_raw = (ctx.config_snapshot.get("env", {}) or {}).get("EAM_DATA_ROOT")
    data_root = Path(data_root_raw) if isinstance(data_root_raw, str) and data_root_raw.strip() else None

    prices, stats = query_prices_df(data_root=data_root, snapshot_id=snapshot_id, symbols=symbols, seg=seg)

    baseline_lag = int(ctx.metrics.get("lag_bars") or 1)
    baseline_lag = max(1, baseline_lag)

    stressed_cost_policy = _mul_cost_bps(ctx.cost_policy, 2.0)
    try:
        stressed = run_adapter(
            adapter_id=adapter_id,
            prices=prices,
            lag_bars=baseline_lag,
            execution_policy=deepcopy(ctx.execution_policy),
            cost_policy=stressed_cost_policy,
        )
    except BacktestInvalid as e:
        return GateResult(
            gate_id="gate_cost_x2_v1",
            gate_version="v1",
            passed=False,
            status="fail",
            metrics={"error": str(e)},
            evidence=GateEvidence(artifacts=["config_snapshot.json", "metrics.json", "curve.csv", "trades.csv"]),
        )

    baseline_total_return = ctx.metrics.get("total_return")
    try:
        baseline_total_return_f = float(baseline_total_return)
    except Exception:
        baseline_total_return_f = 0.0

    stressed_total_return_f = float(stressed.stats.get("total_return") or 0.0)

    max_return_drop = float(params.get("max_return_drop", 0.10))
    passed = stressed_total_return_f >= (baseline_total_return_f - max_return_drop)

    metrics: dict[str, Any] = {
        "rows_before_asof": int(stats["rows_before_asof"]),
        "rows_after_asof": int(stats["rows_after_asof"]),
        "baseline_total_return": baseline_total_return_f,
        "stressed_total_return": stressed_total_return_f,
        "return_drop": float(baseline_total_return_f - stressed_total_return_f),
        "baseline_cost_policy_params": deepcopy((ctx.cost_policy.get("params") if isinstance(ctx.cost_policy, dict) else {})),
        "stressed_cost_policy_params": deepcopy((stressed_cost_policy.get("params") if isinstance(stressed_cost_policy, dict) else {})),
    }
    thresholds = {"max_return_drop": max_return_drop, "factor": 2.0}

    return GateResult(
        gate_id="gate_cost_x2_v1",
        gate_version="v1",
        passed=passed,
        status="pass" if passed else "fail",
        metrics=metrics,
        thresholds=thresholds,
        evidence=GateEvidence(
            artifacts=["config_snapshot.json", "metrics.json", "curve.csv", "trades.csv"],
            notes="re-runs backtest with cost_policy commission/slippage doubled in-memory; compares total_return vs dossier baseline",
        ),
    )

