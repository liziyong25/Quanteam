from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from quant_eam.agents.harness import run_agent


def _write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _contains_forbidden_keys(node: Any) -> bool:
    if isinstance(node, dict):
        for key, value in node.items():
            if str(key).strip().lower() in {"function", "function_override"}:
                return True
            if _contains_forbidden_keys(value):
                return True
        return False
    if isinstance(node, list):
        return any(_contains_forbidden_keys(item) for item in node)
    return False


def test_ui_intake_agent_outputs_intent_first_bundle(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("EAM_LLM_PROVIDER", "mock")
    monkeypatch.setenv("EAM_LLM_MODE", "live")
    monkeypatch.setenv("EAM_AGENT_PROMPT_VERSION", "v1")
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    in_path = tmp_path / "in.json"
    _write_json(
        in_path,
        {
            "message": "帮我检查A股的MA250（年线）的有效性",
            "sample_n": 30,
            "start": "2017-01-01",
            "end": "2025-12-31",
        },
    )
    out_dir = tmp_path / "out"

    res = run_agent(agent_id="ui_intake_agent_v1", input_path=in_path, out_dir=out_dir, provider="mock")
    assert res.output_paths

    out_path = out_dir / "ui_intake_bundle.json"
    assert out_path.is_file()
    bundle = json.loads(out_path.read_text(encoding="utf-8"))

    assert bundle.get("schema_version") == "ui_intake_bundle_v1"
    assert isinstance(bundle.get("normalized_request"), dict)
    assert str(bundle.get("strategy_template")) == "ma250_trend_filter_v1"

    fetch_request = bundle.get("fetch_request")
    assert isinstance(fetch_request, dict)
    assert str(fetch_request.get("schema_version")) == "fetch_request_v1"
    assert isinstance(fetch_request.get("intent"), dict)
    assert _contains_forbidden_keys(fetch_request) is False


def test_ui_intake_agent_sets_clarification_for_ambiguous_message(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("EAM_LLM_PROVIDER", "mock")
    monkeypatch.setenv("EAM_LLM_MODE", "live")
    monkeypatch.setenv("EAM_AGENT_PROMPT_VERSION", "v1")

    in_path = tmp_path / "in.json"
    _write_json(in_path, {"message": "帮我看看这个策略是不是有效"})
    out_dir = tmp_path / "out"

    _ = run_agent(agent_id="ui_intake_agent_v1", input_path=in_path, out_dir=out_dir, provider="mock")
    bundle = json.loads((out_dir / "ui_intake_bundle.json").read_text(encoding="utf-8"))

    normalized = bundle.get("normalized_request")
    assert isinstance(normalized, dict)
    assert bool(normalized.get("need_user_clarification")) is True
