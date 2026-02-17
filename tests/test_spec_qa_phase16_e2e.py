from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from quant_eam.api.app import app
from quant_eam.data_lake.demo_ingest import main as demo_ingest_main
from quant_eam.worker.main import main as worker_main


def test_phase16_spec_qa_checkpoint_and_ui_evidence(tmp_path: Path, monkeypatch) -> None:
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

    snapshot_id = "demo_snap_specqa_001"
    assert demo_ingest_main(["--root", str(data_root), "--snapshot-id", snapshot_id]) == 0

    client = TestClient(app)
    idea = {
        "schema_version": "idea_spec_v1",
        "title": "Idea SpecQA",
        "hypothesis_text": "Spec-QA should gate workflow before runspec compile.",
        "symbols": ["AAA", "BBB"],
        "frequency": "1d",
        "start": "2024-01-01",
        "end": "2024-01-10",
        "evaluation_intent": "spec_qa_phase16",
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
    r = client.get(f"/jobs/{job_id}")
    assert r.status_code == 200
    evs = r.json()["events"]
    assert any(
        ev.get("event_type") == "WAITING_APPROVAL" and (ev.get("outputs") or {}).get("step") == "spec_qa" for ev in evs
    )
    outputs = r.json().get("outputs") or {}
    p_json = Path(outputs["spec_qa_report_path"])
    p_md = Path(outputs["spec_qa_report_md_path"])
    assert p_json.is_file()
    assert p_md.is_file()
    rep = json.loads(p_json.read_text(encoding="utf-8"))
    assert rep.get("schema_version") == "spec_qa_report_v1"
    assert isinstance((rep.get("summary") or {}).get("finding_count"), int)

    # API approve must accept step=spec_qa
    r = client.post(f"/jobs/{job_id}/approve", params={"step": "spec_qa"})
    assert r.status_code == 200, r.text

    # Next pass should proceed to runspec checkpoint.
    assert worker_main(["--run-jobs", "--once"]) == 0
    r = client.get(f"/jobs/{job_id}")
    assert r.status_code == 200
    evs = r.json()["events"]
    assert any(ev.get("event_type") == "RUNSPEC_COMPILED" for ev in evs)
    assert any(ev.get("event_type") == "WAITING_APPROVAL" and (ev.get("outputs") or {}).get("step") == "runspec" for ev in evs)

    # UI evidence should render Spec-QA section.
    ru = client.get(f"/ui/jobs/{job_id}")
    assert ru.status_code == 200
    assert "Spec-QA Report" in ru.text
    assert "spec_qa_report.json" in ru.text
