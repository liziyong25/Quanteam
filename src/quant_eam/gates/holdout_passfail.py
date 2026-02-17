from __future__ import annotations

from pathlib import Path
from typing import Any

from quant_eam.gates.types import GateContext, GateEvidence, GateResult
from quant_eam.gates.util import extract_segment, extract_symbols
from quant_eam.holdout.vault import HoldoutInvalid, evaluate_holdout_minimal


def run_gate_holdout_passfail_v1(ctx: GateContext, params: dict[str, Any] | None) -> GateResult:
    params = params or {}
    runspec = ctx.runspec

    holdout_seg = extract_segment(runspec, "holdout")
    if holdout_seg is None:
        return GateResult(
            gate_id="gate_holdout_passfail_v1",
            gate_version="v1",
            passed=True,
            status="skipped",
            metrics={"holdout_present": False},
            evidence=GateEvidence(artifacts=["config_snapshot.json"], notes="no holdout segment in runspec"),
        )

    # Enforce policy holdout output restriction (GateRunner also enforces globally).
    out = (((ctx.gate_suite.get("params", {}) or {}).get("holdout_policy", {}) or {}).get("output"))
    if out != "pass_fail_minimal_summary":
        return GateResult(
            gate_id="gate_holdout_passfail_v1",
            gate_version="v1",
            passed=False,
            status="fail",
            metrics={"error": f"holdout_policy.output must be 'pass_fail_minimal_summary' (got {out!r})"},
            evidence=GateEvidence(artifacts=["config_snapshot.json"]),
        )

    snapshot_id = str(runspec.get("data_snapshot_id", ""))
    dataset_id = str((runspec.get("extensions", {}) or {}).get("dataset_id", "ohlcv_1d")) or "ohlcv_1d"
    symbols = extract_symbols(runspec)
    adapter_id = str((runspec.get("adapter", {}) or {}).get("adapter_id", ""))

    # Data root from config snapshot; fallback to env.
    data_root_raw = (ctx.config_snapshot.get("env", {}) or {}).get("EAM_DATA_ROOT")
    data_root = Path(data_root_raw) if isinstance(data_root_raw, str) and data_root_raw.strip() else None

    lag_bars = int(ctx.metrics.get("lag_bars") or 1)
    lag_bars = max(1, lag_bars)
    try:
        h = evaluate_holdout_minimal(
            data_root=data_root,
            snapshot_id=snapshot_id,
            dataset_id=dataset_id,
            symbols=symbols,
            seg=holdout_seg,
            adapter_id=adapter_id,
            lag_bars=lag_bars,
            execution_policy=ctx.execution_policy,
            cost_policy=ctx.cost_policy,
            params=params,
        )
    except HoldoutInvalid as e:
        return GateResult(
            gate_id="gate_holdout_passfail_v1",
            gate_version="v1",
            passed=False,
            status="fail",
            metrics={"error": str(e), "holdout_present": True},
            evidence=GateEvidence(artifacts=["config_snapshot.json", "metrics.json"]),
        )

    metrics: dict[str, Any] = {
        "holdout_present": True,
        "pass": bool(h.passed),
        "summary": h.summary,
        "metrics_minimal": h.metrics_minimal,
    }
    return GateResult(
        gate_id="gate_holdout_passfail_v1",
        gate_version="v1",
        passed=bool(h.passed),
        status="pass" if h.passed else "fail",
        metrics=metrics,
        evidence=GateEvidence(
            artifacts=["config_snapshot.json", "metrics.json"],
            notes="holdout evaluated via HoldoutVault with restricted output (no curve/trades written)",
        ),
    )

