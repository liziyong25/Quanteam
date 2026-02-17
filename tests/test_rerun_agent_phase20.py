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


def test_phase20_api_rerun_executes_agent_and_writes_evidence(tmp_path: Path, monkeypatch) -> None:
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

    snapshot_id = "demo_snap_rerun_phase20_001"
    assert demo_ingest_main(["--root", str(data_root), "--snapshot-id", snapshot_id]) == 0

    client = TestClient(app)
    idea = {
        "schema_version": "idea_spec_v1",
        "title": "Idea Rerun API",
        "hypothesis_text": "Rerun should execute selected agent and append rerun evidence.",
        "symbols": ["AAA", "BBB"],
        "frequency": "1d",
        "start": "2024-01-01",
        "end": "2024-01-10",
        "evaluation_intent": "rerun_phase20_api",
        "snapshot_id": snapshot_id,
        "policy_bundle_path": "policies/policy_bundle_v1.yaml",
    }
    r = client.post("/jobs/idea", json=idea)
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]

    assert worker_main(["--run-jobs", "--once"]) == 0
    rr = client.post(f"/jobs/{job_id}/rerun", params={"agent_id": "intent_agent_v1"})
    assert rr.status_code == 200, rr.text
    body = rr.json()
    assert body["status"] == "rerun_requested"
    assert body["agent_id"] == "intent_agent_v1"
    assert str(body["rerun_id"]).startswith("rerun_")
    agent_run_path = Path(body["agent_run_path"])
    assert agent_run_path.is_file()
    assert "/reruns/" in agent_run_path.as_posix()
    llm_session = agent_run_path.parent / "llm_session.json"
    assert llm_session.is_file()

    r2 = client.get(f"/jobs/{job_id}")
    assert r2.status_code == 200
    outputs = r2.json().get("outputs") or {}
    rerun_log_path = Path(str(outputs.get("rerun_log_path")))
    rerun_state_path = Path(str(outputs.get("rerun_state_path")))
    assert rerun_log_path.is_file()
    assert rerun_state_path.is_file()
    rows = [json.loads(ln) for ln in rerun_log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert rows
    assert rows[-1]["schema_version"] == "job_rerun_event_v1"
    assert rows[-1]["job_id"] == job_id
    assert rows[-1]["agent_id"] == "intent_agent_v1"
    assert rows[-1]["agent_run_path"] == agent_run_path.as_posix()

    events = r2.json().get("events") or []
    assert any(
        str(ev.get("event_type")) == "SPAWNED"
        and isinstance(ev.get("outputs"), dict)
        and str(ev["outputs"].get("action")) == "rerun_requested"
        and str(ev["outputs"].get("agent_id")) == "intent_agent_v1"
        for ev in events
    )


def test_phase20_ui_rerun_basic_auth_guard_and_success(tmp_path: Path, monkeypatch) -> None:
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

    snapshot_id = "demo_snap_rerun_phase20_002"
    assert demo_ingest_main(["--root", str(data_root), "--snapshot-id", snapshot_id]) == 0

    client = TestClient(app)
    idea = {
        "schema_version": "idea_spec_v1",
        "title": "Idea Rerun UI",
        "hypothesis_text": "UI rerun should be write-auth guarded.",
        "symbols": ["AAA"],
        "frequency": "1d",
        "start": "2024-01-01",
        "end": "2024-01-02",
        "evaluation_intent": "rerun_phase20_ui",
        "snapshot_id": snapshot_id,
        "policy_bundle_path": "policies/policy_bundle_v1.yaml",
    }
    r = client.post("/jobs/idea", json=idea, headers=_basic("u1", "p1"))
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]

    assert worker_main(["--run-jobs", "--once"]) == 0

    r = client.post(
        f"/ui/jobs/{job_id}/rerun",
        data={"agent_id": "intent_agent_v1"},
        follow_redirects=False,
    )
    assert r.status_code == 401

    r = client.post(
        f"/ui/jobs/{job_id}/rerun",
        data={"agent_id": "intent_agent_v1"},
        headers=_basic("u1", "p1"),
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert (r.headers.get("location") or "") == f"/ui/jobs/{job_id}"

    r2 = client.get(f"/jobs/{job_id}")
    assert r2.status_code == 200
    outputs = r2.json().get("outputs") or {}
    rerun_log_path = Path(str(outputs.get("rerun_log_path")))
    assert rerun_log_path.is_file()
    rows = [json.loads(ln) for ln in rerun_log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert rows
    assert rows[-1]["agent_id"] == "intent_agent_v1"


def test_phase21_rerun_does_not_consume_spawn_budget(tmp_path: Path, monkeypatch) -> None:
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

    snapshot_id = "demo_snap_rerun_phase21_001"
    assert demo_ingest_main(["--root", str(data_root), "--snapshot-id", snapshot_id]) == 0

    budget_path = tmp_path / "budget_policy_v1_phase21.yaml"
    budget_path.write_text(
        "\n".join(
            [
                "policy_id: budget_policy_v1_phase21",
                'policy_version: "v1"',
                "title: Budget Policy v1 (phase21)",
                "description: phase21 budget",
                "params:",
                "  max_proposals_per_job: 1",
                "  max_spawn_per_job: 1",
                "  max_total_iterations: 10",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    client = TestClient(app)
    idea = {
        "schema_version": "idea_spec_v1",
        "title": "Idea Rerun Budget Semantics",
        "hypothesis_text": "Rerun should not consume spawn budget.",
        "symbols": ["AAA", "BBB"],
        "frequency": "1d",
        "start": "2024-01-01",
        "end": "2024-01-10",
        "evaluation_intent": "rerun_phase21_budget",
        "snapshot_id": snapshot_id,
        "policy_bundle_path": "policies/policy_bundle_v1.yaml",
        "budget_policy_path": str(budget_path),
    }
    r = client.post("/jobs/idea", json=idea)
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]

    reached_improvements = False
    for _ in range(12):
        assert worker_main(["--run-jobs", "--once"]) == 0
        state = client.get(f"/jobs/{job_id}")
        assert state.status_code == 200, state.text
        events = state.json().get("events") or []
        if not events:
            continue
        last = events[-1]
        last_type = str(last.get("event_type") or "")
        if last_type == "WAITING_APPROVAL":
            out = last.get("outputs") if isinstance(last.get("outputs"), dict) else {}
            waiting_step = str(out.get("step") or "").strip()
            if waiting_step == "improvements":
                reached_improvements = True
                break
            assert client.post(f"/jobs/{job_id}/approve", params={"step": waiting_step}).status_code == 200
    assert reached_improvements

    rp = client.get(f"/jobs/{job_id}/proposals")
    assert rp.status_code == 200, rp.text
    proposals = (rp.json().get("proposals") or {}).get("proposals") or []
    assert isinstance(proposals, list) and proposals
    proposal_id = str(proposals[0]["proposal_id"])

    rr = client.post(f"/jobs/{job_id}/rerun", params={"agent_id": "intent_agent_v1"})
    assert rr.status_code == 200, rr.text

    rs1 = client.post(f"/jobs/{job_id}/spawn", params={"proposal_id": proposal_id})
    assert rs1.status_code == 200, rs1.text

    rs2 = client.post(f"/jobs/{job_id}/spawn", params={"proposal_id": proposal_id})
    assert rs2.status_code == 409, rs2.text

    rj = client.get(f"/jobs/{job_id}")
    assert rj.status_code == 200
    events = rj.json().get("events") or []
    rerun_spawns = [
        ev
        for ev in events
        if str(ev.get("event_type")) == "SPAWNED"
        and isinstance(ev.get("outputs"), dict)
        and str(ev["outputs"].get("action")) == "rerun_requested"
    ]
    assert rerun_spawns
    child_spawns = [
        ev
        for ev in events
        if str(ev.get("event_type")) == "SPAWNED"
        and isinstance(ev.get("outputs"), dict)
        and str(ev["outputs"].get("action", "")) != "rerun_requested"
    ]
    assert len(child_spawns) == 1

    stopped = [ev for ev in events if str(ev.get("event_type")) == "STOPPED_BUDGET"]
    assert stopped
    stop_outputs = stopped[-1].get("outputs") if isinstance(stopped[-1].get("outputs"), dict) else {}
    assert int(stop_outputs.get("current_spawn_count")) == 1
