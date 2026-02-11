from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from quant_eam.compiler.compile import EXIT_OK as COMPILER_OK, main as compiler_main
from quant_eam.contracts import validate as contracts_validate
from quant_eam.data_lake.demo_ingest import main as demo_ingest_main
from quant_eam.gaterunner.run import main as gaterunner_main
from quant_eam.registry import cli as registry_cli
from quant_eam.registry.storage import registry_paths
from quant_eam.runner.run import EXIT_OK as RUNNER_OK, main as runner_main

from quant_eam.composer.run import EXIT_OK as COMPOSER_OK, EXIT_INVALID as COMPOSER_INVALID, run_once as composer_run_once


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _make_card(tmp_path: Path, *, snap: str, title: str, monkeypatch) -> str:
    data_root = Path(os.environ["EAM_DATA_ROOT"])
    art_root = Path(os.environ["EAM_ARTIFACT_ROOT"])
    reg_root = Path(os.environ["EAM_REGISTRY_ROOT"])

    assert demo_ingest_main(["--root", str(data_root), "--snapshot-id", snap]) == 0

    bp = _repo_root() / "contracts" / "examples" / "blueprint_buyhold_demo_ok.json"
    bundle = _repo_root() / "policies" / "policy_bundle_v1.yaml"
    runspec = tmp_path / f"runspec_{snap}.json"
    assert (
        compiler_main(["--blueprint", str(bp), "--snapshot-id", snap, "--out", str(runspec), "--policy-bundle", str(bundle)])
        == COMPILER_OK
    )
    assert runner_main(["--runspec", str(runspec), "--policy-bundle", str(bundle)]) == RUNNER_OK

    # Find the dossier by evidence (snapshot_id), not by name sort.
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

    # Record trial then create card.
    assert registry_cli.main(["--registry-root", str(reg_root), "record-trial", "--dossier", str(dossier)]) == 0
    # Find run_id from trial log line.
    lines = [ln for ln in registry_paths(reg_root).trial_log.read_text(encoding="utf-8").splitlines() if ln.strip()]
    ev = json.loads(lines[-1])
    run_id = str(ev["run_id"])
    assert bool(ev["overall_pass"]), "component run must be Gate PASS to create a card"
    assert (
        registry_cli.main(["--registry-root", str(reg_root), "create-card", "--run-id", run_id, "--title", title])
        == 0
    )
    return f"card_{run_id}"


def test_e2e_compose_two_cards_and_register_new_card(tmp_path: Path, monkeypatch) -> None:
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

    c1 = _make_card(tmp_path, snap="demo_snap_comp_card_001", title="c1", monkeypatch=monkeypatch)
    c2 = _make_card(tmp_path, snap="demo_snap_comp_card_002", title="c2", monkeypatch=monkeypatch)

    bundle = _repo_root() / "policies" / "policy_bundle_curve_composer_v1.yaml"
    code, out = composer_run_once(
        card_ids=[c1, c2],
        weights=[0.5, 0.5],
        policy_bundle_path=bundle,
        register_card=True,
        title="composed_demo",
    )
    assert code == COMPOSER_OK, out
    run_id = str(out["run_id"])
    dossier_dir = Path(out["dossier_path"])
    assert dossier_dir.is_dir()
    assert (dossier_dir / "components.json").is_file()
    assert (dossier_dir / "gate_results.json").is_file()
    assert contracts_validate.main([str(dossier_dir / "gate_results.json")]) == contracts_validate.EXIT_OK

    comps = json.loads((dossier_dir / "components.json").read_text(encoding="utf-8"))
    assert comps["schema_version"] == "curve_composer_components_v1"
    assert len(comps["components"]) == 2
    assert all("gate_results_path" in c for c in comps["components"])
    assert "alignment_stats" in comps
    assert comps["alignment_stats"]["overall"]["intersection_points"] > 0
    for pc in comps["alignment_stats"]["per_component"]:
        assert pc["original_points"] >= pc["intersection_points"]
        dr = pc["drop_ratio"]
        assert (dr is None) or (0.0 <= float(dr) <= 1.0)

    # The composed run should be registrable as a new card (Gate PASS required).
    assert str(out["card_id"]).startswith("card_")

    # Append-only noop: same inputs again without re-register.
    h_manifest = _sha256_file(dossier_dir / "dossier_manifest.json")
    h_components = _sha256_file(dossier_dir / "components.json")
    code2, out2 = composer_run_once(
        card_ids=[c1, c2],
        weights=[0.5, 0.5],
        policy_bundle_path=bundle,
        register_card=False,
        title=None,
    )
    assert code2 == COMPOSER_OK, out2
    assert str(out2["run_id"]) == run_id
    assert _sha256_file(dossier_dir / "dossier_manifest.json") == h_manifest
    assert _sha256_file(dossier_dir / "components.json") == h_components


def test_integrity_gate_blocks_registration_if_component_fails(tmp_path: Path, monkeypatch) -> None:
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

    c1 = _make_card(tmp_path, snap="demo_snap_comp_fail_001", title="c1", monkeypatch=monkeypatch)
    c2 = _make_card(tmp_path, snap="demo_snap_comp_fail_002", title="c2", monkeypatch=monkeypatch)

    # Tamper component gate_results to simulate FAIL.
    comp_run_id = c1.replace("card_", "")
    comp_gr = art_root / "dossiers" / comp_run_id / "gate_results.json"
    gr = json.loads(comp_gr.read_text(encoding="utf-8"))
    gr["overall_pass"] = False
    comp_gr.write_text(json.dumps(gr, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    bundle = _repo_root() / "policies" / "policy_bundle_curve_composer_v1.yaml"
    code, out = composer_run_once(
        card_ids=[c1, c2],
        weights=[0.6, 0.4],
        policy_bundle_path=bundle,
        register_card=True,
        title="should_not_register",
    )
    assert code == COMPOSER_INVALID
    assert "run_id" in out
    # Ensure the card for composed run was not created.
    composed_run_id = str(out["run_id"])
    assert not (reg_root / "cards" / f"card_{composed_run_id}").exists()


def test_canonical_sorting_makes_run_id_stable_across_input_order(tmp_path: Path, monkeypatch) -> None:
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

    c1 = _make_card(tmp_path, snap="demo_snap_comp_stable_001", title="c1", monkeypatch=monkeypatch)
    c2 = _make_card(tmp_path, snap="demo_snap_comp_stable_002", title="c2", monkeypatch=monkeypatch)

    bundle = _repo_root() / "policies" / "policy_bundle_curve_composer_v1.yaml"
    code1, out1 = composer_run_once(
        card_ids=[c1, c2],
        weights=[0.6, 0.4],
        policy_bundle_path=bundle,
        register_card=False,
        title=None,
    )
    assert code1 == COMPOSER_OK, out1
    code2, out2 = composer_run_once(
        card_ids=[c2, c1],
        weights=[0.4, 0.6],
        policy_bundle_path=bundle,
        register_card=False,
        title=None,
    )
    assert code2 == COMPOSER_OK, out2
    assert out1["run_id"] == out2["run_id"]


def test_components_integrity_required_gate_ids_enforced(tmp_path: Path, monkeypatch) -> None:
    # Unit-level enforcement: configure gate params without changing v1 policy assets.
    from quant_eam.gates.components_integrity import run_components_integrity_v1
    from quant_eam.gates.types import GateContext

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

    c1 = _make_card(tmp_path, snap="demo_snap_comp_gate_001", title="c1", monkeypatch=monkeypatch)
    c2 = _make_card(tmp_path, snap="demo_snap_comp_gate_002", title="c2", monkeypatch=monkeypatch)

    # Compose once to get a composed dossier dir.
    bundle = _repo_root() / "policies" / "policy_bundle_curve_composer_v1.yaml"
    code, out = composer_run_once(
        card_ids=[c1, c2],
        weights=[0.5, 0.5],
        policy_bundle_path=bundle,
        register_card=False,
        title=None,
    )
    assert code == COMPOSER_OK, out
    dossier_dir = Path(out["dossier_path"])

    # Tamper one component gate_results: mark basic_sanity as not passed but keep overall_pass=true.
    comp_run_id = c1.replace("card_", "")
    gr_path = art_root / "dossiers" / comp_run_id / "gate_results.json"
    gr = json.loads(gr_path.read_text(encoding="utf-8"))
    for r in gr.get("results", []):
        if isinstance(r, dict) and r.get("gate_id") == "basic_sanity":
            r["pass"] = False
            r["status"] = "fail"
    gr["overall_pass"] = True
    gr_path.write_text(json.dumps(gr, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # Build a minimal ctx for the gate.
    dossier_manifest = json.loads((dossier_dir / "dossier_manifest.json").read_text(encoding="utf-8"))
    config_snapshot = json.loads((dossier_dir / "config_snapshot.json").read_text(encoding="utf-8"))
    metrics = json.loads((dossier_dir / "metrics.json").read_text(encoding="utf-8"))
    ctx = GateContext(
        dossier_dir=dossier_dir,
        policies_dir=_repo_root() / "policies",
        policy_bundle={},
        execution_policy={},
        cost_policy={},
        asof_latency_policy={},
        risk_policy=None,
        gate_suite={},
        runspec=config_snapshot["runspec"],
        dossier_manifest=dossier_manifest,
        config_snapshot=config_snapshot,
        metrics=metrics,
    )

    gr2 = run_components_integrity_v1(
        ctx,
        {
            "require_overall_pass": False,
            "required_gate_ids": ["basic_sanity"],
            "min_intersection_points": 1,
        },
    )
    assert gr2.passed is False
