from __future__ import annotations

import json
from pathlib import Path

from quant_eam.agents import backtest_agent, demo_agent
from quant_eam.qa_fetch.runtime import (
    FetchExecutionResult,
    STATUS_ERROR_RUNTIME,
    STATUS_PASS_HAS_DATA,
)


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _result(*, status: str, mode: str, reason: str = "ok") -> FetchExecutionResult:
    return FetchExecutionResult(
        status=status,
        reason=reason,
        source="fetch",
        source_internal="mongo_fetch",
        engine="mongo",
        provider_id="fetch",
        provider_internal="mongo_fetch",
        resolved_function="fetch_stock_day",
        public_function="fetch_stock_day",
        elapsed_sec=0.01,
        row_count=1 if status == STATUS_PASS_HAS_DATA else 0,
        columns=["code", "date"] if status == STATUS_PASS_HAS_DATA else [],
        dtypes={"code": "object", "date": "object"} if status == STATUS_PASS_HAS_DATA else {},
        preview=[{"code": "000001", "date": "2024-01-02"}] if status == STATUS_PASS_HAS_DATA else [],
        final_kwargs={"symbol": "000001"},
        mode=mode,
        data=None,
    )


def test_demo_agent_writes_fetch_evidence_bundle(tmp_path: Path, monkeypatch) -> None:
    job_id = "job_demo_fetch_001"
    out_dir = tmp_path / "jobs" / job_id / "outputs" / "agents" / "demo"
    in_path = out_dir / "agent_input.json"
    _write_json(
        in_path,
        {
            "job_id": job_id,
            "snapshot_id": "snap_demo",
            "fetch_request": {
                "mode": "smoke",
                "function": "fetch_stock_day",
                "kwargs": {"symbol": "000001", "start": "2024-01-01", "end": "2024-01-02"},
            },
        },
    )

    monkeypatch.setattr(demo_agent, "execute_fetch_by_name", lambda **_kwargs: _result(status=STATUS_PASS_HAS_DATA, mode="smoke"))

    output_paths = demo_agent.run_demo_agent(input_path=in_path, out_dir=out_dir, provider="mock")
    assert (out_dir / "demo_plan.json").is_file()

    fetch_dir = tmp_path / "jobs" / job_id / "outputs" / "fetch"
    assert (fetch_dir / "fetch_request.json").is_file()
    assert (fetch_dir / "fetch_result_meta.json").is_file()
    assert (fetch_dir / "fetch_preview.csv").is_file()
    assert not (fetch_dir / "fetch_error.json").exists()

    plan = json.loads((out_dir / "demo_plan.json").read_text(encoding="utf-8"))
    fetch_meta = plan.get("fetch") or {}
    assert fetch_meta.get("enabled") is True
    assert fetch_meta.get("status") == STATUS_PASS_HAS_DATA
    assert fetch_meta.get("source") == "fetch"
    assert fetch_meta.get("engine") == "mongo"
    assert len(output_paths) >= 4


def test_backtest_agent_writes_fetch_error_when_runtime_fails(tmp_path: Path, monkeypatch) -> None:
    job_id = "job_backtest_fetch_001"
    out_dir = tmp_path / "jobs" / job_id / "outputs" / "agents" / "backtest"
    in_path = out_dir / "agent_input.json"
    _write_json(
        in_path,
        {
            "job_id": job_id,
            "runspec_path": "runspec.json",
            "fetch_request": {
                "mode": "backtest",
                "intent": {"asset": "bond", "freq": "day", "symbols": "240011.IB", "start": "2026-01-01", "end": "2026-01-31"},
            },
        },
    )

    monkeypatch.setattr(
        backtest_agent,
        "execute_fetch_by_intent",
        lambda *_args, **_kwargs: _result(status=STATUS_ERROR_RUNTIME, mode="backtest", reason="timeout_skip_30s"),
    )

    _ = backtest_agent.run_backtest_agent(input_path=in_path, out_dir=out_dir, provider="mock")

    fetch_dir = tmp_path / "jobs" / job_id / "outputs" / "fetch"
    assert (fetch_dir / "fetch_request.json").is_file()
    assert (fetch_dir / "fetch_result_meta.json").is_file()
    assert (fetch_dir / "fetch_preview.csv").is_file()
    assert (fetch_dir / "fetch_error.json").is_file()

    plan = json.loads((out_dir / "backtest_plan.json").read_text(encoding="utf-8"))
    fetch_meta = plan.get("fetch") or {}
    assert fetch_meta.get("enabled") is True
    assert fetch_meta.get("status") == STATUS_ERROR_RUNTIME
    assert fetch_meta.get("source") == "fetch"
    assert fetch_meta.get("engine") == "mongo"
