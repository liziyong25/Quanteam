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


def _build_demo_run_with_gates(tmp_path: Path, monkeypatch) -> tuple[str, Path]:
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

    snap = "demo_ui_gate_detail_001"
    assert demo_ingest_main(["--root", str(data_root), "--snapshot-id", snap]) == 0

    bp = _repo_root() / "contracts" / "examples" / "blueprint_buyhold_demo_ok.json"
    bundle = _repo_root() / "policies" / "policy_bundle_v1.yaml"
    runspec = tmp_path / "runspec.json"

    assert compiler_main(["--blueprint", str(bp), "--snapshot-id", snap, "--out", str(runspec), "--policy-bundle", str(bundle)]) == 0
    assert runner_main(["--runspec", str(runspec), "--policy-bundle", str(bundle)]) == 0

    dossiers_dir = art_root / "dossiers"
    dossier = sorted([p for p in dossiers_dir.iterdir() if p.is_dir()])[0]
    run_id = dossier.name

    assert gaterunner_main(["--dossier", str(dossier), "--policy-bundle", str(bundle)]) in (0, 2)
    return run_id, art_root


def test_run_gate_detail_readonly_page_renders_gate_evidence(tmp_path: Path, monkeypatch) -> None:
    run_id, _art_root = _build_demo_run_with_gates(tmp_path, monkeypatch)
    client = TestClient(app)

    url = f"/ui/runs/{run_id}/gates"
    r = client.get(url)
    assert r.status_code == 200
    text = r.text

    assert f"Run {run_id} Gates" in text
    assert "read-only" in text.lower()
    assert "no write actions" in text.lower()
    assert f"dossiers/{run_id}/gate_results.json" in text

    assert "basic_sanity" in text
    assert "determinism_guard" in text
    assert "risk_policy_compliance_v1" in text
    assert "<th>thresholds</th>" in text.lower()
    assert "<th>evidence refs</th>" in text.lower()
    assert "config_snapshot.json" in text

    assert "<form" not in text.lower()
    assert "method=\"post\"" not in text.lower()

    assert client.head(url).status_code == 200
    assert client.post(url).status_code == 405


def test_run_gate_detail_holdout_summary_stays_minimal(tmp_path: Path, monkeypatch) -> None:
    art_root = tmp_path / "artifacts"
    run_id = "demo_holdout_001"
    dossier = art_root / "dossiers" / run_id
    dossier.mkdir(parents=True)
    gate_results = {
        "schema_version": "gate_results_v1",
        "run_id": run_id,
        "gate_suite_id": "gate_suite_v1_default",
        "overall_pass": True,
        "results": [
            {
                "gate_id": "gate_holdout_passfail_v1",
                "gate_version": "v1",
                "pass": True,
                "status": "pass",
                "evidence": {"artifacts": ["config_snapshot.json"], "notes": "holdout minimal"},
            }
        ],
        "holdout_summary": {
            "pass": True,
            "summary": "holdout evaluated (minimal output)",
            "metrics_minimal": {"total_return": 0.01, "trade_count": 2},
        },
    }
    (dossier / "gate_results.json").write_text(json.dumps(gate_results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    monkeypatch.setenv("EAM_ARTIFACT_ROOT", str(art_root))

    client = TestClient(app)
    r = client.get(f"/ui/runs/{run_id}/gates")
    assert r.status_code == 200
    text = r.text
    assert "Holdout (Minimal Summary)" in text
    assert "holdout evaluated (minimal output)" in text
    assert "metrics_minimal" not in text
    assert "trade_count" not in text


def test_run_gate_detail_degrades_without_gate_results(tmp_path: Path, monkeypatch) -> None:
    art_root = tmp_path / "artifacts"
    run_id = "demo_no_gates_001"
    (art_root / "dossiers" / run_id).mkdir(parents=True)
    monkeypatch.setenv("EAM_ARTIFACT_ROOT", str(art_root))

    client = TestClient(app)
    r = client.get(f"/ui/runs/{run_id}/gates")
    assert r.status_code == 200
    assert "No <code>gate_results.json</code> found for this run." in r.text
    assert "Holdout (Minimal Summary)" not in r.text


def test_run_gate_detail_rejects_invalid_or_missing_run() -> None:
    client = TestClient(app)
    assert client.get("/ui/runs/not_existing_run/gates").status_code == 404
    assert client.get("/ui/runs/../../etc/passwd/gates").status_code in (400, 404)
