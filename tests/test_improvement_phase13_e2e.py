from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from quant_eam.api.app import app
from quant_eam.contracts import validate as contracts_validate
from quant_eam.data_lake.demo_ingest import main as demo_ingest_main
from quant_eam.worker.main import main as worker_main


def test_phase13_budget_proposals_and_spawn(tmp_path: Path, monkeypatch) -> None:
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

    snapshot_id = "demo_snap_phase13_001"
    assert demo_ingest_main(["--root", str(data_root), "--snapshot-id", snapshot_id]) == 0

    # Tight budget for test determinism.
    budget_path = tmp_path / "budget_policy_v1_test.yaml"
    budget_path.write_text(
        "\n".join(
            [
                "policy_id: budget_policy_v1_test",
                'policy_version: "v1"',
                "title: Budget Policy v1 (test)",
                "description: test budget",
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
        "title": "Idea Phase13",
        "hypothesis_text": "Budget/proposals/spawn plumbing should be deterministic.",
        "symbols": ["AAA", "BBB"],
        "frequency": "1d",
        "start": "2024-01-01",
        "end": "2024-01-10",
        "evaluation_intent": "phase13_e2e",
        "snapshot_id": snapshot_id,
        "policy_bundle_path": "policies/policy_bundle_v1.yaml",
        # additionalProperties allowed by idea_spec_v1:
        "budget_policy_path": str(budget_path),
    }

    r = client.post("/jobs/idea", json=idea)
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]
    # Canonical policy bundle reference is stored by id (path is convenience only).
    job_dir = job_root / job_id
    spec_doc = json.loads((job_dir / "job_spec.json").read_text(encoding="utf-8"))
    assert spec_doc.get("policy_bundle_id") == "policy_bundle_v1_default"
    ref = json.loads((job_dir / "outputs" / "policy_bundle_ref.json").read_text(encoding="utf-8"))
    assert ref.get("policy_bundle_id") == "policy_bundle_v1_default"
    assert isinstance(ref.get("policy_bundle_sha256"), str) and len(ref.get("policy_bundle_sha256")) == 64

    # Advance to blueprint checkpoint
    assert worker_main(["--run-jobs", "--once"]) == 0
    r = client.post(f"/jobs/{job_id}/approve", params={"step": "blueprint"})
    assert r.status_code == 200
    assert worker_main(["--run-jobs", "--once"]) == 0

    # Approve strategy_spec -> spec_qa -> runspec -> trace_preview
    r = client.post(f"/jobs/{job_id}/approve", params={"step": "strategy_spec"})
    assert r.status_code == 200
    assert worker_main(["--run-jobs", "--once"]) == 0
    r = client.post(f"/jobs/{job_id}/approve", params={"step": "spec_qa"})
    assert r.status_code == 200
    assert worker_main(["--run-jobs", "--once"]) == 0
    r = client.post(f"/jobs/{job_id}/approve", params={"step": "runspec"})
    assert r.status_code == 200
    assert worker_main(["--run-jobs", "--once"]) == 0
    r = client.post(f"/jobs/{job_id}/approve", params={"step": "trace_preview"})
    assert r.status_code == 200

    # This pass should run -> gates -> registry -> report -> improvements checkpoint.
    assert worker_main(["--run-jobs", "--once"]) == 0
    r = client.get(f"/jobs/{job_id}")
    assert r.status_code == 200
    evs = r.json()["events"]
    assert any(ev.get("event_type") == "REPORT_COMPLETED" for ev in evs)
    assert any(ev.get("event_type") == "IMPROVEMENTS_PROPOSED" for ev in evs)
    assert any(
        ev.get("event_type") == "WAITING_APPROVAL" and (ev.get("outputs") or {}).get("step") == "improvements" for ev in evs
    )

    # Fetch proposals and validate contract.
    r = client.get(f"/jobs/{job_id}/proposals")
    assert r.status_code == 200, r.text
    proposals_doc = r.json()["proposals"]
    assert isinstance(proposals_doc, dict)
    code, _msg = contracts_validate.validate_payload(proposals_doc)
    assert code == contracts_validate.EXIT_OK
    proposals = proposals_doc.get("proposals")
    assert isinstance(proposals, list)
    assert len(proposals) == 1  # max_proposals_per_job=1
    proposal_id = str(proposals[0]["proposal_id"])

    # Spawn one child job from proposal.
    r = client.post(f"/jobs/{job_id}/spawn", params={"proposal_id": proposal_id})
    assert r.status_code == 200, r.text
    child_job_id = r.json()["child_job_id"]
    assert isinstance(child_job_id, str) and len(child_job_id) == 12

    # Second spawn must fail due to max_spawn_per_job=1.
    r = client.post(f"/jobs/{job_id}/spawn", params={"proposal_id": proposal_id})
    assert r.status_code == 409, r.text
    # Failure must be evidence-logged (append-only) with stop reason.
    r2 = client.get(f"/jobs/{job_id}")
    assert r2.status_code == 200
    evs_stop = r2.json()["events"]
    assert any(ev.get("event_type") == "STOPPED_BUDGET" for ev in evs_stop), json.dumps(evs_stop, indent=2, sort_keys=True)

    # Child job must return to blueprint review checkpoint (no auto-run).
    assert worker_main(["--run-jobs", "--once"]) == 0
    r = client.get(f"/jobs/{child_job_id}")
    assert r.status_code == 200
    evs2 = r.json()["events"]
    assert any(
        ev.get("event_type") == "WAITING_APPROVAL" and (ev.get("outputs") or {}).get("step") == "blueprint" for ev in evs2
    )


def test_phase13r_max_total_iterations_stops_improvements(tmp_path: Path, monkeypatch) -> None:
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

    snapshot_id = "demo_snap_phase13r_001"
    assert demo_ingest_main(["--root", str(data_root), "--snapshot-id", snapshot_id]) == 0

    # max_total_iterations=1 means root generation=0 cannot spawn any child (attempted child generation=1 is rejected).
    budget_path = tmp_path / "budget_policy_v1_test_stop.yaml"
    budget_path.write_text(
        "\n".join(
            [
                "policy_id: budget_policy_v1_test_stop",
                'policy_version: "v1"',
                "title: Budget Policy v1 (test stop)",
                "description: test budget stop",
                "params:",
                "  max_proposals_per_job: 1",
                "  max_spawn_per_job: 1",
                "  max_total_iterations: 1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    client = TestClient(app)
    idea = {
        "schema_version": "idea_spec_v1",
        "title": "Idea Phase13R",
        "hypothesis_text": "max_total_iterations should stop improvements when no spawn is allowed.",
        "symbols": ["AAA"],
        "frequency": "1d",
        "start": "2024-01-01",
        "end": "2024-01-03",
        "evaluation_intent": "phase13r_e2e",
        "snapshot_id": snapshot_id,
        "policy_bundle_path": "policies/policy_bundle_v1.yaml",
        "budget_policy_path": str(budget_path),
    }

    r = client.post("/jobs/idea", json=idea)
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]

    # Advance through checkpoints to reach post-report stage.
    assert worker_main(["--run-jobs", "--once"]) == 0
    assert client.post(f"/jobs/{job_id}/approve", params={"step": "blueprint"}).status_code == 200
    assert worker_main(["--run-jobs", "--once"]) == 0
    assert client.post(f"/jobs/{job_id}/approve", params={"step": "strategy_spec"}).status_code == 200
    assert worker_main(["--run-jobs", "--once"]) == 0
    assert client.post(f"/jobs/{job_id}/approve", params={"step": "spec_qa"}).status_code == 200
    assert worker_main(["--run-jobs", "--once"]) == 0
    assert client.post(f"/jobs/{job_id}/approve", params={"step": "runspec"}).status_code == 200
    assert worker_main(["--run-jobs", "--once"]) == 0
    assert client.post(f"/jobs/{job_id}/approve", params={"step": "trace_preview"}).status_code == 200

    # This pass should run -> gates -> registry -> report -> STOPPED_BUDGET -> DONE (no improvements proposed).
    assert worker_main(["--run-jobs", "--once"]) == 0
    r = client.get(f"/jobs/{job_id}")
    assert r.status_code == 200
    evs = r.json()["events"]
    assert any(ev.get("event_type") == "REPORT_COMPLETED" for ev in evs)
    assert any(ev.get("event_type") == "STOPPED_BUDGET" for ev in evs)
    assert any(ev.get("event_type") == "DONE" for ev in evs)
    assert not any(ev.get("event_type") == "IMPROVEMENTS_PROPOSED" for ev in evs)

    # Proposals endpoint should be unavailable.
    r = client.get(f"/jobs/{job_id}/proposals")
    assert r.status_code == 404
