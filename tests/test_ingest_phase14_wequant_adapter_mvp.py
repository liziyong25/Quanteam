from __future__ import annotations

import hashlib
import json
from pathlib import Path

from quant_eam.data_lake.timeutil import parse_iso_datetime
from quant_eam.datacatalog.catalog import DataCatalog
from quant_eam.ingest.wequant_ohlcv import main as ingest_main


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def test_phase14_mock_ingest_is_reproducible_and_writes_manifest(tmp_path: Path, monkeypatch) -> None:
    data_root = tmp_path / "data"
    data_root.mkdir()
    monkeypatch.setenv("EAM_DATA_ROOT", str(data_root))
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    snap = "demo_wq_snap_test_001"
    args = [
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

    assert ingest_main(args) == 0
    snap_dir = data_root / "lake" / snap
    csv_path = snap_dir / "ohlcv_1d.csv"
    snap_manifest = snap_dir / "manifest.json"
    ingest_manifest = snap_dir / "ingest_manifest.json"
    assert csv_path.is_file()
    assert snap_manifest.is_file()
    assert ingest_manifest.is_file()

    h1 = (_sha256(csv_path), _sha256(snap_manifest), _sha256(ingest_manifest))

    # Run again; should be identical under fixed SOURCE_DATE_EPOCH.
    assert ingest_main(args) == 0
    h2 = (_sha256(csv_path), _sha256(snap_manifest), _sha256(ingest_manifest))
    assert h1 == h2

    doc = json.loads(ingest_manifest.read_text(encoding="utf-8"))
    assert doc["snapshot_id"] == snap
    assert doc["provider_id"] == "mock"
    req = doc["request_spec"]
    assert req["symbols"] == ["AAA", "BBB"]
    assert req["start"] == "2024-01-01"
    assert req["end"] == "2024-01-10"
    assert req["frequency"] == "1d"
    assert "sha256_of_data_file" in doc and isinstance(doc["sha256_of_data_file"], str)
    assert doc["sha256_of_data_file"] == doc["sha256_of_data_file"].lower()


def test_phase14_available_at_generated_and_asof_filtering_works(tmp_path: Path, monkeypatch) -> None:
    data_root = tmp_path / "data"
    data_root.mkdir()
    monkeypatch.setenv("EAM_DATA_ROOT", str(data_root))
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    snap = "demo_wq_snap_test_002"
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

    cat = DataCatalog(root=data_root)
    # With asof at 2024-01-05 00:00+08, only dt <= 2024-01-04 should be visible (bar close is 16:00+08).
    rows, stats = cat.query_ohlcv(
        snapshot_id=snap,
        symbols=["AAA", "BBB"],
        start="2024-01-01",
        end="2024-01-10",
        as_of="2024-01-05T00:00:00+08:00",
    )
    assert stats.rows_before_asof > stats.rows_after_asof
    assert len(rows) == 2 * 4  # 2 symbols * 4 days (01..04)

    # available_at must be present and <= as_of for returned rows.
    asof_dt = parse_iso_datetime("2024-01-05T00:00:00+08:00")
    for r in rows:
        assert "available_at" in r
        av = parse_iso_datetime(str(r["available_at"]))
        assert av <= asof_dt
