from __future__ import annotations

from typing import Any

from quant_eam.qa_fetch import runtime


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
    monkeypatch.setattr(runtime, "_resolve_callable", lambda _fn_name, source_hint=None: (_fn, "wbdata"))

    res = runtime.execute_fetch_by_name(
        function="fetch_demo",
        kwargs={"symbol": "from_llm"},
        policy={"mode": "smoke"},
    )

    assert res.status == runtime.STATUS_PASS_HAS_DATA
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
    monkeypatch.setattr(runtime, "_resolve_callable", lambda _fn_name, source_hint=None: (_fn, "wbdata"))
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
    monkeypatch.setattr(runtime, "_resolve_callable", lambda _fn_name, source_hint=None: (_fn, "wequant"))

    pass_empty = runtime.execute_fetch_by_name(function="fetch_demo", kwargs={}, policy={"mode": "smoke"})
    as_error = runtime.execute_fetch_by_name(
        function="fetch_demo",
        kwargs={},
        policy={"mode": "smoke", "on_no_data": "error"},
    )

    assert pass_empty.status == runtime.STATUS_PASS_EMPTY
    assert as_error.status == runtime.STATUS_ERROR_RUNTIME
    assert as_error.reason == "no_data"


def test_runtime_exception_mapping_and_decision_gate(monkeypatch) -> None:
    def _missing_table_fn() -> None:
        raise RuntimeError("ProgrammingError: table test2.clean_bond_quote doesn't exist")

    monkeypatch.setattr(runtime, "load_smoke_window_profile", lambda _path: {})
    monkeypatch.setattr(runtime, "load_exception_decisions", lambda _path: {})
    monkeypatch.setattr(runtime, "_resolve_callable", lambda _fn_name, source_hint=None: (_missing_table_fn, "wbdata"))

    blocked = runtime.execute_fetch_by_name(function="fetch_clean_quote", kwargs={}, policy={"mode": "smoke"})
    assert blocked.status == runtime.STATUS_BLOCKED_SOURCE_MISSING

    monkeypatch.setattr(
        runtime,
        "load_exception_decisions",
        lambda _path: {
            "fetch_clean_quote": {
                "issue_type": "source_table_missing",
                "smoke_policy": "blocked",
                "research_policy": "blocked",
                "decision": "pending",
                "notes": "manual",
            }
        },
    )
    pending = runtime.execute_fetch_by_name(function="fetch_clean_quote", kwargs={}, policy={"mode": "smoke"})
    assert pending.status == runtime.STATUS_BLOCKED_SOURCE_MISSING
    assert "disabled_by_exception_policy" in pending.reason
