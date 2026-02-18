from __future__ import annotations

import asyncio
from pathlib import Path

import httpx

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
            "title": "G361 ownership test",
            "symbols": "AAA,BBB",
            "hypothesis_text": "session ownership should be enforced",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["schema_version"] == "workbench_session_create_response_v1"
    assert body["owner_id"] == owner
    return str(body["session_id"])


def test_workbench_get_session_ownership_404_403(tmp_path: Path, monkeypatch) -> None:
    _setup_env(tmp_path, monkeypatch)
    session_id = _create_session(owner="alice")

    ok = _request_via_asgi("GET", f"/workbench/sessions/{session_id}", headers={"x-workbench-owner": "alice"})
    assert ok.status_code == 200, ok.text
    doc = ok.json()
    assert doc["schema_version"] == "workbench_session_get_response_v1"
    assert doc["owner_id"] == "alice"

    forbidden = _request_via_asgi("GET", f"/workbench/sessions/{session_id}", headers={"x-workbench-owner": "bob"})
    assert forbidden.status_code == 403

    missing = _request_via_asgi("GET", "/workbench/sessions/ws_missing000", headers={"x-workbench-owner": "alice"})
    assert missing.status_code == 404


def test_workbench_message_appends_and_triggers_processing(tmp_path: Path, monkeypatch) -> None:
    _setup_env(tmp_path, monkeypatch)
    session_id = _create_session(owner="alice")

    msg = _request_via_asgi(
        "POST",
        f"/workbench/sessions/{session_id}/message",
        headers={"x-workbench-owner": "alice"},
        json={"message": "please continue to next review checkpoint"},
    )
    assert msg.status_code == 200, msg.text
    doc = msg.json()
    assert doc["schema_version"] == "workbench_session_message_response_v1"
    assert doc["owner_id"] == "alice"
    assert doc["processing_triggered"] is True
    assert doc["event"]["event_type"] == "message_appended"
    assert doc["trigger_event"]["event_type"] == "message_processing_triggered"

    forbidden = _request_via_asgi(
        "POST",
        f"/workbench/sessions/{session_id}/message",
        headers={"x-workbench-owner": "bob"},
        json={"message": "unauthorized writer"},
    )
    assert forbidden.status_code == 403


def test_workbench_continue_idempotency_key_replay(tmp_path: Path, monkeypatch) -> None:
    _setup_env(tmp_path, monkeypatch)
    session_id = _create_session(owner="alice")
    headers = {"x-workbench-owner": "alice", "Idempotency-Key": "continue-k1"}

    before_events = _request_via_asgi(
        "GET",
        f"/workbench/sessions/{session_id}/events",
        headers={"x-workbench-owner": "alice"},
    ).json()["event_count"]

    first = _request_via_asgi(
        "POST",
        f"/workbench/sessions/{session_id}/continue",
        headers=headers,
        json={"target_step": "strategy_spec"},
    )
    assert first.status_code == 200, first.text
    first_doc = first.json()
    assert first_doc["schema_version"] == "workbench_session_continue_response_v1"
    assert first_doc["current_step"] == "strategy_spec"
    assert first_doc["idempotency_replayed"] is False

    mid_events = _request_via_asgi(
        "GET",
        f"/workbench/sessions/{session_id}/events",
        headers={"x-workbench-owner": "alice"},
    ).json()["event_count"]
    assert mid_events > before_events

    second = _request_via_asgi(
        "POST",
        f"/workbench/sessions/{session_id}/continue",
        headers=headers,
        json={"target_step": "strategy_spec"},
    )
    assert second.status_code == 200, second.text
    second_doc = second.json()
    assert second_doc["idempotency_replayed"] is True
    assert second_doc["current_step"] == "strategy_spec"
    assert second_doc["previous_step"] == "idea"

    after_events = _request_via_asgi(
        "GET",
        f"/workbench/sessions/{session_id}/events",
        headers={"x-workbench-owner": "alice"},
    ).json()["event_count"]
    assert after_events == mid_events
