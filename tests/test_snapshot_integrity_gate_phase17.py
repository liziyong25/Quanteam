from __future__ import annotations

import json
from pathlib import Path

from quant_eam.compiler.compile import EXIT_OK as COMPILER_OK, main as compiler_main
from quant_eam.gaterunner.run import main as gaterunner_main
from quant_eam.ingest.wequant_ohlcv import main as ingest_main
from quant_eam.policies.load import load_yaml
from quant_eam.runner.run import EXIT_OK as RUNNER_OK, main as runner_main


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_bundle_id(bundle_path: Path) -> str:
    doc = load_yaml(bundle_path)
    assert isinstance(doc, dict)
    bid = str(doc.get("policy_bundle_id") or "").strip()
    assert bid
    return bid


def _write_blueprint_with_bundle(tmp_path: Path, *, bundle_id: str) -> Path:
    bp_src = _repo_root() / "contracts" / "examples" / "blueprint_buyhold_demo_ok.json"
    bp = json.loads(bp_src.read_text(encoding="utf-8"))
    assert isinstance(bp, dict)
    bp["policy_bundle_id"] = bundle_id
    out = tmp_path / "blueprint.json"
    out.write_text(json.dumps(bp, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


def _tamper_csv(path: Path) -> None:
    # Deterministic single-byte change: replace the first occurrence of "100" with "101".
    txt = path.read_text(encoding="utf-8")
    if "100" in txt:
        path.write_text(txt.replace("100", "101", 1), encoding="utf-8")
    else:
        # Fallback: append a harmless space to the last line to change sha.
        path.write_text(txt.rstrip("\n") + " \n", encoding="utf-8")


def test_phase17_data_snapshot_integrity_gate_pass_e2e(tmp_path: Path, monkeypatch) -> None:
    data_root = tmp_path / "data"
    art_root = tmp_path / "artifacts"
    data_root.mkdir()
    art_root.mkdir()

    monkeypatch.setenv("EAM_DATA_ROOT", str(data_root))
    monkeypatch.setenv("EAM_ARTIFACT_ROOT", str(art_root))
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    snap = "snap_gate_ok_001"
    assert (
        ingest_main(
            [
                "--provider",
                "mock",
                "--root",
                str(data_root),
                "--snapshot-id",
                snap,
                "--symbols",
                "AAA,BBB",
                "--start",
                "2024-01-01",
                "--end",
                "2024-01-10",
            ]
        )
        == 0
    )

    bundle = _repo_root() / "policies" / "policy_bundle_v2_snapshot_integrity.yaml"
    bundle_id = _load_bundle_id(bundle)
    bp = _write_blueprint_with_bundle(tmp_path, bundle_id=bundle_id)

    runspec_out = tmp_path / "runspec.json"
    assert (
        compiler_main(
            [
                "--blueprint",
                str(bp),
                "--snapshot-id",
                snap,
                "--out",
                str(runspec_out),
                "--policy-bundle",
                str(bundle),
                "--check-availability",
            ]
        )
        == COMPILER_OK
    )
    assert runner_main(["--runspec", str(runspec_out), "--policy-bundle", str(bundle)]) == RUNNER_OK

    dossiers_dir = art_root / "dossiers"
    d = sorted([p for p in dossiers_dir.iterdir() if p.is_dir()])[0]

    # GateRunner must include the integrity gate and it must PASS.
    code = gaterunner_main(["--dossier", str(d), "--policy-bundle", str(bundle)])
    assert code in (0, 2)
    gr = json.loads((d / "gate_results.json").read_text(encoding="utf-8"))
    results = gr.get("results")
    assert isinstance(results, list)
    r = [x for x in results if isinstance(x, dict) and x.get("gate_id") == "data_snapshot_integrity_v1"]
    assert r, "missing data_snapshot_integrity_v1 gate result"
    assert bool(r[0].get("pass")) is True, r[0]


def test_phase17_data_snapshot_integrity_gate_detects_tamper(tmp_path: Path, monkeypatch) -> None:
    data_root = tmp_path / "data"
    art_root = tmp_path / "artifacts"
    data_root.mkdir()
    art_root.mkdir()

    monkeypatch.setenv("EAM_DATA_ROOT", str(data_root))
    monkeypatch.setenv("EAM_ARTIFACT_ROOT", str(art_root))
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    snap = "snap_gate_tamper_001"
    assert (
        ingest_main(
            [
                "--provider",
                "mock",
                "--root",
                str(data_root),
                "--snapshot-id",
                snap,
                "--symbols",
                "AAA,BBB",
                "--start",
                "2024-01-01",
                "--end",
                "2024-01-10",
            ]
        )
        == 0
    )

    # Tamper the written dataset without updating manifests.
    csv_path = data_root / "lake" / snap / "ohlcv_1d.csv"
    assert csv_path.is_file()
    _tamper_csv(csv_path)

    bundle = _repo_root() / "policies" / "policy_bundle_v2_snapshot_integrity.yaml"
    bundle_id = _load_bundle_id(bundle)
    bp = _write_blueprint_with_bundle(tmp_path, bundle_id=bundle_id)
    runspec_out = tmp_path / "runspec.json"

    assert compiler_main(["--blueprint", str(bp), "--snapshot-id", snap, "--out", str(runspec_out), "--policy-bundle", str(bundle)]) == COMPILER_OK
    assert runner_main(["--runspec", str(runspec_out), "--policy-bundle", str(bundle)]) == RUNNER_OK

    d = sorted([p for p in (art_root / "dossiers").iterdir() if p.is_dir()])[0]
    code = gaterunner_main(["--dossier", str(d), "--policy-bundle", str(bundle)])
    assert code == 2, "tamper must be treated as INVALID (exit=2)"
    gr = json.loads((d / "gate_results.json").read_text(encoding="utf-8"))
    results = gr.get("results")
    assert isinstance(results, list)
    r = [x for x in results if isinstance(x, dict) and x.get("gate_id") == "data_snapshot_integrity_v1"]
    assert r, "missing data_snapshot_integrity_v1 gate result"
    assert bool(r[0].get("pass")) is False
    metrics = r[0].get("metrics") if isinstance(r[0].get("metrics"), dict) else {}
    assert any("sha256 mismatch" in str(e) for e in (metrics.get("errors") or []))

