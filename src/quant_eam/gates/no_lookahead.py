from __future__ import annotations

from pathlib import Path
from typing import Any

from quant_eam.gates.types import GateContext, GateEvidence, GateResult
from quant_eam.gates.util import count_asof_violations, extract_segment, extract_symbols, query_prices_df


def run_gate_no_lookahead_v1(ctx: GateContext, params: dict[str, Any] | None) -> GateResult:
    _ = params or {}
    runspec = ctx.runspec

    seg = extract_segment(runspec, "test")
    if seg is None:
        return GateResult(
            gate_id="gate_no_lookahead_v1",
            gate_version="v1",
            passed=False,
            status="fail",
            metrics={"reason": "missing runspec.segments.test.{start,end,as_of}"},
            evidence=GateEvidence(artifacts=["config_snapshot.json"]),
        )

    snapshot_id = str(runspec.get("data_snapshot_id", ""))
    symbols = extract_symbols(runspec)

    data_root_raw = (ctx.config_snapshot.get("env", {}) or {}).get("EAM_DATA_ROOT")
    data_root = None
    if isinstance(data_root_raw, str) and data_root_raw.strip():
        data_root = Path(data_root_raw)

    prices, stats = query_prices_df(
        data_root=data_root,
        snapshot_id=snapshot_id,
        symbols=symbols,
        seg=seg,
    )
    violations = count_asof_violations(prices, seg.as_of)
    passed = violations == 0
    metrics: dict[str, Any] = {
        "rows_before_asof": int(stats["rows_before_asof"]),
        "rows_after_asof": int(stats["rows_after_asof"]),
        "violations_count": int(violations),
        "snapshot_id": snapshot_id,
        "segment": {"start": seg.start, "end": seg.end, "as_of": seg.as_of},
    }
    return GateResult(
        gate_id="gate_no_lookahead_v1",
        gate_version="v1",
        passed=passed,
        status="pass" if passed else "fail",
        metrics=metrics,
        evidence=GateEvidence(
            artifacts=["config_snapshot.json", "data_manifest.json"],
            notes="re-queries DataCatalog and asserts as_of filtering is enforced (available_at <= as_of)",
        ),
    )
