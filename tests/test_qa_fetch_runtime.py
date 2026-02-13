from __future__ import annotations

import json
from typing import Any

import pytest

from quant_eam.qa_fetch import runtime


def _registry_row(
    function: str,
    *,
    source: str = "mysql_fetch",
    target_name: str | None = None,
) -> dict[str, dict[str, str]]:
    return {
        function: {
            "function": function,
            "source": source,
            "target_name": target_name or function,
            "status": "active",
        }
    }


def test_runtime_param_priority_notebook_over_profile(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def _fn(symbol: str, start: str, end: str, format: str = "pd") -> list[dict[str, int]]:
        captured["symbol"] = symbol
        captured["start"] = start
        captured["end"] = end
        captured["format"] = format
        return [{"ok": 1}]

    monkeypatch.setattr(
        runtime,
        "load_smoke_window_profile",
        lambda _path: {
            "fetch_demo": {
                "smoke_kwargs": {"symbol": "from_profile", "start": "2026-01-01", "end": "2026-01-31"},
                "smoke_timeout_sec": 30,
            }
        },
    )
    monkeypatch.setattr(runtime, "load_exception_decisions", lambda _path: {})
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: _registry_row("fetch_demo"))
    monkeypatch.setattr(runtime, "_resolve_callable", lambda _fn_name, source_hint=None: (_fn, "mysql_fetch"))

    res = runtime.execute_fetch_by_name(
        function="fetch_demo",
        kwargs={"symbol": "from_llm"},
        policy={"mode": "smoke"},
    )

    assert res.status == runtime.STATUS_PASS_HAS_DATA
    assert res.source == "fetch"
    assert res.engine == "mysql"
    assert res.source_internal == "mysql_fetch"
    assert captured["symbol"] == "from_llm"
    assert captured["start"] == "2026-01-01"
    assert captured["end"] == "2026-01-31"
    assert captured["format"] == "pd"


def test_runtime_timeout_rule_by_mode(monkeypatch) -> None:
    called: list[int | None] = []

    def _fn() -> list[int]:
        return []

    def _fake_call_with_timeout(fn, *, timeout_sec):
        called.append(timeout_sec)
        return fn()

    monkeypatch.setattr(runtime, "load_smoke_window_profile", lambda _path: {})
    monkeypatch.setattr(runtime, "load_exception_decisions", lambda _path: {})
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: _registry_row("fetch_demo"))
    monkeypatch.setattr(runtime, "_resolve_callable", lambda _fn_name, source_hint=None: (_fn, "mysql_fetch"))
    monkeypatch.setattr(runtime, "_call_with_timeout", _fake_call_with_timeout)

    _ = runtime.execute_fetch_by_name(function="fetch_demo", kwargs={}, policy={"mode": "smoke"})
    _ = runtime.execute_fetch_by_name(function="fetch_demo", kwargs={}, policy={"mode": "research"})

    assert called[0] == 30
    assert called[1] is None


def test_runtime_status_on_empty_data(monkeypatch) -> None:
    def _fn() -> list[int]:
        return []

    monkeypatch.setattr(runtime, "load_smoke_window_profile", lambda _path: {})
    monkeypatch.setattr(runtime, "load_exception_decisions", lambda _path: {})
    monkeypatch.setattr(
        runtime,
        "load_function_registry",
        lambda _path: _registry_row("fetch_demo", source="mongo_fetch"),
    )
    monkeypatch.setattr(runtime, "_resolve_callable", lambda _fn_name, source_hint=None: (_fn, "mongo_fetch"))

    pass_empty = runtime.execute_fetch_by_name(function="fetch_demo", kwargs={}, policy={"mode": "smoke"})
    as_error = runtime.execute_fetch_by_name(
        function="fetch_demo",
        kwargs={},
        policy={"mode": "smoke", "on_no_data": "error"},
    )

    assert pass_empty.status == runtime.STATUS_PASS_EMPTY
    assert pass_empty.source == "fetch"
    assert pass_empty.engine == "mongo"
    assert as_error.status == runtime.STATUS_ERROR_RUNTIME
    assert as_error.reason == "no_data"


def test_runtime_exception_mapping_and_decision_gate(monkeypatch) -> None:
    def _missing_table_fn() -> None:
        raise RuntimeError("ProgrammingError: table test2.clean_bond_quote doesn't exist")

    monkeypatch.setattr(runtime, "load_smoke_window_profile", lambda _path: {})
    monkeypatch.setattr(runtime, "load_exception_decisions", lambda _path: {})
    monkeypatch.setattr(
        runtime,
        "load_function_registry",
        lambda _path: _registry_row("fetch_bond_quote", target_name="fetch_clean_quote"),
    )
    monkeypatch.setattr(
        runtime,
        "_resolve_callable",
        lambda _fn_name, source_hint=None: (_missing_table_fn, "mysql_fetch"),
    )

    blocked = runtime.execute_fetch_by_name(function="fetch_bond_quote", kwargs={}, policy={"mode": "smoke"})
    assert blocked.status == runtime.STATUS_BLOCKED_SOURCE_MISSING
    assert blocked.source == "fetch"
    assert blocked.engine == "mysql"

    monkeypatch.setattr(
        runtime,
        "load_exception_decisions",
        lambda _path: {
            "fetch_bond_quote": {
                "issue_type": "source_table_missing",
                "smoke_policy": "blocked",
                "research_policy": "blocked",
                "decision": "pending",
                "notes": "manual",
            }
        },
    )
    pending = runtime.execute_fetch_by_name(function="fetch_bond_quote", kwargs={}, policy={"mode": "smoke"})
    assert pending.status == runtime.STATUS_BLOCKED_SOURCE_MISSING
    assert "disabled_by_exception_policy" in pending.reason


def test_runtime_blocks_function_outside_frozen_baseline(monkeypatch) -> None:
    monkeypatch.setattr(runtime, "load_smoke_window_profile", lambda _path: {})
    monkeypatch.setattr(runtime, "load_exception_decisions", lambda _path: {})
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: {})

    out = runtime.execute_fetch_by_name(function="fetch_not_in_baseline", kwargs={}, policy={"mode": "smoke"})
    assert out.status == runtime.STATUS_BLOCKED_SOURCE_MISSING
    assert out.reason == "not_in_baseline"
    assert out.source == "fetch"


def _dummy_result() -> runtime.FetchExecutionResult:
    return runtime.FetchExecutionResult(
        status=runtime.STATUS_PASS_HAS_DATA,
        reason="ok",
        source="fetch",
        source_internal="mysql_fetch",
        engine="mysql",
        provider_id="fetch",
        provider_internal="mysql_fetch",
        resolved_function="fetch_demo",
        public_function="fetch_demo",
        elapsed_sec=0.0,
        row_count=1,
        columns=["x"],
        dtypes={"x": "int64"},
        preview=[{"x": 1}],
        final_kwargs={"x": 1},
        mode="backtest",
        data=[{"x": 1}],
    )


def test_execute_fetch_by_intent_accepts_fetch_request_wrapper(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class _Resolution:
        source = "mysql_fetch"
        public_name = "fetch_stock_day"

    def _fake_execute_fetch_by_name(**kwargs):
        captured.update(kwargs)
        return _dummy_result()

    monkeypatch.setattr(runtime, "resolve_fetch", lambda **_: _Resolution())
    monkeypatch.setattr(runtime, "execute_fetch_by_name", _fake_execute_fetch_by_name)

    payload = {
        "intent": {
            "asset": "stock",
            "freq": "day",
            "extra_kwargs": {"bar": 2},
        },
        "symbols": ["000001"],
        "start": "2024-01-01",
        "end": "2024-01-31",
        "kwargs": {"foo": 1, "bar": 9},
        "policy": {"mode": "backtest", "on_no_data": "error"},
    }
    _ = runtime.execute_fetch_by_intent(payload)

    assert captured["function"] == "fetch_stock_day"
    assert captured["source_hint"] == "mysql_fetch"
    assert isinstance(captured["policy"], runtime.FetchExecutionPolicy)
    assert captured["policy"].mode == "backtest"
    assert captured["policy"].on_no_data == "error"
    assert captured["kwargs"]["symbols"] == ["000001"]
    assert captured["kwargs"]["start"] == "2024-01-01"
    assert captured["kwargs"]["end"] == "2024-01-31"
    assert captured["kwargs"]["foo"] == 1
    # intent.extra_kwargs should have higher priority than top-level kwargs on collisions.
    assert captured["kwargs"]["bar"] == 2


def test_execute_fetch_by_intent_accepts_function_wrapper(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def _fake_execute_fetch_by_name(**kwargs):
        captured.update(kwargs)
        return _dummy_result()

    monkeypatch.setattr(runtime, "execute_fetch_by_name", _fake_execute_fetch_by_name)
    monkeypatch.setattr(
        runtime,
        "resolve_fetch",
        lambda **_: (_ for _ in ()).throw(AssertionError("resolve_fetch should not be called")),
    )

    payload = {
        "function": "fetch_stock_day",
        "kwargs": {"code": "000001", "start": "2024-01-01", "end": "2024-01-31"},
        "policy": {"mode": "research"},
    }
    _ = runtime.execute_fetch_by_intent(payload)

    assert captured["function"] == "fetch_stock_day"
    assert captured["kwargs"] == {"code": "000001", "start": "2024-01-01", "end": "2024-01-31"}
    assert isinstance(captured["policy"], runtime.FetchExecutionPolicy)
    assert captured["policy"].mode == "research"


def test_execute_fetch_by_intent_rejects_invalid_fetch_request_kwargs() -> None:
    with pytest.raises(ValueError, match=r"fetch_request.kwargs must be an object when provided"):
        runtime.execute_fetch_by_intent(
            {
                "intent": {"asset": "stock", "freq": "day"},
                "kwargs": "bad",
            }
        )


def test_write_fetch_evidence_emits_steps_index(tmp_path) -> None:
    result = runtime.FetchExecutionResult(
        status=runtime.STATUS_PASS_HAS_DATA,
        reason="ok",
        source="fetch",
        source_internal="mysql_fetch",
        engine="mysql",
        provider_id="fetch",
        provider_internal="mysql_fetch",
        resolved_function="fetch_stock_day",
        public_function="fetch_stock_day",
        elapsed_sec=0.01,
        row_count=2,
        columns=["code", "close"],
        dtypes={"code": "object", "close": "float64"},
        preview=[{"code": "000001", "date": "2024-01-02", "close": 10.0}],
        final_kwargs={"code": "000001"},
        mode="smoke",
        data=[{"code": "000001", "date": "2024-01-02", "close": 10.0}],
    )

    paths = runtime.write_fetch_evidence(
        request_payload={"intent": {"asset": "stock", "freq": "day"}},
        result=result,
        out_dir=tmp_path,
    )
    assert "fetch_steps_index_path" in paths
    idx = json.loads((tmp_path / "fetch_steps_index.json").read_text(encoding="utf-8"))
    assert idx["schema_version"] == "qa_fetch_steps_index_v1"
    assert isinstance(idx.get("steps"), list) and len(idx["steps"]) == 1
    step = idx["steps"][0]
    assert step["step_index"] == 1
    assert step["step_kind"] == "single_fetch"
    assert step["status"] == runtime.STATUS_PASS_HAS_DATA
    assert step["request_path"] == paths["fetch_request_path"]
    assert step["result_meta_path"] == paths["fetch_result_meta_path"]
    assert step["preview_path"] == paths["fetch_preview_path"]
    assert "error_path" not in step
    meta = json.loads((tmp_path / "fetch_result_meta.json").read_text(encoding="utf-8"))
    assert meta["selected_function"] == "fetch_stock_day"
    assert meta["col_count"] == 2
    assert meta["probe_status"] == runtime.STATUS_PASS_HAS_DATA
    assert isinstance(meta["request_hash"], str) and len(meta["request_hash"]) == 64
    assert meta["warnings"] == []
    assert meta["min_ts"] == "2024-01-02"
    assert meta["max_ts"] == "2024-01-02"
    assert meta["coverage"]["requested_symbol_count"] == 0
    assert meta["coverage"]["observed_symbol_count"] == 1
    assert meta["coverage"]["observed_symbols"] == ["000001"]
    sanity = meta["sanity_checks"]
    assert sanity["timestamp_field"] == "date"
    assert sanity["timestamp_monotonic_non_decreasing"] is True
    assert sanity["timestamp_duplicate_count"] == 0
    assert sanity["missing_ratio_by_column"]["code"] == 0.0
    assert sanity["missing_ratio_by_column"]["close"] == 0.0
    assert sanity["preview_row_count"] == 1


def test_write_fetch_evidence_failure_includes_error_path_in_steps_index(tmp_path) -> None:
    result = runtime.FetchExecutionResult(
        status=runtime.STATUS_ERROR_RUNTIME,
        reason="RuntimeError: boom",
        source="fetch",
        source_internal="mongo_fetch",
        engine="mongo",
        provider_id="fetch",
        provider_internal="mongo_fetch",
        resolved_function="fetch_stock_day",
        public_function="fetch_stock_day",
        elapsed_sec=0.02,
        row_count=0,
        columns=[],
        dtypes={},
        preview=[],
        final_kwargs={"code": "000001"},
        mode="smoke",
        data=None,
    )

    paths = runtime.write_fetch_evidence(
        request_payload={"intent": {"asset": "stock", "freq": "day"}},
        result=result,
        out_dir=tmp_path,
    )
    idx = json.loads((tmp_path / "fetch_steps_index.json").read_text(encoding="utf-8"))
    step = idx["steps"][0]
    assert "fetch_error_path" in paths
    assert step["error_path"] == paths["fetch_error_path"]
    meta = json.loads((tmp_path / "fetch_result_meta.json").read_text(encoding="utf-8"))
    assert meta["probe_status"] == runtime.STATUS_ERROR_RUNTIME
    assert meta["warnings"] == ["RuntimeError: boom"]
    assert isinstance(meta["request_hash"], str) and len(meta["request_hash"]) == 64
    sanity = meta["sanity_checks"]
    assert sanity["timestamp_field"] == ""
    assert sanity["timestamp_monotonic_non_decreasing"] is True
    assert sanity["timestamp_duplicate_count"] == 0
    assert sanity["missing_ratio_by_column"] == {}
    assert sanity["preview_row_count"] == 0


def test_write_fetch_evidence_multistep_canonical_maps_to_final_step(tmp_path) -> None:
    list_result = runtime.FetchExecutionResult(
        status=runtime.STATUS_PASS_HAS_DATA,
        reason="ok",
        source="fetch",
        source_internal="mysql_fetch",
        engine="mysql",
        provider_id="fetch",
        provider_internal="mysql_fetch",
        resolved_function="fetch_stock_list",
        public_function="fetch_stock_list",
        elapsed_sec=0.01,
        row_count=3,
        columns=["symbol"],
        dtypes={"symbol": "object"},
        preview=[{"symbol": "000001"}, {"symbol": "000002"}, {"symbol": "000003"}],
        final_kwargs={},
        mode="smoke",
        data=[{"symbol": "000001"}, {"symbol": "000002"}, {"symbol": "000003"}],
    )
    sample_result = runtime.FetchExecutionResult(
        status=runtime.STATUS_PASS_HAS_DATA,
        reason="ok",
        source="fetch",
        source_internal="planner",
        engine=None,
        provider_id="fetch",
        provider_internal="planner",
        resolved_function="planner_sample_symbols",
        public_function="planner_sample_symbols",
        elapsed_sec=0.0,
        row_count=2,
        columns=["symbol", "rank"],
        dtypes={"symbol": "object", "rank": "int64"},
        preview=[{"symbol": "000001", "rank": 1}, {"symbol": "000002", "rank": 2}],
        final_kwargs={"sample_n": 2, "sample_method": "stable_first_n"},
        mode="smoke",
        data=[{"symbol": "000001", "rank": 1}, {"symbol": "000002", "rank": 2}],
    )
    day_result = runtime.FetchExecutionResult(
        status=runtime.STATUS_ERROR_RUNTIME,
        reason="RuntimeError: downstream failure",
        source="fetch",
        source_internal="mongo_fetch",
        engine="mongo",
        provider_id="fetch",
        provider_internal="mongo_fetch",
        resolved_function="fetch_stock_day",
        public_function="fetch_stock_day",
        elapsed_sec=0.02,
        row_count=0,
        columns=[],
        dtypes={},
        preview=[],
        final_kwargs={"symbols": ["000001", "000002"]},
        mode="smoke",
        data=None,
    )

    paths = runtime.write_fetch_evidence(
        request_payload={"intent": {"asset": "stock", "freq": "day", "auto_symbols": True}},
        result=day_result,
        out_dir=tmp_path,
        step_records=[
            {
                "step_kind": "list",
                "request_payload": {"function": "fetch_stock_list", "kwargs": {}},
                "result": list_result,
            },
            {
                "step_kind": "sample",
                "request_payload": {"planner_step": "sample", "sample": {"n": 2, "method": "stable_first_n"}},
                "result": sample_result,
            },
            {
                "step_kind": "day",
                "request_payload": {"intent": {"asset": "stock", "freq": "day", "symbols": ["000001", "000002"]}},
                "result": day_result,
            },
        ],
    )

    idx = json.loads((tmp_path / "fetch_steps_index.json").read_text(encoding="utf-8"))
    assert [step["step_kind"] for step in idx["steps"]] == ["list", "sample", "day"]
    assert (tmp_path / "step_001_fetch_request.json").is_file()
    assert (tmp_path / "step_002_fetch_request.json").is_file()
    assert (tmp_path / "step_003_fetch_request.json").is_file()
    assert (tmp_path / "step_003_fetch_error.json").is_file()

    canonical_req = json.loads((tmp_path / "fetch_request.json").read_text(encoding="utf-8"))
    step3_req = json.loads((tmp_path / "step_003_fetch_request.json").read_text(encoding="utf-8"))
    assert canonical_req == step3_req
    assert "fetch_error_path" in paths
    assert paths["fetch_result_meta_path"] == (tmp_path / "fetch_result_meta.json").as_posix()
    meta = json.loads((tmp_path / "fetch_result_meta.json").read_text(encoding="utf-8"))
    assert meta["selected_function"] == "fetch_stock_day"
    assert meta["probe_status"] == runtime.STATUS_ERROR_RUNTIME
    sanity = meta["sanity_checks"]
    assert sanity["preview_row_count"] == 0
    assert sanity["missing_ratio_by_column"] == {}


def test_write_fetch_evidence_sanity_checks_detect_non_monotonic_duplicates_and_missing(tmp_path) -> None:
    result = runtime.FetchExecutionResult(
        status=runtime.STATUS_PASS_HAS_DATA,
        reason="ok",
        source="fetch",
        source_internal="mysql_fetch",
        engine="mysql",
        provider_id="fetch",
        provider_internal="mysql_fetch",
        resolved_function="fetch_stock_day",
        public_function="fetch_stock_day",
        elapsed_sec=0.01,
        row_count=3,
        columns=["code", "date", "close", "volume"],
        dtypes={"code": "object", "date": "object", "close": "float64", "volume": "float64"},
        preview=[
            {"code": "000001", "date": "2024-01-03", "close": 10.0, "volume": None},
            {"code": "000001", "date": "2024-01-02", "close": 11.0},
            {"code": "", "date": "2024-01-02", "close": None, "volume": 200.0},
        ],
        final_kwargs={"code": "000001"},
        mode="smoke",
        data=None,
    )

    _ = runtime.write_fetch_evidence(
        request_payload={"intent": {"asset": "stock", "freq": "day"}},
        result=result,
        out_dir=tmp_path,
    )
    meta = json.loads((tmp_path / "fetch_result_meta.json").read_text(encoding="utf-8"))
    sanity = meta["sanity_checks"]
    assert sanity["timestamp_field"] == "date"
    assert sanity["timestamp_monotonic_non_decreasing"] is False
    assert sanity["timestamp_duplicate_count"] == 1
    assert sanity["preview_row_count"] == 3
    assert sanity["missing_ratio_by_column"]["volume"] == pytest.approx(2 / 3, rel=0, abs=1e-6)
    assert sanity["missing_ratio_by_column"]["code"] == pytest.approx(1 / 3, rel=0, abs=1e-6)
    assert sanity["missing_ratio_by_column"]["close"] == pytest.approx(1 / 3, rel=0, abs=1e-6)


def test_write_fetch_evidence_emits_asof_availability_summary(tmp_path) -> None:
    result = runtime.FetchExecutionResult(
        status=runtime.STATUS_PASS_HAS_DATA,
        reason="ok",
        source="fetch",
        source_internal="mysql_fetch",
        engine="mysql",
        provider_id="fetch",
        provider_internal="mysql_fetch",
        resolved_function="fetch_stock_day",
        public_function="fetch_stock_day",
        elapsed_sec=0.01,
        row_count=3,
        columns=["code", "date", "available_at", "close"],
        dtypes={"code": "object", "date": "object", "available_at": "object", "close": "float64"},
        preview=[
            {"code": "000001", "date": "2024-01-01", "available_at": "2024-01-01T16:00:00+08:00", "close": 10.0},
            {"code": "000001", "date": "2024-01-02", "available_at": "2024-01-02T16:00:00+08:00", "close": 11.0},
            {"code": "000001", "date": "2024-01-03", "available_at": "2024-01-03T16:00:00+08:00", "close": 12.0},
        ],
        final_kwargs={"code": "000001"},
        mode="smoke",
        data=None,
    )

    _ = runtime.write_fetch_evidence(
        request_payload={
            "intent": {"asset": "stock", "freq": "day"},
            "as_of": "2024-01-02T23:59:59+08:00",
        },
        result=result,
        out_dir=tmp_path,
    )
    meta = json.loads((tmp_path / "fetch_result_meta.json").read_text(encoding="utf-8"))
    assert meta["as_of"] == "2024-01-02T23:59:59+08:00"
    av = meta["availability_summary"]
    assert av["rule"] == "available_at<=as_of"
    assert av["has_as_of"] is True
    assert av["as_of"] == "2024-01-02T23:59:59+08:00"
    assert av["available_at_field_present"] is True
    assert av["available_at_min"] == "2024-01-01T16:00:00+08:00"
    assert av["available_at_max"] == "2024-01-03T16:00:00+08:00"
    assert av["available_at_violation_count"] == 1


def test_write_fetch_evidence_availability_summary_defaults_without_asof_or_available_at(tmp_path) -> None:
    result = runtime.FetchExecutionResult(
        status=runtime.STATUS_PASS_HAS_DATA,
        reason="ok",
        source="fetch",
        source_internal="mysql_fetch",
        engine="mysql",
        provider_id="fetch",
        provider_internal="mysql_fetch",
        resolved_function="fetch_stock_day",
        public_function="fetch_stock_day",
        elapsed_sec=0.01,
        row_count=1,
        columns=["code", "date", "close"],
        dtypes={"code": "object", "date": "object", "close": "float64"},
        preview=[{"code": "000001", "date": "2024-01-01", "close": 10.0}],
        final_kwargs={"code": "000001"},
        mode="smoke",
        data=None,
    )

    _ = runtime.write_fetch_evidence(
        request_payload={"intent": {"asset": "stock", "freq": "day"}},
        result=result,
        out_dir=tmp_path,
    )
    meta = json.loads((tmp_path / "fetch_result_meta.json").read_text(encoding="utf-8"))
    assert meta["as_of"] is None
    av = meta["availability_summary"]
    assert av["has_as_of"] is False
    assert av["as_of"] is None
    assert av["available_at_field_present"] is False
    assert av["available_at_min"] is None
    assert av["available_at_max"] is None
    assert av["available_at_violation_count"] == 0
