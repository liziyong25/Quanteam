from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

pytest.importorskip("jsonschema")
pytest.importorskip("referencing")

from quant_eam.contracts import validate as contracts_validate


def test_validate_fetch_request_accepts_function_with_kwargs_symbol() -> None:
    payload = {
        "mode": "smoke",
        "function": "fetch_stock_day",
        "kwargs": {
            "symbol": "000001",
            "start": "2024-01-01",
            "end": "2024-01-03",
        },
    }
    code, msg = contracts_validate.validate_fetch_request(payload)
    assert code == contracts_validate.EXIT_OK, msg


def test_validate_fetch_request_accepts_auto_symbols_without_explicit_symbols() -> None:
    payload = {
        "mode": "backtest",
        "intent": {"asset": "stock", "freq": "day", "start": "2024-01-01", "end": "2024-01-10"},
        "auto_symbols": True,
    }
    code, msg = contracts_validate.validate_fetch_request(payload)
    assert code == contracts_validate.EXIT_OK, msg


def test_validate_fetch_request_accepts_intent_scoped_auto_symbols() -> None:
    payload = {
        "mode": "backtest",
        "intent": {
            "asset": "stock",
            "freq": "day",
            "start": "2024-01-01",
            "end": "2024-01-10",
            "auto_symbols": True,
            "sample": {"n": 10, "method": "random"},
        },
        "policy": {"on_no_data": "retry"},
    }
    code, msg = contracts_validate.validate_fetch_request(payload)
    assert code == contracts_validate.EXIT_OK, msg


def test_validate_fetch_request_rejects_missing_symbols_when_auto_symbols_false() -> None:
    payload = {
        "mode": "backtest",
        "intent": {"asset": "stock", "freq": "day", "start": "2024-01-01", "end": "2024-01-10"},
    }
    code, msg = contracts_validate.validate_fetch_request(payload)
    assert code == contracts_validate.EXIT_INVALID
    assert "auto_symbols=true" in msg


def test_validate_fetch_request_rejects_auto_symbols_with_explicit_symbols() -> None:
    payload = {
        "mode": "research",
        "function": "fetch_stock_day",
        "kwargs": {"symbol": "000001"},
        "auto_symbols": True,
    }
    code, msg = contracts_validate.validate_fetch_request(payload)
    assert code == contracts_validate.EXIT_INVALID
    assert "cannot be combined with explicit symbols" in msg


def test_validate_fetch_request_rejects_start_after_end() -> None:
    payload = {
        "mode": "smoke",
        "function": "fetch_stock_day",
        "kwargs": {
            "symbol": "000001",
            "start": "2024-01-10",
            "end": "2024-01-01",
        },
    }
    code, msg = contracts_validate.validate_fetch_request(payload)
    assert code == contracts_validate.EXIT_INVALID
    assert "start must be <= end" in msg


def test_validate_fetch_request_rejects_intent_and_function_together() -> None:
    payload = {
        "mode": "smoke",
        "function": "fetch_stock_day",
        "intent": {"asset": "stock", "freq": "day", "symbols": "000001"},
    }
    code, msg = contracts_validate.validate_fetch_request(payload)
    assert code == contracts_validate.EXIT_INVALID
    assert "should not be valid under" in msg or "mutually exclusive" in msg


def test_validate_fetch_request_rejects_conflicting_auto_symbols_locations() -> None:
    payload = {
        "mode": "smoke",
        "intent": {
            "asset": "stock",
            "freq": "day",
            "auto_symbols": False,
        },
        "auto_symbols": True,
    }
    code, msg = contracts_validate.validate_fetch_request(payload)
    assert code == contracts_validate.EXIT_INVALID
    assert "conflicts with top-level" in msg


def test_validate_fetch_result_meta_schema() -> None:
    payload = {
        "status": "pass_has_data",
        "reason": "ok",
        "source": "fetch",
        "source_internal": "mongo_fetch",
        "engine": "mongo",
        "provider_id": "fetch",
        "provider_internal": "mongo_fetch",
        "resolved_function": "fetch_stock_day",
        "public_function": "fetch_stock_day",
        "selected_function": "fetch_stock_day",
        "elapsed_sec": 0.12,
        "row_count": 3,
        "col_count": 2,
        "columns": ["code", "date"],
        "dtypes": {"code": "object", "date": "object"},
        "preview": [{"code": "000001", "date": "2024-01-01"}],
        "final_kwargs": {"symbol": "000001"},
        "request_hash": "fdbf4f7d73683910b26af3f36e5be24c7ebb8f31c1ecf4ca8ec7037f183a6607",
        "probe_status": "pass_has_data",
        "warnings": [],
        "coverage": {
            "requested_symbol_count": 1,
            "requested_symbols": ["000001"],
            "observed_symbol_count": 1,
            "observed_symbols": ["000001"],
        },
        "min_ts": "2024-01-01",
        "max_ts": "2024-01-01",
        "mode": "smoke",
    }
    code, msg = contracts_validate.validate_fetch_result_meta(payload)
    assert code == contracts_validate.EXIT_OK, msg
