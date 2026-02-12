from __future__ import annotations

import json
from pathlib import Path

from quant_eam.contracts import validate


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_diagnostic_spec_ok_validates_via_discriminator() -> None:
    payload = _repo_root() / "contracts" / "examples" / "diagnostic_spec_ok.json"

    code, msg = validate.validate_json(payload)

    assert code == validate.EXIT_OK, msg
    assert "diagnostic_spec_v1.json" in msg


def test_gate_spec_ok_validates_via_discriminator() -> None:
    payload = _repo_root() / "contracts" / "examples" / "gate_spec_ok.json"

    code, msg = validate.validate_json(payload)

    assert code == validate.EXIT_OK, msg
    assert "gate_spec_v1.json" in msg


def test_unknown_schema_version_still_invalid(tmp_path: Path) -> None:
    payload = tmp_path / "unknown_schema.json"
    payload.write_text(
        json.dumps(
            {
                "schema_version": "unknown_schema_version_v999",
                "foo": "bar",
            }
        ),
        encoding="utf-8",
    )

    code, msg = validate.validate_json(payload)

    assert code == validate.EXIT_INVALID
    assert "discriminator at /schema_version" in msg
