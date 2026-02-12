from __future__ import annotations

from pathlib import Path

from quant_eam.qa_fetch.policy import apply_user_policy
from quant_eam.qa_fetch.registry import build_fetch_mappings, collision_keys
from quant_eam.qa_fetch.source import SOURCE_MONGO, SOURCE_MYSQL


def test_qa_fetch_mapping_counts_and_collisions() -> None:
    rows = build_fetch_mappings()
    wq = [r for r in rows if r.source == SOURCE_MONGO]
    wb = [r for r in rows if r.source == SOURCE_MYSQL]

    assert len(wq) == 83
    assert len(wb) == 55
    assert set(collision_keys()) == {"fetch_future_day", "fetch_future_list", "fetch_future_min"}


def test_qa_fetch_proposed_names_are_snake_case_with_prefix() -> None:
    rows = [r for r in apply_user_policy(build_fetch_mappings()) if r.status != "drop"]
    assert len(rows) == 71
    for row in rows:
        assert row.proposed_name.startswith("fetch_")
        assert row.proposed_name == row.proposed_name.lower()
        assert " " not in row.proposed_name


def test_rename_matrix_v3_matches_user_policy() -> None:
    v3 = Path("docs/05_data_plane/qa_fetch_function_baseline_v1.md").read_text(encoding="utf-8")

    assert "`qa_fetch_" not in v3
    assert "frozen 71-function baseline" in v3
    assert "| fetch | `fetch_clean_quote` | `fetch_bond_quote` |" in v3
    assert "| fetch | `fetch_settlement_bond_day` | `fetch_bond_day_cfets` |" in v3
    assert "| fetch | `fetch_bond_industry_settlement` | `fetch_bond_industry_settlement` |" in v3
    assert "| fetch | `fetch_cfets_bond_amount` | `fetch_bond_amount_cfets` |" in v3
    assert "| fetch | `fetch_ctp_tick` | `fetch_future_transaction_ctp` |" in v3
    assert "| fetch | `fetch_zz_bond_valuation` | `fetch_bond_valuation_zz` |" in v3
    assert "| fetch | `fetch_lhb` |" not in v3
    assert "| fetch | `fetch_quotation` |" not in v3
    assert "| fetch | `fetch_quotations` |" not in v3
    assert "| fetch | `fetch_realtime_min` |" not in v3
    assert "| fetch | `fetch_stock_realtime_adv` |" not in v3
    assert "| fetch | `fetch_financial_report_adv` |" not in v3
    assert "| fetch | `fetch_cryptocurrency_list_adv` |" not in v3
    assert "| fetch | `fetch_index_list_adv` |" not in v3
    assert "| fetch | `fetch_future_list_adv` |" not in v3
    assert "| fetch | `fetch_stock_block_adv` |" not in v3
    assert "| fetch | `fetch_stock_list_adv` | `fetch_stock_list` |" not in v3
    assert v3.startswith("# QA Fetch Function Baseline v1")
