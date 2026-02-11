#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

from quant_eam.contracts import validate as contracts_validate


# Progressive enforcement: Phase-25 enforces core SSOT schemas first.
REQUIRED_SCHEMA_FILES = [
    "blueprint_schema_v1.json",
    "run_spec_schema_v1.json",
    "dossier_schema_v1.json",
    "variable_dictionary_v1.json",
    "calc_trace_plan_v1.json",
    "signal_dsl_v1.json",
]


def _examples_dir(repo_root: Path) -> Path:
    return repo_root / "contracts" / "examples"


def _contracts_dir(repo_root: Path) -> Path:
    return repo_root / "contracts"


def main() -> int:
    repo_root = Path.cwd()
    examples_dir = _examples_dir(repo_root)
    contracts_dir = _contracts_dir(repo_root)

    if not examples_dir.is_dir():
        print("ERROR: missing contracts/examples directory", file=sys.stderr)
        return 2

    errors: list[str] = []

    example_files = sorted([p for p in examples_dir.glob("*.json") if p.is_file()])
    if not example_files:
        errors.append("no contract examples found under contracts/examples")

    for schema_name in REQUIRED_SCHEMA_FILES:
        schema_path = contracts_dir / schema_name
        if not schema_path.is_file():
            errors.append(f"missing required schema file: contracts/{schema_name}")
            continue

        ok = 0
        bad = 0
        for ex in example_files:
            code, _msg = contracts_validate.validate_json(ex, schema_path=schema_path)
            if code == contracts_validate.EXIT_OK:
                ok += 1
            elif code == contracts_validate.EXIT_INVALID:
                bad += 1

        if ok < 1:
            errors.append(f"{schema_name}: missing OK example (forced-schema validation)")
        if bad < 1:
            errors.append(f"{schema_name}: missing INVALID example (forced-schema validation)")

    if errors:
        print("contracts examples: INVALID", file=sys.stderr)
        for e in errors:
            print(f"- {e}", file=sys.stderr)
        return 2

    print("contracts examples: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

