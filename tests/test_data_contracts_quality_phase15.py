from __future__ import annotations

import json
from pathlib import Path

from quant_eam.contracts import validate as contracts_validate
from quant_eam.datacatalog.catalog import DataCatalog
from quant_eam.ingest.wequant_ohlcv import main as ingest_main


def test_phase15_manifests_validate_and_quality_report_exists(tmp_path: Path, monkeypatch) -> None:
    data_root = tmp_path / "data"
    data_root.mkdir()
    monkeypatch.setenv("EAM_DATA_ROOT", str(data_root))
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    snap = "snap_qc_test_001"
    assert (
        ingest_main(
            [
                "--provider",
                "mock",
                "--snapshot-id",
                snap,
                "--symbols",
                "AAA,BBB",
                "--start",
                "2024-01-01",
                "--end",
                "2024-01-10",
            ]
        )
        == 0
    )

    snap_dir = data_root / "lake" / snap
    manifest_path = snap_dir / "manifest.json"
    ingest_manifest_path = snap_dir / "ingest_manifest.json"
    quality_path = snap_dir / "quality_report.json"
    assert manifest_path.is_file()
    assert ingest_manifest_path.is_file()
    assert quality_path.is_file()

    # Contracts validate for manifests.
    assert contracts_validate.validate_json(manifest_path)[0] == contracts_validate.EXIT_OK
    assert contracts_validate.validate_json(ingest_manifest_path)[0] == contracts_validate.EXIT_OK

    # Manifest must reference quality report.
    man = json.loads(manifest_path.read_text(encoding="utf-8"))
    ds = man["datasets"][0]
    ext = ds.get("extensions") if isinstance(ds.get("extensions"), dict) else {}
    assert str(ext.get("quality_report_ref", "")).endswith("/quality_report.json")

    # Quality report has expected fields.
    q = json.loads(quality_path.read_text(encoding="utf-8"))
    for k in (
        "snapshot_id",
        "dataset_id",
        "rows_before_dedupe",
        "rows_after_dedupe",
        "duplicate_count",
        "null_count_by_col",
        "min_by_col",
        "max_by_col",
    ):
        assert k in q

    # as_of filtering should still work.
    cat = DataCatalog(root=data_root)
    rows, stats = cat.query_ohlcv(
        snapshot_id=snap,
        symbols=["AAA", "BBB"],
        start="2024-01-01",
        end="2024-01-10",
        as_of="2024-01-05T00:00:00+08:00",
    )
    assert stats.rows_before_asof > stats.rows_after_asof
    assert len(rows) == 8

