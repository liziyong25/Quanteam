from __future__ import annotations

import json
from pathlib import Path

from quant_eam.compiler.compile import EXIT_INVALID, EXIT_OK, main as compiler_main
from quant_eam.contracts import validate as contracts_validate


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_compiler_demo_blueprint_compiles_to_valid_runspec(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    out = tmp_path / "runspec.json"
    bp = _repo_root() / "contracts" / "examples" / "blueprint_buyhold_demo_ok.json"
    bundle = _repo_root() / "policies" / "policy_bundle_v1.yaml"
    code = compiler_main(
        [
            "--blueprint",
            str(bp),
            "--snapshot-id",
            "demo_snap_001",
            "--out",
            str(out),
            "--policy-bundle",
            str(bundle),
        ]
    )
    assert code == EXIT_OK

    c2, msg2 = contracts_validate.validate_json(out)
    assert c2 == contracts_validate.EXIT_OK, msg2


def test_compiler_rejects_policy_bundle_mismatch(tmp_path: Path) -> None:
    out = tmp_path / "runspec.json"
    bp = _repo_root() / "contracts" / "examples" / "blueprint_policy_mismatch_semantic.json"
    bundle = _repo_root() / "policies" / "policy_bundle_v1.yaml"
    code = compiler_main(
        [
            "--blueprint",
            str(bp),
            "--snapshot-id",
            "demo_snap_001",
            "--out",
            str(out),
            "--policy-bundle",
            str(bundle),
        ]
    )
    assert code == EXIT_INVALID
