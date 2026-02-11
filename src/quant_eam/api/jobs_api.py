from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from quant_eam.api.security import enforce_write_auth, require_safe_job_id
from quant_eam.contracts import validate as contracts_validate
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
    BudgetExceeded,
)

router = APIRouter()


def _job_root() -> Path:
    return default_job_root()


def _safe_policy_bundle_path(p: str) -> str:
    # Keep it simple: allow repo-relative paths like policies/policy_bundle_v1.yaml.
    # Real enforcement belongs to kernel (not UI). Here we only prevent traversal.
    if not p or p.startswith("/") or ".." in p or "\\" in p:
        raise HTTPException(status_code=400, detail="invalid policy_bundle_path")
    return p


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
