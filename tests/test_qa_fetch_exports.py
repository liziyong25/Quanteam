from __future__ import annotations

import quant_eam.qa_fetch as qa_fetch


def test_qa_fetch_exports_have_priority_and_wb_fallback_alias() -> None:
    export_map = qa_fetch.qa_fetch_export_map()

    assert "fetch_future_day" in export_map
    assert export_map["fetch_future_day"]["source"] == "wequant"

    assert "wb_fetch_bond_day" in export_map
    assert export_map["wb_fetch_bond_day"]["source"] == "wbdata"
    assert export_map["wb_fetch_bond_day"]["target_name"] == "fetch_bond_day"


def test_qa_fetch_registry_accessors() -> None:
    rows = qa_fetch.qa_fetch_registry()
    keys = qa_fetch.qa_fetch_collision_keys()
    assert len(rows) == 77
    assert set(keys) == {"fetch_future_day", "fetch_future_list", "fetch_future_min"}


def test_qa_fetch_exports_include_resolver_runtime_apis() -> None:
    assert callable(qa_fetch.resolve_fetch)
    assert callable(qa_fetch.fetch_market_data)
    assert callable(qa_fetch.execute_fetch_by_intent)
    assert callable(qa_fetch.execute_fetch_by_name)
    assert callable(qa_fetch.write_fetch_evidence)
