from __future__ import annotations

from typing import Any

from quant_eam.gates.basic_sanity import run_basic_sanity_v1
from quant_eam.gates.data_snapshot_integrity import run_data_snapshot_integrity_v1
from quant_eam.gates.components_integrity import run_components_integrity_v1
from quant_eam.gates.determinism_guard import run_determinism_guard_v1
from quant_eam.gates.holdout_passfail import run_gate_holdout_passfail_v1
from quant_eam.gates.holdout_leak_guard import run_holdout_leak_guard_v1
from quant_eam.gates.no_lookahead import run_gate_no_lookahead_v1
from quant_eam.gates.risk_policy_compliance import run_risk_policy_compliance_v1
from quant_eam.gates.stress_cost import run_gate_cost_x2_v1
from quant_eam.gates.stress_lag import run_gate_delay_plus_1bar_v1
from quant_eam.gates.types import GateContext, GateFn, GateResult


def get_gate(gate_id: str, gate_version: str) -> GateFn | None:
    key = (str(gate_id), str(gate_version))
    return {
        ("basic_sanity", "v1"): run_basic_sanity_v1,
        ("determinism_guard", "v1"): run_determinism_guard_v1,
        ("data_snapshot_integrity_v1", "v1"): run_data_snapshot_integrity_v1,
        ("components_integrity_v1", "v1"): run_components_integrity_v1,
        ("gate_no_lookahead_v1", "v1"): run_gate_no_lookahead_v1,
        ("gate_delay_plus_1bar_v1", "v1"): run_gate_delay_plus_1bar_v1,
        ("gate_cost_x2_v1", "v1"): run_gate_cost_x2_v1,
        ("gate_holdout_passfail_v1", "v1"): run_gate_holdout_passfail_v1,
        ("holdout_leak_guard_v1", "v1"): run_holdout_leak_guard_v1,
        ("risk_policy_compliance_v1", "v1"): run_risk_policy_compliance_v1,
    }.get(key)


def run_gate(
    *, ctx: GateContext, gate_id: str, gate_version: str, params: dict[str, Any] | None = None
) -> GateResult:
    fn = get_gate(gate_id, gate_version)
    if fn is None:
        return GateResult(
            gate_id=str(gate_id),
            gate_version=str(gate_version),
            passed=False,
            status="fail",
            metrics={"error": f"unsupported gate_id/gate_version: {gate_id!r}/{gate_version!r}"},
        )
    return fn(ctx, params)
