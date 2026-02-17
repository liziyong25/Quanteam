from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

from quant_eam.api.app import app
from quant_eam.compiler.compile import main as compiler_main
from quant_eam.data_lake.demo_ingest import main as demo_ingest_main
from quant_eam.gaterunner.run import main as gaterunner_main
from quant_eam.registry import cli as registry_cli
from quant_eam.registry.storage import registry_paths
from quant_eam.runner.run import main as runner_main


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _make_card(tmp_path: Path, *, snap: str, title: str, monkeypatch) -> str:
    data_root = Path(os.environ["EAM_DATA_ROOT"])
    art_root = Path(os.environ["EAM_ARTIFACT_ROOT"])
    reg_root = Path(os.environ["EAM_REGISTRY_ROOT"])

    assert demo_ingest_main(["--root", str(data_root), "--snapshot-id", snap]) == 0
    bp = _repo_root() / "contracts" / "examples" / "blueprint_buyhold_demo_ok.json"
    bundle = _repo_root() / "policies" / "policy_bundle_v1.yaml"
    runspec = tmp_path / f"runspec_{snap}.json"
    assert compiler_main(["--blueprint", str(bp), "--snapshot-id", snap, "--out", str(runspec), "--policy-bundle", str(bundle)]) == 0
    assert runner_main(["--runspec", str(runspec), "--policy-bundle", str(bundle)]) == 0

    dossiers = sorted([p for p in (art_root / "dossiers").iterdir() if p.is_dir()])
    dossier = None
    for d in dossiers:
        cfg = json.loads((d / "config_snapshot.json").read_text(encoding="utf-8"))
        rs = cfg.get("runspec", {}) if isinstance(cfg, dict) else {}
        if isinstance(rs, dict) and str(rs.get("data_snapshot_id")) == snap:
            dossier = d
            break
    assert dossier is not None
    assert gaterunner_main(["--dossier", str(dossier), "--policy-bundle", str(bundle)]) in (0, 2)

    assert registry_cli.main(["--registry-root", str(reg_root), "record-trial", "--dossier", str(dossier)]) == 0
    lines = [ln for ln in registry_paths(reg_root).trial_log.read_text(encoding="utf-8").splitlines() if ln.strip()]
    ev = json.loads(lines[-1])
    run_id = str(ev["run_id"])
    assert bool(ev["overall_pass"]), "component run must pass gates before card creation"
    assert registry_cli.main(["--registry-root", str(reg_root), "create-card", "--run-id", run_id, "--title", title]) == 0
    return f"card_{run_id}"


def test_phase24_ui_composer_flow(tmp_path: Path, monkeypatch) -> None:
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

    c1 = _make_card(tmp_path, snap="demo_snap_comp_ui_001", title="phase24_c1", monkeypatch=monkeypatch)
    c2 = _make_card(tmp_path, snap="demo_snap_comp_ui_002", title="phase24_c2", monkeypatch=monkeypatch)
    bundle = _repo_root() / "policies" / "policy_bundle_curve_composer_v1.yaml"

    client = TestClient(app)

    r = client.get("/ui/composer")
    assert r.status_code == 200
    assert c1 in r.text
    assert c2 in r.text
    assert "Compose Run" in r.text

    form = {
        "title": "phase24_ui_composed",
        "policy_bundle_path": str(bundle),
        "register_card": "true",
        "card_ids": [c1, c2],
        "weights": ["0.5", "0.5"],
    }
    r = client.post("/ui/composer/compose", data=form, follow_redirects=False)
    assert r.status_code == 303, r.text
    loc = str(r.headers.get("location") or "")
    assert loc.startswith("/ui/runs/")
    run_id = loc.rsplit("/", 1)[-1]

    dossier_dir = art_root / "dossiers" / run_id
    assert dossier_dir.is_dir()
    assert (dossier_dir / "dossier_manifest.json").is_file()
    assert (dossier_dir / "gate_results.json").is_file()

    trials = [ln for ln in (reg_root / "trial_log.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert any(str(json.loads(ln).get("run_id")) == run_id for ln in trials)
    assert (reg_root / "cards" / f"card_{run_id}" / "card_v1.json").is_file()

    rr = client.get(loc)
    assert rr.status_code == 200
    assert f"Run {run_id}" in rr.text
