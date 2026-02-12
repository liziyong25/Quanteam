from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

pytest.importorskip("jsonschema")
pytest.importorskip("referencing")

from quant_eam.jobstore.store import load_job_events
from quant_eam.orchestrator.workflow import advance_job_once


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")


def test_orchestrator_failfast_invalid_fetch_request_before_agent_dispatch(tmp_path: Path, monkeypatch) -> None:
    job_root = tmp_path / "jobs"
    monkeypatch.setenv("EAM_JOB_ROOT", str(job_root))
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    job_id = "a1b2c3d4e5f6"
    job_dir = job_root / job_id
    outputs_dir = job_dir / "outputs"

    _write_json(
        job_dir / "job_spec.json",
        {
            "schema_version": "idea_spec_v1",
            "title": "fetch failfast",
            "hypothesis_text": "invalid fetch request must fail before agent dispatch",
            "symbols": ["000001"],
            "frequency": "1d",
            "start": "2024-01-01",
            "end": "2024-01-31",
            "evaluation_intent": "phase77_failfast",
            "snapshot_id": "snap_phase77",
            "policy_bundle_path": "policies/policy_bundle_v1.yaml",
            "policy_bundle_id": "policy_bundle_v1",
            "fetch_request": {
                "mode": "backtest",
                "function": "fetch_stock_day",
                "kwargs": {
                    "symbol": "000001",
                    "start": "2024-02-10",
                    "end": "2024-01-01"
                }
            },
        },
    )

    spec_qa_report = outputs_dir / "agents" / "spec_qa" / "spec_qa_report.json"
    _write_json(spec_qa_report, {"schema_version": "spec_qa_report_v1", "summary": {"finding_count": 0}})
    _write_json(
        outputs_dir / "outputs.json",
        {
            "spec_qa_report_path": spec_qa_report.as_posix(),
        },
    )
    _write_json(
        outputs_dir / "runspec.json",
        {
            "schema_version": "run_spec_v1",
            "data_snapshot_id": "snap_phase77",
            "segments": {"test": {"start": "2024-01-01", "end": "2024-01-31", "as_of": "2024-01-31"}},
            "extensions": {"symbols": ["000001"]},
        },
    )
    _write_jsonl(
        job_dir / "events.jsonl",
        [
            {"event_type": "IDEA_SUBMITTED"},
            {"event_type": "BLUEPRINT_PROPOSED"},
            {"event_type": "APPROVED", "outputs": {"step": "blueprint"}},
            {"event_type": "STRATEGY_SPEC_PROPOSED"},
            {"event_type": "APPROVED", "outputs": {"step": "strategy_spec"}},
            {"event_type": "APPROVED", "outputs": {"step": "spec_qa"}},
            {"event_type": "RUNSPEC_COMPILED", "outputs": {"runspec_path": (outputs_dir / "runspec.json").as_posix()}},
            {"event_type": "APPROVED", "outputs": {"step": "runspec"}},
        ],
    )

    import quant_eam.agents.harness as harness

    agent_calls = {"count": 0}

    def _should_not_run_agent(*_args, **_kwargs):
        agent_calls["count"] += 1
        raise AssertionError("run_agent must not be called when fetch_request validation fails")

    monkeypatch.setattr(harness, "run_agent", _should_not_run_agent)

    out = advance_job_once(job_id=job_id)
    assert out["status"] == "stopped"
    assert out["state"] == "ERROR"
    assert out["reason"] == "FETCH_REQUEST_INVALID"
    assert agent_calls["count"] == 0

    err_path = outputs_dir / "fetch" / "fetch_request_validation_error.json"
    assert err_path.is_file()
    err_doc = json.loads(err_path.read_text(encoding="utf-8"))
    assert err_doc["reason"] == "FETCH_REQUEST_INVALID"
    assert err_doc["fetch_request_source"] == "job_spec.fetch_request"

    outputs_doc = json.loads((outputs_dir / "outputs.json").read_text(encoding="utf-8"))
    assert outputs_doc.get("fetch_request_validation_error_path") == err_path.as_posix()

    events = load_job_events(job_id)
    assert any(ev.get("event_type") == "ERROR" and ev.get("message") == "FETCH_REQUEST_INVALID" for ev in events)
    assert any(ev.get("event_type") == "DONE" and (ev.get("outputs") or {}).get("status") == "stopped_invalid_fetch_request" for ev in events)
