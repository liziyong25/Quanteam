from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from quant_eam.api.app import app
from quant_eam.agents.intent_agent import run_intent_agent
from quant_eam.agents.promptpack import load_promptpack
from quant_eam.llm.cassette import prompt_hash_v1, sha256_hex
from quant_eam.llm.redaction import sanitize_for_llm
from quant_eam.worker.main import main as worker_main


def test_phase28_live_confirm_blocks_real_live(tmp_path: Path, monkeypatch) -> None:
    # Real provider + live mode must not run agents until an explicit llm_live_confirm approval exists.
    data_root = tmp_path / "data"
    art_root = tmp_path / "artifacts"
    reg_root = tmp_path / "registry"
    job_root = tmp_path / "jobs"
    data_root.mkdir()
    art_root.mkdir()
    reg_root.mkdir()
    job_root.mkdir()

    monkeypatch.setenv("EAM_DATA_ROOT", str(data_root))
    monkeypatch.setenv("EAM_ARTIFACT_ROOT", str(art_root))
    monkeypatch.setenv("EAM_REGISTRY_ROOT", str(reg_root))
    monkeypatch.setenv("EAM_JOB_ROOT", str(job_root))
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    monkeypatch.setenv("EAM_LLM_PROVIDER", "real")
    monkeypatch.setenv("EAM_LLM_MODE", "live")
    monkeypatch.setenv("EAM_LLM_REAL_MODEL", "test-model")

    client = TestClient(app)
    idea = {
        "schema_version": "idea_spec_v1",
        "title": "Idea Phase28 Live Confirm",
        "hypothesis_text": "Real/live must require explicit confirmation.",
        "symbols": ["AAA"],
        "frequency": "1d",
        "start": "2024-01-01",
        "end": "2024-01-05",
        "evaluation_intent": "phase28",
        "snapshot_id": "snap_x",
        "policy_bundle_path": "policies/policy_bundle_v1.yaml",
    }
    r = client.post("/jobs/idea", json=idea)
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]

    assert worker_main(["--run-jobs", "--once"]) == 0

    r = client.get(f"/jobs/{job_id}")
    assert r.status_code == 200
    evs = r.json()["events"]
    assert any(ev.get("event_type") == "WAITING_APPROVAL" and (ev.get("outputs") or {}).get("step") == "llm_live_confirm" for ev in evs)
    assert not any(ev.get("event_type") == "BLUEPRINT_PROPOSED" for ev in evs)

    # UI should label the LIVE/RECORD confirmation and show budget/mode context (best-effort).
    r = client.get(f"/ui/jobs/{job_id}")
    assert r.status_code == 200
    assert "LIVE/RECORD Confirmation Required" in r.text
    assert "llm_live_confirm" in r.text


def test_phase28_guard_fail_blocks_agent_output_invalid(tmp_path: Path, monkeypatch) -> None:
    # In replay mode, a cassette can deliver an output that violates hard guard rules.
    # The workflow must block at WAITING_APPROVAL(step=agent_output_invalid).
    data_root = tmp_path / "data"
    art_root = tmp_path / "artifacts"
    reg_root = tmp_path / "registry"
    job_root = tmp_path / "jobs"
    data_root.mkdir()
    art_root.mkdir()
    reg_root.mkdir()
    job_root.mkdir()

    monkeypatch.setenv("EAM_DATA_ROOT", str(data_root))
    monkeypatch.setenv("EAM_ARTIFACT_ROOT", str(art_root))
    monkeypatch.setenv("EAM_REGISTRY_ROOT", str(reg_root))
    monkeypatch.setenv("EAM_JOB_ROOT", str(job_root))
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    monkeypatch.setenv("EAM_LLM_PROVIDER", "mock")
    monkeypatch.setenv("EAM_LLM_MODE", "replay")
    monkeypatch.setenv("EAM_AGENT_PROMPT_VERSION", "v1")

    client = TestClient(app)
    idea = {
        "schema_version": "idea_spec_v1",
        "title": "Idea Phase28 Guard Fail",
        "hypothesis_text": "Guard must block invalid agent output.",
        "symbols": ["AAA"],
        "frequency": "1d",
        "start": "2024-01-01",
        "end": "2024-01-05",
        "evaluation_intent": "phase28",
        "snapshot_id": "snap_x",
        "policy_bundle_path": "policies/policy_bundle_v1.yaml",
    }
    r = client.post("/jobs/idea", json=idea)
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]

    job_spec = json.loads((job_root / job_id / "job_spec.json").read_text(encoding="utf-8"))

    # Build a valid blueprint then inject a forbidden inline policy param key.
    seed_out = tmp_path / "seed_out"
    idea_path = tmp_path / "idea.json"
    idea_path.write_text(json.dumps(idea, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _ = run_intent_agent(input_path=idea_path, out_dir=seed_out, provider="mock")
    bp = json.loads((seed_out / "blueprint_draft.json").read_text(encoding="utf-8"))
    bp["commission_bps"] = 1  # forbidden by Output Guard (Phase-19/28)

    # Prepare cassette entry for the orchestrator's intent agent out_dir.
    pp = load_promptpack(agent_id="intent_agent_v1", version="v1", root=None)
    sanitized, red_summary = sanitize_for_llm(job_spec)
    bundle_schema = {"type": "object", "required": ["blueprint_draft"], "properties": {"blueprint_draft": {"type": "object"}}}
    request_obj = {
        "agent_id": "intent_agent_v1",
        "agent_version": "v1",
        "provider_id": "mock",
        "sanitized_input_sha256": red_summary.sanitized_sha256,
        "prompt_version": pp.prompt_version,
        "output_schema_version": pp.output_schema_version,
        "promptpack_sha256": __import__("hashlib").sha256(pp.path.read_bytes()).hexdigest(),
        "system": pp.system,
        "user": json.dumps(sanitized, sort_keys=True, separators=(",", ":"), ensure_ascii=True),
        "schema_sha256": sha256_hex(bundle_schema),
        "temperature": 0.0,
        "seed": None,
    }
    ph = prompt_hash_v1(request=request_obj)

    out_dir = job_root / job_id / "outputs" / "agents" / "intent"
    out_dir.mkdir(parents=True, exist_ok=True)
    cassette_path = out_dir / "cassette.jsonl"
    cassette_path.write_text(
        json.dumps(
            {
                "schema_version": "llm_call_v1",
                "prompt_hash": ph,
                "provider_id": "mock",
                "mode": "record",
                "request": request_obj,
                "response_json": {"blueprint_draft": bp},
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        + "\n",
        encoding="utf-8",
    )

    assert worker_main(["--run-jobs", "--once"]) == 0

    r = client.get(f"/jobs/{job_id}")
    assert r.status_code == 200
    evs = r.json()["events"]
    assert any(ev.get("event_type") == "WAITING_APPROVAL" and (ev.get("outputs") or {}).get("step") == "agent_output_invalid" for ev in evs)
    assert not any(ev.get("event_type") == "BLUEPRINT_PROPOSED" for ev in evs)

    # UI should show guard FAIL evidence.
    r = client.get(f"/ui/jobs/{job_id}")
    assert r.status_code == 200
    assert "LLM Evidence" in r.text
    assert "FAIL" in r.text
    assert "commission_bps" in r.text


def test_phase28_real_live_provider_error_falls_back_to_replay(tmp_path: Path, monkeypatch) -> None:
    # The harness should evidence provider failure and downgrade to replay if a cassette is present.
    from quant_eam.agents.harness import run_agent

    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    monkeypatch.setenv("EAM_LLM_PROVIDER", "real")
    monkeypatch.setenv("EAM_LLM_MODE", "live")
    monkeypatch.setenv("EAM_AGENT_PROMPT_VERSION", "v1")

    cassette_dir = tmp_path / "cassette"
    cassette_dir.mkdir()
    monkeypatch.setenv("EAM_LLM_CASSETTE_DIR", str(cassette_dir))
    # Base URL should not be used under pytest; provider raises before network.
    monkeypatch.setenv("EAM_LLM_REAL_BASE_URL", "http://127.0.0.1:9")

    idea = {
        "schema_version": "idea_spec_v1",
        "title": "Idea Phase28 Fallback",
        "hypothesis_text": "Provider error falls back to replay.",
        "symbols": ["AAA"],
        "frequency": "1d",
        "start": "2024-01-01",
        "end": "2024-01-05",
        "evaluation_intent": "phase28",
        "snapshot_id": "snap_x",
        "policy_bundle_path": "policies/policy_bundle_v1.yaml",
    }
    in_path = tmp_path / "idea.json"
    in_path.write_text(json.dumps(idea, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # Seed a valid blueprint.
    seed_out = tmp_path / "seed_out"
    _ = run_intent_agent(input_path=in_path, out_dir=seed_out, provider="mock")
    bp = json.loads((seed_out / "blueprint_draft.json").read_text(encoding="utf-8"))

    pp = load_promptpack(agent_id="intent_agent_v1", version="v1", root=None)
    sanitized, red_summary = sanitize_for_llm(idea)
    bundle_schema = {"type": "object", "required": ["blueprint_draft"], "properties": {"blueprint_draft": {"type": "object"}}}
    request_obj = {
        "agent_id": "intent_agent_v1",
        "agent_version": "v1",
        "provider_id": "real",
        "sanitized_input_sha256": red_summary.sanitized_sha256,
        "prompt_version": pp.prompt_version,
        "output_schema_version": pp.output_schema_version,
        "promptpack_sha256": __import__("hashlib").sha256(pp.path.read_bytes()).hexdigest(),
        "system": pp.system,
        "user": json.dumps(sanitized, sort_keys=True, separators=(",", ":"), ensure_ascii=True),
        "schema_sha256": sha256_hex(bundle_schema),
        "temperature": 0.0,
        "seed": None,
    }
    ph = prompt_hash_v1(request=request_obj)
    cassette_path = cassette_dir / "cassette.jsonl"
    cassette_path.write_text(
        json.dumps(
            {
                "schema_version": "llm_call_v1",
                "prompt_hash": ph,
                "provider_id": "real",
                "mode": "record",
                "request": request_obj,
                "response_json": {"blueprint_draft": bp},
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        + "\n",
        encoding="utf-8",
    )

    out_dir = tmp_path / "out"
    res = run_agent(agent_id="intent_agent_v1", input_path=in_path, out_dir=out_dir, provider="mock")
    assert res.agent_run_path.is_file()
    assert (out_dir / "blueprint_draft.json").is_file()
    assert (out_dir / "error_summary.json").is_file()

    sess = json.loads((out_dir / "llm_session.json").read_text(encoding="utf-8"))
    assert sess.get("mode") == "replay"
