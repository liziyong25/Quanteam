from __future__ import annotations

import csv
from pathlib import Path

from quant_eam.datacatalog.catalog import DataCatalog


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_query_dataset_market_asof_and_wrapper_compat(tmp_path: Path) -> None:
    root = tmp_path
    dataset = root / "lake" / "snap_1" / "ohlcv_1d.csv"
    _write_csv(
        dataset,
        [
            {
                "symbol": "AAA",
                "dt": "2024-01-01",
                "open": "1",
                "high": "2",
                "low": "1",
                "close": "2",
                "volume": "10",
                "available_at": "2024-01-01T16:00:00+08:00",
            },
            {
                "symbol": "AAA",
                "dt": "2024-01-02",
                "open": "2",
                "high": "3",
                "low": "2",
                "close": "3",
                "volume": "20",
                "available_at": "2024-01-03T16:00:00+08:00",
            },
        ],
    )

    cat = DataCatalog(root=root)
    result = cat.query_dataset(
        snapshot_id="snap_1",
        dataset_id="ohlcv_1d",
        filters={"symbol": ["AAA"], "dt": {"gte": "2024-01-01", "lte": "2024-01-10"}},
        as_of="2024-01-02T00:00:00+08:00",
    )
    assert result["schema_version"] == "qa_dataset_query_result_v1"
    assert result["row_count"] == 1
    assert result["as_of_applied"]["applied"] is True
    assert result["as_of_applied"]["rows_before_asof"] == 2
    assert result["as_of_applied"]["rows_after_asof"] == 1

    rows, stats = cat.query_ohlcv(
        snapshot_id="snap_1",
        symbols=["AAA"],
        start="2024-01-01",
        end="2024-01-10",
        as_of="2024-01-02T00:00:00+08:00",
    )
    assert len(rows) == 1
    assert stats.rows_before_asof == 2
    assert stats.rows_after_asof == 1


def test_query_dataset_reference_mode_without_available_at(tmp_path: Path) -> None:
    root = tmp_path
    dataset = root / "lake" / "snap_2" / "stock_reference.csv"
    _write_csv(
        dataset,
        [
            {"symbol": "AAA", "industry": "bank"},
            {"symbol": "BBB", "industry": "tech"},
        ],
    )

    cat = DataCatalog(root=root)
    result = cat.query_dataset(
        snapshot_id="snap_2",
        dataset_id="stock_reference",
        filters={"symbol": ["AAA", "BBB"]},
        as_of="2024-01-10T00:00:00+08:00",
        fields=["symbol", "industry"],
    )
    assert result["row_count"] == 2
    assert result["as_of_applied"]["mode"] == "reference"
    assert result["as_of_applied"]["applied"] is False

