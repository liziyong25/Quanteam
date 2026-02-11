from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from quant_eam.api.app import app
from quant_eam.contracts import validate as contracts_validate
from quant_eam.data_lake.demo_ingest import main as demo_ingest_main
from quant_eam.worker.main import main as worker_main


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_phase26_replay_mode_real_provider_not_called(tmp_path: Path, monkeypatch) -> None:
    # Prepare a cassette entry for provider_id=real and verify replay works without any network.
    from quant_eam.agents.intent_agent import run_intent_agent
    from quant_eam.agents.promptpack import load_promptpack
    from quant_eam.llm.cassette import prompt_hash_v1, sha256_hex
    from quant_eam.llm.redaction import sanitize_for_llm

    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    monkeypatch.setenv("EAM_LLM_PROVIDER", "real")
    monkeypatch.setenv("EAM_LLM_MODE", "replay")
    monkeypatch.setenv("EAM_AGENT_PROMPT_VERSION", "v1")
    cassette_dir = tmp_path / "cassette"
    cassette_dir.mkdir()
    monkeypatch.setenv("EAM_LLM_CASSETTE_DIR", str(cassette_dir))
    # Intentionally set an invalid base url; replay must not use it.
    monkeypatch.setenv("EAM_LLM_REAL_BASE_URL", "http://127.0.0.1:9")

    idea = {
        "schema_version": "idea_spec_v1",
        "title": "Idea Demo",
        "hypothesis_text": "Replay must not call network.",
        "symbols": ["AAA"],
        "frequency": "1d",
        "start": "2024-01-01",
        "end": "2024-01-05",
        "evaluation_intent": "phase26",
        "snapshot_id": "snap_x",
        "policy_bundle_path": "policies/policy_bundle_v1.yaml",
    }
    idea_path = tmp_path / "idea.json"
    idea_path.write_text(json.dumps(idea, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # Generate a valid blueprint using deterministic agent logic (no network).
    out_seed = tmp_path / "seed_out"
    _ = run_intent_agent(input_path=idea_path, out_dir=out_seed, provider="mock")
    bp = json.loads((out_seed / "blueprint_draft.json").read_text(encoding="utf-8"))

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

    from quant_eam.agents.harness import run_agent

    out_dir = tmp_path / "out_replay"
    res = run_agent(agent_id="intent_agent_v1", input_path=idea_path, out_dir=out_dir, provider="mock")
    assert res.agent_run_path.is_file()
    assert (out_dir / "blueprint_draft.json").is_file()


def test_phase26_job_level_budget_stops_second_agent_run(tmp_path: Path, monkeypatch) -> None:
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
    monkeypatch.setenv("EAM_LLM_MODE", "live")
    monkeypatch.setenv("EAM_AGENT_PROMPT_VERSION", "v1")

    snapshot_id = "demo_snap_phase26_001"
    assert demo_ingest_main(["--root", str(data_root), "--snapshot-id", snapshot_id]) == 0

    # Tight budget: only 1 call per job.
    budget_path = tmp_path / "llm_budget_policy_v1_test.yaml"
    budget_path.write_text(
        "\n".join(
            [
                "policy_id: llm_budget_policy_v1_test",
                'policy_version: \"v1\"',
                "title: LLM Budget Policy v1 (test)",
                "description: test budget",
                "params:",
                "  max_calls_per_job: 1",
                "  max_prompt_chars_per_job: 999999",
                "  max_response_chars_per_job: 999999",
                "  max_wall_seconds_per_job: 999999",
                "  max_calls_per_agent_run: 1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    client = TestClient(app)
    idea = {
        "schema_version": "idea_spec_v1",
        "title": "Idea Phase26",
        "hypothesis_text": "Budget should stop deterministic job after max calls.",
        "symbols": ["AAA", "BBB"],
        "frequency": "1d",
        "start": "2024-01-01",
        "end": "2024-01-10",
        "evaluation_intent": "phase26_e2e",
        "snapshot_id": snapshot_id,
        "policy_bundle_path": "policies/policy_bundle_v1.yaml",
        "llm_budget_policy_path": str(budget_path),
    }

    r = client.post("/jobs/idea", json=idea)
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]

    # First agent run (intent) consumes 1 call and stops at blueprint approval checkpoint.
    assert worker_main(["--run-jobs", "--once"]) == 0
    assert client.post(f"/jobs/{job_id}/approve", params={"step": "blueprint"}).status_code == 200

    # Second agent run (strategy_spec) should be blocked by max_calls_per_job and job must stop.
    assert worker_main(["--run-jobs", "--once"]) == 0

    r = client.get(f"/jobs/{job_id}")
    assert r.status_code == 200
    evs = r.json()["events"]
    assert any(ev.get("event_type") == "STOPPED_BUDGET" for ev in evs)
    assert any(ev.get("event_type") == "DONE" for ev in evs)

    # Evidence files exist and report validates.
    up_dir = job_root / job_id / "outputs" / "llm"
    events_p = up_dir / "llm_usage_events.jsonl"
    report_p = up_dir / "llm_usage_report.json"
    assert events_p.is_file()
    assert report_p.is_file()
    lines = [ln for ln in events_p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) >= 2  # first call + blocked attempt
    assert contracts_validate.validate_json(report_p)[0] == contracts_validate.EXIT_OK

    # UI must render budget/usage section and include report path.
    r = client.get(f"/ui/jobs/{job_id}")
    assert r.status_code == 200
    assert "LLM Budget/Usage" in r.text
    assert "llm_usage_report.json" in r.text


def test_phase26_policy_asset_validates(monkeypatch) -> None:
    # Sanity: default policy must validate via policies.validate.
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    from quant_eam.policies.validate import validate_file, EXIT_OK

    code, _msg = validate_file(_repo_root() / "policies" / "llm_budget_policy_v1.yaml")
    assert code == EXIT_OK

