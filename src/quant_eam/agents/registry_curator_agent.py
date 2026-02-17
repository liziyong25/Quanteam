from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_registry_curator_agent(*, input_path: Path, out_dir: Path, provider: str = "mock") -> list[Path]:
    if str(provider).strip() != "mock":
        raise ValueError("provider 'external' is not supported in registry_curator_agent MVP")
    payload = _load_json(Path(input_path))
    if not isinstance(payload, dict):
        raise ValueError("registry_curator_agent input must be a JSON object")

    run_id = str(payload.get("run_id") or "").strip()
    card_id = str(payload.get("card_id") or "").strip()
    overall_pass = bool(payload.get("overall_pass"))

    summary = {
        "schema_version": "registry_curator_summary_v1",
        "agent_id": "registry_curator_v1",
        "run_id": run_id,
        "card_id": card_id,
        "overall_pass": overall_pass,
        "curation_status": "promote_candidate" if overall_pass else "hold_draft",
        "rationale": {
            "evidence_refs": [
                "gate_results.json#/overall_pass",
                "registry/trial_log.jsonl",
            ],
            "message": "Registry curation remains advisory; deterministic gate outcome is the only arbiter.",
        },
    }

    out_path = Path(out_dir) / "registry_curator_summary.json"
    _write_json(out_path, summary)
    return [out_path]
