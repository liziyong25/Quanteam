from __future__ import annotations

import json
import subprocess
from pathlib import Path

from quant_eam.compiler.compile import main as compiler_main
from quant_eam.data_lake.demo_ingest import main as demo_ingest_main
from quant_eam.gates.holdout_leak_guard import run_holdout_leak_guard_v1
from quant_eam.gates.types import GateContext
from quant_eam.gaterunner.run import main as gaterunner_main
from quant_eam.runner.run import main as runner_main


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def test_phase27_holdout_leak_guard_detects_numeric_holdout_leak(tmp_path: Path, monkeypatch) -> None:
    art_root = tmp_path / "artifacts"
    job_root = tmp_path / "jobs"
    art_root.mkdir()
    job_root.mkdir()

    # Create a sweep leaderboard that leaks a numeric holdout metric.
    j = job_root / "job_001" / "outputs" / "sweep"
    j.mkdir(parents=True)
    (j / "leaderboard.json").write_text(
        json.dumps({"best": {"holdout_sharpe": 1.23, "holdout_pass": True}}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    dossier_dir = art_root / "dossiers" / "run_001"
    dossier_dir.mkdir(parents=True)
    config_snapshot = {"env": {"EAM_ARTIFACT_ROOT": str(art_root), "EAM_JOB_ROOT": str(job_root)}}

    # Minimal context (other fields are irrelevant for this gate).
    ctx = GateContext(
        dossier_dir=dossier_dir,
        policies_dir=tmp_path,
        policy_bundle={},
        execution_policy={},
        cost_policy={},
        asof_latency_policy={},
        risk_policy=None,
        gate_suite={},
        runspec={},
        dossier_manifest={},
        config_snapshot=config_snapshot,
        metrics={},
    )

    gr = run_holdout_leak_guard_v1(ctx, params={})
    assert gr.passed is False
    assert "error" not in gr.metrics  # leak => FAIL, not INVALID
    assert int(gr.metrics.get("leak_count") or 0) >= 1


def test_phase27_holdout_leak_guard_allows_pass_fail_only(tmp_path: Path, monkeypatch) -> None:
    art_root = tmp_path / "artifacts"
    job_root = tmp_path / "jobs"
    art_root.mkdir()
    job_root.mkdir()

    j = job_root / "job_001" / "outputs" / "sweep"
    j.mkdir(parents=True)
    (j / "leaderboard.json").write_text(
        json.dumps({"best": {"holdout_pass": True, "holdout_summary": "pass"}}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    dossier_dir = art_root / "dossiers" / "run_001"
    dossier_dir.mkdir(parents=True)
    config_snapshot = {"env": {"EAM_ARTIFACT_ROOT": str(art_root), "EAM_JOB_ROOT": str(job_root)}}
    ctx = GateContext(
        dossier_dir=dossier_dir,
        policies_dir=tmp_path,
        policy_bundle={},
        execution_policy={},
        cost_policy={},
        asof_latency_policy={},
        risk_policy=None,
        gate_suite={},
        runspec={},
        dossier_manifest={},
        config_snapshot=config_snapshot,
        metrics={},
    )

    gr = run_holdout_leak_guard_v1(ctx, params={})
    assert gr.passed is True
    assert int(gr.metrics.get("leak_count") or 0) == 0


def test_phase27_risk_evidence_artifacts_written_and_used_by_gate(tmp_path: Path, monkeypatch) -> None:
    data_root = tmp_path / "data"
    art_root = tmp_path / "artifacts"
    data_root.mkdir()
    art_root.mkdir()
    monkeypatch.setenv("EAM_DATA_ROOT", str(data_root))
    monkeypatch.setenv("EAM_ARTIFACT_ROOT", str(art_root))
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    snap = "snap_phase27_001"
    assert demo_ingest_main(["--root", str(data_root), "--snapshot-id", snap]) == 0

    bp = _repo_root() / "contracts" / "examples" / "blueprint_buyhold_demo_ok.json"
    bundle = _repo_root() / "policies" / "policy_bundle_v1.yaml"
    runspec_path = tmp_path / "runspec.json"
    assert (
        compiler_main(
            [
                "--blueprint",
                str(bp),
                "--snapshot-id",
                snap,
                "--out",
                str(runspec_path),
                "--policy-bundle",
                str(bundle),
            ]
        )
        == 0
    )

    assert runner_main(["--runspec", str(runspec_path), "--policy-bundle", str(bundle)]) == 0

    dossiers_dir = art_root / "dossiers"
    run_dirs = sorted([p for p in dossiers_dir.iterdir() if p.is_dir()])
    assert run_dirs, "no dossier written"
    d = run_dirs[0]

    # Risk evidence artifacts must exist (append-only).
    assert (d / "positions.csv").is_file()
    assert (d / "turnover.csv").is_file()
    assert (d / "exposure.json").is_file()

    # Run gates using a bundle that includes the holdout guard (risk gate is mandatory).
    bundle2 = _repo_root() / "policies" / "policy_bundle_v2_holdout_guard.yaml"
    assert gaterunner_main(["--dossier", str(d), "--policy-bundle", str(bundle2)]) in (0, 2)

    # risk_report.json must reference the new evidence artifacts.
    rr = _load_json(d / "risk_report.json")
    computed = rr.get("computed_from") if isinstance(rr.get("computed_from"), dict) else {}
    assert computed.get("positions") == "positions.csv"
    assert computed.get("turnover") == "turnover.csv"
    assert computed.get("exposure") == "exposure.json"


def test_phase27_lint_scope_check_script_and_ci_hook() -> None:
    repo = _repo_root()
    r = subprocess.run(["python3", "scripts/check_lint_scope.py"], cwd=repo, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    ci = (repo / "scripts/ci_local.sh").read_text(encoding="utf-8")
    assert "check_lint_scope.py" in ci
