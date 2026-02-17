from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from quant_eam.policies.load import default_policies_dir, iter_policy_assets, load_yaml, sha256_file

EXIT_OK = 0
EXIT_USAGE_OR_ERROR = 1
EXIT_INVALID = 2

LOCK_FILENAME = "policy_lock_v1.json"
LOCK_VERSION = "policy_lock_v1"


@dataclass(frozen=True)
class VError(Exception):
    path: tuple[str, ...]
    reason: str

    def format(self) -> str:
        if not self.path:
            return f"/: {self.reason}"
        return "/" + "/".join(self.path) + f": {self.reason}"


def _is_nonempty_str(x: Any) -> bool:
    return isinstance(x, str) and x.strip() != ""


def _require(mapping: dict[str, Any], key: str, path: tuple[str, ...]) -> Any:
    if key not in mapping:
        raise VError(path + (key,), "missing required key")
    return mapping[key]


def _expect(mapping: dict[str, Any], key: str, typ: type, path: tuple[str, ...]) -> Any:
    v = _require(mapping, key, path)
    if not isinstance(v, typ):
        raise VError(path + (key,), f"expected {typ.__name__}")
    return v


def _expect_one_of_str(mapping: dict[str, Any], key: str, allowed: set[str], path: tuple[str, ...]) -> str:
    v = _expect(mapping, key, str, path)
    if v not in allowed:
        raise VError(path + (key,), f"expected one of {sorted(allowed)} (got={v!r})")
    return v


def _yaml_key_path_to_str(parts: Iterable[str]) -> str:
    parts = list(parts)
    return "/" if not parts else "/" + "/".join(parts)


def _load_lock(lock_path: Path) -> dict[str, dict[str, str]]:
    """Return lock mapping: id -> {file, sha256}."""
    doc = json.loads(lock_path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise VError((), "lock must be a JSON object")
    if doc.get("lock_version") != LOCK_VERSION:
        raise VError(("lock_version",), f"must equal {LOCK_VERSION!r}")
    items = doc.get("items")
    if not isinstance(items, list):
        raise VError(("items",), "must be a list")

    out: dict[str, dict[str, str]] = {}
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            raise VError(("items", str(i)), "each item must be an object")
        pid = it.get("id")
        fp = it.get("file")
        sha = it.get("sha256")
        if not _is_nonempty_str(pid):
            raise VError(("items", str(i), "id"), "must be non-empty string")
        if not _is_nonempty_str(fp):
            raise VError(("items", str(i), "file"), "must be non-empty string")
        if not _is_nonempty_str(sha):
            raise VError(("items", str(i), "sha256"), "must be non-empty string")
        if pid in out:
            raise VError(("items", str(i), "id"), f"duplicate id in lock: {pid!r}")
        out[pid] = {"file": str(fp), "sha256": str(sha)}
    return out


def _resolve_lock_file_path(policies_dir: Path, file_field: str) -> Path:
    # Prefer repo-root-relative paths if they exist; otherwise treat as policies-dir-relative.
    repo_root = policies_dir.parent
    c1 = repo_root / file_field
    if c1.exists():
        return c1
    c2 = policies_dir / file_field
    if c2.exists():
        return c2
    return policies_dir / Path(file_field).name


def _write_lock(policies_dir: Path) -> tuple[int, str]:
    policies_dir = policies_dir.resolve()
    items: list[dict[str, str]] = []

    # Include all policy assets under policies/ (not only *_v1.yaml filenames).
    # Rationale: bundles may reference policy_id values that encode versioning in the id, not the filename.
    for p in sorted([pp for pp in policies_dir.glob("*.y*ml") if pp.is_file()]):
        doc = load_yaml(p)
        if not isinstance(doc, dict):
            continue
        pid = doc.get("policy_id") or doc.get("policy_bundle_id")
        if not _is_nonempty_str(pid):
            continue
        sha = sha256_file(p)

        # Stable file paths where possible (repo-root-relative); fallback to policies_dir-relative.
        try:
            file_str = p.resolve().relative_to(policies_dir.parent.resolve()).as_posix()
        except Exception:  # noqa: BLE001
            file_str = p.resolve().relative_to(policies_dir).as_posix()

        items.append({"id": str(pid), "file": file_str, "sha256": sha})

    items.sort(key=lambda d: d["id"])

    # Deterministic timestamp if SOURCE_DATE_EPOCH is provided (reproducible builds).
    sde = os.getenv("SOURCE_DATE_EPOCH")
    if sde and sde.isdigit():
        generated_at = datetime.fromtimestamp(int(sde), tz=timezone.utc).isoformat()
    else:
        generated_at = datetime.now(tz=timezone.utc).isoformat()

    lock_doc = {"lock_version": LOCK_VERSION, "generated_at": generated_at, "items": items}
    out_path = policies_dir / LOCK_FILENAME
    out_path.write_text(json.dumps(lock_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return EXIT_OK, f"WROTE: {out_path.as_posix()} items={len(items)}"


def _validate_policy_struct(doc: Any, file_path: Path) -> tuple[str, str]:
    if not isinstance(doc, dict):
        raise VError((), "top-level YAML must be a mapping/object")

    policy_id = _expect(doc, "policy_id", str, ())
    if not _is_nonempty_str(policy_id):
        raise VError(("policy_id",), "must be a non-empty string")

    policy_version = _expect(doc, "policy_version", str, ())
    if policy_version != "v1":
        raise VError(("policy_version",), 'must equal "v1"')

    _expect(doc, "title", str, ())
    _expect(doc, "description", str, ())
    params = _expect(doc, "params", dict, ())
    if params == {}:
        # Keep v1 minimally useful: empty params usually indicates a mistake.
        raise VError(("params",), "must not be empty")

    # Optional forward-compatible extension area (must not override governance/policies).
    if "extensions" in doc and not isinstance(doc["extensions"], dict):
        raise VError(("extensions",), "expected object")

    # Minimal param checks (avoid overfitting v1).
    # Policy type is determined by policy_id prefix (not filename) to keep semantics stable across locations
    # (e.g. examples/).
    if policy_id.startswith("execution_policy_v1"):
        allowed_timing = {"next_open", "close", "next_close"}
        _expect_one_of_str(params, "order_timing", allowed_timing, ("params",))
        if "fill_price" in params:
            _expect_one_of_str(params, "fill_price", {"open", "close", "vwap"}, ("params",))
        if "allow_short" in params and not isinstance(params["allow_short"], bool):
            raise VError(("params", "allow_short"), "expected bool")
        if "lot_size" in params and not isinstance(params["lot_size"], int):
            raise VError(("params", "lot_size"), "expected int")
        if "rounding" in params:
            _expect_one_of_str(params, "rounding", {"floor", "round", "ceil"}, ("params",))

    if policy_id.startswith("cost_policy_v1"):
        for k in ("commission_bps", "slippage_bps"):
            v = _require(params, k, ("params",))
            if not isinstance(v, (int, float)):
                raise VError(("params", k), "expected number")
        for k in ("tax_bps", "min_fee"):
            if k in params and not isinstance(params[k], (int, float)):
                raise VError(("params", k), "expected number")
        if "currency" in params and not _is_nonempty_str(params["currency"]):
            raise VError(("params", "currency"), "expected non-empty string")

    if policy_id.startswith("asof_latency_policy_v1"):
        asof_rule = _expect(params, "asof_rule", str, ("params",))
        if asof_rule != "available_at<=as_of":
            raise VError(("params", "asof_rule"), 'must equal "available_at<=as_of"')
        for k in ("default_latency_seconds", "bar_close_to_signal_seconds", "trade_lag_bars_default"):
            if k in params and not isinstance(params[k], int):
                raise VError(("params", k), "expected int")

    if policy_id.startswith("risk_policy_v1"):
        for k in ("max_leverage", "max_turnover"):
            if k in params and not isinstance(params[k], (int, float)):
                raise VError(("params", k), "expected number")
        for k in ("max_positions",):
            if k in params and not isinstance(params[k], int):
                raise VError(("params", k), "expected int")
        if "max_drawdown" in params and not isinstance(params["max_drawdown"], (int, float)):
            raise VError(("params", "max_drawdown"), "expected number")

    if policy_id.startswith("gate_suite_v1"):
        gates = _expect(params, "gates", list, ("params",))
        if not gates:
            raise VError(("params", "gates"), "must not be empty")
        for i, g in enumerate(gates):
            if not isinstance(g, dict):
                raise VError(("params", "gates", str(i)), "each gate must be an object")
            if not _is_nonempty_str(g.get("gate_id")):
                raise VError(("params", "gates", str(i), "gate_id"), "must be non-empty string")
            if not _is_nonempty_str(g.get("gate_version")):
                raise VError(("params", "gates", str(i), "gate_version"), "must be non-empty string")
            if "params" in g and not isinstance(g["params"], dict):
                raise VError(("params", "gates", str(i), "params"), "expected object")
        holdout = _expect(params, "holdout_policy", dict, ("params",))
        out = _expect(holdout, "output", str, ("params", "holdout_policy"))
        if out != "pass_fail_minimal_summary":
            raise VError(("params", "holdout_policy", "output"), 'must equal "pass_fail_minimal_summary"')

    if policy_id.startswith("budget_policy_v1"):
        # Workflow governance inputs: budgets/stops. Keep this minimal + strict.
        for k in ("max_proposals_per_job", "max_spawn_per_job", "max_total_iterations"):
            v = _require(params, k, ("params",))
            if not isinstance(v, int):
                raise VError(("params", k), "expected int")
            if v < 0:
                raise VError(("params", k), "must be >= 0")
        if "stop_if_no_improvement_n" in params:
            v = params["stop_if_no_improvement_n"]
            if not isinstance(v, int):
                raise VError(("params", "stop_if_no_improvement_n"), "expected int")
            if v < 0:
                raise VError(("params", "stop_if_no_improvement_n"), "must be >= 0")

    if policy_id.startswith("llm_budget_policy_v1"):
        # Job-level LLM budgets. Enforced by harness + orchestrator; keep semantics strict.
        for k in (
            "max_calls_per_job",
            "max_prompt_chars_per_job",
            "max_response_chars_per_job",
            "max_wall_seconds_per_job",
        ):
            v = _require(params, k, ("params",))
            if not isinstance(v, int):
                raise VError(("params", k), "expected int")
            if v < 0:
                raise VError(("params", k), "must be >= 0")
        if "max_calls_per_agent_run" in params:
            v = params["max_calls_per_agent_run"]
            if not isinstance(v, int):
                raise VError(("params", "max_calls_per_agent_run"), "expected int")
            if v < 0:
                raise VError(("params", "max_calls_per_agent_run"), "must be >= 0")

    return policy_id, sha256_file(file_path)


def _validate_bundle_struct(doc: Any) -> tuple[str, dict[str, str]]:
    if not isinstance(doc, dict):
        raise VError((), "top-level YAML must be a mapping/object")

    forbidden_inline = {"params", "overrides", "policies"}
    for k in forbidden_inline:
        if k in doc:
            raise VError((k,), "bundle must not inline/override policy content (bundle references ids only)")

    bundle_id = _expect(doc, "policy_bundle_id", str, ())
    if not _is_nonempty_str(bundle_id):
        raise VError(("policy_bundle_id",), "must be a non-empty string")

    policy_version = _expect(doc, "policy_version", str, ())
    if policy_version != "v1":
        raise VError(("policy_version",), 'must equal "v1"')

    # Optional metadata.
    if "title" in doc and not isinstance(doc["title"], str):
        raise VError(("title",), "expected string")
    if "description" in doc and not isinstance(doc["description"], str):
        raise VError(("description",), "expected string")
    if "extensions" in doc and not isinstance(doc["extensions"], dict):
        raise VError(("extensions",), "expected object")

    ref_keys = [
        "execution_policy_id",
        "cost_policy_id",
        "asof_latency_policy_id",
        "risk_policy_id",
        "gate_suite_id",
    ]
    refs: dict[str, str] = {}
    for k in ref_keys:
        v = _require(doc, k, ())
        if not _is_nonempty_str(v):
            raise VError((k,), "must be a non-empty string policy_id reference")
        refs[k] = v
    return bundle_id, refs


def _index_policies(policies_dir: Path) -> tuple[dict[str, Path], dict[str, str]]:
    """Index v1 policy assets (not bundles) by policy_id. Returns (id->path, id->sha256)."""
    id_to_path: dict[str, Path] = {}
    id_to_sha: dict[str, str] = {}

    for p in iter_policy_assets(policies_dir):
        doc = load_yaml(p)
        if isinstance(doc, dict) and "policy_id" in doc:
            policy_id, sha = _validate_policy_struct(doc, p)
            if policy_id in id_to_path:
                raise VError(("policy_id",), f"duplicate policy_id found: {policy_id!r} in {p.name} and {id_to_path[policy_id].name}")
            id_to_path[policy_id] = p
            id_to_sha[policy_id] = sha
    return id_to_path, id_to_sha


def validate_file(yaml_path: Path, policies_dir: Path | None = None) -> tuple[int, str]:
    """Validate a policy or bundle YAML file. Returns (exit_code, message)."""
    policies_dir = policies_dir or default_policies_dir()
    doc = load_yaml(yaml_path)

    try:
        if isinstance(doc, dict) and "policy_bundle_id" in doc:
            bundle_id, refs = _validate_bundle_struct(doc)
            id_to_path, id_to_sha = _index_policies(policies_dir)

            # Ensure referenced ids exist.
            for k, pid in refs.items():
                if pid not in id_to_path:
                    raise VError((k,), f"referenced policy_id not found in policies/: {pid!r}")

            # If a lock exists, enforce anti-tamper + replay consistency for referenced policies.
            lock_path = policies_dir / LOCK_FILENAME
            if lock_path.is_file():
                lock = _load_lock(lock_path)
                for k, pid in refs.items():
                    rec = lock.get(pid)
                    if not rec:
                        raise VError((k,), f"policy_id missing from lock: {pid!r}")
                    locked_file = _resolve_lock_file_path(policies_dir, rec["file"])
                    if not locked_file.is_file():
                        raise VError((k,), f"lock file path not found: {rec['file']!r}")
                    actual_sha = sha256_file(locked_file)
                    if actual_sha != rec["sha256"]:
                        raise VError(
                            (k,),
                            f"sha256 mismatch vs lock for {pid!r} (lock={rec['sha256']}, actual={actual_sha})",
                        )

            sha = sha256_file(yaml_path)
            return EXIT_OK, f"OK: {bundle_id} sha256={sha}"

        if isinstance(doc, dict) and "policy_id" in doc:
            policy_id, sha = _validate_policy_struct(doc, yaml_path)
            return EXIT_OK, f"OK: {policy_id} sha256={sha}"

        raise VError((), "missing policy_id or policy_bundle_id discriminator")
    except VError as e:
        return EXIT_INVALID, f"INVALID: {yaml_path.name} at {e.format()}"
    except Exception as e:  # noqa: BLE001
        return EXIT_USAGE_OR_ERROR, f"ERROR: {e}"


def validate_directory(policies_dir: Path) -> int:
    """Validate all *_v1.yaml files in a directory (excluding examples/)."""
    if not policies_dir.is_dir():
        print(f"ERROR: not a directory: {policies_dir}", file=sys.stderr)
        return EXIT_USAGE_OR_ERROR

    ok = 0
    invalid = 0
    for p in sorted([pp for pp in policies_dir.glob("*_v1.y*ml") if pp.is_file()]):
        code, msg = validate_file(p, policies_dir=policies_dir)
        if code == EXIT_OK:
            ok += 1
            print(msg)
        elif code == EXIT_INVALID:
            invalid += 1
            print(msg, file=sys.stderr)
        else:
            print(msg, file=sys.stderr)
            return EXIT_USAGE_OR_ERROR

    print(f"SUMMARY: OK={ok} INVALID={invalid}")
    return EXIT_INVALID if invalid else EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m quant_eam.policies.validate")
    parser.add_argument(
        "yaml_path",
        nargs="?",
        help="Path to a policy YAML file, a bundle YAML file, or a policies directory.",
    )
    parser.add_argument(
        "--policies-dir",
        default=None,
        help="Policies directory root to resolve bundle references (default: auto-detect repo policies/).",
    )
    parser.add_argument(
        "--write-lock",
        action="store_true",
        help="Generate or update policies/policy_lock_v1.json under the given policies directory.",
    )
    args = parser.parse_args(argv)

    if args.write_lock:
        target = Path(args.yaml_path) if args.yaml_path else default_policies_dir()
        policies_dir = target if target.is_dir() else target.parent
        try:
            code, msg = _write_lock(policies_dir)
            print(msg)
            return code
        except Exception as e:  # noqa: BLE001
            print(f"ERROR: {e}", file=sys.stderr)
            return EXIT_USAGE_OR_ERROR

    if not args.yaml_path:
        print("ERROR: missing yaml_path", file=sys.stderr)
        return EXIT_USAGE_OR_ERROR

    p = Path(args.yaml_path)
    if not p.exists():
        print(f"ERROR: path does not exist: {p}", file=sys.stderr)
        return EXIT_USAGE_OR_ERROR

    policies_dir = Path(args.policies_dir) if args.policies_dir else None
    if p.is_dir():
        return validate_directory(p if policies_dir is None else policies_dir)

    if not p.is_file():
        print(f"ERROR: not a file: {p}", file=sys.stderr)
        return EXIT_USAGE_OR_ERROR

    code, msg = validate_file(p, policies_dir=policies_dir)
    print(msg if code == EXIT_OK else msg, file=sys.stdout if code == EXIT_OK else sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
