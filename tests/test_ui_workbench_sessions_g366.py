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
            "title": "G366 nfr regression",
            "symbols": "AAA,BBB",
            "hypothesis_text": "idempotency + append-only + refresh contract",
        },
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["session_id"])


def _events_doc(session_id: str, *, owner: str = "alice") -> dict:
    resp = _request_via_asgi(
        "GET",
        f"/workbench/sessions/{session_id}/events",
        headers={"x-workbench-owner": owner},
    )
    assert resp.status_code == 200, resp.text
    out = resp.json()
    assert isinstance(out, dict)
    return out


def test_workbench_fetch_probe_idempotency_key_preserves_append_only_events(tmp_path: Path, monkeypatch) -> None:
    _setup_env(tmp_path, monkeypatch)
    session_id = _create_session(owner="alice")

    before_doc = _events_doc(session_id, owner="alice")
    before_events = int(before_doc["event_count"])

    headers = {"x-workbench-owner": "alice", "Idempotency-Key": "fetch-probe-k1"}
    first = _request_via_asgi(
        "POST",
        f"/workbench/sessions/{session_id}/fetch-probe",
        headers=headers,
        json={"symbols": ["AAA", "BBB"]},
    )
    assert first.status_code == 200, first.text
    first_doc = first.json()
    assert first_doc["schema_version"] == "workbench_session_fetch_probe_response_v1"
    assert first_doc["status"] == "ok"

    mid_doc = _events_doc(session_id, owner="alice")
    mid_events = int(mid_doc["event_count"])
    assert mid_events > before_events

    second = _request_via_asgi(
        "POST",
        f"/workbench/sessions/{session_id}/fetch-probe",
        headers=headers,
        json={"symbols": ["AAA", "BBB"]},
    )
    assert second.status_code == 200, second.text
    second_doc = second.json()
    assert second_doc["event_id"] == first_doc["event_id"]
    assert second_doc["status"] == first_doc["status"]

    after_doc = _events_doc(session_id, owner="alice")
    after_events = int(after_doc["event_count"])
    assert after_events == mid_events

    event_types = [str(ev.get("event_type") or "") for ev in after_doc.get("events", []) if isinstance(ev, dict)]
    assert event_types.count("fetch_probe_requested") == 1
    assert event_types.count("fetch_probe") == 1


def test_workbench_draft_apply_and_rollback_idempotency_key_replay(tmp_path: Path, monkeypatch) -> None:
    _setup_env(tmp_path, monkeypatch)
    session_id = _create_session(owner="alice")

    for content in ("draft-v1", "draft-v2"):
        d = _request_via_asgi(
            "POST",
            f"/workbench/sessions/{session_id}/steps/strategy_spec/drafts",
            headers={"x-workbench-owner": "alice"},
            json={"content": {"note": content}},
        )
        assert d.status_code == 200, d.text

    apply_headers = {"x-workbench-owner": "alice", "Idempotency-Key": "draft-apply-k1"}
    first_apply = _request_via_asgi(
        "POST",
        f"/workbench/sessions/{session_id}/steps/strategy_spec/drafts/2/apply",
        headers=apply_headers,
        json={},
    )
    assert first_apply.status_code == 200, first_apply.text
    first_apply_doc = first_apply.json()
    assert first_apply_doc["selected_draft_version"] == 2

    apply_mid = int(_events_doc(session_id, owner="alice")["event_count"])
    second_apply = _request_via_asgi(
        "POST",
        f"/workbench/sessions/{session_id}/steps/strategy_spec/drafts/2/apply",
        headers=apply_headers,
        json={},
    )
    assert second_apply.status_code == 200, second_apply.text
    second_apply_doc = second_apply.json()
    assert second_apply_doc["event"]["event_id"] == first_apply_doc["event"]["event_id"]
    assert second_apply_doc["state_event"]["event_id"] == first_apply_doc["state_event"]["event_id"]
    apply_after = int(_events_doc(session_id, owner="alice")["event_count"])
    assert apply_after == apply_mid

    rollback_headers = {"x-workbench-owner": "alice", "Idempotency-Key": "draft-rollback-k1"}
    first_rollback = _request_via_asgi(
        "POST",
        f"/workbench/sessions/{session_id}/steps/strategy_spec/drafts/rollback",
        headers=rollback_headers,
        json={},
    )
    assert first_rollback.status_code == 200, first_rollback.text
    first_rollback_doc = first_rollback.json()
    assert first_rollback_doc["rollback_to_version"] == 1

    rollback_mid = int(_events_doc(session_id, owner="alice")["event_count"])
    second_rollback = _request_via_asgi(
        "POST",
        f"/workbench/sessions/{session_id}/steps/strategy_spec/drafts/rollback",
        headers=rollback_headers,
        json={},
    )
    assert second_rollback.status_code == 200, second_rollback.text
    second_rollback_doc = second_rollback.json()
    assert second_rollback_doc["event"]["event_id"] == first_rollback_doc["event"]["event_id"]
    assert second_rollback_doc["state_event"]["event_id"] == first_rollback_doc["state_event"]["event_id"]
    rollback_after = int(_events_doc(session_id, owner="alice")["event_count"])
    assert rollback_after == rollback_mid


def test_workbench_events_polling_response_shape_for_single_page_refresh(tmp_path: Path, monkeypatch) -> None:
    _setup_env(tmp_path, monkeypatch)
    session_id = _create_session(owner="alice")

    msg = _request_via_asgi(
        "POST",
        f"/workbench/sessions/{session_id}/message",
        headers={"x-workbench-owner": "alice"},
        json={"message": "refresh shape should stay stable"},
    )
    assert msg.status_code == 200, msg.text

    resp = _request_via_asgi(
        "GET",
        f"/workbench/sessions/{session_id}/events?after=0&limit=5",
        headers={"x-workbench-owner": "alice"},
    )
    assert resp.status_code == 200, resp.text
    doc = resp.json()

    required_fields = {
        "schema_version",
        "session_id",
        "owner_id",
        "mode",
        "after_event_index",
        "events",
        "event_count",
        "total_event_count",
    }
    assert required_fields.issubset(set(doc.keys()))
    assert doc["schema_version"] == "workbench_session_events_response_v1"
    assert doc["mode"] == "polling"
    assert doc["session_id"] == session_id
    assert isinstance(doc["events"], list)
