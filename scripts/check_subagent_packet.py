#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml


REQUIRED_VALIDATOR_CHECKS = {
    "task_card_published",
    "executor_is_codex_cli",
    "allowed_paths_only",
    "acceptance_commands_executed",
    "ssot_updated",
}
SNAPSHOT_SCHEMA_VERSION = "subagent_workspace_snapshot_v1"
EVIDENCE_POLICY_LEGACY = "legacy"
EVIDENCE_POLICY_HARDENED = "hardened"
REQUIRED_EVIDENCE_FILE_KEYS = ("workspace_before", "workspace_after", "acceptance_log")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
EPHEMERAL_IGNORE_PATTERNS = (
    ".pytest_cache/**",
    ".ruff_cache/**",
    ".mypy_cache/**",
    "**/__pycache__/**",
)


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        obj = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"invalid yaml: {path.as_posix()}: {e}") from e
    if not isinstance(obj, dict):
        raise ValueError(f"yaml root must be mapping: {path.as_posix()}")
    return obj


def _load_json(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"invalid json: {path.as_posix()}: {e}") from e
    if not isinstance(obj, dict):
        raise ValueError(f"json root must be object: {path.as_posix()}")
    return obj


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        ln = line.strip()
        if not ln:
            continue
        try:
            obj = json.loads(ln)
        except Exception as e:  # noqa: BLE001
            raise ValueError(f"invalid jsonl row {i}: {path.as_posix()}: {e}") from e
        if not isinstance(obj, dict):
            raise ValueError(f"jsonl row {i} must be object: {path.as_posix()}")
        rows.append(obj)
    return rows


def _norm_path(p: str) -> str:
    s = str(p).strip().replace("\\", "/")
    while s.startswith("./"):
        s = s[2:]
    return s.rstrip("/")


def _match_allowed(changed: str, rule: str) -> bool:
    ch = _norm_path(changed)
    rr = _norm_path(rule)
    if not rr:
        return False
    if "*" in rr or "?" in rr or "[" in rr:
        return fnmatch.fnmatch(ch, rr)
    return ch == rr or ch.startswith(rr + "/")


def _contains_command(required: str, commands_run: list[str]) -> bool:
    req = str(required).strip()
    if not req:
        return False
    for c in commands_run:
        if req in str(c):
            return True
    return False


def _is_packet_internal(path: str, packet_prefix: str) -> bool:
    pp = _norm_path(packet_prefix)
    if not pp:
        return False
    p = _norm_path(path)
    return p == pp or p.startswith(pp + "/")


def _is_ignored_workspace_path(path: str, *, ignore_patterns: tuple[str, ...]) -> bool:
    p = _norm_path(path)
    for pat in ignore_patterns:
        if fnmatch.fnmatch(p, _norm_path(pat)):
            return True
    return False


def _resolve_evidence_path(raw: str, *, repo_root: Path, packet_dir: Path) -> Path:
    s = str(raw).strip()
    if not s:
        return Path("")
    p = Path(s)
    if p.is_absolute():
        return p
    cand_repo = repo_root / p
    if cand_repo.exists():
        return cand_repo
    cand_packet = packet_dir / p
    return cand_packet


def _snapshot_files(doc: dict[str, Any], *, label: str) -> dict[str, str]:
    if str(doc.get("schema_version", "")).strip() != SNAPSHOT_SCHEMA_VERSION:
        raise ValueError(f"{label} schema_version must be {SNAPSHOT_SCHEMA_VERSION}")
    files = doc.get("files")
    if not isinstance(files, dict):
        raise ValueError(f"{label} files must be an object mapping path->sha256")

    out: dict[str, str] = {}
    for raw_p, raw_h in files.items():
        path_key = _norm_path(str(raw_p))
        hash_val = str(raw_h).strip().lower()
        if not path_key:
            raise ValueError(f"{label} contains empty path key")
        if not HEX64_RE.match(hash_val):
            raise ValueError(f"{label} has non-sha256 hash for {path_key}")
        out[path_key] = hash_val
    return out


def _compute_changed(before_files: dict[str, str], after_files: dict[str, str]) -> set[str]:
    all_paths = set(before_files) | set(after_files)
    return {p for p in all_paths if before_files.get(p) != after_files.get(p)}


def _coerce_exit_code(v: Any) -> int | None:
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, str):
        s = v.strip()
        if s.startswith("-"):
            s2 = s[1:]
            if s2.isdigit():
                return -int(s2)
            return None
        if s.isdigit():
            return int(s)
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate subagent control packet (v1).")
    ap.add_argument("--phase-id", required=True, help="Phase id, e.g. phase_30")
    ap.add_argument(
        "--packet-root",
        default="artifacts/subagent_control",
        help="Packet root directory (default: artifacts/subagent_control)",
    )
    args = ap.parse_args()

    phase_id = str(args.phase_id).strip()
    packet_dir = Path(args.packet_root) / phase_id
    errors: list[str] = []
    repo_root = Path.cwd()
    packet_prefix = _norm_path((Path(args.packet_root) / phase_id).as_posix())

    task_path = packet_dir / "task_card.yaml"
    exec_path = packet_dir / "executor_report.yaml"
    val_path = packet_dir / "validator_report.yaml"
    for p in (task_path, exec_path, val_path):
        if not p.is_file():
            errors.append(f"missing required file: {p.as_posix()}")

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 2

    try:
        task = _load_yaml(task_path)
        exe = _load_yaml(exec_path)
        val = _load_yaml(val_path)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    if task.get("schema_version") != "subagent_task_card_v1":
        errors.append("task_card.yaml schema_version must be subagent_task_card_v1")
    if exe.get("schema_version") != "subagent_executor_report_v1":
        errors.append("executor_report.yaml schema_version must be subagent_executor_report_v1")
    if val.get("schema_version") != "subagent_validator_report_v1":
        errors.append("validator_report.yaml schema_version must be subagent_validator_report_v1")

    # Phase consistency.
    for name, doc in (("task_card.yaml", task), ("executor_report.yaml", exe), ("validator_report.yaml", val)):
        pid = str(doc.get("phase_id", "")).strip()
        if pid != phase_id:
            errors.append(f"{name} phase_id mismatch: expected {phase_id!r}, got {pid!r}")

    # Enforce codex-cli delegation.
    req_exec = str(task.get("executor_required", "")).strip()
    if req_exec != "codex_cli_subagent":
        errors.append("task_card.yaml executor_required must be codex_cli_subagent")
    ex_meta = exe.get("executor") if isinstance(exe.get("executor"), dict) else {}
    if str(ex_meta.get("role", "")).strip() != "codex_cli_subagent":
        errors.append("executor_report.yaml executor.role must be codex_cli_subagent")
    if str(ex_meta.get("runtime", "")).strip() != "codex_cli":
        errors.append("executor_report.yaml executor.runtime must be codex_cli")

    # Allowed paths check.
    allowed_paths = task.get("allowed_paths") if isinstance(task.get("allowed_paths"), list) else []
    if not allowed_paths:
        errors.append("task_card.yaml allowed_paths must be a non-empty list")

    raw_external_noise_paths = task.get("external_noise_paths")
    external_noise_paths: list[str] = []
    if raw_external_noise_paths is not None:
        if not isinstance(raw_external_noise_paths, list):
            errors.append("task_card.yaml external_noise_paths must be a list when provided")
        else:
            for i, raw in enumerate(raw_external_noise_paths, start=1):
                pat = _norm_path(str(raw))
                if not pat:
                    errors.append(f"task_card.yaml external_noise_paths[{i}] must be non-empty")
                    continue
                external_noise_paths.append(pat)

    ignore_patterns = tuple([*EPHEMERAL_IGNORE_PATTERNS, *external_noise_paths])

    changed_files = exe.get("changed_files") if isinstance(exe.get("changed_files"), list) else []
    for f in changed_files:
        fs = str(f).strip()
        if not fs:
            continue
        if not any(_match_allowed(fs, str(r)) for r in allowed_paths):
            errors.append(f"changed file outside allowed paths: {fs}")

    # Acceptance commands executed.
    required_cmds = task.get("acceptance_commands") if isinstance(task.get("acceptance_commands"), list) else []
    commands_run = exe.get("commands_run") if isinstance(exe.get("commands_run"), list) else []
    if not required_cmds:
        errors.append("task_card.yaml acceptance_commands must be a non-empty list")
    for rc in required_cmds:
        if not _contains_command(str(rc), [str(c) for c in commands_run]):
            errors.append(f"required acceptance command not found in executor report: {rc}")

    # Validator report structure and consistency.
    validator = val.get("validator") if isinstance(val.get("validator"), dict) else {}
    if str(validator.get("role", "")).strip() != "orchestrator_codex":
        errors.append("validator_report.yaml validator.role must be orchestrator_codex")
    status = str(val.get("status", "")).strip()
    if status not in ("pass", "fail"):
        errors.append("validator_report.yaml status must be pass|fail")
    checks = val.get("checks") if isinstance(val.get("checks"), list) else []
    names: set[str] = set()
    failed_names: set[str] = set()
    for ch in checks:
        if not isinstance(ch, dict):
            continue
        n = str(ch.get("name", "")).strip()
        if not n:
            continue
        names.add(n)
        if bool(ch.get("pass")) is not True:
            failed_names.add(n)
    missing_checks = sorted(REQUIRED_VALIDATOR_CHECKS - names)
    if missing_checks:
        errors.append(f"validator missing required checks: {missing_checks}")
    if status == "pass" and failed_names:
        errors.append(f"validator status=pass but failed checks present: {sorted(failed_names)}")

    # Evidence hardening check.
    evidence_policy = str(task.get("evidence_policy", EVIDENCE_POLICY_LEGACY)).strip().lower()
    if not evidence_policy:
        evidence_policy = EVIDENCE_POLICY_LEGACY
    if evidence_policy not in {EVIDENCE_POLICY_LEGACY, EVIDENCE_POLICY_HARDENED}:
        errors.append(f"task_card.yaml evidence_policy must be legacy|hardened, got {evidence_policy!r}")
    elif evidence_policy == EVIDENCE_POLICY_HARDENED:
        ef = task.get("evidence_files")
        if not isinstance(ef, dict):
            errors.append("task_card.yaml evidence_files must be mapping in hardened mode")
        else:
            resolved: dict[str, Path] = {}
            for key in REQUIRED_EVIDENCE_FILE_KEYS:
                raw = ef.get(key)
                if not isinstance(raw, str) or not raw.strip():
                    errors.append(f"task_card.yaml evidence_files.{key} is required in hardened mode")
                    continue
                p = _resolve_evidence_path(raw, repo_root=repo_root, packet_dir=packet_dir)
                if not p.is_file():
                    errors.append(f"missing hardened evidence file: {key} -> {p.as_posix()}")
                    continue
                resolved[key] = p

            if not errors:
                try:
                    before_doc = _load_json(resolved["workspace_before"])
                    after_doc = _load_json(resolved["workspace_after"])
                except ValueError as e:
                    errors.append(str(e))
                    before_doc = {}
                    after_doc = {}

                try:
                    before_files = _snapshot_files(before_doc, label="workspace_before")
                    after_files = _snapshot_files(after_doc, label="workspace_after")
                except ValueError as e:
                    errors.append(str(e))
                    before_files = {}
                    after_files = {}

                actual_changed = _compute_changed(before_files, after_files)
                actual_non_packet = {
                    p
                    for p in actual_changed
                    if not _is_packet_internal(p, packet_prefix)
                    and not _is_ignored_workspace_path(p, ignore_patterns=ignore_patterns)
                }
                reported_non_packet = {
                    _norm_path(str(x))
                    for x in changed_files
                    if (
                        str(x).strip()
                        and not _is_packet_internal(str(x), packet_prefix)
                        and not _is_ignored_workspace_path(str(x), ignore_patterns=ignore_patterns)
                    )
                }
                if actual_non_packet != reported_non_packet:
                    missing_from_report = sorted(actual_non_packet - reported_non_packet)
                    extra_in_report = sorted(reported_non_packet - actual_non_packet)
                    errors.append(
                        "hardened changed_files mismatch: "
                        f"missing_from_report={missing_from_report}, extra_in_report={extra_in_report}"
                    )

                for f in sorted(actual_non_packet):
                    if not any(_match_allowed(f, str(r)) for r in allowed_paths):
                        errors.append(f"hardened actual changed file outside allowed paths: {f}")

                try:
                    rows = _load_jsonl(resolved["acceptance_log"])
                except ValueError as e:
                    errors.append(str(e))
                    rows = []

                successful_commands: list[str] = []
                for i, row in enumerate(rows, start=1):
                    cmd = str(row.get("command", "")).strip()
                    code = _coerce_exit_code(row.get("exit_code"))
                    started = str(row.get("started_at", "")).strip()
                    ended = str(row.get("ended_at", "")).strip()
                    if not cmd:
                        errors.append(f"acceptance log row {i} missing command")
                        continue
                    if code is None:
                        errors.append(f"acceptance log row {i} has invalid exit_code")
                        continue
                    if not started or not ended:
                        errors.append(f"acceptance log row {i} missing started_at/ended_at")
                        continue
                    if code == 0:
                        successful_commands.append(cmd)

                for rc in required_cmds:
                    if not _contains_command(str(rc), successful_commands):
                        errors.append(f"required acceptance command missing successful log entry: {rc}")

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 2

    print("subagent packet: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
