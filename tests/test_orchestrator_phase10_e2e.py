from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from quant_eam.api.app import app
from quant_eam.contracts import validate as contracts_validate
from quant_eam.data_lake.demo_ingest import main as demo_ingest_main
from quant_eam.worker.main import main as worker_main


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_phase10_workflow_job_checkpoint_and_completion(tmp_path: Path, monkeypatch) -> None:
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

    snapshot_id = "demo_snap_job_001"
    assert demo_ingest_main(["--root", str(data_root), "--snapshot-id", snapshot_id]) == 0

    bp_path = _repo_root() / "contracts" / "examples" / "blueprint_buyhold_demo_ok.json"
    blueprint = json.loads(bp_path.read_text(encoding="utf-8"))
    client = TestClient(app)

    r = client.post(
        "/jobs/blueprint",
        params={"snapshot_id": snapshot_id, "policy_bundle_path": "policies/policy_bundle_v1.yaml"},
        json=blueprint,
    )
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]

    # Worker advances to WAITING_APPROVAL and must not write dossiers yet.
    assert worker_main(["--run-jobs", "--once"]) == 0
    dossiers_dir = art_root / "dossiers"
    assert (not dossiers_dir.exists()) or (len([p for p in dossiers_dir.glob("*")]) == 0)

    r = client.get(f"/jobs/{job_id}")
    assert r.status_code == 200
    events = r.json()["events"]
    assert any(ev.get("event_type") == "WAITING_APPROVAL" for ev in events)
    assert not any(ev.get("event_type") == "APPROVED" for ev in events)

    # Approve, then worker should finish end-to-end to DONE in one pass.
    r = client.post(f"/jobs/{job_id}/approve")
    assert r.status_code == 200
    assert worker_main(["--run-jobs", "--once"]) == 0

    r = client.get(f"/jobs/{job_id}")
    assert r.status_code == 200
    events = r.json()["events"]
    assert any(ev.get("event_type") == "DONE" for ev in events)

    outputs = r.json().get("outputs") or {}
    dossier_path = Path(outputs["dossier_path"])
    assert dossier_path.is_dir()

    # Evidence contracts: dossier manifest + gate results must validate.
    code, _msg = contracts_validate.validate_json(dossier_path / "dossier_manifest.json")
    assert code == contracts_validate.EXIT_OK
    code, _msg = contracts_validate.validate_json(dossier_path / "gate_results.json")
    assert code == contracts_validate.EXIT_OK

    # Registry updated: trial log should include run_id.
    run_id = str(outputs.get("run_id"))
    trial_log = reg_root / "trial_log.jsonl"
    assert trial_log.is_file()
    assert run_id in trial_log.read_text(encoding="utf-8")

    # UI jobs page renders.
    r = client.get("/ui/jobs")
    assert r.status_code == 200
    assert job_id in r.text

