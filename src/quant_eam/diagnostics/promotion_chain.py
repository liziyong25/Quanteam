from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from quant_eam.contracts import validate as contracts_validate
from quant_eam.policies.load import find_repo_root


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError(f"json root must be object: {path.as_posix()}")
    return doc


def _schema_path(name: str) -> Path:
    return find_repo_root() / "contracts" / name


def _validate_with_schema(payload: dict[str, Any], schema_name: str) -> None:
    code, msg = contracts_validate.validate_payload(payload, schema_path=_schema_path(schema_name))
    if code != contracts_validate.EXIT_OK:
        raise ValueError(msg)


def _to_float(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        try:
            return float(s)
        except Exception:
            return None
    return None


OPS: dict[str, Callable[[float, float], bool]] = {
    "lt": lambda a, b: a < b,
    "le": lambda a, b: a <= b,
    "gt": lambda a, b: a > b,
    "ge": lambda a, b: a >= b,
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
}
OP_EXPR = {
    "lt": "<",
    "le": "<=",
    "gt": ">",
    "ge": ">=",
    "eq": "==",
    "ne": "!=",
}


def _build_check_results(*, checks: list[dict[str, Any]], metrics: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for c in checks:
        check_id = str(c.get("check_id") or "").strip()
        metric_key = str(c.get("metric_key") or "").strip()
        operator = str(c.get("operator") or "").strip()
        threshold_raw = c.get("threshold")
        threshold = _to_float(threshold_raw)
        actual_raw = metrics.get(metric_key)
        actual = _to_float(actual_raw)

        passed = False
        reason = ""
        if not check_id or not metric_key or operator not in OPS or threshold is None:
            reason = "invalid_check_spec"
        elif actual is None:
            reason = "metric_missing_or_non_numeric"
        else:
            passed = bool(OPS[operator](actual, threshold))
            reason = "ok" if passed else "threshold_not_met"

        rows.append(
            {
                "check_id": check_id,
                "metric_key": metric_key,
                "operator": operator,
                "threshold": threshold_raw,
                "actual_value": actual_raw,
                "severity": str(c.get("severity") or "warn"),
                "passed": bool(passed),
                "reason": reason,
            }
        )
    return rows


def _build_gate_spec(*, run_id: str, diagnostic_id: str, check_rows: list[dict[str, Any]]) -> dict[str, Any]:
    gates: list[dict[str, Any]] = []
    for r in check_rows:
        if bool(r.get("passed")):
            continue
        sev = str(r.get("severity") or "warn")
        gate_severity = "fail" if sev == "error" else "warn"
        metric_key = str(r.get("metric_key") or "")
        op = str(r.get("operator") or "")
        op_expr = OP_EXPR.get(op, "==")
        thr = r.get("threshold")
        gates.append(
            {
                "gate_id": f"diag_{str(r.get('check_id') or 'check')}",
                "expression": f"metrics.{metric_key} {op_expr} {thr}",
                "severity": gate_severity,
                "threshold": thr,
                "evidence_refs": [
                    f"diagnostics/{diagnostic_id}/diagnostic_report.json#/checks/{str(r.get('check_id') or '')}",
                    f"metrics.json#/{metric_key}",
                ],
                "description": f"Derived from diagnostics check {str(r.get('check_id') or '')}.",
            }
        )

    if not gates:
        gates.append(
            {
                "gate_id": f"diag_monitor_{diagnostic_id}",
                "expression": "true",
                "severity": "warn",
                "evidence_refs": [
                    f"diagnostics/{diagnostic_id}/diagnostic_report.json#/summary",
                ],
                "description": "All diagnostics checks passed; monitor-only candidate.",
            }
        )

    return {
        "schema_version": "gate_spec_v1",
        "gate_spec_id": f"gate_spec_{diagnostic_id}",
        "source_run_id": run_id,
        "source_diagnostic_id": diagnostic_id,
        "candidate_gates": gates,
        "extensions": {
            "generated_at": _now_iso(),
            "generator": "diagnostics_promotion_chain_v1",
        },
    }


def run_diagnostic_spec(*, run_id: str, diagnostic_spec: dict[str, Any], dossiers_dir: Path) -> dict[str, Any]:
    run = str(run_id).strip()
    if not run:
        raise ValueError("missing run_id")
    if not isinstance(diagnostic_spec, dict):
        raise ValueError("diagnostic_spec must be an object")

    _validate_with_schema(diagnostic_spec, "diagnostic_spec_v1.json")

    diagnostic_id = str(diagnostic_spec.get("diagnostic_id") or "").strip()
    dossier_dir = Path(dossiers_dir) / run
    if not dossier_dir.is_dir():
        raise FileNotFoundError(f"run dossier not found: {run}")

    metrics_path = dossier_dir / "metrics.json"
    gate_results_path = dossier_dir / "gate_results.json"
    if not metrics_path.is_file():
        raise FileNotFoundError("missing metrics.json")
    if not gate_results_path.is_file():
        raise FileNotFoundError("missing gate_results.json")

    metrics = _load_json(metrics_path)
    gate_results = _load_json(gate_results_path)

    diag_dir = dossier_dir / "diagnostics" / diagnostic_id
    spec_path = diag_dir / "diagnostic_spec.json"
    report_path = diag_dir / "diagnostic_report.json"
    outputs_dir = diag_dir / "diagnostic_outputs"
    promotion_gate_spec_path = diag_dir / "promotion_candidate" / "gate_spec.json"

    if spec_path.is_file():
        existing = _load_json(spec_path)
        if json.dumps(existing, sort_keys=True) != json.dumps(diagnostic_spec, sort_keys=True):
            raise ValueError(f"diagnostic_id already exists with different spec: {diagnostic_id}")

    _write_json(spec_path, diagnostic_spec)

    checks_raw = diagnostic_spec.get("checks")
    checks = checks_raw if isinstance(checks_raw, list) else []
    check_rows = _build_check_results(
        checks=[c for c in checks if isinstance(c, dict)],
        metrics=metrics,
    )

    fail_count = sum(1 for r in check_rows if not bool(r.get("passed")))
    pass_count = sum(1 for r in check_rows if bool(r.get("passed")))
    report = {
        "schema_version": "diagnostic_report_v1",
        "run_id": run,
        "diagnostic_id": diagnostic_id,
        "recorded_at": _now_iso(),
        "summary": {
            "check_count": len(check_rows),
            "pass_count": pass_count,
            "fail_count": fail_count,
            "overall": "pass" if fail_count == 0 else "fail",
        },
        "checks": check_rows,
        "evidence_refs": {
            "metrics_path": "metrics.json",
            "gate_results_path": "gate_results.json",
            "diagnostic_spec_path": f"diagnostics/{diagnostic_id}/diagnostic_spec.json",
        },
        "extensions": {
            "gate_suite_id": gate_results.get("gate_suite_id"),
            "overall_pass": gate_results.get("overall_pass"),
        },
    }
    _write_json(report_path, report)

    _write_json(outputs_dir / "metrics_snapshot.json", metrics)
    _write_json(outputs_dir / "gate_results_snapshot.json", gate_results)
    _write_json(
        outputs_dir / "check_results.json",
        {
            "schema_version": "diagnostic_check_results_v1",
            "run_id": run,
            "diagnostic_id": diagnostic_id,
            "checks": check_rows,
        },
    )

    gate_spec = _build_gate_spec(run_id=run, diagnostic_id=diagnostic_id, check_rows=check_rows)
    _validate_with_schema(gate_spec, "gate_spec_v1.json")
    _write_json(promotion_gate_spec_path, gate_spec)

    return {
        "run_id": run,
        "diagnostic_id": diagnostic_id,
        "diagnostic_spec_path": spec_path.as_posix(),
        "diagnostic_report_path": report_path.as_posix(),
        "diagnostic_outputs_dir": outputs_dir.as_posix(),
        "promotion_gate_spec_path": promotion_gate_spec_path.as_posix(),
        "summary": report["summary"],
    }
