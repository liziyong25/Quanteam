from __future__ import annotations

from typing import Any

from quant_eam.gates.types import GateContext, GateEvidence, GateResult


def run_determinism_guard_v1(ctx: GateContext, params: dict[str, Any] | None) -> GateResult:
    params = params or {}
    require_config_snapshot = bool(params.get("require_config_snapshot", True))

    # This gate is intentionally conservative: it validates that the dossier contains config_snapshot,
    # and that it captures policy sha256 map for replayability.
    cfg = ctx.config_snapshot if isinstance(ctx.config_snapshot, dict) else {}
    ok_cfg = isinstance(cfg, dict) and (not require_config_snapshot or "runspec" in cfg)
    ok_policy_sha = isinstance(cfg.get("policy_sha256"), dict) if isinstance(cfg, dict) else False

    passed = bool(ok_cfg and ok_policy_sha)
    metrics: dict[str, Any] = {
        "require_config_snapshot": require_config_snapshot,
        "has_runspec": bool(isinstance(cfg, dict) and "runspec" in cfg),
        "has_policy_sha256": bool(ok_policy_sha),
    }
    return GateResult(
        gate_id="determinism_guard",
        gate_version="v1",
        passed=passed,
        status="pass" if passed else "fail",
        metrics=metrics,
        evidence=GateEvidence(artifacts=["config_snapshot.json"], notes="checks replay metadata presence"),
    )

