from __future__ import annotations

import json
from pathlib import Path

from quant_eam.orchestrator.workflow import _sync_fetch_evidence_into_dossier


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_sync_fetch_evidence_into_dossier_updates_manifest_and_paths(tmp_path: Path) -> None:
    outputs_dir = tmp_path / "jobs" / "job_001" / "outputs"
    fetch_dir = outputs_dir / "fetch"
    fetch_dir.mkdir(parents=True, exist_ok=True)

    req_path = fetch_dir / "fetch_request.json"
    meta_path = fetch_dir / "fetch_result_meta.json"
    preview_path = fetch_dir / "fetch_preview.csv"
    idx_path = fetch_dir / "fetch_steps_index.json"

    _write_json(req_path, {"mode": "smoke", "function": "fetch_not_in_baseline", "kwargs": {"symbol": "000001"}})
    _write_json(meta_path, {"status": "blocked_source_missing", "reason": "not_in_baseline"})
    preview_path.write_text("status,reason\nblocked_source_missing,not_in_baseline\n", encoding="utf-8")
    _write_json(
        idx_path,
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

    dossier_dir = tmp_path / "artifacts" / "dossiers" / "run_001"
    dossier_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        dossier_dir / "dossier_manifest.json",
        {
            "schema_version": "dossier_v1",
            "run_id": "run_001",
            "created_at": "2026-02-13T00:00:00Z",
            "blueprint_hash": "abc",
            "policy_bundle_id": "policy_bundle_v1",
            "data_snapshot_id": "snap_001",
            "append_only": True,
            "artifacts": {"metrics": "metrics.json"},
            "hashes": {},
        },
    )

    out = _sync_fetch_evidence_into_dossier(outputs_dir=outputs_dir, dossier_dir=dossier_dir)
    assert out["synced"] is True
    assert out["copied_count"] >= 4

    dossier_fetch = dossier_dir / "fetch"
    assert (dossier_fetch / "fetch_request.json").is_file()
    assert (dossier_fetch / "fetch_result_meta.json").is_file()
    assert (dossier_fetch / "fetch_preview.csv").is_file()
    assert (dossier_fetch / "fetch_steps_index.json").is_file()

    idx_synced = json.loads((dossier_fetch / "fetch_steps_index.json").read_text(encoding="utf-8"))
    step = idx_synced["steps"][0]
    assert step["request_path"] == (dossier_fetch / "fetch_request.json").as_posix()
    assert step["result_meta_path"] == (dossier_fetch / "fetch_result_meta.json").as_posix()
    assert step["preview_path"] == (dossier_fetch / "fetch_preview.csv").as_posix()

    manifest = json.loads((dossier_dir / "dossier_manifest.json").read_text(encoding="utf-8"))
    artifacts = manifest.get("artifacts") or {}
    assert artifacts.get("fetch_steps_index") == "fetch/fetch_steps_index.json"
    assert artifacts.get("fetch_request") == "fetch/fetch_request.json"
    hashes = manifest.get("hashes") or {}
    assert "fetch/fetch_steps_index.json" in hashes
