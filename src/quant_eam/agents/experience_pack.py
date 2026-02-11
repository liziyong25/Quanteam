from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from quant_eam.jobstore.store import default_job_root, write_outputs_index
from quant_eam.registry.experience_retrieval import ExperienceQuery, build_experience_pack_payload


def _write_json_atomic(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / (path.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def experience_pack_path_for_job(job_id: str, *, job_root: Path | None = None) -> Path:
    jr = Path(job_root) if job_root is not None else default_job_root()
    return jr / str(job_id) / "outputs" / "experience" / "experience_pack.json"


def ensure_experience_pack_for_job(
    *,
    job_id: str,
    query: str,
    symbols: list[str] | None = None,
    frequency: str | None = None,
    tags: list[str] | None = None,
    top_k: int = 5,
    job_root: Path | None = None,
) -> Path:
    """Append-only: write jobs/<job_id>/outputs/experience/experience_pack.json if missing."""
    p = experience_pack_path_for_job(job_id, job_root=job_root)
    if p.is_file():
        return p

    q = ExperienceQuery(query=query, symbols=symbols, frequency=frequency, tags=tags, top_k=top_k)
    payload = build_experience_pack_payload(q=q)
    payload["job_id"] = str(job_id)
    payload.setdefault("extensions", {})
    if isinstance(payload["extensions"], dict):
        payload["extensions"]["writer"] = "experience_retrieval_v1"

    _write_json_atomic(p, payload)

    # Convenience pointer for UI/API; keeps job outputs discoverable.
    try:
        jr = Path(job_root) if job_root is not None else default_job_root()
        write_outputs_index(job_id=job_id, updates={"experience_pack_path": p.as_posix()}, job_root=jr)
    except Exception:
        pass

    return p


def load_experience_pack_for_job(job_id: str, *, job_root: Path | None = None) -> dict[str, Any] | None:
    p = experience_pack_path_for_job(job_id, job_root=job_root)
    if not p.is_file():
        return None
    try:
        doc = _load_json(p)
        return doc if isinstance(doc, dict) else None
    except Exception:
        return None


def infer_job_id_from_input_path(input_path: Path) -> str | None:
    """Best-effort inference for agents invoked with job_spec.json as input."""
    try:
        input_path = Path(input_path)
    except Exception:
        return None
    if input_path.name != "job_spec.json":
        return None
    # jobs/<job_id>/job_spec.json
    job_id = input_path.parent.name
    if not job_id or len(job_id) < 8:
        return None
    return job_id


def retrieval_enabled() -> bool:
    # Default ON (Phase-29). Allow disabling to reduce prompt/input size.
    v = str(os.getenv("EAM_EXPERIENCE_RETRIEVAL", "on")).strip().lower()
    return v not in ("0", "off", "false", "no")

