from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

EXIT_OK = 0
EXIT_USAGE_OR_ERROR = 1
EXIT_INVALID = 2


SCHEMA_VERSION_TO_FILE = {
    "blueprint_v1": "blueprint_schema_v1.json",
    "variable_dictionary_v1": "variable_dictionary_v1.json",
    "calc_trace_plan_v1": "calc_trace_plan_v1.json",
    "diagnostic_spec_v1": "diagnostic_spec_v1.json",
    "gate_spec_v1": "gate_spec_v1.json",
    "run_spec_v1": "run_spec_schema_v1.json",
    "run_spec_v2": "run_spec_schema_v2.json",
    "dossier_v1": "dossier_schema_v1.json",
    "gate_results_v1": "gate_results_schema_v1.json",
    "gate_results_v2": "gate_results_schema_v2.json",
    "trial_event_v1": "trial_event_schema_v1.json",
    "experience_card_v1": "experience_card_schema_v1.json",
    "job_spec_v1": "job_spec_schema_v1.json",
    "job_event_v1": "job_event_schema_v1.json",
    "job_event_v2": "job_event_schema_v2.json",
    "idea_spec_v1": "idea_spec_schema_v1.json",
    "agent_run_v1": "agent_run_schema_v1.json",
    "improvement_proposals_v1": "improvement_proposals_schema_v1.json",
    "data_snapshot_manifest_v1": "data_snapshot_manifest_schema_v1.json",
    "ingest_manifest_v1": "ingest_manifest_schema_v1.json",
    "quality_report_v1": "quality_report_schema_v1.json",
    "data_quality_report_v1": "quality_report_schema_v1.json",
    "llm_call_v1": "llm_call_schema_v1.json",
    "llm_session_v1": "llm_session_schema_v1.json",
    "llm_usage_report_v1": "llm_usage_report_schema_v1.json",
    "output_guard_report_v1": "output_guard_report_schema_v1.json",
}

DSL_VERSION_TO_FILE = {
    "signal_dsl_v1": "signal_dsl_v1.json",
}


def _json_path(p: str) -> Path:
    path = Path(p)
    if not path.exists():
        raise FileNotFoundError(p)
    if not path.is_file():
        raise IsADirectoryError(p)
    return path


def _format_json_pointer(err: ValidationError) -> str:
    # RFC 6901. Root is "" but we print "/" for readability.
    if not err.path:
        return "/"

    def esc(token: str) -> str:
        return token.replace("~", "~0").replace("/", "~1")

    parts: list[str] = []
    for part in err.path:
        parts.append(str(part) if isinstance(part, int) else esc(str(part)))
    return "/" + "/".join(parts)


def _format_reason(err: ValidationError) -> str:
    msg = err.message
    if isinstance(err.instance, (str, int, float, bool)) or err.instance is None:
        msg = f"{msg} (got={err.instance!r})"
    return msg


def _find_repo_root() -> Path:
    candidates: list[Path] = []
    env_root = os.getenv("EAM_REPO")
    if env_root:
        candidates.append(Path(env_root))
    cwd = Path.cwd()
    candidates.append(cwd)
    candidates.extend(cwd.parents)

    here = Path(__file__).resolve()
    candidates.append(here)
    candidates.extend(here.parents)

    for c in candidates:
        if c.is_dir() and (c / "contracts").is_dir():
            return c

    return cwd


def _contracts_dir() -> Path:
    return _find_repo_root() / "contracts"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_registry(contracts_dir: Path) -> Registry:
    registry = Registry()
    for schema_path in sorted(contracts_dir.rglob("*.json")):
        schema = _load_json(schema_path)
        schema_id = schema.get("$id") if isinstance(schema, dict) else None
        if not schema_id:
            continue
        resource = Resource.from_contents(schema, default_specification=DRAFT202012)
        registry = registry.with_resource(schema_id, resource)
    return registry


class _MissingDiscriminator(ValueError):
    pass


class _UnknownDiscriminator(ValueError):
    def __init__(self, field: str, value: str) -> None:
        super().__init__(f"Unknown {field}: {value!r}")
        self.field = field
        self.value = value


def _select_schema_path(payload: Any, contracts_dir: Path) -> Path:
    if not isinstance(payload, dict):
        raise ValueError("Top-level JSON must be an object.")

    schema_version = payload.get("schema_version")
    dsl_version = payload.get("dsl_version")

    if isinstance(schema_version, str):
        filename = SCHEMA_VERSION_TO_FILE.get(schema_version)
        if not filename:
            raise _UnknownDiscriminator("schema_version", schema_version)
        return contracts_dir / filename
    if schema_version is not None:
        raise ValueError("schema_version must be a string.")

    if isinstance(dsl_version, str):
        filename = DSL_VERSION_TO_FILE.get(dsl_version)
        if not filename:
            raise _UnknownDiscriminator("dsl_version", dsl_version)
        return contracts_dir / filename
    if dsl_version is not None:
        raise ValueError("dsl_version must be a string.")

    raise _MissingDiscriminator("missing schema_version/dsl_version")


def validate_payload(payload: Any, schema_path: Path | None = None) -> tuple[int, str]:
    """Validate an in-memory JSON payload (object) and return (exit_code, message)."""
    contracts_dir = _contracts_dir()
    registry = _build_registry(contracts_dir)

    if schema_path is not None:
        resolved_schema_path = schema_path
    else:
        try:
            resolved_schema_path = _select_schema_path(payload, contracts_dir)
        except _MissingDiscriminator:
            return (
                EXIT_USAGE_OR_ERROR,
                "ERROR: missing schema_version/dsl_version (or pass --schema <schema_file>)",
            )
        except _UnknownDiscriminator as e:
            return (EXIT_INVALID, f"INVALID: discriminator at /{e.field}: {e}")
        except ValueError as e:
            return (EXIT_INVALID, f"INVALID: discriminator at /: {e}")

    schema = _load_json(resolved_schema_path)
    validator = Draft202012Validator(schema, registry=registry)
    errors = sorted(validator.iter_errors(payload), key=lambda e: (list(e.path), e.message))
    if errors:
        first = errors[0]
        path_str = _format_json_pointer(first)
        msg = f"INVALID: {resolved_schema_path.name} at {path_str}: {_format_reason(first)}"
        return (EXIT_INVALID, msg)
    return (EXIT_OK, f"OK: {resolved_schema_path.name}")


def validate_json(payload_path: Path, schema_path: Path | None = None) -> tuple[int, str]:
    """Validate a JSON payload file and return (exit_code, schema_label)."""
    payload = _load_json(payload_path)
    return validate_payload(payload, schema_path=schema_path)


def _fetch_schema_path(filename: str) -> Path:
    schema_path = _contracts_dir() / filename
    if not schema_path.is_file():
        raise FileNotFoundError(f"missing schema: {schema_path.as_posix()}")
    return schema_path


def _extract_fetch_value(fetch_request: dict[str, Any], key: str) -> tuple[str | None, Any]:
    if fetch_request.get(key) is not None:
        return f"/{key}", fetch_request.get(key)
    intent_obj = fetch_request.get("intent")
    if isinstance(intent_obj, dict) and intent_obj.get(key) is not None:
        return f"/intent/{key}", intent_obj.get(key)
    kwargs_obj = fetch_request.get("kwargs")
    if isinstance(kwargs_obj, dict) and kwargs_obj.get(key) is not None:
        return f"/kwargs/{key}", kwargs_obj.get(key)
    return None, None


def _parse_iso_date(raw: str) -> date | None:
    s = raw.strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _has_symbol_value(v: Any) -> bool:
    if isinstance(v, str):
        return bool(v.strip())
    if isinstance(v, list):
        for item in v:
            if isinstance(item, str) and item.strip():
                return True
        return False
    if isinstance(v, tuple):
        return _has_symbol_value(list(v))
    return v is not None


def _fetch_request_has_symbols(fetch_request: dict[str, Any]) -> bool:
    intent_obj = fetch_request.get("intent")
    kwargs_obj = fetch_request.get("kwargs")
    candidates: list[Any] = [fetch_request.get("symbols")]
    if isinstance(intent_obj, dict):
        candidates.append(intent_obj.get("symbols"))
    if isinstance(kwargs_obj, dict):
        candidates.append(kwargs_obj.get("symbols"))
        candidates.append(kwargs_obj.get("symbol"))
    return any(_has_symbol_value(v) for v in candidates)


def _fetch_request_auto_symbols(fetch_request: dict[str, Any]) -> tuple[bool, str]:
    intent_obj = fetch_request.get("intent")
    top_level = fetch_request.get("auto_symbols")
    in_intent = intent_obj.get("auto_symbols") if isinstance(intent_obj, dict) else None

    if top_level is not None and not isinstance(top_level, bool):
        raise ValueError("INVALID: fetch_request at /auto_symbols: auto_symbols must be boolean")
    if in_intent is not None and not isinstance(in_intent, bool):
        raise ValueError("INVALID: fetch_request at /intent/auto_symbols: auto_symbols must be boolean")

    if top_level is not None and in_intent is not None and top_level != in_intent:
        raise ValueError(
            "INVALID: fetch_request at /intent/auto_symbols: auto_symbols conflicts with top-level /auto_symbols"
        )

    if in_intent is not None:
        return in_intent, "/intent/auto_symbols"
    if top_level is not None:
        return top_level, "/auto_symbols"
    return False, "/auto_symbols"


def validate_fetch_request(fetch_request: Any) -> tuple[int, str]:
    """Validate fetch_request against schema + logical constraints."""
    schema_path = _fetch_schema_path("fetch_request_schema_v1.json")
    code, msg = validate_payload(fetch_request, schema_path=schema_path)
    if code != EXIT_OK:
        return code, msg

    if not isinstance(fetch_request, dict):
        return EXIT_INVALID, "INVALID: fetch_request must be an object"

    intent_obj = fetch_request.get("intent")
    has_intent = isinstance(intent_obj, dict)
    function_name = fetch_request.get("function")
    has_function = isinstance(function_name, str) and bool(function_name.strip())
    if has_function and has_intent:
        return (
            EXIT_INVALID,
            "INVALID: fetch_request at /: intent and function modes are mutually exclusive in v1",
        )

    has_symbols = _fetch_request_has_symbols(fetch_request)
    try:
        auto_symbols, auto_symbols_path = _fetch_request_auto_symbols(fetch_request)
    except ValueError as e:
        return EXIT_INVALID, str(e)
    if not has_symbols and not auto_symbols:
        return (
            EXIT_INVALID,
            "INVALID: fetch_request at /: symbols (or kwargs.symbol) is required unless auto_symbols=true",
        )
    if has_symbols and auto_symbols:
        return (
            EXIT_INVALID,
            f"INVALID: fetch_request at {auto_symbols_path}: auto_symbols=true cannot be combined with explicit symbols",
        )

    start_path, start_raw = _extract_fetch_value(fetch_request, "start")
    end_path, end_raw = _extract_fetch_value(fetch_request, "end")
    start_date: date | None = None
    end_date: date | None = None
    if start_raw is not None:
        if not isinstance(start_raw, str):
            return EXIT_INVALID, f"INVALID: fetch_request at {start_path}: start must be string"
        start_date = _parse_iso_date(start_raw)
        if start_date is None:
            return (
                EXIT_INVALID,
                f"INVALID: fetch_request at {start_path}: start must be ISO date/datetime string",
            )
    if end_raw is not None:
        if not isinstance(end_raw, str):
            return EXIT_INVALID, f"INVALID: fetch_request at {end_path}: end must be string"
        end_date = _parse_iso_date(end_raw)
        if end_date is None:
            return (
                EXIT_INVALID,
                f"INVALID: fetch_request at {end_path}: end must be ISO date/datetime string",
            )
    if start_date is not None and end_date is not None and start_date > end_date:
        return (
            EXIT_INVALID,
            f"INVALID: fetch_request at {start_path}: start must be <= end ({start_date.isoformat()} > {end_date.isoformat()})",
        )

    return EXIT_OK, f"OK: {schema_path.name}"


def validate_fetch_result_meta(fetch_result_meta: Any) -> tuple[int, str]:
    """Validate fetch_result_meta payload against the versioned contract."""
    schema_path = _fetch_schema_path("fetch_result_meta_schema_v1.json")
    return validate_payload(fetch_result_meta, schema_path=schema_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m quant_eam.contracts.validate")
    parser.add_argument("json_path", nargs="?", help="Path to a JSON file to validate.")
    parser.add_argument(
        "--schema",
        dest="schema",
        default=None,
        help="Force a schema file (path). When omitted, uses schema_version/dsl_version mapping.",
    )
    parser.add_argument(
        "--examples",
        dest="examples",
        default=None,
        help="Validate all '*_ok.json' examples under this directory.",
    )
    args = parser.parse_args(argv)

    try:
        forced_schema_path = _json_path(args.schema) if args.schema else None

        if args.examples:
            examples_dir = Path(args.examples)
            ok_files = sorted(examples_dir.glob("*_ok.json"))
            if not ok_files:
                print(f"ERROR: no '*_ok.json' files found under: {examples_dir}", file=sys.stderr)
                return EXIT_USAGE_OR_ERROR

            worst = EXIT_OK
            for p in ok_files:
                code, msg = validate_json(p, schema_path=forced_schema_path)
                print(msg if code == EXIT_OK else msg, file=sys.stdout if code == EXIT_OK else sys.stderr)
                worst = max(worst, code)
            return worst

        if not args.json_path:
            print("ERROR: missing json_path (or use --examples).", file=sys.stderr)
            return EXIT_USAGE_OR_ERROR

        payload_path = _json_path(args.json_path)
        code, msg = validate_json(payload_path, schema_path=forced_schema_path)
        print(msg if code == EXIT_OK else msg, file=sys.stdout if code == EXIT_OK else sys.stderr)
        return code
    except json.JSONDecodeError as e:
        print(f"ERROR: invalid JSON: {e}", file=sys.stderr)
        return EXIT_USAGE_OR_ERROR
    except (OSError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return EXIT_USAGE_OR_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
