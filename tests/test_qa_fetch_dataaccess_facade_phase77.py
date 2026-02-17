from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest

from quant_eam.qa_fetch import facade
from quant_eam.qa_fetch.runtime import FetchExecutionResult, STATUS_PASS_HAS_DATA


def _ok_result(*, fn_name: str) -> FetchExecutionResult:
    return FetchExecutionResult(
        status=STATUS_PASS_HAS_DATA,
        reason="ok",
        source="fetch",
        source_internal="mongo_fetch",
        engine="mongo",
        provider_id="fetch",
        provider_internal="mongo_fetch",
        resolved_function=fn_name,
        public_function=fn_name,
        elapsed_sec=0.01,
        row_count=1,
        columns=["code"],
        dtypes={"code": "object"},
        preview=[{"code": "000001"}],
        final_kwargs={"code": "000001"},
        mode="smoke",
        data=[{"code": "000001"}],
    )


def test_execute_fetch_request_dispatches_function_mode(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def _fake_execute_fetch_by_intent(intent_payload, **kwargs):
        captured["intent_payload"] = intent_payload
        captured.update(kwargs)
        return _ok_result(fn_name="fetch_stock_day")

    monkeypatch.setattr(facade, "execute_fetch_by_intent", _fake_execute_fetch_by_intent)

    out = facade.execute_fetch_request(
        {
            "function": "fetch_stock_day",
            "strong_control_function": True,
            "kwargs": {"symbol": "000001"},
            "source_hint": "mongo_fetch",
            "public_function": "fetch_stock_day",
        },
        policy={"mode": "smoke"},
    )

    assert out.status == STATUS_PASS_HAS_DATA
    assert captured["intent_payload"]["function"] == "fetch_stock_day"
    assert captured["intent_payload"]["kwargs"] == {"symbol": "000001"}
    assert captured["intent_payload"]["source_hint"] == "mongo_fetch"
    assert captured["intent_payload"]["public_function"] == "fetch_stock_day"
    assert captured["policy"]["mode"] == "smoke"


def test_execute_fetch_request_dispatches_intent_mode(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def _fake_execute_fetch_by_intent(intent_payload, **kwargs):
        captured["intent_payload"] = intent_payload
        captured.update(kwargs)
        return _ok_result(fn_name="fetch_stock_day")

    monkeypatch.setattr(facade, "execute_fetch_by_intent", _fake_execute_fetch_by_intent)

    out = facade.execute_fetch_request(
        {
            "intent": {"asset": "stock", "freq": "day", "symbols": ["000001"]},
        },
        policy={"mode": "backtest"},
    )

    assert out.status == STATUS_PASS_HAS_DATA
    assert (captured["intent_payload"]["intent"] or {})["asset"] == "stock"
    assert captured["policy"]["mode"] == "backtest"


def test_agents_import_facade_execution_calls_and_block_runtime_execution_imports() -> None:
    targets = [
        Path("src/quant_eam/agents/demo_agent.py"),
        Path("src/quant_eam/agents/backtest_agent.py"),
    ]
    for path in targets:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        facade_imports: set[str] = set()
        runtime_imports: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            names = {alias.name for alias in node.names}
            if node.module == "quant_eam.qa_fetch.facade":
                facade_imports.update(names)
            if node.module == "quant_eam.qa_fetch.runtime":
                runtime_imports.update(names)

        assert "execute_fetch_by_name" in facade_imports
        assert "execute_fetch_by_intent" in facade_imports
        assert "execute_fetch_by_name" not in runtime_imports
        assert "execute_fetch_by_intent" not in runtime_imports

        text = path.read_text(encoding="utf-8")
        assert "quant_eam.qa_fetch.providers" not in text


def test_execute_fetch_request_rejects_non_mapping_payload_before_runtime_entry(monkeypatch) -> None:
    captured: dict[str, bool] = {}

    def _fake_execute_fetch_by_intent(_intent_payload, **_kwargs) -> None:
        captured["called"] = True
        raise AssertionError("execute_fetch_by_intent should not be called on invalid request")

    monkeypatch.setattr(facade, "execute_fetch_by_intent", _fake_execute_fetch_by_intent)

    with pytest.raises(ValueError, match=r"fetch_request must be an object"):
        facade.execute_fetch_request("bad")

    assert not captured


def test_agents_imports_do_not_bypass_facade_via_providers_or_db_paths() -> None:
    forbidden_import_fragments = (
        "quant_eam.qa_fetch.providers",
        "quant_eam.qa_fetch.mongo_bridge",
        "quant_eam.qa_fetch.mysql_bridge",
        "quant_eam.qa_fetch.providers.mongo_fetch",
        "quant_eam.qa_fetch.providers.mysql_fetch",
        "quant_eam.qa_fetch.providers.mongo_fetch.mongo import get_db",
        "quant_eam.qa_fetch.providers.mysql_fetch.utils import DATABASE_TEST2",
    )
    for path in sorted(Path("src/quant_eam/agents").glob("*.py")):
        if path.name == "__init__.py":
            continue
        text = path.read_text(encoding="utf-8")
        for fragment in forbidden_import_fragments:
            assert fragment not in text, f"{path} contains forbidden fragment: {fragment}"
