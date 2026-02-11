from __future__ import annotations

from pathlib import Path
from typing import Any

from quant_eam.gates.types import GateContext, GateEvidence, GateResult


def run_basic_sanity_v1(ctx: GateContext, params: dict[str, Any] | None) -> GateResult:
    """Minimal sanity checks for dossier evidence presence.

    Note: policy gate_suite may list 'gate_results.json' as a required artifact, but this is circular
    for a runner that is producing gate_results.json. We intentionally do NOT require gate_results.json
    here; we require only core dossier artifacts the gates will consume.
    """
    params = params or {}
    required = [
        "config_snapshot.json",
        "metrics.json",
        "curve.csv",
        "trades.csv",
        "dossier_manifest.json",
    ]
    # Allow policy to request additional artifacts, but never require gate_results.json (circular).
    extra = params.get("require_artifacts")
    if isinstance(extra, list):
        for x in extra:
            if isinstance(x, str) and x.strip() and x.strip() != "gate_results.json":
                if x.strip() not in required:
                    required.append(x.strip())
    missing: list[str] = []
    for rel in required:
        if not (ctx.dossier_dir / rel).is_file():
            missing.append(rel)

    passed = not missing
    metrics = {"missing_artifacts": missing, "required_artifacts": required}
    return GateResult(
        gate_id="basic_sanity",
        gate_version="v1",
        passed=passed,
        status="pass" if passed else "fail",
        metrics=metrics,
        evidence=GateEvidence(artifacts=required, notes="core dossier artifact presence"),
    )
