from __future__ import annotations

from pathlib import Path

from quant_eam.contracts import validate


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_diagnostic_spec_examples_validate_with_forced_schema() -> None:
    root = _repo_root()
    schema = root / "contracts" / "diagnostic_spec_v1.json"
    ok = root / "contracts" / "examples" / "diagnostic_spec_ok.json"
    bad = root / "contracts" / "examples" / "diagnostic_spec_bad.json"

    code_ok, msg_ok = validate.validate_json(ok, schema_path=schema)
    assert code_ok == validate.EXIT_OK, msg_ok
    code_bad, msg_bad = validate.validate_json(bad, schema_path=schema)
    assert code_bad == validate.EXIT_INVALID, msg_bad


def test_gate_spec_examples_validate_with_forced_schema() -> None:
    root = _repo_root()
    schema = root / "contracts" / "gate_spec_v1.json"
    ok = root / "contracts" / "examples" / "gate_spec_ok.json"
    bad = root / "contracts" / "examples" / "gate_spec_bad.json"

    code_ok, msg_ok = validate.validate_json(ok, schema_path=schema)
    assert code_ok == validate.EXIT_OK, msg_ok
    code_bad, msg_bad = validate.validate_json(bad, schema_path=schema)
    assert code_bad == validate.EXIT_INVALID, msg_bad


def test_contracts_examples_checker_passes() -> None:
    root = _repo_root()
    code = validate.EXIT_USAGE_OR_ERROR
    # Reuse project script entry behavior inside test runner process.
    import subprocess

    cp = subprocess.run(
        ["python3", "scripts/check_contracts_examples.py"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    code = cp.returncode
    assert code == 0, cp.stderr or cp.stdout
