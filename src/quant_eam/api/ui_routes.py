from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from quant_eam.api.roots import dossiers_root, registry_root
from quant_eam.api.security import require_child_dir, require_safe_id, require_safe_job_id
from quant_eam.datacatalog.catalog import DataCatalog
from quant_eam.jobstore.store import (
    append_event as jobs_append_event,
    default_job_root,
    job_paths as jobs_job_paths,
    list_job_ids as jobs_list_job_ids,
    load_job_events as jobs_load_events,
    load_job_spec as jobs_load_spec,
)
from quant_eam.registry.cards import list_cards as reg_list_cards
from quant_eam.registry.cards import show_card as reg_show_card
from quant_eam.registry.storage import registry_paths
from quant_eam.snapshots.catalog import SnapshotCatalog

router = APIRouter()


def _templates() -> Jinja2Templates:
    base = Path(__file__).resolve().parents[1]  # src/quant_eam
    td = base / "ui" / "templates"
    return Jinja2Templates(directory=str(td))


TEMPLATES = _templates()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        return [dict(row) for row in r]


def _plotly_equity_curve_html(curve_rows: list[dict[str, str]]) -> str:
    try:
        import plotly.graph_objs as go
        from plotly.io import to_html
    except Exception:
        # Fallback: no JS, just return an empty placeholder.
        return "<div class='plot-fallback'>plotly not available</div>"

    x = [r.get("dt") for r in curve_rows]
    y = []
    for r in curve_rows:
        try:
            y.append(float(r.get("equity", "0") or 0))
        except Exception:
            y.append(0.0)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines", name="equity", line={"width": 2}))
    fig.update_layout(
        height=320,
        margin={"l": 40, "r": 20, "t": 10, "b": 30},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis={"title": "dt"},
        yaxis={"title": "equity"},
        showlegend=False,
    )
    return to_html(fig, full_html=False, include_plotlyjs="inline", config={"displayModeBar": False})


def _plotly_candles_html(
    *,
    ohlcv_rows: list[dict[str, Any]],
    trades_rows: list[dict[str, str]],
    symbol: str,
) -> str:
    try:
        import plotly.graph_objs as go
        from plotly.io import to_html
    except Exception:
        return "<div class='plot-fallback'>plotly not available</div>"

    x = [r.get("dt") for r in ohlcv_rows]
    o = [float(r.get("open") or 0.0) for r in ohlcv_rows]
    h = [float(r.get("high") or 0.0) for r in ohlcv_rows]
    l = [float(r.get("low") or 0.0) for r in ohlcv_rows]
    c = [float(r.get("close") or 0.0) for r in ohlcv_rows]

    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=x, open=o, high=h, low=l, close=c, name=symbol, increasing_line_width=1))

    # Trade markers (entry/exit) for this symbol only.
    entries_x: list[str] = []
    exits_x: list[str] = []
    entries_y: list[float] = []
    exits_y: list[float] = []
    close_by_dt = {str(r.get("dt")): float(r.get("close") or 0.0) for r in ohlcv_rows}
    for tr in trades_rows:
        if str(tr.get("symbol", "")).strip() != symbol:
            continue
        ed = str(tr.get("entry_dt", ""))
        xd = str(tr.get("exit_dt", ""))
        if ed:
            dt_key = ed.split("T")[0] if "T" in ed else ed
            if dt_key in close_by_dt:
                entries_x.append(dt_key)
                entries_y.append(close_by_dt[dt_key])
        if xd:
            dt_key = xd.split("T")[0] if "T" in xd else xd
            if dt_key in close_by_dt:
                exits_x.append(dt_key)
                exits_y.append(close_by_dt[dt_key])

    if entries_x:
        fig.add_trace(
            go.Scatter(
                x=entries_x,
                y=entries_y,
                mode="markers",
                marker={"size": 10, "symbol": "triangle-up", "color": "#0ea5e9"},
                name="entry",
            )
        )
    if exits_x:
        fig.add_trace(
            go.Scatter(
                x=exits_x,
                y=exits_y,
                mode="markers",
                marker={"size": 10, "symbol": "triangle-down", "color": "#f97316"},
                name="exit",
            )
        )

    fig.update_layout(
        height=360,
        margin={"l": 40, "r": 20, "t": 10, "b": 30},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis={"title": "dt"},
        yaxis={"title": "price"},
        showlegend=True,
        legend={"orientation": "h"},
    )
    # Do not inline plotly.js again (equity plot already includes it).
    return to_html(fig, full_html=False, include_plotlyjs=False, config={"displayModeBar": False})


def _job_root() -> Path:
    return default_job_root()


@router.api_route("/ui/snapshots", methods=["GET", "HEAD"], response_class=HTMLResponse)
def ui_snapshots(request: Request) -> HTMLResponse:
    cat = SnapshotCatalog(root=Path(os.getenv("EAM_DATA_ROOT", "/data")))
    snaps: list[dict[str, Any]] = []
    for rec in cat.list_snapshots():
        try:
            doc = cat.load_snapshot(rec.snapshot_id)
        except Exception:
            continue
        man = doc.get("manifest") if isinstance(doc.get("manifest"), dict) else {}
        datasets = man.get("datasets") if isinstance(man.get("datasets"), list) else []
        parts: list[str] = []
        for ds in datasets:
            if not isinstance(ds, dict):
                continue
            parts.append(f"{ds.get('dataset_id')} rows={ds.get('row_count')}")
        snaps.append(
            {
                "snapshot_id": rec.snapshot_id,
                "created_at": man.get("created_at", rec.created_at),
                "datasets_summary": ", ".join(parts),
                "has_quality": bool(doc.get("quality_report")),
                "has_ingest_manifest": bool(doc.get("ingest_manifest")),
            }
        )

    return TEMPLATES.TemplateResponse(request, "snapshots.html", {"snapshots": snaps, "title": "Snapshots"})


@router.api_route("/ui/snapshots/{snapshot_id}", methods=["GET", "HEAD"], response_class=HTMLResponse)
def ui_snapshot_detail(
    request: Request,
    snapshot_id: str,
    symbols: str | None = None,
    start: str | None = None,
    end: str | None = None,
    as_of: str | None = None,
    limit: int = 30,
) -> HTMLResponse:
    snapshot_id = require_safe_id(snapshot_id, kind="snapshot_id")
    cat = SnapshotCatalog(root=Path(os.getenv("EAM_DATA_ROOT", "/data")))
    try:
        doc = cat.load_snapshot(snapshot_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="not found")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    man = doc["manifest"]
    datasets = man.get("datasets") if isinstance(man.get("datasets"), list) else []
    ds0 = datasets[0] if datasets and isinstance(datasets[0], dict) else {}
    default_symbols = []
    if isinstance(ds0, dict) and isinstance(ds0.get("symbols"), list):
        default_symbols = [str(s) for s in ds0.get("symbols") if str(s).strip()]
    default_symbols = default_symbols or ["AAA"]

    preview_symbols = symbols or ",".join(default_symbols[:2])
    preview_start = start or str(ds0.get("dt_min", ""))[:10] or "2024-01-01"
    preview_end = end or str(ds0.get("dt_max", ""))[:10] or preview_start
    preview_asof_default = str(ds0.get("available_at_max", "")) or "2024-01-05T00:00:00+08:00"
    preview_as_of = as_of or preview_asof_default
    preview_limit = max(1, min(int(limit or 30), 200))

    preview_rows: list[dict[str, Any]] = []
    preview_stats: dict[str, Any] | None = None
    # Only attempt preview if query params exist (or we have defaults).
    try:
        dc = DataCatalog(root=Path(os.getenv("EAM_DATA_ROOT", "/data")))
        syms = [s.strip() for s in str(preview_symbols).split(",") if s.strip()]
        rows, stats = dc.query_ohlcv(snapshot_id=snapshot_id, symbols=syms, start=preview_start, end=preview_end, as_of=preview_as_of)
        preview_rows = rows[:preview_limit]
        preview_stats = {"rows_before_asof": stats.rows_before_asof, "rows_after_asof": stats.rows_after_asof}
    except Exception:
        preview_rows = []
        preview_stats = None

    q = doc.get("quality_report") if isinstance(doc.get("quality_report"), dict) else None
    quality_key = None
    if isinstance(q, dict):
        quality_key = {
            "rows_before_dedupe": q.get("rows_before_dedupe"),
            "rows_after_dedupe": q.get("rows_after_dedupe"),
            "duplicate_count": q.get("duplicate_count"),
            "dt_min": q.get("dt_min"),
            "dt_max": q.get("dt_max"),
        }

    return TEMPLATES.TemplateResponse(
        request,
        "snapshot.html",
        {
            "snapshot_id": snapshot_id,
            "snapshot_dir": (doc.get("paths") or {}).get("snapshot_dir"),
            "manifest_json": json.dumps(doc.get("manifest"), indent=2, sort_keys=True),
            "ingest_manifest_json": json.dumps(doc.get("ingest_manifest"), indent=2, sort_keys=True) if doc.get("ingest_manifest") else "",
            "quality_report_json": json.dumps(doc.get("quality_report"), indent=2, sort_keys=True) if doc.get("quality_report") else "",
            "quality_key_json": json.dumps(quality_key, indent=2, sort_keys=True) if quality_key else "",
            "preview_symbols": preview_symbols,
            "preview_start": preview_start,
            "preview_end": preview_end,
            "preview_as_of": preview_as_of,
            "preview_limit": preview_limit,
            "preview_rows": preview_rows,
            "preview_stats_json": json.dumps(preview_stats, indent=2, sort_keys=True) if preview_stats else "",
            "title": f"Snapshot {snapshot_id}",
        },
    )


@router.api_route("/ui/jobs", methods=["GET", "HEAD"], response_class=HTMLResponse)
def ui_jobs(request: Request) -> HTMLResponse:
    jobs: list[dict[str, Any]] = []
    jr = _job_root()
    for jid in jobs_list_job_ids(job_root=jr):
        try:
            spec = jobs_load_spec(jid, job_root=jr)
            events = jobs_load_events(jid, job_root=jr)
        except Exception:
            continue
        sv = spec.get("schema_version") if isinstance(spec, dict) else None
        if sv == "job_spec_v1":
            bp = spec.get("blueprint") if isinstance(spec, dict) else {}
            blueprint_id = bp.get("blueprint_id") if isinstance(bp, dict) else None
            title = bp.get("title") if isinstance(bp, dict) else None
        else:
            blueprint_id = None
            title = spec.get("title") if isinstance(spec, dict) else None
        jobs.append(
            {
                "job_id": jid,
                "state": str(events[-1].get("event_type")) if events else "unknown",
                "schema_version": sv,
                "blueprint_id": blueprint_id,
                "title": title,
            }
        )

    return TEMPLATES.TemplateResponse(request, "jobs.html", {"jobs": jobs, "title": "Jobs"})


def _recent_trials(limit: int = 20) -> list[dict[str, Any]]:
    paths = registry_paths(registry_root())
    if not paths.trial_log.is_file():
        return []
    lines = [ln.strip() for ln in paths.trial_log.read_text(encoding="utf-8").splitlines() if ln.strip()]
    out: list[dict[str, Any]] = []
    for ln in reversed(lines[-limit:]):
        try:
            doc = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if isinstance(doc, dict):
            out.append(doc)
    return out


@router.api_route("/ui", methods=["GET", "HEAD"], response_class=HTMLResponse)
def ui_index(request: Request) -> HTMLResponse:
    cards = reg_list_cards(registry_root=registry_root())
    trials = _recent_trials(limit=20)
    return TEMPLATES.TemplateResponse(
        request,
        "index.html",
        {"cards": cards, "trials": trials, "title": "Review Console"},
    )


@router.api_route("/ui/runs/{run_id}", methods=["GET", "HEAD"], response_class=HTMLResponse)
def ui_run(request: Request, run_id: str, symbol: str | None = None, segment_id: str | None = None) -> HTMLResponse:
    run_id = require_safe_id(run_id, kind="run_id")
    d = require_child_dir(dossiers_root(), run_id)
    if not d.is_dir():
        raise HTTPException(status_code=404, detail="not found")

    dossier_manifest = _load_json(d / "dossier_manifest.json")
    metrics = _load_json(d / "metrics.json")
    gate_results = _load_json(d / "gate_results.json") if (d / "gate_results.json").is_file() else {}
    cfg = _load_json(d / "config_snapshot.json")
    runspec = cfg.get("runspec") if isinstance(cfg, dict) else {}
    risk_report = _load_json(d / "risk_report.json") if (d / "risk_report.json").is_file() else None
    attribution_report = _load_json(d / "attribution_report.json") if (d / "attribution_report.json").is_file() else None
    attribution_md = ""
    p_attr_md = d / "reports" / "attribution" / "report.md"
    if p_attr_md.is_file():
        attribution_md = p_attr_md.read_text(encoding="utf-8")

    # Phase-21: per-segment evidence (optional). Default view remains top-level.
    segments_summary = _load_json(d / "segments_summary.json") if (d / "segments_summary.json").is_file() else {}
    seg_rows = segments_summary.get("segments") if isinstance(segments_summary, dict) else None
    seg_list: list[dict[str, Any]] = []
    if isinstance(seg_rows, list):
        for s in seg_rows:
            if isinstance(s, dict) and isinstance(s.get("segment_id"), str) and isinstance(s.get("kind"), str):
                seg_list.append(s)

    selected = None
    if isinstance(segment_id, str) and segment_id.strip():
        for s in seg_list:
            if str(s.get("segment_id")) == segment_id:
                selected = s
                break
    if selected is None:
        # Default: first test segment if exists, else top-level.
        for s in seg_list:
            if str(s.get("kind")) == "test":
                selected = s
                break

    selected_id = str(selected.get("segment_id")) if isinstance(selected, dict) else None
    selected_kind = str(selected.get("kind")) if isinstance(selected, dict) else None
    is_holdout_view = bool(selected_kind == "holdout")
    if is_holdout_view:
        # Holdout view is minimal-only; do not render attribution evidence (derived from curve/trades).
        attribution_report = None
        attribution_md = ""

    # Load metrics/curve/trades from selected segment directory when present (non-holdout only).
    seg_dir = (d / "segments" / selected_id) if (selected_id and (d / "segments" / selected_id).is_dir()) else None
    if seg_dir is not None and (not is_holdout_view):
        metrics = _load_json(seg_dir / "metrics.json") if (seg_dir / "metrics.json").is_file() else metrics
        curve_rows = _read_csv_rows(seg_dir / "curve.csv") if (seg_dir / "curve.csv").is_file() else []
        trades_rows = _read_csv_rows(seg_dir / "trades.csv") if (seg_dir / "trades.csv").is_file() else []
    else:
        curve_rows = _read_csv_rows(d / "curve.csv") if (d / "curve.csv").is_file() else []
        trades_rows = _read_csv_rows(d / "trades.csv") if (d / "trades.csv").is_file() else []

    # Symbol selection: from runspec.extensions.symbols.
    symbols = []
    if isinstance(runspec, dict):
        ext = runspec.get("extensions", {})
        if isinstance(ext, dict) and isinstance(ext.get("symbols"), list):
            symbols = [str(s) for s in ext.get("symbols") if str(s).strip()]
    symbols = symbols or ["AAA"]
    sym = symbol if (isinstance(symbol, str) and symbol in symbols) else symbols[0]

    # Candles: query DataCatalog (no direct lake CSV reads).
    snapshot_id = str(dossier_manifest.get("data_snapshot_id", "")).strip()
    snapshot_id_safe = None
    if snapshot_id:
        try:
            snapshot_id_safe = require_safe_id(snapshot_id, kind="snapshot_id")
        except Exception:
            snapshot_id_safe = None
    # Segment candles window: prefer selected segment, fallback to runspec.segments.test.
    if isinstance(selected, dict):
        start = str(selected.get("start") or "")
        end = str(selected.get("end") or "")
        as_of = str(selected.get("as_of") or "")
        # Holdout still uses minimal summary only; do not render candles/trades/curve.
        if is_holdout_view:
            start, end, as_of = "", "", ""
    else:
        seg = (runspec.get("segments", {}) or {}).get("test", {}) if isinstance(runspec, dict) else {}
        start = str(seg.get("start", ""))
        end = str(seg.get("end", ""))
        as_of = str(seg.get("as_of", ""))

    ohlcv_rows: list[dict[str, Any]] = []
    if snapshot_id and start and end and as_of:
        cat = DataCatalog(root=Path(os.getenv("EAM_DATA_ROOT", "/data")))
        rows, _stats = cat.query_ohlcv(snapshot_id=snapshot_id, symbols=[sym], start=start, end=end, as_of=as_of)
        # Convert numeric strings for plotly.
        for r in rows:
            rr = dict(r)
            for k in ("open", "high", "low", "close", "volume"):
                try:
                    rr[k] = float(rr.get(k) or 0.0)
                except Exception:
                    rr[k] = 0.0
            rr["dt"] = str(rr.get("dt"))
            ohlcv_rows.append(rr)

    equity_html = _plotly_equity_curve_html(curve_rows) if (curve_rows and not is_holdout_view) else ""
    candles_html = _plotly_candles_html(ohlcv_rows=ohlcv_rows, trades_rows=trades_rows, symbol=sym) if (ohlcv_rows and not is_holdout_view) else ""

    # Holdout summary is allowed only as minimal output.
    holdout_summary = gate_results.get("holdout_summary") if isinstance(gate_results, dict) else None

    # Gate table.
    gate_rows = []
    if isinstance(gate_results, dict) and isinstance(gate_results.get("results"), list):
        for r in gate_results["results"]:
            if isinstance(r, dict):
                gate_rows.append(
                    {
                        "gate_id": r.get("gate_id"),
                        "pass": r.get("pass"),
                        "status": r.get("status"),
                    }
                )

    return TEMPLATES.TemplateResponse(
        request,
        "run.html",
        {
            "run_id": run_id,
            "snapshot_id": snapshot_id_safe,
            "metrics": metrics,
            "gate_rows": gate_rows,
            "overall_pass": bool(gate_results.get("overall_pass")) if isinstance(gate_results, dict) else None,
            "holdout_summary": holdout_summary,
            "risk_report": risk_report,
            "attribution_report": attribution_report,
            "attribution_md": attribution_md,
            "segments": seg_list,
            "segment_id": selected_id,
            "segment_kind": selected_kind,
            "is_holdout_view": is_holdout_view,
            "equity_html": equity_html,
            "candles_html": candles_html,
            "symbols": symbols,
            "symbol": sym,
        },
    )


@router.api_route("/ui/cards/{card_id}", methods=["GET", "HEAD"], response_class=HTMLResponse)
def ui_card(request: Request, card_id: str) -> HTMLResponse:
    card_id = require_safe_id(card_id, kind="card_id")
    try:
        doc = reg_show_card(registry_root=registry_root(), card_id=card_id)
    except Exception:
        raise HTTPException(status_code=404, detail="not found")
    # Phase-24 attribution preview (best-effort).
    attr = None
    try:
        run_id = str(doc.get("primary_run_id") or "")
        run_id = require_safe_id(run_id, kind="run_id")
        d = require_child_dir(dossiers_root(), run_id)
        p = d / "attribution_report.json"
        if p.is_file():
            attr = _load_json(p)
    except Exception:
        attr = None

    return TEMPLATES.TemplateResponse(request, "card.html", {"card": doc, "card_id": card_id, "attribution_report": attr})


@router.api_route("/ui/jobs/{job_id}", methods=["GET", "HEAD"], response_class=HTMLResponse)
def ui_job_detail(request: Request, job_id: str) -> HTMLResponse:
    job_id = require_safe_job_id(job_id)
    jr = _job_root()
    paths = jobs_job_paths(job_id, job_root=jr)
    if not paths.job_spec.is_file():
        raise HTTPException(status_code=404, detail="not found")
    spec = jobs_load_spec(job_id, job_root=jr)
    events = jobs_load_events(job_id, job_root=jr)
    outputs_path = paths.outputs_dir / "outputs.json"
    outputs: dict[str, Any] = {}
    if outputs_path.is_file():
        try:
            doc = json.loads(outputs_path.read_text(encoding="utf-8"))
            if isinstance(doc, dict):
                outputs = doc
        except Exception:
            outputs = {}

    sv = spec.get("schema_version") if isinstance(spec, dict) else None
    bp = spec.get("blueprint") if (isinstance(spec, dict) and sv == "job_spec_v1") else {}
    state = str(events[-1].get("event_type")) if events else "unknown"
    waiting_step = None
    for ev in reversed(events):
        if str(ev.get("event_type")) == "WAITING_APPROVAL":
            out = ev.get("outputs") if isinstance(ev.get("outputs"), dict) else {}
            waiting_step = str(out.get("step") or "") or None
            break
    approved_steps: set[str] = set()
    has_global_approved = False
    for ev in events:
        if str(ev.get("event_type")) != "APPROVED":
            continue
        if not isinstance(ev.get("outputs"), dict):
            has_global_approved = True
            continue
        st = str(ev["outputs"].get("step") or "")
        if st:
            approved_steps.add(st)
        else:
            has_global_approved = True
    waiting = waiting_step is not None and (waiting_step not in approved_steps) and (not has_global_approved)

    # Optional artifacts for review.
    blueprint_draft = None
    blueprint_final = None
    signal_dsl = None
    variable_dictionary = None
    calc_trace_plan = None
    runspec = None
    trace_preview_rows: list[dict[str, str]] = []
    trace_meta = None
    report_text = None
    report_summary = None
    improvement_proposals = None
    llm_evidence: list[dict[str, Any]] = []
    llm_usage_report = None
    llm_usage_report_json = ""
    llm_usage_report_path = None
    llm_usage_events_path = None
    sweep_leaderboard = None
    sweep_trials_tail: list[dict[str, Any]] = []
    experience_pack = None
    experience_pack_json = ""
    llm_live_confirm_info: dict[str, Any] | None = None

    # Job-level LLM budget/usage evidence (Phase-26).
    usage_report_p = paths.outputs_dir / "llm" / "llm_usage_report.json"
    usage_events_p = paths.outputs_dir / "llm" / "llm_usage_events.jsonl"
    if usage_report_p.is_file():
        llm_usage_report_path = usage_report_p.as_posix()
        llm_usage_events_path = usage_events_p.as_posix() if usage_events_p.exists() else None
        try:
            doc = json.loads(usage_report_p.read_text(encoding="utf-8"))
            if isinstance(doc, dict):
                llm_usage_report = doc
                llm_usage_report_json = json.dumps(doc, indent=2, sort_keys=True)
        except Exception:
            llm_usage_report = None
            llm_usage_report_json = ""

    # Phase-28: LIVE/RECORD rollout review checkpoint details (best-effort).
    if waiting and waiting_step == "llm_live_confirm":
        try:
            from quant_eam.jobstore.llm_usage import aggregate_totals, load_llm_budget_policy

            pol_path = None
            if isinstance(spec, dict):
                pp = spec.get("llm_budget_policy_path")
                if isinstance(pp, str) and pp.strip():
                    pol_path = pp.strip()
            pol_path = pol_path or "policies/llm_budget_policy_v1.yaml"
            thresholds = load_llm_budget_policy(Path(pol_path))
            totals, _by_agent, _stop_reason = aggregate_totals(job_id=job_id, job_root=jr)

            # Best-effort estimate: remaining agent calls in the idea workflow.
            est_calls = 0
            if isinstance(spec, dict) and str(spec.get("schema_version") or "") == "idea_spec_v1":
                if not any(str(ev.get("event_type")) == "BLUEPRINT_PROPOSED" for ev in events):
                    est_calls += 1
                if not any(str(ev.get("event_type")) == "STRATEGY_SPEC_PROPOSED" for ev in events):
                    est_calls += 1
                if not any(str(ev.get("event_type")) == "REPORT_COMPLETED" for ev in events):
                    est_calls += 1
                if not any(str(ev.get("event_type")) == "IMPROVEMENTS_PROPOSED" for ev in events):
                    est_calls += 1

            llm_live_confirm_info = {
                "provider_id": str(os.getenv("EAM_LLM_PROVIDER", "mock")).strip() or "mock",
                "mode": str(os.getenv("EAM_LLM_MODE", "live")).strip() or "live",
                "model": (str(os.getenv("EAM_LLM_REAL_MODEL", "")).strip() or None),
                "budget_policy_path": pol_path,
                "budget_policy_id": thresholds.policy_id,
                "thresholds": {
                    "max_calls_per_job": thresholds.max_calls_per_job,
                    "max_prompt_chars_per_job": thresholds.max_prompt_chars_per_job,
                    "max_response_chars_per_job": thresholds.max_response_chars_per_job,
                    "max_wall_seconds_per_job": thresholds.max_wall_seconds_per_job,
                    "max_calls_per_agent_run": thresholds.max_calls_per_agent_run,
                },
                "totals": {
                    "calls": totals.calls,
                    "prompt_chars": totals.prompt_chars,
                    "response_chars": totals.response_chars,
                    "wall_seconds": totals.wall_seconds,
                },
                "estimated_remaining_calls": int(est_calls),
            }
        except Exception:
            llm_live_confirm_info = {
                "provider_id": str(os.getenv("EAM_LLM_PROVIDER", "mock")).strip() or "mock",
                "mode": str(os.getenv("EAM_LLM_MODE", "live")).strip() or "live",
                "model": (str(os.getenv("EAM_LLM_REAL_MODEL", "")).strip() or None),
            }

    bp_path = outputs.get("blueprint_draft_path")
    if isinstance(bp_path, str) and Path(bp_path).is_file():
        try:
            blueprint_draft = json.loads(Path(bp_path).read_text(encoding="utf-8"))
        except Exception:
            blueprint_draft = None

    bp_final_path = outputs.get("blueprint_final_path")
    if isinstance(bp_final_path, str) and Path(bp_final_path).is_file():
        try:
            blueprint_final = json.loads(Path(bp_final_path).read_text(encoding="utf-8"))
        except Exception:
            blueprint_final = None

    dsl_path = outputs.get("signal_dsl_path")
    if isinstance(dsl_path, str) and Path(dsl_path).is_file():
        try:
            signal_dsl = json.loads(Path(dsl_path).read_text(encoding="utf-8"))
        except Exception:
            signal_dsl = None

    vars_path = outputs.get("variable_dictionary_path")
    if isinstance(vars_path, str) and Path(vars_path).is_file():
        try:
            variable_dictionary = json.loads(Path(vars_path).read_text(encoding="utf-8"))
        except Exception:
            variable_dictionary = None

    plan_path = outputs.get("calc_trace_plan_path")
    if isinstance(plan_path, str) and Path(plan_path).is_file():
        try:
            calc_trace_plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
        except Exception:
            calc_trace_plan = None

    rs_path = outputs.get("runspec_path")
    if isinstance(rs_path, str) and Path(rs_path).is_file():
        try:
            runspec = json.loads(Path(rs_path).read_text(encoding="utf-8"))
        except Exception:
            runspec = None

    tp_path = outputs.get("calc_trace_preview_path")
    if isinstance(tp_path, str) and Path(tp_path).is_file():
        try:
            trace_preview_rows = _read_csv_rows(Path(tp_path))[:30]
        except Exception:
            trace_preview_rows = []

    tm_path = outputs.get("trace_meta_path")
    if isinstance(tm_path, str) and Path(tm_path).is_file():
        try:
            trace_meta = json.loads(Path(tm_path).read_text(encoding="utf-8"))
        except Exception:
            trace_meta = None

    rpt_path = outputs.get("report_md_path")
    if isinstance(rpt_path, str) and Path(rpt_path).is_file():
        try:
            report_text = Path(rpt_path).read_text(encoding="utf-8")
        except Exception:
            report_text = None

    rpt_sum_path = outputs.get("report_summary_path")
    if isinstance(rpt_sum_path, str) and Path(rpt_sum_path).is_file():
        try:
            report_summary = json.loads(Path(rpt_sum_path).read_text(encoding="utf-8"))
        except Exception:
            report_summary = None

    prop_path = outputs.get("improvement_proposals_path")
    if isinstance(prop_path, str) and Path(prop_path).is_file():
        try:
            improvement_proposals = json.loads(Path(prop_path).read_text(encoding="utf-8"))
        except Exception:
            improvement_proposals = None

    # LLM evidence (Phase-18/19/28): scan agent output dirs for llm_session + redaction + calls + output guard + errors.
    agents_root = paths.outputs_dir / "agents"
    if agents_root.is_dir():
        for name in ("intent", "strategy_spec", "report", "improvement"):
            d = agents_root / name
            sess_p = d / "llm_session.json"
            red_p = d / "redaction_summary.json"
            calls_p = d / "llm_calls.jsonl"
            guard_p = d / "output_guard_report.json"
            err_p = d / "error_summary.json"
            if not (sess_p.is_file() or guard_p.is_file() or err_p.is_file() or calls_p.is_file()):
                continue
            try:
                sess = json.loads(sess_p.read_text(encoding="utf-8"))
            except Exception:
                sess = {}
            try:
                red = json.loads(red_p.read_text(encoding="utf-8")) if red_p.is_file() else {}
            except Exception:
                red = {}
            calls_tail = ""
            if calls_p.is_file():
                try:
                    lines = [ln for ln in calls_p.read_text(encoding="utf-8").splitlines() if ln.strip()]
                    calls_tail = "\n".join(lines[-5:]) + ("\n" if lines else "")
                except Exception:
                    calls_tail = ""
            guard = {}
            if guard_p.is_file():
                try:
                    doc = json.loads(guard_p.read_text(encoding="utf-8"))
                    if isinstance(doc, dict):
                        guard = doc
                except Exception:
                    guard = {}
            err_json = ""
            if err_p.is_file():
                try:
                    doc = json.loads(err_p.read_text(encoding="utf-8"))
                    err_json = json.dumps(doc, indent=2, sort_keys=True) if isinstance(doc, dict) else ""
                except Exception:
                    err_json = ""
            findings_preview = []
            if isinstance(guard, dict) and isinstance(guard.get("findings"), list):
                for f in guard["findings"][:10]:
                    if isinstance(f, dict):
                        findings_preview.append(
                            {
                                "rule_id": f.get("rule_id"),
                                "path": f.get("path"),
                                "message": f.get("message"),
                            }
                        )
            findings_preview_json = json.dumps(findings_preview, indent=2, sort_keys=True) if findings_preview else ""
            llm_evidence.append(
                {
                    "agent": name,
                    "dir": d.as_posix(),
                    "session_json": json.dumps(sess, indent=2, sort_keys=True) if isinstance(sess, dict) else "",
                    "provider_id": (sess.get("provider_id") if isinstance(sess, dict) else None),
                    "mode": (sess.get("mode") if isinstance(sess, dict) else None),
                    "prompt_version": (sess.get("prompt_version") if isinstance(sess, dict) else None),
                    "output_schema_version": (sess.get("output_schema_version") if isinstance(sess, dict) else None),
                    "guard_passed": (guard.get("passed") if isinstance(guard, dict) else None),
                    "guard_status": (guard.get("guard_status") if isinstance(guard, dict) else None),
                    "guard_finding_count": (guard.get("finding_count") if isinstance(guard, dict) else None),
                    "guard_findings_preview": findings_preview,
                    "guard_findings_preview_json": findings_preview_json,
                    "redaction_json": json.dumps(red, indent=2, sort_keys=True) if isinstance(red, dict) and red else "",
                    "calls_tail": calls_tail,
                    "error_summary_json": err_json,
                }
            )

    # Phase-23: sweep evidence (append-only trials.jsonl + derived leaderboard.json).
    sweep_dir = paths.outputs_dir / "sweep"
    lb_path = sweep_dir / "leaderboard.json"
    if lb_path.is_file():
        try:
            sweep_leaderboard = json.loads(lb_path.read_text(encoding="utf-8"))
        except Exception:
            sweep_leaderboard = None
    trials_path = sweep_dir / "trials.jsonl"
    if trials_path.is_file():
        try:
            lines = [ln for ln in trials_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
            for ln in lines[-20:]:
                try:
                    doc = json.loads(ln)
                except Exception:
                    continue
                if isinstance(doc, dict):
                    sweep_trials_tail.append(doc)
        except Exception:
            sweep_trials_tail = []

    # Phase-29: experience retrieval evidence (append-only).
    exp_p = paths.outputs_dir / "experience" / "experience_pack.json"
    if exp_p.is_file():
        try:
            doc = json.loads(exp_p.read_text(encoding="utf-8"))
            if isinstance(doc, dict):
                experience_pack = doc
                experience_pack_json = json.dumps(doc, indent=2, sort_keys=True)
        except Exception:
            experience_pack = None
            experience_pack_json = ""

    snapshot_id_safe = None
    try:
        sid = spec.get("snapshot_id") if isinstance(spec, dict) else None
        if isinstance(sid, str) and sid.strip():
            snapshot_id_safe = require_safe_id(sid.strip(), kind="snapshot_id")
    except Exception:
        snapshot_id_safe = None

    return TEMPLATES.TemplateResponse(
        request,
        "job.html",
        {
            "job_id": job_id,
            "state": state,
            "waiting_approval": waiting,
            "approval_step": waiting_step,
            "snapshot_id": snapshot_id_safe,
            "policy_bundle_path": spec.get("policy_bundle_path"),
            "blueprint_id": (bp.get("blueprint_id") if isinstance(bp, dict) else None),
            "bp_title": (bp.get("title") if isinstance(bp, dict) else spec.get("title") if isinstance(spec, dict) else None),
            "outputs_json": json.dumps(outputs, indent=2, sort_keys=True),
            "events_json": json.dumps(events, indent=2, sort_keys=True),
            "blueprint_draft_json": json.dumps(blueprint_draft, indent=2, sort_keys=True) if blueprint_draft else "",
            "blueprint_final_json": json.dumps(blueprint_final, indent=2, sort_keys=True) if blueprint_final else "",
            "signal_dsl_json": json.dumps(signal_dsl, indent=2, sort_keys=True) if signal_dsl else "",
            "variable_dictionary_json": json.dumps(variable_dictionary, indent=2, sort_keys=True) if variable_dictionary else "",
            "calc_trace_plan_json": json.dumps(calc_trace_plan, indent=2, sort_keys=True) if calc_trace_plan else "",
            "trace_preview_rows": trace_preview_rows,
            "trace_meta_json": json.dumps(trace_meta, indent=2, sort_keys=True) if trace_meta else "",
            "runspec_json": json.dumps(runspec, indent=2, sort_keys=True) if runspec else "",
            "report_text": report_text or "",
            "report_summary_json": json.dumps(report_summary, indent=2, sort_keys=True) if report_summary else "",
            "improvement_proposals_json": json.dumps(improvement_proposals, indent=2, sort_keys=True) if improvement_proposals else "",
            "improvement_proposals_list": (improvement_proposals.get("proposals") if isinstance(improvement_proposals, dict) else []),
            "sweep_leaderboard_json": json.dumps(sweep_leaderboard, indent=2, sort_keys=True) if sweep_leaderboard else "",
            "sweep_leaderboard_obj": (sweep_leaderboard if isinstance(sweep_leaderboard, dict) else None),
            "sweep_trials_tail": sweep_trials_tail,
            "experience_pack": experience_pack,
            "experience_pack_json": experience_pack_json,
            "llm_evidence": llm_evidence,
            "llm_usage_report": llm_usage_report,
            "llm_usage_report_json": llm_usage_report_json,
            "llm_usage_report_path": llm_usage_report_path,
            "llm_usage_events_path": llm_usage_events_path,
            "llm_live_confirm_info": llm_live_confirm_info,
            "title": f"Job {job_id}",
        },
    )


@router.post("/ui/jobs/{job_id}/approve")
def ui_job_approve(request: Request, job_id: str, step: str | None = None) -> RedirectResponse:
    from quant_eam.api.security import enforce_write_auth

    enforce_write_auth(request)
    job_id = require_safe_job_id(job_id)
    jr = _job_root()
    paths = jobs_job_paths(job_id, job_root=jr)
    if not paths.job_spec.is_file():
        raise HTTPException(status_code=404, detail="not found")
    events = jobs_load_events(job_id, job_root=jr)
    if step:
        step = str(step)
        if step not in (
            "blueprint",
            "strategy_spec",
            "runspec",
            "trace_preview",
            "improvements",
            "sweep",
            # Phase-28: operational rollout checkpoints.
            "llm_live_confirm",
            "agent_output_invalid",
        ):
            raise HTTPException(status_code=400, detail="invalid step")
        already = any(
            str(ev.get("event_type")) == "APPROVED"
            and isinstance(ev.get("outputs"), dict)
            and str(ev["outputs"].get("step")) == step
            for ev in events
        )
        if not already:
            jobs_append_event(job_id=job_id, event_type="APPROVED", outputs={"step": step}, job_root=jr)
    else:
        if not any(str(ev.get("event_type")) == "APPROVED" for ev in events):
            jobs_append_event(job_id=job_id, event_type="APPROVED", job_root=jr)
    return RedirectResponse(url=f"/ui/jobs/{job_id}", status_code=303)


@router.post("/ui/jobs/{job_id}/spawn")
def ui_job_spawn(request: Request, job_id: str, proposal_id: str) -> RedirectResponse:
    """UI helper: spawn a child job from a proposal, then redirect back to the base job page."""
    from quant_eam.api.security import enforce_write_auth
    from quant_eam.jobstore.store import BudgetExceeded, spawn_child_job_from_proposal

    enforce_write_auth(request)
    job_id = require_safe_job_id(job_id)
    proposal_id = str(proposal_id).strip()
    if not proposal_id:
        raise HTTPException(status_code=400, detail="missing proposal_id")
    try:
        _ = spawn_child_job_from_proposal(base_job_id=job_id, proposal_id=proposal_id, job_root=_job_root())
    except BudgetExceeded as e:
        raise HTTPException(status_code=409, detail=str(e))
    return RedirectResponse(url=f"/ui/jobs/{job_id}", status_code=303)


@router.post("/ui/jobs/{job_id}/spawn_best")
def ui_job_spawn_best(request: Request, job_id: str) -> RedirectResponse:
    """UI helper: spawn a child job from sweep best, then redirect back to the base job page."""
    from quant_eam.api.security import enforce_write_auth
    from quant_eam.jobstore.store import BudgetExceeded, spawn_child_job_from_sweep_best

    enforce_write_auth(request)
    job_id = require_safe_job_id(job_id)
    try:
        _ = spawn_child_job_from_sweep_best(base_job_id=job_id, job_root=_job_root())
    except BudgetExceeded as e:
        raise HTTPException(status_code=409, detail=str(e))
    return RedirectResponse(url=f"/ui/jobs/{job_id}", status_code=303)
