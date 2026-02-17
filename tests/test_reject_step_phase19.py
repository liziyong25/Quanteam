from __future__ import annotations

import base64
import json
from pathlib import Path

from fastapi.testclient import TestClient

from quant_eam.api.app import app
from quant_eam.data_lake.demo_ingest import main as demo_ingest_main
from quant_eam.worker.main import main as worker_main


def _basic(user: str, passwd: str) -> dict[str, str]:
    token = base64.b64encode(f"{user}:{passwd}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def test_phase19_api_reject_appends_rejection_evidence_and_fallback(tmp_path: Path, monkeypatch) -> None:
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

    snapshot_id = "demo_snap_reject_phase19_001"
    assert demo_ingest_main(["--root", str(data_root), "--snapshot-id", snapshot_id]) == 0

    client = TestClient(app)
    idea = {
        "schema_version": "idea_spec_v1",
        "title": "Idea Reject API",
        "hypothesis_text": "Reject should append deterministic evidence and keep fallback checkpoint visible.",
        "symbols": ["AAA", "BBB"],
        "frequency": "1d",
        "start": "2024-01-01",
        "end": "2024-01-10",
        "evaluation_intent": "reject_phase19_api",
        "snapshot_id": snapshot_id,
        "policy_bundle_path": "policies/policy_bundle_v1.yaml",
    }
    r = client.post("/jobs/idea", json=idea)
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]

    assert worker_main(["--run-jobs", "--once"]) == 0
    r = client.get(f"/jobs/{job_id}")
    assert r.status_code == 200
    assert any(
        str(ev.get("event_type")) == "WAITING_APPROVAL"
        and isinstance(ev.get("outputs"), dict)
        and str(ev["outputs"].get("step")) == "blueprint"
        for ev in r.json()["events"]
    )

    rj = client.post(f"/jobs/{job_id}/reject", params={"step": "blueprint", "note": "needs revision"})
    assert rj.status_code == 200, rj.text
    body = rj.json()
    assert body["status"] == "rejected"
    assert body["rejected_step"] == "blueprint"
    assert body["fallback_step"] == "blueprint"

    r2 = client.get(f"/jobs/{job_id}")
    assert r2.status_code == 200
    events = r2.json()["events"]
    last = events[-1]
    assert str(last.get("event_type")) == "WAITING_APPROVAL"
    out = last.get("outputs") if isinstance(last.get("outputs"), dict) else {}
    assert str(out.get("step")) == "blueprint"
    reject_action = out.get("reject_action") if isinstance(out.get("reject_action"), dict) else {}
    assert str(reject_action.get("rejected_step")) == "blueprint"
    assert str(reject_action.get("fallback_step")) == "blueprint"
    assert str(reject_action.get("note")) == "needs revision"

    outputs = r2.json().get("outputs") or {}
    reject_log_path = Path(str(outputs.get("reject_log_path")))
    reject_state_path = Path(str(outputs.get("reject_state_path")))
    assert reject_log_path.is_file()
    assert reject_state_path.is_file()

    rows = [json.loads(ln) for ln in reject_log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert rows
    assert rows[-1]["schema_version"] == "job_reject_event_v1"
    assert rows[-1]["job_id"] == job_id
    assert rows[-1]["rejected_step"] == "blueprint"
    assert rows[-1]["fallback_step"] == "blueprint"
    assert rows[-1]["note"] == "needs revision"

    state = json.loads(reject_state_path.read_text(encoding="utf-8"))
    assert state["schema_version"] == "job_reject_state_v1"
    assert state["job_id"] == job_id
    assert state["last_rejection"]["rejected_step"] == "blueprint"


def test_phase19_ui_reject_basic_auth_guard_and_success(tmp_path: Path, monkeypatch) -> None:
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
    monkeypatch.setenv("EAM_WRITE_AUTH_MODE", "basic")
    monkeypatch.setenv("EAM_WRITE_AUTH_USER", "u1")
    monkeypatch.setenv("EAM_WRITE_AUTH_PASS", "p1")

    snapshot_id = "demo_snap_reject_phase19_002"
    assert demo_ingest_main(["--root", str(data_root), "--snapshot-id", snapshot_id]) == 0

    client = TestClient(app)
    idea = {
        "schema_version": "idea_spec_v1",
        "title": "Idea Reject UI",
        "hypothesis_text": "UI reject should be auth-guarded and append evidence on success.",
        "symbols": ["AAA"],
        "frequency": "1d",
        "start": "2024-01-01",
        "end": "2024-01-02",
        "evaluation_intent": "reject_phase19_ui",
        "snapshot_id": snapshot_id,
        "policy_bundle_path": "policies/policy_bundle_v1.yaml",
    }
    r = client.post("/jobs/idea", json=idea, headers=_basic("u1", "p1"))
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]

    assert worker_main(["--run-jobs", "--once"]) == 0

    r = client.post(f"/ui/jobs/{job_id}/reject", params={"step": "blueprint"}, data={"note": "unauthorized"}, follow_redirects=False)
    assert r.status_code == 401

    r = client.post(
        f"/ui/jobs/{job_id}/reject",
        params={"step": "blueprint"},
        data={"note": "rework before approve"},
        headers=_basic("u1", "p1"),
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert (r.headers.get("location") or "") == f"/ui/jobs/{job_id}"

    r2 = client.get(f"/jobs/{job_id}")
    assert r2.status_code == 200
    outputs = r2.json().get("outputs") or {}
    reject_log_path = Path(str(outputs.get("reject_log_path")))
    assert reject_log_path.is_file()
    rows = [json.loads(ln) for ln in reject_log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert rows
    assert rows[-1]["note"] == "rework before approve"


def test_phase21_api_reject_works_after_rerun_on_waiting_step(tmp_path: Path, monkeypatch) -> None:
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

    snapshot_id = "demo_snap_reject_phase21_001"
    assert demo_ingest_main(["--root", str(data_root), "--snapshot-id", snapshot_id]) == 0

    client = TestClient(app)
    idea = {
        "schema_version": "idea_spec_v1",
        "title": "Idea Reject After Rerun",
        "hypothesis_text": "Reject should still work after rerun when the job is waiting approval.",
        "symbols": ["AAA", "BBB"],
        "frequency": "1d",
        "start": "2024-01-01",
        "end": "2024-01-10",
        "evaluation_intent": "reject_phase21_after_rerun",
        "snapshot_id": snapshot_id,
        "policy_bundle_path": "policies/policy_bundle_v1.yaml",
    }
    r = client.post("/jobs/idea", json=idea)
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]

    assert worker_main(["--run-jobs", "--once"]) == 0
    rr = client.post(f"/jobs/{job_id}/rerun", params={"agent_id": "intent_agent_v1"})
    assert rr.status_code == 200, rr.text

    rj = client.post(f"/jobs/{job_id}/reject", params={"step": "blueprint", "note": "reject after rerun"})
    assert rj.status_code == 200, rj.text
    body = rj.json()
    assert body["status"] == "rejected"
    assert body["rejected_step"] == "blueprint"
    assert body["fallback_step"] == "blueprint"

    r2 = client.get(f"/jobs/{job_id}")
    assert r2.status_code == 200
    outputs = r2.json().get("outputs") or {}
    reject_log_path = Path(str(outputs.get("reject_log_path")))
    assert reject_log_path.is_file()

    rows = [json.loads(ln) for ln in reject_log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert rows
    assert rows[-1]["rejected_step"] == "blueprint"
    assert rows[-1]["note"] == "reject after rerun"
