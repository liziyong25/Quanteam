from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_composer_agent(*, input_path: Path, out_dir: Path, provider: str = "mock") -> list[Path]:
    if str(provider).strip() != "mock":
        raise ValueError("provider 'external' is not supported in composer_agent MVP")
    payload = _load_json(Path(input_path))
    if not isinstance(payload, dict):
        raise ValueError("composer_agent input must be a JSON object")

    base_run_id = str(payload.get("run_id") or "").strip()
    base_card_id = str(payload.get("card_id") or "").strip()
    overall_pass = bool(payload.get("overall_pass"))

    plan = {
        "schema_version": "composer_agent_plan_v1",
        "agent_id": "composer_agent_v1",
        "base_run_id": base_run_id,
        "base_card_id": base_card_id,
        "eligible_for_compose": bool(overall_pass and base_card_id),
        "compose_candidates": [
            {
                "card_id": base_card_id,
                "weight_hint": 1.0,
                "reason": "Current run passed deterministic gates and is eligible as a compose component.",
            }
        ]
        if overall_pass and base_card_id
        else [],
        "notes": [
            "Composer agent emits advisory plan only; deterministic compose execution is explicit and governed.",
            "No policy overrides are emitted in agent outputs.",
        ],
    }

    out_path = Path(out_dir) / "composer_agent_plan.json"
    _write_json(out_path, plan)
    return [out_path]
