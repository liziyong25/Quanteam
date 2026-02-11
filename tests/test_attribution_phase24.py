from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from quant_eam.analysis.attribution_v1 import write_attribution_artifacts
from quant_eam.api.app import app
from quant_eam.compiler.compile import main as compiler_main
from quant_eam.contracts import validate as contracts_validate
from quant_eam.data_lake.demo_ingest import main as demo_ingest_main
from quant_eam.gaterunner.run import main as gaterunner_main
from quant_eam.registry import cli as registry_cli
from quant_eam.runner.run import main as runner_main


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _build_demo_evidence(tmp_path: Path, monkeypatch) -> tuple[Path, str, str]:
    data_root = tmp_path / "data"
    art_root = tmp_path / "artifacts"
    reg_root = tmp_path / "registry"
    data_root.mkdir()
    art_root.mkdir()
    reg_root.mkdir()

    monkeypatch.setenv("EAM_DATA_ROOT", str(data_root))
    monkeypatch.setenv("EAM_ARTIFACT_ROOT", str(art_root))
    monkeypatch.setenv("EAM_REGISTRY_ROOT", str(reg_root))
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    snap = "demo_snap_attr_001"
    assert demo_ingest_main(["--root", str(data_root), "--snapshot-id", snap]) == 0

    bp = _repo_root() / "contracts" / "examples" / "blueprint_buyhold_demo_ok.json"
    bundle = _repo_root() / "policies" / "policy_bundle_v1.yaml"
    runspec = tmp_path / "runspec.json"
    assert compiler_main(["--blueprint", str(bp), "--snapshot-id", snap, "--out", str(runspec), "--policy-bundle", str(bundle)]) == 0
    assert runner_main(["--runspec", str(runspec), "--policy-bundle", str(bundle)]) == 0

    dossiers_dir = art_root / "dossiers"
    d = sorted([p for p in dossiers_dir.iterdir() if p.is_dir()])[0]
    run_id = d.name

    assert gaterunner_main(["--dossier", str(d), "--policy-bundle", str(bundle)]) in (0, 2)
    assert registry_cli.main(["--registry-root", str(reg_root), "record-trial", "--dossier", str(d)]) == 0
    assert registry_cli.main(["--registry-root", str(reg_root), "create-card", "--run-id", run_id, "--title", "buyhold_demo"]) == 0

    card_id = f"card_{run_id}"
    return d, run_id, card_id


def test_phase24_attribution_artifacts_and_ui(tmp_path: Path, monkeypatch) -> None:
    dossier_dir, run_id, card_id = _build_demo_evidence(tmp_path, monkeypatch)

    # Generate deterministic attribution evidence into the dossier (append-only).
    written = write_attribution_artifacts(dossier_dir=dossier_dir)
    assert written, "expected attribution to write at least one artifact on first run"

    report_path = dossier_dir / "attribution_report.json"
    md_path = dossier_dir / "reports" / "attribution" / "report.md"
    assert report_path.is_file()
    assert md_path.is_file()

    # Contract validate (forced schema).
    schema = _repo_root() / "contracts" / "attribution_report_schema_v1.json"
    code, msg = contracts_validate.validate_json(report_path, schema_path=schema)
    assert code == contracts_validate.EXIT_OK, msg

    # Basic content sanity.
    rep = json.loads(report_path.read_text(encoding="utf-8"))
    assert rep["schema_version"] == "attribution_report_v1"
    assert "returns" in rep and "net_return" in rep["returns"]
    assert rep["evidence_refs"]["curve"] == "curve.csv"

    client = TestClient(app)

    r = client.get(f"/ui/runs/{run_id}")
    assert r.status_code == 200
    assert "Attribution" in r.text
    assert "attribution_report.json" in r.text

    r = client.get(f"/ui/cards/{card_id}")
    assert r.status_code == 200
    assert "Attribution" in r.text

