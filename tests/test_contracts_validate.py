from __future__ import annotations

from pathlib import Path

from quant_eam.contracts import validate


def _examples_dir() -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    return repo_root / "contracts" / "examples"


def test_examples_ok_pass() -> None:
    ok_files = sorted(_examples_dir().glob("*_ok.json"))
    assert ok_files, "no *_ok.json examples found"

    for p in ok_files:
        code, msg = validate.validate_json(p)
        assert code == validate.EXIT_OK, f"{p.name}: {msg}"


def test_examples_bad_fail() -> None:
    bad_files = sorted(_examples_dir().glob("*_bad.json"))
    assert bad_files, "no *_bad.json examples found"

    for p in bad_files:
        code, msg = validate.validate_json(p)
        assert code == validate.EXIT_INVALID, f"{p.name}: {msg}"


def test_missing_discriminator_is_usage_error(tmp_path: Path) -> None:
    p = tmp_path / "missing_discriminator.json"
    p.write_text('{"hello":"world"}', encoding="utf-8")
    code = validate.main([str(p)])
    assert code == validate.EXIT_USAGE_OR_ERROR


def test_unknown_schema_version_is_invalid() -> None:
    p = _examples_dir() / "blueprint_bad.json"
    code = validate.main([str(p)])
    assert code == validate.EXIT_INVALID


def test_forced_schema_overrides_auto_selection() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    schema = repo_root / "contracts" / "blueprint_schema_v1.json"
    ok = _examples_dir() / "blueprint_ok.json"
    assert validate.main(["--schema", str(schema), str(ok)]) == validate.EXIT_OK

    # blueprint_bad.json has schema_version mismatch, which should be caught by the forced schema.
    bad = _examples_dir() / "blueprint_bad.json"
    assert validate.main(["--schema", str(schema), str(bad)]) == validate.EXIT_INVALID


def test_error_message_contains_schema_and_json_pointer() -> None:
    p = _examples_dir() / "signal_dsl_bad.json"
    code, msg = validate.validate_json(p)
    assert code == validate.EXIT_INVALID
    assert "signal_dsl_v1.json" in msg
    assert "/execution/cost_model/ref_policy" in msg
