from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_diagnostics_agent(*, input_path: Path, out_dir: Path, provider: str = "mock") -> list[Path]:
    if str(provider).strip() != "mock":
        raise ValueError("provider 'external' is not supported in diagnostics_agent MVP")
    payload = _load_json(Path(input_path))
    if not isinstance(payload, dict):
        raise ValueError("diagnostics_agent input must be a JSON object")

    run_id = str(payload.get("run_id") or "").strip()
    dossier_path = str(payload.get("dossier_path") or "").strip()
    failed_gates = payload.get("failed_gates")
    if not isinstance(failed_gates, list):
        failed_gates = []

    plan = {
        "schema_version": "diagnostics_agent_plan_v1",
        "agent_id": "diagnostics_agent_v1",
        "run_id": run_id,
        "dossier_path": dossier_path,
        "failed_gates": [str(g) for g in failed_gates if str(g).strip()],
        "diagnostic_candidates": [
            {
                "diagnostic_id": f"diag_{run_id[:8]}" if run_id else "diag_default",
                "objective": "Translate deterministic run metrics and gate results into promotable gate candidates.",
                "recommended_checks": [
                    {"metric_key": "max_drawdown", "operator": "le", "severity": "error"},
                    {"metric_key": "sharpe", "operator": "ge", "severity": "warn"},
                ],
            }
        ],
        "notes": [
            "Diagnostics agent is evidence-only and does not arbitrate PASS/FAIL.",
            "DiagnosticSpec execution remains deterministic and governed by kernel tooling.",
        ],
    }

    out_path = Path(out_dir) / "diagnostics_plan.json"
    _write_json(out_path, plan)
    return [out_path]
