from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from quant_eam.api.roots import dossiers_root, registry_root
from quant_eam.api.security import require_child_dir, require_safe_id
from quant_eam.index.reader import list_jobs_from_index, list_runs_from_index
from quant_eam.registry.experience_retrieval import ExperienceQuery, build_experience_pack_payload
from quant_eam.registry.cards import list_cards as reg_list_cards
from quant_eam.registry.cards import show_card as reg_show_card
from quant_eam.registry.storage import registry_paths
from quant_eam.registry.triallog import record_trial as _unused_record_trial  # noqa: F401

router = APIRouter()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        return [dict(row) for row in r]


def _require_file(path: Path) -> None:
    if not path.is_file():
        raise HTTPException(status_code=404, detail="not found")


@router.get("/runs")
def list_runs(limit: int = 30) -> dict[str, Any]:
    limit = max(1, min(200, int(limit)))
    # Phase-25: prefer artifacts index when present (reduces directory scans).
    idx_rows = list_runs_from_index(limit=limit)
    if idx_rows:
        return {"runs": [{"run_id": r["run_id"]} for r in idx_rows if isinstance(r.get("run_id"), str)]}

    root = dossiers_root()
    if not root.is_dir():
        return {"runs": []}
    # Newest first by directory mtime.
    runs = sorted([p for p in root.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True)
    out = [{"run_id": p.name} for p in runs[:limit]]
    return {"runs": out}


@router.get("/index/runs")
def index_runs(limit: int = 50) -> dict[str, Any]:
    limit = max(1, min(200, int(limit)))
    rows = list_runs_from_index(limit=limit)
    return {"runs": rows, "count": len(rows)}


@router.get("/index/jobs")
def index_jobs(limit: int = 50) -> dict[str, Any]:
    limit = max(1, min(200, int(limit)))
    rows = list_jobs_from_index(limit=limit)
    return {"jobs": rows, "count": len(rows)}


@router.get("/experience/search")
def experience_search(q: str = "", symbols: str | None = None, frequency: str | None = None, tags: str | None = None, k: int = 5) -> dict[str, Any]:
    """Deterministic experience retrieval over registry cards (no embeddings)."""
    sym_list = [s.strip() for s in (symbols or "").split(",") if s.strip()] if symbols else []
    tag_list = [t.strip() for t in (tags or "").split(",") if t.strip()] if tags else []
    qq = ExperienceQuery(query=str(q or ""), symbols=sym_list, frequency=frequency, tags=tag_list, top_k=int(k))
    pack = build_experience_pack_payload(q=qq)
    return pack


@router.get("/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    run_id = require_safe_id(run_id, kind="run_id")
    d = require_child_dir(dossiers_root(), run_id)
    if not d.is_dir():
        raise HTTPException(status_code=404, detail="not found")

    man_p = d / "dossier_manifest.json"
    met_p = d / "metrics.json"
    gate_p = d / "gate_results.json"

    _require_file(man_p)
    _require_file(met_p)
    dossier_manifest = _load_json(man_p)
    metrics = _load_json(met_p)

    gate_results = None
    if gate_p.is_file():
        gate_results = _load_json(gate_p)

    # Keep response small: include gate summary only.
    gate_summary = None
    if isinstance(gate_results, dict):
        gate_summary = {
            "overall_pass": bool(gate_results.get("overall_pass")),
            "gate_suite_id": gate_results.get("gate_suite_id"),
            "results": [
                {"gate_id": r.get("gate_id"), "pass": r.get("pass"), "status": r.get("status")}
                for r in (gate_results.get("results") or [])
                if isinstance(r, dict)
            ],
            "holdout_summary": gate_results.get("holdout_summary"),
        }

    return {
        "run_id": run_id,
        "dossier_manifest": dossier_manifest,
        "metrics": metrics,
        "gate_results": gate_summary,
    }


@router.get("/runs/{run_id}/curve")
def get_curve(run_id: str) -> dict[str, Any]:
    run_id = require_safe_id(run_id, kind="run_id")
    d = require_child_dir(dossiers_root(), run_id)
    p = d / "curve.csv"
    _require_file(p)
    return {"run_id": run_id, "rows": _read_csv_rows(p)}


@router.get("/runs/{run_id}/trades")
def get_trades(run_id: str) -> dict[str, Any]:
    run_id = require_safe_id(run_id, kind="run_id")
    d = require_child_dir(dossiers_root(), run_id)
    p = d / "trades.csv"
    _require_file(p)
    return {"run_id": run_id, "rows": _read_csv_rows(p)}


@router.get("/runs/{run_id}/artifacts")
def list_run_artifacts(run_id: str) -> dict[str, Any]:
    run_id = require_safe_id(run_id, kind="run_id")
    d = require_child_dir(dossiers_root(), run_id)
    man_p = d / "dossier_manifest.json"
    _require_file(man_p)
    man = _load_json(man_p)
    artifacts = man.get("artifacts") if isinstance(man, dict) else None
    if not isinstance(artifacts, dict):
        artifacts = {}
    # Ensure artifacts are safe relative paths (no traversal).
    safe: dict[str, str] = {}
    for k, v in artifacts.items():
        if not isinstance(k, str) or not isinstance(v, str):
            continue
        if v.startswith("/") or ".." in v or "\\" in v:
            continue
        safe[k] = v
    return {"run_id": run_id, "artifacts": safe}


@router.get("/runs/{run_id}/diagnostics")
def list_run_diagnostics(run_id: str) -> dict[str, Any]:
    run_id = require_safe_id(run_id, kind="run_id")
    d = require_child_dir(dossiers_root(), run_id)
    if not d.is_dir():
        raise HTTPException(status_code=404, detail="not found")

    diag_root = d / "diagnostics"
    rows: list[dict[str, Any]] = []
    if diag_root.is_dir():
        for dd in sorted(diag_root.iterdir(), key=lambda p: p.name):
            if not dd.is_dir():
                continue
            diagnostic_id = str(dd.name)
            try:
                diagnostic_id = require_safe_id(diagnostic_id, kind="diagnostic_id")
            except HTTPException:
                continue
            spec_path = dd / "diagnostic_spec.json"
            report_path = dd / "diagnostic_report.json"
            gate_spec_path = dd / "promotion_candidate" / "gate_spec.json"
            report = _load_json(report_path) if report_path.is_file() else {}
            gate_spec = _load_json(gate_spec_path) if gate_spec_path.is_file() else {}
            candidates = gate_spec.get("candidate_gates") if isinstance(gate_spec, dict) else None
            rows.append(
                {
                    "diagnostic_id": diagnostic_id,
                    "summary": report.get("summary") if isinstance(report, dict) else None,
                    "candidate_gate_count": len(candidates) if isinstance(candidates, list) else 0,
                    "paths": {
                        "diagnostic_spec_path": spec_path.relative_to(d).as_posix() if spec_path.is_file() else None,
                        "diagnostic_report_path": report_path.relative_to(d).as_posix() if report_path.is_file() else None,
                        "promotion_gate_spec_path": gate_spec_path.relative_to(d).as_posix() if gate_spec_path.is_file() else None,
                    },
                }
            )

    return {"run_id": run_id, "diagnostics": rows}


@router.get("/runs/{run_id}/diagnostics/{diagnostic_id}")
def get_run_diagnostic(run_id: str, diagnostic_id: str) -> dict[str, Any]:
    run_id = require_safe_id(run_id, kind="run_id")
    diagnostic_id = require_safe_id(diagnostic_id, kind="diagnostic_id")
    d = require_child_dir(dossiers_root(), run_id)
    if not d.is_dir():
        raise HTTPException(status_code=404, detail="not found")

    dd = require_child_dir(d / "diagnostics", diagnostic_id)
    if not dd.is_dir():
        raise HTTPException(status_code=404, detail="diagnostic not found")

    spec_path = dd / "diagnostic_spec.json"
    report_path = dd / "diagnostic_report.json"
    outputs_dir = dd / "diagnostic_outputs"
    gate_spec_path = dd / "promotion_candidate" / "gate_spec.json"
    if not spec_path.is_file() or not report_path.is_file():
        raise HTTPException(status_code=404, detail="diagnostic artifacts incomplete")

    output_files: list[str] = []
    if outputs_dir.is_dir():
        for p in sorted(outputs_dir.glob("*.json"), key=lambda x: x.name):
            if p.is_file():
                output_files.append(p.relative_to(d).as_posix())

    gate_spec = _load_json(gate_spec_path) if gate_spec_path.is_file() else {}
    return {
        "run_id": run_id,
        "diagnostic_id": diagnostic_id,
        "diagnostic_spec": _load_json(spec_path),
        "diagnostic_report": _load_json(report_path),
        "promotion_gate_spec": gate_spec if isinstance(gate_spec, dict) else {},
        "paths": {
            "diagnostic_spec_path": spec_path.relative_to(d).as_posix(),
            "diagnostic_report_path": report_path.relative_to(d).as_posix(),
            "diagnostic_outputs_dir": outputs_dir.relative_to(d).as_posix(),
            "promotion_gate_spec_path": gate_spec_path.relative_to(d).as_posix() if gate_spec_path.is_file() else None,
            "diagnostic_output_files": output_files,
        },
    }


@router.get("/registry/trials")
def list_trials(limit: int = 50, offset: int = 0) -> dict[str, Any]:
    limit = max(1, min(200, int(limit)))
    offset = max(0, int(offset))
    paths = registry_paths(registry_root())
    if not paths.trial_log.is_file():
        return {"trials": [], "total": 0}
    lines = paths.trial_log.read_text(encoding="utf-8").splitlines()
    events: list[dict[str, Any]] = []
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        try:
            doc = json.loads(ln)
            if isinstance(doc, dict):
                events.append(doc)
        except json.JSONDecodeError:
            continue
    # Newest first.
    events.reverse()
    total = len(events)
    page = events[offset : offset + limit]
    return {"trials": page, "total": total, "limit": limit, "offset": offset}


@router.get("/registry/cards")
def list_cards() -> dict[str, Any]:
    cards = reg_list_cards(registry_root=registry_root())
    return {"cards": cards}


@router.get("/registry/cards/{card_id}")
def show_card(card_id: str) -> dict[str, Any]:
    card_id = require_safe_id(card_id, kind="card_id")
    try:
        doc = reg_show_card(registry_root=registry_root(), card_id=card_id)
    except Exception:
        raise HTTPException(status_code=404, detail="not found")
    return doc
