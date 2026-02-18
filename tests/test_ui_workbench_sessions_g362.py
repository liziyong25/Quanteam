from __future__ import annotations

import asyncio

import httpx
from pathlib import Path

from quant_eam.api.app import app


def _request_via_asgi(method: str, path: str, **kwargs):
    async def _run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(_run())


def _setup_env(tmp_path: Path, monkeypatch) -> None:
    art_root = tmp_path / "artifacts"
    job_root = tmp_path / "jobs"
    reg_root = tmp_path / "registry"
    data_root = tmp_path / "data"
    art_root.mkdir()
    job_root.mkdir()
    reg_root.mkdir()
    data_root.mkdir()

    monkeypatch.setenv("EAM_ARTIFACT_ROOT", str(art_root))
    monkeypatch.setenv("EAM_JOB_ROOT", str(job_root))
    monkeypatch.setenv("EAM_REGISTRY_ROOT", str(reg_root))
    monkeypatch.setenv("EAM_DATA_ROOT", str(data_root))
    monkeypatch.setenv("EAM_WORKBENCH_REAL_JOBS", "0")


def _create_session(*, owner: str = "alice") -> str:
    resp = _request_via_asgi(
        "POST",
        "/workbench/sessions",
        headers={"x-workbench-owner": owner},
        json={
            "title": "G362 endpoint coverage",
            "symbols": "AAA,BBB",
            "hypothesis_text": "verify events/fetch-probe/draft endpoints",
        },
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["session_id"])


def test_workbench_events_supports_polling_and_sse_modes(tmp_path: Path, monkeypatch) -> None:
    _setup_env(tmp_path, monkeypatch)
    session_id = _create_session(owner="alice")

    _request_via_asgi(
        "POST",
        f"/workbench/sessions/{session_id}/message",
        headers={"x-workbench-owner": "alice"},
        json={"message": "seed one user message event"},
    )

    polling = _request_via_asgi(
        "GET",
        f"/workbench/sessions/{session_id}/events?after=0&limit=5",
        headers={"x-workbench-owner": "alice"},
    )
    assert polling.status_code == 200, polling.text
    polling_doc = polling.json()
    assert polling_doc["schema_version"] == "workbench_session_events_response_v1"
    assert polling_doc["mode"] == "polling"
    assert polling_doc["owner_id"] == "alice"
    assert polling_doc["event_count"] <= 5

    forbidden = _request_via_asgi(
        "GET",
        f"/workbench/sessions/{session_id}/events",
        headers={"x-workbench-owner": "bob"},
    )
    assert forbidden.status_code == 403

    sse = _request_via_asgi(
        "GET",
        f"/workbench/sessions/{session_id}/events?mode=sse&after=0",
        headers={"x-workbench-owner": "alice", "accept": "text/event-stream"},
    )
    assert sse.status_code == 200, sse.text
    assert "text/event-stream" in str(sse.headers.get("content-type", "")).lower()
    assert "event: ready" in sse.text
    assert "event: end" in sse.text
    assert f'"session_id":"{session_id}"' in sse.text


def test_workbench_fetch_probe_appends_probe_events(tmp_path: Path, monkeypatch) -> None:
    _setup_env(tmp_path, monkeypatch)
    session_id = _create_session(owner="alice")

    before = _request_via_asgi(
        "GET",
        f"/workbench/sessions/{session_id}/events",
        headers={"x-workbench-owner": "alice"},
    ).json()["event_count"]

    probe = _request_via_asgi(
        "POST",
        f"/workbench/sessions/{session_id}/fetch-probe",
        headers={"x-workbench-owner": "alice"},
        json={"symbols": ["AAA", "BBB"]},
    )
    assert probe.status_code == 200, probe.text
    probe_doc = probe.json()
    assert probe_doc["schema_version"] == "workbench_session_fetch_probe_response_v1"
    assert probe_doc["owner_id"] == "alice"
    assert probe_doc["status"] == "ok"

    events_doc = _request_via_asgi(
        "GET",
        f"/workbench/sessions/{session_id}/events",
        headers={"x-workbench-owner": "alice"},
    ).json()
    assert events_doc["event_count"] > before
    event_types = [str(ev.get("event_type") or "") for ev in events_doc.get("events", []) if isinstance(ev, dict)]
    assert "fetch_probe_requested" in event_types
    assert "fetch_probe" in event_types

    forbidden = _request_via_asgi(
        "POST",
        f"/workbench/sessions/{session_id}/fetch-probe",
        headers={"x-workbench-owner": "bob"},
        json={"symbols": ["AAA"]},
    )
    assert forbidden.status_code == 403


def test_workbench_step_drafts_validation_and_apply_state_event(tmp_path: Path, monkeypatch) -> None:
    _setup_env(tmp_path, monkeypatch)
    session_id = _create_session(owner="alice")

    bad_step = _request_via_asgi(
        "POST",
        f"/workbench/sessions/{session_id}/steps/not_a_step/drafts",
        headers={"x-workbench-owner": "alice"},
        json={"content": {"note": "x"}},
    )
    assert bad_step.status_code == 422

    empty = _request_via_asgi(
        "POST",
        f"/workbench/sessions/{session_id}/steps/strategy_spec/drafts",
        headers={"x-workbench-owner": "alice"},
        json={"content": "   "},
    )
    assert empty.status_code == 422

    d1 = _request_via_asgi(
        "POST",
        f"/workbench/sessions/{session_id}/steps/strategy_spec/drafts",
        headers={"x-workbench-owner": "alice"},
        json={"content": {"note": "draft-v1"}},
    )
    assert d1.status_code == 200, d1.text
    d1_doc = d1.json()
    assert d1_doc["schema_version"] == "workbench_step_draft_create_response_v1"
    assert int(d1_doc["draft_version"]) == 1

    d2 = _request_via_asgi(
        "POST",
        f"/workbench/sessions/{session_id}/steps/strategy_spec/drafts",
        headers={"x-workbench-owner": "alice"},
        json={"content": {"note": "draft-v2"}},
    )
    assert d2.status_code == 200, d2.text
    assert int(d2.json()["draft_version"]) == 2

    apply = _request_via_asgi(
        "POST",
        f"/workbench/sessions/{session_id}/steps/strategy_spec/drafts/2/apply",
        headers={"x-workbench-owner": "alice"},
        json={},
    )
    assert apply.status_code == 200, apply.text
    apply_doc = apply.json()
    assert apply_doc["schema_version"] == "workbench_step_draft_apply_response_v1"
    assert apply_doc["selected_draft_version"] == 2
    assert str(apply_doc["state_event"]["event_type"]) == "draft_selection_changed"

    events_doc = _request_via_asgi(
        "GET",
        f"/workbench/sessions/{session_id}/events",
        headers={"x-workbench-owner": "alice"},
    ).json()
    event_types = [str(ev.get("event_type") or "") for ev in events_doc.get("events", []) if isinstance(ev, dict)]
    assert "draft_saved" in event_types
    assert "draft_applied" in event_types
    assert "draft_selection_changed" in event_types

    missing = _request_via_asgi(
        "POST",
        f"/workbench/sessions/{session_id}/steps/strategy_spec/drafts/99/apply",
        headers={"x-workbench-owner": "alice"},
        json={},
    )
    assert missing.status_code == 404

    forbidden = _request_via_asgi(
        "POST",
        f"/workbench/sessions/{session_id}/steps/strategy_spec/drafts/2/apply",
        headers={"x-workbench-owner": "bob"},
        json={},
    )
    assert forbidden.status_code == 403
