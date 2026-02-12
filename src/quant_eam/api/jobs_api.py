from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from quant_eam.api.roots import dossiers_root
from quant_eam.api.security import enforce_write_auth, require_child_dir, require_safe_id, require_safe_job_id
from quant_eam.contracts import validate as contracts_validate
from quant_eam.diagnostics.promotion_chain import run_diagnostic_spec
from quant_eam.jobstore.store import (
    append_event,
    create_job_from_blueprint,
    create_job_from_ideaspec,
    default_job_root,
    job_paths,
    list_job_ids,
    load_job_events,
    load_job_spec,
    spawn_child_job_from_proposal,
    spawn_child_job_from_sweep_best,
    write_outputs_index,
    BudgetExceeded,
)

router = APIRouter()

APPROVAL_STEPS = (
    "blueprint",
    "strategy_spec",
    "spec_qa",
    "runspec",
    "trace_preview",
    "improvements",
    "sweep",
    # Phase-28: operational rollout checkpoints.
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
RERUN_AGENT_DIR: dict[str, str] = {
    "intent_agent_v1": "intent",
    "strategy_spec_agent_v1": "strategy_spec",
    "spec_qa_agent_v1": "spec_qa",
    "demo_agent_v1": "demo",
    "backtest_agent_v1": "backtest",
    "improvement_agent_v1": "improvement",
    "report_agent_v1": "report",
}


def _job_root() -> Path:
    return default_job_root()


def _safe_policy_bundle_path(p: str) -> str:
    # Keep it simple: allow repo-relative paths like policies/policy_bundle_v1.yaml.
    # Real enforcement belongs to kernel (not UI). Here we only prevent traversal.
    if not p or p.startswith("/") or ".." in p or "\\" in p:
        raise HTTPException(status_code=400, detail="invalid policy_bundle_path")
    return p


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def _append_jsonl(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(doc, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n")


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _latest_waiting_step(events: list[dict[str, Any]]) -> str | None:
    if not events:
        return None

    idx = len(events) - 1
    while idx >= 0:
        ev = events[idx]
        if str(ev.get("event_type")) != "SPAWNED":
            break
        out = ev.get("outputs") if isinstance(ev.get("outputs"), dict) else {}
        if str(out.get("action") or "").strip() != "rerun_requested":
            return None
        idx -= 1

    if idx < 0:
        return None
    ev = events[idx]
    if str(ev.get("event_type")) != "WAITING_APPROVAL":
        return None
    out = ev.get("outputs") if isinstance(ev.get("outputs"), dict) else {}
    step = str(out.get("step") or "").strip()
    return step or None


def _record_rejection(*, job_id: str, rejected_step: str, fallback_step: str, note: str, source: str) -> dict[str, Any]:
    paths = job_paths(job_id, job_root=_job_root())
    rej_dir = paths.outputs_dir / "rejections"
    reject_log_path = rej_dir / "reject_log.jsonl"
    reject_state_path = rej_dir / "reject_state.json"

    entry = {
        "schema_version": "job_reject_event_v1",
        "job_id": job_id,
        "rejected_step": rejected_step,
        "fallback_step": fallback_step,
        "note": note,
        "source": source,
        "recorded_at": _now_iso(),
    }
    _append_jsonl(reject_log_path, entry)

    state = {
        "schema_version": "job_reject_state_v1",
        "job_id": job_id,
        "last_rejection": entry,
        "updated_at": entry["recorded_at"],
    }
    _write_json(reject_state_path, state)
    write_outputs_index(
        job_id=job_id,
        updates={
            "reject_log_path": reject_log_path.as_posix(),
            "reject_state_path": reject_state_path.as_posix(),
            "reject_last_step": rejected_step,
            "reject_last_fallback_step": fallback_step,
        },
        job_root=_job_root(),
    )
    return {
        "entry": entry,
        "reject_log_path": reject_log_path.as_posix(),
        "reject_state_path": reject_state_path.as_posix(),
    }


def _load_outputs(job_id: str) -> dict[str, Any]:
    paths = job_paths(job_id, job_root=_job_root())
    p = paths.outputs_dir / "outputs.json"
    if not p.is_file():
        return {}
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return doc if isinstance(doc, dict) else {}


def _new_rerun_id() -> str:
    return f"rerun_{datetime.now().strftime('%Y%m%dT%H%M%S%f')}"


def _resolve_rerun_io(*, job_id: str, agent_id: str) -> dict[str, str]:
    paths = job_paths(job_id, job_root=_job_root())
    outputs = _load_outputs(job_id)
    aid = str(agent_id).strip()

    if aid == "intent_agent_v1":
        input_path = paths.job_spec
        out_base = paths.outputs_dir / "agents" / "intent"
    elif aid in {
        "strategy_spec_agent_v1",
        "spec_qa_agent_v1",
        "demo_agent_v1",
        "backtest_agent_v1",
        "improvement_agent_v1",
    }:
        out_base = paths.outputs_dir / "agents" / str(RERUN_AGENT_DIR[aid])
        input_path = out_base / "agent_input.json"
    elif aid == "report_agent_v1":
        dossier_path = Path(str(outputs.get("dossier_path", "")))
        out_base = dossier_path / "reports" / "agent"
        input_path = dossier_path / "dossier_manifest.json"
    else:
        raise HTTPException(status_code=400, detail="invalid agent_id")

    if not input_path.is_file():
        raise HTTPException(status_code=409, detail=f"missing rerun input for {aid}: {input_path.as_posix()}")

    rerun_id = _new_rerun_id()
    out_dir = out_base / "reruns" / rerun_id
    return {
        "agent_id": aid,
        "input_path": input_path.as_posix(),
        "out_dir": out_dir.as_posix(),
        "rerun_id": rerun_id,
    }


def _load_prompt_pin_version(*, job_id: str, agent_id: str) -> str | None:
    paths = job_paths(job_id, job_root=_job_root())
    pin_state = paths.outputs_dir / "prompts" / "prompt_pin_state.json"
    if not pin_state.is_file():
        return None
    try:
        doc = json.loads(pin_state.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(doc, dict):
        return None
    pins = doc.get("pins")
    if not isinstance(pins, dict):
        return None
    item = pins.get(agent_id)
    if not isinstance(item, dict):
        return None
    v = str(item.get("prompt_version") or "").strip()
    return v or None


def _detect_prompt_version_from_session(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(doc, dict):
        return None
    v = str(doc.get("prompt_version") or "").strip()
    return v or None


def _record_rerun(
    *,
    job_id: str,
    agent_id: str,
    rerun_id: str,
    input_path: Path,
    out_dir: Path,
    agent_run_path: Path,
    prompt_version: str | None,
    source: str,
) -> dict[str, Any]:
    paths = job_paths(job_id, job_root=_job_root())
    rr_dir = paths.outputs_dir / "reruns"
    rerun_log_path = rr_dir / "rerun_log.jsonl"
    rerun_state_path = rr_dir / "rerun_state.json"
    llm_session_path = out_dir / "llm_session.json"

    entry = {
        "schema_version": "job_rerun_event_v1",
        "job_id": job_id,
        "rerun_id": rerun_id,
        "agent_id": agent_id,
        "prompt_version": prompt_version or "",
        "input_path": input_path.as_posix(),
        "output_dir": out_dir.as_posix(),
        "agent_run_path": agent_run_path.as_posix(),
        "llm_session_path": llm_session_path.as_posix() if llm_session_path.is_file() else "",
        "source": source,
        "recorded_at": _now_iso(),
    }
    _append_jsonl(rerun_log_path, entry)

    state = {
        "schema_version": "job_rerun_state_v1",
        "job_id": job_id,
        "last_rerun": entry,
        "updated_at": entry["recorded_at"],
    }
    _write_json(rerun_state_path, state)
    write_outputs_index(
        job_id=job_id,
        updates={
            "rerun_log_path": rerun_log_path.as_posix(),
            "rerun_state_path": rerun_state_path.as_posix(),
            "rerun_last_agent_id": agent_id,
            "rerun_last_agent_run_path": agent_run_path.as_posix(),
            "rerun_last_output_dir": out_dir.as_posix(),
            "rerun_last_prompt_version": prompt_version or "",
        },
        job_root=_job_root(),
    )
    return {
        "entry": entry,
        "rerun_log_path": rerun_log_path.as_posix(),
        "rerun_state_path": rerun_state_path.as_posix(),
    }


def _reject_inline_policy_overrides(ext: Any) -> None:
    if not isinstance(ext, dict):
        return
    # Extensions must be metadata only; do not allow policy "inline override" knobs here.
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


@router.post("/jobs/blueprint")
async def submit_blueprint(
    request: Request,
    snapshot_id: str | None = None,
    policy_bundle_path: str | None = None,
) -> dict[str, Any]:
    """Create a deterministic JobSpec from a Blueprint JSON body."""
    enforce_write_auth(request)
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="invalid json")

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="blueprint must be a json object")

    # Validate blueprint contract (I/O SSOT).
    code, msg = contracts_validate.validate_payload(payload)
    if code != contracts_validate.EXIT_OK:
        raise HTTPException(status_code=422, detail=msg)

    sid = (snapshot_id or os.getenv("EAM_DEFAULT_SNAPSHOT_ID") or "").strip()
    if not sid:
        raise HTTPException(status_code=400, detail="missing snapshot_id (query param or EAM_DEFAULT_SNAPSHOT_ID)")

    pb = (policy_bundle_path or os.getenv("EAM_DEFAULT_POLICY_BUNDLE_PATH") or "policies/policy_bundle_v1.yaml").strip()
    pb = _safe_policy_bundle_path(pb)

    try:
        res = create_job_from_blueprint(
            blueprint=payload,
            snapshot_id=sid,
            policy_bundle_path=pb,
            job_root=_job_root(),
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))

    return {"job_id": res["job_id"], "status": res["status"], "job_dir": res["job_dir"]}


@router.post("/jobs/idea")
async def submit_idea(
    request: Request,
    snapshot_id: str | None = None,
    policy_bundle_path: str | None = None,
) -> dict[str, Any]:
    """Create a deterministic job from an IdeaSpec JSON body."""
    enforce_write_auth(request)
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="invalid json")

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="idea_spec must be a json object")

    # Validate idea spec contract.
    code, msg = contracts_validate.validate_payload(payload)
    if code != contracts_validate.EXIT_OK:
        raise HTTPException(status_code=422, detail=msg)

    _reject_inline_policy_overrides(payload.get("extensions"))

    sid = (snapshot_id or payload.get("snapshot_id") or "").strip()
    if not sid:
        raise HTTPException(status_code=400, detail="missing snapshot_id (query param or idea_spec.snapshot_id)")

    pb = (
        policy_bundle_path
        or payload.get("policy_bundle_path")
        or os.getenv("EAM_DEFAULT_POLICY_BUNDLE_PATH")
        or "policies/policy_bundle_v1.yaml"
    )
    pb = _safe_policy_bundle_path(str(pb).strip())

    try:
        res = create_job_from_ideaspec(
            idea_spec=payload,
            snapshot_id=str(sid),
            policy_bundle_path=pb,
            job_root=_job_root(),
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))

    return {"job_id": res["job_id"], "status": res["status"], "job_dir": res["job_dir"]}


@router.post("/jobs/{job_id}/approve")
def approve(request: Request, job_id: str, step: str | None = None) -> dict[str, Any]:
    enforce_write_auth(request)
    job_id = require_safe_job_id(job_id)
    paths = job_paths(job_id, job_root=_job_root())
    if not paths.job_spec.is_file():
        raise HTTPException(status_code=404, detail="not found")

    # Idempotent: if already approved, noop.
    events = load_job_events(job_id, job_root=_job_root())
    if step:
        step = str(step)
        if step not in APPROVAL_STEPS:
            raise HTTPException(status_code=400, detail="invalid step")
        for ev in events:
            if str(ev.get("event_type")) == "APPROVED" and isinstance(ev.get("outputs"), dict):
                if str(ev["outputs"].get("step")) == step:
                    return {"job_id": job_id, "status": "noop"}
    else:
        if any(str(ev.get("event_type")) == "APPROVED" for ev in events):
            return {"job_id": job_id, "status": "noop"}

    outputs = {"step": step} if step else None
    ev = append_event(job_id=job_id, event_type="APPROVED", outputs=outputs, job_root=_job_root())
    return {"job_id": job_id, "status": "approved", "event": ev}


@router.post("/jobs/{job_id}/reject")
def reject(request: Request, job_id: str, step: str | None = None, note: str | None = None) -> dict[str, Any]:
    enforce_write_auth(request)
    job_id = require_safe_job_id(job_id)
    paths = job_paths(job_id, job_root=_job_root())
    if not paths.job_spec.is_file():
        raise HTTPException(status_code=404, detail="not found")

    events = load_job_events(job_id, job_root=_job_root())
    waiting_step = _latest_waiting_step(events)
    if not waiting_step:
        raise HTTPException(status_code=409, detail="job is not waiting approval")

    step_resolved = str(step or waiting_step).strip()
    if step_resolved not in REJECTABLE_STEPS:
        raise HTTPException(status_code=400, detail="invalid step")
    if step_resolved != waiting_step:
        raise HTTPException(status_code=409, detail=f"step mismatch: waiting approval step is {waiting_step}")

    fallback_step = str(REJECT_FALLBACK_STEP.get(step_resolved, step_resolved))
    note_text = str(note or "").strip()
    rej = _record_rejection(
        job_id=job_id,
        rejected_step=step_resolved,
        fallback_step=fallback_step,
        note=note_text,
        source="jobs_api",
    )
    ev = append_event(
        job_id=job_id,
        event_type="WAITING_APPROVAL",
        message=f"REJECTED(step={step_resolved})",
        outputs={
            "step": fallback_step,
            "reject_action": {
                "rejected_step": step_resolved,
                "fallback_step": fallback_step,
                "note": note_text,
                "reject_log_path": rej["reject_log_path"],
            },
        },
        job_root=_job_root(),
    )
    return {
        "job_id": job_id,
        "status": "rejected",
        "rejected_step": step_resolved,
        "fallback_step": fallback_step,
        "event": ev,
        "rejection": rej["entry"],
    }


@router.post("/jobs/{job_id}/rerun")
def rerun(request: Request, job_id: str, agent_id: str) -> dict[str, Any]:
    from quant_eam.agents.harness import run_agent

    enforce_write_auth(request)
    job_id = require_safe_job_id(job_id)
    paths = job_paths(job_id, job_root=_job_root())
    if not paths.job_spec.is_file():
        raise HTTPException(status_code=404, detail="not found")

    aid = str(agent_id).strip()
    if aid not in RERUN_AGENT_DIR:
        raise HTTPException(status_code=400, detail="invalid agent_id")

    io = _resolve_rerun_io(job_id=job_id, agent_id=aid)
    input_path = Path(io["input_path"])
    out_dir = Path(io["out_dir"])
    rerun_id = str(io["rerun_id"])

    pinned_prompt_version = _load_prompt_pin_version(job_id=job_id, agent_id=aid)
    prev_prompt = os.getenv("EAM_AGENT_PROMPT_VERSION")
    prev_job = os.getenv("EAM_CURRENT_JOB_ID")
    try:
        if pinned_prompt_version:
            os.environ["EAM_AGENT_PROMPT_VERSION"] = pinned_prompt_version
        os.environ["EAM_CURRENT_JOB_ID"] = job_id
        res = run_agent(agent_id=aid, input_path=input_path, out_dir=out_dir, provider="mock")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"rerun failed: {e}")
    finally:
        if prev_prompt is None:
            os.environ.pop("EAM_AGENT_PROMPT_VERSION", None)
        else:
            os.environ["EAM_AGENT_PROMPT_VERSION"] = prev_prompt
        if prev_job is None:
            os.environ.pop("EAM_CURRENT_JOB_ID", None)
        else:
            os.environ["EAM_CURRENT_JOB_ID"] = prev_job

    llm_session_path = out_dir / "llm_session.json"
    effective_prompt_version = pinned_prompt_version or _detect_prompt_version_from_session(llm_session_path)
    rr = _record_rerun(
        job_id=job_id,
        agent_id=aid,
        rerun_id=rerun_id,
        input_path=input_path,
        out_dir=out_dir,
        agent_run_path=res.agent_run_path,
        prompt_version=effective_prompt_version,
        source="jobs_api",
    )
    ev = append_event(
        job_id=job_id,
        event_type="SPAWNED",
        message=f"RERUN_REQUESTED(agent_id={aid})",
        outputs={
            "action": "rerun_requested",
            "agent_id": aid,
            "rerun_id": rerun_id,
            "agent_run_path": res.agent_run_path.as_posix(),
            "rerun_log_path": rr["rerun_log_path"],
            "prompt_version": effective_prompt_version or "",
        },
        job_root=_job_root(),
    )
    return {
        "job_id": job_id,
        "status": "rerun_requested",
        "agent_id": aid,
        "rerun_id": rerun_id,
        "agent_run_path": res.agent_run_path.as_posix(),
        "prompt_version": effective_prompt_version or "",
        "event": ev,
        "rerun": rr["entry"],
    }


@router.post("/runs/{run_id}/diagnostics")
async def run_diagnostic(request: Request, run_id: str) -> dict[str, Any]:
    """Execute a diagnostic_spec against an existing dossier run and persist deterministic artifacts."""
    enforce_write_auth(request)
    run_id = require_safe_id(run_id, kind="run_id")
    dossier_dir = require_child_dir(dossiers_root(), run_id)
    if not dossier_dir.is_dir():
        raise HTTPException(status_code=404, detail="run not found")

    try:
        body = await request.json()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"invalid json body: {e}") from e

    spec: dict[str, Any]
    if isinstance(body, dict) and isinstance(body.get("diagnostic_spec"), dict):
        spec = dict(body["diagnostic_spec"])
    elif isinstance(body, dict):
        spec = dict(body)
    else:
        raise HTTPException(status_code=422, detail="json body must be object or include diagnostic_spec object")

    stated_run = str(spec.get("run_id") or "").strip()
    if stated_run and stated_run != run_id:
        raise HTTPException(status_code=422, detail=f"run_id mismatch: path={run_id} body={stated_run}")
    spec["run_id"] = run_id

    try:
        out = run_diagnostic_spec(run_id=run_id, diagnostic_spec=spec, dossiers_dir=dossiers_root())
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"diagnostic execution failed: {e}") from e

    return {
        "run_id": run_id,
        "diagnostic_id": str(out.get("diagnostic_id") or ""),
        "summary": out.get("summary"),
        "artifacts": {
            "diagnostic_spec_path": out.get("diagnostic_spec_path"),
            "diagnostic_report_path": out.get("diagnostic_report_path"),
            "diagnostic_outputs_dir": out.get("diagnostic_outputs_dir"),
            "promotion_gate_spec_path": out.get("promotion_gate_spec_path"),
        },
    }


@router.get("/jobs/{job_id}/proposals")
def get_job_proposals(job_id: str) -> dict[str, Any]:
    job_id = require_safe_job_id(job_id)
    paths = job_paths(job_id, job_root=_job_root())
    if not paths.job_spec.is_file():
        raise HTTPException(status_code=404, detail="not found")
    outputs_path = paths.outputs_dir / "outputs.json"
    if not outputs_path.is_file():
        raise HTTPException(status_code=404, detail="no outputs")
    try:
        outputs = json.loads(outputs_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        outputs = {}
    if not isinstance(outputs, dict):
        outputs = {}
    p = outputs.get("improvement_proposals_path")
    if not isinstance(p, str) or not Path(p).is_file():
        raise HTTPException(status_code=404, detail="no proposals")
    try:
        doc = json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="invalid proposals json")
    return {"job_id": job_id, "proposals": doc}


@router.get("/jobs/{job_id}/llm_usage")
def get_job_llm_usage(job_id: str) -> dict[str, Any]:
    """Read-only: return job-level LLM usage report if present (Phase-26)."""
    job_id = require_safe_job_id(job_id)
    paths = job_paths(job_id, job_root=_job_root())
    if not paths.job_spec.is_file():
        raise HTTPException(status_code=404, detail="not found")
    report_p = paths.outputs_dir / "llm" / "llm_usage_report.json"
    events_p = paths.outputs_dir / "llm" / "llm_usage_events.jsonl"
    if not report_p.is_file():
        raise HTTPException(status_code=404, detail="no llm_usage_report")
    try:
        doc = json.loads(report_p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="invalid llm_usage_report json")
    if not isinstance(doc, dict):
        raise HTTPException(status_code=500, detail="invalid llm_usage_report structure")
    return {
        "job_id": job_id,
        "llm_usage_report": doc,
        "paths": {
            "llm_usage_report": report_p.as_posix(),
            "llm_usage_events": events_p.as_posix() if events_p.exists() else None,
        },
    }


@router.post("/jobs/{job_id}/spawn")
def spawn_job(request: Request, job_id: str, proposal_id: str) -> dict[str, Any]:
    """Spawn a new blueprint job from a selected improvement proposal.

    The spawned job must return to WAITING_APPROVAL(step=blueprint) and not auto-run.
    """
    enforce_write_auth(request)

    job_id = require_safe_job_id(job_id)
    proposal_id = str(proposal_id).strip()
    if not proposal_id:
        raise HTTPException(status_code=400, detail="missing proposal_id")

    try:
        return spawn_child_job_from_proposal(base_job_id=job_id, proposal_id=proposal_id, job_root=_job_root())
    except BudgetExceeded as e:
        raise HTTPException(status_code=409, detail=str(e))
    except FileNotFoundError as e:
        msg = str(e)
        if "proposal_id" in msg:
            raise HTTPException(status_code=404, detail="proposal_id not found")
        raise HTTPException(status_code=404, detail="not found")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/jobs/{job_id}/spawn_best")
def spawn_best(request: Request, job_id: str) -> dict[str, Any]:
    """Spawn a child job from sweep best candidate params.

    The spawned job must return to WAITING_APPROVAL(step=blueprint) and not auto-run.
    """
    enforce_write_auth(request)
    job_id = require_safe_job_id(job_id)
    try:
        return spawn_child_job_from_sweep_best(base_job_id=job_id, job_root=_job_root())
    except BudgetExceeded as e:
        raise HTTPException(status_code=409, detail=str(e))
    except FileNotFoundError as e:
        msg = str(e)
        if "leaderboard" in msg:
            raise HTTPException(status_code=404, detail="no sweep leaderboard")
        raise HTTPException(status_code=404, detail="not found")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/{job_id}/sweep/leaderboard")
def get_sweep_leaderboard(job_id: str) -> dict[str, Any]:
    job_id = require_safe_job_id(job_id)
    paths = job_paths(job_id, job_root=_job_root())
    lb = paths.outputs_dir / "sweep" / "leaderboard.json"
    if not lb.is_file():
        raise HTTPException(status_code=404, detail="no leaderboard")
    try:
        doc = json.loads(lb.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="invalid leaderboard json")
    return {"job_id": job_id, "leaderboard": doc}


@router.get("/jobs")
def list_jobs() -> dict[str, Any]:
    out: list[dict[str, Any]] = []
    for jid in list_job_ids(job_root=_job_root()):
        try:
            spec = load_job_spec(jid, job_root=_job_root())
            events = load_job_events(jid, job_root=_job_root())
        except Exception:
            continue
        state = str(events[-1].get("event_type")) if events else "unknown"
        schema_version = spec.get("schema_version") if isinstance(spec, dict) else None
        if schema_version == "job_spec_v1":
            bp = spec.get("blueprint") if isinstance(spec, dict) else {}
            bp_id = bp.get("blueprint_id") if isinstance(bp, dict) else None
            title = bp.get("title") if isinstance(bp, dict) else None
        else:
            bp_id = spec.get("title") if isinstance(spec, dict) else None
            title = spec.get("title") if isinstance(spec, dict) else None
        out.append({"job_id": jid, "state": state, "schema_version": schema_version, "blueprint_id": bp_id, "title": title})
    return {"jobs": out}


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    job_id = require_safe_job_id(job_id)
    paths = job_paths(job_id, job_root=_job_root())
    if not paths.job_spec.is_file():
        raise HTTPException(status_code=404, detail="not found")
    spec = load_job_spec(job_id, job_root=_job_root())
    events = load_job_events(job_id, job_root=_job_root())
    outputs_path = paths.outputs_dir / "outputs.json"
    outputs = {}
    if outputs_path.is_file():
        try:
            doc = json.loads(outputs_path.read_text(encoding="utf-8"))
            if isinstance(doc, dict):
                outputs = doc
        except Exception:
            outputs = {}
    return {"job_id": job_id, "spec": spec, "events": events, "outputs": outputs}
