from __future__ import annotations

import asyncio
import json
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
    session_doc = _request_via_asgi(
        "GET",
        f"/workbench/sessions/{session_id}",
        headers={"x-workbench-owner": "alice"},
    ).json()
    session_payload = session_doc["session"]
    assert isinstance(session_payload, dict)
    job_id = str(session_payload["job_id"])
    selected_path = (
        tmp_path
        / "artifacts"
        / "jobs"
        / job_id
        / "outputs"
        / "workbench"
        / "step_drafts"
        / "strategy_spec"
        / "selected.json"
    )

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
    assert selected_path.is_file()
    selected_after_first_apply = json.loads(selected_path.read_text(encoding="utf-8"))

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
    selected_after_second_apply = json.loads(selected_path.read_text(encoding="utf-8"))
    assert selected_after_second_apply == selected_after_first_apply
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
    selected_after_first_rollback = json.loads(selected_path.read_text(encoding="utf-8"))

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
    selected_after_second_rollback = json.loads(selected_path.read_text(encoding="utf-8"))
    assert selected_after_second_rollback == selected_after_first_rollback
    rollback_after = int(_events_doc(session_id, owner="alice")["event_count"])
    assert rollback_after == rollback_mid


def test_workbench_draft_revision_conflict_returns_409(tmp_path: Path, monkeypatch) -> None:
    _setup_env(tmp_path, monkeypatch)
    session_id = _create_session(owner="alice")

    d1 = _request_via_asgi(
        "POST",
        f"/workbench/sessions/{session_id}/steps/strategy_spec/drafts",
        headers={"x-workbench-owner": "alice"},
        json={"content": {"note": "draft-v1"}},
    )
    assert d1.status_code == 200, d1.text

    session_doc = _request_via_asgi(
        "GET",
        f"/workbench/sessions/{session_id}",
        headers={"x-workbench-owner": "alice"},
    ).json()
    session_payload = session_doc.get("session")
    assert isinstance(session_payload, dict)
    current_revision = int(session_payload.get("revision") or 0)
    assert current_revision >= 2

    conflict = _request_via_asgi(
        "POST",
        f"/workbench/sessions/{session_id}/steps/strategy_spec/drafts/1/apply",
        headers={"x-workbench-owner": "alice"},
        json={"expected_revision": current_revision - 1},
    )
    assert conflict.status_code == 409, conflict.text
    detail = conflict.json().get("detail")
    assert isinstance(detail, dict)
    assert detail.get("error") == "revision_conflict"
    assert int(detail.get("expected_revision") or 0) == current_revision - 1
    assert int(detail.get("current_revision") or 0) == current_revision


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


def test_workbench_fetch_probe_failure_exposes_readable_reason_and_evidence_refs(tmp_path: Path, monkeypatch) -> None:
    _setup_env(tmp_path, monkeypatch)
    session_id = _create_session(owner="alice")
    art_root = tmp_path / "artifacts"
    session_path = art_root / "workbench" / "sessions" / session_id / "session.json"

    session_doc = json.loads(session_path.read_text(encoding="utf-8"))
    session_doc["job_id"] = "aaaaaaaaaaaa"
    session_doc["message"] = "force fetch probe failure"
    session_doc["fetch_request"] = {
        "schema_version": "fetch_request_v1",
        "mode": "backtest",
        "auto_symbols": False,
        "intent": {"symbols": ["AAA"], "auto_symbols": False},
    }
    session_path.write_text(json.dumps(session_doc, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    monkeypatch.setenv("EAM_WORKBENCH_REAL_JOBS", "1")

    from quant_eam.qa_fetch import runtime as qa_runtime

    def _boom(*_args, **_kwargs):
        raise RuntimeError("backend timeout from fetch runtime")

    monkeypatch.setattr(qa_runtime, "execute_ui_llm_query", _boom)

    resp = _request_via_asgi(
        "POST",
        f"/workbench/sessions/{session_id}/fetch-probe",
        headers={"x-workbench-owner": "alice"},
        json={},
    )
    assert resp.status_code == 200, resp.text
    doc = resp.json()
    assert doc["status"] == "error"
    failure = doc.get("failure")
    assert isinstance(failure, dict)
    assert failure.get("schema_version") == "workbench_failure_context_v1"
    assert failure.get("failure_reason") == "fetch_probe_execution_failed"
    assert "backend timeout from fetch runtime" in str(failure.get("readable_message") or "")
    evidence_refs = failure.get("evidence_refs")
    assert isinstance(evidence_refs, list)
    assert any(str(ref).endswith("/fetch_probe_error.json") for ref in evidence_refs)

    saved = json.loads(session_path.read_text(encoding="utf-8"))
    saved_failure = saved.get("last_failure")
    assert isinstance(saved_failure, dict)
    assert saved_failure.get("failure_reason") == "fetch_probe_execution_failed"
    assert str(saved.get("fetch_probe_error_ref") or "").endswith("/fetch_probe_error.json")

    ui = _request_via_asgi("GET", f"/ui/workbench/{session_id}")
    assert ui.status_code == 200, ui.text
    assert "Failure Explainability (WB-026)" in ui.text
    assert "fetch_probe_execution_failed" in ui.text
    assert "fetch_probe_error.json" in ui.text
