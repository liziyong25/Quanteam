from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from quant_eam.contracts import validate as contracts_validate
from quant_eam.policies.load import find_repo_root
from quant_eam.policies.load import load_yaml, sha256_file


def _utc_now_iso() -> str:
    sde = os.getenv("SOURCE_DATE_EPOCH")
    if sde and sde.isdigit():
        return datetime.fromtimestamp(int(sde), tz=timezone.utc).isoformat()
    return datetime.now(tz=timezone.utc).isoformat()


def default_job_root(*, artifact_root: Path | None = None) -> Path:
    jr = os.getenv("EAM_JOB_ROOT")
    if jr and jr.strip():
        return Path(jr)
    ar = artifact_root or Path(os.getenv("EAM_ARTIFACT_ROOT", "/artifacts"))
    return Path(ar) / "jobs"


def _canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def job_id_from_spec(spec: dict[str, Any]) -> str:
    h = hashlib.sha256(_canonical_bytes(spec)).hexdigest()
    return h[:12]


def _write_json_atomic(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / (path.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _jsonl_append(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            doc = json.loads(ln)
            if isinstance(doc, dict):
                out.append(doc)
    return out


@dataclass(frozen=True)
class JobPaths:
    job_root: Path
    job_dir: Path
    job_spec: Path
    blueprint: Path
    events: Path
    outputs_dir: Path
    logs_dir: Path


def job_paths(job_id: str, *, job_root: Path | None = None) -> JobPaths:
    jr = job_root or default_job_root()
    jd = Path(jr) / str(job_id)
    return JobPaths(
        job_root=Path(jr),
        job_dir=jd,
        job_spec=jd / "job_spec.json",
        blueprint=jd / "inputs" / "blueprint.json",
        events=jd / "events.jsonl",
        outputs_dir=jd / "outputs",
        logs_dir=jd / "logs",
    )


def resolve_repo_relative(path_str: str) -> Path:
    p = Path(path_str)
    if p.is_absolute():
        return p
    # Default resolve relative to repo root (policies/contracts locate use this convention).
    return find_repo_root() / p


def _resolve_policy_bundle_id_and_sha(*, policy_bundle_path: str) -> tuple[str, str]:
    pb_path = resolve_repo_relative(str(policy_bundle_path))
    if not pb_path.is_file():
        raise ValueError(f"policy bundle not found: {policy_bundle_path}")
    doc = load_yaml(pb_path)
    if not isinstance(doc, dict):
        raise ValueError("policy bundle must be a YAML mapping")
    bundle_id = str(doc.get("policy_bundle_id", "")).strip()
    if not bundle_id:
        raise ValueError("policy bundle missing policy_bundle_id")
    return bundle_id, sha256_file(pb_path)


def _ensure_policy_bundle_ref(
    *,
    job_id: str,
    policy_bundle_path: str,
    policy_bundle_id: str,
    policy_bundle_sha256: str,
    job_root: Path | None = None,
) -> None:
    paths = job_paths(job_id, job_root=job_root)
    ref_path = paths.outputs_dir / "policy_bundle_ref.json"
    _write_json_atomic(
        ref_path,
        {
            "policy_bundle_path": str(policy_bundle_path),
            "policy_bundle_id": str(policy_bundle_id),
            "policy_bundle_sha256": str(policy_bundle_sha256),
        },
    )
    write_outputs_index(
        job_id=job_id,
        updates={
            "policy_bundle_path": str(policy_bundle_path),
            "policy_bundle_id": str(policy_bundle_id),
            "policy_bundle_sha256": str(policy_bundle_sha256),
            "policy_bundle_ref_path": ref_path.as_posix(),
        },
        job_root=job_root,
    )


def create_job_from_blueprint(
    *,
    blueprint: dict[str, Any],
    snapshot_id: str,
    policy_bundle_path: str,
    extensions: dict[str, Any] | None = None,
    job_root: Path | None = None,
) -> dict[str, Any]:
    bundle_id, bundle_sha = _resolve_policy_bundle_id_and_sha(policy_bundle_path=policy_bundle_path)
    bp_bundle_id = str(blueprint.get("policy_bundle_id", "")).strip() if isinstance(blueprint, dict) else ""
    if bp_bundle_id and bp_bundle_id != bundle_id:
        raise ValueError("policy_bundle_id mismatch between blueprint JSON and policy bundle asset")

    spec: dict[str, Any] = {
        "schema_version": "job_spec_v1",
        "snapshot_id": str(snapshot_id),
        "policy_bundle_path": str(policy_bundle_path),
        "policy_bundle_id": bundle_id,
        "blueprint": blueprint,
    }
    if extensions:
        spec["extensions"] = extensions

    # Validate spec contract (also validates blueprint via $ref).
    code, msg = contracts_validate.validate_payload(spec)
    if code != contracts_validate.EXIT_OK:
        raise ValueError(f"invalid job_spec_v1: {msg}")

    job_id = job_id_from_spec(spec)
    paths = job_paths(job_id, job_root=job_root)

    if paths.job_spec.is_file() and paths.events.is_file():
        _ensure_policy_bundle_ref(
            job_id=job_id,
            policy_bundle_path=str(policy_bundle_path),
            policy_bundle_id=bundle_id,
            policy_bundle_sha256=bundle_sha,
            job_root=job_root,
        )
        return {"job_id": job_id, "status": "exists", "job_dir": paths.job_dir.as_posix()}

    paths.job_dir.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(paths.job_spec, spec)
    _write_json_atomic(paths.blueprint, blueprint)

    # First append-only event.
    ev = {
        "schema_version": "job_event_v2",
        "job_id": job_id,
        "event_type": "BLUEPRINT_SUBMITTED",
        "extensions": {"recorded_at": _utc_now_iso()},
    }
    code2, msg2 = contracts_validate.validate_payload(ev)
    if code2 != contracts_validate.EXIT_OK:
        raise ValueError(f"invalid job_event_v2: {msg2}")
    _jsonl_append(paths.events, ev)
    _ensure_policy_bundle_ref(
        job_id=job_id,
        policy_bundle_path=str(policy_bundle_path),
        policy_bundle_id=bundle_id,
        policy_bundle_sha256=bundle_sha,
        job_root=job_root,
    )

    return {"job_id": job_id, "status": "created", "job_dir": paths.job_dir.as_posix()}


def create_job_from_ideaspec(
    *,
    idea_spec: dict[str, Any],
    snapshot_id: str,
    policy_bundle_path: str,
    job_root: Path | None = None,
) -> dict[str, Any]:
    """Create an idea-based job where job_spec.json is the IdeaSpec itself (schema_version=idea_spec_v1).

    snapshot_id/policy_bundle_path are normalized into the IdeaSpec to keep job_id deterministic.
    """
    if not isinstance(idea_spec, dict):
        raise ValueError("idea_spec must be a JSON object")

    spec = dict(idea_spec)
    spec["schema_version"] = "idea_spec_v1"
    spec["snapshot_id"] = str(snapshot_id)
    spec["policy_bundle_path"] = str(policy_bundle_path)
    bundle_id, bundle_sha = _resolve_policy_bundle_id_and_sha(policy_bundle_path=policy_bundle_path)
    idea_bundle_id = str(spec.get("policy_bundle_id", "")).strip()
    if idea_bundle_id and idea_bundle_id != bundle_id:
        raise ValueError("policy_bundle_id mismatch between idea_spec and policy bundle asset")
    spec["policy_bundle_id"] = bundle_id

    code, msg = contracts_validate.validate_payload(spec)
    if code != contracts_validate.EXIT_OK:
        raise ValueError(f"invalid idea_spec_v1: {msg}")

    job_id = job_id_from_spec(spec)
    paths = job_paths(job_id, job_root=job_root)

    if paths.job_spec.is_file() and paths.events.is_file():
        _ensure_policy_bundle_ref(
            job_id=job_id,
            policy_bundle_path=str(policy_bundle_path),
            policy_bundle_id=bundle_id,
            policy_bundle_sha256=bundle_sha,
            job_root=job_root,
        )
        return {"job_id": job_id, "status": "exists", "job_dir": paths.job_dir.as_posix()}

    paths.job_dir.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(paths.job_spec, spec)
    # Keep a copy in inputs/ for UI rendering.
    _write_json_atomic(paths.job_dir / "inputs" / "idea_spec.json", spec)

    ev = {
        "schema_version": "job_event_v2",
        "job_id": job_id,
        "event_type": "IDEA_SUBMITTED",
        "extensions": {"recorded_at": _utc_now_iso()},
    }
    code2, msg2 = contracts_validate.validate_payload(ev)
    if code2 != contracts_validate.EXIT_OK:
        raise ValueError(f"invalid job_event_v2: {msg2}")
    _jsonl_append(paths.events, ev)
    _ensure_policy_bundle_ref(
        job_id=job_id,
        policy_bundle_path=str(policy_bundle_path),
        policy_bundle_id=bundle_id,
        policy_bundle_sha256=bundle_sha,
        job_root=job_root,
    )

    return {"job_id": job_id, "status": "created", "job_dir": paths.job_dir.as_posix()}


def append_event(
    *,
    job_id: str,
    event_type: str,
    message: str | None = None,
    outputs: dict[str, Any] | None = None,
    job_root: Path | None = None,
) -> dict[str, Any]:
    paths = job_paths(job_id, job_root=job_root)
    if not paths.job_spec.is_file():
        raise FileNotFoundError(f"job not found: {job_id}")

    ev: dict[str, Any] = {
        "schema_version": "job_event_v2",
        "job_id": str(job_id),
        "event_type": str(event_type),
        "extensions": {"recorded_at": _utc_now_iso()},
    }
    if message:
        ev["message"] = str(message)
    if outputs:
        ev["outputs"] = outputs

    code, msg = contracts_validate.validate_payload(ev)
    if code != contracts_validate.EXIT_OK:
        raise ValueError(f"invalid job_event_v2: {msg}")

    _jsonl_append(paths.events, ev)
    return ev


def load_job_spec(job_id: str, *, job_root: Path | None = None) -> dict[str, Any]:
    paths = job_paths(job_id, job_root=job_root)
    return json.loads(paths.job_spec.read_text(encoding="utf-8"))


def list_job_ids(*, job_root: Path | None = None) -> list[str]:
    jr = job_root or default_job_root()
    if not Path(jr).is_dir():
        return []
    out = [p.name for p in Path(jr).iterdir() if p.is_dir()]
    return sorted(out)


def load_job_events(job_id: str, *, job_root: Path | None = None) -> list[dict[str, Any]]:
    paths = job_paths(job_id, job_root=job_root)
    return list(iter_jsonl(paths.events))


def write_outputs_index(
    *,
    job_id: str,
    updates: dict[str, Any],
    job_root: Path | None = None,
) -> Path:
    paths = job_paths(job_id, job_root=job_root)
    idx_path = paths.outputs_dir / "outputs.json"
    existing: dict[str, Any] = {}
    if idx_path.is_file():
        try:
            doc = json.loads(idx_path.read_text(encoding="utf-8"))
            if isinstance(doc, dict):
                existing = doc
        except Exception:
            existing = {}
    merged = dict(existing)
    merged.update(updates)
    _write_json_atomic(idx_path, merged)
    return idx_path


class BudgetExceeded(RuntimeError):
    def __init__(self, message: str, *, outputs: dict[str, Any]) -> None:
        super().__init__(message)
        self.outputs = outputs


def _counts_toward_spawn_budget(ev: dict[str, Any]) -> bool:
    if str(ev.get("event_type")) != "SPAWNED":
        return False
    out = ev.get("outputs")
    if not isinstance(out, dict):
        return True
    # Rerun writes SPAWNED(action=rerun_requested) for audit, but it is not a child spawn.
    return str(out.get("action") or "").strip() != "rerun_requested"


def _load_sweep_best_params(*, job_id: str, job_root: Path | None = None) -> dict[str, Any]:
    """Load best sweep params from jobs/<job_id>/outputs/sweep/leaderboard.json.

    This is a workflow-level convenience; the source of truth remains the sweep evidence file.
    """
    paths = job_paths(job_id, job_root=job_root)
    lb = paths.outputs_dir / "sweep" / "leaderboard.json"
    if not lb.is_file():
        raise FileNotFoundError("no sweep leaderboard")
    doc = json.loads(lb.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError("invalid leaderboard json")
    best = doc.get("best")
    if not isinstance(best, dict):
        raise ValueError("invalid leaderboard.best")
    params = best.get("params")
    if not isinstance(params, dict) or not params:
        raise ValueError("no best params")
    return params


def spawn_child_job_from_sweep_best(
    *,
    base_job_id: str,
    job_root: Path | None = None,
) -> dict[str, Any]:
    """Spawn a child job from sweep best candidate params.

    Budget enforcement happens here so both API and UI can share the same guardrails.
    """
    paths = job_paths(base_job_id, job_root=job_root)
    if not paths.job_spec.is_file():
        raise FileNotFoundError(f"job not found: {base_job_id}")

    spec = load_job_spec(base_job_id, job_root=job_root)
    events = load_job_events(base_job_id, job_root=job_root)

    # Load best params (evidence) and apply to blueprint.strategy_spec.params.
    best_params = _load_sweep_best_params(job_id=base_job_id, job_root=job_root)

    # Budget policy path: prefer job_spec.budget_policy_path (idea jobs) else default.
    budget_policy_path = spec.get("budget_policy_path") or "policies/budget_policy_v1.yaml"
    ext = spec.get("extensions") if isinstance(spec, dict) else {}
    if isinstance(ext, dict) and isinstance(ext.get("sweep_spec"), dict):
        sp = ext.get("sweep_spec", {})
        if isinstance(sp, dict) and sp.get("budget_policy_path"):
            budget_policy_path = sp.get("budget_policy_path")
    bp_path = resolve_repo_relative(str(budget_policy_path))
    budget_doc = load_yaml(bp_path)
    if not isinstance(budget_doc, dict):
        raise ValueError("invalid budget policy")
    params = budget_doc.get("params") if isinstance(budget_doc.get("params"), dict) else {}

    # Budget: spawn limit per base job.
    spawn_count = sum(1 for ev in events if _counts_toward_spawn_budget(ev))
    max_spawn = int(params.get("max_spawn_per_job", 0)) if isinstance(params.get("max_spawn_per_job", 0), int) else 0
    if max_spawn and spawn_count >= max_spawn:
        stop_out = {"reason": "max_spawn_per_job", "limit": max_spawn, "current_spawn_count": spawn_count}
        append_event(job_id=base_job_id, event_type="STOPPED_BUDGET", message="STOP: spawn budget exhausted", outputs=stop_out, job_root=job_root)
        raise BudgetExceeded("spawn budget exhausted (max_spawn_per_job)", outputs=stop_out)

    # Iteration depth budget (lineage is optional; default generation=0).
    lineage = (ext.get("lineage") if isinstance(ext, dict) else {}) or {}
    gen = None
    if isinstance(lineage, dict) and isinstance(lineage.get("generation"), int):
        gen = int(lineage["generation"])
    elif isinstance(lineage, dict) and isinstance(lineage.get("iteration"), int):
        gen = int(lineage["iteration"])
    else:
        gen = 0

    max_iter = int(params.get("max_total_iterations", 0)) if isinstance(params.get("max_total_iterations", 0), int) else 0
    child_gen = gen + 1
    if max_iter and child_gen >= max_iter:
        stop_out = {
            "reason": "max_total_iterations",
            "limit": max_iter,
            "current_generation": gen,
            "attempted_child_generation": child_gen,
        }
        append_event(job_id=base_job_id, event_type="STOPPED_BUDGET", message="STOP: iteration budget exhausted", outputs=stop_out, job_root=job_root)
        raise BudgetExceeded("iteration budget exhausted (max_total_iterations)", outputs=stop_out)

    snapshot_id = str(spec.get("snapshot_id", "")).strip()
    policy_bundle_path = str(spec.get("policy_bundle_path", "")).strip() or "policies/policy_bundle_v1.yaml"
    if not snapshot_id:
        raise ValueError("missing snapshot_id in base job spec")

    sv = str(spec.get("schema_version") or "")
    if sv == "job_spec_v1":
        base_blueprint = spec.get("blueprint")
    else:
        # idea_spec_v1: prefer blueprint_final_path if present, else blueprint_draft_path.
        outputs_path = paths.outputs_dir / "outputs.json"
        if not outputs_path.is_file():
            raise FileNotFoundError("no outputs")
        outputs_doc = json.loads(outputs_path.read_text(encoding="utf-8"))
        outputs = outputs_doc if isinstance(outputs_doc, dict) else {}
        bp_final_path = outputs.get("blueprint_final_path")
        bp_draft_path = outputs.get("blueprint_draft_path")
        picked = bp_final_path if isinstance(bp_final_path, str) and Path(bp_final_path).is_file() else bp_draft_path
        if not isinstance(picked, str) or not Path(picked).is_file():
            raise FileNotFoundError("no blueprint found for sweep spawn")
        base_blueprint = json.loads(Path(picked).read_text(encoding="utf-8"))

    if not isinstance(base_blueprint, dict):
        raise ValueError("invalid blueprint in base job")

    child_blueprint = dict(base_blueprint)
    strat = child_blueprint.get("strategy_spec")
    if not isinstance(strat, dict):
        raise ValueError("base blueprint missing strategy_spec")
    strat2 = dict(strat)
    p0 = strat2.get("params") if isinstance(strat2.get("params"), dict) else {}
    p1 = dict(p0)
    p1.update(best_params)
    strat2["params"] = p1
    child_blueprint["strategy_spec"] = strat2

    # Metadata-only extensions for audit.
    ext_bp = child_blueprint.get("extensions") if isinstance(child_blueprint.get("extensions"), dict) else {}
    ext_bp2 = dict(ext_bp)
    ext_bp2["sweep_best_from"] = {"base_job_id": base_job_id, "params": dict(best_params)}
    child_blueprint["extensions"] = ext_bp2

    root_job_id = str(lineage.get("root_job_id") or base_job_id) if isinstance(lineage, dict) else base_job_id
    child_extensions = {
        "lineage": {
            "root_job_id": root_job_id,
            "parent_job_id": base_job_id,
            "generation": child_gen,
            "iteration": child_gen,
        },
        "spawned_from": {"base_job_id": base_job_id, "sweep_best": True},
    }

    res = create_job_from_blueprint(
        blueprint=child_blueprint,
        snapshot_id=snapshot_id,
        policy_bundle_path=str(policy_bundle_path),
        extensions=child_extensions,
        job_root=job_root,
    )

    append_event(
        job_id=base_job_id,
        event_type="SPAWNED",
        outputs={"child_job_id": res["job_id"], "generation": child_gen, "source": "sweep_best"},
        job_root=job_root,
    )

    return {"base_job_id": base_job_id, "child_job_id": res["job_id"], "status": res["status"], "params": best_params}

def spawn_child_job_from_proposal(
    *,
    base_job_id: str,
    proposal_id: str,
    job_root: Path | None = None,
) -> dict[str, Any]:
    """Spawn a child job from a previously generated improvement proposal.

    Budget enforcement happens here so both API and UI can share the same guardrails.
    """
    paths = job_paths(base_job_id, job_root=job_root)
    if not paths.job_spec.is_file():
        raise FileNotFoundError(f"job not found: {base_job_id}")

    spec = load_job_spec(base_job_id, job_root=job_root)
    events = load_job_events(base_job_id, job_root=job_root)

    outputs_path = paths.outputs_dir / "outputs.json"
    if not outputs_path.is_file():
        raise FileNotFoundError("no outputs")
    outputs_doc = json.loads(outputs_path.read_text(encoding="utf-8"))
    outputs = outputs_doc if isinstance(outputs_doc, dict) else {}

    proposals_path = outputs.get("improvement_proposals_path")
    if not isinstance(proposals_path, str) or not Path(proposals_path).is_file():
        raise FileNotFoundError("no proposals")
    proposals_doc = json.loads(Path(proposals_path).read_text(encoding="utf-8"))
    if not isinstance(proposals_doc, dict):
        raise ValueError("invalid proposals doc")

    budget_policy_path = outputs.get("budget_policy_path") or spec.get("budget_policy_path") or "policies/budget_policy_v1.yaml"
    bp_path = resolve_repo_relative(str(budget_policy_path))
    budget_doc = load_yaml(bp_path)
    if not isinstance(budget_doc, dict):
        raise ValueError("invalid budget policy")
    params = budget_doc.get("params") if isinstance(budget_doc.get("params"), dict) else {}

    # Budget: spawn limit per base job.
    spawn_count = sum(1 for ev in events if _counts_toward_spawn_budget(ev))
    max_spawn = int(params.get("max_spawn_per_job", 0)) if isinstance(params.get("max_spawn_per_job", 0), int) else 0
    if max_spawn and spawn_count >= max_spawn:
        stop_out = {"reason": "max_spawn_per_job", "limit": max_spawn, "current_spawn_count": spawn_count}
        append_event(job_id=base_job_id, event_type="STOPPED_BUDGET", message="STOP: spawn budget exhausted", outputs=stop_out, job_root=job_root)
        raise BudgetExceeded("spawn budget exhausted (max_spawn_per_job)", outputs=stop_out)

    # Iteration depth budget (lineage is optional; default generation=0).
    ext = spec.get("extensions") if isinstance(spec, dict) else {}
    lineage = (ext.get("lineage") if isinstance(ext, dict) else {}) or {}
    gen = None
    if isinstance(lineage, dict) and isinstance(lineage.get("generation"), int):
        gen = int(lineage["generation"])
    elif isinstance(lineage, dict) and isinstance(lineage.get("iteration"), int):
        gen = int(lineage["iteration"])
    else:
        gen = 0

    max_iter = int(params.get("max_total_iterations", 0)) if isinstance(params.get("max_total_iterations", 0), int) else 0
    child_gen = gen + 1
    if max_iter and child_gen >= max_iter:
        stop_out = {
            "reason": "max_total_iterations",
            "limit": max_iter,
            "current_generation": gen,
            "attempted_child_generation": child_gen,
        }
        append_event(job_id=base_job_id, event_type="STOPPED_BUDGET", message="STOP: iteration budget exhausted", outputs=stop_out, job_root=job_root)
        raise BudgetExceeded("iteration budget exhausted (max_total_iterations)", outputs=stop_out)

    proposals = proposals_doc.get("proposals")
    if not isinstance(proposals, list):
        raise ValueError("invalid proposals format")
    picked = None
    for p in proposals:
        if isinstance(p, dict) and str(p.get("proposal_id", "")) == str(proposal_id):
            picked = p
            break
    if not picked or not isinstance(picked, dict):
        raise FileNotFoundError("proposal_id not found")
    # Proposals/extensions must not act as policy override knobs.
    pext = picked.get("extensions")
    if isinstance(pext, dict):
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
        hit = [k for k in pext.keys() if str(k) in forbidden]
        if hit:
            raise ValueError(f"proposal.extensions must not override policies (forbidden keys: {hit})")
    blueprint = picked.get("blueprint_draft_json")
    if not isinstance(blueprint, dict):
        raise ValueError("invalid blueprint in proposal")

    snapshot_id = str(spec.get("snapshot_id", "")).strip()
    policy_bundle_path = str(spec.get("policy_bundle_path", "")).strip() or "policies/policy_bundle_v1.yaml"
    if not snapshot_id:
        raise ValueError("missing snapshot_id in base job spec")

    root_job_id = str(lineage.get("root_job_id") or base_job_id) if isinstance(lineage, dict) else base_job_id
    child_extensions = {
        "lineage": {
            "root_job_id": root_job_id,
            "parent_job_id": base_job_id,
            "generation": child_gen,
            # Backward-compatible alias used by Phase-13 code/tests.
            "iteration": child_gen,
        },
        "spawned_from": {
            "base_job_id": base_job_id,
            "proposal_id": str(proposal_id),
        },
    }

    res = create_job_from_blueprint(
        blueprint=blueprint,
        snapshot_id=snapshot_id,
        policy_bundle_path=str(policy_bundle_path),
        extensions=child_extensions,
        job_root=job_root,
    )

    append_event(
        job_id=base_job_id,
        event_type="SPAWNED",
        outputs={"child_job_id": res["job_id"], "proposal_id": str(proposal_id), "generation": child_gen},
        job_root=job_root,
    )

    return {"base_job_id": base_job_id, "child_job_id": res["job_id"], "status": res["status"]}
