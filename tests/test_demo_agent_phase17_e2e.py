from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from quant_eam.api.app import app
from quant_eam.contracts import validate as contracts_validate
from quant_eam.data_lake.demo_ingest import main as demo_ingest_main
from quant_eam.worker.main import main as worker_main


def test_phase17_demo_agent_run_artifact_before_trace_preview_review(tmp_path: Path, monkeypatch) -> None:
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

    snapshot_id = "demo_snap_demo_agent_001"
    assert demo_ingest_main(["--root", str(data_root), "--snapshot-id", snapshot_id]) == 0

    client = TestClient(app)
    idea = {
        "schema_version": "idea_spec_v1",
        "title": "Idea Demo Agent",
        "hypothesis_text": "Demo agent should produce agent_run evidence before trace preview approval.",
        "symbols": ["AAA", "BBB"],
        "frequency": "1d",
        "start": "2024-01-01",
        "end": "2024-01-10",
        "evaluation_intent": "demo_agent_phase17",
        "snapshot_id": snapshot_id,
        "policy_bundle_path": "policies/policy_bundle_v1.yaml",
    }
    r = client.post("/jobs/idea", json=idea)
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]

    # intent -> blueprint wait
    assert worker_main(["--run-jobs", "--once"]) == 0
    assert client.post(f"/jobs/{job_id}/approve", params={"step": "blueprint"}).status_code == 200

    # strategy_spec wait
    assert worker_main(["--run-jobs", "--once"]) == 0
    assert client.post(f"/jobs/{job_id}/approve", params={"step": "strategy_spec"}).status_code == 200

    # spec_qa wait
    assert worker_main(["--run-jobs", "--once"]) == 0
    assert client.post(f"/jobs/{job_id}/approve", params={"step": "spec_qa"}).status_code == 200

    # runspec wait
    assert worker_main(["--run-jobs", "--once"]) == 0
    assert client.post(f"/jobs/{job_id}/approve", params={"step": "runspec"}).status_code == 200

    # demo step + trace preview evidence, then WAITING_APPROVAL(trace_preview)
    assert worker_main(["--run-jobs", "--once"]) == 0
    r = client.get(f"/jobs/{job_id}")
    assert r.status_code == 200
    evs = r.json()["events"]
    assert any(ev.get("event_type") == "TRACE_PREVIEW_COMPLETED" for ev in evs)
    assert any(
        ev.get("event_type") == "WAITING_APPROVAL" and (ev.get("outputs") or {}).get("step") == "trace_preview" for ev in evs
    )
    outputs = r.json().get("outputs") or {}
    demo_run = Path(outputs["demo_agent_run_path"])
    trace_csv = Path(outputs["calc_trace_preview_path"])
    trace_meta = Path(outputs["trace_meta_path"])
    assert demo_run.is_file()
    assert contracts_validate.validate_json(demo_run)[0] == contracts_validate.EXIT_OK
    assert trace_csv.is_file()
    assert trace_meta.is_file()
