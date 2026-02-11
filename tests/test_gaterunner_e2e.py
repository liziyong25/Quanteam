from __future__ import annotations

import hashlib
import json
from pathlib import Path

from quant_eam.compiler.compile import EXIT_OK as COMPILER_OK, main as compiler_main
from quant_eam.contracts import validate as contracts_validate
from quant_eam.data_lake.demo_ingest import main as demo_ingest_main
from quant_eam.gaterunner.run import EXIT_OK as GATE_OK, main as gaterunner_main
from quant_eam.runner.run import EXIT_OK as RUNNER_OK, main as runner_main


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def test_e2e_compile_run_gates_and_contract_valid_gate_results(tmp_path: Path, monkeypatch) -> None:
    data_root = tmp_path / "data"
    art_root = tmp_path / "artifacts"
    data_root.mkdir()
    art_root.mkdir()

    monkeypatch.setenv("EAM_DATA_ROOT", str(data_root))
    monkeypatch.setenv("EAM_ARTIFACT_ROOT", str(art_root))
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    snap = "demo_snap_gate_e2e_001"
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
    assert runner_main(["--runspec", str(out), "--policy-bundle", str(bundle)]) == RUNNER_OK

    dossiers_dir = art_root / "dossiers"
    runs = sorted([p for p in dossiers_dir.iterdir() if p.is_dir()])
    assert runs, "no dossier written"
    d = runs[0]

    # Run gates -> gate_results.json must be produced and contract-valid.
    assert gaterunner_main(["--dossier", str(d), "--policy-bundle", str(bundle)]) in (GATE_OK, 2)
    gate_results = d / "gate_results.json"
    assert gate_results.is_file()

    code, msg = contracts_validate.validate_json(gate_results)
    assert code == contracts_validate.EXIT_OK, msg

    doc = json.loads(gate_results.read_text(encoding="utf-8"))
    assert doc["schema_version"] in ("gate_results_v2", "gate_results_v1")
    assert "overall_pass" in doc
    assert isinstance(doc["results"], list) and doc["results"]


def test_gate_results_append_only_noop(tmp_path: Path, monkeypatch) -> None:
    data_root = tmp_path / "data"
    art_root = tmp_path / "artifacts"
    data_root.mkdir()
    art_root.mkdir()

    monkeypatch.setenv("EAM_DATA_ROOT", str(data_root))
    monkeypatch.setenv("EAM_ARTIFACT_ROOT", str(art_root))
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    snap = "demo_snap_gate_e2e_002"
    assert demo_ingest_main(["--root", str(data_root), "--snapshot-id", snap]) == 0

    bp = _repo_root() / "contracts" / "examples" / "blueprint_buyhold_demo_ok.json"
    bundle = _repo_root() / "policies" / "policy_bundle_v1.yaml"
    out = tmp_path / "runspec.json"
    assert compiler_main(["--blueprint", str(bp), "--snapshot-id", snap, "--out", str(out), "--policy-bundle", str(bundle)]) == COMPILER_OK
    assert runner_main(["--runspec", str(out), "--policy-bundle", str(bundle)]) == RUNNER_OK

    d = sorted([p for p in (art_root / "dossiers").iterdir() if p.is_dir()])[0]
    assert gaterunner_main(["--dossier", str(d), "--policy-bundle", str(bundle)]) in (GATE_OK, 2)
    p = d / "gate_results.json"
    h1 = _sha256_file(p)

    # Run again: must be noop and not modify gate_results.json.
    assert gaterunner_main(["--dossier", str(d), "--policy-bundle", str(bundle)]) == GATE_OK
    h2 = _sha256_file(p)
    assert h1 == h2


def test_holdout_output_is_minimal_and_no_holdout_artifacts_written(tmp_path: Path, monkeypatch) -> None:
    data_root = tmp_path / "data"
    art_root = tmp_path / "artifacts"
    data_root.mkdir()
    art_root.mkdir()

    monkeypatch.setenv("EAM_DATA_ROOT", str(data_root))
    monkeypatch.setenv("EAM_ARTIFACT_ROOT", str(art_root))
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    snap = "demo_snap_gate_e2e_003"
    assert demo_ingest_main(["--root", str(data_root), "--snapshot-id", snap]) == 0

    bp = _repo_root() / "contracts" / "examples" / "blueprint_buyhold_demo_ok.json"
    bundle = _repo_root() / "policies" / "policy_bundle_v1.yaml"
    out = tmp_path / "runspec.json"
    assert compiler_main(["--blueprint", str(bp), "--snapshot-id", snap, "--out", str(out), "--policy-bundle", str(bundle)]) == COMPILER_OK
    assert runner_main(["--runspec", str(out), "--policy-bundle", str(bundle)]) == RUNNER_OK

    d = sorted([p for p in (art_root / "dossiers").iterdir() if p.is_dir()])[0]
    assert gaterunner_main(["--dossier", str(d), "--policy-bundle", str(bundle)]) in (GATE_OK, 2)

    gr = json.loads((d / "gate_results.json").read_text(encoding="utf-8"))
    # Runner/compiler always include a holdout segment in the MVP RunSpec.
    assert "holdout_summary" in gr
    assert set(gr["holdout_summary"].keys()) >= {"pass", "summary"}
    # No holdout curves/trades must exist in dossier dir.
    bad = sorted([p.name for p in d.iterdir() if p.is_file() and p.name.startswith("holdout_")])
    assert not bad, bad


def test_gate_cost_x2_does_not_modify_policy_files(tmp_path: Path, monkeypatch) -> None:
    data_root = tmp_path / "data"
    art_root = tmp_path / "artifacts"
    data_root.mkdir()
    art_root.mkdir()

    monkeypatch.setenv("EAM_DATA_ROOT", str(data_root))
    monkeypatch.setenv("EAM_ARTIFACT_ROOT", str(art_root))
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    # Copy policies into tmp to detect accidental writes.
    pol_dir = tmp_path / "policies"
    pol_dir.mkdir()
    for p in (_repo_root() / "policies").glob("*.y*ml"):
        (pol_dir / p.name).write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
    bundle = pol_dir / "policy_bundle_v1.yaml"

    cost = pol_dir / "cost_policy_v1.yaml"
    before = _sha256_file(cost)

    snap = "demo_snap_gate_e2e_004"
    assert demo_ingest_main(["--root", str(data_root), "--snapshot-id", snap]) == 0

    bp = _repo_root() / "contracts" / "examples" / "blueprint_buyhold_demo_ok.json"
    out = tmp_path / "runspec.json"
    assert compiler_main(["--blueprint", str(bp), "--snapshot-id", snap, "--out", str(out), "--policy-bundle", str(bundle)]) == COMPILER_OK
    assert runner_main(["--runspec", str(out), "--policy-bundle", str(bundle)]) == RUNNER_OK

    d = sorted([p for p in (art_root / "dossiers").iterdir() if p.is_dir()])[0]
    assert gaterunner_main(["--dossier", str(d), "--policy-bundle", str(bundle)]) in (GATE_OK, 2)

    after = _sha256_file(cost)
    assert before == after
