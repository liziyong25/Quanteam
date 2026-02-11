from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from quant_eam.contracts import validate as contracts_validate
from quant_eam.registry.errors import RegistryInvalid
from quant_eam.registry.storage import RegistryPaths, _jsonl_append, iter_jsonl, new_recorded_at, registry_paths, sha256_file
from quant_eam.registry.triallog import get_trial


ALLOWED_STATUSES = ["draft", "challenger", "champion", "retired"]
TRANSITIONS: dict[str, str] = {
    "draft": "challenger",
    "challenger": "champion",
    "champion": "retired",
}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _card_id_from_run(run_id: str) -> str:
    return f"card_{run_id}"


def _card_dir(paths: RegistryPaths, card_id: str) -> Path:
    return paths.cards_dir / card_id


def _card_json_path(paths: RegistryPaths, card_id: str) -> Path:
    return _card_dir(paths, card_id) / "card_v1.json"


def _card_events_path(paths: RegistryPaths, card_id: str) -> Path:
    return _card_dir(paths, card_id) / "events.jsonl"


def _compute_effective_status(card_base: dict[str, Any], events: list[dict[str, Any]]) -> str:
    status = str(card_base.get("status", "draft"))
    for ev in events:
        if str(ev.get("event_type", "")) == "PROMOTED":
            ns = str(ev.get("new_status", ""))
            if ns in ALLOWED_STATUSES:
                status = ns
    return status if status in ALLOWED_STATUSES else "draft"


def create_card_from_run(
    *,
    run_id: str,
    registry_root: Path,
    title: str,
    if_exists: str = "fail",  # "fail" or "noop"
) -> dict[str, Any]:
    paths = registry_paths(registry_root)
    paths.registry_root.mkdir(parents=True, exist_ok=True)
    run_id = str(run_id).strip()
    if not run_id:
        raise RegistryInvalid("run_id must be non-empty")
    title = str(title).strip()
    if not title:
        raise RegistryInvalid("title must be non-empty")

    trial = get_trial(registry_root=paths.registry_root, run_id=run_id)
    if trial is None:
        raise RegistryInvalid("trial not found in trial_log.jsonl; run record-trial first")
    if not bool(trial.get("overall_pass")):
        raise RegistryInvalid("cannot create card: overall_pass is false (Gate PASS required)")

    card_id = _card_id_from_run(run_id)
    card_dir = _card_dir(paths, card_id)
    card_json = _card_json_path(paths, card_id)
    events_jsonl = _card_events_path(paths, card_id)

    if card_json.exists():
        if if_exists == "noop":
            base = _load_json(card_json)
            evs = list(iter_jsonl(events_jsonl))
            if isinstance(base, dict):
                base2 = dict(base)
                base2["effective_status"] = _compute_effective_status(base, evs)
                return base2
        raise RegistryInvalid(f"card already exists: {card_id}")

    dossier_path = str(trial.get("dossier_path", "")).strip()
    gate_results_path = str(trial.get("gate_results_path", "")).strip()
    policy_bundle_id = str(trial.get("policy_bundle_id", "")).strip()
    if not dossier_path or not gate_results_path or not policy_bundle_id:
        raise RegistryInvalid("trial missing required evidence paths or policy_bundle_id")

    # Evidence must reference dossier artifacts (minimum set).
    key_artifacts = [
        "dossier_manifest.json",
        "config_snapshot.json",
        "metrics.json",
        "curve.csv",
        "trades.csv",
        "gate_results.json",
    ]

    card: dict[str, Any] = {
        "schema_version": "experience_card_v1",
        "card_id": card_id,
        "created_at": new_recorded_at(),
        "title": title,
        "status": "draft",
        "primary_run_id": run_id,
        "policy_bundle_id": policy_bundle_id,
        "evidence": {
            "run_id": run_id,
            "dossier_path": dossier_path,
            "gate_results_path": gate_results_path,
            "key_artifacts": key_artifacts,
        },
        "applicability": {
            "universe_hint": "unknown",
            "freq": "ohlcv_1d",
            "horizon_hint": "unknown",
        },
    }

    # Validate contract before writing immutable card_v1.json.
    tmp = paths.registry_root / ".tmp_card.json"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    code, msg = contracts_validate.validate_json(tmp)
    tmp.unlink(missing_ok=True)
    if code != contracts_validate.EXIT_OK:
        raise RegistryInvalid(f"experience_card invalid: {msg}")

    card_dir.mkdir(parents=True, exist_ok=False)
    card_json.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # First event (append-only).
    created_event = {
        "event_version": 1,
        "event_type": "CREATED",
        "recorded_at": new_recorded_at(),
        "card_id": card_id,
        "run_id": run_id,
        "notes": "card created from Gate PASS trial",
    }
    _jsonl_append(events_jsonl, created_event)

    out = dict(card)
    out["effective_status"] = "draft"
    return out


def promote_card(
    *,
    card_id: str,
    new_status: str,
    registry_root: Path,
    allow_skip: bool = False,
) -> dict[str, Any]:
    paths = registry_paths(registry_root)
    card_id = str(card_id).strip()
    if not card_id:
        raise RegistryInvalid("card_id must be non-empty")
    new_status = str(new_status).strip()
    if new_status not in ALLOWED_STATUSES:
        raise RegistryInvalid(f"new_status must be one of {ALLOWED_STATUSES}")

    card_json = _card_json_path(paths, card_id)
    if not card_json.is_file():
        raise RegistryInvalid(f"card not found: {card_id}")
    base = _load_json(card_json)
    if not isinstance(base, dict):
        raise RegistryInvalid("card_v1.json must be a JSON object")

    events_path = _card_events_path(paths, card_id)
    events = list(iter_jsonl(events_path))
    cur = _compute_effective_status(base, events)

    if not allow_skip:
        expected = TRANSITIONS.get(cur)
        if expected is None:
            raise RegistryInvalid(f"cannot promote from terminal status: {cur}")
        if new_status != expected:
            raise RegistryInvalid(f"invalid transition: {cur} -> {new_status} (expected {expected})")

    ev = {
        "event_version": 1,
        "event_type": "PROMOTED",
        "recorded_at": new_recorded_at(),
        "card_id": card_id,
        "old_status": cur,
        "new_status": new_status,
    }
    _jsonl_append(events_path, ev)
    return ev


def list_cards(*, registry_root: Path) -> list[dict[str, Any]]:
    paths = registry_paths(registry_root)
    out: list[dict[str, Any]] = []
    if not paths.cards_dir.is_dir():
        return out
    for d in sorted([p for p in paths.cards_dir.iterdir() if p.is_dir()]):
        card_json = d / "card_v1.json"
        if not card_json.is_file():
            continue
        base = _load_json(card_json)
        if not isinstance(base, dict):
            continue
        evs = list(iter_jsonl(d / "events.jsonl"))
        eff = _compute_effective_status(base, evs)
        out.append({"card_id": str(base.get("card_id", d.name)), "status": eff, "title": base.get("title")})
    return out


def show_card(*, registry_root: Path, card_id: str) -> dict[str, Any]:
    paths = registry_paths(registry_root)
    card_json = _card_json_path(paths, card_id)
    if not card_json.is_file():
        raise RegistryInvalid(f"card not found: {card_id}")
    base = _load_json(card_json)
    if not isinstance(base, dict):
        raise RegistryInvalid("card_v1.json must be a JSON object")
    events_path = _card_events_path(paths, card_id)
    evs = list(iter_jsonl(events_path))
    eff = _compute_effective_status(base, evs)
    out = dict(base)
    out["effective_status"] = eff
    out["events"] = evs
    return out


def card_file_hashes(*, registry_root: Path, card_id: str) -> dict[str, str]:
    paths = registry_paths(registry_root)
    card_json = _card_json_path(paths, card_id)
    events_path = _card_events_path(paths, card_id)
    out: dict[str, str] = {}
    if card_json.is_file():
        out["card_v1.json"] = sha256_file(card_json)
    if events_path.is_file():
        out["events.jsonl"] = sha256_file(events_path)
    return out
