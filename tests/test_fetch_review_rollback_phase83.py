from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from quant_eam.api.app import app
from quant_eam.data_lake.demo_ingest import main as demo_ingest_main
from quant_eam.worker.main import main as worker_main


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _seed_dossier_fetch_evidence(*, dossier_dir: Path) -> None:
    fetch_dir = dossier_dir / "fetch"
    fetch_dir.mkdir(parents=True, exist_ok=True)

    req_path = fetch_dir / "fetch_request.json"
    meta_path = fetch_dir / "fetch_result_meta.json"
    preview_path = fetch_dir / "fetch_preview.csv"
    _write_json(req_path, {"mode": "smoke", "function": "fetch_stock_day", "kwargs": {"symbol": "000001"}})
    _write_json(meta_path, {"status": "pass_has_data", "reason": "ok", "row_count": 1})
    preview_path.write_text("code,date,close\n000001,2024-01-02,10.0\n", encoding="utf-8")
    _write_json(
        fetch_dir / "fetch_steps_index.json",
        {
            "schema_version": "qa_fetch_steps_index_v1",
            "generated_at": "2026-02-13T00:00:00Z",
            "steps": [
                {
                    "step_index": 1,
                    "step_kind": "single_fetch",
                    "status": "pass_has_data",
                    "request_path": req_path.as_posix(),
                    "result_meta_path": meta_path.as_posix(),
                    "preview_path": preview_path.as_posix(),
                }
            ],
        },
    )


def test_fetch_review_rollback_rerun_rereview_ui_loop(tmp_path: Path, monkeypatch) -> None:
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

    snapshot_id = "demo_snap_fetch_review_rollback_001"
    assert demo_ingest_main(["--root", str(data_root), "--snapshot-id", snapshot_id]) == 0

    client = TestClient(app)
    idea = {
        "schema_version": "idea_spec_v1",
        "title": "Fetch Review Rollback Loop",
        "hypothesis_text": "fetch review reject/rerun/re-review should remain evidence-visible in UI",
        "symbols": ["AAA", "BBB"],
        "frequency": "1d",
        "start": "2024-01-01",
        "end": "2024-01-10",
        "evaluation_intent": "fetch_review_rollback_phase83",
        "snapshot_id": snapshot_id,
        "policy_bundle_path": "policies/policy_bundle_v1.yaml",
    }
    r = client.post("/jobs/idea", json=idea)
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]

    # Advance once so job enters waiting approval state.
    assert worker_main(["--run-jobs", "--once"]) == 0

    # Seed dossier fetch evidence for read-only fetch reviewer.
    dossier_dir = art_root / "dossiers" / "run_fetch_review_rollback_001"
    _seed_dossier_fetch_evidence(dossier_dir=dossier_dir)
    outputs_path = job_root / job_id / "outputs" / "outputs.json"
    outputs_doc = {}
    if outputs_path.is_file():
        outputs_doc = json.loads(outputs_path.read_text(encoding="utf-8"))
    outputs_doc["run_id"] = "run_fetch_review_rollback_001"
    outputs_doc["dossier_path"] = dossier_dir.as_posix()
    _write_json(outputs_path, outputs_doc)

    # review fail -> rollback
    rej = client.post(f"/jobs/{job_id}/reject", params={"step": "blueprint", "note": "fetch evidence mismatch"})
    assert rej.status_code == 200, rej.text
    assert rej.json()["status"] == "rejected"
    assert rej.json()["fallback_step"] == "blueprint"

    # rerun after rollback
    rer = client.post(f"/jobs/{job_id}/rerun", params={"agent_id": "intent_agent_v1"})
    assert rer.status_code == 200, rer.text
    assert rer.json()["status"] == "rerun_requested"

    # re-review approval
    ap = client.post(f"/jobs/{job_id}/approve", params={"step": "blueprint"})
    assert ap.status_code == 200, ap.text
    assert ap.json()["status"] in {"approved", "noop"}

    ui = client.get(f"/ui/jobs/{job_id}")
    assert ui.status_code == 200
    text = ui.text
    assert "Fetch Evidence Viewer" in text
    assert "data-testid=\"fetch-evidence-step-1\"" in text
    assert "Rejection Evidence" in text
    assert "Rerun Evidence" in text
