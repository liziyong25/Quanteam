from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from quant_eam.api.app import app
from quant_eam.contracts import validate as contracts_validate
from quant_eam.data_lake.demo_ingest import main as demo_ingest_main
from quant_eam.worker.main import main as worker_main


def _approve_and_advance(client: TestClient, job_id: str, step: str) -> None:
    r = client.post(f"/jobs/{job_id}/approve", params={"step": step})
    assert r.status_code == 200, r.text
    assert worker_main(["--run-jobs", "--once"]) == 0


def test_phase25_productized_agent_roles_are_harnessed_and_visible(tmp_path: Path, monkeypatch) -> None:
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

    snapshot_id = "demo_snap_phase25_001"
    assert demo_ingest_main(["--root", str(data_root), "--snapshot-id", snapshot_id]) == 0

    client = TestClient(app)
    idea = {
        "schema_version": "idea_spec_v1",
        "title": "Phase-25 Roles Demo",
        "hypothesis_text": "Agent role productization should remain auditable.",
        "symbols": ["AAA", "BBB"],
        "frequency": "1d",
        "start": "2024-01-01",
        "end": "2024-01-10",
        "evaluation_intent": "phase25",
        "snapshot_id": snapshot_id,
        "policy_bundle_path": "policies/policy_bundle_v1.yaml",
    }
    r = client.post("/jobs/idea", json=idea)
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]

    assert worker_main(["--run-jobs", "--once"]) == 0
    _approve_and_advance(client, job_id, "blueprint")
    _approve_and_advance(client, job_id, "strategy_spec")
    _approve_and_advance(client, job_id, "spec_qa")
    _approve_and_advance(client, job_id, "runspec")
    _approve_and_advance(client, job_id, "trace_preview")

    r = client.get(f"/jobs/{job_id}")
    assert r.status_code == 200
    doc = r.json()
    outputs = doc.get("outputs") or {}
    events = doc.get("events") or []

    # New role agents must be harnessed and indexed in outputs.
    diag_run = Path(str(outputs.get("diagnostics_agent_run_path") or ""))
    curator_run = Path(str(outputs.get("registry_curator_agent_run_path") or ""))
    composer_run = Path(str(outputs.get("composer_agent_run_path") or ""))
    assert diag_run.is_file()
    assert curator_run.is_file()
    assert composer_run.is_file()

    assert contracts_validate.validate_json(diag_run)[0] == contracts_validate.EXIT_OK
    assert contracts_validate.validate_json(curator_run)[0] == contracts_validate.EXIT_OK
    assert contracts_validate.validate_json(composer_run)[0] == contracts_validate.EXIT_OK

    # Timeline must include role events for audit.
    role_actions = set()
    for ev in events:
        if not isinstance(ev, dict):
            continue
        if str(ev.get("event_type") or "") != "REGISTRY_UPDATED":
            continue
        out = ev.get("outputs") if isinstance(ev.get("outputs"), dict) else {}
        action = str(out.get("action") or "").strip()
        if action:
            role_actions.add(action)
    assert "diagnostics_agent_proposed" in role_actions
    assert "registry_curator_proposed" in role_actions
    assert "composer_agent_proposed" in role_actions

    # UI evidence view should surface new roles and their payload sections.
    ui = client.get(f"/ui/jobs/{job_id}")
    assert ui.status_code == 200
    assert "diagnostics_agent" in ui.text
    assert "registry_curator" in ui.text
    assert "composer_agent" in ui.text
    assert "Diagnostics Role Plan" in ui.text
    assert "Registry Curator Summary" in ui.text
    assert "Composer Agent Plan" in ui.text
