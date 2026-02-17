from __future__ import annotations

import json
from pathlib import Path

from quant_eam.compiler.compile import main as compiler_main
from quant_eam.data_lake.demo_ingest import main as demo_ingest_main
from quant_eam.gaterunner.run import main as gaterunner_main
from quant_eam.runner.run import main as runner_main


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _copy_policies_with_overrides(*, dst: Path, max_positions: int | None = None, max_turnover: float | None = None) -> Path:
    dst.mkdir(parents=True, exist_ok=True)
    for p in (_repo_root() / "policies").glob("*.y*ml"):
        txt = p.read_text(encoding="utf-8")
        if p.name == "risk_policy_v1.yaml":
            if max_positions is not None:
                txt = txt.replace("max_positions: 20", f"max_positions: {int(max_positions)}")
            if max_turnover is not None:
                txt = txt.replace("max_turnover: 1.0", f"max_turnover: {float(max_turnover)}")
        (dst / p.name).write_text(txt, encoding="utf-8")
    return dst / "policy_bundle_v1.yaml"


def _build_run(tmp_path: Path, monkeypatch, *, bundle: Path) -> Path:
    data_root = tmp_path / "data"
    art_root = tmp_path / "artifacts"
    data_root.mkdir()
    art_root.mkdir()

    monkeypatch.setenv("EAM_DATA_ROOT", str(data_root))
    monkeypatch.setenv("EAM_ARTIFACT_ROOT", str(art_root))
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    snap = "demo_snap_phase22_001"
    assert demo_ingest_main(["--root", str(data_root), "--snapshot-id", snap]) == 0

    bp = _repo_root() / "contracts" / "examples" / "blueprint_buyhold_demo_ok.json"
    runspec = tmp_path / "runspec.json"
    assert compiler_main(["--blueprint", str(bp), "--snapshot-id", snap, "--out", str(runspec), "--policy-bundle", str(bundle)]) == 0
    assert runner_main(["--runspec", str(runspec), "--policy-bundle", str(bundle)]) == 0

    d = sorted([p for p in (art_root / "dossiers").iterdir() if p.is_dir()])[0]
    return d


def test_risk_gate_fails_on_max_positions_violation_and_writes_risk_report(tmp_path: Path, monkeypatch) -> None:
    pol_dir = tmp_path / "policies"
    bundle = _copy_policies_with_overrides(dst=pol_dir, max_positions=1)
    dossier = _build_run(tmp_path, monkeypatch, bundle=bundle)

    assert gaterunner_main(["--dossier", str(dossier), "--policy-bundle", str(bundle)]) in (0, 2)

    rr = dossier / "risk_report.json"
    assert rr.is_file()
    doc = json.loads(rr.read_text(encoding="utf-8"))
    assert doc["schema_version"] == "risk_report_v1"
    assert int(doc["max_observed"]["max_positions_observed"]) >= 2
    assert int(doc["violation_count_by_rule"]["max_positions"]) > 0

    gr = json.loads((dossier / "gate_results.json").read_text(encoding="utf-8"))
    rows = [r for r in gr.get("results", []) if isinstance(r, dict) and r.get("gate_id") == "risk_policy_compliance_v1"]
    assert rows, "missing risk_policy_compliance_v1 in gate_results"
    assert rows[0].get("pass") is False


def test_risk_gate_fails_on_max_turnover_violation(tmp_path: Path, monkeypatch) -> None:
    pol_dir = tmp_path / "policies"
    bundle = _copy_policies_with_overrides(dst=pol_dir, max_turnover=0.5)
    dossier = _build_run(tmp_path, monkeypatch, bundle=bundle)

    assert gaterunner_main(["--dossier", str(dossier), "--policy-bundle", str(bundle)]) in (0, 2)
    doc = json.loads((dossier / "risk_report.json").read_text(encoding="utf-8"))
    assert float(doc["max_observed"]["max_turnover_observed"]) > 0.5
    assert int(doc["violation_count_by_rule"]["max_turnover"]) > 0

