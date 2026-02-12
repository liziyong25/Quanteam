from __future__ import annotations

from pathlib import Path

from quant_eam.qa_fetch.policy import apply_user_policy
from quant_eam.qa_fetch.registry import build_fetch_mappings, collision_keys


def test_qa_fetch_mapping_counts_and_collisions() -> None:
    rows = build_fetch_mappings()
    wq = [r for r in rows if r.source == "wequant"]
    wb = [r for r in rows if r.source == "wbdata"]

    assert len(wq) == 83
    assert len(wb) == 55
    assert set(collision_keys()) == {"fetch_future_day", "fetch_future_list", "fetch_future_min"}


def test_qa_fetch_proposed_names_are_snake_case_with_prefix() -> None:
    rows = [r for r in apply_user_policy(build_fetch_mappings()) if r.status != "drop"]
    assert len(rows) == 77
    for row in rows:
        assert row.proposed_name.startswith("fetch_")
        assert row.proposed_name == row.proposed_name.lower()
        assert " " not in row.proposed_name


def test_rename_matrix_v3_matches_user_policy() -> None:
    v3 = Path("docs/05_data_plane/_draft_qa_fetch_rename_matrix_v3.md").read_text(encoding="utf-8")

    assert "`qa_fetch_" not in v3
    assert "| wbdata | `fetch_clean_quote` | `fetch_bond_quote` |" in v3
    assert "| wbdata | `fetch_settlement_bond_day` | `fetch_bond_day_cfets` |" in v3
    assert "| wbdata | `fetch_bond_industry_settlement` | `fetch_bond_industry_cfets` |" in v3
    assert "| wbdata | `fetch_cfets_bond_amount` | `fetch_bond_amount_cfets` |" in v3
    assert "| wequant | `fetch_cryptocurrency_list_adv` |" not in v3
    assert "| wequant | `fetch_index_list_adv` |" not in v3
    assert "| wequant | `fetch_future_list_adv` |" not in v3
    assert "| wequant | `fetch_stock_block_adv` |" not in v3
    assert "| wequant | `fetch_stock_list_adv` | `fetch_stock_list` |" not in v3
    assert v3.startswith("# QA Fetch Rename Matrix (Draft v3)")
