from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from quant_eam.api.app import app
from quant_eam.contracts import validate as contracts_validate
from quant_eam.data_lake.demo_ingest import main as demo_ingest_main
from quant_eam.worker.main import main as worker_main


def test_phase18_backtest_agent_bridge_and_run_link(tmp_path: Path, monkeypatch) -> None:
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

    snapshot_id = "demo_snap_backtest_agent_001"
    assert demo_ingest_main(["--root", str(data_root), "--snapshot-id", snapshot_id]) == 0

    client = TestClient(app)
    idea = {
        "schema_version": "idea_spec_v1",
        "title": "Idea Backtest Agent",
        "hypothesis_text": "Backtest agent should bridge deterministic runner/gaterunner and persist run link evidence.",
        "symbols": ["AAA", "BBB"],
        "frequency": "1d",
        "start": "2024-01-01",
        "end": "2024-01-10",
        "evaluation_intent": "backtest_agent_phase18",
        "snapshot_id": snapshot_id,
        "policy_bundle_path": "policies/policy_bundle_v1.yaml",
    }
    r = client.post("/jobs/idea", json=idea)
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]

    assert worker_main(["--run-jobs", "--once"]) == 0
    assert client.post(f"/jobs/{job_id}/approve", params={"step": "blueprint"}).status_code == 200

    assert worker_main(["--run-jobs", "--once"]) == 0
    assert client.post(f"/jobs/{job_id}/approve", params={"step": "strategy_spec"}).status_code == 200

    assert worker_main(["--run-jobs", "--once"]) == 0
    assert client.post(f"/jobs/{job_id}/approve", params={"step": "spec_qa"}).status_code == 200

    assert worker_main(["--run-jobs", "--once"]) == 0
    assert client.post(f"/jobs/{job_id}/approve", params={"step": "runspec"}).status_code == 200

    # runspec approved -> backtest agent evidence should exist before trace_preview approval.
    assert worker_main(["--run-jobs", "--once"]) == 0
    r = client.get(f"/jobs/{job_id}")
    assert r.status_code == 200
    evs = r.json()["events"]
    assert any(
        ev.get("event_type") == "WAITING_APPROVAL" and (ev.get("outputs") or {}).get("step") == "trace_preview" for ev in evs
    )
    outputs = r.json().get("outputs") or {}
    backtest_agent_run = Path(outputs["backtest_agent_run_path"])
    backtest_plan = Path(outputs["backtest_plan_path"])
    assert backtest_agent_run.is_file()
    assert backtest_plan.is_file()
    assert contracts_validate.validate_json(backtest_agent_run)[0] == contracts_validate.EXIT_OK

    # trace_preview approved -> deterministic run/gates proceed, run_link must be present.
    assert client.post(f"/jobs/{job_id}/approve", params={"step": "trace_preview"}).status_code == 200
    assert worker_main(["--run-jobs", "--once"]) == 0
    r = client.get(f"/jobs/{job_id}")
    assert r.status_code == 200
    outputs = r.json().get("outputs") or {}
    run_link_path = Path(outputs["run_link_path"])
    assert run_link_path.is_file()
    run_link = json.loads(run_link_path.read_text(encoding="utf-8"))
    assert str(run_link.get("run_id")) == str(outputs.get("run_id"))
    dossier_path = Path(str(run_link.get("dossier_path", "")))
    gate_results_path = Path(str(run_link.get("gate_results_path", "")))
    assert dossier_path.is_dir()
    assert gate_results_path.is_file()
    assert (dossier_path / "dossier_manifest.json").is_file()
    assert (dossier_path / "gate_results.json").is_file()
