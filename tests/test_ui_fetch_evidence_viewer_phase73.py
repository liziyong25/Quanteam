from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from quant_eam.api.app import app


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")


def test_ui_job_detail_renders_dossier_fetch_evidence_viewer(tmp_path: Path, monkeypatch) -> None:
    job_root = tmp_path / "jobs"
    monkeypatch.setenv("EAM_JOB_ROOT", str(job_root))

    job_id = "a1b2c3d4e5f6"
    job_dir = job_root / job_id
    outputs_dir = job_dir / "outputs"
    dossier_dir = tmp_path / "artifacts" / "dossiers" / "run_fetch_001"
    dossier_fetch = dossier_dir / "fetch"
    dossier_fetch.mkdir(parents=True, exist_ok=True)

    _write_json(
        job_dir / "job_spec.json",
        {
            "schema_version": "idea_spec_v1",
            "title": "fetch viewer",
            "snapshot_id": "snap_demo",
            "policy_bundle_path": "policies/policy_bundle_v1.yaml",
        },
    )
    _write_jsonl(job_dir / "events.jsonl", [{"event_type": "DONE", "outputs": {"status": "done"}}])

    req_path = dossier_fetch / "fetch_request.json"
    meta_path = dossier_fetch / "fetch_result_meta.json"
    preview_path = dossier_fetch / "fetch_preview.csv"
    _write_json(req_path, {"mode": "smoke", "function": "fetch_not_in_baseline", "kwargs": {"symbol": "000001"}})
    _write_json(meta_path, {"status": "blocked_source_missing", "reason": "not_in_baseline"})
    preview_path.write_text("symbol,status\n000001,blocked_source_missing\n", encoding="utf-8")
    _write_json(
        dossier_fetch / "fetch_steps_index.json",
        {
            "schema_version": "qa_fetch_steps_index_v1",
            "generated_at": "2026-02-13T00:00:00Z",
            "steps": [
                {
                    "step_index": 1,
                    "step_kind": "single_fetch",
                    "status": "blocked_source_missing",
                    "request_path": req_path.as_posix(),
                    "result_meta_path": meta_path.as_posix(),
                    "preview_path": preview_path.as_posix(),
                }
            ],
        },
    )

    _write_json(
        outputs_dir / "outputs.json",
        {
            "run_id": "run_fetch_001",
            "dossier_path": dossier_dir.as_posix(),
        },
    )

    client = TestClient(app)
    r = client.get(f"/ui/jobs/{job_id}")
    assert r.status_code == 200
    text = r.text
    assert "Fetch Evidence Viewer" in text
    assert "fetch_steps_index.json" in text
    assert "single_fetch" in text
    assert "data-testid=\"fetch-evidence-step-1\"" in text
