from __future__ import annotations

import csv
import difflib
import hashlib
import json
import os
import re
import secrets
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

import yaml
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from quant_eam.api.roots import dossiers_root, registry_root
from quant_eam.api.security import enforce_write_auth, require_child_dir, require_safe_id, require_safe_job_id
from quant_eam.contracts import validate as contracts_validate
from quant_eam.datacatalog.catalog import DataCatalog
from quant_eam.jobstore.store import (
    append_event as jobs_append_event,
    create_job_from_ideaspec,
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
APPROVAL_STEPS = (
    "blueprint",
    "strategy_spec",
    "spec_qa",
    "runspec",
    "trace_preview",
    "improvements",
    "sweep",
    "llm_live_confirm",
    "agent_output_invalid",
)
REJECTABLE_STEPS = (
    "blueprint",
    "strategy_spec",
    "spec_qa",
    "runspec",
    "trace_preview",
    "improvements",
    "sweep",
)
REJECT_FALLBACK_STEP: dict[str, str] = {s: s for s in REJECTABLE_STEPS}
RERUN_AGENT_OPTIONS = (
    "intent_agent_v1",
    "strategy_spec_agent_v1",
    "spec_qa_agent_v1",
    "demo_agent_v1",
    "backtest_agent_v1",
    "improvement_agent_v1",
    "report_agent_v1",
)


def _templates() -> Jinja2Templates:
    base = Path(__file__).resolve().parents[1]  # src/quant_eam
    td = base / "ui" / "templates"
    return Jinja2Templates(directory=str(td))


TEMPLATES = _templates()
PROMPT_FILE_RE = re.compile(r"^prompt_v([1-9][0-9]*)\.md$")
PROMPT_VERSION_RE = re.compile(r"^v([1-9][0-9]*)$")
PLAYBOOK_SECTION0_RE = re.compile(r"^##\s*0(?:\s|[.:：])")
PLAYBOOK_SECTION1_RE = re.compile(r"^##\s*1(?:\s|[.:：])")
PLAYBOOK_SECTION2_RE = re.compile(r"^##\s*2(?:\s|[.:：])")
PLAYBOOK_SECTION3_RE = re.compile(r"^##\s*3(?:\s|[.:：])")
PLAYBOOK_SECTION4_RE = re.compile(r"^##\s*4(?:\s|[.:：])")
PLAYBOOK_SECTION5_RE = re.compile(r"^##\s*5(?:\s|[.:：])")
PLAYBOOK_SUBSECTION01_RE = re.compile(r"^###\s*0\.1(?:\s|[.:：])")
PLAYBOOK_SUBSECTION02_RE = re.compile(r"^###\s*0\.2(?:\s|[.:：])")
PLAYBOOK_PHASE_HEADER_RE = re.compile(r"^###\s*Phase[\u2010-\u2015-](\d+)\s*[：:]\s*(.+)$", re.IGNORECASE)
WHOLE_VIEW_SECTION3_RE = re.compile(r"^##\s*3(?:\s|[.:：])")
WHOLE_VIEW_PHASE_HEADER_RE = re.compile(r"^###\s*Phase[\u2010-\u2015-](\d+)\s*[：:]\s*(.+)$", re.IGNORECASE)
WHOLE_VIEW_REVIEW_POINT_RE = re.compile(r"^审阅点\s*#\s*(\d+)(?:（UI）)?\s*[：:]\s*(.+)$")
WHOLE_VIEW_SECTION4_RE = re.compile(r"^##\s*4(?:\s|[.:：])")
WHOLE_VIEW_SECTION5_RE = re.compile(r"^##\s*5(?:\s|[.:：])")
WHOLE_VIEW_OBJECT_HEADER_RE = re.compile(r"^###\s*4\.(\d+)\s*(.+)$")
WHOLE_VIEW_SECTION6_RE = re.compile(r"^##\s*6(?:\s|[.:：])")
WHOLE_VIEW_MODULE_HEADER_RE = re.compile(r"^###\s*6\.(\d+)\s*(.+)$")
WHOLE_VIEW_SECTION7_RE = re.compile(r"^##\s*7(?:\s|[.:：])")
WHOLE_VIEW_SECTION71_RE = re.compile(r"^###\s*7\.1(?:\s|[.:：])")
WHOLE_VIEW_SECTION72_RE = re.compile(r"^###\s*7\.2(?:\s|[.:：])")
WHOLE_VIEW_SECTION8_RE = re.compile(r"^##\s*8(?:\s|[.:：])")
WHOLE_VIEW_SECTION9_RE = re.compile(r"^##\s*9(?:\s|[.:：])")
WHOLE_VIEW_SECTION10_RE = re.compile(r"^##\s*10(?:\s|[.:：])")
WHOLE_VIEW_SECTION11_RE = re.compile(r"^##\s*11(?:\s|[.:：])")
WHOLE_VIEW_SECTION0_RE = re.compile(r"^##\s*0(?:\s|[.:：])")
WHOLE_VIEW_SECTION2_RE = re.compile(r"^##\s*2(?:\s|[.:：])")
WHOLE_VIEW_PLANE_ROW_RE = re.compile(r"^\*\*([^*]+)\*\*\s*[：:]\s*(.+)$")
WHOLE_VIEW_ROADMAP_MILESTONE_RE = re.compile(r"^v([0-9]+(?:\.[0-9]+)?)\s*[：:]\s*(.+)$", re.IGNORECASE)
WHOLE_VIEW_SECTION64_RE = re.compile(r"^###\s*6\.4(?:\s|[.:：])")
WHOLE_VIEW_PHASE_TO_SSOT_CHECKPOINT: dict[int, str] = {
    0: "blueprint",
    1: "strategy_spec",
    2: "trace_preview",
    3: "runspec",
    4: "improvements",
}
PLAYBOOK_PHASE_KEYWORDS: dict[int, tuple[str, ...]] = {
    0: ("repo", "bootstrap", "docker"),
    1: ("contract", "contracts", "schema", "blueprint", "runspec"),
    2: ("policy", "policies", "governance"),
    3: ("data", "snapshot", "ingest", "catalog", "qa fetch"),
    4: ("backtest", "runner", "vectorbt"),
    5: ("gate", "holdout"),
    6: ("ui", "readonly", "read only", "review"),
    7: ("orchestrator", "workflow"),
    8: ("agent", "agents", "spec qa", "improvement"),
    9: ("demo", "trace"),
    10: ("registry", "card", "experience"),
    11: ("composer", "compose"),
    12: ("diagnostic", "diagnostics", "promotion"),
}
OBJECT_MODEL_PLAYBOOK_KEYWORDS: dict[str, tuple[str, ...]] = {
    "IdeaSpec": ("idea", "输入", "审阅点 #1", "intent"),
    "Blueprint": ("blueprint", "审阅点 #1", "data_requirements", "evaluation_protocol"),
    "RunSpec": ("runspec", "compiler", "runspec"),
    "Dossier": ("dossier", "curve", "trades", "metrics"),
    "GateResults": ("gate", "pass/fail", "gate_results", "holdout"),
    "Experience Card": ("experience card", "经验卡", "registry", "card", "入库"),
}
MODULE_BOUNDARY_PLAYBOOK_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Data Plane": ("data plane", "data", "snapshot", "ingest", "catalog", "as_of", "available_at"),
    "Backtest Plane": ("backtest", "vectorbt", "runner", "dossier", "runspec"),
    "Deterministic Kernel": (
        "deterministic",
        "kernel",
        "contracts",
        "policies",
        "compiler",
        "runner",
        "gate",
        "holdout",
        "registry",
        "budget",
    ),
    "Agents Plane": ("agents", "agent", "orchestrator", "harness", "spec qa", "improvement", "diagnostics"),
}
IA_ROUTE_VIEW_CATALOG: dict[str, dict[str, str]] = {
    "/ui": {"view_name": "Idea input", "template": "index.html"},
    "/ui/jobs": {"view_name": "Runs queue", "template": "jobs.html"},
    "/ui/jobs/{job_id}": {"view_name": "Blueprint and review checkpoints", "template": "job.html"},
    "/ui/runs/{run_id}": {"view_name": "Dossier detail", "template": "run.html"},
    "/ui/runs/{run_id}/gates": {"view_name": "Gate detail", "template": "run_gates.html"},
    "/ui/cards/{card_id}": {"view_name": "Registry card detail", "template": "card.html"},
    "/ui/composer": {"view_name": "Composer", "template": "composer.html"},
    "/ui/workbench": {"view_name": "Workbench", "template": "workbench.html"},
    "/ui/workbench/req/wb-002": {"view_name": "Workbench requirement entry", "template": "workbench.html"},
    "/ui/workbench/{session_id}": {"view_name": "Workbench session", "template": "workbench.html"},
}
IA_CHECKLIST_ROUTE_BINDINGS: dict[int, list[str]] = {
    1: ["/ui"],
    2: ["/ui/jobs/{job_id}"],
    3: ["/ui/jobs/{job_id}"],
    4: ["/ui/jobs/{job_id}", "/ui/runs/{run_id}"],
    5: ["/ui/jobs"],
    6: ["/ui/runs/{run_id}"],
    7: ["/ui/runs/{run_id}/gates"],
    8: ["/ui/cards/{card_id}", "/ui/composer"],
}
IA_CHECKLIST_MAPPING_NOTES: dict[int, str] = {
    1: "IdeaSpec form entry and constraint input.",
    2: "Blueprint outputs and policy/data/evaluation review fields.",
    3: "Pseudocode and variable dictionary review evidence on job detail.",
    4: "Trace preview and K-line/trade overlays in checkpoint and run detail.",
    5: "Job list page shows workflow queue and run progression state.",
    6: "Run detail renders dossier metrics, trades, and segmented evidence.",
    7: "Gate detail renders gate-by-gate pass/fail with evidence links.",
    8: "Registry card detail plus composer entry for portfolio composition.",
}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def _repo_root() -> Path:
    cur = Path(__file__).resolve()
    for p in [cur, *cur.parents]:
        if (p / "pyproject.toml").is_file() and (p / "src").is_dir():
            return p
    return cur.parents[3]


def _prompts_root() -> Path:
    raw = str(os.getenv("EAM_PROMPTS_ROOT", "")).strip()
    if raw:
        return Path(raw)
    return _repo_root() / "prompts" / "agents"


def _prompt_overrides_root() -> Path:
    raw = str(os.getenv("EAM_PROMPT_OVERLAY_ROOT", "")).strip()
    if raw:
        return Path(raw)
    return Path(os.getenv("EAM_ARTIFACT_ROOT", "/artifacts")) / "prompt_overrides" / "agents"


def _prompt_audit_log_path() -> Path:
    raw = str(os.getenv("EAM_PROMPT_AUDIT_LOG", "")).strip()
    if raw:
        return Path(raw)
    return Path(os.getenv("EAM_ARTIFACT_ROOT", "/artifacts")) / "audit" / "prompt_events.jsonl"


def _append_jsonl(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(doc, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n")


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


WORKBENCH_PHASE_STEPS = (
    "idea",
    "strategy_spec",
    "trace_preview",
    "runspec",
    "improvements",
)
WORKBENCH_DRAFT_VERSION_RE = re.compile(r"^draft_v([1-9][0-9]*)\.json$")
WORKBENCH_PHASE_TITLES: dict[str, str] = {
    "idea": "Phase-0 Idea Intake",
    "strategy_spec": "Phase-1 Strategy Spec",
    "trace_preview": "Phase-2 Demo Trace Preview",
    "runspec": "Phase-3 Research Backtest",
    "improvements": "Phase-4 Improvements and Registry",
}


def _workbench_root() -> Path:
    return Path(os.getenv("EAM_ARTIFACT_ROOT", "/artifacts")) / "workbench"


def _workbench_sessions_root() -> Path:
    return _workbench_root() / "sessions"


def _workbench_session_root(session_id: str) -> Path:
    sid = require_safe_id(session_id, kind="session_id")
    return _workbench_sessions_root() / sid


def _workbench_session_path(session_id: str) -> Path:
    return _workbench_session_root(session_id) / "session.json"


def _workbench_events_path(session_id: str) -> Path:
    return _workbench_session_root(session_id) / "events.jsonl"


def _workbench_session_store_url(session_id: str) -> str:
    return _workbench_session_path(session_id).as_posix()


def _workbench_job_id(session_id: str) -> str:
    fallback = f"job_{session_id}"
    p = _workbench_session_path(session_id)
    if not p.is_file():
        return fallback
    try:
        doc = _load_json(p)
    except Exception:
        return fallback
    if not isinstance(doc, dict):
        return fallback
    job_id = str(doc.get("job_id") or "").strip()
    if not job_id:
        return fallback
    return job_id


def _workbench_job_outputs_root(session_id: str) -> Path:
    return Path(os.getenv("EAM_ARTIFACT_ROOT", "/artifacts")) / "jobs" / _workbench_job_id(session_id) / "outputs" / "workbench"


def _workbench_cards_root(session_id: str) -> Path:
    return _workbench_job_outputs_root(session_id) / "cards"


def _workbench_step_drafts_root(session_id: str, step: str) -> Path:
    return _workbench_job_outputs_root(session_id) / "step_drafts" / step


def _workbench_cards_index_path(session_id: str) -> Path:
    return _workbench_cards_root(session_id) / "cards_index.jsonl"


def _workbench_phase_no(step: str) -> int:
    try:
        return WORKBENCH_PHASE_STEPS.index(str(step))
    except ValueError:
        return 0


def _workbench_phase_label(step: str) -> str:
    return f"Phase-{_workbench_phase_no(step)}"


def _workbench_phase_title(step: str) -> str:
    return str(WORKBENCH_PHASE_TITLES.get(str(step)) or str(step))


def _new_workbench_session_id() -> str:
    while True:
        sid = f"ws_{secrets.token_hex(4)}"
        if not _workbench_session_root(sid).is_dir():
            return sid


def _parse_workbench_request_payload(payload: Any) -> dict[str, Any]:
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        return {}

    out: dict[str, Any] = {}
    for k, v in payload.items():
        key = str(k).strip()
        if not key:
            continue
        if isinstance(v, list):
            if len(v) == 1:
                out[key] = v[0]
            elif len(v) == 0:
                out[key] = ""
            else:
                out[key] = v
        else:
            out[key] = v
    return out


def _coerce_symbol_list(value: Any) -> list[str]:
    if isinstance(value, list):
        out = [str(x).strip() for x in value if str(x).strip()]
        return out
    if isinstance(value, str):
        return [x.strip() for x in value.split(",") if x.strip()]
    return []


def _env_flag(name: str, *, default: bool = False) -> bool:
    raw = str(os.getenv(name, "1" if default else "0")).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _workbench_real_jobs_enabled() -> bool:
    return _env_flag("EAM_WORKBENCH_REAL_JOBS", default=False)


def _workbench_enable_ui_intake_agent() -> bool:
    return _env_flag("EAM_WORKBENCH_ENABLE_UI_INTAKE_AGENT", default=True)


def _required_workbench_fields(payload: dict[str, Any], *fields: str) -> None:
    missing = [name for name in fields if str(payload.get(name, "")).strip() == ""]
    if missing:
        raise HTTPException(status_code=422, detail=f"missing required workbench fields: {', '.join(sorted(set(missing)))}")


async def _read_workbench_payload(request: Request) -> dict[str, Any]:
    body = await request.body()
    content_type = str(request.headers.get("content-type", "")).lower()
    return _normalize_workbench_body(body, content_type)


def _normalize_workbench_body(body: bytes, content_type: str) -> dict[str, Any]:
    if "application/json" in content_type.lower():
        if not body:
            return {}
        try:
            doc = json.loads(body.decode("utf-8"))
        except Exception:  # noqa: BLE001
            raise HTTPException(status_code=400, detail="invalid JSON body")
        if not isinstance(doc, dict):
            raise HTTPException(status_code=400, detail="request body must be object")
        return _parse_workbench_request_payload(doc)

    parsed = parse_qs(body.decode("utf-8", errors="ignore"), keep_blank_values=True)
    return _parse_workbench_request_payload(parsed)


def _load_workbench_session(session_id: str) -> dict[str, Any]:
    p = _workbench_session_path(session_id)
    if not p.is_file():
        raise HTTPException(status_code=404, detail="workbench session not found")
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=409, detail="workbench session payload invalid")
    if not isinstance(doc, dict):
        raise HTTPException(status_code=409, detail="workbench session payload invalid")
    return doc


def _write_workbench_session(session_id: str, doc: dict[str, Any]) -> None:
    _write_json(_workbench_session_path(session_id), doc)


def _append_workbench_event(
    session_id: str,
    *,
    step: str,
    action: str,
    payload: dict[str, Any] | None = None,
    actor: str = "system",
    source: str = "",
    status: str = "",
) -> dict[str, Any]:
    event_index = len(_read_workbench_events(session_id)) + 1
    actor_norm = "user" if str(actor).strip().lower() == "user" else "system"
    event: dict[str, Any] = {
        "schema_version": "workbench_event_v1",
        "event_id": f"wev_{event_index:04d}",
        "event_index": event_index,
        "event_type": action,
        "actor": actor_norm,
        "session_id": session_id,
        "step": step,
        "created_at": _now_iso(),
    }
    source_text = str(source).strip()
    if source_text:
        event["source"] = source_text
    status_text = str(status).strip()
    if status_text:
        event["status"] = status_text
    if payload:
        event["payload"] = payload
    _append_jsonl(_workbench_events_path(session_id), event)
    return event


def _read_workbench_events(session_id: str) -> list[dict[str, Any]]:
    p = _workbench_events_path(session_id)
    if not p.is_file():
        return []
    out: list[dict[str, Any]] = []
    for raw in p.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
        except Exception:  # noqa: BLE001
            continue
        if isinstance(item, dict):
            out.append(item)
    return out


def _bump_workbench_revision(session: dict[str, Any]) -> int:
    raw = session.get("revision")
    if isinstance(raw, int) and raw >= 0:
        rev = raw + 1
    else:
        rev = 1
    session["revision"] = rev
    return rev


def _ensure_workbench_phase_card(
    *,
    session_id: str,
    session: dict[str, Any],
    step: str,
    trigger_event: dict[str, Any],
    summary_lines: list[str],
    details: dict[str, Any],
    artifacts: list[str],
    force_new: bool = False,
) -> dict[str, Any]:
    cards = session.get("cards")
    if not isinstance(cards, list):
        cards = []
        session["cards"] = cards
    phase_cards = session.get("phase_cards")
    if not isinstance(phase_cards, dict):
        phase_cards = {}
        session["phase_cards"] = phase_cards

    existing_path = str(phase_cards.get(step) or "").strip()
    if existing_path and (not force_new):
        p = Path(existing_path)
        if p.is_file():
            try:
                doc = _load_json(p)
            except Exception:
                doc = None
            if isinstance(doc, dict):
                return doc

    card_index = len(cards) + 1
    now = _now_iso()
    card_path = _workbench_cards_root(session_id) / f"card_{card_index:03d}_{step}.json"
    evidence_artifacts = [str(x).strip() for x in artifacts if str(x).strip()]
    card_doc = {
        "schema_version": "workbench_card_v1",
        "card_id": f"{session_id}-{card_index:03d}",
        "card_index": card_index,
        "session_id": session_id,
        "job_id": str(session.get("job_id") or ""),
        "phase": step,
        "phase_no": _workbench_phase_no(step),
        "phase_label": _workbench_phase_label(step),
        "title": _workbench_phase_title(step),
        "summary_lines": summary_lines,
        "details": details,
        "created_at": now,
        "artifact_path": card_path.as_posix(),
        "evidence": {
            "events_path": _workbench_events_path(session_id).as_posix(),
            "session_path": _workbench_session_path(session_id).as_posix(),
            "cards_index_path": _workbench_cards_index_path(session_id).as_posix(),
            "event_id": str(trigger_event.get("event_id") or ""),
            "event_index": int(trigger_event.get("event_index") or 0),
            "event_type": str(trigger_event.get("event_type") or ""),
            "artifacts": evidence_artifacts,
            "governance": {
                "append_only": True,
                "replay_hint": "Replay from events.jsonl in event_index order and open each card artifact path.",
            },
        },
    }
    _write_json(card_path, card_doc)
    _append_jsonl(
        _workbench_cards_index_path(session_id),
        {
            "schema_version": "workbench_card_index_event_v1",
            "event_type": "card_created",
            "session_id": session_id,
            "phase": step,
            "card_id": card_doc["card_id"],
            "card_index": card_index,
            "card_path": card_path.as_posix(),
            "created_at": now,
            "trigger_event_id": str(trigger_event.get("event_id") or ""),
            "trigger_event_index": int(trigger_event.get("event_index") or 0),
        },
    )
    cards.append(
        {
            "card_id": card_doc["card_id"],
            "card_index": card_index,
            "phase": step,
            "phase_label": _workbench_phase_label(step),
            "title": card_doc["title"],
            "artifact_path": card_path.as_posix(),
            "created_at": now,
        }
    )
    phase_cards[step] = card_path.as_posix()
    session["cards"] = cards
    session["phase_cards"] = phase_cards
    return card_doc


def _workbench_step_summary(session: dict[str, Any], *, step: str) -> tuple[list[str], dict[str, Any], list[str]]:
    idea = session.get("idea")
    idea_doc = idea if isinstance(idea, dict) else {}
    symbols_raw = idea_doc.get("symbols")
    symbols: list[str] = []
    if isinstance(symbols_raw, list):
        symbols = [str(x).strip() for x in symbols_raw if str(x).strip()]
    elif isinstance(symbols_raw, str):
        symbols = [x.strip() for x in symbols_raw.split(",") if x.strip()]
    title = str(idea_doc.get("title") or "").strip()
    hypothesis = str(idea_doc.get("hypothesis_text") or "").strip()

    if step == "idea":
        summary = [
            f"Idea: {title or '(untitled)'}",
            f"Symbols: {', '.join(symbols) if symbols else '(none)'}",
            "Session created and ready for strategy drafting.",
        ]
        return summary, {"idea": idea_doc}, []
    if step == "strategy_spec":
        draft_meta = session.get("drafts") if isinstance(session.get("drafts"), dict) else {}
        sel = draft_meta.get("strategy_spec") if isinstance(draft_meta.get("strategy_spec"), dict) else {}
        sel_path = str(sel.get("path") or "").strip()
        job_id = str(session.get("job_id") or "").strip()
        readable = _workbench_strategy_readable_summary(job_id=job_id) if job_id else {}
        var_summary = readable.get("variable_dictionary_summary") if isinstance(readable, dict) else {}
        trace_summary = readable.get("trace_plan_summary") if isinstance(readable, dict) else {}
        pseudo_lines = readable.get("pseudocode_lines") if isinstance(readable, dict) else []
        variable_count = int(var_summary.get("variable_count") or 0) if isinstance(var_summary, dict) else 0
        lagged_count = int(var_summary.get("lagged_variable_count") or 0) if isinstance(var_summary, dict) else 0
        trace_step_count = int(trace_summary.get("step_count") or 0) if isinstance(trace_summary, dict) else 0
        assertion_count = int(trace_summary.get("assertion_count") or 0) if isinstance(trace_summary, dict) else 0
        source_paths = readable.get("source_paths") if isinstance(readable, dict) else {}
        summary = [
            "Strategy summary prepared for review and draft editing.",
            f"Pseudocode lines: {len(pseudo_lines) if isinstance(pseudo_lines, list) else 0}",
            f"Variable dictionary: {variable_count} vars ({lagged_count} lagged)",
            f"Trace plan: {trace_step_count} steps, {assertion_count} assertions",
            f"Selected draft: {sel_path if sel_path else '(none)'}",
        ]
        arts = [sel_path] if sel_path else []
        if isinstance(source_paths, dict):
            for ref in source_paths.values():
                if isinstance(ref, str) and ref.strip():
                    arts.append(ref.strip())
        return (
            summary,
            {
                "selected_draft_path": sel_path,
                "hypothesis_text": hypothesis,
                "strategy_readable": readable,
            },
            arts,
        )
    if step == "trace_preview":
        probe_path = str(session.get("last_fetch_probe") or "").strip()
        summary = [
            "Demo trace preview checkpoint reached.",
            f"Fetch probe artifact: {probe_path if probe_path else '(not generated yet)'}",
            "Proceed after reviewing preview samples and assumptions.",
        ]
        arts = [probe_path] if probe_path else []
        return summary, {"last_fetch_probe": probe_path}, arts
    if step == "runspec":
        summary = [
            "Research backtest stage prepared.",
            "RunSpec evidence remains deterministic and append-only.",
            f"Job binding: {str(session.get('job_id') or '')}",
        ]
        return summary, {"job_id": str(session.get("job_id") or "")}, []
    summary = [
        "Improvement stage reached.",
        "Artifacts remain traceable for approval and replay.",
        "Session can be replayed from event log + card index.",
    ]
    return summary, {"status": str(session.get("status") or "active")}, []


def _workbench_card_api_payload(card_doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "card_id": str(card_doc.get("card_id") or ""),
        "card_index": int(card_doc.get("card_index") or 0),
        "phase": str(card_doc.get("phase") or ""),
        "phase_label": str(card_doc.get("phase_label") or ""),
        "title": str(card_doc.get("title") or ""),
        "summary_lines": card_doc.get("summary_lines") if isinstance(card_doc.get("summary_lines"), list) else [],
        "artifact_path": str(card_doc.get("artifact_path") or ""),
        "created_at": str(card_doc.get("created_at") or ""),
    }


def _workbench_cards_for_view(session: dict[str, Any]) -> list[dict[str, Any]]:
    refs = session.get("cards")
    if not isinstance(refs, list):
        return []
    out: list[dict[str, Any]] = []
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        card_path = str(ref.get("artifact_path") or "").strip()
        if not card_path:
            continue
        p = Path(card_path)
        if not p.is_file():
            continue
        try:
            doc = _load_json(p)
        except Exception:
            continue
        if not isinstance(doc, dict):
            continue
        evidence = doc.get("evidence") if isinstance(doc.get("evidence"), dict) else {}
        details = doc.get("details") if isinstance(doc.get("details"), (dict, list)) else {}
        summary_lines = doc.get("summary_lines") if isinstance(doc.get("summary_lines"), list) else []
        out.append(
            {
                "card_id": str(doc.get("card_id") or ""),
                "card_index": int(doc.get("card_index") or 0),
                "phase": str(doc.get("phase") or ""),
                "phase_label": str(doc.get("phase_label") or ""),
                "title": str(doc.get("title") or ""),
                "summary_lines": [str(x) for x in summary_lines if str(x).strip()],
                "artifact_path": p.as_posix(),
                "details": details if isinstance(details, dict) else {},
                "evidence_json": json.dumps(evidence, ensure_ascii=True, indent=2, sort_keys=True),
                "details_json": json.dumps(details, ensure_ascii=True, indent=2, sort_keys=True),
                "created_at": str(doc.get("created_at") or ""),
            }
        )
    out.sort(key=lambda row: int(row.get("card_index") or 0))
    return out


def _initial_workbench_session(*, session_id: str, idea: dict[str, Any], job_id: str) -> dict[str, Any]:
    now = _now_iso()
    return {
        "schema_version": "workbench_session_v1",
        "session_id": session_id,
        "job_id": job_id,
        "created_at": now,
        "updated_at": now,
        "title": idea.get("title", ""),
        "status": "active",
        "current_step": "idea",
        "step_index": 0,
        "idea": idea,
        "trace": [
            {
                "step": WORKBENCH_PHASE_STEPS[0],
                "status": "in_progress",
                "status_text": "idea captured",
            }
        ],
        "messages": [],
        "drafts": {},
        "cards": [],
        "phase_cards": {},
        "selected_drafts": {},
        "fetch_probe_status": "idle",
        "fetch_probe_error": "",
        "fetch_probe_preview_rows": [],
        "contract_freeze": {
            "session_schema_version": "workbench_session_v1",
            "session_event_schema_version": "workbench_event_v1",
            "job_event_schema_version": "job_event_v2",
        },
        "revision": 1,
        "session_json_path": _workbench_session_store_url(session_id),
        "events_path": _workbench_events_path(session_id).as_posix(),
        "cards_index_path": _workbench_cards_index_path(session_id).as_posix(),
        "snapshot_artifacts_path": f"artifacts/workbench/sessions/{session_id}/session.json",
    }


def _load_json_dict(path_text: str) -> dict[str, Any] | None:
    path = Path(str(path_text).strip())
    if not path.is_file():
        return None
    try:
        doc = _load_json(path)
    except Exception:
        return None
    if not isinstance(doc, dict):
        return None
    return doc


def _signal_expr_to_pseudocode(expr: Any, *, depth: int = 0) -> str:
    if depth > 6:
        return "..."
    if not isinstance(expr, dict):
        return repr(expr)
    expr_type = str(expr.get("type") or "").strip().lower()
    if expr_type == "const":
        return repr(expr.get("value"))
    if expr_type == "var":
        var_id = str(expr.get("var_id") or "").strip()
        return var_id or "var"
    if expr_type == "not":
        inner = _signal_expr_to_pseudocode(expr.get("value"), depth=depth + 1)
        return f"not ({inner})"

    op_map = {
        "and": "and",
        "or": "or",
        "eq": "==",
        "ne": "!=",
        "gt": ">",
        "ge": ">=",
        "lt": "<",
        "le": "<=",
        "add": "+",
        "sub": "-",
        "mul": "*",
        "div": "/",
    }
    if expr_type in op_map:
        left = _signal_expr_to_pseudocode(expr.get("left"), depth=depth + 1)
        right = _signal_expr_to_pseudocode(expr.get("right"), depth=depth + 1)
        return f"({left} {op_map[expr_type]} {right})"

    args = expr.get("args")
    if isinstance(args, list) and args:
        rendered = ", ".join(_signal_expr_to_pseudocode(x, depth=depth + 1) for x in args[:6])
        return f"{expr_type}({rendered})" if expr_type else f"fn({rendered})"

    raw_blob = json.dumps(expr, ensure_ascii=True, sort_keys=True)
    return raw_blob if len(raw_blob) <= 120 else f"{raw_blob[:117]}..."


def _workbench_strategy_readable_summary(*, job_id: str) -> dict[str, Any]:
    outputs = _load_job_outputs_index(job_id)
    signal_dsl_path = str(outputs.get("signal_dsl_path") or "").strip()
    variable_dictionary_path = str(outputs.get("variable_dictionary_path") or "").strip()
    calc_trace_plan_path = str(outputs.get("calc_trace_plan_path") or "").strip()

    signal_dsl = _load_json_dict(signal_dsl_path) if signal_dsl_path else None
    variable_dictionary = _load_json_dict(variable_dictionary_path) if variable_dictionary_path else None
    calc_trace_plan = _load_json_dict(calc_trace_plan_path) if calc_trace_plan_path else None

    pseudocode_lines: list[str] = []
    if isinstance(signal_dsl, dict):
        signals = signal_dsl.get("signals") if isinstance(signal_dsl.get("signals"), dict) else {}
        expressions = signal_dsl.get("expressions") if isinstance(signal_dsl.get("expressions"), dict) else {}
        entry_id = str(signals.get("entry") or "entry").strip() or "entry"
        exit_id = str(signals.get("exit") or "exit").strip() or "exit"
        pseudocode_lines.append(f"entry_raw = {_signal_expr_to_pseudocode(expressions.get(entry_id))}")
        pseudocode_lines.append(f"exit_raw = {_signal_expr_to_pseudocode(expressions.get(exit_id))}")
        execution = signal_dsl.get("execution") if isinstance(signal_dsl.get("execution"), dict) else {}
        order_timing = str(execution.get("order_timing") or "").strip()
        if order_timing:
            pseudocode_lines.append(f"order_timing = '{order_timing}'")

    kind_counts: dict[str, int] = {}
    lagged_rows: list[str] = []
    sample_var_ids: list[str] = []
    variable_count = 0
    if isinstance(variable_dictionary, dict):
        variables = variable_dictionary.get("variables") if isinstance(variable_dictionary.get("variables"), list) else []
        for row in variables:
            if not isinstance(row, dict):
                continue
            variable_count += 1
            var_id = str(row.get("var_id") or "").strip()
            if var_id and len(sample_var_ids) < 6:
                sample_var_ids.append(var_id)
            kind = str(row.get("kind") or "unknown").strip() or "unknown"
            kind_counts[kind] = int(kind_counts.get(kind, 0)) + 1
            alignment = row.get("alignment") if isinstance(row.get("alignment"), dict) else {}
            lag_bars = alignment.get("lag_bars")
            if not isinstance(lag_bars, int) or lag_bars <= 0:
                continue
            src_var = ""
            compute = row.get("compute") if isinstance(row.get("compute"), dict) else {}
            ast = compute.get("ast") if isinstance(compute.get("ast"), dict) else {}
            if str(ast.get("type") or "") == "var":
                src_var = str(ast.get("var_id") or "").strip()
            if src_var:
                lagged_rows.append(f"{var_id} = lag({src_var}, {lag_bars})")
            else:
                lagged_rows.append(f"{var_id} uses lag={lag_bars}")
        for item in lagged_rows[:2]:
            if item not in pseudocode_lines:
                pseudocode_lines.append(item)

    trace_step_count = 0
    assertion_count = 0
    sample_count = 0
    first_step_title = ""
    first_step_variables: list[str] = []
    sample_windows: list[str] = []
    if isinstance(calc_trace_plan, dict):
        steps = calc_trace_plan.get("steps") if isinstance(calc_trace_plan.get("steps"), list) else []
        assertions = calc_trace_plan.get("assertions") if isinstance(calc_trace_plan.get("assertions"), list) else []
        samples = calc_trace_plan.get("samples") if isinstance(calc_trace_plan.get("samples"), list) else []
        trace_step_count = len(steps)
        assertion_count = len(assertions)
        sample_count = len(samples)
        if steps and isinstance(steps[0], dict):
            first_step_title = str(steps[0].get("title") or "").strip()
            vars0 = steps[0].get("variables") if isinstance(steps[0].get("variables"), list) else []
            first_step_variables = [str(x).strip() for x in vars0 if str(x).strip()][:8]
        for sample in samples[:3]:
            if not isinstance(sample, dict):
                continue
            symbols = sample.get("symbols") if isinstance(sample.get("symbols"), list) else []
            symbols_text = ",".join(str(x).strip() for x in symbols if str(x).strip()) or "(auto)"
            start = str(sample.get("start") or "").strip() or "?"
            end = str(sample.get("end") or "").strip() or "?"
            sample_windows.append(f"{symbols_text} {start}..{end}")

    return {
        "available": bool(signal_dsl or variable_dictionary or calc_trace_plan),
        "pseudocode_lines": pseudocode_lines[:12],
        "pseudocode_text": "\n".join(pseudocode_lines[:12]),
        "variable_dictionary_summary": {
            "variable_count": variable_count,
            "kind_counts": kind_counts,
            "lagged_variable_count": len(lagged_rows),
            "sample_var_ids": sample_var_ids,
        },
        "trace_plan_summary": {
            "step_count": trace_step_count,
            "assertion_count": assertion_count,
            "sample_count": sample_count,
            "first_step_title": first_step_title,
            "first_step_variables": first_step_variables,
            "sample_windows": sample_windows,
        },
        "source_paths": {
            "signal_dsl_path": signal_dsl_path,
            "variable_dictionary_path": variable_dictionary_path,
            "calc_trace_plan_path": calc_trace_plan_path,
        },
    }


def _coerce_workbench_sample_n(value: Any, *, default: int = 50) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = default
    return max(1, min(500, parsed))


def _coerce_workbench_date_text(value: Any, *, default: str) -> str:
    text = str(value or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text
    return default


def _workbench_message_from_payload(payload: dict[str, Any]) -> str:
    message = str(payload.get("message") or "").strip()
    if message:
        return message
    title = str(payload.get("title") or "").strip()
    hypothesis = str(payload.get("hypothesis_text") or "").strip()
    parts = [p for p in (title, hypothesis) if p]
    return "；".join(parts).strip()


def _contains_forbidden_fetch_function_fields(node: Any) -> bool:
    if isinstance(node, dict):
        for key, value in node.items():
            normalized = str(key).strip().lower()
            if normalized in {"function", "function_override"}:
                return True
            if _contains_forbidden_fetch_function_fields(value):
                return True
        return False
    if isinstance(node, list):
        return any(_contains_forbidden_fetch_function_fields(item) for item in node)
    return False


def _extract_symbols_from_preview_rows(rows: Any) -> list[str]:
    if not isinstance(rows, list):
        return []
    seen: set[str] = set()
    out: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        for key in ("code", "symbol", "symbols", "ticker"):
            val = row.get(key)
            if isinstance(val, list):
                values = [str(x).strip() for x in val if str(x).strip()]
            elif isinstance(val, str):
                values = [x.strip() for x in val.split(",") if x.strip()]
            else:
                values = []
            for symbol in values:
                if symbol in seen:
                    continue
                seen.add(symbol)
                out.append(symbol)
    return out


def _extract_symbols_from_fetch_result(result: Any) -> list[str]:
    if result is None:
        return []
    seen: set[str] = set()
    out: list[str] = []

    final_kwargs = getattr(result, "final_kwargs", None)
    if isinstance(final_kwargs, dict):
        for key in ("symbol", "symbols", "code"):
            val = final_kwargs.get(key)
            symbols = _coerce_symbol_list(val) if isinstance(val, (str, list)) else []
            for symbol in symbols:
                if symbol in seen:
                    continue
                seen.add(symbol)
                out.append(symbol)

    preview = getattr(result, "preview", None)
    for symbol in _extract_symbols_from_preview_rows(preview):
        if symbol in seen:
            continue
        seen.add(symbol)
        out.append(symbol)
    return out


def _normalize_idea_frequency(raw: Any) -> str:
    value = str(raw or "").strip().lower()
    if value in {"day", "1d"}:
        return "1d"
    if value:
        return value
    return "1d"


def _workbench_intake_fallback_bundle(
    *,
    message: str,
    sample_n: int,
    start: str,
    end: str,
) -> dict[str, Any]:
    return {
        "schema_version": "ui_intake_bundle_v1",
        "normalized_request": {
            "title": "CN ma250_trend_filter_v1 effectiveness",
            "hypothesis_text": message,
            "asset": "stock",
            "venue": "CN",
            "universe_hint": "A_SHARE",
            "frequency": "1d",
            "start": start,
            "end": end,
            "sample_n": sample_n,
            "need_user_clarification": False,
        },
        "strategy_template": "ma250_trend_filter_v1",
        "fetch_request": {
            "schema_version": "fetch_request_v1",
            "mode": "backtest",
            "auto_symbols": True,
            "intent": {
                "asset": "stock",
                "freq": "day",
                "venue": "CN",
                "universe": "A_SHARE",
                "fields": ["open", "high", "low", "close", "volume"],
                "start": start,
                "end": end,
                "auto_symbols": True,
                "sample": {"method": "stable_first_n", "n": sample_n},
            },
        },
    }


def _run_workbench_ui_intake_agent(*, session_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
    message = _workbench_message_from_payload(payload)
    if not message:
        raise HTTPException(status_code=422, detail="message is required")
    sample_n = _coerce_workbench_sample_n(payload.get("sample_n"), default=50)
    start = _coerce_workbench_date_text(payload.get("start"), default="2016-01-01")
    end = _coerce_workbench_date_text(payload.get("end"), default="2025-12-31")

    if not _workbench_enable_ui_intake_agent():
        return _workbench_intake_fallback_bundle(message=message, sample_n=sample_n, start=start, end=end), message

    from quant_eam.agents.harness import run_agent

    out_dir = _workbench_session_root(session_id) / "agents" / "ui_intake"
    input_path = out_dir / "agent_input.json"
    _write_json(
        input_path,
        {
            "message": message,
            "sample_n": sample_n,
            "start": start,
            "end": end,
            "title": str(payload.get("title") or "").strip(),
            "hypothesis_text": str(payload.get("hypothesis_text") or "").strip(),
        },
    )
    _ = run_agent(agent_id="ui_intake_agent_v1", input_path=input_path, out_dir=out_dir, provider="mock")
    bundle_path = out_dir / "ui_intake_bundle.json"
    if not bundle_path.is_file():
        raise HTTPException(status_code=500, detail="ui intake bundle missing")
    bundle = _load_json(bundle_path)
    if not isinstance(bundle, dict):
        raise HTTPException(status_code=500, detail="ui intake bundle invalid")
    if _contains_forbidden_fetch_function_fields(bundle.get("fetch_request")):
        raise HTTPException(status_code=422, detail="ui intake fetch_request must be intent-first (no function/function_override)")
    return bundle, message


def _workbench_fetch_evidence_root_for_job(job_id: str) -> Path:
    return Path(os.getenv("EAM_ARTIFACT_ROOT", "/artifacts")) / "jobs" / job_id / "outputs" / "fetch"


def _workbench_real_phase_for_checkpoint(checkpoint: str) -> str:
    cp = str(checkpoint or "").strip()
    if cp in {"idea", "blueprint"}:
        return "idea"
    if cp in {"strategy_spec", "spec_qa"}:
        return "strategy_spec"
    if cp in {"trace_preview"}:
        return "trace_preview"
    if cp in {"runspec", "run_completed", "gates_completed", "report_completed"}:
        return "runspec"
    if cp in {"improvements", "done"}:
        return "improvements"
    return "idea"


def _latest_job_waiting_step(events: list[dict[str, Any]]) -> str | None:
    if not events:
        return None
    latest = events[-1]
    if str(latest.get("event_type") or "") != "WAITING_APPROVAL":
        return None
    outputs = latest.get("outputs") if isinstance(latest.get("outputs"), dict) else {}
    step = str(outputs.get("step") or "").strip()
    return step or None


def _job_has_approved_step(events: list[dict[str, Any]], *, step: str) -> bool:
    for ev in events:
        if str(ev.get("event_type") or "") != "APPROVED":
            continue
        outputs = ev.get("outputs") if isinstance(ev.get("outputs"), dict) else {}
        if str(outputs.get("step") or "") == str(step):
            return True
    return False


def _load_job_outputs_index(job_id: str) -> dict[str, Any]:
    try:
        p = jobs_job_paths(job_id).outputs_dir / "outputs.json"
    except Exception:
        return {}
    if not p.is_file():
        return {}
    try:
        doc = _load_json(p)
    except Exception:
        return {}
    if not isinstance(doc, dict):
        return {}
    return doc


def _job_checkpoint_from_events(events: list[dict[str, Any]]) -> str:
    waiting = _latest_job_waiting_step(events)
    if waiting:
        return waiting
    if events:
        latest = str(events[-1].get("event_type") or "")
        if latest == "DONE":
            return "done"
        if latest == "ERROR":
            return "error"
    return "idea"


def _workbench_index_context() -> dict[str, Any]:
    sessions_root = _workbench_sessions_root()
    session_rows: list[dict[str, Any]] = []
    if sessions_root.is_dir():
        for child in sorted(sessions_root.iterdir(), key=lambda p: p.name):
            if not child.is_dir():
                continue
            sid = child.name
            try:
                payload = _load_workbench_session(sid)
            except HTTPException:
                continue
            if not isinstance(payload, dict):
                continue
            session_rows.append(
                {
                    "session_id": sid,
                    "status": str(payload.get("status") or "unknown"),
                    "current_step": str(payload.get("current_step") or "idea"),
                    "title": str(payload.get("title") or ""),
                    "updated_at": str(payload.get("updated_at") or ""),
                    "job_id": str(payload.get("job_id") or ""),
                }
            )
    return {"title": "Workbench", "sessions": session_rows, "session_count": len(session_rows)}


def _workbench_session_context(session_id: str) -> dict[str, Any]:
    payload = _load_workbench_session(session_id)
    events = _read_workbench_events(session_id)
    cards = _workbench_cards_for_view(payload)
    return {
        "title": "Workbench Session",
        "session": payload,
        "events": events,
        "event_count": len(events),
        "cards": cards,
        "cards_count": len(cards),
        "steps": WORKBENCH_PHASE_STEPS,
        "cards_path": _workbench_cards_root(session_id).as_posix(),
    }


def _parse_prompt_text(text: str) -> tuple[dict[str, str], str]:
    lines = text.splitlines()
    meta: dict[str, str] = {}
    body_start = 0
    for i, ln in enumerate(lines):
        if ln.strip() == "---":
            body_start = i + 1
            break
        if ":" not in ln:
            body_start = i
            break
        k, v = ln.split(":", 1)
        k = k.strip()
        v = v.strip()
        if k:
            meta[k] = v
    body = "\n".join(lines[body_start:]).rstrip("\n")
    return meta, body


def _normalize_prompt_version(raw: str) -> str:
    s = str(raw).strip()
    if not s:
        raise HTTPException(status_code=422, detail="missing prompt_version")
    if not s.startswith("v"):
        s = f"v{s}"
    if not PROMPT_VERSION_RE.match(s):
        raise HTTPException(status_code=422, detail="invalid prompt_version")
    return s


def _prompt_version_num(version: str) -> int:
    m = PROMPT_VERSION_RE.match(str(version).strip())
    if not m:
        raise HTTPException(status_code=422, detail="invalid prompt_version")
    return int(m.group(1))


def _prompt_entry_from_file(path: Path, *, source: str, fallback_version: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    meta, body = _parse_prompt_text(text)
    prompt_version = str(meta.get("prompt_version") or fallback_version).strip() or fallback_version
    out_schema = str(meta.get("output_schema_version") or "").strip()
    return {
        "prompt_version": prompt_version,
        "version_num": _prompt_version_num(prompt_version),
        "output_schema_version": out_schema,
        "body": body,
        "source": source,
        "path": path.as_posix(),
    }


def _collect_prompt_versions(agent_id: str) -> list[dict[str, Any]]:
    canonical_dir = _prompts_root() / agent_id
    overlay_dir = _prompt_overrides_root() / agent_id
    merged: dict[int, dict[str, Any]] = {}

    for source, root in (("canonical", canonical_dir), ("overlay", overlay_dir)):
        if not root.is_dir():
            continue
        for p in sorted(root.iterdir()):
            if not p.is_file():
                continue
            m = PROMPT_FILE_RE.match(p.name)
            if not m:
                continue
            fallback_version = f"v{int(m.group(1))}"
            try:
                entry = _prompt_entry_from_file(p, source=source, fallback_version=fallback_version)
            except HTTPException:
                continue
            except Exception:
                continue
            merged[entry["version_num"]] = entry

    return [merged[vn] for vn in sorted(merged)]


def _all_prompt_agent_ids() -> list[str]:
    ids: set[str] = set()
    for root in (_prompts_root(), _prompt_overrides_root()):
        if not root.is_dir():
            continue
        for d in root.iterdir():
            if d.is_dir():
                ids.add(d.name)
    return sorted(ids)


def _render_prompt_diff(previous: str, current: str, *, previous_label: str, current_label: str) -> str:
    lines = difflib.unified_diff(
        previous.splitlines(),
        current.splitlines(),
        fromfile=previous_label,
        tofile=current_label,
        lineterm="",
    )
    return "\n".join(lines)


async def _parse_form_or_json(request: Request) -> dict[str, str]:
    ctype = str(request.headers.get("content-type", "")).lower()
    body = await request.body()
    if "application/json" in ctype:
        if not body:
            return {}
        try:
            doc = json.loads(body.decode("utf-8", errors="ignore"))
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=422, detail=f"invalid json body: {e}") from e
        if not isinstance(doc, dict):
            raise HTTPException(status_code=422, detail="json body must be object")
        return {str(k): str(v) for k, v in doc.items() if isinstance(k, str)}

    data = parse_qs(body.decode("utf-8", errors="ignore"), keep_blank_values=True)
    out: dict[str, str] = {}
    for k, vals in data.items():
        if not isinstance(k, str):
            continue
        out[k] = str(vals[0]) if vals else ""
    return out


def _prompt_file_content(*, version: str, output_schema_version: str, body: str) -> str:
    body_norm = str(body).replace("\r\n", "\n").rstrip("\n")
    return (
        f"prompt_version: {version}\n"
        f"output_schema_version: {output_schema_version}\n"
        "---\n"
        f"{body_norm}\n"
    )


def _gate_detail_rows(gate_results: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    raw_results = gate_results.get("results") if isinstance(gate_results, dict) else None
    if not isinstance(raw_results, list):
        return rows

    for raw in raw_results:
        if not isinstance(raw, dict):
            continue
        evidence = raw.get("evidence") if isinstance(raw.get("evidence"), dict) else {}
        artifacts_raw = evidence.get("artifacts") if isinstance(evidence, dict) else None
        evidence_artifacts = []
        if isinstance(artifacts_raw, list):
            for item in artifacts_raw:
                ref = str(item).strip()
                if ref:
                    evidence_artifacts.append(ref)

        pass_value = raw.get("pass")
        threshold_doc = raw.get("thresholds")
        rows.append(
            {
                "gate_id": str(raw.get("gate_id") or ""),
                "gate_version": str(raw.get("gate_version") or ""),
                "pass": pass_value if isinstance(pass_value, bool) else None,
                "status": str(raw.get("status") or ""),
                "thresholds": threshold_doc if isinstance(threshold_doc, (dict, list)) else None,
                "evidence_artifacts": evidence_artifacts,
                "evidence_notes": str(evidence.get("notes") or "").strip() if isinstance(evidence, dict) else "",
            }
        )

    return rows


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        s = ln.strip()
        if not s:
            continue
        try:
            doc = json.loads(s)
        except Exception:
            continue
        if isinstance(doc, dict):
            rows.append(doc)
    return rows


def _build_prompt_pin_state(*, job_id: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    pins: dict[str, dict[str, str]] = {}
    for ev in events:
        agent_id = str(ev.get("agent_id") or "").strip()
        prompt_version = str(ev.get("prompt_version") or "").strip()
        recorded_at = str(ev.get("recorded_at") or "").strip()
        if not agent_id or not prompt_version:
            continue
        pins[agent_id] = {
            "prompt_version": prompt_version,
            "pinned_at": recorded_at,
        }
    return {
        "schema_version": "prompt_pin_state_v1",
        "job_id": job_id,
        "updated_at": _now_iso(),
        "pins": pins,
    }


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


def _safe_policy_bundle_path(p: str) -> str:
    # Keep it simple: allow repo-relative paths only.
    if not p or p.startswith("/") or ".." in p or "\\" in p:
        raise HTTPException(status_code=400, detail="invalid policy_bundle_path")
    return p


def _seed_blueprint_from_idea_spec(idea_spec: dict[str, Any], *, job_id: str) -> dict[str, Any]:
    """Build a deterministic blueprint draft for UI-created idea jobs."""
    title = str(idea_spec.get("title") or "").strip()
    description = str(idea_spec.get("hypothesis_text") or "").strip()
    symbols_raw = idea_spec.get("symbols")
    symbols = [str(x).strip() for x in symbols_raw if str(x).strip()] if isinstance(symbols_raw, list) else []
    if not symbols:
        symbols = ["AAA"]
    frequency = str(idea_spec.get("frequency") or "1d").strip() or "1d"
    start = str(idea_spec.get("start") or "2024-01-01").strip() or "2024-01-01"
    end = str(idea_spec.get("end") or "2024-01-10").strip() or "2024-01-10"
    policy_bundle_id = str(idea_spec.get("policy_bundle_id") or "policy_bundle_v1_default").strip() or "policy_bundle_v1_default"
    return {
        "schema_version": "blueprint_v1",
        "blueprint_id": f"bp_seed_{job_id}",
        "title": title or f"Intent Draft {job_id}",
        "description": description,
        "policy_bundle_id": policy_bundle_id,
        "universe": {
            "asset_pack": str(idea_spec.get("universe_hint") or "demo"),
            "symbols": symbols,
            "timezone": "Asia/Taipei",
            "calendar": "DEMO",
        },
        "bar_spec": {"frequency": frequency},
        "data_requirements": [
            {
                "dataset_id": "ohlcv_1d",
                "fields": ["open", "high", "low", "close", "volume", "available_at"],
                "frequency": frequency,
                "adjustment": "none",
                "asof_rule": {"mode": "asof"},
            }
        ],
        "strategy_spec": {
            "dsl_version": "signal_dsl_v1",
            "signals": {"entry": "enter", "exit": "exit"},
            "expressions": {"enter": {"type": "const", "value": True}, "exit": {"type": "const", "value": False}},
            "execution": {"order_timing": "next_open", "cost_model": {"ref_policy": True}},
            "extensions": {"engine_contract": "vectorbt_signal_v1", "strategy_id": "buy_and_hold_mvp"},
        },
        "evaluation_protocol": {
            "segments": {
                "train": {"start": start, "end": end},
                "test": {"start": start, "end": end},
                "holdout": {"start": start, "end": end},
            },
            "purge": {"bars": 0},
            "embargo": {"bars": 0},
            "gate_suite_id": "gate_suite_v1_default",
        },
        "report_spec": {"plots": False, "tables": True, "trace": False},
        "extensions": {
            "evaluation_intent": str(idea_spec.get("evaluation_intent") or ""),
            "snapshot_id": str(idea_spec.get("snapshot_id") or ""),
            "seeded_from_ui_submit": True,
        },
    }


def _reject_inline_policy_overrides(ext: Any) -> None:
    if not isinstance(ext, dict):
        return
    forbidden = {
        "policy_overrides",
        "policy_override",
        "overrides",
        "execution_policy",
        "cost_policy",
        "asof_latency_policy",
        "risk_policy",
        "gate_suite",
        "budget_policy",
        "policy_bundle",
    }
    hit = [k for k in ext.keys() if str(k) in forbidden]
    if hit:
        raise HTTPException(status_code=422, detail=f"extensions must not override policies (forbidden keys: {hit})")


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


def _ui_index_context(*, idea_form: dict[str, str] | None = None, idea_form_error: str = "") -> dict[str, Any]:
    defaults = {
        "title": "",
        "hypothesis_text": "",
        "symbols": "AAA,BBB",
        "frequency": "1d",
        "start": "2024-01-01",
        "end": "2024-01-10",
        "evaluation_intent": "demo_e2e",
        "snapshot_id": str(os.getenv("EAM_DEFAULT_SNAPSHOT_ID", "")).strip(),
        "policy_bundle_path": str(os.getenv("EAM_DEFAULT_POLICY_BUNDLE_PATH", "policies/policy_bundle_v1.yaml")).strip()
        or "policies/policy_bundle_v1.yaml",
    }
    merged = dict(defaults)
    if isinstance(idea_form, dict):
        merged.update({k: str(v) for k, v in idea_form.items()})

    return {
        "cards": reg_list_cards(registry_root=registry_root()),
        "trials": _recent_trials(limit=20),
        "idea_form": merged,
        "idea_form_error": idea_form_error,
        "title": "Review Console",
    }


def _counter_rows(counter: Counter[str]) -> list[dict[str, Any]]:
    rows = [{"key": str(k), "count": int(v)} for k, v in counter.items() if int(v) > 0]
    rows.sort(key=lambda row: (-int(row["count"]), str(row["key"])))
    return rows


def _qa_fetch_flag(path: Path) -> int | None:
    if not path.is_file():
        return None
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return 0
    try:
        return int(raw)
    except ValueError:
        return None


def _qa_fetch_evidence_context() -> dict[str, Any]:
    repo_root = _repo_root()
    data_plane_root = repo_root / "docs" / "05_data_plane"

    registry_path = data_plane_root / "qa_fetch_registry_v1.json"
    resolver_doc_path = data_plane_root / "qa_fetch_resolver_registry_v1.md"
    smoke_doc_path = data_plane_root / "qa_fetch_smoke_evidence_v1.md"
    probe_dir = data_plane_root / "qa_fetch_probe_v3"
    probe_summary_path = probe_dir / "probe_summary_v3.json"
    probe_results_json_path = probe_dir / "probe_results_v3.json"
    probe_results_csv_path = probe_dir / "probe_results_v3.csv"
    pass_has_data_path = probe_dir / "candidate_pass_has_data.txt"
    pass_has_data_or_empty_path = probe_dir / "candidate_pass_has_data_or_empty.txt"

    def _rel(path: Path) -> str:
        try:
            return path.relative_to(repo_root).as_posix()
        except Exception:
            return path.as_posix()

    evidence_files = [
        {"path": _rel(registry_path), "exists": registry_path.is_file()},
        {"path": _rel(resolver_doc_path), "exists": resolver_doc_path.is_file()},
        {"path": _rel(probe_summary_path), "exists": probe_summary_path.is_file()},
        {"path": _rel(probe_results_json_path), "exists": probe_results_json_path.is_file()},
        {"path": _rel(probe_results_csv_path), "exists": probe_results_csv_path.is_file()},
        {"path": _rel(pass_has_data_path), "exists": pass_has_data_path.is_file()},
        {"path": _rel(pass_has_data_or_empty_path), "exists": pass_has_data_or_empty_path.is_file()},
        {"path": _rel(smoke_doc_path), "exists": smoke_doc_path.is_file()},
    ]

    registry = {
        "path": _rel(registry_path),
        "exists": registry_path.is_file(),
        "schema_version": "",
        "generated_at_utc": "",
        "function_count": 0,
        "resolver_entry_count": 0,
        "function_status_rows": [],
        "function_source_rows": [],
        "resolver_source_rows": [],
    }
    if registry_path.is_file():
        try:
            doc = _load_json(registry_path)
        except Exception:
            doc = {}
        if isinstance(doc, dict):
            functions = doc.get("functions") if isinstance(doc.get("functions"), list) else []
            resolver_entries = doc.get("resolver_entries") if isinstance(doc.get("resolver_entries"), list) else []
            function_status = Counter()
            function_source = Counter()
            for row in functions:
                if not isinstance(row, dict):
                    continue
                function_status[str(row.get("status") or "unknown")] += 1
                function_source[str(row.get("source") or "unknown")] += 1
            resolver_source = Counter()
            for row in resolver_entries:
                if not isinstance(row, dict):
                    continue
                raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
                resolver_source[str(raw.get("source") or "unknown")] += 1
            registry = {
                "path": _rel(registry_path),
                "exists": True,
                "schema_version": str(doc.get("schema_version") or ""),
                "generated_at_utc": str(doc.get("generated_at_utc") or ""),
                "function_count": len(functions),
                "resolver_entry_count": len(resolver_entries),
                "function_status_rows": _counter_rows(function_status),
                "function_source_rows": _counter_rows(function_source),
                "resolver_source_rows": _counter_rows(resolver_source),
            }

    probe_results: list[dict[str, Any]] = []
    if probe_results_json_path.is_file():
        try:
            rows = _load_json(probe_results_json_path)
        except Exception:
            rows = []
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    probe_results.append(row)
    result_status_counter = Counter()
    result_source_counter = Counter()
    for row in probe_results:
        result_status_counter[str(row.get("status") or "unknown")] += 1
        result_source_counter[str(row.get("source") or "unknown")] += 1

    probe = {
        "summary_path": _rel(probe_summary_path),
        "summary_exists": probe_summary_path.is_file(),
        "results_path": _rel(probe_results_json_path),
        "results_exists": probe_results_json_path.is_file(),
        "results_csv_path": _rel(probe_results_csv_path),
        "results_csv_exists": probe_results_csv_path.is_file(),
        "total": len(probe_results),
        "pass_has_data": _qa_fetch_flag(pass_has_data_path),
        "pass_has_data_or_empty": _qa_fetch_flag(pass_has_data_or_empty_path),
        "status_rows": _counter_rows(result_status_counter),
        "source_rows": _counter_rows(result_source_counter),
        "example_rows": [
            {
                "source": str(r.get("source") or ""),
                "function": str(r.get("function") or ""),
                "status": str(r.get("status") or ""),
                "len": r.get("len"),
                "reason": str(r.get("reason") or ""),
            }
            for r in probe_results[:12]
        ],
    }
    if probe_summary_path.is_file():
        try:
            summary_doc = _load_json(probe_summary_path)
        except Exception:
            summary_doc = {}
        if isinstance(summary_doc, dict):
            if isinstance(summary_doc.get("total"), int):
                probe["total"] = int(summary_doc["total"])
            status_counts = summary_doc.get("status_counts") if isinstance(summary_doc.get("status_counts"), dict) else {}
            source_counts = summary_doc.get("source_counts") if isinstance(summary_doc.get("source_counts"), dict) else {}
            if status_counts:
                c = Counter()
                for k, v in status_counts.items():
                    try:
                        c[str(k)] = int(v)
                    except Exception:
                        continue
                probe["status_rows"] = _counter_rows(c)
            if source_counts:
                c = Counter()
                for k, v in source_counts.items():
                    try:
                        c[str(k)] = int(v)
                    except Exception:
                        continue
                probe["source_rows"] = _counter_rows(c)
            if probe["pass_has_data"] is None:
                raw = summary_doc.get("pass_has_data")
                if isinstance(raw, int):
                    probe["pass_has_data"] = int(raw)
            if probe["pass_has_data_or_empty"] is None:
                raw = summary_doc.get("pass_has_data_or_empty")
                if isinstance(raw, int):
                    probe["pass_has_data_or_empty"] = int(raw)

    resolver_doc = {
        "path": _rel(resolver_doc_path),
        "exists": resolver_doc_path.is_file(),
        "preview": "",
    }
    if resolver_doc_path.is_file():
        lines = resolver_doc_path.read_text(encoding="utf-8").splitlines()
        resolver_doc["preview"] = "\n".join(lines[:24]).strip()

    smoke_doc = {
        "path": _rel(smoke_doc_path),
        "exists": smoke_doc_path.is_file(),
        "date": "",
        "preview": "",
    }
    if smoke_doc_path.is_file():
        lines = smoke_doc_path.read_text(encoding="utf-8").splitlines()
        for line in lines:
            if line.lower().startswith("date:"):
                smoke_doc["date"] = line.split(":", 1)[1].strip().strip("`")
                break
        smoke_doc["preview"] = "\n".join(lines[:24]).strip()

    return {
        "title": "QA Fetch Explorer",
        "evidence_files": evidence_files,
        "registry": registry,
        "probe": probe,
        "resolver_doc": resolver_doc,
        "smoke_doc": smoke_doc,
    }


def _repo_rel(path: Path) -> str:
    root = _repo_root()
    try:
        return path.relative_to(root).as_posix()
    except Exception:
        return path.as_posix()


def _markdown_clean(text: str) -> str:
    s = str(text).strip()
    if not s:
        return ""
    s = re.sub(r"`([^`]+)`", r"\1", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
    s = re.sub(r"\*([^*]+)\*", r"\1", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _extract_whole_view_constraints(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    rows: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw in lines:
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            in_section = ("系统硬约束" in line) or ("Hard Constraints" in line)
            continue
        if not in_section:
            continue
        if not line or line == "---":
            continue
        m = re.match(r"^(\d+)\)\s*(.+)$", line)
        if m:
            if current:
                rows.append(current)
            current = {
                "check_id": f"WV-{m.group(1)}",
                "item": _markdown_clean(m.group(2)),
                "detail": "",
            }
            continue
        if current and line.startswith("- "):
            detail = _markdown_clean(line[2:])
            if detail:
                if current["detail"]:
                    current["detail"] += f" {detail}"
                else:
                    current["detail"] = detail
    if current:
        rows.append(current)
    return rows


def _extract_whole_view_required_contracts(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    rows: list[dict[str, Any]] = []
    for raw in lines:
        line = raw.strip()
        if line.startswith("### "):
            if in_section:
                break
            in_section = ("5.1" in line) and ("Contract" in line)
            continue
        if not in_section or not line:
            continue
        m = re.match(r"^(\d+)\)\s*([A-Za-z0-9_.-]+\.json)\s*(.*)$", line)
        if not m:
            continue
        detail = _markdown_clean(m.group(3)).strip(" -:;,.()[]{}")
        detail = detail.strip("（）")
        rows.append(
            {
                "index": int(m.group(1)),
                "contract_file": m.group(2),
                "detail": detail,
            }
        )
    return sorted(rows, key=lambda r: int(r.get("index") or 0))


def _extract_whole_view_contracts_principles(path: Path) -> dict[str, Any]:
    default_section = "5. Contracts（Schema）体系：让 LLM/Codex 能产、Kernel 能编译、UI 能渲染"
    default_contracts_section = "5.1 必须落地的 Contracts（v1）"
    if not path.is_file():
        return {
            "section": default_section,
            "contracts_section": default_contracts_section,
            "principle_rows": [],
            "contract_rows": [],
            "trace_boundary_note": "",
        }

    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    in_contracts = False
    section = default_section
    contracts_section = default_contracts_section
    principle_rows: list[dict[str, Any]] = []
    contract_rows: list[dict[str, Any]] = []
    trace_boundary_note = ""

    for idx, raw in enumerate(lines, start=1):
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            if WHOLE_VIEW_SECTION5_RE.match(line) and (
                ("Contract" in line) or ("Schema" in line) or ("体系" in line)
            ):
                in_section = True
                section = _markdown_clean(line[3:]) or default_section
            continue
        if (not in_section) or (not line) or (line == "---"):
            continue

        if line.startswith("### "):
            if ("5.1" in line) and ("Contract" in line):
                in_contracts = True
                contracts_section = _markdown_clean(line[4:]) or default_contracts_section
                continue
            if in_contracts:
                break

        if line.startswith(">"):
            quote = _markdown_clean(line.lstrip(">").strip())
            if not quote:
                continue
            if ("原则" in quote) and (not principle_rows):
                principle_blob = quote
                for sep in ("：", ":"):
                    if sep in principle_blob:
                        principle_blob = principle_blob.split(sep, 1)[1].strip()
                        break
                principle_parts = [
                    _markdown_clean(x).strip("。.;；")
                    for x in principle_blob.split("+")
                ]
                principle_rows = [
                    {
                        "index": i + 1,
                        "principle": part,
                        "source_line": idx,
                    }
                    for i, part in enumerate(principle_parts)
                    if part
                ]
                continue
            if (
                ("trace" in quote.lower())
                and ("计划" in quote)
                and ("结果" in quote)
                and (not trace_boundary_note)
            ):
                note = quote
                for sep in ("：", ":"):
                    if sep not in note:
                        continue
                    left, right = note.split(sep, 1)
                    if "说明" in left:
                        note = right.strip()
                    break
                trace_boundary_note = note
                continue

        if not in_contracts:
            continue
        m = re.match(r"^(\d+)\)\s*([A-Za-z0-9_.-]+\.json)\s*(.*)$", line)
        if not m:
            continue
        detail = _markdown_clean(m.group(3)).strip(" -:;,.()[]{}")
        detail = detail.strip("（）")
        contract_rows.append(
            {
                "index": int(m.group(1)),
                "contract_file": m.group(2),
                "detail": detail,
                "source_line": idx,
            }
        )

    contract_rows.sort(key=lambda r: int(r.get("index") or 0))
    return {
        "section": section,
        "contracts_section": contracts_section,
        "principle_rows": principle_rows,
        "contract_rows": contract_rows,
        "trace_boundary_note": trace_boundary_note,
    }


def _contracts_principles_context() -> dict[str, Any]:
    whole_view_path = _whole_view_framework_root_doc()
    whole_view = _extract_whole_view_contracts_principles(whole_view_path)
    principle_rows = [x for x in (whole_view.get("principle_rows") or []) if isinstance(x, dict)]
    contract_rows = [x for x in (whole_view.get("contract_rows") or []) if isinstance(x, dict)]
    trace_boundary_note = str(whole_view.get("trace_boundary_note") or "").strip()

    return {
        "title": "Whole View Contracts Principles and Trace Boundary Evidence",
        "source_files": [
            {
                "path": _repo_rel(whole_view_path),
                "exists": whole_view_path.is_file(),
                "section": str(whole_view.get("section") or "5. Contracts（Schema）体系"),
            },
            {
                "path": _repo_rel(whole_view_path),
                "exists": whole_view_path.is_file(),
                "section": str(whole_view.get("contracts_section") or "5.1 必须落地的 Contracts（v1）"),
            },
        ],
        "summary": {
            "principle_total": len(principle_rows),
            "required_contract_total": len(contract_rows),
            "trace_boundary_note_present": bool(trace_boundary_note),
        },
        "whole_view": whole_view,
    }


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _contracts_coverage_context() -> dict[str, Any]:
    whole_view_path = _find_overview_doc("Whole View Framework.md")
    required = _extract_whole_view_required_contracts(whole_view_path)

    coverage_rows: list[dict[str, Any]] = []
    present_count = 0
    repo_root = _repo_root()
    for item in required:
        contract_file = str(item.get("contract_file") or "").strip()
        contract_path = repo_root / "contracts" / contract_file
        exists = contract_path.is_file()
        if exists:
            present_count += 1
        coverage_rows.append(
            {
                "index": int(item.get("index") or 0),
                "contract_file": contract_file,
                "detail": str(item.get("detail") or ""),
                "path": _repo_rel(contract_path),
                "exists": exists,
                "sha256": (_sha256_file(contract_path) if exists else ""),
            }
        )

    required_total = len(coverage_rows)
    missing_count = max(required_total - present_count, 0)
    return {
        "title": "Whole View Contracts Coverage",
        "source_file": {
            "path": _repo_rel(whole_view_path),
            "exists": whole_view_path.is_file(),
            "section": "5.1 必须落地的 Contracts（v1）",
        },
        "summary": {
            "required_total": required_total,
            "present_total": present_count,
            "missing_total": missing_count,
            "coverage_ratio": f"{present_count}/{required_total}",
        },
        "coverage_rows": coverage_rows,
    }


def _extract_whole_view_ia_checklist(path: Path) -> tuple[str, list[dict[str, Any]]]:
    default_section = "8. UI 信息架构（不看源码的审阅体验）"
    if not path.is_file():
        return default_section, []

    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    section = default_section
    rows: list[dict[str, Any]] = []
    for raw in lines:
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            if WHOLE_VIEW_SECTION8_RE.match(line) and ("UI" in line):
                in_section = True
                section = _markdown_clean(line[3:]) or default_section
            continue
        if not in_section or not line:
            continue
        m = re.match(r"^(\d+)\)\s*(.+)$", line)
        if not m:
            continue
        rows.append(
            {
                "index": int(m.group(1)),
                "item": _markdown_clean(m.group(2)),
            }
        )
    rows.sort(key=lambda row: int(row.get("index") or 0))
    return section, rows


def _split_role_line(text: str) -> tuple[str, str]:
    cleaned = _markdown_clean(text)
    for sep in ("：", ":"):
        if sep in cleaned:
            left, right = cleaned.split(sep, 1)
            return _markdown_clean(left), _markdown_clean(right)
    return cleaned, ""


def _extract_whole_view_agent_roles(path: Path) -> tuple[str, list[dict[str, Any]]]:
    default_section = "6.4 Agents Plane（LLM + Codex，全部通过 harness 运行）"
    if not path.is_file():
        return default_section, []

    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    section = default_section
    rows: list[dict[str, Any]] = []
    for idx, raw in enumerate(lines, start=1):
        line = raw.strip()
        if line.startswith("### "):
            if in_section:
                break
            if WHOLE_VIEW_SECTION64_RE.match(line) and ("Agents Plane" in line):
                in_section = True
                section = _markdown_clean(line[4:]) or default_section
            continue
        if (not in_section) or (not line.startswith("- ")):
            continue
        role_name, boundary = _split_role_line(line[2:])
        if not role_name:
            continue
        rows.append(
            {
                "role_name": role_name,
                "boundary": boundary,
                "source_line": idx,
            }
        )
    return section, rows


def _extract_whole_view_workflow_phases(path: Path) -> tuple[str, list[dict[str, Any]]]:
    default_section = "3. Whole View 工作流（UI Checkpoint 驱动的状态机）"
    if not path.is_file():
        return default_section, []

    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    section = default_section
    rows: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for idx, raw in enumerate(lines, start=1):
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            if WHOLE_VIEW_SECTION3_RE.match(line) and (("工作流" in line) or ("Workflow" in line)):
                in_section = True
                section = _markdown_clean(line[3:]) or default_section
            continue
        if not in_section:
            continue

        m = WHOLE_VIEW_PHASE_HEADER_RE.match(line)
        if m:
            if current:
                rows.append(current)
            phase_no = int(m.group(1))
            current = {
                "phase_no": phase_no,
                "phase_label": f"Phase-{phase_no}",
                "title": _markdown_clean(m.group(2)),
                "source_line": idx,
                "evidence_rows": [],
                "checkpoint_no": None,
                "checkpoint_label": "",
                "checkpoint_detail": "",
            }
            continue

        if (current is None) or (not line.startswith("- ")):
            continue

        item = _markdown_clean(line[2:])
        if not item:
            continue
        current["evidence_rows"].append(item)

        checkpoint_match = WHOLE_VIEW_REVIEW_POINT_RE.match(item)
        if checkpoint_match:
            checkpoint_no = int(checkpoint_match.group(1))
            current["checkpoint_no"] = checkpoint_no
            current["checkpoint_label"] = f"审阅点 #{checkpoint_no}（UI）"
            current["checkpoint_detail"] = _markdown_clean(checkpoint_match.group(2))

    if current:
        rows.append(current)

    rows.sort(key=lambda row: int(row.get("phase_no") or 0))
    return section, rows


def _extract_playbook_phase_flow(path: Path) -> tuple[str, list[dict[str, Any]]]:
    default_section = "3. Phase 列表（推荐施工顺序）"
    if not path.is_file():
        return default_section, []

    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    section = default_section
    rows: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    current_heading = ""

    for idx, raw in enumerate(lines, start=1):
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            if PLAYBOOK_SECTION3_RE.match(line) and ("Phase" in line):
                in_section = True
                section = _markdown_clean(line[3:]) or default_section
            continue
        if not in_section:
            continue

        m = PLAYBOOK_PHASE_HEADER_RE.match(line)
        if m:
            if current:
                rows.append(current)
            phase_no = int(m.group(1))
            current = {
                "phase_no": phase_no,
                "phase_label": f"Phase-{phase_no}",
                "title": _markdown_clean(m.group(2)),
                "source_line": idx,
                "goal_rows": [],
                "acceptance_rows": [],
                "flow_rows": [],
            }
            current_heading = ""
            continue

        if current is None:
            continue
        if line.startswith("**") and line.endswith("**"):
            current_heading = _markdown_clean(line.strip("*"))
            continue
        if not line.startswith("- "):
            continue

        item = _markdown_clean(line[2:])
        if not item:
            continue
        current["flow_rows"].append(item)
        if ("目标" in current_heading) and (len(current["goal_rows"]) < 3):
            current["goal_rows"].append(item)
        if ("验收" in current_heading) and (len(current["acceptance_rows"]) < 3):
            current["acceptance_rows"].append(item)

    if current:
        rows.append(current)

    rows.sort(key=lambda row: int(row.get("phase_no") or 0))
    return section, rows


def _extract_whole_view_object_model(path: Path) -> tuple[str, list[dict[str, Any]]]:
    default_section = "4. 核心对象模型（系统只认这些 I/O）"
    if not path.is_file():
        return default_section, []

    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    section = default_section
    rows: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for idx, raw in enumerate(lines, start=1):
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            if WHOLE_VIEW_SECTION4_RE.match(line) and (("对象模型" in line) or ("Object" in line) or ("I/O" in line)):
                in_section = True
                section = _markdown_clean(line[3:]) or default_section
            continue
        if not in_section:
            continue

        m = WHOLE_VIEW_OBJECT_HEADER_RE.match(line)
        if m:
            if current:
                rows.append(current)
            object_index = int(m.group(1))
            object_title = _markdown_clean(m.group(2))
            object_name = object_title
            for sep in ("（", "(", "：", ":"):
                if sep in object_name:
                    object_name = object_name.split(sep, 1)[0]
            current = {
                "object_index": object_index,
                "section_id": f"4.{object_index}",
                "object_title": object_title,
                "object_name": _markdown_clean(object_name),
                "source_line": idx,
                "io_rows": [],
            }
            continue

        if current is None:
            continue
        if (not line) or (line == "---"):
            continue

        item = ""
        if line.startswith("- "):
            item = _markdown_clean(line[2:])
        else:
            cleaned = _markdown_clean(line)
            if cleaned not in ("必须可静态分析：", "明确本次运行如何复现：", "建议目录："):
                item = cleaned

        if item and (item not in current["io_rows"]):
            current["io_rows"].append(item)

    if current:
        rows.append(current)

    rows.sort(key=lambda row: int(row.get("object_index") or 0))
    return section, rows


def _extract_playbook_phase_context(path: Path) -> tuple[str, list[dict[str, Any]]]:
    default_section = "3. Phase 列表（推荐施工顺序）"
    if not path.is_file():
        return default_section, []

    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    section = default_section
    rows: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    current_heading = ""

    for idx, raw in enumerate(lines, start=1):
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            if PLAYBOOK_SECTION3_RE.match(line) and ("Phase" in line):
                in_section = True
                section = _markdown_clean(line[3:]) or default_section
            continue
        if not in_section:
            continue

        m = PLAYBOOK_PHASE_HEADER_RE.match(line)
        if m:
            if current:
                rows.append(current)
            phase_no = int(m.group(1))
            current = {
                "phase_no": phase_no,
                "phase_label": f"Phase-{phase_no}",
                "title": _markdown_clean(m.group(2)),
                "source_line": idx,
                "goal_rows": [],
                "background_rows": [],
                "flow_rows": [],
            }
            current_heading = ""
            continue

        if current is None:
            continue
        if line.startswith("**") and line.endswith("**"):
            current_heading = _markdown_clean(line.strip("*"))
            continue
        if not line.startswith("- "):
            continue

        item = _markdown_clean(line[2:])
        if not item:
            continue
        current["flow_rows"].append(item)
        if ("目标" in current_heading) and (len(current["goal_rows"]) < 2):
            current["goal_rows"].append(item)
        if ("背景" in current_heading) and (len(current["background_rows"]) < 2):
            current["background_rows"].append(item)

    if current:
        rows.append(current)

    rows.sort(key=lambda row: int(row.get("phase_no") or 0))
    return section, rows


def _object_model_playbook_matches(
    object_name: str, playbook_rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[str]]:
    keys = OBJECT_MODEL_PLAYBOOK_KEYWORDS.get(str(object_name).strip()) or (str(object_name).strip().lower(),)
    keywords = [str(x).strip().lower() for x in keys if str(x).strip()]
    if not keywords:
        return [], []

    matched_keywords: list[str] = []
    matched_rows: list[dict[str, Any]] = []
    for row in playbook_rows:
        if not isinstance(row, dict):
            continue
        goal_rows = [str(x) for x in (row.get("goal_rows") or []) if isinstance(x, str)]
        background_rows = [str(x) for x in (row.get("background_rows") or []) if isinstance(x, str)]
        merged = " ".join([str(row.get("title") or ""), *goal_rows, *background_rows]).lower()
        row_keyword_hits = [kw for kw in keywords if kw in merged]
        if not row_keyword_hits:
            continue
        for kw in row_keyword_hits:
            if kw not in matched_keywords:
                matched_keywords.append(kw)
        matched_rows.append(
            {
                "phase_no": int(row.get("phase_no") or 0),
                "phase_label": str(row.get("phase_label") or ""),
                "title": str(row.get("title") or ""),
                "source_line": int(row.get("source_line") or 0),
                "goal_excerpt": goal_rows[0] if goal_rows else "",
                "background_excerpt": background_rows[0] if background_rows else "",
                "matched_keywords": row_keyword_hits,
            }
        )

    return matched_rows, matched_keywords


def _object_model_context() -> dict[str, Any]:
    ssot_path = _repo_root() / "docs" / "12_workflows" / "skeleton_ssot_v1.yaml"
    whole_view_path = _find_overview_doc("Whole View Framework.md")
    playbook_path = _find_overview_doc("Implementation Phases Playbook.md")

    whole_view_section, whole_view_objects = _extract_whole_view_object_model(whole_view_path)
    playbook_section, playbook_rows = _extract_playbook_phase_context(playbook_path)
    ssot_doc = _load_yaml_map(ssot_path)

    goal_rows = ssot_doc.get("goal_checklist") if isinstance(ssot_doc.get("goal_checklist"), list) else []
    g40: dict[str, Any] = {}
    for row in goal_rows:
        if isinstance(row, dict) and str(row.get("id") or "").strip() == "G40":
            g40 = row
            break

    dispatch_doc = ssot_doc.get("phase_dispatch_plan_v2") if isinstance(ssot_doc.get("phase_dispatch_plan_v2"), dict) else {}
    dispatch_rows = dispatch_doc.get("phases") if isinstance(dispatch_doc.get("phases"), list) else []
    phase60_dispatch: dict[str, Any] = {}
    for row in dispatch_rows:
        if not isinstance(row, dict):
            continue
        phase_id = str(row.get("phase_id") or "").strip()
        goal_id = str(row.get("goal_id") or "").strip()
        if (phase_id == "phase_60") or (goal_id == "G40"):
            phase60_dispatch = row
            break

    exception_rows = (
        ssot_doc.get("autopilot_stop_condition_exceptions_v1")
        if isinstance(ssot_doc.get("autopilot_stop_condition_exceptions_v1"), list)
        else []
    )
    g40_exception: dict[str, Any] = {}
    for row in exception_rows:
        if isinstance(row, dict) and str(row.get("exception_id") or "").strip() == "g40_object_model_ui_scope":
            g40_exception = row
            break
    preauth = g40_exception.get("preauthorized_scope") if isinstance(g40_exception.get("preauthorized_scope"), dict) else {}

    object_rows: list[dict[str, Any]] = []
    mapped_object_total = 0
    io_entry_total = 0
    for row in whole_view_objects:
        object_name = str(row.get("object_name") or "")
        io_rows = [str(x) for x in (row.get("io_rows") or []) if isinstance(x, str)]
        io_entry_total += len(io_rows)
        playbook_matches, matched_keywords = _object_model_playbook_matches(object_name, playbook_rows)
        if playbook_matches:
            mapped_object_total += 1

        object_rows.append(
            {
                "object_index": int(row.get("object_index") or 0),
                "section_id": str(row.get("section_id") or ""),
                "object_name": object_name,
                "object_title": str(row.get("object_title") or ""),
                "source_line": int(row.get("source_line") or 0),
                "io_rows": io_rows,
                "playbook_phase_rows": playbook_matches,
                "playbook_phase_total": len(playbook_matches),
                "matched_keywords": matched_keywords,
            }
        )

    return {
        "title": "Whole View Object Model I/O Coverage",
        "source_files": [
            {
                "path": _repo_rel(whole_view_path),
                "exists": whole_view_path.is_file(),
                "section": whole_view_section,
            },
            {
                "path": _repo_rel(playbook_path),
                "exists": playbook_path.is_file(),
                "section": playbook_section,
            },
            {
                "path": _repo_rel(ssot_path),
                "exists": ssot_path.is_file(),
                "section": "goal_checklist + phase_dispatch_plan_v2 + autopilot_stop_condition_exceptions_v1",
            },
        ],
        "summary": {
            "object_total": len(object_rows),
            "io_entry_total": io_entry_total,
            "playbook_phase_total": len(playbook_rows),
            "mapped_object_total": mapped_object_total,
            "required_guard_total": len([str(x) for x in (preauth.get("required_guards") or []) if isinstance(x, str)]),
        },
        "g40": {
            "id": str(g40.get("id") or ""),
            "title": str(g40.get("title") or ""),
            "status_now": str(g40.get("status_now") or ""),
            "ui_path": str(g40.get("ui_path") or ""),
            "depends_on": [str(x) for x in (g40.get("depends_on") or []) if isinstance(x, str)],
            "expected_state_change": str(g40.get("expected_state_change") or ""),
        },
        "dispatch": {
            "status_now": str(dispatch_doc.get("status_now") or ""),
            "mode": str(dispatch_doc.get("mode") or ""),
            "phase_id": str(phase60_dispatch.get("phase_id") or "phase_60"),
            "goal_id": str(phase60_dispatch.get("goal_id") or "G40"),
            "title": str(phase60_dispatch.get("title") or ""),
        },
        "g40_exception": {
            "exception_id": str(g40_exception.get("exception_id") or ""),
            "allowed_route_prefixes": [str(x) for x in (preauth.get("allowed_route_prefixes") or []) if isinstance(x, str)],
            "allowed_code_paths": [str(x) for x in (preauth.get("allowed_code_paths") or []) if isinstance(x, str)],
            "still_forbidden": [str(x) for x in (preauth.get("still_forbidden") or []) if isinstance(x, str)],
            "required_guards": [str(x) for x in (preauth.get("required_guards") or []) if isinstance(x, str)],
        },
        "object_rows": object_rows,
        "playbook_rows": playbook_rows,
    }


def _extract_whole_view_module_boundaries(path: Path) -> tuple[str, list[dict[str, Any]]]:
    default_section = "6. 模块（Modules）与职责边界（Deterministic vs Agent）"
    if not path.is_file():
        return default_section, []

    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    section = default_section
    rows: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for idx, raw in enumerate(lines, start=1):
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            if WHOLE_VIEW_SECTION6_RE.match(line) and (("模块" in line) or ("Modules" in line)):
                in_section = True
                section = _markdown_clean(line[3:]) or default_section
            continue
        if not in_section:
            continue

        m = WHOLE_VIEW_MODULE_HEADER_RE.match(line)
        if m:
            if current:
                rows.append(current)
            module_index = int(m.group(1))
            module_title = _markdown_clean(m.group(2))
            plane_name = module_title
            for sep in ("（", "(", "：", ":"):
                if sep in plane_name:
                    plane_name = plane_name.split(sep, 1)[0]
            plane_name = _markdown_clean(plane_name)
            module_type = "agent" if (module_index >= 4 or "agents plane" in plane_name.lower()) else "deterministic"
            current = {
                "module_index": module_index,
                "section_id": f"6.{module_index}",
                "module_title": module_title,
                "plane_name": plane_name,
                "module_type": module_type,
                "source_line": idx,
                "note_rows": [],
                "responsibility_rows": [],
                "boundary_rows": [],
            }
            continue

        if current is None:
            continue
        if (not line) or (line == "---"):
            continue

        if line.startswith("- "):
            item = _markdown_clean(line[2:])
            if not item:
                continue
            if item not in current["responsibility_rows"]:
                current["responsibility_rows"].append(item)
                component, boundary = _split_role_line(item)
                current["boundary_rows"].append(
                    {
                        "component": component,
                        "boundary": boundary,
                    }
                )
            continue

        note = _markdown_clean(line)
        if note and (note not in current["note_rows"]):
            current["note_rows"].append(note)

    if current:
        rows.append(current)

    rows.sort(key=lambda row: int(row.get("module_index") or 0))
    return section, rows


def _module_boundary_playbook_matches(
    module_name: str, responsibility_rows: list[str], playbook_rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[str]]:
    keys = MODULE_BOUNDARY_PLAYBOOK_KEYWORDS.get(str(module_name).strip()) or (str(module_name).strip().lower(),)
    keywords = [str(x).strip().lower() for x in keys if str(x).strip()]
    if not keywords:
        return [], []

    module_terms = [str(x).strip().lower() for x in responsibility_rows if str(x).strip()]
    matched_keywords: list[str] = []
    matched_rows: list[dict[str, Any]] = []
    for row in playbook_rows:
        if not isinstance(row, dict):
            continue
        goal_rows = [str(x) for x in (row.get("goal_rows") or []) if isinstance(x, str)]
        background_rows = [str(x) for x in (row.get("background_rows") or []) if isinstance(x, str)]
        flow_rows = [str(x) for x in (row.get("flow_rows") or []) if isinstance(x, str)]
        merged = " ".join([str(row.get("title") or ""), *goal_rows, *background_rows, *flow_rows]).lower()
        row_keyword_hits = [kw for kw in keywords if kw in merged]
        if not row_keyword_hits:
            continue
        for kw in row_keyword_hits:
            if kw not in matched_keywords:
                matched_keywords.append(kw)

        excerpt = ""
        for item in [*goal_rows, *background_rows, *flow_rows]:
            item_norm = str(item).strip().lower()
            if any((kw in item_norm) for kw in row_keyword_hits) or any((term and term in item_norm) for term in module_terms):
                excerpt = item
                break

        matched_rows.append(
            {
                "phase_no": int(row.get("phase_no") or 0),
                "phase_label": str(row.get("phase_label") or ""),
                "title": str(row.get("title") or ""),
                "source_line": int(row.get("source_line") or 0),
                "goal_excerpt": goal_rows[0] if goal_rows else "",
                "background_excerpt": background_rows[0] if background_rows else "",
                "flow_excerpt": excerpt,
                "matched_keywords": row_keyword_hits,
            }
        )

    return matched_rows, matched_keywords


def _module_boundaries_context() -> dict[str, Any]:
    ssot_path = _repo_root() / "docs" / "12_workflows" / "skeleton_ssot_v1.yaml"
    whole_view_path = _find_overview_doc("Whole View Framework.md")
    playbook_path = _find_overview_doc("Implementation Phases Playbook.md")

    whole_view_section, whole_view_modules = _extract_whole_view_module_boundaries(whole_view_path)
    playbook_section, playbook_rows = _extract_playbook_phase_context(playbook_path)
    ssot_doc = _load_yaml_map(ssot_path)

    goal_rows = ssot_doc.get("goal_checklist") if isinstance(ssot_doc.get("goal_checklist"), list) else []
    g41: dict[str, Any] = {}
    for row in goal_rows:
        if isinstance(row, dict) and str(row.get("id") or "").strip() == "G41":
            g41 = row
            break

    dispatch_doc = ssot_doc.get("phase_dispatch_plan_v2") if isinstance(ssot_doc.get("phase_dispatch_plan_v2"), dict) else {}
    dispatch_rows = dispatch_doc.get("phases") if isinstance(dispatch_doc.get("phases"), list) else []
    phase61_dispatch: dict[str, Any] = {}
    for row in dispatch_rows:
        if not isinstance(row, dict):
            continue
        phase_id = str(row.get("phase_id") or "").strip()
        goal_id = str(row.get("goal_id") or "").strip()
        if (phase_id == "phase_61") or (goal_id == "G41"):
            phase61_dispatch = row
            break

    exception_rows = (
        ssot_doc.get("autopilot_stop_condition_exceptions_v1")
        if isinstance(ssot_doc.get("autopilot_stop_condition_exceptions_v1"), list)
        else []
    )
    g41_exception: dict[str, Any] = {}
    for row in exception_rows:
        if isinstance(row, dict) and str(row.get("exception_id") or "").strip() == "g41_module_boundaries_ui_scope":
            g41_exception = row
            break
    preauth = g41_exception.get("preauthorized_scope") if isinstance(g41_exception.get("preauthorized_scope"), dict) else {}

    pipeline_doc = ssot_doc.get("agents_pipeline_v1") if isinstance(ssot_doc.get("agents_pipeline_v1"), dict) else {}
    global_read_rules = [str(x) for x in (pipeline_doc.get("global_read_rules") or []) if isinstance(x, str)]

    module_rows: list[dict[str, Any]] = []
    deterministic_module_total = 0
    agent_module_total = 0
    boundary_entry_total = 0
    mapped_module_total = 0
    for row in whole_view_modules:
        module_type = str(row.get("module_type") or "deterministic")
        if module_type == "agent":
            agent_module_total += 1
        else:
            deterministic_module_total += 1

        boundary_rows = [x for x in (row.get("boundary_rows") or []) if isinstance(x, dict)]
        boundary_entry_total += len(boundary_rows)
        responsibility_rows = [str(x) for x in (row.get("responsibility_rows") or []) if isinstance(x, str)]
        playbook_matches, matched_keywords = _module_boundary_playbook_matches(
            str(row.get("plane_name") or ""),
            responsibility_rows,
            playbook_rows,
        )
        if playbook_matches:
            mapped_module_total += 1

        module_rows.append(
            {
                "module_index": int(row.get("module_index") or 0),
                "section_id": str(row.get("section_id") or ""),
                "module_title": str(row.get("module_title") or ""),
                "plane_name": str(row.get("plane_name") or ""),
                "module_type": module_type,
                "source_line": int(row.get("source_line") or 0),
                "note_rows": [str(x) for x in (row.get("note_rows") or []) if isinstance(x, str)],
                "responsibility_rows": responsibility_rows,
                "boundary_rows": boundary_rows,
                "playbook_phase_rows": playbook_matches,
                "playbook_phase_total": len(playbook_matches),
                "matched_keywords": matched_keywords,
            }
        )

    return {
        "title": "Whole View Modules Deterministic-Agent Boundary Evidence",
        "source_files": [
            {
                "path": _repo_rel(whole_view_path),
                "exists": whole_view_path.is_file(),
                "section": whole_view_section,
            },
            {
                "path": _repo_rel(playbook_path),
                "exists": playbook_path.is_file(),
                "section": playbook_section,
            },
            {
                "path": _repo_rel(ssot_path),
                "exists": ssot_path.is_file(),
                "section": "goal_checklist + phase_dispatch_plan_v2 + autopilot_stop_condition_exceptions_v1 + agents_pipeline_v1",
            },
        ],
        "summary": {
            "module_total": len(module_rows),
            "deterministic_module_total": deterministic_module_total,
            "agent_module_total": agent_module_total,
            "boundary_entry_total": boundary_entry_total,
            "playbook_phase_total": len(playbook_rows),
            "mapped_module_total": mapped_module_total,
            "required_guard_total": len([str(x) for x in (preauth.get("required_guards") or []) if isinstance(x, str)]),
            "global_read_rule_total": len(global_read_rules),
        },
        "g41": {
            "id": str(g41.get("id") or ""),
            "title": str(g41.get("title") or ""),
            "status_now": str(g41.get("status_now") or ""),
            "ui_path": str(g41.get("ui_path") or ""),
            "depends_on": [str(x) for x in (g41.get("depends_on") or []) if isinstance(x, str)],
            "expected_state_change": str(g41.get("expected_state_change") or ""),
        },
        "dispatch": {
            "status_now": str(dispatch_doc.get("status_now") or ""),
            "mode": str(dispatch_doc.get("mode") or ""),
            "phase_id": str(phase61_dispatch.get("phase_id") or "phase_61"),
            "goal_id": str(phase61_dispatch.get("goal_id") or "G41"),
            "title": str(phase61_dispatch.get("title") or ""),
        },
        "g41_exception": {
            "exception_id": str(g41_exception.get("exception_id") or ""),
            "allowed_route_prefixes": [str(x) for x in (preauth.get("allowed_route_prefixes") or []) if isinstance(x, str)],
            "allowed_code_paths": [str(x) for x in (preauth.get("allowed_code_paths") or []) if isinstance(x, str)],
            "still_forbidden": [str(x) for x in (preauth.get("still_forbidden") or []) if isinstance(x, str)],
            "required_guards": [str(x) for x in (preauth.get("required_guards") or []) if isinstance(x, str)],
        },
        "pipeline": {
            "execution_model": str(pipeline_doc.get("execution_model") or ""),
            "orchestration_owner": str(pipeline_doc.get("orchestration_owner") or ""),
            "global_read_rules": global_read_rules,
        },
        "module_rows": module_rows,
        "playbook_rows": playbook_rows,
    }


def _extract_whole_view_diagnostics_promotion(path: Path) -> dict[str, Any]:
    section_default = "7. Codex CLI 的定位：探索者 + 工具工，不是裁判"
    temporary_default = "7.1 临时诊断（Ephemeral Diagnostics）"
    promotion_default = "7.2 晋升机制（Promote → Gate/Library）"
    if not path.is_file():
        return {
            "section": section_default,
            "temporary_section": temporary_default,
            "promotion_section": promotion_default,
            "temporary_rows": [],
            "promotion_rows": [],
        }

    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    section = section_default
    temporary_section = temporary_default
    promotion_section = promotion_default
    active_bucket = ""
    temporary_rows: list[dict[str, Any]] = []
    promotion_rows: list[dict[str, Any]] = []

    for idx, raw in enumerate(lines, start=1):
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            if WHOLE_VIEW_SECTION7_RE.match(line) and (
                ("Codex CLI" in line) or ("探索者" in line) or ("诊断" in line)
            ):
                in_section = True
                section = _markdown_clean(line[3:]) or section_default
            continue
        if not in_section:
            continue

        if line.startswith("### "):
            if WHOLE_VIEW_SECTION71_RE.match(line):
                active_bucket = "temporary"
                temporary_section = _markdown_clean(line[4:]) or temporary_default
                continue
            if WHOLE_VIEW_SECTION72_RE.match(line):
                active_bucket = "promotion"
                promotion_section = _markdown_clean(line[4:]) or promotion_default
                continue

        if not line.startswith("- "):
            continue

        item = _markdown_clean(line[2:])
        if not item:
            continue

        row = {"item": item, "source_line": idx}
        if active_bucket == "temporary":
            temporary_rows.append(row)
        elif active_bucket == "promotion":
            promotion_rows.append(row)

    return {
        "section": section,
        "temporary_section": temporary_section,
        "promotion_section": promotion_section,
        "temporary_rows": temporary_rows,
        "promotion_rows": promotion_rows,
    }


def _extract_whole_view_codex_role_boundary(path: Path) -> dict[str, Any]:
    section_default = "7. Codex CLI 的定位：探索者 + 工具工，不是裁判"
    temporary_default = "7.1 临时诊断（Ephemeral Diagnostics）"
    promotion_default = "7.2 晋升机制（Promote → Gate/Library）"
    if not path.is_file():
        return {
            "section": section_default,
            "role_positioning": "",
            "temporary_section": temporary_default,
            "promotion_section": promotion_default,
            "temporary_rows": [],
            "promotion_rows": [],
            "governance_note": "",
        }

    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    section = section_default
    role_positioning = ""
    temporary_section = temporary_default
    promotion_section = promotion_default
    active_bucket = ""
    temporary_rows: list[dict[str, Any]] = []
    promotion_rows: list[dict[str, Any]] = []
    governance_note = ""

    for idx, raw in enumerate(lines, start=1):
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            if WHOLE_VIEW_SECTION7_RE.match(line) and (
                ("Codex CLI" in line) or ("探索者" in line) or ("裁判" in line)
            ):
                in_section = True
                section = _markdown_clean(line[3:]) or section_default
            continue
        if not in_section:
            continue

        if line.startswith("### "):
            if WHOLE_VIEW_SECTION71_RE.match(line):
                active_bucket = "temporary"
                temporary_section = _markdown_clean(line[4:]) or temporary_default
                continue
            if WHOLE_VIEW_SECTION72_RE.match(line):
                active_bucket = "promotion"
                promotion_section = _markdown_clean(line[4:]) or promotion_default
                continue

        if line.startswith("- "):
            item = _markdown_clean(line[2:])
            if not item:
                continue

            row = {"item": item, "source_line": idx}
            if active_bucket == "temporary":
                temporary_rows.append(row)
            elif active_bucket == "promotion":
                promotion_rows.append(row)
                if (not governance_note) and (
                    ("治理流程" in item) or ("gate_suite" in item.lower()) or ("版本化" in item)
                ):
                    governance_note = item
            continue

        if not active_bucket:
            cleaned = _markdown_clean(line)
            if cleaned and not role_positioning:
                role_positioning = cleaned

    if (not governance_note) and promotion_rows:
        governance_note = str(promotion_rows[-1].get("item") or "")

    return {
        "section": section,
        "role_positioning": role_positioning,
        "temporary_section": temporary_section,
        "promotion_section": promotion_section,
        "temporary_rows": temporary_rows,
        "promotion_rows": promotion_rows,
        "governance_note": governance_note,
    }


def _extract_playbook_phase12_evidence(path: Path) -> dict[str, Any]:
    section_default = "Phase-12：Diagnostics（Codex 提出验证方法）+ 晋升 Gate"
    if not path.is_file():
        return {
            "section": section_default,
            "goal_rows": [],
            "background_rows": [],
            "code_rows": [],
            "acceptance_rows": [],
        }

    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    section = section_default
    current_heading = ""
    goal_rows: list[dict[str, Any]] = []
    background_rows: list[dict[str, Any]] = []
    code_rows: list[dict[str, Any]] = []
    acceptance_rows: list[dict[str, Any]] = []

    for idx, raw in enumerate(lines, start=1):
        line = raw.strip()
        if line.startswith("### "):
            if in_section:
                break
            m = PLAYBOOK_PHASE_HEADER_RE.match(line)
            if m and int(m.group(1)) == 12:
                in_section = True
                section = _markdown_clean(line[4:]) or section_default
            continue
        if not in_section:
            continue

        if line.startswith("**") and line.endswith("**"):
            current_heading = _markdown_clean(line.strip("*"))
            continue
        if not line.startswith("- "):
            continue

        item = _markdown_clean(line[2:])
        if not item:
            continue

        row = {"item": item, "source_line": idx}
        if "目标" in current_heading:
            goal_rows.append(row)
        elif "背景" in current_heading:
            background_rows.append(row)
        elif "编码内容" in current_heading:
            code_rows.append(row)
        elif "验收" in current_heading:
            acceptance_rows.append(row)

    return {
        "section": section,
        "goal_rows": goal_rows,
        "background_rows": background_rows,
        "code_rows": code_rows,
        "acceptance_rows": acceptance_rows,
    }


def _diagnostics_promotion_context() -> dict[str, Any]:
    ssot_path = _repo_root() / "docs" / "12_workflows" / "skeleton_ssot_v1.yaml"
    whole_view_path = _find_overview_doc("Whole View Framework.md")
    playbook_path = _find_overview_doc("Implementation Phases Playbook.md")

    whole_view = _extract_whole_view_diagnostics_promotion(whole_view_path)
    phase12 = _extract_playbook_phase12_evidence(playbook_path)
    ssot_doc = _load_yaml_map(ssot_path)

    goal_rows = ssot_doc.get("goal_checklist") if isinstance(ssot_doc.get("goal_checklist"), list) else []
    g42: dict[str, Any] = {}
    for row in goal_rows:
        if isinstance(row, dict) and str(row.get("id") or "").strip() == "G42":
            g42 = row
            break

    dispatch_doc = ssot_doc.get("phase_dispatch_plan_v2") if isinstance(ssot_doc.get("phase_dispatch_plan_v2"), dict) else {}
    dispatch_rows = dispatch_doc.get("phases") if isinstance(dispatch_doc.get("phases"), list) else []
    phase62_dispatch: dict[str, Any] = {}
    for row in dispatch_rows:
        if not isinstance(row, dict):
            continue
        phase_id = str(row.get("phase_id") or "").strip()
        goal_id = str(row.get("goal_id") or "").strip()
        if (phase_id == "phase_62") or (goal_id == "G42"):
            phase62_dispatch = row
            break

    exception_rows = (
        ssot_doc.get("autopilot_stop_condition_exceptions_v1")
        if isinstance(ssot_doc.get("autopilot_stop_condition_exceptions_v1"), list)
        else []
    )
    g42_exception: dict[str, Any] = {}
    for row in exception_rows:
        if isinstance(row, dict) and str(row.get("exception_id") or "").strip() == "g42_diagnostics_promotion_ui_scope":
            g42_exception = row
            break
    preauth = g42_exception.get("preauthorized_scope") if isinstance(g42_exception.get("preauthorized_scope"), dict) else {}

    pipeline_doc = ssot_doc.get("agents_pipeline_v1") if isinstance(ssot_doc.get("agents_pipeline_v1"), dict) else {}
    global_read_rules = [str(x) for x in (pipeline_doc.get("global_read_rules") or []) if isinstance(x, str)]

    g42_expected_artifacts = [str(x) for x in (g42.get("expected_artifacts") or []) if isinstance(x, str)]
    g42_acceptance_commands = [str(x) for x in (g42.get("acceptance_commands") or []) if isinstance(x, str)]

    return {
        "title": "Codex Diagnostics Promotion Chain Evidence",
        "source_files": [
            {
                "path": _repo_rel(whole_view_path),
                "exists": whole_view_path.is_file(),
                "section": str(whole_view.get("section") or "7. Codex CLI 的定位：探索者 + 工具工，不是裁判"),
            },
            {
                "path": _repo_rel(playbook_path),
                "exists": playbook_path.is_file(),
                "section": str(phase12.get("section") or "Phase-12"),
            },
            {
                "path": _repo_rel(ssot_path),
                "exists": ssot_path.is_file(),
                "section": "goal_checklist(G42) + phase_dispatch_plan_v2 + g42_diagnostics_promotion_ui_scope + agents_pipeline_v1",
            },
        ],
        "summary": {
            "whole_view_temporary_total": len([x for x in (whole_view.get("temporary_rows") or []) if isinstance(x, dict)]),
            "whole_view_promotion_total": len([x for x in (whole_view.get("promotion_rows") or []) if isinstance(x, dict)]),
            "playbook_goal_total": len([x for x in (phase12.get("goal_rows") or []) if isinstance(x, dict)]),
            "playbook_background_total": len([x for x in (phase12.get("background_rows") or []) if isinstance(x, dict)]),
            "playbook_code_total": len([x for x in (phase12.get("code_rows") or []) if isinstance(x, dict)]),
            "playbook_acceptance_total": len([x for x in (phase12.get("acceptance_rows") or []) if isinstance(x, dict)]),
            "required_guard_total": len([str(x) for x in (preauth.get("required_guards") or []) if isinstance(x, str)]),
            "global_read_rule_total": len(global_read_rules),
            "expected_artifact_total": len(g42_expected_artifacts),
            "acceptance_command_total": len(g42_acceptance_commands),
        },
        "g42": {
            "id": str(g42.get("id") or ""),
            "title": str(g42.get("title") or ""),
            "status_now": str(g42.get("status_now") or ""),
            "ui_path": str(g42.get("ui_path") or ""),
            "depends_on": [str(x) for x in (g42.get("depends_on") or []) if isinstance(x, str)],
            "expected_state_change": str(g42.get("expected_state_change") or ""),
        },
        "dispatch": {
            "status_now": str(dispatch_doc.get("status_now") or ""),
            "mode": str(dispatch_doc.get("mode") or ""),
            "phase_id": str(phase62_dispatch.get("phase_id") or "phase_62"),
            "goal_id": str(phase62_dispatch.get("goal_id") or "G42"),
            "title": str(phase62_dispatch.get("title") or ""),
        },
        "whole_view": whole_view,
        "phase12": phase12,
        "g42_exception": {
            "exception_id": str(g42_exception.get("exception_id") or ""),
            "allowed_route_prefixes": [str(x) for x in (preauth.get("allowed_route_prefixes") or []) if isinstance(x, str)],
            "allowed_code_paths": [str(x) for x in (preauth.get("allowed_code_paths") or []) if isinstance(x, str)],
            "still_forbidden": [str(x) for x in (preauth.get("still_forbidden") or []) if isinstance(x, str)],
            "required_guards": [str(x) for x in (preauth.get("required_guards") or []) if isinstance(x, str)],
        },
        "pipeline": {
            "pipeline_id": str(pipeline_doc.get("pipeline_id") or ""),
            "execution_model": str(pipeline_doc.get("execution_model") or ""),
            "orchestration_owner": str(pipeline_doc.get("orchestration_owner") or ""),
            "global_read_rules": global_read_rules,
        },
        "g42_expected_artifacts": g42_expected_artifacts,
        "g42_acceptance_commands": g42_acceptance_commands,
    }


def _codex_role_boundary_context() -> dict[str, Any]:
    whole_view_path = _whole_view_framework_root_doc()
    whole_view = _extract_whole_view_codex_role_boundary(whole_view_path)
    temporary_rows = [x for x in (whole_view.get("temporary_rows") or []) if isinstance(x, dict)]
    promotion_rows = [x for x in (whole_view.get("promotion_rows") or []) if isinstance(x, dict)]
    role_positioning = str(whole_view.get("role_positioning") or "")
    governance_note = str(whole_view.get("governance_note") or "")

    return {
        "title": "Whole View Codex Role Boundary",
        "source_files": [
            {
                "path": _repo_rel(whole_view_path),
                "exists": whole_view_path.is_file(),
                "section": str(whole_view.get("section") or "7. Codex CLI 的定位：探索者 + 工具工，不是裁判"),
            }
        ],
        "summary": {
            "role_positioning_present": int(bool(role_positioning)),
            "temporary_row_total": len(temporary_rows),
            "promotion_row_total": len(promotion_rows),
            "governance_note_present": int(bool(governance_note)),
        },
        "whole_view": whole_view,
    }


def _workflow_checkpoints_context() -> dict[str, Any]:
    ssot_path = _repo_root() / "docs" / "12_workflows" / "skeleton_ssot_v1.yaml"
    whole_view_path = _find_overview_doc("Whole View Framework.md")
    playbook_path = _find_overview_doc("Implementation Phases Playbook.md")

    whole_view_section, whole_view_rows = _extract_whole_view_workflow_phases(whole_view_path)
    playbook_section, playbook_rows = _extract_playbook_phase_flow(playbook_path)
    ssot_doc = _load_yaml_map(ssot_path)

    goal_rows = ssot_doc.get("goal_checklist") if isinstance(ssot_doc.get("goal_checklist"), list) else []
    g39: dict[str, Any] = {}
    for row in goal_rows:
        if isinstance(row, dict) and str(row.get("id") or "") == "G39":
            g39 = row
            break

    dispatch_doc = ssot_doc.get("phase_dispatch_plan_v2") if isinstance(ssot_doc.get("phase_dispatch_plan_v2"), dict) else {}
    dispatch_rows = dispatch_doc.get("phases") if isinstance(dispatch_doc.get("phases"), list) else []
    phase59_dispatch: dict[str, Any] = {}
    for row in dispatch_rows:
        if not isinstance(row, dict):
            continue
        phase_id = str(row.get("phase_id") or "").strip()
        goal_id = str(row.get("goal_id") or "").strip()
        if (phase_id == "phase_59") or (goal_id == "G39"):
            phase59_dispatch = row
            break

    autopilot_doc = (
        ssot_doc.get("orchestrator_autopilot_v1")
        if isinstance(ssot_doc.get("orchestrator_autopilot_v1"), dict)
        else {}
    )
    autopilot_cycle = [str(x) for x in (autopilot_doc.get("cycle") or []) if isinstance(x, str)]
    next_goal_policy = autopilot_doc.get("next_goal_policy") if isinstance(autopilot_doc.get("next_goal_policy"), dict) else {}
    priority_order = [str(x) for x in (next_goal_policy.get("priority_order") or []) if isinstance(x, str)]

    pipeline_doc = ssot_doc.get("agents_pipeline_v1") if isinstance(ssot_doc.get("agents_pipeline_v1"), dict) else {}
    step_rows_raw = pipeline_doc.get("steps") if isinstance(pipeline_doc.get("steps"), list) else []
    pipeline_checkpoint_rows: list[dict[str, Any]] = []
    for row in step_rows_raw:
        if not isinstance(row, dict):
            continue
        step_id_raw = row.get("step_id")
        try:
            step_id = int(step_id_raw)
        except Exception:
            step_id = 0
        step_raw = row.get("checkpoint_step")
        checkpoint_step = str(step_raw).strip() if step_raw is not None else ""
        if checkpoint_step.lower() in ("none", "null"):
            checkpoint_step = ""
        planned_step = str(row.get("planned_checkpoint_step") or "").strip()
        if (not checkpoint_step) and planned_step:
            checkpoint_step = f"planned:{planned_step}"
        if not checkpoint_step:
            continue
        pipeline_checkpoint_rows.append(
            {
                "step_id": step_id,
                "name": str(row.get("name") or ""),
                "agent_id": str(row.get("agent_id") or ""),
                "status_now": str(row.get("status_now") or ""),
                "mapped_goal_id": str(row.get("mapped_goal_id") or ""),
                "checkpoint_step": checkpoint_step,
            }
        )
    pipeline_checkpoint_rows.sort(key=lambda row: int(row.get("step_id") or 0))

    checkpoint_summary_map: dict[str, dict[str, Any]] = {}
    for row in pipeline_checkpoint_rows:
        step = str(row.get("checkpoint_step") or "")
        if step not in checkpoint_summary_map:
            checkpoint_summary_map[step] = {
                "checkpoint_step": step,
                "step_total": 0,
                "agent_ids": [],
                "mapped_goal_ids": [],
            }
        summary_row = checkpoint_summary_map[step]
        summary_row["step_total"] = int(summary_row.get("step_total") or 0) + 1
        agent_id = str(row.get("agent_id") or "")
        if agent_id and (agent_id not in summary_row["agent_ids"]):
            summary_row["agent_ids"].append(agent_id)
        mapped_goal_id = str(row.get("mapped_goal_id") or "")
        if mapped_goal_id and (mapped_goal_id not in summary_row["mapped_goal_ids"]):
            summary_row["mapped_goal_ids"].append(mapped_goal_id)
    checkpoint_summary_rows = sorted(checkpoint_summary_map.values(), key=lambda row: str(row.get("checkpoint_step") or ""))

    whole_view_matrix_rows: list[dict[str, Any]] = []
    mapped_phase_total = 0
    for row in whole_view_rows:
        phase_no = int(row.get("phase_no") or 0)
        inferred_step = WHOLE_VIEW_PHASE_TO_SSOT_CHECKPOINT.get(phase_no, "")
        pipeline_matches = [r for r in pipeline_checkpoint_rows if str(r.get("checkpoint_step") or "") == inferred_step]
        mapping_status = "mapped" if pipeline_matches else ("inferred_only" if inferred_step else "n/a")
        if mapping_status == "mapped":
            mapped_phase_total += 1

        mapped_agents: list[str] = []
        mapped_goal_ids: list[str] = []
        for item in pipeline_matches:
            agent_id = str(item.get("agent_id") or "")
            if agent_id and (agent_id not in mapped_agents):
                mapped_agents.append(agent_id)
            mapped_goal_id = str(item.get("mapped_goal_id") or "")
            if mapped_goal_id and (mapped_goal_id not in mapped_goal_ids):
                mapped_goal_ids.append(mapped_goal_id)

        whole_view_matrix_rows.append(
            {
                "phase_no": phase_no,
                "phase_label": str(row.get("phase_label") or ""),
                "title": str(row.get("title") or ""),
                "source_line": int(row.get("source_line") or 0),
                "checkpoint_no": row.get("checkpoint_no"),
                "checkpoint_label": str(row.get("checkpoint_label") or ""),
                "checkpoint_detail": str(row.get("checkpoint_detail") or ""),
                "evidence_rows": list(row.get("evidence_rows") or []),
                "inferred_checkpoint_step": inferred_step,
                "mapping_status": mapping_status,
                "mapped_agents": mapped_agents,
                "mapped_goal_ids": mapped_goal_ids,
            }
        )
    whole_view_checkpoint_total = len([row for row in whole_view_matrix_rows if row.get("checkpoint_no") is not None])

    return {
        "title": "Whole View Workflow Checkpoints Matrix",
        "source_files": [
            {
                "path": _repo_rel(whole_view_path),
                "exists": whole_view_path.is_file(),
                "section": whole_view_section,
            },
            {
                "path": _repo_rel(playbook_path),
                "exists": playbook_path.is_file(),
                "section": playbook_section,
            },
            {
                "path": _repo_rel(ssot_path),
                "exists": ssot_path.is_file(),
                "section": "orchestrator_autopilot_v1 + phase_dispatch_plan_v2 + agents_pipeline_v1",
            },
        ],
        "summary": {
            "whole_view_phase_total": len(whole_view_matrix_rows),
            "whole_view_checkpoint_total": whole_view_checkpoint_total,
            "playbook_phase_total": len(playbook_rows),
            "ssot_pipeline_step_total": len([row for row in step_rows_raw if isinstance(row, dict)]),
            "ssot_pipeline_checkpoint_total": len(pipeline_checkpoint_rows),
            "ssot_checkpoint_kind_total": len(checkpoint_summary_rows),
            "mapped_phase_total": mapped_phase_total,
            "autopilot_cycle_total": len(autopilot_cycle),
        },
        "g39": {
            "id": str(g39.get("id") or ""),
            "title": str(g39.get("title") or ""),
            "status_now": str(g39.get("status_now") or ""),
            "ui_path": str(g39.get("ui_path") or ""),
            "depends_on": [str(x) for x in (g39.get("depends_on") or []) if isinstance(x, str)],
            "expected_state_change": str(g39.get("expected_state_change") or ""),
        },
        "dispatch": {
            "status_now": str(dispatch_doc.get("status_now") or ""),
            "mode": str(dispatch_doc.get("mode") or ""),
            "phase_id": str(phase59_dispatch.get("phase_id") or "phase_59"),
            "goal_id": str(phase59_dispatch.get("goal_id") or "G39"),
            "title": str(phase59_dispatch.get("title") or ""),
        },
        "autopilot": {
            "status_now": str(autopilot_doc.get("status_now") or ""),
            "enabled": bool(autopilot_doc.get("enabled")),
            "cycle_rows": autopilot_cycle,
            "priority_order": priority_order,
        },
        "pipeline": {
            "pipeline_id": str(pipeline_doc.get("pipeline_id") or ""),
            "execution_model": str(pipeline_doc.get("execution_model") or ""),
            "orchestration_owner": str(pipeline_doc.get("orchestration_owner") or ""),
            "checkpoint_rows": pipeline_checkpoint_rows,
            "checkpoint_summary_rows": checkpoint_summary_rows,
        },
        "whole_view_rows": whole_view_matrix_rows,
        "playbook_rows": playbook_rows,
    }


def _ui_route_methods_map() -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {}
    for route in router.routes:
        path = str(getattr(route, "path", "") or "").strip()
        if (not path) or (not path.startswith("/ui")):
            continue
        methods_raw = getattr(route, "methods", None) or set()
        methods = sorted({str(m).upper() for m in methods_raw if str(m).upper() != "OPTIONS"})
        rows[path] = methods
    return rows


def _ui_route_method_flags(methods: list[str]) -> dict[str, bool]:
    mset = {str(m).upper() for m in methods}
    has_get = "GET" in mset
    has_head = "HEAD" in mset
    has_write = bool(mset.intersection({"POST", "PUT", "PATCH", "DELETE"}))
    return {
        "has_get": has_get,
        "has_head": has_head,
        "has_write": has_write,
        "is_read_only": has_get and has_head and (not has_write),
    }


def _ia_coverage_context() -> dict[str, Any]:
    whole_view_path = _find_overview_doc("Whole View Framework.md")
    section_label, checklist = _extract_whole_view_ia_checklist(whole_view_path)
    route_method_map = _ui_route_methods_map()

    checklist_rows: list[dict[str, Any]] = []
    route_evidence_rows: list[dict[str, Any]] = []
    seen_routes: set[str] = set()

    mapped_item_total = 0
    covered_item_total = 0
    partial_item_total = 0
    missing_item_total = 0

    for item in checklist:
        idx = int(item.get("index") or 0)
        mapping_paths = IA_CHECKLIST_ROUTE_BINDINGS.get(idx, [])
        if mapping_paths:
            mapped_item_total += 1

        route_rows: list[dict[str, Any]] = []
        present_count = 0
        readonly_count = 0
        for route_path in mapping_paths:
            meta = IA_ROUTE_VIEW_CATALOG.get(route_path, {})
            template_name = str(meta.get("template") or "")
            methods = route_method_map.get(route_path, [])
            flags = _ui_route_method_flags(methods)
            route_exists = bool(methods)
            if route_exists:
                present_count += 1
            if flags["is_read_only"]:
                readonly_count += 1
            methods_label = ",".join(methods) if methods else "n/a"
            route_status = "read-only" if flags["is_read_only"] else ("present" if route_exists else "missing")

            route_row = {
                "path": route_path,
                "view_name": str(meta.get("view_name") or "n/a"),
                "template": template_name or "n/a",
                "methods": methods,
                "methods_label": methods_label,
                "route_exists": route_exists,
                "has_write": flags["has_write"],
                "is_read_only": flags["is_read_only"],
                "status": route_status,
            }
            route_rows.append(route_row)
            if route_path not in seen_routes:
                seen_routes.add(route_path)
                route_evidence_rows.append(route_row)

        required_count = len(mapping_paths)
        if required_count > 0 and readonly_count == required_count:
            item_status = "covered"
            covered_item_total += 1
        elif present_count > 0:
            item_status = "partial"
            partial_item_total += 1
        else:
            item_status = "missing"
            missing_item_total += 1

        checklist_rows.append(
            {
                "index": idx,
                "item": str(item.get("item") or ""),
                "mapping_note": IA_CHECKLIST_MAPPING_NOTES.get(idx, ""),
                "required_route_total": required_count,
                "present_route_total": present_count,
                "read_only_route_total": readonly_count,
                "status": item_status,
                "route_rows": route_rows,
            }
        )

    checklist_total = len(checklist_rows)
    route_total = len(route_evidence_rows)
    present_route_total = len([row for row in route_evidence_rows if bool(row.get("route_exists"))])
    read_only_route_total = len([row for row in route_evidence_rows if bool(row.get("is_read_only"))])
    denominator = mapped_item_total if mapped_item_total > 0 else checklist_total
    coverage_ratio = f"{covered_item_total}/{denominator}" if denominator > 0 else "n/a"

    return {
        "title": "UI Information Architecture Coverage",
        "source_file": {
            "path": _repo_rel(whole_view_path),
            "exists": whole_view_path.is_file(),
            "section": section_label,
        },
        "summary": {
            "checklist_total": checklist_total,
            "mapped_item_total": mapped_item_total,
            "covered_item_total": covered_item_total,
            "partial_item_total": partial_item_total,
            "missing_item_total": missing_item_total,
            "route_total": route_total,
            "present_route_total": present_route_total,
            "read_only_route_total": read_only_route_total,
            "coverage_ratio": coverage_ratio,
        },
        "checklist_rows": checklist_rows,
        "route_evidence_rows": route_evidence_rows,
    }


def _ui_coverage_matrix_context() -> dict[str, Any]:
    ssot_path = _repo_root() / "docs" / "12_workflows" / "skeleton_ssot_v1.yaml"
    ui_routes_path = _repo_root() / "src" / "quant_eam" / "api" / "ui_routes.py"
    whole_view_path = _find_overview_doc("Whole View Framework.md")
    whole_view_section, checklist = _extract_whole_view_ia_checklist(whole_view_path)
    route_method_map = _ui_route_methods_map()
    ssot_doc = _load_yaml_map(ssot_path)

    goal_rows = ssot_doc.get("goal_checklist") if isinstance(ssot_doc.get("goal_checklist"), list) else []
    g43: dict[str, Any] = {}
    for row in goal_rows:
        if isinstance(row, dict) and str(row.get("id") or "").strip() == "G43":
            g43 = row
            break

    dispatch_doc = ssot_doc.get("phase_dispatch_plan_v2") if isinstance(ssot_doc.get("phase_dispatch_plan_v2"), dict) else {}
    dispatch_rows = dispatch_doc.get("phases") if isinstance(dispatch_doc.get("phases"), list) else []
    phase63_dispatch: dict[str, Any] = {}
    for row in dispatch_rows:
        if not isinstance(row, dict):
            continue
        phase_id = str(row.get("phase_id") or "").strip()
        goal_id = str(row.get("goal_id") or "").strip()
        if (phase_id == "phase_63") or (goal_id == "G43"):
            phase63_dispatch = row
            break

    exception_rows = (
        ssot_doc.get("autopilot_stop_condition_exceptions_v1")
        if isinstance(ssot_doc.get("autopilot_stop_condition_exceptions_v1"), list)
        else []
    )
    g43_exception: dict[str, Any] = {}
    for row in exception_rows:
        if isinstance(row, dict) and str(row.get("exception_id") or "").strip() == "g43_ui_coverage_matrix_scope":
            g43_exception = row
            break
    preauth = g43_exception.get("preauthorized_scope") if isinstance(g43_exception.get("preauthorized_scope"), dict) else {}

    g43_expected_artifacts = [str(x) for x in (g43.get("expected_artifacts") or []) if isinstance(x, str)]
    g43_acceptance_commands = [str(x) for x in (g43.get("acceptance_commands") or []) if isinstance(x, str)]

    page_rows: list[dict[str, Any]] = []
    mapped_route_rows: list[dict[str, Any]] = []
    mapped_route_seen: set[str] = set()
    mapped_route_binding_total = 0
    covered_page_total = 0
    partial_page_total = 0
    missing_page_total = 0

    for item in checklist:
        idx = int(item.get("index") or 0)
        mapping_paths = IA_CHECKLIST_ROUTE_BINDINGS.get(idx, [])
        mapped_route_binding_total += len(mapping_paths)

        route_rows: list[dict[str, Any]] = []
        present_route_total = 0
        read_only_route_total = 0

        for route_path in mapping_paths:
            meta = IA_ROUTE_VIEW_CATALOG.get(route_path, {})
            methods = route_method_map.get(route_path, [])
            flags = _ui_route_method_flags(methods)
            route_exists = bool(methods)
            if route_exists:
                present_route_total += 1
            if flags["is_read_only"]:
                read_only_route_total += 1

            methods_label = ",".join(methods) if methods else "n/a"
            status = "read-only" if flags["is_read_only"] else ("present" if route_exists else "missing")
            route_row = {
                "path": route_path,
                "view_name": str(meta.get("view_name") or "n/a"),
                "template": str(meta.get("template") or "n/a"),
                "methods": methods,
                "methods_label": methods_label,
                "route_exists": route_exists,
                "is_read_only": flags["is_read_only"],
                "has_write": flags["has_write"],
                "status": status,
            }
            route_rows.append(route_row)
            if route_path not in mapped_route_seen:
                mapped_route_seen.add(route_path)
                mapped_route_rows.append(route_row)

        required_route_total = len(mapping_paths)
        if required_route_total > 0 and read_only_route_total == required_route_total:
            coverage_status = "covered"
            covered_page_total += 1
        elif present_route_total > 0:
            coverage_status = "partial"
            partial_page_total += 1
        else:
            coverage_status = "missing"
            missing_page_total += 1

        page_rows.append(
            {
                "index": idx,
                "item": str(item.get("item") or ""),
                "mapping_note": IA_CHECKLIST_MAPPING_NOTES.get(idx, ""),
                "required_route_total": required_route_total,
                "present_route_total": present_route_total,
                "read_only_route_total": read_only_route_total,
                "coverage_status": coverage_status,
                "route_rows": route_rows,
            }
        )

    all_ui_route_rows: list[dict[str, Any]] = []
    for route_path in sorted(route_method_map):
        methods = route_method_map.get(route_path, [])
        flags = _ui_route_method_flags(methods)
        meta = IA_ROUTE_VIEW_CATALOG.get(route_path, {})
        all_ui_route_rows.append(
            {
                "path": route_path,
                "view_name": str(meta.get("view_name") or "n/a"),
                "template": str(meta.get("template") or "n/a"),
                "methods": methods,
                "methods_label": ",".join(methods) if methods else "n/a",
                "route_exists": True,
                "is_read_only": flags["is_read_only"],
                "has_write": flags["has_write"],
                "mapped_to_section8": route_path in mapped_route_seen,
                "status": "read-only" if flags["is_read_only"] else ("write-enabled" if flags["has_write"] else "present"),
            }
        )

    mapped_route_total = len(mapped_route_rows)
    mapped_present_route_total = len([row for row in mapped_route_rows if bool(row.get("route_exists"))])
    mapped_read_only_route_total = len([row for row in mapped_route_rows if bool(row.get("is_read_only"))])
    all_ui_route_total = len(all_ui_route_rows)
    all_ui_route_read_only_total = len([row for row in all_ui_route_rows if bool(row.get("is_read_only"))])
    checklist_total = len(page_rows)
    coverage_ratio = f"{covered_page_total}/{checklist_total}" if checklist_total > 0 else "n/a"
    required_guards = [str(x) for x in (preauth.get("required_guards") or []) if isinstance(x, str)]

    return {
        "title": "Whole View UI Eight-Page Coverage Matrix",
        "source_files": [
            {
                "path": _repo_rel(whole_view_path),
                "exists": whole_view_path.is_file(),
                "section": whole_view_section,
            },
            {
                "path": _repo_rel(ui_routes_path),
                "exists": ui_routes_path.is_file(),
                "section": "IA_CHECKLIST_ROUTE_BINDINGS + IA_ROUTE_VIEW_CATALOG + router(/ui*)",
            },
            {
                "path": _repo_rel(ssot_path),
                "exists": ssot_path.is_file(),
                "section": "goal_checklist(G43) + phase_dispatch_plan_v2 + g43_ui_coverage_matrix_scope",
            },
        ],
        "summary": {
            "checklist_total": checklist_total,
            "covered_page_total": covered_page_total,
            "partial_page_total": partial_page_total,
            "missing_page_total": missing_page_total,
            "mapped_route_binding_total": mapped_route_binding_total,
            "mapped_route_total": mapped_route_total,
            "mapped_present_route_total": mapped_present_route_total,
            "mapped_read_only_route_total": mapped_read_only_route_total,
            "all_ui_route_total": all_ui_route_total,
            "all_ui_route_read_only_total": all_ui_route_read_only_total,
            "required_guard_total": len(required_guards),
            "expected_artifact_total": len(g43_expected_artifacts),
            "acceptance_command_total": len(g43_acceptance_commands),
            "coverage_ratio": coverage_ratio,
        },
        "g43": {
            "id": str(g43.get("id") or ""),
            "title": str(g43.get("title") or ""),
            "status_now": str(g43.get("status_now") or ""),
            "ui_path": str(g43.get("ui_path") or ""),
            "depends_on": [str(x) for x in (g43.get("depends_on") or []) if isinstance(x, str)],
            "expected_state_change": str(g43.get("expected_state_change") or ""),
        },
        "dispatch": {
            "status_now": str(dispatch_doc.get("status_now") or ""),
            "mode": str(dispatch_doc.get("mode") or ""),
            "phase_id": str(phase63_dispatch.get("phase_id") or "phase_63"),
            "goal_id": str(phase63_dispatch.get("goal_id") or "G43"),
            "title": str(phase63_dispatch.get("title") or ""),
        },
        "g43_exception": {
            "exception_id": str(g43_exception.get("exception_id") or ""),
            "allowed_route_prefixes": [str(x) for x in (preauth.get("allowed_route_prefixes") or []) if isinstance(x, str)],
            "allowed_code_paths": [str(x) for x in (preauth.get("allowed_code_paths") or []) if isinstance(x, str)],
            "still_forbidden": [str(x) for x in (preauth.get("still_forbidden") or []) if isinstance(x, str)],
            "required_guards": required_guards,
        },
        "page_rows": page_rows,
        "mapped_route_rows": mapped_route_rows,
        "all_ui_route_rows": all_ui_route_rows,
        "g43_expected_artifacts": g43_expected_artifacts,
        "g43_acceptance_commands": g43_acceptance_commands,
    }


def _extract_whole_view_runtime_topology(path: Path) -> dict[str, Any]:
    default_section = "9. 仓库与运行形态（Linux + Docker + Python）"
    default_intro = "推荐仓库结构"
    if not path.is_file():
        return {
            "section": default_section,
            "intro": default_intro,
            "topology_rows": [],
            "service_rows": [],
        }

    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    section = default_section
    intro = default_intro
    topology_rows: list[dict[str, Any]] = []
    service_markers = (
        "dockerfile.api",
        "dockerfile.worker",
        "docker-compose.yml",
        "ui/server",
    )

    for idx, raw in enumerate(lines, start=1):
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            if WHOLE_VIEW_SECTION9_RE.match(line) and (("仓库" in line) or ("运行形态" in line) or ("Docker" in line)):
                in_section = True
                section = _markdown_clean(line[3:]) or default_section
            continue
        if (not in_section) or (not line) or (line == "---"):
            continue

        cleaned = _markdown_clean(line)
        if not cleaned:
            continue
        if cleaned.endswith("：") and ("推荐仓库结构" in cleaned):
            intro = cleaned.rstrip("：").rstrip(":") or default_intro
            continue

        normalized = cleaned.rstrip("/")
        entry_kind = "directory" if cleaned.endswith("/") else "file"
        lower = cleaned.lower()
        is_service_evidence = any(marker in lower for marker in service_markers)

        topology_rows.append(
            {
                "index": len(topology_rows) + 1,
                "entry": cleaned,
                "entry_kind": entry_kind,
                "normalized": normalized,
                "source_line": idx,
                "is_service_evidence": is_service_evidence,
            }
        )

    service_rows = [row for row in topology_rows if bool(row.get("is_service_evidence"))]
    return {
        "section": section,
        "intro": intro,
        "topology_rows": topology_rows,
        "service_rows": service_rows,
    }


def _extract_playbook_section1_runtime_stack(path: Path) -> dict[str, Any]:
    section_default = "1. 技术栈建议（可替换，但先固定）"
    foundation_default = "1.1 基础"
    service_default = "1.2 服务（MVP）"
    if not path.is_file():
        return {
            "section": section_default,
            "foundation_section": foundation_default,
            "service_section": service_default,
            "foundation_rows": [],
            "service_rows": [],
        }

    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    section = section_default
    foundation_section = foundation_default
    service_section = service_default
    active_bucket = ""
    foundation_rows: list[dict[str, Any]] = []
    service_rows: list[dict[str, Any]] = []

    for idx, raw in enumerate(lines, start=1):
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            if PLAYBOOK_SECTION1_RE.match(line) and (("技术栈" in line) or ("stack" in line.lower())):
                in_section = True
                section = _markdown_clean(line[3:]) or section_default
            continue
        if not in_section:
            continue

        if line.startswith("### "):
            header = _markdown_clean(line[4:])
            if line.startswith("### 1.1") or header.startswith("1.1"):
                active_bucket = "foundation"
                foundation_section = header or foundation_default
                continue
            if line.startswith("### 1.2") or header.startswith("1.2"):
                active_bucket = "service"
                service_section = header or service_default
                continue
            active_bucket = ""
            continue

        if not line.startswith("- "):
            continue
        item = _markdown_clean(line[2:])
        if not item:
            continue
        row = {"item": item, "source_line": idx}
        if active_bucket == "foundation":
            foundation_rows.append(row)
        elif active_bucket == "service":
            service_rows.append(row)

    return {
        "section": section,
        "foundation_section": foundation_section,
        "service_section": service_section,
        "foundation_rows": foundation_rows,
        "service_rows": service_rows,
    }


def _extract_playbook_runtime_phase_context(path: Path) -> tuple[str, list[dict[str, Any]]]:
    section, rows = _extract_playbook_phase_flow(path)
    runtime_keywords = ("docker", "compose", "api", "worker", "ui", "service", "orchestrator")
    runtime_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        haystack_parts = [
            str(row.get("title") or ""),
            *[str(x) for x in (row.get("goal_rows") or []) if isinstance(x, str)],
            *[str(x) for x in (row.get("acceptance_rows") or []) if isinstance(x, str)],
            *[str(x) for x in (row.get("flow_rows") or []) if isinstance(x, str)],
        ]
        haystack = " ".join(haystack_parts).lower()
        matched_keywords = [kw for kw in runtime_keywords if kw in haystack]
        if not matched_keywords:
            continue
        runtime_rows.append(
            {
                "phase_no": int(row.get("phase_no") or 0),
                "phase_label": str(row.get("phase_label") or ""),
                "title": str(row.get("title") or ""),
                "source_line": int(row.get("source_line") or 0),
                "matched_keywords": matched_keywords,
                "goal_rows": [str(x) for x in (row.get("goal_rows") or []) if isinstance(x, str)],
                "acceptance_rows": [str(x) for x in (row.get("acceptance_rows") or []) if isinstance(x, str)],
                "flow_rows": [str(x) for x in (row.get("flow_rows") or []) if isinstance(x, str)],
            }
        )
    return section, runtime_rows


def _runtime_topology_context() -> dict[str, Any]:
    ssot_path = _repo_root() / "docs" / "12_workflows" / "skeleton_ssot_v1.yaml"
    whole_view_path = _find_overview_doc("Whole View Framework.md")
    playbook_path = _find_overview_doc("Implementation Phases Playbook.md")

    whole_view = _extract_whole_view_runtime_topology(whole_view_path)
    playbook_section1 = _extract_playbook_section1_runtime_stack(playbook_path)
    playbook_section3, playbook_phase_rows = _extract_playbook_runtime_phase_context(playbook_path)
    ssot_doc = _load_yaml_map(ssot_path)

    goal_rows = ssot_doc.get("goal_checklist") if isinstance(ssot_doc.get("goal_checklist"), list) else []
    g44: dict[str, Any] = {}
    for row in goal_rows:
        if isinstance(row, dict) and str(row.get("id") or "").strip() == "G44":
            g44 = row
            break

    dispatch_doc = ssot_doc.get("phase_dispatch_plan_v2") if isinstance(ssot_doc.get("phase_dispatch_plan_v2"), dict) else {}
    dispatch_rows = dispatch_doc.get("phases") if isinstance(dispatch_doc.get("phases"), list) else []
    phase64_dispatch: dict[str, Any] = {}
    for row in dispatch_rows:
        if not isinstance(row, dict):
            continue
        phase_id = str(row.get("phase_id") or "").strip()
        goal_id = str(row.get("goal_id") or "").strip()
        if (phase_id == "phase_64") or (goal_id == "G44"):
            phase64_dispatch = row
            break

    exception_rows = (
        ssot_doc.get("autopilot_stop_condition_exceptions_v1")
        if isinstance(ssot_doc.get("autopilot_stop_condition_exceptions_v1"), list)
        else []
    )
    g44_exception: dict[str, Any] = {}
    for row in exception_rows:
        if isinstance(row, dict) and str(row.get("exception_id") or "").strip() == "g44_runtime_topology_ui_scope":
            g44_exception = row
            break
    preauth = g44_exception.get("preauthorized_scope") if isinstance(g44_exception.get("preauthorized_scope"), dict) else {}
    required_guards = [str(x) for x in (preauth.get("required_guards") or []) if isinstance(x, str)]

    ui_requirements = ssot_doc.get("ui_requirements_v1") if isinstance(ssot_doc.get("ui_requirements_v1"), dict) else {}
    ports_doc = ui_requirements.get("ui_ports") if isinstance(ui_requirements.get("ui_ports"), dict) else {}
    ui_port_rows = [
        {"name": str(k), "value": str(v)}
        for k, v in sorted(ports_doc.items(), key=lambda kv: str(kv[0]))
        if str(k).strip()
    ]

    runtime_pref = ssot_doc.get("runtime_preferences_v1") if isinstance(ssot_doc.get("runtime_preferences_v1"), dict) else {}
    min_set = (
        runtime_pref.get("acceptance_evidence_min_set")
        if isinstance(runtime_pref.get("acceptance_evidence_min_set"), dict)
        else {}
    )
    runtime_required_commands = [str(x) for x in (min_set.get("required_commands") or []) if isinstance(x, str)]

    g44_expected_artifacts = [str(x) for x in (g44.get("expected_artifacts") or []) if isinstance(x, str)]
    g44_acceptance_commands = [str(x) for x in (g44.get("acceptance_commands") or []) if isinstance(x, str)]

    return {
        "title": "Whole View Runtime Topology and Service Ports",
        "source_files": [
            {
                "path": _repo_rel(whole_view_path),
                "exists": whole_view_path.is_file(),
                "section": str(whole_view.get("section") or "9. 仓库与运行形态（Linux + Docker + Python）"),
            },
            {
                "path": _repo_rel(playbook_path),
                "exists": playbook_path.is_file(),
                "section": "1. 技术栈建议（可替换，但先固定） + 3. Phase 列表（推荐施工顺序）",
            },
            {
                "path": _repo_rel(ssot_path),
                "exists": ssot_path.is_file(),
                "section": "goal_checklist(G44) + phase_dispatch_plan_v2 + g44_runtime_topology_ui_scope + ui_requirements_v1.ui_ports",
            },
        ],
        "summary": {
            "topology_entry_total": len([x for x in (whole_view.get("topology_rows") or []) if isinstance(x, dict)]),
            "whole_view_service_entry_total": len([x for x in (whole_view.get("service_rows") or []) if isinstance(x, dict)]),
            "playbook_foundation_total": len([x for x in (playbook_section1.get("foundation_rows") or []) if isinstance(x, dict)]),
            "playbook_service_total": len([x for x in (playbook_section1.get("service_rows") or []) if isinstance(x, dict)]),
            "playbook_runtime_phase_total": len(playbook_phase_rows),
            "ui_port_total": len(ui_port_rows),
            "required_guard_total": len(required_guards),
            "expected_artifact_total": len(g44_expected_artifacts),
            "acceptance_command_total": len(g44_acceptance_commands),
            "runtime_required_command_total": len(runtime_required_commands),
        },
        "g44": {
            "id": str(g44.get("id") or ""),
            "title": str(g44.get("title") or ""),
            "status_now": str(g44.get("status_now") or ""),
            "ui_path": str(g44.get("ui_path") or ""),
            "depends_on": [str(x) for x in (g44.get("depends_on") or []) if isinstance(x, str)],
            "expected_state_change": str(g44.get("expected_state_change") or ""),
        },
        "dispatch": {
            "status_now": str(dispatch_doc.get("status_now") or ""),
            "mode": str(dispatch_doc.get("mode") or ""),
            "phase_id": str(phase64_dispatch.get("phase_id") or "phase_64"),
            "goal_id": str(phase64_dispatch.get("goal_id") or "G44"),
            "title": str(phase64_dispatch.get("title") or ""),
        },
        "whole_view": whole_view,
        "playbook_section1": playbook_section1,
        "playbook_section3": playbook_section3,
        "playbook_phase_rows": playbook_phase_rows,
        "g44_exception": {
            "exception_id": str(g44_exception.get("exception_id") or ""),
            "allowed_route_prefixes": [str(x) for x in (preauth.get("allowed_route_prefixes") or []) if isinstance(x, str)],
            "allowed_code_paths": [str(x) for x in (preauth.get("allowed_code_paths") or []) if isinstance(x, str)],
            "still_forbidden": [str(x) for x in (preauth.get("still_forbidden") or []) if isinstance(x, str)],
            "required_guards": required_guards,
        },
        "ui_port_rows": ui_port_rows,
        "runtime_required_commands": runtime_required_commands,
        "g44_expected_artifacts": g44_expected_artifacts,
        "g44_acceptance_commands": g44_acceptance_commands,
    }


def _extract_whole_view_preflight_checklist(path: Path) -> dict[str, Any]:
    default_section = "10. “不跑偏”检查清单（每次新增功能前先对齐）"
    if not path.is_file():
        return {
            "section": default_section,
            "checklist_rows": [],
        }

    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    section = default_section
    checklist_rows: list[dict[str, Any]] = []

    for idx, raw in enumerate(lines, start=1):
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            if WHOLE_VIEW_SECTION10_RE.match(line) and (
                ("不跑偏" in line)
                or ("检查清单" in line)
                or ("anti-drift" in line.lower())
                or ("preflight" in line.lower())
            ):
                in_section = True
                section = _markdown_clean(line[3:]) or default_section
            continue
        if (not in_section) or (not line) or (line == "---"):
            continue
        if not line.startswith("- "):
            continue

        item = _markdown_clean(line[2:])
        if not item:
            continue
        checklist_rows.append(
            {
                "index": len(checklist_rows) + 1,
                "item": item,
                "source_line": idx,
            }
        )

    return {
        "section": section,
        "checklist_rows": checklist_rows,
    }


def _preflight_checklist_context() -> dict[str, Any]:
    whole_view_path = _find_overview_doc("Whole View Framework.md")
    whole_view = _extract_whole_view_preflight_checklist(whole_view_path)
    checklist_rows = [x for x in (whole_view.get("checklist_rows") or []) if isinstance(x, dict)]

    return {
        "title": "Whole View Anti-Drift Preflight Checklist",
        "source_files": [
            {
                "path": _repo_rel(whole_view_path),
                "exists": whole_view_path.is_file(),
                "section": str(whole_view.get("section") or "10. “不跑偏”检查清单（每次新增功能前先对齐）"),
            },
        ],
        "summary": {
            "checklist_total": len(checklist_rows),
        },
        "whole_view": whole_view,
    }


def _extract_whole_view_version_roadmap(path: Path) -> dict[str, Any]:
    default_section = "11. 版本路线（建议）"
    if not path.is_file():
        return {
            "section": default_section,
            "milestone_rows": [],
        }

    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    section = default_section
    milestone_rows: list[dict[str, Any]] = []

    for idx, raw in enumerate(lines, start=1):
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            if WHOLE_VIEW_SECTION11_RE.match(line) and (("版本路线" in line) or ("roadmap" in line.lower())):
                in_section = True
                section = _markdown_clean(line[3:]) or default_section
            continue
        if (not in_section) or (not line) or (line == "---"):
            continue
        if not line.startswith("- "):
            continue

        item = _markdown_clean(line[2:])
        m = WHOLE_VIEW_ROADMAP_MILESTONE_RE.match(item)
        if not m:
            continue
        version_num = str(m.group(1)).strip()
        milestone_rows.append(
            {
                "index": len(milestone_rows) + 1,
                "version": f"v{version_num}",
                "milestones": _markdown_clean(m.group(2)),
                "source_line": idx,
            }
        )

    return {
        "section": section,
        "milestone_rows": milestone_rows,
    }


def _version_roadmap_context() -> dict[str, Any]:
    whole_view_path = _find_overview_doc("Whole View Framework.md")
    whole_view = _extract_whole_view_version_roadmap(whole_view_path)
    milestone_rows = [x for x in (whole_view.get("milestone_rows") or []) if isinstance(x, dict)]

    versions = [str(x.get("version") or "") for x in milestone_rows if str(x.get("version") or "").strip()]
    return {
        "title": "Whole View Version Roadmap Milestones",
        "source_files": [
            {
                "path": _repo_rel(whole_view_path),
                "exists": whole_view_path.is_file(),
                "section": str(whole_view.get("section") or "11. 版本路线（建议）"),
            },
        ],
        "summary": {
            "milestone_total": len(milestone_rows),
            "versions": ", ".join(versions),
        },
        "whole_view": whole_view,
    }


def _extract_whole_view_system_definition(path: Path) -> dict[str, Any]:
    default_section = "0. 你要构建的系统是什么（Definition）"
    if not path.is_file():
        return {
            "section": default_section,
            "definition_statement": "",
            "capability_rows": [],
        }

    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    section = default_section
    definition_statement = ""
    capability_rows: list[dict[str, Any]] = []

    for idx, raw in enumerate(lines, start=1):
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            if WHOLE_VIEW_SECTION0_RE.match(line) and (("Definition" in line) or ("系统" in line)):
                in_section = True
                section = _markdown_clean(line[3:]) or default_section
            continue
        if (not in_section) or (not line) or (line == "---"):
            continue

        if line.startswith("- "):
            item = _markdown_clean(line[2:])
            if item:
                capability_rows.append(
                    {
                        "index": len(capability_rows) + 1,
                        "item": item,
                        "source_line": idx,
                    }
                )
            continue

        cleaned = _markdown_clean(line)
        if cleaned and not definition_statement:
            definition_statement = cleaned

    return {
        "section": section,
        "definition_statement": definition_statement,
        "capability_rows": capability_rows,
    }


def _extract_whole_view_five_planes(path: Path) -> dict[str, Any]:
    default_section = "2. 总体架构：五个平面（Planes）"
    if not path.is_file():
        return {
            "section": default_section,
            "plane_rows": [],
        }

    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    section = default_section
    plane_rows: list[dict[str, Any]] = []

    for idx, raw in enumerate(lines, start=1):
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            if WHOLE_VIEW_SECTION2_RE.match(line) and (("平面" in line) or ("Planes" in line)):
                in_section = True
                section = _markdown_clean(line[3:]) or default_section
            continue
        if (not in_section) or (not line) or (line == "---"):
            continue
        if not line.startswith("- "):
            continue

        item = line[2:].strip()
        m = WHOLE_VIEW_PLANE_ROW_RE.match(item)
        if m:
            plane_name = _markdown_clean(m.group(1))
            description = _markdown_clean(m.group(2))
        else:
            cleaned = _markdown_clean(item)
            plane_name, description = _split_role_line(cleaned)
        if not plane_name:
            continue
        plane_rows.append(
            {
                "index": len(plane_rows) + 1,
                "plane_name": plane_name,
                "description": description,
                "source_line": idx,
            }
        )

    return {
        "section": section,
        "plane_rows": plane_rows,
    }


def _system_definition_context() -> dict[str, Any]:
    whole_view_path = _whole_view_framework_root_doc()
    definition = _extract_whole_view_system_definition(whole_view_path)
    planes = _extract_whole_view_five_planes(whole_view_path)
    capability_rows = [x for x in (definition.get("capability_rows") or []) if isinstance(x, dict)]
    plane_rows = [x for x in (planes.get("plane_rows") or []) if isinstance(x, dict)]

    return {
        "title": "Whole View System Definition and Planes Evidence",
        "source_files": [
            {
                "path": _repo_rel(whole_view_path),
                "exists": whole_view_path.is_file(),
                "section": str(definition.get("section") or "0. 你要构建的系统是什么（Definition）"),
            },
            {
                "path": _repo_rel(whole_view_path),
                "exists": whole_view_path.is_file(),
                "section": str(planes.get("section") or "2. 总体架构：五个平面（Planes）"),
            },
        ],
        "summary": {
            "definition_rule_total": len(capability_rows),
            "plane_total": len(plane_rows),
        },
        "definition": definition,
        "planes": planes,
    }


def _extract_whole_view_dossier_structure(path: Path) -> dict[str, Any]:
    default_root = "dossiers/<run_id>/"
    if not path.is_file():
        return {"section": "4.4 Dossier", "root_entry": default_root, "run_entries": []}

    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    section = "4.4 Dossier"
    raw_entries: list[str] = []
    for raw in lines:
        line = raw.strip()
        if line.startswith("### "):
            if in_section:
                break
            if line.startswith("### 4.4") and ("Dossier" in line):
                in_section = True
                section = _markdown_clean(line[4:])
            continue
        if not in_section:
            continue
        if (not line) or (line == "---") or ("建议目录" in line) or line.startswith("```"):
            continue
        item = line[2:].strip() if line.startswith("- ") else line
        cleaned = _markdown_clean(item)
        if not cleaned:
            continue
        if cleaned.startswith("dossiers/<run_id>/") and cleaned != default_root:
            cleaned = cleaned[len("dossiers/<run_id>/") :]
        raw_entries.append(cleaned)

    root_entry = default_root
    run_entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw_entries:
        if item in ("dossiers/<run_id>", default_root):
            root_entry = default_root
            continue
        normalized = item.strip("/")
        if not normalized:
            continue
        is_dir = item.endswith("/")
        entry = f"{normalized}/" if is_dir else normalized
        if entry in seen:
            continue
        seen.add(entry)
        run_entries.append(
            {
                "entry": entry,
                "target": normalized,
                "kind": "directory" if is_dir else "file",
                "is_dir": is_dir,
            }
        )

    return {"section": section, "root_entry": root_entry, "run_entries": run_entries}


def _dossier_evidence_context() -> dict[str, Any]:
    whole_view_path = _find_overview_doc("Whole View Framework.md")
    structure = _extract_whole_view_dossier_structure(whole_view_path)

    required_run_entries = list(structure.get("run_entries") or [])
    required_total = len(required_run_entries)
    required_keys = {str(row.get("entry") or "") for row in required_run_entries}
    entry_present_runs = {str(row.get("entry") or ""): 0 for row in required_run_entries}

    dr = dossiers_root()
    run_dirs: list[Path] = []
    if dr.is_dir():
        run_dirs = sorted([p for p in dr.iterdir() if p.is_dir()], key=lambda p: p.name)

    run_rows: list[dict[str, Any]] = []
    for run_dir in run_dirs:
        present_count = 0
        missing_entries: list[str] = []
        for req in required_run_entries:
            entry = str(req.get("entry") or "")
            target = str(req.get("target") or "")
            is_dir = bool(req.get("is_dir"))
            if (not entry) or (not target):
                continue
            full = run_dir / target
            exists = full.is_dir() if is_dir else full.is_file()
            if exists:
                present_count += 1
                entry_present_runs[entry] = int(entry_present_runs.get(entry, 0)) + 1
            else:
                missing_entries.append(entry)

        discovered_entries = sorted(
            [f"{p.name}/" if p.is_dir() else p.name for p in run_dir.iterdir()],
            key=lambda x: x,
        )
        extra_entries = [name for name in discovered_entries if name not in required_keys]
        run_rows.append(
            {
                "run_id": run_dir.name,
                "path": _repo_rel(run_dir),
                "present_count": present_count,
                "required_count": required_total,
                "missing_count": len(missing_entries),
                "coverage_ratio": f"{present_count}/{required_total}" if required_total > 0 else "n/a",
                "missing_entries": missing_entries,
                "extra_count": len(extra_entries),
                "extra_entries": extra_entries[:12],
            }
        )

    entry_rows: list[dict[str, Any]] = []
    run_total = len(run_rows)
    for req in required_run_entries:
        entry = str(req.get("entry") or "")
        present_runs = int(entry_present_runs.get(entry, 0))
        missing_runs = max(run_total - present_runs, 0)
        entry_rows.append(
            {
                "entry": entry,
                "kind": str(req.get("kind") or ""),
                "present_runs": present_runs,
                "missing_runs": missing_runs,
                "coverage_ratio": f"{present_runs}/{run_total}" if run_total > 0 else "n/a",
            }
        )

    structure_rows = [{"entry": str(structure.get("root_entry") or "dossiers/<run_id>/"), "kind": "directory"}]
    for row in required_run_entries:
        structure_rows.append({"entry": str(row.get("entry") or ""), "kind": str(row.get("kind") or "")})

    return {
        "title": "Dossier Evidence Spec Coverage",
        "source_file": {
            "path": _repo_rel(whole_view_path),
            "exists": whole_view_path.is_file(),
            "section": str(structure.get("section") or "4.4 Dossier"),
            "root_entry": str(structure.get("root_entry") or "dossiers/<run_id>/"),
        },
        "dossiers_root": {
            "path": _repo_rel(dr),
            "exists": dr.is_dir(),
        },
        "summary": {
            "structure_entry_total": len(structure_rows),
            "required_run_entry_total": required_total,
            "dossier_run_total": run_total,
        },
        "structure_rows": structure_rows,
        "run_rows": run_rows,
        "entry_rows": entry_rows,
    }


def _extract_playbook_bullets(path: Path, heading_contains: str) -> list[str]:
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    start_idx = -1
    for i, raw in enumerate(lines):
        line = raw.strip()
        if line.startswith("### ") and heading_contains in line:
            start_idx = i + 1
            break
    if start_idx < 0:
        return []

    out: list[str] = []
    for raw in lines[start_idx:]:
        line = raw.strip()
        if line.startswith("### ") or line.startswith("## "):
            break
        if not line.startswith("- "):
            continue
        item = _markdown_clean(line[2:])
        if item:
            out.append(item)
    return out


def _load_yaml_map(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _extract_playbook_phase8_evidence(path: Path) -> dict[str, Any]:
    section_default = "Phase-8：Agents v1（Intent / StrategySpec / Spec‑QA / Report / Improvement）"
    if not path.is_file():
        return {
            "section": section_default,
            "goal_rows": [],
            "background_rows": [],
            "code_rows": [],
            "module_rows": [],
            "harness_rows": [],
            "docs_rows": [],
            "acceptance_rows": [],
        }

    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    section = section_default
    current_heading = ""
    goal_rows: list[str] = []
    background_rows: list[str] = []
    code_rows: list[str] = []
    module_rows: list[str] = []
    harness_rows: list[str] = []
    docs_rows: list[str] = []
    acceptance_rows: list[str] = []

    def _append_unique(bucket: list[str], item: str) -> None:
        if item and item not in bucket:
            bucket.append(item)

    for raw in lines:
        line = raw.strip()
        if line.startswith("### "):
            if in_section:
                break
            m = PLAYBOOK_PHASE_HEADER_RE.match(line)
            if m and int(m.group(1)) == 8:
                in_section = True
                section = _markdown_clean(line[4:]) or section_default
            continue
        if not in_section:
            continue
        if line.startswith("**") and line.endswith("**"):
            current_heading = _markdown_clean(line.strip("*"))
            continue
        if not line.startswith("- "):
            continue
        item = _markdown_clean(line[2:])
        if not item:
            continue

        if "目标" in current_heading:
            _append_unique(goal_rows, item)
            continue
        if "背景" in current_heading:
            _append_unique(background_rows, item)
            continue
        if "编码内容" in current_heading:
            _append_unique(code_rows, item)
            if item.startswith("agents/"):
                _append_unique(module_rows, item)
            else:
                _append_unique(harness_rows, item)
            continue
        if "文档" in current_heading:
            _append_unique(docs_rows, item)
            continue
        if "验收" in current_heading:
            _append_unique(acceptance_rows, item)
            continue

    return {
        "section": section,
        "goal_rows": goal_rows,
        "background_rows": background_rows,
        "code_rows": code_rows,
        "module_rows": module_rows,
        "harness_rows": harness_rows,
        "docs_rows": docs_rows,
        "acceptance_rows": acceptance_rows,
    }


def _agent_roles_context() -> dict[str, Any]:
    whole_view_path = _find_overview_doc("Whole View Framework.md")
    playbook_path = _find_overview_doc("Implementation Phases Playbook.md")
    ssot_path = _repo_root() / "docs" / "12_workflows" / "skeleton_ssot_v1.yaml"

    whole_view_section, whole_view_roles = _extract_whole_view_agent_roles(whole_view_path)
    phase8 = _extract_playbook_phase8_evidence(playbook_path)
    ssot_doc = _load_yaml_map(ssot_path)
    pipeline_doc = ssot_doc.get("agents_pipeline_v1") if isinstance(ssot_doc.get("agents_pipeline_v1"), dict) else {}
    goal_rows = ssot_doc.get("goal_checklist") if isinstance(ssot_doc.get("goal_checklist"), list) else []

    g38: dict[str, Any] = {}
    for row in goal_rows:
        if isinstance(row, dict) and str(row.get("id") or "") == "G38":
            g38 = row
            break

    shared_storage = (
        pipeline_doc.get("shared_storage_contract")
        if isinstance(pipeline_doc.get("shared_storage_contract"), dict)
        else {}
    )
    shared_storage_rows = [
        {"key": str(k), "value": str(v)}
        for k, v in sorted(shared_storage.items(), key=lambda kv: str(kv[0]))
    ]

    global_read_rules = [str(x) for x in (pipeline_doc.get("global_read_rules") or []) if isinstance(x, str)]
    steps_raw = pipeline_doc.get("steps") if isinstance(pipeline_doc.get("steps"), list) else []
    step_rows: list[dict[str, Any]] = []
    implemented_total = 0
    with_checkpoint_total = 0
    for row in steps_raw:
        if not isinstance(row, dict):
            continue
        step_id_raw = row.get("step_id")
        try:
            step_id = int(step_id_raw)
        except Exception:
            step_id = 0
        checkpoint_step = row.get("checkpoint_step")
        checkpoint_value = str(checkpoint_step).strip() if checkpoint_step is not None else ""
        if checkpoint_value.lower() in ("none", "null"):
            checkpoint_value = ""
        planned_checkpoint = str(row.get("planned_checkpoint_step") or "").strip()
        checkpoint_label = checkpoint_value or (f"planned:{planned_checkpoint}" if planned_checkpoint else "n/a")
        status_now = str(row.get("status_now") or "unknown").strip() or "unknown"
        if status_now == "implemented":
            implemented_total += 1
        if checkpoint_value:
            with_checkpoint_total += 1

        notes = [str(x) for x in (row.get("notes") or []) if isinstance(x, str)]
        step_rows.append(
            {
                "step_id": step_id,
                "name": str(row.get("name") or ""),
                "agent_id": str(row.get("agent_id") or ""),
                "status_now": status_now,
                "mapped_goal_id": str(row.get("mapped_goal_id") or ""),
                "checkpoint_step": checkpoint_label,
                "outputs_dir": str(row.get("outputs_dir") or ""),
                "notes": notes,
            }
        )

    step_rows.sort(key=lambda item: int(item.get("step_id") or 0))

    return {
        "title": "Agents Roles and Harness Boundary Evidence",
        "source_files": [
            {
                "path": _repo_rel(whole_view_path),
                "exists": whole_view_path.is_file(),
                "section": whole_view_section,
            },
            {
                "path": _repo_rel(playbook_path),
                "exists": playbook_path.is_file(),
                "section": str(phase8.get("section") or "Phase-8"),
            },
            {
                "path": _repo_rel(ssot_path),
                "exists": ssot_path.is_file(),
                "section": "agents_pipeline_v1",
            },
        ],
        "g38": {
            "id": str(g38.get("id") or ""),
            "title": str(g38.get("title") or ""),
            "status_now": str(g38.get("status_now") or ""),
            "ui_path": str(g38.get("ui_path") or ""),
            "depends_on": [str(x) for x in (g38.get("depends_on") or []) if isinstance(x, str)],
        },
        "summary": {
            "whole_view_role_total": len(whole_view_roles),
            "playbook_phase8_module_total": len(phase8.get("module_rows") or []),
            "playbook_phase8_harness_total": len(phase8.get("harness_rows") or []),
            "playbook_phase8_acceptance_total": len(phase8.get("acceptance_rows") or []),
            "pipeline_step_total": len(step_rows),
            "pipeline_implemented_step_total": implemented_total,
            "pipeline_checkpoint_step_total": with_checkpoint_total,
            "global_read_rule_total": len(global_read_rules),
        },
        "whole_view_roles": whole_view_roles,
        "phase8": phase8,
        "pipeline": {
            "pipeline_id": str(pipeline_doc.get("pipeline_id") or ""),
            "execution_model": str(pipeline_doc.get("execution_model") or ""),
            "orchestration_owner": str(pipeline_doc.get("orchestration_owner") or ""),
            "shared_storage_rows": shared_storage_rows,
            "global_read_rules": global_read_rules,
            "step_rows": step_rows,
        },
    }


def _extract_playbook_phase_rows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []

    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    rows: list[dict[str, Any]] = []
    for idx, raw in enumerate(lines, start=1):
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            in_section = bool(PLAYBOOK_SECTION3_RE.match(line)) and ("Phase" in line)
            continue
        if not in_section:
            continue
        m = PLAYBOOK_PHASE_HEADER_RE.match(line)
        if not m:
            continue
        phase_no = int(m.group(1))
        rows.append(
            {
                "phase_no": phase_no,
                "phase_label": f"Phase-{phase_no}",
                "title": _markdown_clean(m.group(2)),
                "source_line": idx,
            }
        )
    return rows


def _normalize_match_text(text: str) -> str:
    s = str(text).strip().lower()
    if not s:
        return ""
    s = (
        s.replace("‐", "-")
        .replace("‑", "-")
        .replace("‒", "-")
        .replace("–", "-")
        .replace("—", "-")
        .replace("/", " ")
        .replace("_", " ")
        .replace("-", " ")
    )
    s = re.sub(r"[^a-z0-9+ ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _keyword_hits(text_norm: str, keywords: tuple[str, ...]) -> list[str]:
    if not text_norm:
        return []
    padded = f" {text_norm} "
    hits: list[str] = []
    for raw in keywords:
        key = _normalize_match_text(raw)
        if not key:
            continue
        if (" " in key and key in text_norm) or (f" {key} " in padded):
            hits.append(key)
    return hits


def _infer_playbook_phase_no(*, dispatch_title: str, goal_title: str, goal_ui_path: str) -> tuple[int | None, list[str]]:
    merged = _normalize_match_text(" ".join([dispatch_title, goal_title, goal_ui_path]))
    best_phase: int | None = None
    best_hits: list[str] = []
    best_score = 0

    for phase_no in sorted(PLAYBOOK_PHASE_KEYWORDS):
        hits = _keyword_hits(merged, PLAYBOOK_PHASE_KEYWORDS[phase_no])
        score = len(hits)
        if goal_ui_path.startswith("/ui") and phase_no == 6:
            score += 2
            hits = [*hits, "ui_path:/ui*"]
        if score > best_score:
            best_phase = phase_no
            best_hits = hits
            best_score = score

    if (best_phase is None) or (best_score <= 0):
        return None, []
    return best_phase, sorted(dict.fromkeys(best_hits))


def _playbook_phases_context() -> dict[str, Any]:
    ssot_path = _repo_root() / "docs" / "12_workflows" / "skeleton_ssot_v1.yaml"
    playbook_path = _find_overview_doc("Implementation Phases Playbook.md")
    ssot_doc = _load_yaml_map(ssot_path)

    playbook_rows_raw = _extract_playbook_phase_rows(playbook_path)
    playbook_rows: list[dict[str, Any]] = []
    playbook_rows_by_no: dict[int, dict[str, Any]] = {}
    for row in playbook_rows_raw:
        prepared = {
            "phase_no": int(row.get("phase_no") or 0),
            "phase_label": str(row.get("phase_label") or ""),
            "title": str(row.get("title") or ""),
            "source_line": int(row.get("source_line") or 0),
            "dispatch_rows": [],
            "mapped_total": 0,
            "status_rows": [],
        }
        playbook_rows.append(prepared)
        playbook_rows_by_no[int(prepared["phase_no"])] = prepared

    goal_rows = ssot_doc.get("goal_checklist") if isinstance(ssot_doc.get("goal_checklist"), list) else []
    goals_by_id: dict[str, dict[str, Any]] = {}
    for row in goal_rows:
        if not isinstance(row, dict):
            continue
        goal_id = str(row.get("id") or "").strip()
        if goal_id:
            goals_by_id[goal_id] = row

    dispatch_doc = ssot_doc.get("phase_dispatch_plan_v2") if isinstance(ssot_doc.get("phase_dispatch_plan_v2"), dict) else {}
    dispatch_plan_rows = dispatch_doc.get("phases") if isinstance(dispatch_doc.get("phases"), list) else []

    dispatch_rows: list[dict[str, Any]] = []
    for row in dispatch_plan_rows:
        if not isinstance(row, dict):
            continue
        phase_id = str(row.get("phase_id") or "").strip()
        goal_id = str(row.get("goal_id") or "").strip()
        dispatch_title = str(row.get("title") or "").strip()
        goal = goals_by_id.get(goal_id, {})
        goal_title = str(goal.get("title") or "").strip()
        goal_status = str(goal.get("status_now") or "unknown").strip() or "unknown"
        goal_ui_path = str(goal.get("ui_path") or "").strip()
        depends_on = [str(x) for x in (goal.get("depends_on") or []) if isinstance(x, str)]
        mapped_phase_no, mapping_terms = _infer_playbook_phase_no(
            dispatch_title=dispatch_title,
            goal_title=goal_title,
            goal_ui_path=goal_ui_path,
        )
        dispatch_row = {
            "phase_id": phase_id,
            "goal_id": goal_id,
            "dispatch_title": dispatch_title,
            "goal_title": goal_title,
            "goal_status": goal_status,
            "goal_ui_path": goal_ui_path,
            "depends_on": depends_on,
            "mapped_phase_no": mapped_phase_no,
            "mapped_phase_label": (f"Phase-{mapped_phase_no}" if mapped_phase_no is not None else "unmapped"),
            "mapping_terms": mapping_terms,
            "mapping_reason": (", ".join(mapping_terms) if mapping_terms else "no keyword match"),
        }
        dispatch_rows.append(dispatch_row)
        if mapped_phase_no is not None and mapped_phase_no in playbook_rows_by_no:
            playbook_rows_by_no[mapped_phase_no]["dispatch_rows"].append(dispatch_row)

    for playbook_row in playbook_rows:
        mapped = playbook_row.get("dispatch_rows") if isinstance(playbook_row.get("dispatch_rows"), list) else []
        playbook_row["mapped_total"] = len(mapped)
        status_counter = Counter(str(x.get("goal_status") or "unknown") for x in mapped if isinstance(x, dict))
        playbook_row["status_rows"] = [
            {"status": key, "count": int(status_counter[key])}
            for key in sorted(status_counter, key=lambda k: (-int(status_counter[k]), str(k)))
        ]

    status_counter = Counter(str(x.get("goal_status") or "unknown") for x in dispatch_rows)
    status_rows = [
        {"status": key, "count": int(status_counter[key])}
        for key in sorted(status_counter, key=lambda k: (-int(status_counter[k]), str(k)))
    ]

    unmapped_dispatch_rows = [row for row in dispatch_rows if row.get("mapped_phase_no") is None]
    g36 = goals_by_id.get("G36", {})

    return {
        "title": "Playbook Phase Matrix Evidence",
        "source_files": [
            {
                "path": _repo_rel(playbook_path),
                "exists": playbook_path.is_file(),
                "section": "3. Phase 列表（推荐施工顺序）",
            },
            {
                "path": _repo_rel(ssot_path),
                "exists": ssot_path.is_file(),
                "section": "phase_dispatch_plan_v2 + goal_checklist",
            },
        ],
        "dispatch_meta": {
            "status_now": str(dispatch_doc.get("status_now") or ""),
            "mode": str(dispatch_doc.get("mode") or ""),
        },
        "summary": {
            "playbook_phase_total": len(playbook_rows),
            "dispatch_phase_total": len(dispatch_rows),
            "mapped_dispatch_total": len(dispatch_rows) - len(unmapped_dispatch_rows),
            "unmapped_dispatch_total": len(unmapped_dispatch_rows),
            "goal_checklist_total": len(goals_by_id),
        },
        "goal_status_rows": status_rows,
        "playbook_rows": playbook_rows,
        "dispatch_rows": dispatch_rows,
        "unmapped_dispatch_rows": unmapped_dispatch_rows,
        "g36": {
            "id": str(g36.get("id") or ""),
            "title": str(g36.get("title") or ""),
            "status_now": str(g36.get("status_now") or ""),
            "ui_path": str(g36.get("ui_path") or ""),
            "depends_on": [str(x) for x in (g36.get("depends_on") or []) if isinstance(x, str)],
        },
    }


def _extract_playbook_section0_principles(path: Path) -> dict[str, Any]:
    default_section = "0. 施工总原则（Codex 任务组织）"
    default_principle_section = "0.1 单次 Codex 任务必须满足"
    default_quality_section = "0.2 全局质量门槛（CI 必须强制）"
    if not path.is_file():
        return {
            "section": default_section,
            "principle_section": default_principle_section,
            "quality_section": default_quality_section,
            "principle_rows": [],
            "quality_rows": [],
        }

    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    section = default_section
    principle_section = default_principle_section
    quality_section = default_quality_section
    in_quality_subsection = False
    principle_rows: list[dict[str, Any]] = []
    quality_rows: list[dict[str, Any]] = []

    for idx, raw in enumerate(lines, start=1):
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            if PLAYBOOK_SECTION0_RE.match(line):
                in_section = True
                section = _markdown_clean(line[3:]) or default_section
            continue
        if (not in_section) or (not line) or (line == "---"):
            continue

        if line.startswith("### "):
            subsection = _markdown_clean(line[4:])
            if PLAYBOOK_SUBSECTION01_RE.match(line):
                in_quality_subsection = False
                principle_section = subsection or default_principle_section
            elif PLAYBOOK_SUBSECTION02_RE.match(line):
                in_quality_subsection = True
                quality_section = subsection or default_quality_section
            else:
                in_quality_subsection = False
            continue

        if not line.startswith("- "):
            continue

        item = _markdown_clean(line[2:])
        if not item:
            continue

        bucket = quality_rows if in_quality_subsection else principle_rows
        bucket.append(
            {
                "index": len(bucket) + 1,
                "item": item,
                "source_line": idx,
            }
        )

    return {
        "section": section,
        "principle_section": principle_section,
        "quality_section": quality_section,
        "principle_rows": principle_rows,
        "quality_rows": quality_rows,
    }


def _playbook_principles_context() -> dict[str, Any]:
    playbook_path = _find_overview_doc("Implementation Phases Playbook.md")
    playbook = _extract_playbook_section0_principles(playbook_path)
    principle_rows = [x for x in (playbook.get("principle_rows") or []) if isinstance(x, dict)]
    quality_rows = [x for x in (playbook.get("quality_rows") or []) if isinstance(x, dict)]

    return {
        "title": "Playbook Construction Principles and Quality Gates",
        "source_files": [
            {
                "path": _repo_rel(playbook_path),
                "exists": playbook_path.is_file(),
                "section": str(playbook.get("section") or "0. 施工总原则（Codex 任务组织）"),
            },
            {
                "path": _repo_rel(playbook_path),
                "exists": playbook_path.is_file(),
                "section": str(playbook.get("quality_section") or "0.2 全局质量门槛（CI 必须强制）"),
            },
        ],
        "summary": {
            "principle_total": len(principle_rows),
            "quality_gate_total": len(quality_rows),
        },
        "playbook": playbook,
    }


def _playbook_tech_stack_context() -> dict[str, Any]:
    playbook_path = _find_overview_doc("Implementation Phases Playbook.md")
    playbook = _extract_playbook_section1_runtime_stack(playbook_path)
    foundation_rows = [x for x in (playbook.get("foundation_rows") or []) if isinstance(x, dict)]
    service_rows = [x for x in (playbook.get("service_rows") or []) if isinstance(x, dict)]

    return {
        "title": "Playbook Technical Stack Baseline",
        "source_files": [
            {
                "path": _repo_rel(playbook_path),
                "exists": playbook_path.is_file(),
                "section": str(playbook.get("section") or "1. 技术栈建议（可替换，但先固定）"),
            },
            {
                "path": _repo_rel(playbook_path),
                "exists": playbook_path.is_file(),
                "section": str(playbook.get("foundation_section") or "1.1 基础"),
            },
            {
                "path": _repo_rel(playbook_path),
                "exists": playbook_path.is_file(),
                "section": str(playbook.get("service_section") or "1.2 服务（MVP）"),
            },
        ],
        "summary": {
            "foundation_total": len(foundation_rows),
            "service_total": len(service_rows),
        },
        "playbook": playbook,
    }


def _extract_playbook_section2_phase_template(path: Path) -> dict[str, Any]:
    section_default = "2. Phase 模板（后续你要我写每个 phase 标准内容，就按这个模板）"
    template_default = "Phase‑X 标准输出结构"
    if not path.is_file():
        return {
            "section": section_default,
            "intro": "",
            "template_section": template_default,
            "template_rows": [],
        }

    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    in_template = False
    section = section_default
    intro = ""
    template_section = template_default
    template_rows: list[dict[str, Any]] = []

    for idx, raw in enumerate(lines, start=1):
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            if PLAYBOOK_SECTION2_RE.match(line) and (("phase" in line.lower()) and (("模板" in line) or ("template" in line.lower()))):
                in_section = True
                section = _markdown_clean(line[3:]) or section_default
            continue
        if (not in_section) or (not line) or (line == "---"):
            continue

        if line.startswith(">"):
            quote = _markdown_clean(line.lstrip(">").strip())
            if quote and not intro:
                intro = quote
            continue

        if line.startswith("### "):
            header = _markdown_clean(line[4:])
            header_l = header.lower()
            if ("phase" in header_l) and (("标准输出结构" in header) or ("template" in header_l)):
                in_template = True
                template_section = header or template_default
            else:
                in_template = False
            continue

        if not in_template:
            continue

        m = re.match(r"^([1-9][0-9]*)[.)]\s*(.+)$", line)
        if not m:
            continue
        item = _markdown_clean(m.group(2))
        if not item:
            continue
        template_rows.append(
            {
                "index": int(m.group(1)),
                "item": item,
                "source_line": idx,
            }
        )

    return {
        "section": section,
        "intro": intro,
        "template_section": template_section,
        "template_rows": template_rows,
    }


def _playbook_phase_template_context() -> dict[str, Any]:
    playbook_path = _find_overview_doc("Implementation Phases Playbook.md")
    playbook = _extract_playbook_section2_phase_template(playbook_path)
    template_rows = [x for x in (playbook.get("template_rows") or []) if isinstance(x, dict)]

    return {
        "title": "Playbook Phase Template Structure",
        "source_files": [
            {
                "path": _repo_rel(playbook_path),
                "exists": playbook_path.is_file(),
                "section": str(playbook.get("section") or "2. Phase 模板（后续你要我写每个 phase 标准内容，就按这个模板）"),
            },
            {
                "path": _repo_rel(playbook_path),
                "exists": playbook_path.is_file(),
                "section": str(playbook.get("template_section") or "Phase‑X 标准输出结构"),
            },
        ],
        "summary": {
            "template_item_total": len(template_rows),
        },
        "playbook": playbook,
    }


def _extract_playbook_section4_codex_task_card(path: Path) -> dict[str, Any]:
    section_default = "4. 每个 Phase 给 Codex 的“标准任务卡模板”（你后续可反复复用）"
    template_default = "Codex Task Card Template"
    if not path.is_file():
        return {
            "section": section_default,
            "intro": "",
            "template_section": template_default,
            "field_rows": [],
            "must_rows": [],
            "forbidden_rows": [],
            "acceptance_rows": [],
        }

    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    in_template = False
    section = section_default
    intro = ""
    template_section = template_default
    field_rows: list[dict[str, Any]] = []
    must_rows: list[dict[str, Any]] = []
    forbidden_rows: list[dict[str, Any]] = []
    acceptance_rows: list[dict[str, Any]] = []
    list_mode = ""

    for idx, raw in enumerate(lines, start=1):
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            if PLAYBOOK_SECTION4_RE.match(line) and (("任务卡" in line) or ("task card" in line.lower())):
                in_section = True
                section = _markdown_clean(line[3:]) or section_default
            continue
        if (not in_section) or (not line) or (line == "---"):
            continue

        if line.startswith(">"):
            quote = _markdown_clean(line.lstrip(">").strip())
            if quote and not intro:
                intro = quote
            continue

        if line.startswith("### "):
            header = _markdown_clean(line[4:])
            header_l = header.lower()
            if ("codex" in header_l) and (("task card" in header_l) or ("任务卡" in header)):
                in_template = True
                template_section = header or template_default
            else:
                in_template = False
            list_mode = ""
            continue

        if not in_template:
            continue

        row = re.match(r"^\*\*([^*]+)\*\*[:：]\s*(.*)$", line)
        if row:
            label = _markdown_clean(row.group(1))
            value = _markdown_clean(row.group(2))
            label_l = label.lower()
            if ("必须实现" in label) or ("must implement" in label_l):
                list_mode = "must"
            elif ("禁止项" in label) or ("forbidden" in label_l):
                list_mode = "forbidden"
            elif ("验收命令" in label) or ("acceptance" in label_l):
                list_mode = "acceptance"
            else:
                list_mode = ""
                field_rows.append(
                    {
                        "index": len(field_rows) + 1,
                        "label": label,
                        "value": value,
                        "source_line": idx,
                    }
                )
            continue

        if not line.startswith("- "):
            continue

        item = _markdown_clean(line[2:])
        if not item:
            continue
        bucket: list[dict[str, Any]]
        if list_mode == "must":
            bucket = must_rows
        elif list_mode == "forbidden":
            bucket = forbidden_rows
        elif list_mode == "acceptance":
            bucket = acceptance_rows
        else:
            continue
        bucket.append(
            {
                "index": len(bucket) + 1,
                "item": item,
                "source_line": idx,
            }
        )

    return {
        "section": section,
        "intro": intro,
        "template_section": template_section,
        "field_rows": field_rows,
        "must_rows": must_rows,
        "forbidden_rows": forbidden_rows,
        "acceptance_rows": acceptance_rows,
    }


def _playbook_codex_task_card_context() -> dict[str, Any]:
    playbook_path = _find_overview_doc("Implementation Phases Playbook.md")
    playbook = _extract_playbook_section4_codex_task_card(playbook_path)
    field_rows = [x for x in (playbook.get("field_rows") or []) if isinstance(x, dict)]
    must_rows = [x for x in (playbook.get("must_rows") or []) if isinstance(x, dict)]
    forbidden_rows = [x for x in (playbook.get("forbidden_rows") or []) if isinstance(x, dict)]
    acceptance_rows = [x for x in (playbook.get("acceptance_rows") or []) if isinstance(x, dict)]

    return {
        "title": "Playbook Codex Task Card Template",
        "source_files": [
            {
                "path": _repo_rel(playbook_path),
                "exists": playbook_path.is_file(),
                "section": str(playbook.get("section") or "4. 每个 Phase 给 Codex 的“标准任务卡模板”（你后续可反复复用）"),
            },
            {
                "path": _repo_rel(playbook_path),
                "exists": playbook_path.is_file(),
                "section": str(playbook.get("template_section") or "Codex Task Card Template"),
            },
        ],
        "summary": {
            "field_total": len(field_rows),
            "must_total": len(must_rows),
            "forbidden_total": len(forbidden_rows),
            "acceptance_total": len(acceptance_rows),
        },
        "playbook": playbook,
    }


def _extract_playbook_section5_sequence(path: Path) -> dict[str, Any]:
    section_default = "5. 结束语（施工顺序建议）"
    if not path.is_file():
        return {
            "section": section_default,
            "intro": "",
            "sequence_rows": [],
            "sequence_phase_rows": [],
            "loop_first_note": "",
            "loop_component_rows": [],
            "automation_note": "",
        }

    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    section = section_default
    intro = ""
    sequence_rows: list[dict[str, Any]] = []
    sequence_phase_rows: list[dict[str, Any]] = []
    loop_first_note = ""
    loop_component_rows: list[dict[str, Any]] = []
    automation_note = ""
    seen_phase_nos: set[int] = set()
    seen_components: set[str] = set()

    for idx, raw in enumerate(lines, start=1):
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            if PLAYBOOK_SECTION5_RE.match(line) and (
                ("施工顺序" in line) or ("结束语" in line) or ("sequence" in line.lower())
            ):
                in_section = True
                section = _markdown_clean(line[3:]) or section_default
            continue
        if (not in_section) or (not line) or (line == "---"):
            continue

        if line.startswith("- "):
            item = _markdown_clean(line[2:])
            if not item:
                continue
            sequence_rows.append(
                {
                    "index": len(sequence_rows) + 1,
                    "item": item,
                    "source_line": idx,
                }
            )
            for raw_no in re.findall(r"Phase[\u2010-\u2015-](\d+)", item, flags=re.IGNORECASE):
                phase_no = int(raw_no)
                if phase_no in seen_phase_nos:
                    continue
                seen_phase_nos.add(phase_no)
                sequence_phase_rows.append(
                    {
                        "phase_no": phase_no,
                        "phase_label": f"Phase-{phase_no}",
                        "source_line": idx,
                    }
                )
            continue

        item = _markdown_clean(line)
        if not item:
            continue
        if not intro:
            intro = item
        if ("先闭环" in item) and (not loop_first_note):
            loop_first_note = item
            m = re.search(r"(?:即[:：])?\s*(.+?)\s*先闭环", item)
            component_blob = m.group(1).strip() if m else ""
            for raw_component in re.split(r"[、,/，]", component_blob):
                component = raw_component.strip().strip("。.;；：:")
                if (not component) or (component in seen_components):
                    continue
                seen_components.add(component)
                loop_component_rows.append(
                    {
                        "index": len(loop_component_rows) + 1,
                        "component": component,
                        "source_line": idx,
                    }
                )
        if (("自动化放在闭环之后" in item) or ("不可审计" in item)) and (not automation_note):
            automation_note = item

    sequence_phase_rows.sort(key=lambda row: int(row.get("phase_no") or 0))
    for i, row in enumerate(sequence_phase_rows, start=1):
        row["index"] = i

    return {
        "section": section,
        "intro": intro,
        "sequence_rows": sequence_rows,
        "sequence_phase_rows": sequence_phase_rows,
        "loop_first_note": loop_first_note,
        "loop_component_rows": loop_component_rows,
        "automation_note": automation_note,
    }


def _playbook_sequence_context() -> dict[str, Any]:
    playbook_path = _find_overview_doc("Implementation Phases Playbook.md")
    playbook = _extract_playbook_section5_sequence(playbook_path)
    sequence_rows = [x for x in (playbook.get("sequence_rows") or []) if isinstance(x, dict)]
    sequence_phase_rows = [x for x in (playbook.get("sequence_phase_rows") or []) if isinstance(x, dict)]
    loop_component_rows = [x for x in (playbook.get("loop_component_rows") or []) if isinstance(x, dict)]
    automation_note = str(playbook.get("automation_note") or "")

    return {
        "title": "Playbook Construction Sequence Recommendation",
        "source_files": [
            {
                "path": _repo_rel(playbook_path),
                "exists": playbook_path.is_file(),
                "section": str(playbook.get("section") or "5. 结束语（施工顺序建议）"),
            }
        ],
        "summary": {
            "sequence_item_total": len(sequence_rows),
            "sequence_phase_total": len(sequence_phase_rows),
            "loop_component_total": len(loop_component_rows),
            "automation_note_present": int(bool(automation_note)),
        },
        "playbook": playbook,
    }


def _find_overview_doc(suffix: str) -> Path:
    root = _repo_root() / "docs" / "00_overview"
    matches = sorted(p for p in root.glob(f"*{suffix}") if p.is_file())
    if matches:
        return matches[0]
    return root / suffix


def _whole_view_framework_root_doc() -> Path:
    root = _repo_root()
    matches = sorted(p for p in root.glob("*Whole View Framework.md") if p.is_file())
    if matches:
        return matches[0]
    return root / "Quant‑EAM Whole View Framework.md"


def _governance_checks_context() -> dict[str, Any]:
    ssot_path = _repo_root() / "docs" / "12_workflows" / "skeleton_ssot_v1.yaml"
    whole_view_path = _find_overview_doc("Whole View Framework.md")
    playbook_path = _find_overview_doc("Implementation Phases Playbook.md")

    ssot_doc: dict[str, Any] = {}
    if ssot_path.is_file():
        try:
            loaded = yaml.safe_load(ssot_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                ssot_doc = loaded
        except Exception:
            ssot_doc = {}

    source_docs = [str(x) for x in (ssot_doc.get("source_documents") or []) if isinstance(x, str)]
    design_principles = ssot_doc.get("design_principles") if isinstance(ssot_doc.get("design_principles"), dict) else {}
    design_rows = [
        {
            "key": str(k),
            "value": ("true" if bool(v) else "false"),
        }
        for k, v in sorted(design_principles.items(), key=lambda kv: str(kv[0]))
    ]

    goal_rows = ssot_doc.get("goal_checklist") if isinstance(ssot_doc.get("goal_checklist"), list) else []
    g32 = {}
    for row in goal_rows:
        if isinstance(row, dict) and str(row.get("id") or "") == "G32":
            g32 = row
            break

    exception_rows = (
        ssot_doc.get("autopilot_stop_condition_exceptions_v1")
        if isinstance(ssot_doc.get("autopilot_stop_condition_exceptions_v1"), list)
        else []
    )
    g32_exception = {}
    for row in exception_rows:
        if isinstance(row, dict) and str(row.get("exception_id") or "") == "g32_governance_checks_ui_scope":
            g32_exception = row
            break
    preauth = g32_exception.get("preauthorized_scope") if isinstance(g32_exception.get("preauthorized_scope"), dict) else {}

    whole_view = ssot_doc.get("whole_view_autopilot_v1") if isinstance(ssot_doc.get("whole_view_autopilot_v1"), dict) else {}
    done_criteria = whole_view.get("done_criteria") if isinstance(whole_view.get("done_criteria"), dict) else {}
    minimum_final_checks = [str(x) for x in (done_criteria.get("minimum_final_checks") or []) if isinstance(x, str)]
    ssot_enforcement_rules = [str(x) for x in (ssot_doc.get("ssot_enforcement_rules") or []) if isinstance(x, str)]

    whole_view_constraints = _extract_whole_view_constraints(whole_view_path)
    playbook_task_rules = _extract_playbook_bullets(playbook_path, "0.1")
    playbook_quality_rules = _extract_playbook_bullets(playbook_path, "0.2")

    checklist_rows: list[dict[str, str]] = []
    for row in whole_view_constraints:
        checklist_rows.append(
            {
                "source": _repo_rel(whole_view_path),
                "category": "whole_view_hard_constraint",
                "item": row.get("item") or "",
                "detail": row.get("detail") or "",
            }
        )
    for item in [str(x) for x in (preauth.get("required_guards") or []) if isinstance(x, str)]:
        checklist_rows.append(
            {
                "source": _repo_rel(ssot_path),
                "category": "ssot_required_guard",
                "item": item,
                "detail": "",
            }
        )
    for item in minimum_final_checks:
        checklist_rows.append(
            {
                "source": _repo_rel(ssot_path),
                "category": "minimum_final_check",
                "item": item,
                "detail": "",
            }
        )
    for item in playbook_task_rules:
        checklist_rows.append(
            {
                "source": _repo_rel(playbook_path),
                "category": "playbook_task_rule",
                "item": item,
                "detail": "",
            }
        )
    for item in playbook_quality_rules:
        checklist_rows.append(
            {
                "source": _repo_rel(playbook_path),
                "category": "playbook_quality_gate",
                "item": item,
                "detail": "",
            }
        )

    return {
        "title": "Whole View Governance Checks",
        "source_files": [
            {"path": _repo_rel(ssot_path), "exists": ssot_path.is_file()},
            {"path": _repo_rel(whole_view_path), "exists": whole_view_path.is_file()},
            {"path": _repo_rel(playbook_path), "exists": playbook_path.is_file()},
        ],
        "source_documents": source_docs,
        "design_principles": design_rows,
        "g32": {
            "id": str(g32.get("id") or ""),
            "title": str(g32.get("title") or ""),
            "status_now": str(g32.get("status_now") or ""),
            "depends_on": [str(x) for x in (g32.get("depends_on") or []) if isinstance(x, str)],
            "ui_path": str(g32.get("ui_path") or ""),
            "expected_state_change": str(g32.get("expected_state_change") or ""),
        },
        "g32_exception": {
            "exception_id": str(g32_exception.get("exception_id") or ""),
            "allowed_route_prefixes": [str(x) for x in (preauth.get("allowed_route_prefixes") or []) if isinstance(x, str)],
            "allowed_code_paths": [str(x) for x in (preauth.get("allowed_code_paths") or []) if isinstance(x, str)],
            "still_forbidden": [str(x) for x in (preauth.get("still_forbidden") or []) if isinstance(x, str)],
            "required_guards": [str(x) for x in (preauth.get("required_guards") or []) if isinstance(x, str)],
        },
        "whole_view_constraints": whole_view_constraints,
        "playbook_task_rules": playbook_task_rules,
        "playbook_quality_rules": playbook_quality_rules,
        "minimum_final_checks": minimum_final_checks,
        "ssot_enforcement_rules": ssot_enforcement_rules,
        "checklist_rows": checklist_rows,
    }


def _policies_constraints_context() -> dict[str, Any]:
    whole_view_path = _find_overview_doc("Whole View Framework.md")
    playbook_path = _find_overview_doc("Implementation Phases Playbook.md")
    whole_view_constraints = _extract_whole_view_constraints(whole_view_path)
    playbook_task_rules = _extract_playbook_bullets(playbook_path, "0.1")
    playbook_quality_rules = _extract_playbook_bullets(playbook_path, "0.2")

    combined_rows: list[dict[str, str]] = []
    for row in whole_view_constraints:
        combined_rows.append(
            {
                "source": _repo_rel(whole_view_path),
                "category": "whole_view_hard_constraint",
                "item": str(row.get("item") or ""),
                "detail": str(row.get("detail") or ""),
            }
        )
    for item in playbook_task_rules:
        combined_rows.append(
            {
                "source": _repo_rel(playbook_path),
                "category": "playbook_task_rule",
                "item": item,
                "detail": "section 0.1",
            }
        )
    for item in playbook_quality_rules:
        combined_rows.append(
            {
                "source": _repo_rel(playbook_path),
                "category": "playbook_quality_gate",
                "item": item,
                "detail": "section 0.2",
            }
        )

    return {
        "title": "Policies Constraints",
        "source_files": [
            {
                "path": _repo_rel(whole_view_path),
                "exists": whole_view_path.is_file(),
                "section": "1. 系统硬约束（写入 GOVERNANCE.md + CI 强制）",
            },
            {
                "path": _repo_rel(playbook_path),
                "exists": playbook_path.is_file(),
                "section": "0.1 单次 Codex 任务必须满足 / 0.2 全局质量门槛（CI 必须强制）",
            },
        ],
        "whole_view_constraints": whole_view_constraints,
        "playbook_task_rules": playbook_task_rules,
        "playbook_quality_rules": playbook_quality_rules,
        "combined_rows": combined_rows,
    }


def _hard_constraints_context() -> dict[str, Any]:
    whole_view_path = _whole_view_framework_root_doc()
    whole_view_constraints = _extract_whole_view_constraints(whole_view_path)

    return {
        "title": "Whole View Hard Constraints Governance Evidence",
        "source_files": [
            {
                "path": _repo_rel(whole_view_path),
                "exists": whole_view_path.is_file(),
                "section": "1. 系统硬约束（写入 GOVERNANCE.md + CI 强制）",
            }
        ],
        "summary": {
            "constraint_total": len(whole_view_constraints),
        },
        "whole_view_constraints": whole_view_constraints,
    }


@router.post("/workbench/sessions", status_code=201)
async def workbench_session_create(request: Request) -> Any:
    enforce_write_auth(request)
    payload = await _read_workbench_payload(request)
    session_id = _new_workbench_session_id()

    # Backward-compatible simulation mode (rollback path).
    if not _workbench_real_jobs_enabled():
        _required_workbench_fields(payload, "title", "symbols", "hypothesis_text")
        symbols = _coerce_symbol_list(payload.get("symbols"))
        if not symbols:
            raise HTTPException(status_code=422, detail="symbols must include at least one symbol")

        job_id = _workbench_job_id(session_id)
        idea = {
            "title": str(payload.get("title", "")).strip(),
            "symbols": symbols,
            "hypothesis_text": str(payload.get("hypothesis_text", "")).strip(),
            "frequency": str(payload.get("frequency", "")).strip() or "1d",
            "evaluation_intent": str(payload.get("evaluation_intent", "")).strip() or "demo_e2e",
            "start": str(payload.get("start", "")).strip(),
            "end": str(payload.get("end", "")).strip(),
            "snapshot_id": str(payload.get("snapshot_id", "")).strip(),
            "policy_bundle_path": str(payload.get("policy_bundle_path", "policies/policy_bundle_v1.yaml")).strip(),
        }
        session_doc = _initial_workbench_session(session_id=session_id, idea=idea, job_id=job_id)
        _write_workbench_session(session_id, session_doc)
        _append_workbench_event(
            session_id=session_id,
            step=WORKBENCH_PHASE_STEPS[0],
            action="session_create_requested",
            actor="user",
            source="workbench_session_create",
            payload={"mode": "simulation", "symbol_count": len(symbols), "title": idea["title"]},
        )
        event = _append_workbench_event(
            session_id=session_id,
            step=WORKBENCH_PHASE_STEPS[0],
            action="session_created",
            actor="system",
            source="workbench_session_create",
            payload={"job_id": job_id, "title": idea["title"]},
        )
        summary_lines, details, artifacts = _workbench_step_summary(session_doc, step=WORKBENCH_PHASE_STEPS[0])
        card_doc = _ensure_workbench_phase_card(
            session_id=session_id,
            session=session_doc,
            step=WORKBENCH_PHASE_STEPS[0],
            trigger_event=event,
            summary_lines=summary_lines,
            details=details,
            artifacts=artifacts,
        )
        session_doc["updated_at"] = _now_iso()
        _write_workbench_session(session_id, session_doc)

        out = {
            "session_id": session_id,
            "job_id": job_id,
            "status": "created",
            "created_at": str(session_doc.get("created_at") or ""),
            "card": _workbench_card_api_payload(card_doc),
            "api_paths": {
                "session": f"/workbench/sessions/{session_id}",
                "events": f"/workbench/sessions/{session_id}/events",
                "ui": f"/ui/workbench/{session_id}",
            },
        }
        if str(payload.get("_ui", "")).strip() in {"1", "true", "yes"}:
            return RedirectResponse(url=f"/ui/workbench/{session_id}", status_code=303)
        return out

    # Real jobs path: message-only intake -> fetch autosymbols -> idea job -> append-only fetch evidence.
    intake_bundle, message = _run_workbench_ui_intake_agent(session_id=session_id, payload=payload)
    normalized = intake_bundle.get("normalized_request") if isinstance(intake_bundle.get("normalized_request"), dict) else {}
    fetch_request = intake_bundle.get("fetch_request") if isinstance(intake_bundle.get("fetch_request"), dict) else None
    if not isinstance(fetch_request, dict):
        raise HTTPException(status_code=422, detail="ui intake bundle missing fetch_request")
    if _contains_forbidden_fetch_function_fields(fetch_request):
        raise HTTPException(status_code=422, detail="fetch_request must be intent-first (no function/function_override)")

    snapshot_id = str(payload.get("snapshot_id") or os.getenv("EAM_DEFAULT_SNAPSHOT_ID") or "").strip()
    if not snapshot_id:
        raise HTTPException(status_code=422, detail="snapshot_id is required (payload or EAM_DEFAULT_SNAPSHOT_ID)")
    policy_bundle_path = str(
        payload.get("policy_bundle_path") or os.getenv("EAM_DEFAULT_POLICY_BUNDLE_PATH") or "policies/policy_bundle_v1.yaml"
    ).strip()

    from quant_eam.qa_fetch.runtime import execute_fetch_by_intent, execute_ui_llm_query

    sampled_symbols = _coerce_symbol_list(payload.get("symbols"))
    if not sampled_symbols:
        try:
            probe_res = execute_fetch_by_intent(fetch_request, write_evidence=False, _allow_evidence_opt_out=True)
            sampled_symbols = _extract_symbols_from_fetch_result(probe_res)
        except Exception:
            sampled_symbols = []
    if not sampled_symbols:
        sampled_symbols = ["AAA"]

    idea_start = _coerce_workbench_date_text(
        payload.get("start") or normalized.get("start"),
        default="2016-01-01",
    )
    idea_end = _coerce_workbench_date_text(
        payload.get("end") or normalized.get("end"),
        default="2025-12-31",
    )
    idea_title = str(normalized.get("title") or payload.get("title") or "").strip() or f"Workbench session {session_id}"
    idea_hypothesis = str(normalized.get("hypothesis_text") or message).strip() or message
    idea: dict[str, Any] = {
        "schema_version": "idea_spec_v1",
        "title": idea_title,
        "symbols": sampled_symbols,
        "hypothesis_text": idea_hypothesis,
        "frequency": _normalize_idea_frequency(normalized.get("frequency") or payload.get("frequency")),
        "evaluation_intent": str(payload.get("evaluation_intent") or "workbench_ma250_one_shot").strip() or "workbench_ma250_one_shot",
        "start": idea_start,
        "end": idea_end,
        "snapshot_id": snapshot_id,
        "policy_bundle_path": policy_bundle_path,
        "extensions": {
            "strategy_template": str(intake_bundle.get("strategy_template") or "ma250_trend_filter_v1"),
            "fetch_request": fetch_request,
            "workbench_message": message,
        },
    }
    universe_hint = str(normalized.get("universe_hint") or "").strip()
    if universe_hint:
        idea["universe_hint"] = universe_hint

    try:
        create_res = create_job_from_ideaspec(
            idea_spec=idea,
            snapshot_id=snapshot_id,
            policy_bundle_path=policy_bundle_path,
            job_root=default_job_root(),
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))

    job_id = str(create_res.get("job_id") or "").strip()
    if not job_id:
        raise HTTPException(status_code=500, detail="failed to create idea job")

    fetch_query_result: dict[str, Any] = {}
    fetch_evidence_paths: dict[str, Any] = {}
    fetch_review_checkpoint: dict[str, Any] = {}
    fetch_preview_rows: list[dict[str, Any]] = []
    fetch_probe_status = "idle"
    fetch_probe_error = ""
    try:
        fetch_query_result = execute_ui_llm_query(
            {
                "query_id": f"workbench_{session_id}_create",
                "query_text": message,
                "fetch_request": fetch_request,
            },
            out_dir=_workbench_fetch_evidence_root_for_job(job_id),
        )
        if isinstance(fetch_query_result.get("fetch_evidence_paths"), dict):
            fetch_evidence_paths = fetch_query_result["fetch_evidence_paths"]
        if isinstance(fetch_query_result.get("fetch_review_checkpoint"), dict):
            fetch_review_checkpoint = fetch_query_result["fetch_review_checkpoint"]
        query_result = fetch_query_result.get("query_result")
        if isinstance(query_result, dict) and isinstance(query_result.get("preview"), list):
            fetch_preview_rows = [row for row in query_result["preview"] if isinstance(row, dict)][:20]
        fetch_probe_status = "ok"
    except Exception as e:  # noqa: BLE001
        fetch_probe_status = "error"
        fetch_probe_error = str(e)
        err_path = _workbench_fetch_evidence_root_for_job(job_id) / "ui_intake_fetch_error.json"
        _write_json(
            err_path,
            {
                "schema_version": "workbench_ui_intake_fetch_error_v1",
                "job_id": job_id,
                "session_id": session_id,
                "message": str(e),
            },
        )

    session_doc = _initial_workbench_session(session_id=session_id, idea=idea, job_id=job_id)
    session_doc["message"] = message
    session_doc["sampled_symbols"] = sampled_symbols
    session_doc["ui_intake_bundle"] = intake_bundle
    session_doc["fetch_request"] = fetch_request
    session_doc["fetch_evidence_paths"] = fetch_evidence_paths
    session_doc["fetch_review_checkpoint"] = fetch_review_checkpoint
    session_doc["fetch_probe_preview_rows"] = fetch_preview_rows
    session_doc["fetch_probe_status"] = fetch_probe_status
    session_doc["fetch_probe_error"] = fetch_probe_error
    if isinstance(fetch_evidence_paths.get("fetch_result_meta_path"), str):
        session_doc["last_fetch_probe"] = str(fetch_evidence_paths.get("fetch_result_meta_path"))
    _write_workbench_session(session_id, session_doc)
    _append_workbench_event(
        session_id=session_id,
        step=WORKBENCH_PHASE_STEPS[0],
        action="session_create_requested",
        actor="user",
        source="workbench_session_create",
        payload={"mode": "real_jobs", "message": message, "sample_n": _coerce_workbench_sample_n(payload.get("sample_n"), default=50)},
    )

    event = _append_workbench_event(
        session_id=session_id,
        step=WORKBENCH_PHASE_STEPS[0],
        action="session_created_real_job",
        actor="system",
        source="workbench_session_create",
        status="ok" if fetch_probe_status == "ok" else "degraded",
        payload={
            "job_id": job_id,
            "title": idea_title,
            "sampled_symbol_count": len(sampled_symbols),
            "sampled_symbols_preview": sampled_symbols[:20],
        },
    )
    summary_lines, details, artifacts = _workbench_step_summary(session_doc, step=WORKBENCH_PHASE_STEPS[0])
    details = dict(details)
    details["message"] = message
    details["normalized_request"] = normalized
    details["fetch_evidence_paths"] = fetch_evidence_paths
    if fetch_preview_rows:
        details["fetch_preview_rows"] = fetch_preview_rows
    artifact_rows = [str(x).strip() for x in artifacts if str(x).strip()]
    artifact_rows.extend(str(v).strip() for v in fetch_evidence_paths.values() if isinstance(v, str) and str(v).strip())
    card_doc = _ensure_workbench_phase_card(
        session_id=session_id,
        session=session_doc,
        step=WORKBENCH_PHASE_STEPS[0],
        trigger_event=event,
        summary_lines=summary_lines,
        details=details,
        artifacts=artifact_rows,
    )
    session_doc["updated_at"] = _now_iso()
    _write_workbench_session(session_id, session_doc)

    out = {
        "session_id": session_id,
        "job_id": job_id,
        "status": "created",
        "created_at": str(session_doc.get("created_at") or ""),
        "card": _workbench_card_api_payload(card_doc),
        "sampled_symbols": sampled_symbols,
        "fetch_evidence_paths": fetch_evidence_paths,
        "api_paths": {
            "session": f"/workbench/sessions/{session_id}",
            "events": f"/workbench/sessions/{session_id}/events",
            "ui": f"/ui/workbench/{session_id}",
        },
    }
    if str(payload.get("_ui", "")).strip() in {"1", "true", "yes"}:
        return RedirectResponse(url=f"/ui/workbench/{session_id}", status_code=303)
    return out


@router.get("/workbench/sessions/{session_id}")
def workbench_session_get(session_id: str) -> Any:
    session_id = require_safe_id(session_id, kind="session_id")
    payload = _load_workbench_session(session_id)
    events = _read_workbench_events(session_id)
    cards = _workbench_cards_for_view(payload)
    return {
        "session": payload,
        "cards": cards,
        "cards_count": len(cards),
        "event_count": len(events),
        "events": events[-30:],
    }


@router.post("/workbench/sessions/{session_id}/message")
async def workbench_session_message(session_id: str, request: Request) -> Any:
    enforce_write_auth(request)
    session_id = require_safe_id(session_id, kind="session_id")
    payload = await _read_workbench_payload(request)
    message = str(payload.get("message", "")).strip()
    if not message:
        raise HTTPException(status_code=422, detail="message is required")

    session = _load_workbench_session(session_id)
    messages = session.get("messages")
    if not isinstance(messages, list):
        messages = []
        session["messages"] = messages
    step = str(payload.get("step", "")).strip() or str(session.get("current_step") or WORKBENCH_PHASE_STEPS[0])
    msg_item = {"created_at": _now_iso(), "step": step, "text": message}
    messages.append(msg_item)
    _bump_workbench_revision(session)
    session["updated_at"] = _now_iso()
    ev = _append_workbench_event(
        session_id=session_id,
        step=step,
        action="message_appended",
        actor="user",
        source="workbench_session_message",
        payload={"text": message},
    )
    _write_workbench_session(session_id, session)
    if str(payload.get("_ui", "")).strip() in {"1", "true", "yes"}:
        return RedirectResponse(url=f"/ui/workbench/{session_id}", status_code=303)
    return {"session_id": session_id, "message_count": len(messages), "latest_message": msg_item, "event": ev}


@router.post("/workbench/sessions/{session_id}/continue")
async def workbench_session_continue(session_id: str, request: Request) -> Any:
    enforce_write_auth(request)
    session_id = require_safe_id(session_id, kind="session_id")
    payload = await _read_workbench_payload(request)
    session = _load_workbench_session(session_id)
    current_step = str(session.get("current_step") or WORKBENCH_PHASE_STEPS[0])
    if current_step not in WORKBENCH_PHASE_STEPS:
        raise HTTPException(status_code=409, detail="invalid session step")
    requested = str(payload.get("target_step", "")).strip()
    if requested and requested not in WORKBENCH_PHASE_STEPS:
        raise HTTPException(status_code=422, detail="invalid target_step")

    if _workbench_real_jobs_enabled():
        job_id = str(session.get("job_id") or "").strip()
        if not job_id:
            raise HTTPException(status_code=409, detail="workbench session missing job_id")
        try:
            require_safe_job_id(job_id)
        except HTTPException:
            raise HTTPException(status_code=409, detail="workbench session job_id is not a real job id")
        if requested and requested != current_step:
            raise HTTPException(status_code=409, detail="target_step must match current_step in real jobs mode")

        from quant_eam.orchestrator.workflow import advance_job_once
        _append_workbench_event(
            session_id=session_id,
            step=current_step,
            action="continue_requested",
            actor="user",
            source="workbench_session_continue",
            payload={"target_step": requested or current_step},
        )

        before_events = jobs_load_events(job_id, job_root=default_job_root())
        waiting_step = _latest_job_waiting_step(before_events)
        approved_step: str | None = None
        if waiting_step and waiting_step in APPROVAL_STEPS and not _job_has_approved_step(before_events, step=waiting_step):
            jobs_append_event(
                job_id=job_id,
                event_type="APPROVED",
                outputs={"step": waiting_step},
                job_root=default_job_root(),
            )
            approved_step = waiting_step
            _append_workbench_event(
                session_id=session_id,
                step=current_step,
                action="checkpoint_auto_approved",
                actor="system",
                source="workbench_session_continue",
                payload={"job_id": job_id, "checkpoint": waiting_step},
            )

        advance_result = advance_job_once(job_id=job_id)
        after_events = jobs_load_events(job_id, job_root=default_job_root())
        checkpoint = _job_checkpoint_from_events(after_events)
        phase_step = _workbench_real_phase_for_checkpoint(checkpoint)

        prev_step = current_step
        prev_idx = WORKBENCH_PHASE_STEPS.index(prev_step) if prev_step in WORKBENCH_PHASE_STEPS else 0
        phase_idx = WORKBENCH_PHASE_STEPS.index(phase_step) if phase_step in WORKBENCH_PHASE_STEPS else 0
        if phase_idx < prev_idx:
            phase_step = prev_step
            phase_idx = prev_idx
        transitioned = phase_step != prev_step

        trace = session.get("trace")
        if not isinstance(trace, list):
            trace = []
            session["trace"] = trace
        if transitioned:
            for idx in range(len(trace) - 1, -1, -1):
                row = trace[idx]
                if not isinstance(row, dict):
                    continue
                if str(row.get("step") or "") == prev_step:
                    row["status"] = "completed"
                    row["status_text"] = f"continued_to_{phase_step}"
                    row["updated_at"] = _now_iso()
                    break
            trace.append({"step": phase_step, "status": "in_progress", "status_text": "job_checkpoint_advanced", "created_at": _now_iso()})

        outputs_index = _load_job_outputs_index(job_id)
        artifact_refs = [str(v).strip() for v in outputs_index.values() if isinstance(v, str) and str(v).strip()]

        session["current_step"] = phase_step
        session["step_index"] = phase_idx
        session["job_checkpoint"] = checkpoint
        session["job_advance_result"] = advance_result
        session["job_outputs_ref"] = outputs_index
        session["updated_at"] = _now_iso()
        if checkpoint in {"done", "improvements"} or str(advance_result.get("state") or "").upper() == "DONE":
            session["status"] = "completed"
            if trace and isinstance(trace[-1], dict):
                trace[-1]["status"] = "completed"
                trace[-1]["status_text"] = "job_done"
                trace[-1]["updated_at"] = _now_iso()

        _bump_workbench_revision(session)
        event = _append_workbench_event(
            session_id=session_id,
            step=phase_step,
            action="real_job_continued",
            actor="system",
            source="workbench_session_continue",
            payload={
                "job_id": job_id,
                "checkpoint": checkpoint,
                "approved_step": approved_step,
                "previous_step": prev_step,
                "current_step": phase_step,
                "event_count_before": len(before_events),
                "event_count_after": len(after_events),
            },
        )
        summary_lines, details, artifacts = _workbench_step_summary(session, step=phase_step)
        details = dict(details)
        details["job_checkpoint"] = checkpoint
        details["approved_step"] = approved_step
        details["job_outputs_ref"] = outputs_index
        details["job_advance_result"] = advance_result
        artifacts = [*artifacts, *artifact_refs]
        card_doc = _ensure_workbench_phase_card(
            session_id=session_id,
            session=session,
            step=phase_step,
            trigger_event=event,
            summary_lines=summary_lines,
            details=details,
            artifacts=artifacts,
        )
        _write_workbench_session(session_id, session)

        idempotent = (len(after_events) == len(before_events)) and (approved_step is None) and (not transitioned)
        out = {
            "session_id": session_id,
            "job_id": job_id,
            "previous_step": prev_step,
            "current_step": phase_step,
            "checkpoint": checkpoint,
            "status": str(session.get("status") or "active"),
            "idempotent": bool(idempotent),
            "approved_step": approved_step,
            "artifact_refs": artifact_refs,
            "card": _workbench_card_api_payload(card_doc),
        }
        if str(payload.get("_ui", "")).strip() in {"1", "true", "yes"}:
            return RedirectResponse(url=f"/ui/workbench/{session_id}", status_code=303)
        return out

    _append_workbench_event(
        session_id=session_id,
        step=current_step,
        action="continue_requested",
        actor="user",
        source="workbench_session_continue",
        payload={"target_step": requested or "auto_next"},
    )
    current_idx = WORKBENCH_PHASE_STEPS.index(current_step)
    if requested:
        requested = requested.strip()
        req_idx = WORKBENCH_PHASE_STEPS.index(requested)
        if req_idx not in (current_idx, current_idx + 1):
            raise HTTPException(status_code=409, detail="target_step must be current step or immediate next step")
        next_step = requested
    else:
        next_step = WORKBENCH_PHASE_STEPS[min(current_idx + 1, len(WORKBENCH_PHASE_STEPS) - 1)]
    transitioned = next_step != current_step

    trace = session.get("trace")
    if not isinstance(trace, list):
        trace = []
        session["trace"] = trace
    if transitioned:
        for idx in range(len(trace) - 1, -1, -1):
            row = trace[idx]
            if not isinstance(row, dict):
                continue
            if str(row.get("step") or "") == current_step:
                row["status"] = "completed"
                row["status_text"] = f"continued_to_{next_step}"
                row["updated_at"] = _now_iso()
                break
        trace.append({"step": next_step, "status": "in_progress", "status_text": "user_continue_invoked", "created_at": _now_iso()})

    session["current_step"] = next_step
    session["step_index"] = WORKBENCH_PHASE_STEPS.index(next_step)
    _bump_workbench_revision(session)
    session["updated_at"] = _now_iso()
    if next_step == WORKBENCH_PHASE_STEPS[-1]:
        session["status"] = "completed"
        if transitioned and trace and isinstance(trace[-1], dict):
            trace[-1]["status"] = "completed"
            trace[-1]["status_text"] = "final_phase_reached"
            trace[-1]["updated_at"] = _now_iso()

    ev = _append_workbench_event(
        session_id=session_id,
        step=next_step,
        action="step_continued" if transitioned else "step_refreshed",
        actor="system",
        source="workbench_session_continue",
        payload={"target_step": next_step, "previous_step": current_step},
    )
    summary_lines, details, artifacts = _workbench_step_summary(session, step=next_step)
    card_doc = _ensure_workbench_phase_card(
        session_id=session_id,
        session=session,
        step=next_step,
        trigger_event=ev,
        summary_lines=summary_lines,
        details=details,
        artifacts=artifacts,
    )
    _write_workbench_session(session_id, session)

    out = {
        "session_id": session_id,
        "previous_step": current_step,
        "current_step": next_step,
        "status": str(session.get("status") or "active"),
        "idempotent": not transitioned,
        "card": _workbench_card_api_payload(card_doc),
    }
    if str(payload.get("_ui", "")).strip() in {"1", "true", "yes"}:
        return RedirectResponse(url=f"/ui/workbench/{session_id}", status_code=303)
    return out


@router.get("/workbench/sessions/{session_id}/events")
def workbench_session_events(session_id: str, limit: int | None = None) -> Any:
    session_id = require_safe_id(session_id, kind="session_id")
    session = _load_workbench_session(session_id)
    events = _read_workbench_events(session_id)
    if limit and limit > 0:
        events = events[-limit:]
    return {"session_id": session_id, "events": events, "event_count": len(events)}


@router.post("/workbench/sessions/{session_id}/fetch-probe")
async def workbench_session_fetch_probe(session_id: str, request: Request) -> Any:
    enforce_write_auth(request)
    session_id = require_safe_id(session_id, kind="session_id")
    payload = await _read_workbench_payload(request)
    session = _load_workbench_session(session_id)
    symbols_from_payload = _coerce_symbol_list(payload.get("symbols"))
    request_step = str(session.get("current_step") or WORKBENCH_PHASE_STEPS[0])
    _append_workbench_event(
        session_id=session_id,
        step=request_step,
        action="fetch_probe_requested",
        actor="user",
        source="workbench_session_fetch_probe",
        payload={"symbol_count": len(symbols_from_payload)},
    )

    if _workbench_real_jobs_enabled():
        job_id = str(session.get("job_id") or "").strip()
        if not job_id:
            raise HTTPException(status_code=409, detail="workbench session missing job_id")
        try:
            require_safe_job_id(job_id)
        except HTTPException:
            raise HTTPException(status_code=409, detail="workbench session job_id is not a real job id")

        fetch_request = payload.get("fetch_request")
        if not isinstance(fetch_request, dict):
            fetch_request = session.get("fetch_request")
        if not isinstance(fetch_request, dict):
            intake_bundle = session.get("ui_intake_bundle")
            if isinstance(intake_bundle, dict) and isinstance(intake_bundle.get("fetch_request"), dict):
                fetch_request = intake_bundle.get("fetch_request")
        if not isinstance(fetch_request, dict):
            raise HTTPException(status_code=422, detail="fetch_request is required for fetch-probe")
        if _contains_forbidden_fetch_function_fields(fetch_request):
            raise HTTPException(status_code=422, detail="fetch_request must be intent-first (no function/function_override)")

        symbols = symbols_from_payload
        if symbols:
            req_copy = json.loads(json.dumps(fetch_request))
            intent = req_copy.get("intent") if isinstance(req_copy.get("intent"), dict) else {}
            req_copy["intent"] = intent
            intent["symbols"] = symbols
            intent["auto_symbols"] = False
            req_copy["auto_symbols"] = False
            fetch_request = req_copy

        session["fetch_probe_status"] = "running"
        session["fetch_probe_error"] = ""
        _bump_workbench_revision(session)
        session["updated_at"] = _now_iso()
        _write_workbench_session(session_id, session)

        from quant_eam.qa_fetch.runtime import execute_ui_llm_query

        try:
            query_result = execute_ui_llm_query(
                {
                    "query_id": f"workbench_{session_id}_fetch_probe",
                    "query_text": str(session.get("message") or ""),
                    "fetch_request": fetch_request,
                },
                out_dir=_workbench_fetch_evidence_root_for_job(job_id),
            )
        except Exception as e:  # noqa: BLE001
            session["fetch_probe_status"] = "error"
            session["fetch_probe_error"] = str(e)
            session["fetch_probe_preview_rows"] = []
            _bump_workbench_revision(session)
            session["updated_at"] = _now_iso()
            ev = _append_workbench_event(
                session_id=session_id,
                step="trace_preview",
                action="fetch_probe_failed",
                actor="system",
                source="workbench_session_fetch_probe",
                status="error",
                payload={"job_id": job_id, "error": str(e)},
            )
            _write_workbench_session(session_id, session)
            out = {
                "session_id": session_id,
                "job_id": job_id,
                "status": "error",
                "error": str(e),
                "event_id": str(ev.get("event_id") or ""),
            }
            if str(payload.get("_ui", "")).strip() in {"1", "true", "yes"}:
                return RedirectResponse(url=f"/ui/workbench/{session_id}", status_code=303)
            return out

        fetch_evidence_paths = query_result.get("fetch_evidence_paths") if isinstance(query_result.get("fetch_evidence_paths"), dict) else {}
        fetch_review_checkpoint = (
            query_result.get("fetch_review_checkpoint") if isinstance(query_result.get("fetch_review_checkpoint"), dict) else {}
        )
        query_doc = query_result.get("query_result") if isinstance(query_result.get("query_result"), dict) else {}
        sample_rows = query_doc.get("preview") if isinstance(query_doc.get("preview"), list) else []
        sample_rows = [row for row in sample_rows if isinstance(row, dict)][:20]

        session["fetch_request"] = fetch_request
        session["fetch_evidence_paths"] = fetch_evidence_paths
        session["fetch_review_checkpoint"] = fetch_review_checkpoint
        session["fetch_probe_preview_rows"] = sample_rows
        session["fetch_probe_status"] = "ok"
        session["fetch_probe_error"] = ""
        if isinstance(fetch_evidence_paths.get("fetch_result_meta_path"), str):
            session["last_fetch_probe"] = str(fetch_evidence_paths.get("fetch_result_meta_path"))
        _bump_workbench_revision(session)
        session["updated_at"] = _now_iso()
        ev = _append_workbench_event(
            session_id=session_id,
            step="trace_preview",
            action="fetch_probe_real",
            actor="system",
            source="workbench_session_fetch_probe",
            status="ok",
            payload={"job_id": job_id, "fetch_evidence_paths": fetch_evidence_paths},
        )
        summary_lines, details, artifacts = _workbench_step_summary(session, step="trace_preview")
        details = dict(details)
        details["fetch_evidence_paths"] = fetch_evidence_paths
        details["fetch_review_checkpoint"] = fetch_review_checkpoint
        if sample_rows:
            details["sample_rows"] = sample_rows
        artifacts = [*artifacts, *[str(v) for v in fetch_evidence_paths.values() if isinstance(v, str)]]
        card_doc = _ensure_workbench_phase_card(
            session_id=session_id,
            session=session,
            step="trace_preview",
            trigger_event=ev,
            summary_lines=summary_lines,
            details=details,
            artifacts=artifacts,
            force_new=True,
        )
        _write_workbench_session(session_id, session)

        out = {
            "session_id": session_id,
            "job_id": job_id,
            "status": "ok",
            "fetch_evidence_paths": fetch_evidence_paths,
            "fetch_review_checkpoint": fetch_review_checkpoint,
            "probe_rows": sample_rows,
            "card": _workbench_card_api_payload(card_doc),
        }
        if str(payload.get("_ui", "")).strip() in {"1", "true", "yes"}:
            return RedirectResponse(url=f"/ui/workbench/{session_id}", status_code=303)
        return out

    symbols = symbols_from_payload
    if not symbols:
        idea = session.get("idea")
        idea_doc = idea if isinstance(idea, dict) else {}
        symbols = _coerce_symbol_list(idea_doc.get("symbols"))
    if not symbols:
        symbols = ["BTCUSDT"]

    session["fetch_probe_status"] = "running"
    session["fetch_probe_error"] = ""
    _bump_workbench_revision(session)
    session["updated_at"] = _now_iso()
    _write_workbench_session(session_id, session)

    sample_rows = [{"symbol": symbols[0], "sample": 100.0, "window": "demo"}, {"symbol": symbols[0], "sample": 101.2, "window": "demo"}]
    probe = {
        "schema_version": "workbench_fetch_probe_v1",
        "session_id": session_id,
        "status": "ok",
        "symbols": symbols,
        "probe_at": _now_iso(),
        "sample_rows": sample_rows,
    }
    probe_path = _workbench_cards_root(session_id) / "fetch_probe.json"
    _write_json(probe_path, probe)

    session["last_fetch_probe"] = probe_path.as_posix()
    session["fetch_probe_preview_rows"] = sample_rows
    session["fetch_probe_status"] = "ok"
    session["fetch_probe_error"] = ""
    _bump_workbench_revision(session)
    session["updated_at"] = _now_iso()
    ev = _append_workbench_event(
        session_id=session_id,
        step="trace_preview",
        action="fetch_probe",
        actor="system",
        source="workbench_session_fetch_probe",
        status="ok",
        payload={"probe_path": probe_path.as_posix()},
    )
    summary_lines, details, artifacts = _workbench_step_summary(session, step="trace_preview")
    if sample_rows:
        details = dict(details)
        details["sample_rows"] = sample_rows
    artifacts = [*artifacts, probe_path.as_posix()]
    card_doc = _ensure_workbench_phase_card(
        session_id=session_id,
        session=session,
        step="trace_preview",
        trigger_event=ev,
        summary_lines=summary_lines,
        details=details,
        artifacts=artifacts,
        force_new=True,
    )
    _write_workbench_session(session_id, session)

    out = {
        "session_id": session_id,
        "status": "ok",
        "artifact_path": probe_path.as_posix(),
        "probe_rows": sample_rows,
        "card": _workbench_card_api_payload(card_doc),
    }
    if str(payload.get("_ui", "")).strip() in {"1", "true", "yes"}:
        return RedirectResponse(url=f"/ui/workbench/{session_id}", status_code=303)
    return out


@router.post("/workbench/sessions/{session_id}/steps/{step}/drafts")
async def workbench_session_save_draft(session_id: str, step: str, request: Request) -> Any:
    enforce_write_auth(request)
    session_id = require_safe_id(session_id, kind="session_id")
    step = require_safe_id(step, kind="workbench_step")
    payload = await _read_workbench_payload(request)
    draft_content = payload.get("content", "")
    if draft_content == "":
        draft_content = payload

    session = _load_workbench_session(session_id)
    draft_dir = _workbench_step_drafts_root(session_id, step)
    version_list = []
    if draft_dir.is_dir():
        for p in draft_dir.iterdir():
            if not p.is_file():
                continue
            m = WORKBENCH_DRAFT_VERSION_RE.match(p.name)
            if m:
                version_list.append(int(m.group(1)))
    next_version = max(version_list, default=0) + 1
    draft_path = draft_dir / f"draft_v{next_version}.json"

    draft_record = {
        "schema_version": "workbench_step_draft_v1",
        "session_id": session_id,
        "step": step,
        "version": next_version,
        "created_at": _now_iso(),
        "content": draft_content,
    }
    _write_json(draft_path, draft_record)
    _bump_workbench_revision(session)
    session["updated_at"] = _now_iso()
    _write_workbench_session(session_id, session)
    _append_workbench_event(
        session_id=session_id,
        step=step,
        action="draft_saved",
        actor="user",
        source="workbench_session_save_draft",
        payload={"version": next_version, "draft_path": draft_path.as_posix()},
    )
    return {"session_id": session_id, "step": step, "draft_version": next_version, "artifact_path": draft_path.as_posix()}


@router.post("/workbench/sessions/{session_id}/steps/{step}/drafts/{version}/apply")
async def workbench_session_apply_draft(session_id: str, step: str, version: str, request: Request) -> Any:
    enforce_write_auth(request)
    session_id = require_safe_id(session_id, kind="session_id")
    step = require_safe_id(step, kind="workbench_step")
    _ = await _read_workbench_payload(request)
    draft_no = int(version) if version.isdigit() else None
    if draft_no is None or draft_no < 1:
        raise HTTPException(status_code=422, detail="version must be a positive integer")

    draft_path = _workbench_step_drafts_root(session_id, step) / f"draft_v{draft_no}.json"
    if not draft_path.is_file():
        raise HTTPException(status_code=404, detail="draft not found")
    session = _load_workbench_session(session_id)
    drafts = session.get("drafts")
    if not isinstance(drafts, dict):
        drafts = {}
        session["drafts"] = drafts

    step_drafts = drafts.get(step)
    if not isinstance(step_drafts, dict):
        step_drafts = {}
    step_drafts["selected"] = draft_no
    step_drafts["path"] = draft_path.as_posix()
    drafts[step] = step_drafts
    session["drafts"] = drafts
    selected_path = _workbench_step_drafts_root(session_id, step) / "selected.json"
    _write_json(
        selected_path,
        {
            "schema_version": "workbench_step_selected_v1",
            "session_id": session_id,
            "step": step,
            "selected_version": draft_no,
            "selected_path": draft_path.as_posix(),
            "selected_at": _now_iso(),
        },
    )
    _bump_workbench_revision(session)
    session["updated_at"] = _now_iso()
    _write_workbench_session(session_id, session)
    _append_workbench_event(
        session_id=session_id,
        step=step,
        action="draft_applied",
        actor="user",
        source="workbench_session_apply_draft",
        payload={"version": draft_no, "selected_path": selected_path.as_posix()},
    )

    return {
        "session_id": session_id,
        "step": step,
        "selected_draft_version": draft_no,
        "path": draft_path.as_posix(),
        "selected_index_path": selected_path.as_posix(),
    }


@router.api_route("/ui/workbench", methods=["GET", "HEAD"], response_class=HTMLResponse)
def ui_workbench(request: Request) -> HTMLResponse:
    ctx = _workbench_index_context()
    return TEMPLATES.TemplateResponse(request, "workbench.html", ctx)


@router.api_route("/ui/workbench/req/wb-002", methods=["GET", "HEAD"], response_class=HTMLResponse)
def ui_workbench_req_wb002(request: Request) -> HTMLResponse:
    # Stable requirement-bound entry path used by SSOT ui_path for G350.
    return ui_workbench(request)


@router.api_route("/ui/workbench/{session_id}", methods=["GET", "HEAD"], response_class=HTMLResponse)
def ui_workbench_session(request: Request, session_id: str) -> HTMLResponse:
    sid = require_safe_id(session_id, kind="session_id")
    ctx = _workbench_index_context()
    ctx["selected_session"] = _workbench_session_context(sid)
    return TEMPLATES.TemplateResponse(request, "workbench.html", ctx)


@router.api_route("/ui", methods=["GET", "HEAD"], response_class=HTMLResponse)
def ui_index(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(request, "index.html", _ui_index_context())


@router.api_route("/ui/qa-fetch", methods=["GET", "HEAD"], response_class=HTMLResponse)
def ui_qa_fetch(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(request, "qa_fetch.html", _qa_fetch_evidence_context())


@router.api_route("/ui/governance-checks", methods=["GET", "HEAD"], response_class=HTMLResponse)
def ui_governance_checks(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(request, "governance_checks.html", _governance_checks_context())


@router.api_route("/ui/policies-constraints", methods=["GET", "HEAD"], response_class=HTMLResponse)
def ui_policies_constraints(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(request, "policies_constraints.html", _policies_constraints_context())


@router.api_route("/ui/hard-constraints", methods=["GET", "HEAD"], response_class=HTMLResponse)
def ui_hard_constraints(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(request, "hard_constraints.html", _hard_constraints_context())


@router.api_route("/ui/contracts-coverage", methods=["GET", "HEAD"], response_class=HTMLResponse)
def ui_contracts_coverage(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(request, "contracts_coverage.html", _contracts_coverage_context())


@router.api_route("/ui/contracts-principles", methods=["GET", "HEAD"], response_class=HTMLResponse)
def ui_contracts_principles(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(request, "contracts_principles.html", _contracts_principles_context())


@router.api_route("/ui/dossier-evidence", methods=["GET", "HEAD"], response_class=HTMLResponse)
def ui_dossier_evidence(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(request, "dossier_evidence.html", _dossier_evidence_context())


@router.api_route("/ui/playbook-principles", methods=["GET", "HEAD"], response_class=HTMLResponse)
def ui_playbook_principles(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(request, "playbook_principles.html", _playbook_principles_context())


@router.api_route("/ui/playbook-tech-stack", methods=["GET", "HEAD"], response_class=HTMLResponse)
def ui_playbook_tech_stack(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(request, "playbook_tech_stack.html", _playbook_tech_stack_context())


@router.api_route("/ui/playbook-phase-template", methods=["GET", "HEAD"], response_class=HTMLResponse)
def ui_playbook_phase_template(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(request, "playbook_phase_template.html", _playbook_phase_template_context())


@router.api_route("/ui/playbook-codex-task-card", methods=["GET", "HEAD"], response_class=HTMLResponse)
def ui_playbook_codex_task_card(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(request, "playbook_codex_task_card.html", _playbook_codex_task_card_context())


@router.api_route("/ui/playbook-sequence", methods=["GET", "HEAD"], response_class=HTMLResponse)
def ui_playbook_sequence(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(request, "playbook_sequence.html", _playbook_sequence_context())


@router.api_route("/ui/playbook-phases", methods=["GET", "HEAD"], response_class=HTMLResponse)
def ui_playbook_phases(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(request, "playbook_phases.html", _playbook_phases_context())


@router.api_route("/ui/ia-coverage", methods=["GET", "HEAD"], response_class=HTMLResponse)
def ui_ia_coverage(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(request, "ia_coverage.html", _ia_coverage_context())


@router.api_route("/ui/agent-roles", methods=["GET", "HEAD"], response_class=HTMLResponse)
def ui_agent_roles(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(request, "agent_roles.html", _agent_roles_context())


@router.api_route("/ui/workflow-checkpoints", methods=["GET", "HEAD"], response_class=HTMLResponse)
def ui_workflow_checkpoints(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(request, "workflow_checkpoints.html", _workflow_checkpoints_context())


@router.api_route("/ui/object-model", methods=["GET", "HEAD"], response_class=HTMLResponse)
def ui_object_model(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(request, "object_model.html", _object_model_context())


@router.api_route("/ui/module-boundaries", methods=["GET", "HEAD"], response_class=HTMLResponse)
def ui_module_boundaries(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(request, "module_boundaries.html", _module_boundaries_context())


@router.api_route("/ui/diagnostics-promotion", methods=["GET", "HEAD"], response_class=HTMLResponse)
def ui_diagnostics_promotion(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(request, "diagnostics_promotion.html", _diagnostics_promotion_context())


@router.api_route("/ui/codex-role-boundary", methods=["GET", "HEAD"], response_class=HTMLResponse)
def ui_codex_role_boundary(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(request, "codex_role_boundary.html", _codex_role_boundary_context())


@router.api_route("/ui/ui-coverage-matrix", methods=["GET", "HEAD"], response_class=HTMLResponse)
def ui_ui_coverage_matrix(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(request, "ui_coverage_matrix.html", _ui_coverage_matrix_context())


@router.api_route("/ui/runtime-topology", methods=["GET", "HEAD"], response_class=HTMLResponse)
def ui_runtime_topology(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(request, "runtime_topology.html", _runtime_topology_context())


@router.api_route("/ui/preflight-checklist", methods=["GET", "HEAD"], response_class=HTMLResponse)
def ui_preflight_checklist(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(request, "preflight_checklist.html", _preflight_checklist_context())


@router.api_route("/ui/version-roadmap", methods=["GET", "HEAD"], response_class=HTMLResponse)
def ui_version_roadmap(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(request, "version_roadmap.html", _version_roadmap_context())


@router.api_route("/ui/system-definition", methods=["GET", "HEAD"], response_class=HTMLResponse)
def ui_system_definition(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(request, "system_definition.html", _system_definition_context())


def _composer_policy_bundle_default() -> str:
    return str(os.getenv("EAM_COMPOSER_POLICY_BUNDLE_PATH", "policies/policy_bundle_curve_composer_v1.yaml")).strip() or "policies/policy_bundle_curve_composer_v1.yaml"


def _composer_context(*, compose_error: str = "", compose_form: dict[str, Any] | None = None) -> dict[str, Any]:
    cards = reg_list_cards(registry_root=registry_root())
    default_form: dict[str, Any] = {
        "title": "composed_ui_run",
        "policy_bundle_path": _composer_policy_bundle_default(),
        "register_card": "true",
        "selected_card_ids": [],
        "weights_by_card": {},
    }
    if isinstance(compose_form, dict):
        default_form.update(compose_form)
    return {
        "title": "Composer",
        "cards": cards,
        "compose_error": compose_error,
        "compose_form": default_form,
    }


@router.api_route("/ui/composer", methods=["GET", "HEAD"], response_class=HTMLResponse)
def ui_composer(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(request, "composer.html", _composer_context())


@router.post("/ui/composer/compose")
async def ui_composer_compose(request: Request):
    from quant_eam.composer.run import EXIT_OK as COMPOSER_OK, run_once as composer_run_once

    enforce_write_auth(request)
    ctype = str(request.headers.get("content-type", "")).lower()
    body = await request.body()

    card_ids: list[str] = []
    weights_raw: list[str] = []
    title = ""
    policy_bundle_path = _composer_policy_bundle_default()
    register_card = True

    if "application/json" in ctype:
        try:
            doc = json.loads(body.decode("utf-8", errors="ignore")) if body else {}
        except Exception as e:  # noqa: BLE001
            return TEMPLATES.TemplateResponse(
                request,
                "composer.html",
                _composer_context(compose_error=f"invalid json body: {e}"),
                status_code=422,
            )
        if not isinstance(doc, dict):
            return TEMPLATES.TemplateResponse(
                request,
                "composer.html",
                _composer_context(compose_error="json body must be object"),
                status_code=422,
            )
        card_ids = [str(x).strip() for x in (doc.get("card_ids") or []) if str(x).strip()]
        weights_raw = [str(x).strip() for x in (doc.get("weights") or []) if str(x).strip()]
        title = str(doc.get("title") or "").strip()
        pb = str(doc.get("policy_bundle_path") or "").strip()
        if pb:
            policy_bundle_path = pb
        rc = str(doc.get("register_card") or "").strip().lower()
        if rc in ("0", "false", "no"):
            register_card = False
    else:
        form = parse_qs(body.decode("utf-8", errors="ignore"), keep_blank_values=True)
        card_ids = [str(x).strip() for x in (form.get("card_ids") or []) if str(x).strip()]
        weights_raw = [str(x).strip() for x in (form.get("weights") or []) if str(x).strip()]
        title = str((form.get("title") or [""])[0]).strip()
        pb = str((form.get("policy_bundle_path") or [""])[0]).strip()
        if pb:
            policy_bundle_path = pb
        rc = str((form.get("register_card") or ["true"])[0]).strip().lower()
        register_card = rc not in ("0", "false", "no")

    form_state = {
        "title": title,
        "policy_bundle_path": policy_bundle_path,
        "register_card": "true" if register_card else "false",
        "selected_card_ids": card_ids,
        "weights_by_card": {},
    }

    try:
        card_ids = [require_safe_id(cid, kind="card_id") for cid in card_ids]
    except HTTPException as e:
        return TEMPLATES.TemplateResponse(
            request,
            "composer.html",
            _composer_context(compose_error=str(e.detail), compose_form=form_state),
            status_code=422,
        )

    if len(card_ids) < 2:
        return TEMPLATES.TemplateResponse(
            request,
            "composer.html",
            _composer_context(compose_error="select at least two cards", compose_form=form_state),
            status_code=422,
        )

    weights: list[float] = []
    if weights_raw:
        if len(weights_raw) != len(card_ids):
            return TEMPLATES.TemplateResponse(
                request,
                "composer.html",
                _composer_context(compose_error="weights count must match card_ids", compose_form=form_state),
                status_code=422,
            )
        for w in weights_raw:
            try:
                weights.append(float(w))
            except Exception:
                return TEMPLATES.TemplateResponse(
                    request,
                    "composer.html",
                    _composer_context(compose_error=f"invalid weight: {w}", compose_form=form_state),
                    status_code=422,
                )
    else:
        equal = 1.0 / float(len(card_ids))
        weights = [equal for _ in card_ids]
    form_state["weights_by_card"] = {cid: str(weights[i]) for i, cid in enumerate(card_ids)}

    code, out = composer_run_once(
        card_ids=card_ids,
        weights=weights,
        policy_bundle_path=Path(policy_bundle_path),
        register_card=bool(register_card),
        title=(title or None),
    )
    if code != COMPOSER_OK:
        return TEMPLATES.TemplateResponse(
            request,
            "composer.html",
            _composer_context(compose_error=str(out), compose_form=form_state),
            status_code=422,
        )

    run_id = str(out.get("run_id") or "").strip()
    if not run_id:
        return TEMPLATES.TemplateResponse(
            request,
            "composer.html",
            _composer_context(compose_error="composer finished without run_id", compose_form=form_state),
            status_code=500,
        )
    run_id = require_safe_id(run_id, kind="run_id")
    return RedirectResponse(url=f"/ui/runs/{run_id}", status_code=303)


@router.api_route("/ui/prompts", methods=["GET", "HEAD"], response_class=HTMLResponse)
def ui_prompts_index(request: Request) -> HTMLResponse:
    rows: list[dict[str, Any]] = []
    for raw_agent_id in _all_prompt_agent_ids():
        try:
            agent_id = require_safe_id(raw_agent_id, kind="agent_id")
        except HTTPException:
            continue
        versions = _collect_prompt_versions(agent_id)
        if not versions:
            continue
        latest = versions[-1]
        rows.append(
            {
                "agent_id": agent_id,
                "versions": [v["prompt_version"] for v in versions],
                "latest_version": latest["prompt_version"],
                "latest_source": latest["source"],
                "latest_output_schema_version": latest["output_schema_version"],
            }
        )

    return TEMPLATES.TemplateResponse(
        request,
        "prompts.html",
        {
            "title": "Prompt Studio",
            "agents": rows,
        },
    )


@router.api_route("/ui/prompts/{agent_id}", methods=["GET", "HEAD"], response_class=HTMLResponse)
def ui_prompts_detail(request: Request, agent_id: str, version: str | None = None) -> HTMLResponse:
    agent_id = require_safe_id(agent_id, kind="agent_id")
    versions = _collect_prompt_versions(agent_id)
    if not versions:
        raise HTTPException(status_code=404, detail="prompt agent not found")

    by_version = {str(v["prompt_version"]): v for v in versions}
    selected_version = versions[-1]["prompt_version"] if not version else _normalize_prompt_version(version)
    selected = by_version.get(selected_version)
    if not isinstance(selected, dict):
        raise HTTPException(status_code=404, detail="prompt version not found")

    prev = None
    for v in versions:
        if int(v["version_num"]) < int(selected["version_num"]):
            prev = v
    diff_text = ""
    if isinstance(prev, dict):
        diff_text = _render_prompt_diff(
            str(prev.get("body") or ""),
            str(selected.get("body") or ""),
            previous_label=str(prev.get("prompt_version") or "previous"),
            current_label=str(selected.get("prompt_version") or "current"),
        )

    return TEMPLATES.TemplateResponse(
        request,
        "prompt_detail.html",
        {
            "title": f"Prompt {agent_id}",
            "agent_id": agent_id,
            "versions": versions,
            "selected_version": selected["prompt_version"],
            "selected_output_schema_version": selected.get("output_schema_version") or "",
            "selected_source": selected.get("source") or "",
            "selected_path": selected.get("path") or "",
            "selected_body": selected.get("body") or "",
            "diff_text": diff_text,
            "previous_version": (prev.get("prompt_version") if isinstance(prev, dict) else ""),
        },
    )


@router.post("/ui/prompts/{agent_id}/publish")
async def ui_prompts_publish(request: Request, agent_id: str) -> RedirectResponse:
    enforce_write_auth(request)
    agent_id = require_safe_id(agent_id, kind="agent_id")
    payload = await _parse_form_or_json(request)

    output_schema_version = str(payload.get("output_schema_version") or "").strip()
    body = str(payload.get("body") or "")
    base_version_raw = str(payload.get("base_version") or "").strip()
    if not output_schema_version:
        raise HTTPException(status_code=422, detail="missing output_schema_version")
    if not body.strip():
        raise HTTPException(status_code=422, detail="missing body")

    versions = _collect_prompt_versions(agent_id)
    if not versions:
        raise HTTPException(status_code=404, detail="prompt agent not found")
    latest = versions[-1]
    latest_version = str(latest["prompt_version"])
    next_version = f"v{int(latest['version_num']) + 1}"

    if base_version_raw:
        base_version = _normalize_prompt_version(base_version_raw)
        if base_version != latest_version:
            raise HTTPException(
                status_code=409,
                detail=f"base_version must equal latest ({latest_version}) for publish vN+1",
            )

    target = _prompt_overrides_root() / agent_id / f"prompt_{next_version}.md"
    if target.exists():
        raise HTTPException(status_code=409, detail=f"prompt version already exists: {next_version}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        _prompt_file_content(version=next_version, output_schema_version=output_schema_version, body=body),
        encoding="utf-8",
    )

    _append_jsonl(
        _prompt_audit_log_path(),
        {
            "schema_version": "prompt_studio_event_v1",
            "event_type": "prompt_publish",
            "recorded_at": _now_iso(),
            "agent_id": agent_id,
            "prompt_version": next_version,
            "output_schema_version": output_schema_version,
            "target_path": target.as_posix(),
            "target_scope": "overlay",
        },
    )

    return RedirectResponse(url=f"/ui/prompts/{agent_id}?version={next_version}", status_code=303)


@router.post("/ui/prompts/{agent_id}/pin")
async def ui_prompts_pin(request: Request, agent_id: str) -> RedirectResponse:
    enforce_write_auth(request)
    agent_id = require_safe_id(agent_id, kind="agent_id")
    payload = await _parse_form_or_json(request)

    job_id = require_safe_job_id(str(payload.get("job_id") or ""))
    prompt_version = _normalize_prompt_version(str(payload.get("prompt_version") or ""))

    versions = _collect_prompt_versions(agent_id)
    valid_versions = {str(v["prompt_version"]) for v in versions}
    if prompt_version not in valid_versions:
        raise HTTPException(status_code=404, detail="prompt version not found")

    paths = jobs_job_paths(job_id, job_root=_job_root())
    if not paths.job_spec.is_file():
        raise HTTPException(status_code=404, detail="job not found")

    pin_dir = paths.outputs_dir / "prompts"
    pin_events_path = pin_dir / "prompt_pin_events.jsonl"
    pin_state_path = pin_dir / "prompt_pin_state.json"
    pin_event = {
        "schema_version": "prompt_pin_event_v1",
        "event_type": "prompt_pin",
        "recorded_at": _now_iso(),
        "job_id": job_id,
        "agent_id": agent_id,
        "prompt_version": prompt_version,
    }
    _append_jsonl(pin_events_path, pin_event)
    state = _build_prompt_pin_state(job_id=job_id, events=_read_jsonl(pin_events_path))
    _write_json(pin_state_path, state)

    _append_jsonl(
        _prompt_audit_log_path(),
        {
            "schema_version": "prompt_studio_event_v1",
            "event_type": "prompt_pin",
            "recorded_at": _now_iso(),
            "job_id": job_id,
            "agent_id": agent_id,
            "prompt_version": prompt_version,
            "pin_events_path": pin_events_path.as_posix(),
            "pin_state_path": pin_state_path.as_posix(),
        },
    )

    return RedirectResponse(url=f"/ui/prompts/{agent_id}?version={prompt_version}", status_code=303)


@router.post("/ui/jobs/idea")
async def ui_submit_idea_job(request: Request):
    """UI helper: create an idea job from form payload and redirect to job detail."""
    enforce_write_auth(request)
    body = (await request.body()).decode("utf-8", errors="ignore")
    data = parse_qs(body, keep_blank_values=True)

    def _f(name: str) -> str:
        vals = data.get(name)
        if not vals:
            return ""
        return str(vals[0]).strip()

    idea_form = {
        "title": _f("title"),
        "hypothesis_text": _f("hypothesis_text"),
        "symbols": _f("symbols"),
        "frequency": _f("frequency"),
        "start": _f("start"),
        "end": _f("end"),
        "evaluation_intent": _f("evaluation_intent"),
        "snapshot_id": _f("snapshot_id"),
        "policy_bundle_path": _f("policy_bundle_path"),
    }

    sid = idea_form["snapshot_id"] or str(os.getenv("EAM_DEFAULT_SNAPSHOT_ID", "")).strip()
    pb = idea_form["policy_bundle_path"] or str(os.getenv("EAM_DEFAULT_POLICY_BUNDLE_PATH", "policies/policy_bundle_v1.yaml")).strip()
    pb = _safe_policy_bundle_path(pb)

    symbols = [x.strip() for x in idea_form["symbols"].split(",") if x.strip()]
    payload: dict[str, Any] = {
        "schema_version": "idea_spec_v1",
        "title": idea_form["title"],
        "hypothesis_text": idea_form["hypothesis_text"],
        "symbols": symbols,
        "frequency": idea_form["frequency"],
        "start": idea_form["start"],
        "end": idea_form["end"],
        "evaluation_intent": idea_form["evaluation_intent"],
        "snapshot_id": sid,
        "policy_bundle_path": pb,
    }

    try:
        _reject_inline_policy_overrides(payload.get("extensions"))
    except HTTPException as e:
        return TEMPLATES.TemplateResponse(
            request,
            "index.html",
            _ui_index_context(idea_form=idea_form, idea_form_error=str(e.detail)),
            status_code=e.status_code,
        )

    code, msg = contracts_validate.validate_payload(payload)
    if code != contracts_validate.EXIT_OK:
        return TEMPLATES.TemplateResponse(
            request,
            "index.html",
            _ui_index_context(idea_form=idea_form, idea_form_error=msg),
            status_code=422,
        )

    try:
        res = create_job_from_ideaspec(
            idea_spec=payload,
            snapshot_id=sid,
            policy_bundle_path=pb,
            job_root=_job_root(),
        )
    except ValueError as e:
        return TEMPLATES.TemplateResponse(
            request,
            "index.html",
            _ui_index_context(idea_form=idea_form, idea_form_error=str(e)),
            status_code=422,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))

    job_id = str(res.get("job_id") or "").strip()
    if job_id and str(res.get("status") or "") == "created":
        try:
            jr = _job_root()
            paths = jobs_job_paths(job_id, job_root=jr)
            events = jobs_load_events(job_id, job_root=jr)

            has_blueprint_proposed = any(str(ev.get("event_type") or "") == "BLUEPRINT_PROPOSED" for ev in events)
            if not has_blueprint_proposed:
                spec = jobs_load_spec(job_id, job_root=jr)
                if isinstance(spec, dict):
                    blueprint_draft = _seed_blueprint_from_idea_spec(spec, job_id=job_id)
                    blueprint_draft_path = paths.outputs_dir / "agents" / "intent" / "blueprint_draft.json"
                    _write_json(blueprint_draft_path, blueprint_draft)

                    outputs_path = paths.outputs_dir / "outputs.json"
                    outputs_doc: dict[str, Any] = {}
                    if outputs_path.is_file():
                        try:
                            existing = _load_json(outputs_path)
                            if isinstance(existing, dict):
                                outputs_doc = existing
                        except Exception:
                            outputs_doc = {}
                    outputs_doc["blueprint_draft_path"] = blueprint_draft_path.as_posix()
                    outputs_doc["snapshot_id"] = str(spec.get("snapshot_id") or sid)
                    outputs_doc["policy_bundle_path"] = str(spec.get("policy_bundle_path") or pb)
                    _write_json(outputs_path, outputs_doc)

                    jobs_append_event(
                        job_id=job_id,
                        event_type="BLUEPRINT_PROPOSED",
                        outputs={"blueprint_draft_path": blueprint_draft_path.as_posix()},
                        job_root=jr,
                    )

            has_blueprint_waiting = any(
                str(ev.get("event_type") or "") == "WAITING_APPROVAL"
                and isinstance(ev.get("outputs"), dict)
                and str((ev.get("outputs") or {}).get("step") or "") == "blueprint"
                for ev in events
            )
            if not has_blueprint_waiting:
                jobs_append_event(
                    job_id=job_id,
                    event_type="WAITING_APPROVAL",
                    outputs={"step": "blueprint"},
                    job_root=jr,
                )
        except Exception:
            pass

    return RedirectResponse(url=f"/ui/jobs/{res['job_id']}", status_code=303)


@router.api_route("/ui/runs/{run_id}", methods=["GET", "HEAD"], response_class=HTMLResponse)
def ui_run(
    request: Request,
    run_id: str,
    symbol: str | None = None,
    segment_id: str | None = None,
    diagnostic_id: str | None = None,
) -> HTMLResponse:
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
        try:
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
        except Exception:
            ohlcv_rows = []

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

    # Phase-43: diagnostics evidence index under dossier diagnostics path.
    diagnostics: list[dict[str, Any]] = []
    diagnostics_root = d / "diagnostics"
    if diagnostics_root.is_dir():
        for dd in sorted(diagnostics_root.iterdir(), key=lambda x: x.name):
            if not dd.is_dir():
                continue
            did = str(dd.name).strip()
            try:
                did = require_safe_id(did, kind="diagnostic_id")
            except HTTPException:
                continue
            report_path = dd / "diagnostic_report.json"
            gate_spec_path = dd / "promotion_candidate" / "gate_spec.json"
            report = _load_json(report_path) if report_path.is_file() else {}
            gate_spec = _load_json(gate_spec_path) if gate_spec_path.is_file() else {}
            candidate_gates = gate_spec.get("candidate_gates") if isinstance(gate_spec, dict) else None
            diagnostics.append(
                {
                    "diagnostic_id": did,
                    "summary": report.get("summary") if isinstance(report, dict) else None,
                    "candidate_gate_count": len(candidate_gates) if isinstance(candidate_gates, list) else 0,
                    "diagnostic_spec_path": f"diagnostics/{did}/diagnostic_spec.json",
                    "diagnostic_report_path": f"diagnostics/{did}/diagnostic_report.json",
                    "promotion_gate_spec_path": (
                        f"diagnostics/{did}/promotion_candidate/gate_spec.json" if gate_spec_path.is_file() else ""
                    ),
                }
            )

    selected_diagnostic_id = ""
    selected_diagnostic_report: dict[str, Any] | None = None
    selected_promotion_gate_spec: dict[str, Any] | None = None
    if diagnostics:
        requested_diag = str(diagnostic_id or "").strip()
        if requested_diag:
            try:
                requested_diag = require_safe_id(requested_diag, kind="diagnostic_id")
            except HTTPException:
                requested_diag = ""
        selected_diagnostic_id = requested_diag or str(diagnostics[0]["diagnostic_id"])
        selected_dir = diagnostics_root / selected_diagnostic_id
        report_path = selected_dir / "diagnostic_report.json"
        gate_spec_path = selected_dir / "promotion_candidate" / "gate_spec.json"
        if report_path.is_file():
            doc = _load_json(report_path)
            if isinstance(doc, dict):
                selected_diagnostic_report = doc
        if gate_spec_path.is_file():
            doc = _load_json(gate_spec_path)
            if isinstance(doc, dict):
                selected_promotion_gate_spec = doc

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
            "diagnostics": diagnostics,
            "selected_diagnostic_id": selected_diagnostic_id,
            "selected_diagnostic_report": selected_diagnostic_report,
            "selected_promotion_gate_spec": selected_promotion_gate_spec,
        },
    )


@router.api_route("/ui/runs/{run_id}/gates", methods=["GET", "HEAD"], response_class=HTMLResponse)
def ui_run_gates(request: Request, run_id: str) -> HTMLResponse:
    run_id = require_safe_id(run_id, kind="run_id")
    d = require_child_dir(dossiers_root(), run_id)
    if not d.is_dir():
        raise HTTPException(status_code=404, detail="not found")

    gate_results_path = d / "gate_results.json"
    gate_results = _load_json(gate_results_path) if gate_results_path.is_file() else {}
    holdout = gate_results.get("holdout_summary") if isinstance(gate_results, dict) else None
    holdout_summary = None
    if isinstance(holdout, dict):
        holdout_summary = {
            "pass": holdout.get("pass"),
            "summary": holdout.get("summary"),
        }

    overall_pass = gate_results.get("overall_pass") if isinstance(gate_results, dict) else None
    gate_suite_id = gate_results.get("gate_suite_id") if isinstance(gate_results, dict) else None
    schema_version = gate_results.get("schema_version") if isinstance(gate_results, dict) else None

    return TEMPLATES.TemplateResponse(
        request,
        "run_gates.html",
        {
            "run_id": run_id,
            "gate_results_path": f"dossiers/{run_id}/gate_results.json",
            "gate_results_present": gate_results_path.is_file(),
            "gate_results_schema_version": str(schema_version or ""),
            "gate_suite_id": str(gate_suite_id or ""),
            "overall_pass": overall_pass if isinstance(overall_pass, bool) else None,
            "gate_rows": _gate_detail_rows(gate_results),
            "holdout_summary": holdout_summary,
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
    spec_qa_report = None
    spec_qa_report_md = ""
    diagnostics_plan = None
    registry_curator_summary = None
    composer_agent_plan = None
    llm_evidence: list[dict[str, Any]] = []
    llm_usage_report = None
    llm_usage_report_json = ""
    llm_usage_report_path = None
    llm_usage_events_path = None
    reject_log_rows: list[dict[str, Any]] = []
    reject_state = None
    rerun_log_rows: list[dict[str, Any]] = []
    rerun_state = None
    sweep_leaderboard = None
    sweep_trials_tail: list[dict[str, Any]] = []
    experience_pack = None
    experience_pack_json = ""
    dossier_fetch_summary = None
    dossier_fetch_steps: list[dict[str, Any]] = []
    dossier_fetch_index_json = ""
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

    try:
        reject_log_rows = _read_jsonl(paths.outputs_dir / "rejections" / "reject_log.jsonl")[-20:]
    except Exception:
        reject_log_rows = []
    try:
        rej_state_path = paths.outputs_dir / "rejections" / "reject_state.json"
        if rej_state_path.is_file():
            doc = _load_json(rej_state_path)
            if isinstance(doc, dict):
                reject_state = doc
    except Exception:
        reject_state = None
    try:
        rerun_log_rows = _read_jsonl(paths.outputs_dir / "reruns" / "rerun_log.jsonl")[-20:]
    except Exception:
        rerun_log_rows = []
    try:
        rerun_state_path = paths.outputs_dir / "reruns" / "rerun_state.json"
        if rerun_state_path.is_file():
            doc = _load_json(rerun_state_path)
            if isinstance(doc, dict):
                rerun_state = doc
    except Exception:
        rerun_state = None

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

    spec_qa_json_path = outputs.get("spec_qa_report_path")
    if isinstance(spec_qa_json_path, str) and Path(spec_qa_json_path).is_file():
        try:
            spec_qa_report = json.loads(Path(spec_qa_json_path).read_text(encoding="utf-8"))
        except Exception:
            spec_qa_report = None
    spec_qa_md_path = outputs.get("spec_qa_report_md_path")
    if isinstance(spec_qa_md_path, str) and Path(spec_qa_md_path).is_file():
        try:
            spec_qa_report_md = Path(spec_qa_md_path).read_text(encoding="utf-8")
        except Exception:
            spec_qa_report_md = ""

    diagnostics_plan_path = outputs.get("diagnostics_plan_path")
    if isinstance(diagnostics_plan_path, str) and Path(diagnostics_plan_path).is_file():
        try:
            diagnostics_plan = json.loads(Path(diagnostics_plan_path).read_text(encoding="utf-8"))
        except Exception:
            diagnostics_plan = None

    curator_summary_path = outputs.get("registry_curator_summary_path")
    if isinstance(curator_summary_path, str) and Path(curator_summary_path).is_file():
        try:
            registry_curator_summary = json.loads(Path(curator_summary_path).read_text(encoding="utf-8"))
        except Exception:
            registry_curator_summary = None

    composer_plan_path = outputs.get("composer_agent_plan_path")
    if isinstance(composer_plan_path, str) and Path(composer_plan_path).is_file():
        try:
            composer_agent_plan = json.loads(Path(composer_plan_path).read_text(encoding="utf-8"))
        except Exception:
            composer_agent_plan = None

    # LLM evidence (Phase-18/19/28): scan agent output dirs for llm_session + redaction + calls + output guard + errors.
    agents_root = paths.outputs_dir / "agents"
    if agents_root.is_dir():
        for d in sorted([p for p in agents_root.iterdir() if p.is_dir()], key=lambda x: x.name):
            name = str(d.name)
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

    # Dossier-local fetch evidence viewer (read-only).
    def _resolve_fetch_path(raw: Any, fetch_dir: Path) -> Path | None:
        if not isinstance(raw, str) or not raw.strip():
            return None
        p = Path(raw)
        if p.is_file():
            return p
        cand_rel = fetch_dir / raw
        if cand_rel.is_file():
            return cand_rel
        cand_name = fetch_dir / p.name
        if cand_name.is_file():
            return cand_name
        return None

    dossier_raw = outputs.get("dossier_path")
    if isinstance(dossier_raw, str) and Path(dossier_raw).is_dir():
        fetch_dir = Path(dossier_raw) / "fetch"
        idx_path = fetch_dir / "fetch_steps_index.json"
        if idx_path.is_file():
            idx_doc: dict[str, Any] = {}
            try:
                loaded = json.loads(idx_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    idx_doc = loaded
            except Exception:
                idx_doc = {}
            if idx_doc:
                dossier_fetch_index_json = json.dumps(idx_doc, indent=2, sort_keys=True)
                rows = idx_doc.get("steps")
                if isinstance(rows, list):
                    for row in rows:
                        if not isinstance(row, dict):
                            continue
                        request_p = _resolve_fetch_path(row.get("request_path"), fetch_dir)
                        meta_p = _resolve_fetch_path(row.get("result_meta_path"), fetch_dir)
                        preview_p = _resolve_fetch_path(row.get("preview_path"), fetch_dir)
                        error_p = _resolve_fetch_path(row.get("error_path"), fetch_dir)

                        request_json = ""
                        meta_json = ""
                        error_json = ""
                        preview_rows: list[dict[str, str]] = []
                        if request_p and request_p.is_file():
                            try:
                                request_json = json.dumps(json.loads(request_p.read_text(encoding="utf-8")), indent=2, sort_keys=True)
                            except Exception:
                                request_json = ""
                        if meta_p and meta_p.is_file():
                            try:
                                meta_json = json.dumps(json.loads(meta_p.read_text(encoding="utf-8")), indent=2, sort_keys=True)
                            except Exception:
                                meta_json = ""
                        if error_p and error_p.is_file():
                            try:
                                error_json = json.dumps(json.loads(error_p.read_text(encoding="utf-8")), indent=2, sort_keys=True)
                            except Exception:
                                error_json = ""
                        if preview_p and preview_p.is_file():
                            try:
                                preview_rows = _read_csv_rows(preview_p)[:10]
                            except Exception:
                                preview_rows = []

                        dossier_fetch_steps.append(
                            {
                                "step_index": row.get("step_index"),
                                "step_kind": row.get("step_kind"),
                                "status": row.get("status"),
                                "request_path": request_p.as_posix() if request_p else str(row.get("request_path") or ""),
                                "result_meta_path": meta_p.as_posix() if meta_p else str(row.get("result_meta_path") or ""),
                                "preview_path": preview_p.as_posix() if preview_p else str(row.get("preview_path") or ""),
                                "error_path": error_p.as_posix() if error_p else str(row.get("error_path") or ""),
                                "request_json": request_json,
                                "meta_json": meta_json,
                                "error_json": error_json,
                                "preview_rows": preview_rows,
                            }
                        )

                dossier_fetch_summary = {
                    "fetch_dir": fetch_dir.as_posix(),
                    "steps_index_path": idx_path.as_posix(),
                    "step_count": len(dossier_fetch_steps),
                }

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
            "spec_qa_report_json": json.dumps(spec_qa_report, indent=2, sort_keys=True) if spec_qa_report else "",
            "spec_qa_report_md": spec_qa_report_md,
            "diagnostics_plan_json": json.dumps(diagnostics_plan, indent=2, sort_keys=True) if diagnostics_plan else "",
            "registry_curator_summary_json": (
                json.dumps(registry_curator_summary, indent=2, sort_keys=True) if registry_curator_summary else ""
            ),
            "composer_agent_plan_json": json.dumps(composer_agent_plan, indent=2, sort_keys=True) if composer_agent_plan else "",
            "sweep_leaderboard_json": json.dumps(sweep_leaderboard, indent=2, sort_keys=True) if sweep_leaderboard else "",
            "sweep_leaderboard_obj": (sweep_leaderboard if isinstance(sweep_leaderboard, dict) else None),
            "sweep_trials_tail": sweep_trials_tail,
            "experience_pack": experience_pack,
            "experience_pack_json": experience_pack_json,
            "dossier_fetch_summary": dossier_fetch_summary,
            "dossier_fetch_steps": dossier_fetch_steps,
            "dossier_fetch_index_json": dossier_fetch_index_json,
            "llm_evidence": llm_evidence,
            "llm_usage_report": llm_usage_report,
            "llm_usage_report_json": llm_usage_report_json,
            "llm_usage_report_path": llm_usage_report_path,
            "llm_usage_events_path": llm_usage_events_path,
            "reject_enabled": bool(waiting and waiting_step in REJECTABLE_STEPS),
            "reject_fallback_step": REJECT_FALLBACK_STEP.get(waiting_step or "", waiting_step),
            "reject_log_rows": reject_log_rows,
            "reject_state_json": json.dumps(reject_state, indent=2, sort_keys=True) if reject_state else "",
            "rerun_agent_options": list(RERUN_AGENT_OPTIONS),
            "rerun_log_rows": rerun_log_rows,
            "rerun_state_json": json.dumps(rerun_state, indent=2, sort_keys=True) if rerun_state else "",
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
        if step not in APPROVAL_STEPS:
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


@router.post("/ui/jobs/{job_id}/reject")
async def ui_job_reject(request: Request, job_id: str, step: str | None = None) -> RedirectResponse:
    from quant_eam.api.jobs_api import reject as api_job_reject

    note = ""
    try:
        raw = (await request.body()).decode("utf-8")
        data = parse_qs(raw, keep_blank_values=True) if raw else {}
        vals = data.get("note") if isinstance(data, dict) else None
        note = str(vals[0]).strip() if isinstance(vals, list) and vals else ""
    except Exception:
        note = ""
    _ = api_job_reject(request, job_id, step=step, note=note)
    return RedirectResponse(url=f"/ui/jobs/{job_id}", status_code=303)


@router.post("/ui/jobs/{job_id}/rerun")
async def ui_job_rerun(request: Request, job_id: str, agent_id: str | None = None) -> RedirectResponse:
    from quant_eam.api.jobs_api import rerun as api_job_rerun

    aid = str(agent_id or "").strip()
    if not aid:
        try:
            raw = (await request.body()).decode("utf-8")
            data = parse_qs(raw, keep_blank_values=True) if raw else {}
            vals = data.get("agent_id") if isinstance(data, dict) else None
            aid = str(vals[0]).strip() if isinstance(vals, list) and vals else ""
        except Exception:
            aid = ""
    _ = api_job_rerun(request, job_id, agent_id=aid)
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
