from __future__ import annotations

import json
from pathlib import Path

import pytest

from quant_eam.agents.harness import run_agent
from quant_eam.llm.redaction import sanitize_for_llm


def test_phase18_redaction_removes_sensitive_keys() -> None:
    obj = {
        "a": 1,
        "holdout": {"curve": [1, 2, 3]},
        "extensions": {"token": "secret", "auth": {"bearer": "x"}},
        "nested": {"vault_path": "/artifacts/holdout", "ok": True},
    }
    sanitized, summary = sanitize_for_llm(obj)
    assert isinstance(sanitized, dict)
    # Sensitive keys must be removed at any nesting.
    assert "holdout" not in sanitized
    assert "token" not in (sanitized.get("extensions") or {})
    assert "auth" not in (sanitized.get("extensions") or {})
    assert "vault_path" not in (sanitized.get("nested") or {})
    assert summary.removed_keys


def test_phase18_record_then_replay_produces_identical_outputs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    monkeypatch.setenv("EAM_LLM_PROVIDER", "mock")
    cassette_dir = tmp_path / "cassette"
    cassette_dir.mkdir()
    monkeypatch.setenv("EAM_LLM_CASSETTE_DIR", str(cassette_dir))

    idea = {
        "schema_version": "idea_spec_v1",
        "title": "Idea Demo",
        "hypothesis_text": "Deterministic record/replay test.",
        "symbols": ["AAA"],
        "frequency": "1d",
        "start": "2024-01-01",
        "end": "2024-01-05",
        "evaluation_intent": "phase18",
        "snapshot_id": "snap_x",
        "policy_bundle_path": "policies/policy_bundle_v1.yaml",
        "extensions": {"token": "SHOULD_BE_REDACTED", "holdout": "SHOULD_BE_REDACTED"},
    }
    in_path = tmp_path / "idea.json"
    in_path.write_text(json.dumps(idea, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    out1 = tmp_path / "out_record"
    out2 = tmp_path / "out_replay"

    monkeypatch.setenv("EAM_LLM_MODE", "record")
    res1 = run_agent(agent_id="intent_agent_v1", input_path=in_path, out_dir=out1, provider="mock")
    p1 = out1 / "blueprint_draft.json"
    assert p1.is_file()
    assert (out1 / "llm_calls.jsonl").is_file()
    assert (out1 / "llm_session.json").is_file()
    assert (out1 / "redaction_summary.json").is_file()

    monkeypatch.setenv("EAM_LLM_MODE", "replay")
    res2 = run_agent(agent_id="intent_agent_v1", input_path=in_path, out_dir=out2, provider="mock")
    p2 = out2 / "blueprint_draft.json"
    assert p2.is_file()

    # Deterministic replay: output bytes must match.
    assert p1.read_text(encoding="utf-8") == p2.read_text(encoding="utf-8")
    # Evidence should exist in replay too.
    assert (out2 / "llm_calls.jsonl").is_file()
    assert (out2 / "llm_session.json").is_file()

    # AgentRun exists.
    assert res1.agent_run_path.is_file()
    assert res2.agent_run_path.is_file()


def test_phase18_replay_missing_cassette_fails(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    monkeypatch.setenv("EAM_LLM_PROVIDER", "mock")
    cassette_dir = tmp_path / "cassette_empty"
    cassette_dir.mkdir()
    monkeypatch.setenv("EAM_LLM_CASSETTE_DIR", str(cassette_dir))
    monkeypatch.setenv("EAM_LLM_MODE", "replay")

    idea = {
        "schema_version": "idea_spec_v1",
        "title": "Idea Demo",
        "hypothesis_text": "Replay miss must fail.",
        "symbols": ["AAA"],
        "frequency": "1d",
        "start": "2024-01-01",
        "end": "2024-01-05",
        "evaluation_intent": "phase18",
        "snapshot_id": "snap_x",
        "policy_bundle_path": "policies/policy_bundle_v1.yaml",
    }
    in_path = tmp_path / "idea.json"
    in_path.write_text(json.dumps(idea, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    out = tmp_path / "out"
    with pytest.raises(ValueError, match="cassette miss"):
        _ = run_agent(agent_id="intent_agent_v1", input_path=in_path, out_dir=out, provider="mock")

