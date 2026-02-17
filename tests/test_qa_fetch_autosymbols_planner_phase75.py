from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from quant_eam.agents import backtest_agent, demo_agent
from quant_eam.qa_fetch.runtime import (
    FetchExecutionResult,
    STATUS_BLOCKED_SOURCE_MISSING,
    STATUS_ERROR_RUNTIME,
    STATUS_PASS_HAS_DATA,
)


def _write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _result(
    *,
    status: str,
    mode: str,
    resolved_function: str,
    preview: list[dict[str, Any]] | None = None,
    reason: str = "ok",
    source_internal: str = "mongo_fetch",
    engine: str | None = "mongo",
) -> FetchExecutionResult:
    rows = list(preview or [])
    cols = list(rows[0].keys()) if rows else []
    dtypes = {k: "object" for k in cols}
    return FetchExecutionResult(
        status=status,
        reason=reason,
        source="fetch",
        source_internal=source_internal,
        engine=engine,
        provider_id="fetch",
        provider_internal=source_internal,
        resolved_function=resolved_function,
        public_function=resolved_function,
        elapsed_sec=0.01,
        row_count=len(rows),
        columns=cols,
        dtypes=dtypes,
        preview=rows,
        final_kwargs={},
        mode=mode,
        data=rows if rows else None,
    )


def test_demo_agent_auto_symbols_planner_emits_list_sample_day_steps(tmp_path: Path, monkeypatch) -> None:
    job_id = "job_demo_auto_symbols_001"
    out_dir = tmp_path / "jobs" / job_id / "outputs" / "agents" / "demo"
    in_path = out_dir / "agent_input.json"
    _write_json(
        in_path,
        {
            "job_id": job_id,
            "snapshot_id": "snap_auto_symbols",
            "fetch_request": {
                "mode": "smoke",
                "intent": {
                    "asset": "stock",
                    "freq": "day",
                    "auto_symbols": True,
                    "start": "2024-01-01",
                    "end": "2024-01-31",
                    "sample": {"n": 2, "method": "stable_first_n"},
                },
            },
        },
    )

    captured_day: dict[str, Any] = {}

    def _fake_execute_fetch_by_name(**kwargs):
        assert kwargs["function"] == "fetch_stock_list"
        return _result(
            status=STATUS_PASS_HAS_DATA,
            mode="smoke",
            resolved_function="fetch_stock_list",
            preview=[
                {"code": "000003"},
                {"symbol": "000001"},
                {"ticker": "000002"},
            ],
        )

    def _fake_execute_fetch_by_intent(intent_payload, **kwargs):
        assert kwargs["policy"].mode == "smoke"
        assert isinstance(intent_payload, dict)
        captured_day.update(intent_payload)
        resolved_symbols = (intent_payload.get("intent") or {}).get("symbols")
        assert resolved_symbols == ["000003", "000001"]
        return _result(
            status=STATUS_PASS_HAS_DATA,
            mode="smoke",
            resolved_function="fetch_stock_day",
            preview=[{"code": "000003", "date": "2024-01-02", "close": 10.0}],
        )

    monkeypatch.setattr(demo_agent, "execute_fetch_by_name", _fake_execute_fetch_by_name)
    monkeypatch.setattr(demo_agent, "execute_fetch_by_intent", _fake_execute_fetch_by_intent)

    _ = demo_agent.run_demo_agent(input_path=in_path, out_dir=out_dir, provider="mock")

    fetch_dir = tmp_path / "jobs" / job_id / "outputs" / "fetch"
    assert (fetch_dir / "step_001_fetch_request.json").is_file()
    assert (fetch_dir / "step_002_fetch_request.json").is_file()
    assert (fetch_dir / "step_003_fetch_request.json").is_file()
    idx = json.loads((fetch_dir / "fetch_steps_index.json").read_text(encoding="utf-8"))
    assert [step["step_kind"] for step in idx["steps"]] == ["list", "sample", "day"]

    canonical_req = json.loads((fetch_dir / "fetch_request.json").read_text(encoding="utf-8"))
    assert canonical_req["symbols"] == ["000003", "000001"]
    assert (captured_day.get("intent") or {}).get("auto_symbols") is False

    plan = json.loads((out_dir / "demo_plan.json").read_text(encoding="utf-8"))
    fetch_meta = plan.get("fetch") or {}
    assert fetch_meta.get("planner_applied") is True
    assert fetch_meta.get("planner_step_count") == 3
    assert fetch_meta.get("planner_sampled_symbols") == ["000003", "000001"]


def test_backtest_agent_auto_symbols_list_failure_still_emits_three_steps(tmp_path: Path, monkeypatch) -> None:
    job_id = "job_backtest_auto_symbols_001"
    out_dir = tmp_path / "jobs" / job_id / "outputs" / "agents" / "backtest"
    in_path = out_dir / "agent_input.json"
    _write_json(
        in_path,
        {
            "job_id": job_id,
            "runspec_path": "runspec.json",
            "fetch_request": {
                "mode": "backtest",
                "intent": {
                    "asset": "stock",
                    "freq": "day",
                    "auto_symbols": True,
                    "start": "2024-01-01",
                    "end": "2024-01-31",
                },
            },
        },
    )

    def _fake_execute_fetch_by_name(**kwargs):
        assert kwargs["function"] == "fetch_stock_list"
        return _result(
            status=STATUS_BLOCKED_SOURCE_MISSING,
            mode="backtest",
            resolved_function="fetch_stock_list",
            preview=[],
            reason="not_in_baseline",
            source_internal="mysql_fetch",
            engine="mysql",
        )

    monkeypatch.setattr(backtest_agent, "execute_fetch_by_name", _fake_execute_fetch_by_name)
    monkeypatch.setattr(
        backtest_agent,
        "execute_fetch_by_intent",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("day step should not execute without sampled symbols")),
    )

    _ = backtest_agent.run_backtest_agent(input_path=in_path, out_dir=out_dir, provider="mock")

    fetch_dir = tmp_path / "jobs" / job_id / "outputs" / "fetch"
    idx = json.loads((fetch_dir / "fetch_steps_index.json").read_text(encoding="utf-8"))
    assert [step["step_kind"] for step in idx["steps"]] == ["list", "sample", "day"]
    assert [step["status"] for step in idx["steps"]] == [
        STATUS_BLOCKED_SOURCE_MISSING,
        STATUS_BLOCKED_SOURCE_MISSING,
        STATUS_ERROR_RUNTIME,
    ]
    assert (fetch_dir / "step_003_fetch_error.json").is_file()

    meta = json.loads((fetch_dir / "fetch_result_meta.json").read_text(encoding="utf-8"))
    assert meta["probe_status"] == STATUS_ERROR_RUNTIME
    assert "sample step produced no symbols" in (meta.get("warnings") or [""])[0]

    plan = json.loads((out_dir / "backtest_plan.json").read_text(encoding="utf-8"))
    fetch_meta = plan.get("fetch") or {}
    assert fetch_meta.get("planner_applied") is True
    assert fetch_meta.get("planner_sampled_symbols") == []
    assert fetch_meta.get("planner_step_count") == 3
