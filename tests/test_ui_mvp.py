from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from quant_eam.api.app import app
from quant_eam.compiler.compile import main as compiler_main
from quant_eam.data_lake.demo_ingest import main as demo_ingest_main
from quant_eam.gaterunner.run import main as gaterunner_main
from quant_eam.registry import cli as registry_cli
from quant_eam.runner.run import main as runner_main


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _build_demo_evidence(tmp_path: Path, monkeypatch) -> tuple[str, str]:
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

    snap = "demo_snap_ui_001"
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
    assert registry_cli.main(
        ["--registry-root", str(reg_root), "create-card", "--run-id", run_id, "--title", "buyhold_demo"]
    ) == 0

    card_id = f"card_{run_id}"
    return run_id, card_id


def test_readonly_api_and_ui_pages_200(tmp_path: Path, monkeypatch) -> None:
    run_id, card_id = _build_demo_evidence(tmp_path, monkeypatch)
    client = TestClient(app)

    r = client.get("/runs")
    assert r.status_code == 200
    assert any(x["run_id"] == run_id for x in r.json()["runs"])

    r = client.get(f"/runs/{run_id}")
    assert r.status_code == 200
    assert r.json()["run_id"] == run_id

    assert client.get(f"/runs/{run_id}/curve").status_code == 200
    assert client.get(f"/runs/{run_id}/trades").status_code == 200
    assert client.get(f"/runs/{run_id}/artifacts").status_code == 200

    r = client.get("/registry/cards")
    assert r.status_code == 200
    assert any(c["card_id"] == card_id for c in r.json()["cards"])

    r = client.get(f"/registry/cards/{card_id}")
    assert r.status_code == 200
    assert r.json()["card_id"] == card_id

    r = client.get("/ui")
    assert r.status_code == 200
    assert card_id in r.text
    assert run_id in r.text

    r = client.get(f"/ui/runs/{run_id}")
    assert r.status_code == 200
    assert run_id in r.text
    # Provenance linkage: run page must link to snapshot detail page (read-only).
    assert "/ui/snapshots/" in r.text
    # Phase-22: risk report rendered when present.
    assert "Risk" in r.text

    r = client.get(f"/ui/cards/{card_id}")
    assert r.status_code == 200
    assert card_id in r.text


def test_path_traversal_blocked() -> None:
    client = TestClient(app)
    r = client.get("/runs/../../etc/passwd")
    assert r.status_code in (400, 404)


def test_holdout_leak_not_rendered(tmp_path: Path, monkeypatch) -> None:
    run_id, _card_id = _build_demo_evidence(tmp_path, monkeypatch)
    client = TestClient(app)
    r = client.get(f"/ui/runs/{run_id}")
    assert r.status_code == 200
    # UI must not render holdout curve/trades artifacts.
    assert "holdout_curve" not in r.text
    assert "holdout_trades" not in r.text
