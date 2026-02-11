from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from quant_eam.contracts import validate as contracts_validate
from quant_eam.gates.types import GateContext, GateEvidence, GateResult


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _components_path(ctx: GateContext) -> Path:
    # Prefer dossier_manifest artifacts mapping if present.
    arts = ctx.dossier_manifest.get("artifacts")
    if isinstance(arts, dict) and isinstance(arts.get("components"), str):
        return ctx.dossier_dir / str(arts["components"])
    return ctx.dossier_dir / "components.json"


def run_components_integrity_v1(ctx: GateContext, params: dict[str, Any] | None) -> GateResult:
    """Validate composed portfolio evidence references.

    Rules (MVP):
    - components.json must exist and list components with run_id + weight.
    - For each component, gate_results.json must exist and be contract-valid.
    - Default: each component gate_results.overall_pass must be true (can be relaxed via params).
    """
    params = params or {}
    require_overall_pass = bool(params.get("require_overall_pass", True))
    # New name: required_gate_ids; keep backward compat with required_gates.
    required_gates = params.get("required_gate_ids", params.get("required_gates"))
    required_gates_list: list[str] | None = None
    if isinstance(required_gates, list) and all(isinstance(x, str) for x in required_gates):
        required_gates_list = [str(x) for x in required_gates if str(x).strip()]
    min_intersection_points = int(params.get("min_intersection_points", 1))
    min_intersection_points = max(1, min_intersection_points)

    comp_path = _components_path(ctx)
    if not comp_path.is_file():
        return GateResult(
            gate_id="components_integrity_v1",
            gate_version="v1",
            passed=False,
            status="fail",
            metrics={"error": "missing components.json", "path": comp_path.as_posix()},
            evidence=GateEvidence(artifacts=["components.json"], notes="composed run must include component evidence list"),
        )

    doc = _load_json(comp_path)
    comps = None
    if isinstance(doc, dict) and isinstance(doc.get("components"), list):
        comps = doc.get("components")
    elif isinstance(doc, dict) and isinstance(doc.get("composer_spec"), dict):
        # Support older layout: {composer_spec:{components:[...]}}
        cs = doc.get("composer_spec")
        comps = cs.get("components") if isinstance(cs, dict) else None
    elif isinstance(doc, dict) and isinstance(doc.get("components"), dict):
        comps = []

    if not isinstance(comps, list) or not comps:
        return GateResult(
            gate_id="components_integrity_v1",
            gate_version="v1",
            passed=False,
            status="fail",
            metrics={"error": "components.json missing non-empty components list"},
            evidence=GateEvidence(artifacts=[comp_path.name], notes="requires components list"),
        )

    errors: list[str] = []
    checked = 0
    pass_count = 0

    for i, c in enumerate(comps):
        if not isinstance(c, dict):
            errors.append(f"components[{i}] not an object")
            continue
        run_id = c.get("run_id")
        if not isinstance(run_id, str) or not run_id.strip():
            errors.append(f"components[{i}].run_id missing")
            continue
        run_id_s = str(run_id).strip()

        # Default: component dossiers live under the same artifact root.
        comp_dossier = ctx.dossier_dir.parent / run_id_s
        gate_results = comp_dossier / "gate_results.json"
        if not gate_results.is_file():
            errors.append(f"missing gate_results for component run_id={run_id_s}")
            continue

        code, msg = contracts_validate.validate_json(gate_results)
        if code != contracts_validate.EXIT_OK:
            errors.append(f"component gate_results invalid for run_id={run_id_s}: {msg}")
            continue

        gr = _load_json(gate_results)
        if not isinstance(gr, dict):
            errors.append(f"component gate_results not an object for run_id={run_id_s}")
            continue

        checked += 1
        overall = bool(gr.get("overall_pass"))

        if require_overall_pass and not overall:
            errors.append(f"component overall_pass=false for run_id={run_id_s}")
            continue

        if required_gates_list is not None:
            results = gr.get("results")
            if not isinstance(results, list):
                errors.append(f"component results missing for run_id={run_id_s}")
                continue
            passed_gate_ids = {str(r.get("gate_id")) for r in results if isinstance(r, dict) and bool(r.get("pass"))}
            missing_req = sorted([gid for gid in required_gates_list if gid not in passed_gate_ids])
            if missing_req:
                errors.append(f"component missing required gates {missing_req} for run_id={run_id_s}")
                continue

        pass_count += 1

    # Also ensure composed curve is non-empty (alignment success).
    aligned_rows = 0
    intersection_points = 0
    curve = ctx.dossier_dir / "curve.csv"
    if curve.is_file():
        try:
            lines = [ln for ln in curve.read_text(encoding="utf-8").splitlines() if ln.strip()]
            aligned_rows = max(0, len(lines) - 1)
        except Exception:
            aligned_rows = 0

    # Prefer explicit alignment stats if present (audit surface).
    try:
        if isinstance(doc, dict) and isinstance(doc.get("alignment_stats"), dict):
            overall = doc["alignment_stats"].get("overall")
            if isinstance(overall, dict) and isinstance(overall.get("intersection_points"), int):
                intersection_points = int(overall["intersection_points"])
    except Exception:
        intersection_points = 0
    if intersection_points <= 0:
        intersection_points = aligned_rows

    if intersection_points < min_intersection_points:
        errors.append(f"intersection_points {intersection_points} < min_intersection_points {min_intersection_points}")

    passed = not errors
    metrics: dict[str, Any] = {
        "checked_components": int(checked),
        "passed_components": int(pass_count),
        "total_components": int(len(comps)),
        "require_overall_pass": bool(require_overall_pass),
        "required_gate_ids": required_gates_list or [],
        "min_intersection_points": int(min_intersection_points),
        "intersection_points": int(intersection_points),
    }
    if errors:
        metrics["errors"] = errors

    return GateResult(
        gate_id="components_integrity_v1",
        gate_version="v1",
        passed=passed,
        status="pass" if passed else "fail",
        metrics=metrics,
        evidence=GateEvidence(
            artifacts=[comp_path.name, "curve.csv"],
            notes="validates component gate_results evidence + PASS prerequisite for composition",
        ),
    )
