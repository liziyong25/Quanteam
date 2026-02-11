from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from quant_eam.index.indexer import _is_safe_id, index_paths  # internal helpers (Phase-25)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                doc = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if isinstance(doc, dict):
                out.append(doc)
    return out


def list_runs_from_index(*, artifact_root_dir: Path | None = None, limit: int = 30) -> list[dict[str, Any]]:
    idxp = index_paths(artifact_root_dir=artifact_root_dir)
    rows = _read_jsonl(idxp.runs_index)
    # Newest first by append order.
    rows.reverse()
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for r in rows:
        rid = r.get("run_id")
        if not isinstance(rid, str) or not _is_safe_id(rid):
            continue
        if rid in seen:
            continue
        seen.add(rid)
        out.append(r)
        if len(out) >= int(limit):
            break
    return out


def list_jobs_from_index(*, artifact_root_dir: Path | None = None, limit: int = 50) -> list[dict[str, Any]]:
    idxp = index_paths(artifact_root_dir=artifact_root_dir)
    rows = _read_jsonl(idxp.jobs_index)
    rows.reverse()
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for r in rows:
        jid = r.get("job_id")
        if not isinstance(jid, str) or not _is_safe_id(jid):
            continue
        if jid in seen:
            continue
        seen.add(jid)
        out.append(r)
        if len(out) >= int(limit):
            break
    return out

