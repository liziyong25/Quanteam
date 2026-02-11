from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from quant_eam.contracts import validate as contracts_validate
from quant_eam.policies.resolve import load_policy_bundle
from quant_eam.agents.experience_pack import ensure_experience_pack_for_job, infer_job_id_from_input_path, retrieval_enabled


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_sha12(obj: Any) -> str:
    b = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(b).hexdigest()[:12]


def run_intent_agent(*, input_path: Path, out_dir: Path, provider: str = "mock") -> list[Path]:
    if provider != "mock":
        raise ValueError("IntentAgent MVP supports provider=mock only")

    # Phase-29: deterministic experience retrieval (append-only job evidence), before drafting blueprint.
    if retrieval_enabled():
        try:
            job_id = infer_job_id_from_input_path(Path(input_path))
            if job_id:
                # IdeaSpec fields are loaded below; for robustness, use a cheap pre-load now.
                idea0 = _load_json(Path(input_path))
                title0 = str(idea0.get("title") or "")
                hyp0 = str(idea0.get("hypothesis_text") or "")
                q = " ".join([x for x in (title0, hyp0) if x.strip()]).strip() or title0 or "idea"
                syms0 = idea0.get("symbols") if isinstance(idea0.get("symbols"), list) else []
                syms = [str(s) for s in syms0 if str(s).strip()]
                freq0 = str(idea0.get("frequency") or "").strip() or None
                ensure_experience_pack_for_job(job_id=job_id, query=q, symbols=syms, frequency=freq0, top_k=5)
        except Exception:
            pass

    idea = _load_json(Path(input_path))
    if not isinstance(idea, dict):
        raise ValueError("idea_spec must be a JSON object")

    code, msg = contracts_validate.validate_payload(idea)
    if code != contracts_validate.EXIT_OK:
        raise ValueError(f"invalid IdeaSpec: {msg}")

    # Resolve policy bundle id from path if provided; fallback to repo default.
    pb_path = Path(str(idea.get("policy_bundle_path") or "policies/policy_bundle_v1.yaml"))
    if not pb_path.is_absolute():
        # Resolve relative to repo root via policies loader helper.
        from quant_eam.policies.load import find_repo_root

        pb_path = find_repo_root() / pb_path
    bundle_doc = load_policy_bundle(pb_path)
    bundle_id = str(bundle_doc["policy_bundle_id"])

    title = str(idea.get("title", ""))
    symbols = idea.get("symbols") if isinstance(idea.get("symbols"), list) else []
    symbols = [str(s) for s in symbols if str(s).strip()] or ["AAA"]
    freq = str(idea.get("frequency") or "1d")
    start = str(idea.get("start") or "2024-01-01")
    end = str(idea.get("end") or "2024-01-10")

    blueprint_id = f"bp_{_canonical_sha12(idea)}"
    bp: dict[str, Any] = {
        "schema_version": "blueprint_v1",
        "blueprint_id": blueprint_id,
        "title": title or f"Intent Draft {blueprint_id}",
        "description": str(idea.get("hypothesis_text") or ""),
        "policy_bundle_id": bundle_id,
        "universe": {
            "asset_pack": str(idea.get("universe_hint") or "demo"),
            "symbols": symbols,
            "timezone": "Asia/Taipei",
            "calendar": "DEMO",
        },
        "bar_spec": {"frequency": freq},
        "data_requirements": [
            {
                "dataset_id": "ohlcv_1d",
                "fields": ["open", "high", "low", "close", "volume", "available_at"],
                "frequency": freq,
                "adjustment": "none",
                "asof_rule": {"mode": "asof"},
            }
        ],
        "strategy_spec": {
            "dsl_version": "signal_dsl_v1",
            "signals": {"entry": "enter", "exit": "exit"},
            "expressions": {"enter": {"type": "const", "value": True}, "exit": {"type": "const", "value": False}},
            "execution": {"order_timing": "next_open", "cost_model": {"ref_policy": True}},
            "extensions": {"engine_contract": "vectorbt_signal_v1", "strategy_id": "buy_and_hold_mvp"},
        },
        "evaluation_protocol": {
            "segments": {
                "train": {"start": start, "end": end},
                "test": {"start": start, "end": end},
                "holdout": {"start": start, "end": end},
            },
            "purge": {"bars": 0},
            "embargo": {"bars": 0},
            "gate_suite_id": str(bundle_doc.get("gate_suite_id") or "gate_suite_v1_default"),
        },
        "report_spec": {"plots": False, "tables": True, "trace": False},
        "extensions": {
            "idea_spec_title": title,
            "evaluation_intent": str(idea.get("evaluation_intent") or ""),
            "snapshot_id": str(idea.get("snapshot_id") or ""),
            "agent_provider": provider,
        },
    }

    # Validate blueprint contract (must pass).
    code2, msg2 = contracts_validate.validate_payload(bp)
    if code2 != contracts_validate.EXIT_OK:
        raise ValueError(f"IntentAgent produced invalid blueprint: {msg2}")

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "blueprint_draft.json"
    out_path.write_text(json.dumps(bp, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return [out_path]
