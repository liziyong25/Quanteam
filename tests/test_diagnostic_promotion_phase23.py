from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from quant_eam.api.app import app
from quant_eam.compiler.compile import main as compiler_main
from quant_eam.data_lake.demo_ingest import main as demo_ingest_main
from quant_eam.gaterunner.run import main as gaterunner_main
from quant_eam.runner.run import main as runner_main


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _build_demo_run(tmp_path: Path, monkeypatch) -> str:
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

    snapshot_id = "demo_snap_diag_phase23_001"
    assert demo_ingest_main(["--root", str(data_root), "--snapshot-id", snapshot_id]) == 0

    blueprint = _repo_root() / "contracts" / "examples" / "blueprint_buyhold_demo_ok.json"
    bundle = _repo_root() / "policies" / "policy_bundle_v1.yaml"
    runspec = tmp_path / "runspec_phase23.json"
    assert compiler_main(["--blueprint", str(blueprint), "--snapshot-id", snapshot_id, "--out", str(runspec), "--policy-bundle", str(bundle)]) == 0
    assert runner_main(["--runspec", str(runspec), "--policy-bundle", str(bundle)]) == 0

    dossiers_dir = art_root / "dossiers"
    dossier = sorted([p for p in dossiers_dir.iterdir() if p.is_dir()], key=lambda p: p.name)[0]
    assert gaterunner_main(["--dossier", str(dossier), "--policy-bundle", str(bundle)]) in (0, 2)
    return dossier.name


def test_phase23_diagnostic_promotion_api_and_ui(tmp_path: Path, monkeypatch) -> None:
    run_id = _build_demo_run(tmp_path, monkeypatch)
    client = TestClient(app)

    diagnostic_spec = {
        "schema_version": "diagnostic_spec_v1",
        "diagnostic_id": "diag_phase23_main",
        "run_id": run_id,
        "title": "Phase-23 Diagnostic",
        "objective": "Generate deterministic diagnostic report and promotion candidate gate spec.",
        "checks": [
            {
                "check_id": "max_drawdown_guard",
                "metric_key": "max_drawdown",
                "operator": "le",
                "threshold": 0.5,
                "severity": "error",
                "description": "max drawdown should remain in controlled range",
            },
            {
                "check_id": "sharpe_floor",
                "metric_key": "sharpe",
                "operator": "ge",
                "threshold": 0.1,
                "severity": "warn",
                "description": "warn when sharpe falls below baseline floor",
            },
        ],
        "artifacts": {
            "metrics_path": "metrics.json",
            "gate_results_path": "gate_results.json",
        },
    }

    r = client.post(f"/runs/{run_id}/diagnostics", json=diagnostic_spec)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["run_id"] == run_id
    assert body["diagnostic_id"] == "diag_phase23_main"
    assert isinstance(body.get("summary"), dict)

    diag_spec_path = Path(str(body["artifacts"]["diagnostic_spec_path"]))
    diag_report_path = Path(str(body["artifacts"]["diagnostic_report_path"]))
    gate_spec_path = Path(str(body["artifacts"]["promotion_gate_spec_path"]))
    assert diag_spec_path.is_file()
    assert diag_report_path.is_file()
    assert gate_spec_path.is_file()

    gate_spec = json.loads(gate_spec_path.read_text(encoding="utf-8"))
    assert gate_spec["schema_version"] == "gate_spec_v1"
    assert gate_spec["source_run_id"] == run_id
    assert gate_spec["source_diagnostic_id"] == "diag_phase23_main"
    assert isinstance(gate_spec.get("candidate_gates"), list)
    assert gate_spec["candidate_gates"], "promotion candidate must include at least one gate"
    assert all(isinstance(g.get("evidence_refs"), list) and g.get("evidence_refs") for g in gate_spec["candidate_gates"])

    # Deterministic re-run with identical spec should be accepted and stable.
    r2 = client.post(f"/runs/{run_id}/diagnostics", json=diagnostic_spec)
    assert r2.status_code == 200, r2.text
    assert r2.json()["diagnostic_id"] == "diag_phase23_main"

    r = client.get(f"/runs/{run_id}/diagnostics")
    assert r.status_code == 200
    rows = r.json().get("diagnostics") or []
    assert any(str(x.get("diagnostic_id")) == "diag_phase23_main" for x in rows)

    r = client.get(f"/runs/{run_id}/diagnostics/diag_phase23_main")
    assert r.status_code == 200
    detail = r.json()
    assert detail["run_id"] == run_id
    assert detail["diagnostic_id"] == "diag_phase23_main"
    assert detail["diagnostic_report"]["schema_version"] == "diagnostic_report_v1"
    assert detail["promotion_gate_spec"]["schema_version"] == "gate_spec_v1"

    ui = client.get(f"/ui/runs/{run_id}?diagnostic_id=diag_phase23_main")
    assert ui.status_code == 200
    assert "Diagnostics" in ui.text
    assert "diag_phase23_main" in ui.text
    assert "promotion_candidate/gate_spec.json" in ui.text
