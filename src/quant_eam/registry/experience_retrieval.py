from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from quant_eam.api.roots import dossiers_root, registry_root
from quant_eam.index.reader import list_runs_from_index
from quant_eam.registry.storage import registry_paths


_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _utc_now_iso() -> str:
    sde = os.getenv("SOURCE_DATE_EPOCH")
    if sde and sde.isdigit():
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(sde)))
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _tokenize(s: str) -> list[str]:
    s = str(s or "").lower()
    toks = [m.group(0) for m in _TOKEN_RE.finditer(s)]
    toks = [t for t in toks if t]
    # Stable unique order.
    seen: set[str] = set()
    out: list[str] = []
    for t in toks:
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def _safe_str(x: Any) -> str:
    return str(x) if isinstance(x, (str, int, float, bool)) or x is None else json.dumps(x, sort_keys=True)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for ln in path.read_text(encoding="utf-8").splitlines():
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


def _effective_status(card_base: dict[str, Any], events: list[dict[str, Any]]) -> str:
    status = str(card_base.get("status") or "draft")
    for ev in events:
        if str(ev.get("event_type") or "") == "PROMOTED":
            ns = str(ev.get("new_status") or "")
            if ns:
                status = ns
    return status or "draft"


def _load_run_symbols_from_dossier(run_id: str, dossier_path_hint: str | None = None) -> list[str]:
    # Prefer card evidence dossier_path when present; fallback to standard dossiers_root/run_id.
    d: Path | None = None
    if isinstance(dossier_path_hint, str) and dossier_path_hint.strip():
        try:
            d = Path(dossier_path_hint)
        except Exception:
            d = None
    if d is None or not d.is_dir():
        try:
            d = dossiers_root() / run_id
        except Exception:
            d = None
    if d is None or not d.is_dir():
        return []

    cfg_p = d / "config_snapshot.json"
    if not cfg_p.is_file():
        return []
    try:
        cfg = _load_json(cfg_p)
    except Exception:
        return []
    if not isinstance(cfg, dict):
        return []
    runspec = cfg.get("runspec") if isinstance(cfg.get("runspec"), dict) else {}
    ext = runspec.get("extensions") if isinstance(runspec, dict) and isinstance(runspec.get("extensions"), dict) else {}
    syms = ext.get("symbols") if isinstance(ext, dict) and isinstance(ext.get("symbols"), list) else []
    out = [str(s) for s in syms if str(s).strip()]
    return sorted(set(out))


@dataclass(frozen=True)
class ExperienceQuery:
    query: str
    symbols: list[str] | None = None
    frequency: str | None = None
    tags: list[str] | None = None
    top_k: int = 5


@dataclass(frozen=True)
class ExperienceMatch:
    card_id: str
    run_id: str
    score: float
    effective_status: str
    title: str
    policy_bundle_id: str | None
    symbols: list[str]
    ranking_explain: list[dict[str, Any]]


def search_experience_cards(*, q: ExperienceQuery, reg_root: Path | None = None) -> list[ExperienceMatch]:
    """Deterministic, evidence-first registry search (no embeddings, no network IO)."""
    reg_root = reg_root or registry_root()
    paths = registry_paths(reg_root)
    cards_dir = paths.cards_dir
    if not cards_dir.is_dir():
        return []

    top_k = max(1, min(50, int(q.top_k)))
    query_text = str(q.query or "")
    query_tokens = _tokenize(query_text)
    tag_tokens = []
    if isinstance(q.tags, list):
        for t in q.tags:
            tag_tokens.extend(_tokenize(str(t)))
    # Merge tag tokens into query tokens (lower weight but same deterministic behavior).
    merged_tokens = query_tokens + [t for t in tag_tokens if t not in query_tokens]

    wanted_symbols = []
    if isinstance(q.symbols, list):
        wanted_symbols = [str(s).strip() for s in q.symbols if str(s).strip()]
    wanted_set = {s.upper() for s in wanted_symbols}

    wanted_freq = str(q.frequency).strip() if isinstance(q.frequency, str) and q.frequency.strip() else None

    # Optional index accelerators.
    runs_index_rows = list_runs_from_index(limit=2000)
    run_id_to_index: dict[str, dict[str, Any]] = {}
    for r in runs_index_rows:
        rid = r.get("run_id")
        if isinstance(rid, str) and rid:
            run_id_to_index[rid] = r

    matches: list[ExperienceMatch] = []

    for d in sorted([p for p in cards_dir.iterdir() if p.is_dir()], key=lambda p: p.name):
        card_json = d / "card_v1.json"
        if not card_json.is_file():
            continue
        try:
            base = _load_json(card_json)
        except Exception:
            continue
        if not isinstance(base, dict):
            continue
        evs = _read_jsonl(d / "events.jsonl")
        eff = _effective_status(base, evs)

        card_id = str(base.get("card_id") or d.name)
        title = str(base.get("title") or "")
        run_id = str(base.get("primary_run_id") or "")
        pb = str(base.get("policy_bundle_id") or "").strip() or None
        app = base.get("applicability") if isinstance(base.get("applicability"), dict) else {}
        freq = str(app.get("freq") or "").strip() or None
        evidence = base.get("evidence") if isinstance(base.get("evidence"), dict) else {}
        dossier_path_hint = str(evidence.get("dossier_path") or "").strip() or None

        # Pull symbols from dossier config snapshot (best-effort).
        sym_list = _load_run_symbols_from_dossier(run_id=run_id, dossier_path_hint=dossier_path_hint)
        sym_set = {s.upper() for s in sym_list}

        # Ranking: simple token match scoring + optional structured matches.
        # Keep weights conservative; output must explain why.
        score = 0.0
        explain: list[dict[str, Any]] = []

        def add(reason: str, *, field: str, token: str | None, weight: float) -> None:
            nonlocal score
            score += float(weight)
            explain.append({"reason": reason, "field": field, "token": token, "weight": float(weight)})

        title_l = title.lower()
        # tags: read from extensions.tags when present (metadata only).
        ext = base.get("extensions") if isinstance(base.get("extensions"), dict) else {}
        tags = ext.get("tags") if isinstance(ext.get("tags"), list) else []
        tags_l = " ".join([str(t) for t in tags]).lower()

        notes_l = " ".join([str(ev.get("notes") or "") for ev in evs if isinstance(ev, dict)]).lower()

        for tok in merged_tokens:
            if tok and tok in title_l:
                add("token_in_title", field="title", token=tok, weight=5.0)
            if tok and tok in tags_l:
                add("token_in_tags", field="tags", token=tok, weight=3.0)
            if tok and tok in notes_l:
                add("token_in_notes", field="notes", token=tok, weight=2.0)
            # symbols: allow matching query tokens (e.g. "AAA") as well.
            if tok and tok.upper() in sym_set:
                add("token_in_symbols", field="symbols", token=tok.upper(), weight=4.0)

        # Structured symbol match.
        if wanted_set and sym_set:
            common = sorted(wanted_set & sym_set)
            if common:
                add("symbols_intersection", field="symbols", token=",".join(common), weight=6.0)

        # Frequency match.
        if wanted_freq and freq and wanted_freq == freq:
            add("frequency_match", field="frequency", token=wanted_freq, weight=2.0)

        # Favor champion/challenger slightly when all else equal.
        if eff == "champion":
            add("status_bonus", field="effective_status", token=eff, weight=0.2)
        elif eff == "challenger":
            add("status_bonus", field="effective_status", token=eff, weight=0.1)

        # If no match at all, skip unless empty query (then include for deterministic browse).
        if (not merged_tokens) and (not wanted_set) and (not wanted_freq):
            add("empty_query", field="query", token=None, weight=0.0)
        elif score <= 0.0:
            continue

        # Stable explain ordering.
        explain.sort(key=lambda r: (-float(r.get("weight") or 0.0), str(r.get("field") or ""), str(r.get("token") or "")))

        # If index is available, prefer canonical policy_bundle_id from index when present.
        idx_row = run_id_to_index.get(run_id, {})
        if isinstance(idx_row, dict) and isinstance(idx_row.get("policy_bundle_id"), str) and idx_row.get("policy_bundle_id"):
            pb = str(idx_row.get("policy_bundle_id"))

        matches.append(
            ExperienceMatch(
                card_id=card_id,
                run_id=run_id,
                score=float(score),
                effective_status=eff,
                title=title,
                policy_bundle_id=pb,
                symbols=sym_list,
                ranking_explain=explain,
            )
        )

    # Deterministic ranking + tie-breaks.
    status_rank = {"champion": 0, "challenger": 1, "draft": 2, "retired": 3}

    def key(m: ExperienceMatch) -> tuple:
        return (
            -float(m.score),
            int(status_rank.get(m.effective_status, 9)),
            str(m.card_id),
        )

    matches.sort(key=key)
    return matches[:top_k]


def build_experience_pack_payload(*, q: ExperienceQuery, reg_root: Path | None = None) -> dict[str, Any]:
    matches = search_experience_cards(q=q, reg_root=reg_root)
    return {
        "schema_version": "experience_pack_v1",
        "created_at": _utc_now_iso(),
        "query_input": {
            "query": str(q.query or ""),
            "symbols": list(q.symbols) if isinstance(q.symbols, list) else [],
            "frequency": (str(q.frequency) if isinstance(q.frequency, str) else None),
            "tags": list(q.tags) if isinstance(q.tags, list) else [],
            "top_k": int(q.top_k),
        },
        "results": [
            {
                "card_id": m.card_id,
                "run_id": m.run_id,
                "title": m.title,
                "effective_status": m.effective_status,
                "score": m.score,
                "policy_bundle_id": m.policy_bundle_id,
                "symbols": m.symbols,
                "ranking_explain": m.ranking_explain,
            }
            for m in matches
        ],
    }

