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


def _setup_env(tmp_path: Path, monkeypatch, *, real_jobs: bool = False) -> tuple[Path, Path]:
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
    monkeypatch.setenv("EAM_WORKBENCH_REAL_JOBS", "1" if real_jobs else "0")
    return art_root, job_root


def _create_session(*, owner: str = "alice") -> str:
    resp = _request_via_asgi(
        "POST",
        "/workbench/sessions",
        headers={"x-workbench-owner": owner},
        json={
            "title": "G365 recovery loop",
            "symbols": "AAA,BBB",
            "hypothesis_text": "rerun/apply-history/rollback controls",
        },
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["session_id"])


def test_workbench_recovery_apply_history_and_rollback_append_only_events(tmp_path: Path, monkeypatch) -> None:
    art_root, _job_root = _setup_env(tmp_path, monkeypatch, real_jobs=False)
    session_id = _create_session(owner="alice")
    session_doc = _request_via_asgi(
        "GET",
        f"/workbench/sessions/{session_id}",
        headers={"x-workbench-owner": "alice"},
    ).json()
    session_payload = session_doc["session"]
    assert isinstance(session_payload, dict)
    job_id = str(session_payload["job_id"])
    selected_path = art_root / "jobs" / job_id / "outputs" / "workbench" / "step_drafts" / "strategy_spec" / "selected.json"
    assert selected_path.as_posix().endswith(f"/jobs/{job_id}/outputs/workbench/step_drafts/strategy_spec/selected.json")
    assert ".." not in selected_path.as_posix()

    d1 = _request_via_asgi(
        "POST",
        f"/workbench/sessions/{session_id}/steps/strategy_spec/drafts",
        headers={"x-workbench-owner": "alice"},
        json={"content": {"note": "draft-v1"}},
    )
    assert d1.status_code == 200, d1.text
    d2 = _request_via_asgi(
        "POST",
        f"/workbench/sessions/{session_id}/steps/strategy_spec/drafts",
        headers={"x-workbench-owner": "alice"},
        json={"content": {"note": "draft-v2"}},
    )
    assert d2.status_code == 200, d2.text

    apply_v1 = _request_via_asgi(
        "POST",
        f"/workbench/sessions/{session_id}/steps/strategy_spec/drafts/1/apply",
        headers={"x-workbench-owner": "alice"},
        json={},
    )
    assert apply_v1.status_code == 200, apply_v1.text
    apply_v1_doc = apply_v1.json()
    assert apply_v1_doc["selected_index_path"] == selected_path.as_posix()
    assert selected_path.is_file()
    selected_v1 = json.loads(selected_path.read_text(encoding="utf-8"))
    assert selected_v1["schema_version"] == "workbench_step_selected_v1"
    assert selected_v1["session_id"] == session_id
    assert selected_v1["step"] == "strategy_spec"
    assert selected_v1["selected_version"] == 1
    assert selected_v1["selected_path"] == (selected_path.parent / "draft_v1.json").as_posix()
    assert selected_v1["selection_history"] == [1]
    assert str(selected_v1["selected_at"]).strip()

    apply_v2 = _request_via_asgi(
        "POST",
        f"/workbench/sessions/{session_id}/steps/strategy_spec/drafts/apply",
        headers={"x-workbench-owner": "alice"},
        json={"version": 2},
    )
    assert apply_v2.status_code == 200, apply_v2.text
    apply_v2_doc = apply_v2.json()
    assert apply_v2_doc["selected_index_path"] == selected_path.as_posix()
    selected_v2 = json.loads(selected_path.read_text(encoding="utf-8"))
    assert selected_v2["selected_version"] == 2
    assert selected_v2["selected_path"] == (selected_path.parent / "draft_v2.json").as_posix()
    assert selected_v2["selection_history"] == [1, 2]
    assert str(selected_v2["selected_at"]).strip()

    rollback = _request_via_asgi(
        "POST",
        f"/workbench/sessions/{session_id}/steps/strategy_spec/drafts/rollback",
        headers={"x-workbench-owner": "alice"},
        json={},
    )
    assert rollback.status_code == 200, rollback.text
    rollback_doc = rollback.json()
    assert rollback_doc["schema_version"] == "workbench_step_draft_rollback_response_v1"
    assert rollback_doc["rollback_from_version"] == 2
    assert rollback_doc["rollback_to_version"] == 1
    assert rollback_doc["selected_draft_version"] == 1
    assert rollback_doc["selected_index_path"] == selected_path.as_posix()
    selected_after_rollback = json.loads(selected_path.read_text(encoding="utf-8"))
    assert selected_after_rollback["selected_version"] == 1
    assert selected_after_rollback["selected_path"] == (selected_path.parent / "draft_v1.json").as_posix()
    assert selected_after_rollback["selection_history"] == [1, 2, 1]
    assert str(selected_after_rollback["selected_at"]).strip()

    events = _request_via_asgi(
        "GET",
        f"/workbench/sessions/{session_id}/events",
        headers={"x-workbench-owner": "alice"},
    ).json()
    event_types = [str(ev.get("event_type") or "") for ev in events.get("events", []) if isinstance(ev, dict)]
    assert "draft_applied" in event_types
    assert "draft_rolled_back" in event_types
    assert "draft_selection_rollback_applied" in event_types

    events_path = art_root / "workbench" / "sessions" / session_id / "events.jsonl"
    rows = [json.loads(ln) for ln in events_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert [int(ev["event_index"]) for ev in rows] == list(range(1, len(rows) + 1))


def test_workbench_recovery_ownership_invalid_step_and_version_guards(tmp_path: Path, monkeypatch) -> None:
    _setup_env(tmp_path, monkeypatch, real_jobs=False)
    session_id = _create_session(owner="alice")

    no_previous = _request_via_asgi(
        "POST",
        f"/workbench/sessions/{session_id}/steps/strategy_spec/drafts/rollback",
        headers={"x-workbench-owner": "alice"},
        json={},
    )
    assert no_previous.status_code == 409

    forbidden = _request_via_asgi(
        "POST",
        f"/workbench/sessions/{session_id}/steps/strategy_spec/drafts/rollback",
        headers={"x-workbench-owner": "bob"},
        json={},
    )
    assert forbidden.status_code == 403

    invalid_step = _request_via_asgi(
        "POST",
        f"/workbench/sessions/{session_id}/steps/not_a_step/drafts/rollback",
        headers={"x-workbench-owner": "alice"},
        json={},
    )
    assert invalid_step.status_code == 422

    invalid_version = _request_via_asgi(
        "POST",
        f"/workbench/sessions/{session_id}/steps/strategy_spec/drafts/apply",
        headers={"x-workbench-owner": "alice"},
        json={"version": "abc"},
    )
    assert invalid_version.status_code == 422


def test_workbench_rerun_step_mismatch_and_missing_input_409(tmp_path: Path, monkeypatch) -> None:
    art_root, job_root = _setup_env(tmp_path, monkeypatch, real_jobs=False)
    session_id = _create_session(owner="alice")

    mismatch = _request_via_asgi(
        "POST",
        f"/workbench/sessions/{session_id}/steps/strategy_spec/rerun",
        headers={"x-workbench-owner": "alice"},
        json={},
    )
    assert mismatch.status_code == 409

    session_path = art_root / "workbench" / "sessions" / session_id / "session.json"
    session_doc = json.loads(session_path.read_text(encoding="utf-8"))
    fake_job_id = "aaaaaaaaaaaa"
    session_doc["job_id"] = fake_job_id
    session_doc["current_step"] = "strategy_spec"
    session_doc["step_index"] = 1
    session_path.write_text(json.dumps(session_doc, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    (job_root / fake_job_id).mkdir(parents=True, exist_ok=True)
    (job_root / fake_job_id / "job_spec.json").write_text("{}\n", encoding="utf-8")
    monkeypatch.setenv("EAM_WORKBENCH_REAL_JOBS", "1")

    missing_input = _request_via_asgi(
        "POST",
        f"/workbench/sessions/{session_id}/steps/strategy_spec/rerun",
        headers={"x-workbench-owner": "alice"},
        json={},
    )
    assert missing_input.status_code == 409
    assert "missing rerun input" in str(missing_input.text)
    missing_doc = missing_input.json()
    detail = missing_doc.get("detail")
    assert isinstance(detail, dict)
    failure = detail.get("failure")
    assert isinstance(failure, dict)
    assert failure.get("schema_version") == "workbench_failure_context_v1"
    assert failure.get("failure_reason") == "step_rerun_failed"
    assert "missing rerun input" in str(failure.get("readable_message") or "")
    refs = failure.get("evidence_refs")
    assert isinstance(refs, list)
    assert any(str(ref).endswith("/events.jsonl") for ref in refs)

    events = _request_via_asgi(
        "GET",
        f"/workbench/sessions/{session_id}/events",
        headers={"x-workbench-owner": "alice"},
    ).json()
    event_types = [str(ev.get("event_type") or "") for ev in events.get("events", []) if isinstance(ev, dict)]
    assert "step_rerun_requested" in event_types
    assert "step_rerun_failed" in event_types

    saved_session = json.loads(session_path.read_text(encoding="utf-8"))
    saved_failure = saved_session.get("last_failure")
    assert isinstance(saved_failure, dict)
    assert saved_failure.get("failure_reason") == "step_rerun_failed"
    assert isinstance(saved_failure.get("evidence_refs"), list)

    ui = _request_via_asgi("GET", f"/ui/workbench/{session_id}")
    assert ui.status_code == 200, ui.text
    assert "Failure Explainability (WB-026)" in ui.text
    assert "step_rerun_failed" in ui.text
    assert "Evidence refs" in ui.text


def test_workbench_recovery_safe_pathing_blocks_tampered_job_id(tmp_path: Path, monkeypatch) -> None:
    art_root, _job_root = _setup_env(tmp_path, monkeypatch, real_jobs=False)
    session_id = _create_session(owner="alice")

    for note in ("draft-v1", "draft-v2"):
        resp = _request_via_asgi(
            "POST",
            f"/workbench/sessions/{session_id}/steps/strategy_spec/drafts",
            headers={"x-workbench-owner": "alice"},
            json={"content": {"note": note}},
        )
        assert resp.status_code == 200, resp.text

    apply_ok = _request_via_asgi(
        "POST",
        f"/workbench/sessions/{session_id}/steps/strategy_spec/drafts/2/apply",
        headers={"x-workbench-owner": "alice"},
        json={},
    )
    assert apply_ok.status_code == 200, apply_ok.text

    session_path = art_root / "workbench" / "sessions" / session_id / "session.json"
    session_doc = json.loads(session_path.read_text(encoding="utf-8"))
    session_doc["job_id"] = "../escape"
    session_path.write_text(json.dumps(session_doc, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    blocked_apply = _request_via_asgi(
        "POST",
        f"/workbench/sessions/{session_id}/steps/strategy_spec/drafts/apply",
        headers={"x-workbench-owner": "alice"},
        json={"version": 1},
    )
    assert blocked_apply.status_code == 400

    blocked_rollback = _request_via_asgi(
        "POST",
        f"/workbench/sessions/{session_id}/steps/strategy_spec/drafts/rollback",
        headers={"x-workbench-owner": "alice"},
        json={},
    )
    assert blocked_rollback.status_code == 400
