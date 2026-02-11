from __future__ import annotations

import json
from pathlib import Path

from quant_eam.compiler.compile import EXIT_OK as COMPILER_OK, main as compiler_main
from quant_eam.contracts import validate as contracts_validate
from quant_eam.data_lake.demo_ingest import main as demo_ingest_main
from quant_eam.runner.run import EXIT_OK as RUNNER_OK, main as runner_main


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_e2e_compile_to_runner_to_contract_valid_dossier(tmp_path: Path, monkeypatch) -> None:
    data_root = tmp_path / "data"
    art_root = tmp_path / "artifacts"
    data_root.mkdir()
    art_root.mkdir()

    monkeypatch.setenv("EAM_DATA_ROOT", str(data_root))
    monkeypatch.setenv("EAM_ARTIFACT_ROOT", str(art_root))
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    snap = "demo_snap_e2e_001"
    assert demo_ingest_main(["--root", str(data_root), "--snapshot-id", snap]) == 0

    bp = _repo_root() / "contracts" / "examples" / "blueprint_buyhold_demo_ok.json"
    bundle = _repo_root() / "policies" / "policy_bundle_v1.yaml"
    out = tmp_path / "runspec.json"

    assert (
        compiler_main(
            [
                "--blueprint",
                str(bp),
                "--snapshot-id",
                snap,
                "--out",
                str(out),
                "--policy-bundle",
                str(bundle),
                "--check-availability",
            ]
        )
        == COMPILER_OK
    )

    # Run.
    assert runner_main(["--runspec", str(out), "--policy-bundle", str(bundle)]) == RUNNER_OK

    dossiers_dir = art_root / "dossiers"
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

    code, msg = contracts_validate.validate_json(d / "dossier_manifest.json")
    assert code == contracts_validate.EXIT_OK, msg

