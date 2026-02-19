from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any

import httpx
from fastapi.testclient import TestClient

from quant_eam.api.app import app
from quant_eam.data_lake.demo_ingest import main as demo_ingest_main


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _request_via_asgi(method: str, path: str, **kwargs: Any) -> httpx.Response:
    async def _run() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(_run())


def _write_json(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _seed_minimal_run_dossier(tmp_path: Path, monkeypatch) -> str:
    art_root = tmp_path / "artifacts"
    job_root = tmp_path / "jobs"
    art_root.mkdir()
    job_root.mkdir()

    monkeypatch.setenv("EAM_ARTIFACT_ROOT", str(art_root))
    monkeypatch.setenv("EAM_JOB_ROOT", str(job_root))
    run_id = "run_g388_regression_001"
    dossier_dir = art_root / "dossiers" / run_id
    dossier_dir.mkdir(parents=True, exist_ok=True)

    _write_json(
        dossier_dir / "dossier_manifest.json",
        {
            "schema_version": "dossier_manifest_v1",
            "run_id": run_id,
            "data_snapshot_id": "demo_snap_ui_g388_regression_001",
        },
    )
    _write_json(dossier_dir / "metrics.json", {"schema_version": "metrics_v1", "total_return": 0.01, "trade_count": 1})
    _write_json(
        dossier_dir / "config_snapshot.json",
        {
            "schema_version": "config_snapshot_v1",
            "runspec": {
                "segments": {
                    "test": {
                        "start": "2024-01-01",
                        "end": "2024-01-10",
                        "as_of": "2024-01-10T00:00:00+08:00",
                    }
                },
                "extensions": {"symbols": ["AAA"]},
            },
        },
    )
    _write_json(
        dossier_dir / "gate_results.json",
        {
            "schema_version": "gate_results_v1",
            "overall_pass": True,
            "results": [{"gate_id": "basic_sanity", "pass": True, "status": "pass"}],
        },
    )
    return run_id


def _create_idea_job_for_ui(tmp_path: Path, monkeypatch) -> tuple[Path, str]:
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
    monkeypatch.setenv("EAM_LLM_PROVIDER", "mock")
    monkeypatch.setenv("EAM_LLM_MODE", "live")
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    snapshot_id = "demo_snap_ui_g388_idea_001"
    assert demo_ingest_main(["--root", str(data_root), "--snapshot-id", snapshot_id]) == 0

    form = {
        "title": "G388 Idea Demo",
        "hypothesis_text": "g388 api/ui/integration regression",
        "symbols": "AAA,BBB",
        "frequency": "1d",
        "start": "2024-01-01",
        "end": "2024-01-10",
        "evaluation_intent": "g388",
        "snapshot_id": snapshot_id,
        "policy_bundle_path": "policies/policy_bundle_v1.yaml",
    }
    created = _request_via_asgi("POST", "/ui/jobs/idea", data=form, follow_redirects=False)
    assert created.status_code == 303, created.text
    loc = str(created.headers.get("location") or "")
    assert loc.startswith("/ui/jobs/")
    return job_root, loc.rsplit("/", 1)[-1]


def test_g388_wb069_api_ui_e2e_and_integration(tmp_path: Path, monkeypatch) -> None:
    job_root, job_id = _create_idea_job_for_ui(tmp_path, monkeypatch)

    ui_job = _request_via_asgi("GET", f"/ui/jobs/{job_id}")
    assert ui_job.status_code == 200
    assert f"Job {job_id}" in ui_job.text
    assert "Events (append-only)" in ui_job.text

    api_job = _request_via_asgi("GET", f"/jobs/{job_id}")
    assert api_job.status_code == 200
    api_doc = api_job.json()
    assert api_doc["job_id"] == job_id
    events = api_doc.get("events")
    assert isinstance(events, list)
    assert any(str(ev.get("event_type")) == "IDEA_SUBMITTED" for ev in events if isinstance(ev, dict))

    approved = _request_via_asgi("POST", f"/jobs/{job_id}/approve?step=blueprint")
    assert approved.status_code == 200
    approved_doc = approved.json()
    assert approved_doc["status"] in {"approved", "noop"}

    api_job_after = _request_via_asgi("GET", f"/jobs/{job_id}")
    assert api_job_after.status_code == 200
    events_after = api_job_after.json().get("events")
    assert isinstance(events_after, list)
    assert any(
        str(ev.get("event_type")) == "APPROVED"
        and isinstance(ev.get("outputs"), dict)
        and str(ev["outputs"].get("step")) == "blueprint"
        for ev in events_after
        if isinstance(ev, dict)
    )

    events_path = job_root / job_id / "events.jsonl"
    assert events_path.is_file()


def test_g388_wb070_regression_ui_jobs_runs_qa_fetch(tmp_path: Path, monkeypatch) -> None:
    run_id = _seed_minimal_run_dossier(tmp_path, monkeypatch)
    with TestClient(app) as client:
        jobs_page = client.get("/ui/jobs")
        assert jobs_page.status_code == 200
        assert "Workflow: blueprint -> compile -> WAITING_APPROVAL -> run -> gates -> registry" in jobs_page.text

        runs_page = client.get(f"/ui/runs/{run_id}")
        assert runs_page.status_code == 200
        assert f"Run {run_id}" in runs_page.text

        qa_fetch_page = client.get("/ui/qa-fetch")
        assert qa_fetch_page.status_code == 200
        assert "QA Fetch Explorer" in qa_fetch_page.text
        assert "<form" not in qa_fetch_page.text.lower()


def test_g388_wb071_job_events_append_only_guard(tmp_path: Path, monkeypatch) -> None:
    job_root, job_id = _create_idea_job_for_ui(tmp_path, monkeypatch)
    events_path = job_root / job_id / "events.jsonl"

    before_rows = [ln for ln in events_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert before_rows

    rejected = _request_via_asgi(
        "POST",
        f"/ui/jobs/{job_id}/reject?step=blueprint",
        data={"note": "append-only-check"},
        follow_redirects=False,
    )
    assert rejected.status_code == 303

    after_reject_rows = [ln for ln in events_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(after_reject_rows) > len(before_rows)
    assert after_reject_rows[: len(before_rows)] == before_rows

    approved = _request_via_asgi(
        "POST",
        f"/ui/jobs/{job_id}/approve?step=blueprint",
        data={},
        follow_redirects=False,
    )
    assert approved.status_code == 303

    after_approve_rows = [ln for ln in events_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(after_approve_rows) > len(after_reject_rows)
    assert after_approve_rows[: len(after_reject_rows)] == after_reject_rows

    approved_noop = _request_via_asgi(
        "POST",
        f"/ui/jobs/{job_id}/approve?step=blueprint",
        data={},
        follow_redirects=False,
    )
    assert approved_noop.status_code == 303
    after_noop_rows = [ln for ln in events_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert after_noop_rows == after_approve_rows


def test_g388_wb072_object_model_alignment_with_v05_draft(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("EAM_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("EAM_JOB_ROOT", str(tmp_path / "jobs"))
    (tmp_path / "artifacts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "jobs").mkdir(parents=True, exist_ok=True)

    draft_doc = _repo_root() / "Quant‑EAM Whole View Framework.md（v0.5‑draft）.md"
    assert draft_doc.is_file(), "v0.5 draft object-model source must exist"
    draft_text = draft_doc.read_text(encoding="utf-8")
    draft_object_titles = re.findall(r"^###\\s*4\\.(\\d+)\\s*(.+)$", draft_text, flags=re.MULTILINE)
    assert draft_object_titles, "draft section 4 object model headings must be present"

    with TestClient(app) as client:
        object_model_page = client.get("/ui/object-model")
        assert object_model_page.status_code == 200
        object_model_text = object_model_page.text

        for required_name in ("IdeaSpec", "Blueprint", "RunSpec", "Dossier", "GateResults", "Experience Card"):
            assert required_name in object_model_text

        workbench_page = client.get("/ui/workbench")
        assert workbench_page.status_code == 200
        assert "DataIntent card" in workbench_page.text
        assert "FetchRequest card" in workbench_page.text
