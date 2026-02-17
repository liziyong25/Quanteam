from __future__ import annotations

from quant_eam.api.ui_routes import _coerce_symbol_list


def test_workbench_symbol_coerce_accepts_csv_string() -> None:
    assert _coerce_symbol_list("AAPL, MSFT,,") == ["AAPL", "MSFT"]


def test_workbench_symbol_coerce_accepts_list() -> None:
    assert _coerce_symbol_list(["AAPL", "  ", "MSFT"]) == ["AAPL", "MSFT"]


def test_workbench_symbol_coerce_rejects_non_string_shapes() -> None:
    assert _coerce_symbol_list({"a": 1}) == []
    assert _coerce_symbol_list(None) == []
