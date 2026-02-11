from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from quant_eam.api.app import app
from quant_eam.ingest.wequant_ohlcv import main as ingest_main
from quant_eam.snapshots.catalog import SnapshotCatalog


def test_phase16_snapshot_catalog_api_and_ui(tmp_path: Path, monkeypatch) -> None:
    data_root = tmp_path / "data"
    data_root.mkdir()
    monkeypatch.setenv("EAM_DATA_ROOT", str(data_root))
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    snap = "snap_ui_test_001"
    assert (
        ingest_main(
            [
                "--provider",
                "mock",
                "--root",
                str(data_root),
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

    # Catalog: list + load + contract validation.
    cat = SnapshotCatalog(root=data_root)
    snaps = cat.list_snapshots()
    assert any(r.snapshot_id == snap for r in snaps)
    doc = cat.load_snapshot(snap)
    assert doc["snapshot_id"] == snap
    assert isinstance(doc["manifest"], dict)
    assert isinstance(doc["ingest_manifest"], dict)
    assert isinstance(doc["quality_report"], dict)

    # API/ UI
    client = TestClient(app)

    r = client.get("/snapshots")
    assert r.status_code == 200, r.text
    payload = r.json()
    assert any(s.get("snapshot_id") == snap for s in payload.get("snapshots", []))

    r = client.get(f"/snapshots/{snap}")
    assert r.status_code == 200, r.text
    doc2 = r.json()
    assert doc2["snapshot_id"] == snap

    r = client.get(f"/snapshots/{snap}/quality")
    assert r.status_code == 200
    q = r.json()["quality_report"]
    assert q["snapshot_id"] == snap

    r = client.get(
        f"/snapshots/{snap}/preview/ohlcv",
        params={
            "symbols": "AAA,BBB",
            "start": "2024-01-01",
            "end": "2024-01-10",
            "as_of": "2024-01-05T00:00:00+08:00",
            "limit": 50,
        },
    )
    assert r.status_code == 200, r.text
    prev = r.json()
    assert prev["snapshot_id"] == snap
    assert prev["stats"]["rows_before_asof"] > prev["stats"]["rows_after_asof"]
    assert len(prev["rows"]) <= 50

    r = client.get("/ui/snapshots")
    assert r.status_code == 200
    assert snap in r.text

    r = client.get(f"/ui/snapshots/{snap}")
    assert r.status_code == 200
    assert snap in r.text

