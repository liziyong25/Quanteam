from __future__ import annotations

import json
from pathlib import Path

from quant_eam.wequant_adapter.client import FakeScenario, FakeWequantClient
from quant_eam.wequant_adapter.ingest import EXIT_INVALID, EXIT_OK, ingest_ohlcv_1d, main as ingest_main


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_cli_fake_ingest_writes_files(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("EAM_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    snap = "wq_snap_ok_001"
    args = [
        "--client",
        "fake",
        "--snapshot-id",
        snap,
        "--dataset-id",
        "ohlcv_1d",
        "--symbols",
        "AAA,BBB",
        "--start",
        "2024-01-01",
        "--end",
        "2024-01-03",
        "--policy-bundle",
        str(_repo_root() / "policies" / "policy_bundle_v1.yaml"),
    ]
    assert ingest_main(args) == EXIT_OK

    base = tmp_path / "lake" / snap
    assert (base / "ohlcv_1d.csv").is_file()
    assert (base / "manifest.json").is_file()
    assert (base / "ingest_manifests" / "ohlcv_1d_wequant_ingest.json").is_file()


def test_available_at_generation_exact(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("EAM_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    client = FakeWequantClient(FakeScenario(include_available_at=False))
    res = ingest_ohlcv_1d(
        client=client,
        root=tmp_path,
        snapshot_id="wq_snap_av_001",
        dataset_id="ohlcv_1d",
        symbols=["AAA"],
        start="2024-01-01",
        end="2024-01-01",
        policy_bundle_path=_repo_root() / "policies" / "policy_bundle_v1.yaml",
        dry_run=False,
    )
    csv_path = Path(res.data_file)
    lines = csv_path.read_text(encoding="utf-8").splitlines()
    assert lines[0].split(",")[:2] == ["symbol", "dt"]
    # First data row has dt=2024-01-01 and policy default latency=0; anchor is 16:00+08:00.
    first = lines[1].split(",")
    header = lines[0].split(",")
    idx_dt = header.index("dt")
    idx_av = header.index("available_at")
    assert first[idx_dt] == "2024-01-01"
    assert first[idx_av] == "2024-01-01T16:00:00+08:00"


def test_available_at_validation_rejects_future_leak(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("EAM_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    snap = "wq_snap_bad_av_001"
    args = [
        "--client",
        "fake",
        "--snapshot-id",
        snap,
        "--dataset-id",
        "ohlcv_1d",
        "--symbols",
        "AAA",
        "--start",
        "2024-01-01",
        "--end",
        "2024-01-01",
        "--policy-bundle",
        str(_repo_root() / "policies" / "policy_bundle_v1.yaml"),
    ]
    # Use a bad available_at fake client by invoking ingest_ohlcv_1d directly.
    client = FakeWequantClient(FakeScenario(include_available_at=True, bad_available_at=True))
    try:
        ingest_ohlcv_1d(
            client=client,
            root=tmp_path,
            snapshot_id=snap,
            dataset_id="ohlcv_1d",
            symbols=["AAA"],
            start="2024-01-01",
            end="2024-01-01",
            policy_bundle_path=_repo_root() / "policies" / "policy_bundle_v1.yaml",
        )
        assert False, "expected ValueError for invalid available_at"
    except ValueError:
        pass


def test_dedupe_and_manifest_duplicate_count(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("EAM_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    client = FakeWequantClient(FakeScenario(include_available_at=False, include_duplicates=True))
    snap = "wq_snap_dup_001"
    res = ingest_ohlcv_1d(
        client=client,
        root=tmp_path,
        snapshot_id=snap,
        dataset_id="ohlcv_1d",
        symbols=["AAA"],
        start="2024-01-01",
        end="2024-01-02",
        policy_bundle_path=_repo_root() / "policies" / "policy_bundle_v1.yaml",
        dry_run=False,
    )
    mf = json.loads(Path(res.ingest_manifest_file).read_text(encoding="utf-8"))
    assert mf["duplicate_count"] == 1
    assert mf["rows_in"] > mf["rows_out"]

