from __future__ import annotations

import json
from pathlib import Path

from quant_eam.contracts import validate as contracts_validate
from quant_eam.data_lake.demo_ingest import main as demo_ingest_main
from quant_eam.runner.run import EXIT_OK, main as runner_main


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_runner_demo_writes_contract_valid_dossier(tmp_path: Path, monkeypatch) -> None:
    data_root = tmp_path / "data"
    art_root = tmp_path / "artifacts"
    data_root.mkdir()
    art_root.mkdir()

    monkeypatch.setenv("EAM_DATA_ROOT", str(data_root))
    monkeypatch.setenv("EAM_ARTIFACT_ROOT", str(art_root))
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    # Ensure snapshot exists.
    snap = "demo_snap_001"
    assert demo_ingest_main(["--root", str(data_root), "--snapshot-id", snap]) == 0

    # Run runner demo (deterministic run_id).
    bundle = _repo_root() / "policies" / "policy_bundle_v1.yaml"
    code = runner_main(["--demo", "--policy-bundle", str(bundle), "--snapshot-id", snap])
    assert code == EXIT_OK

    # Derive run_id by reading the generated demo runspec on disk is not stable here;
    # instead locate dossiers directory.
    dossiers_dir = art_root / "dossiers"
    assert dossiers_dir.is_dir()
    runs = sorted([p for p in dossiers_dir.iterdir() if p.is_dir()])
    assert runs, "no dossier written"
    d = runs[0]

    required = [
        "dossier_manifest.json",
        "config_snapshot.json",
        "data_manifest.json",
        "metrics.json",
        "curve.csv",
        "trades.csv",
        "reports/report.md",
    ]
    for rel in required:
        assert (d / rel).is_file(), rel

    # Contract validation for dossier manifest must pass.
    code2, msg2 = contracts_validate.validate_json(d / "dossier_manifest.json")
    assert code2 == contracts_validate.EXIT_OK, msg2


def test_append_only_noop_on_same_runspec(tmp_path: Path, monkeypatch) -> None:
    data_root = tmp_path / "data"
    art_root = tmp_path / "artifacts"
    data_root.mkdir()
    art_root.mkdir()
    monkeypatch.setenv("EAM_DATA_ROOT", str(data_root))
    monkeypatch.setenv("EAM_ARTIFACT_ROOT", str(art_root))
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    snap = "demo_snap_001"
    assert demo_ingest_main(["--root", str(data_root), "--snapshot-id", snap]) == 0

    bundle = _repo_root() / "policies" / "policy_bundle_v1.yaml"
    assert runner_main(["--demo", "--policy-bundle", str(bundle), "--snapshot-id", snap, "--if-exists", "noop"]) == EXIT_OK
    # Run again: must not fail and must not create a second dossier.
    assert runner_main(["--demo", "--policy-bundle", str(bundle), "--snapshot-id", snap, "--if-exists", "noop"]) == EXIT_OK

    dossiers_dir = art_root / "dossiers"
    runs = sorted([p for p in dossiers_dir.iterdir() if p.is_dir()])
    assert len(runs) == 1


def test_cost_policy_changes_metrics(tmp_path: Path, monkeypatch) -> None:
    data_root = tmp_path / "data"
    art_root = tmp_path / "artifacts"
    data_root.mkdir()
    art_root.mkdir()
    monkeypatch.setenv("EAM_DATA_ROOT", str(data_root))
    monkeypatch.setenv("EAM_ARTIFACT_ROOT", str(art_root))
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    snap = "demo_snap_001"
    assert demo_ingest_main(["--root", str(data_root), "--snapshot-id", snap]) == 0

    # Copy policies into tmp and modify cost bps to prove policy is read.
    pol_dir = tmp_path / "policies"
    pol_dir.mkdir()
    for p in (_repo_root() / "policies").glob("*.y*ml"):
        (pol_dir / p.name).write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
    bundle_path = pol_dir / "policy_bundle_v1.yaml"

    # Baseline run.
    assert runner_main(["--demo", "--policy-bundle", str(bundle_path), "--snapshot-id", snap]) == EXIT_OK
    d1 = sorted((art_root / "dossiers").iterdir())[0]
    m1 = json.loads((d1 / "metrics.json").read_text(encoding="utf-8"))

    # Modify cost_policy slippage, new run_id requires different runspec to avoid append-only noop.
    cost = pol_dir / "cost_policy_v1.yaml"
    txt = cost.read_text(encoding="utf-8").replace("slippage_bps: 2.0", "slippage_bps: 50.0")
    cost.write_text(txt, encoding="utf-8")

    # Different snapshot id -> different runspec -> different run_id.
    snap2 = "demo_snap_002"
    assert demo_ingest_main(["--root", str(data_root), "--snapshot-id", snap2]) == 0
    assert runner_main(["--demo", "--policy-bundle", str(bundle_path), "--snapshot-id", snap2]) == EXIT_OK
    runs = sorted([p for p in (art_root / "dossiers").iterdir() if p.is_dir()])
    assert len(runs) == 2
    d2 = runs[1]
    m2 = json.loads((d2 / "metrics.json").read_text(encoding="utf-8"))

    assert m1["total_return"] != m2["total_return"]


def test_lag_no_trade_on_first_day(tmp_path: Path, monkeypatch) -> None:
    data_root = tmp_path / "data"
    art_root = tmp_path / "artifacts"
    data_root.mkdir()
    art_root.mkdir()
    monkeypatch.setenv("EAM_DATA_ROOT", str(data_root))
    monkeypatch.setenv("EAM_ARTIFACT_ROOT", str(art_root))
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    snap = "demo_snap_001"
    assert demo_ingest_main(["--root", str(data_root), "--snapshot-id", snap]) == 0

    bundle = _repo_root() / "policies" / "policy_bundle_v1.yaml"
    assert runner_main(["--demo", "--policy-bundle", str(bundle), "--snapshot-id", snap]) == EXIT_OK

    d = sorted((art_root / "dossiers").iterdir())[0]
    trades = (d / "trades.csv").read_text(encoding="utf-8").splitlines()
    if len(trades) >= 2:
        header = trades[0].split(",")
        idx_entry = header.index("entry_dt")
        first_trade = trades[1].split(",")
        # With lag=1, entry should not be on the first bar day.
        assert "2024-01-01" not in first_trade[idx_entry]

