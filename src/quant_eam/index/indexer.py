from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from quant_eam.api.roots import artifact_root, dossiers_root, registry_root
from quant_eam.jobstore.store import default_job_root
from quant_eam.registry.storage import registry_paths


SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def _is_safe_id(s: str) -> bool:
    if not isinstance(s, str):
        return False
    if not s or s.startswith(".") or ".." in s or "/" in s or "\\" in s:
        return False
    return bool(SAFE_ID_RE.match(s))


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_json_line(obj: dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _jsonl_existing_ids(path: Path, key: str) -> set[str]:
    if not path.is_file():
        return set()
    out: set[str] = set()
    with path.open("r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                doc = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if isinstance(doc, dict) and isinstance(doc.get(key), str):
                out.add(str(doc[key]))
    return out


def _append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(_canonical_json_line(obj) + "\n")


def _utc_now_iso() -> str:
    # Deterministic in tests/CI via SOURCE_DATE_EPOCH.
    import time

    sde = os.getenv("SOURCE_DATE_EPOCH")
    if sde and sde.isdigit():
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(sde)))
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@dataclass(frozen=True)
class IndexPaths:
    root: Path
    runs_index: Path
    jobs_index: Path


def index_paths(*, artifact_root_dir: Path | None = None) -> IndexPaths:
    ar = Path(artifact_root_dir) if artifact_root_dir is not None else artifact_root()
    idx = ar / "index"
    return IndexPaths(root=idx, runs_index=idx / "runs_index.jsonl", jobs_index=idx / "jobs_index.jsonl")


def _scan_cards_by_run_id() -> dict[str, list[str]]:
    """Return mapping run_id -> [card_id,...] (sorted)."""
    rr = registry_root()
    paths = registry_paths(rr)
    m: dict[str, list[str]] = {}
    if not paths.cards_dir.is_dir():
        return m
    for p in sorted(paths.cards_dir.glob("*.json")):
        if not p.is_file():
            continue
        try:
            doc = _load_json(p)
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(doc, dict):
            continue
        rid = str(doc.get("primary_run_id") or "").strip()
        cid = str(doc.get("card_id") or p.stem).strip()
        if not (_is_safe_id(rid) and _is_safe_id(cid)):
            continue
        m.setdefault(rid, []).append(cid)
    for rid in list(m.keys()):
        m[rid] = sorted(set(m[rid]))
    return m


def build_runs_index(*, artifact_root_dir: Path | None = None, limit: int | None = None) -> dict[str, Any]:
    """Append-only build for runs_index.jsonl (id-deduped).

    Returns summary dict for logging/tests.
    """
    idxp = index_paths(artifact_root_dir=artifact_root_dir)
    existing = _jsonl_existing_ids(idxp.runs_index, "run_id")
    cards_by_run = _scan_cards_by_run_id()

    root = dossiers_root()
    if not root.is_dir():
        return {"indexed": 0, "skipped_existing": 0, "total_seen": 0, "index_path": idxp.runs_index.as_posix()}

    run_dirs = sorted([p for p in root.iterdir() if p.is_dir()], key=lambda p: p.name)
    total_seen = 0
    indexed = 0
    skipped = 0

    for d in run_dirs:
        rid = d.name
        if not _is_safe_id(rid):
            continue
        total_seen += 1
        if rid in existing:
            skipped += 1
            continue

        # Minimal, deterministic fields.
        snapshot_id = None
        policy_bundle_id = None
        overall_pass = None

        man_p = d / "dossier_manifest.json"
        cfg_p = d / "config_snapshot.json"
        gate_p = d / "gate_results.json"
        try:
            if man_p.is_file():
                man = _load_json(man_p)
                if isinstance(man, dict):
                    snapshot_id = str(man.get("data_snapshot_id") or "").strip() or None
            if cfg_p.is_file():
                cfg = _load_json(cfg_p)
                if isinstance(cfg, dict):
                    policy_bundle_id = str(cfg.get("policy_bundle_id") or "").strip() or None
                    rs = cfg.get("runspec") if isinstance(cfg.get("runspec"), dict) else {}
                    if isinstance(rs, dict) and not policy_bundle_id:
                        policy_bundle_id = str(rs.get("policy_bundle_id") or "").strip() or None
            if gate_p.is_file():
                gate = _load_json(gate_p)
                if isinstance(gate, dict) and "overall_pass" in gate:
                    overall_pass = bool(gate.get("overall_pass"))
        except Exception:  # noqa: BLE001
            # Index should be best-effort; do not fail build.
            snapshot_id = snapshot_id or None
            policy_bundle_id = policy_bundle_id or None
            overall_pass = overall_pass if isinstance(overall_pass, bool) else None

        obj: dict[str, Any] = {
            "schema_version": "runs_index_v1",
            "indexed_at": _utc_now_iso(),
            "run_id": rid,
            "snapshot_id": snapshot_id,
            "policy_bundle_id": policy_bundle_id,
            "overall_pass": overall_pass,
            # Stable relative refs (prevent traversal).
            "dossier_path": f"dossiers/{rid}",
            "card_ids": cards_by_run.get(rid, []),
        }
        _append_jsonl(idxp.runs_index, obj)
        existing.add(rid)
        indexed += 1

        if limit is not None and indexed >= int(limit):
            break

    return {
        "indexed": indexed,
        "skipped_existing": skipped,
        "total_seen": total_seen,
        "index_path": idxp.runs_index.as_posix(),
    }


def _job_last_state(events: list[dict[str, Any]]) -> dict[str, Any]:
    if not events:
        return {"last_event_type": None, "last_recorded_at": None, "waiting_step": None}
    last = events[-1] if isinstance(events[-1], dict) else {}
    et = str(last.get("event_type") or "") or None
    rec_at = None
    ext = last.get("extensions") if isinstance(last.get("extensions"), dict) else {}
    if isinstance(ext, dict) and isinstance(ext.get("recorded_at"), str):
        rec_at = str(ext.get("recorded_at"))

    waiting_step = None
    if et == "WAITING_APPROVAL":
        outs = last.get("outputs") if isinstance(last.get("outputs"), dict) else {}
        if isinstance(outs, dict) and isinstance(outs.get("step"), str):
            waiting_step = str(outs.get("step"))
    return {"last_event_type": et, "last_recorded_at": rec_at, "waiting_step": waiting_step}


def _extract_llm_evidence_summary(outputs_idx: dict[str, Any]) -> dict[str, Any]:
    """Best-effort, minimal summary of agent/LLM evidence (no heavy reads)."""
    if not isinstance(outputs_idx, dict):
        return {"agent_run_paths": [], "agent_run_count": 0}

    paths: list[str] = []
    for k, v in outputs_idx.items():
        if not isinstance(k, str):
            continue
        if not k.endswith("_agent_run_path"):
            continue
        if isinstance(v, str) and v.strip():
            paths.append(v)

    paths = sorted(set(paths))
    return {"agent_run_paths": paths, "agent_run_count": int(len(paths))}


def build_jobs_index(*, artifact_root_dir: Path | None = None, limit: int | None = None) -> dict[str, Any]:
    idxp = index_paths(artifact_root_dir=artifact_root_dir)
    existing = _jsonl_existing_ids(idxp.jobs_index, "job_id")

    jr = default_job_root(artifact_root=Path(artifact_root_dir) if artifact_root_dir is not None else None)
    jr = Path(jr)
    if not jr.is_dir():
        return {"indexed": 0, "skipped_existing": 0, "total_seen": 0, "index_path": idxp.jobs_index.as_posix()}

    job_dirs = sorted([p for p in jr.iterdir() if p.is_dir()], key=lambda p: p.name)
    total_seen = 0
    indexed = 0
    skipped = 0

    for d in job_dirs:
        jid = d.name
        if not _is_safe_id(jid):
            continue
        total_seen += 1
        if jid in existing:
            skipped += 1
            continue

        spec_p = d / "job_spec.json"
        events_p = d / "events.jsonl"
        outputs_p = d / "outputs" / "outputs.json"

        schema_version = None
        snapshot_id = None
        policy_bundle_id = None
        outputs_idx: dict[str, Any] = {}
        state = {"last_event_type": None, "last_recorded_at": None, "waiting_step": None}

        try:
            if spec_p.is_file():
                spec = _load_json(spec_p)
                if isinstance(spec, dict):
                    schema_version = str(spec.get("schema_version") or "").strip() or None
                    snapshot_id = str(spec.get("snapshot_id") or "").strip() or None
                    policy_bundle_id = str(spec.get("policy_bundle_id") or "").strip() or None

            if outputs_p.is_file():
                doc = _load_json(outputs_p)
                if isinstance(doc, dict):
                    outputs_idx = doc
                    if not snapshot_id and isinstance(doc.get("snapshot_id"), str):
                        snapshot_id = str(doc.get("snapshot_id"))
                    if not policy_bundle_id and isinstance(doc.get("policy_bundle_id"), str):
                        policy_bundle_id = str(doc.get("policy_bundle_id"))

            # Events: only need last state. Keep it cheap.
            events: list[dict[str, Any]] = []
            if events_p.is_file():
                with events_p.open("r", encoding="utf-8") as f:
                    for ln in f:
                        ln = ln.strip()
                        if not ln:
                            continue
                        try:
                            ev = json.loads(ln)
                        except json.JSONDecodeError:
                            continue
                        if isinstance(ev, dict):
                            events.append(ev)
            state = _job_last_state(events)
        except Exception:  # noqa: BLE001
            pass

        obj: dict[str, Any] = {
            "schema_version": "jobs_index_v1",
            "indexed_at": _utc_now_iso(),
            "job_id": jid,
            "job_schema_version": schema_version,
            "snapshot_id": snapshot_id,
            "policy_bundle_id": policy_bundle_id,
            "state": state,
            "llm_evidence": _extract_llm_evidence_summary(outputs_idx),
            "job_dir": f"jobs/{jid}",
        }
        _append_jsonl(idxp.jobs_index, obj)
        existing.add(jid)
        indexed += 1
        if limit is not None and indexed >= int(limit):
            break

    return {
        "indexed": indexed,
        "skipped_existing": skipped,
        "total_seen": total_seen,
        "index_path": idxp.jobs_index.as_posix(),
    }


def build_all_indexes(*, artifact_root_dir: Path | None = None) -> dict[str, Any]:
    runs = build_runs_index(artifact_root_dir=artifact_root_dir)
    jobs = build_jobs_index(artifact_root_dir=artifact_root_dir)
    return {"runs": runs, "jobs": jobs}

