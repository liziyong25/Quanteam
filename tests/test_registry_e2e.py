from __future__ import annotations

import json
from pathlib import Path

from quant_eam.compiler.compile import EXIT_OK as COMPILER_OK, main as compiler_main
from quant_eam.contracts import validate as contracts_validate
from quant_eam.data_lake.demo_ingest import main as demo_ingest_main
from quant_eam.gaterunner.run import main as gaterunner_main
from quant_eam.registry import cli as registry_cli
from quant_eam.registry.cards import card_file_hashes
from quant_eam.registry.storage import registry_paths
from quant_eam.runner.run import EXIT_OK as RUNNER_OK, main as runner_main


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _jsonl_lines(p: Path) -> list[str]:
    if not p.is_file():
        return []
    return [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def test_e2e_triallog_and_experience_card(tmp_path: Path, monkeypatch) -> None:
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

    snap = "demo_snap_registry_e2e_001"
    assert demo_ingest_main(["--root", str(data_root), "--snapshot-id", snap]) == 0

    bp = _repo_root() / "contracts" / "examples" / "blueprint_buyhold_demo_ok.json"
    bundle = _repo_root() / "policies" / "policy_bundle_v1.yaml"
    runspec = tmp_path / "runspec.json"
    assert compiler_main(["--blueprint", str(bp), "--snapshot-id", snap, "--out", str(runspec), "--policy-bundle", str(bundle)]) == COMPILER_OK
    assert runner_main(["--runspec", str(runspec), "--policy-bundle", str(bundle)]) == RUNNER_OK

    d = sorted([p for p in (art_root / "dossiers").iterdir() if p.is_dir()])[0]
    assert gaterunner_main(["--dossier", str(d), "--policy-bundle", str(bundle)]) in (0, 2)

    # record-trial (CLI)
    assert registry_cli.main(["--registry-root", str(reg_root), "record-trial", "--dossier", str(d)]) == 0

    paths = registry_paths(reg_root)
    assert paths.trial_log.is_file()
    lines = _jsonl_lines(paths.trial_log)
    assert len(lines) == 1
    ev = json.loads(lines[0])
    tmp_ev = tmp_path / "trial_event.json"
    tmp_ev.write_text(json.dumps(ev, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    assert contracts_validate.main([str(tmp_ev)]) == contracts_validate.EXIT_OK

    # create-card (CLI)
    run_id = str(ev["run_id"])
    assert registry_cli.main(
        ["--registry-root", str(reg_root), "create-card", "--run-id", run_id, "--title", "buyhold_demo"]
    ) == 0

    card_id = f"card_{run_id}"
    card_json = reg_root / "cards" / card_id / "card_v1.json"
    assert card_json.is_file()
    assert contracts_validate.main([str(card_json)]) == contracts_validate.EXIT_OK


def test_gate_pass_required_for_card_creation(tmp_path: Path, monkeypatch) -> None:
    reg_root = tmp_path / "registry"
    reg_root.mkdir()
    monkeypatch.setenv("EAM_REGISTRY_ROOT", str(reg_root))
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    # Minimal fake trial event with overall_pass=false.
    ev = {
        "schema_version": "trial_event_v1",
        "run_id": "run_fail_001",
        "recorded_at": "2024-01-01T00:00:00+00:00",
        "dossier_path": "/tmp/dossier/run_fail_001",
        "gate_results_path": "/tmp/dossier/run_fail_001/gate_results.json",
        "overall_pass": False,
        "policy_bundle_id": "policy_bundle_v1_default",
        "snapshot_id": "snap_x",
        "adapter_id": "vectorbt_signal_v1",
    }
    paths = registry_paths(reg_root)
    paths.registry_root.mkdir(parents=True, exist_ok=True)
    paths.trial_log.write_text(json.dumps(ev, sort_keys=True) + "\n", encoding="utf-8")

    assert (
        registry_cli.main(
            [
                "--registry-root",
                str(reg_root),
                "create-card",
                "--run-id",
                "run_fail_001",
                "--title",
                "should_fail",
            ]
        )
        == 2
    )


def test_append_only_semantics_triallog_and_card_events(tmp_path: Path, monkeypatch) -> None:
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

    snap = "demo_snap_registry_e2e_002"
    assert demo_ingest_main(["--root", str(data_root), "--snapshot-id", snap]) == 0

    bp = _repo_root() / "contracts" / "examples" / "blueprint_buyhold_demo_ok.json"
    bundle = _repo_root() / "policies" / "policy_bundle_v1.yaml"
    runspec = tmp_path / "runspec.json"
    assert compiler_main(["--blueprint", str(bp), "--snapshot-id", snap, "--out", str(runspec), "--policy-bundle", str(bundle)]) == COMPILER_OK
    assert runner_main(["--runspec", str(runspec), "--policy-bundle", str(bundle)]) == RUNNER_OK
    d = sorted([p for p in (art_root / "dossiers").iterdir() if p.is_dir()])[0]
    assert gaterunner_main(["--dossier", str(d), "--policy-bundle", str(bundle)]) in (0, 2)

    # record-trial twice: default noop, should not duplicate.
    assert registry_cli.main(["--registry-root", str(reg_root), "record-trial", "--dossier", str(d)]) == 0
    assert registry_cli.main(["--registry-root", str(reg_root), "record-trial", "--dossier", str(d)]) == 0
    lines = _jsonl_lines(registry_paths(reg_root).trial_log)
    assert len(lines) == 1
    ev = json.loads(lines[0])
    run_id = str(ev["run_id"])

    # create-card then promote: card_v1.json must not change; events.jsonl must append.
    assert registry_cli.main(
        ["--registry-root", str(reg_root), "create-card", "--run-id", run_id, "--title", "buyhold_demo"]
    ) == 0
    card_id = f"card_{run_id}"
    h1 = card_file_hashes(registry_root=reg_root, card_id=card_id)
    assert registry_cli.main(
        [
            "--registry-root",
            str(reg_root),
            "promote-card",
            "--card-id",
            card_id,
            "--new-status",
            "challenger",
        ]
    ) == 0
    h2 = card_file_hashes(registry_root=reg_root, card_id=card_id)
    assert h1["card_v1.json"] == h2["card_v1.json"]
    assert h1.get("events.jsonl") != h2.get("events.jsonl")

