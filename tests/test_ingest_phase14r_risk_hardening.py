from __future__ import annotations

import json
import re
from pathlib import Path

from quant_eam.contracts import validate as contracts_validate
from quant_eam.datacatalog.catalog import DataCatalog
from quant_eam.ingest.wequant_ohlcv import MockWeQuantProvider, ingest_wequant_ohlcv_1d, main as ingest_main
from quant_eam.policies.load import load_yaml


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def test_phase14r_ingest_manifest_has_policy_audit_fields(tmp_path: Path, monkeypatch) -> None:
    data_root = tmp_path / "data"
    data_root.mkdir()
    monkeypatch.setenv("EAM_DATA_ROOT", str(data_root))
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    snap = "demo_wq_snap_risk_001"
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
    ingest_manifest_path = snap_dir / "ingest_manifest.json"
    assert ingest_manifest_path.is_file()

    # Contract validate through schema dispatch.
    assert contracts_validate.validate_json(ingest_manifest_path)[0] == contracts_validate.EXIT_OK

    doc = json.loads(ingest_manifest_path.read_text(encoding="utf-8"))
    assert doc["schema_version"] == "ingest_manifest_v1"

    pol = load_yaml(Path("policies/asof_latency_policy_v1.yaml"))
    assert isinstance(pol, dict)
    params = pol.get("params")
    assert isinstance(params, dict)

    assert doc["asof_rule"] == "available_at<=as_of"
    assert doc["asof_latency_policy_id"] == pol["policy_id"]
    assert doc["default_latency_seconds"] == int(params.get("default_latency_seconds", 0))
    assert int(doc.get("sha256_of_data_file", "0"), 16) >= 0

    # Optional trade lag if present in policy params.
    if "trade_lag_bars_default" in params:
        assert doc.get("trade_lag_bars_default") == int(params["trade_lag_bars_default"])


def test_phase14r_dt_normalization_when_provider_returns_datetime(tmp_path: Path, monkeypatch) -> None:
    data_root = tmp_path / "data"
    data_root.mkdir()
    monkeypatch.setenv("EAM_DATA_ROOT", str(data_root))
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    provider = MockWeQuantProvider(seed="dt_datetime_test", dt_mode="datetime")
    res = ingest_wequant_ohlcv_1d(
        provider=provider,
        provider_id="mock",
        provider_version="v1",
        root=data_root,
        snapshot_id="demo_wq_snap_risk_dt_001",
        symbols=["AAA"],
        start="2024-01-01",
        end="2024-01-03",
    )

    csv_path = Path(res.data_file)
    assert csv_path.is_file()
    lines = csv_path.read_text(encoding="utf-8").splitlines()
    assert lines[0].split(",")[0:2] == ["symbol", "dt"]
    dt_col = [ln.split(",")[1] for ln in lines[1:]]
    assert all(_DATE_RE.match(v) for v in dt_col)


def test_phase14r_real_provider_stub_fails_with_exit_2(tmp_path: Path, monkeypatch) -> None:
    data_root = tmp_path / "data"
    data_root.mkdir()
    monkeypatch.setenv("EAM_DATA_ROOT", str(data_root))
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    # wequant is not available in CI; must fail deterministically with exit=2 and message suggesting mock.
    code = ingest_main(
        [
            "--provider",
            "wequant",
            "--snapshot-id",
            "demo_wq_snap_risk_real_001",
            "--symbols",
            "AAA",
            "--start",
            "2024-01-01",
            "--end",
            "2024-01-02",
        ]
    )
    assert code == 2


def test_phase14r_asof_filtering_still_works(tmp_path: Path, monkeypatch) -> None:
    data_root = tmp_path / "data"
    data_root.mkdir()
    monkeypatch.setenv("EAM_DATA_ROOT", str(data_root))
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    snap = "demo_wq_snap_risk_asof_001"
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
    rows, stats = cat.query_ohlcv(
        snapshot_id=snap,
        symbols=["AAA", "BBB"],
        start="2024-01-01",
        end="2024-01-10",
        as_of="2024-01-05T00:00:00+08:00",
    )
    assert stats.rows_before_asof > stats.rows_after_asof
    assert len(rows) == 8
