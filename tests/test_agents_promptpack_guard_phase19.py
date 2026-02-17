from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from quant_eam.agents.guards import validate_agent_output
from quant_eam.agents.harness import run_agent
from quant_eam.api.app import app
from quant_eam.data_lake.demo_ingest import main as demo_ingest_main
from quant_eam.worker.main import main as worker_main


def _fixture_dir() -> Path:
    return Path(__file__).resolve().parent / "fixtures"


def test_phase19_regression_fixture_intent_agent_output_matches_expected(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    monkeypatch.setenv("EAM_LLM_PROVIDER", "mock")
    monkeypatch.setenv("EAM_LLM_MODE", "live")
    monkeypatch.setenv("EAM_AGENT_PROMPT_VERSION", "v1")

    case_dir = _fixture_dir() / "agents" / "intent_agent_v1" / "basic_case"
    in_path = case_dir / "input.json"
    exp_path = case_dir / "expected_output.json"
    assert in_path.is_file()
    assert exp_path.is_file()

    out_dir = tmp_path / "out"
    res = run_agent(agent_id="intent_agent_v1", input_path=in_path, out_dir=out_dir, provider="mock")
    assert res.output_paths
    got = json.loads((out_dir / "blueprint_draft.json").read_text(encoding="utf-8"))
    exp = json.loads(exp_path.read_text(encoding="utf-8"))
    assert {"blueprint_draft": got} == exp


def test_phase19_prompt_version_changes_prompt_hash(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    monkeypatch.setenv("EAM_LLM_PROVIDER", "mock")
    monkeypatch.setenv("EAM_LLM_MODE", "live")

    idea = {
        "schema_version": "idea_spec_v1",
        "title": "Idea Demo",
        "hypothesis_text": "Promptpack hash stability test.",
        "symbols": ["AAA"],
        "frequency": "1d",
        "start": "2024-01-01",
        "end": "2024-01-05",
        "evaluation_intent": "phase19",
        "snapshot_id": "snap_x",
        "policy_bundle_path": "policies/policy_bundle_v1.yaml",
    }
    in_path = tmp_path / "idea.json"
    in_path.write_text(json.dumps(idea, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    out_v1 = tmp_path / "out_v1"
    out_v2 = tmp_path / "out_v2"

    monkeypatch.setenv("EAM_AGENT_PROMPT_VERSION", "v1")
    _ = run_agent(agent_id="intent_agent_v1", input_path=in_path, out_dir=out_v1, provider="mock")
    sess1 = json.loads((out_v1 / "llm_session.json").read_text(encoding="utf-8"))
    h1 = (sess1.get("prompt_hashes") or [""])[0]

    monkeypatch.setenv("EAM_AGENT_PROMPT_VERSION", "v2")
    _ = run_agent(agent_id="intent_agent_v1", input_path=in_path, out_dir=out_v2, provider="mock")
    sess2 = json.loads((out_v2 / "llm_session.json").read_text(encoding="utf-8"))
    h2 = (sess2.get("prompt_hashes") or [""])[0]

    assert isinstance(h1, str) and h1
    assert isinstance(h2, str) and h2
    assert h1 != h2


def test_phase19_output_guard_blocks_inline_policy_params() -> None:
    out = {
        "blueprint_draft": {
            "schema_version": "blueprint_v1",
            "blueprint_id": "bp_x",
            "title": "X",
            "policy_bundle_id": "bundle_x",
            "extensions": {"commission_bps": 1.0},
        }
    }
    guard = validate_agent_output(agent_id="intent_agent_v1", output_json=out)
    assert guard["schema_version"] == "output_guard_report_v1"
    assert guard["passed"] is False
    assert int(guard.get("finding_count") or 0) >= 1


def test_phase19_ui_shows_prompt_version_and_guard_status(tmp_path: Path, monkeypatch) -> None:
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

    snapshot_id = "demo_snap_phase19_ui_001"
    assert demo_ingest_main(["--root", str(data_root), "--snapshot-id", snapshot_id]) == 0

    client = TestClient(app)
    idea = {
        "schema_version": "idea_spec_v1",
        "title": "Idea Demo",
        "hypothesis_text": "UI evidence test.",
        "symbols": ["AAA"],
        "frequency": "1d",
        "start": "2024-01-01",
        "end": "2024-01-05",
        "evaluation_intent": "phase19_ui",
        "snapshot_id": snapshot_id,
        "policy_bundle_path": "policies/policy_bundle_v1.yaml",
    }
    r = client.post("/jobs/idea", json=idea)
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]

    # Advance once: should propose blueprint and write LLM evidence for intent agent.
    assert worker_main(["--run-jobs", "--once"]) == 0

    r = client.get(f"/ui/jobs/{job_id}")
    assert r.status_code == 200
    # Phase-19 requirement: UI must explicitly show prompt_version + guard_status (not only raw JSON).
    assert "prompt_version" in r.text
    assert "guard_status" in r.text
