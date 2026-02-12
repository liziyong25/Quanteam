from __future__ import annotations

import base64
from pathlib import Path

from fastapi.testclient import TestClient

from quant_eam.api.app import app


def _basic(user: str, passwd: str) -> dict[str, str]:
    token = base64.b64encode(f"{user}:{passwd}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def test_write_auth_basic_mode_guards_write_endpoints(tmp_path: Path, monkeypatch) -> None:
    job_root = tmp_path / "jobs"
    job_root.mkdir()
    monkeypatch.setenv("EAM_JOB_ROOT", str(job_root))
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    monkeypatch.setenv("EAM_WRITE_AUTH_MODE", "basic")
    monkeypatch.setenv("EAM_WRITE_AUTH_USER", "u1")
    monkeypatch.setenv("EAM_WRITE_AUTH_PASS", "p1")

    client = TestClient(app)

    idea = {
        "schema_version": "idea_spec_v1",
        "title": "Idea Auth",
        "hypothesis_text": "write endpoints should be guarded when auth enabled",
        "symbols": ["AAA"],
        "frequency": "1d",
        "start": "2024-01-01",
        "end": "2024-01-02",
        "evaluation_intent": "auth_test",
        "snapshot_id": "snap_auth_001",
        "policy_bundle_path": "policies/policy_bundle_v1.yaml",
    }

    r = client.post("/jobs/idea", json=idea)
    assert r.status_code == 401

    ui_form = {
        "title": idea["title"],
        "hypothesis_text": idea["hypothesis_text"],
        "symbols": ",".join(idea["symbols"]),
        "frequency": idea["frequency"],
        "start": idea["start"],
        "end": idea["end"],
        "evaluation_intent": idea["evaluation_intent"],
        "snapshot_id": idea["snapshot_id"],
        "policy_bundle_path": idea["policy_bundle_path"],
    }
    r = client.post("/ui/jobs/idea", data=ui_form, follow_redirects=False)
    assert r.status_code == 401

    r = client.post("/ui/jobs/idea", data=ui_form, headers=_basic("u1", "p1"), follow_redirects=False)
    assert r.status_code == 303
    assert (r.headers.get("location") or "").startswith("/ui/jobs/")

    r = client.post("/jobs/idea", json=idea, headers=_basic("u1", "p1"))
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]

    r = client.post(f"/jobs/{job_id}/approve", params={"step": "blueprint"})
    assert r.status_code == 401

    r = client.post(f"/jobs/{job_id}/approve", params={"step": "blueprint"}, headers=_basic("u1", "p1"))
    assert r.status_code == 200, r.text
