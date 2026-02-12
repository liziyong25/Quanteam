from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from dataclasses import replace
from typing import Iterable

from .registry import FetchMapping


ADV_ALLOWED_FREQ = {"day", "min", "transaction", "dk"}


def snake_case(name: str) -> str:
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    return s2.lower()


def normalize_fetch_name(name: str) -> str:
    normalized = snake_case(name)
    if normalized.startswith("fetch_"):
        return normalized
    return f"fetch_{normalized}"


def normalize_venue_suffix(name: str) -> str:
    # Normalize prefixed venue naming (fetch_cfets_*) to suffix naming (*_cfets).
    if name.startswith("fetch_cfets_"):
        stem = name[len("fetch_cfets_") :]
        if stem.endswith("_cfets"):
            return f"fetch_{stem}"
        return f"fetch_{stem}_cfets"
    return name


def adv_is_allowed(name: str) -> bool:
    n = snake_case(name)
    if not n.endswith("_adv"):
        return True
    parts = n.split("_")
    if len(parts) < 4 or parts[0] != "fetch":
        return False
    # fetch_<asset>_<freq>_adv => freq token is the token before adv.
    freq = parts[-2]
    return freq in ADV_ALLOWED_FREQ


def drop_adv_suffix(name: str) -> str:
    if name.endswith("_adv"):
        return name[: -len("_adv")]
    return name


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


@lru_cache(maxsize=1)
def _matrix_v3_rows() -> dict[tuple[str, str], dict[str, object]]:
    root = _repo_root()
    path = root / "docs" / "05_data_plane" / "qa_fetch_function_baseline_v1.md"
    if not path.is_file():
        # One-cycle compatibility path.
        path = root / "docs" / "05_data_plane" / "_draft_qa_fetch_rename_matrix_v3.md"
    if not path.is_file():
        return {}
    rows: dict[tuple[str, str], dict[str, object]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| "):
            continue
        if "source | old_name | proposed_name" in line or line.startswith("|---"):
            continue
        parts = [item.strip() for item in line.strip("|").split("|")]
        if len(parts) < 8:
            continue
        source = parts[0]
        old_name = parts[1].strip("`")
        proposed_name = parts[2].strip("`")
        keep_alias_text = parts[5].lower()
        status = parts[6].lower()
        notes = parts[7]
        if source not in {"wequant", "wbdata"} or not old_name.startswith("fetch_"):
            continue
        rows[(source, snake_case(old_name))] = {
            "old_name": old_name,
            "proposed_name": proposed_name,
            "keep_alias": keep_alias_text in {"yes", "true"},
            "status": status,
            "notes": notes,
        }
    return rows


@lru_cache(maxsize=1)
def _function_registry_active_set() -> set[tuple[str, str]]:
    path = _repo_root() / "docs" / "05_data_plane" / "qa_fetch_function_registry_v1.json"
    if not path.is_file():
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    rows = payload.get("functions")
    if not isinstance(rows, list):
        return set()
    out: set[tuple[str, str]] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        source = str(row.get("source", "")).strip().lower()
        function = str(row.get("function", "")).strip()
        status = str(row.get("status", "")).strip().lower()
        if source not in {"wequant", "wbdata"} or not function.startswith("fetch_"):
            continue
        if status not in {"active", "allow", "review", ""}:
            continue
        out.add((source, snake_case(function)))
    return out


def apply_user_policy(rows: Iterable[FetchMapping]) -> tuple[FetchMapping, ...]:
    matrix_rows = _matrix_v3_rows()
    active_set = _function_registry_active_set()
    out: list[FetchMapping] = []
    for row in rows:
        old_key = snake_case(row.old_name)
        matrix_entry = matrix_rows.get((row.source, old_key))
        proposed = normalize_fetch_name(row.old_name)
        keep_alias = row.keep_alias
        notes = row.notes
        status = "review"
        should_drop = False

        if matrix_entry is None:
            should_drop = True
            notes = "not included in v3 matrix baseline"
        else:
            proposed = normalize_fetch_name(str(matrix_entry.get("proposed_name", row.old_name)))
            proposed = normalize_venue_suffix(proposed)
            keep_alias = bool(matrix_entry.get("keep_alias", keep_alias))
            status = str(matrix_entry.get("status", "review"))
            notes = str(matrix_entry.get("notes", notes))
            if status == "drop":
                should_drop = True
                notes = "dropped by v3 matrix status"
            elif active_set and (row.source, old_key) not in active_set:
                should_drop = True
                notes = "not included in function_registry_v1 active set"

        if should_drop:
            out.append(
                replace(
                    row,
                    proposed_name=proposed,
                    keep_alias=keep_alias,
                    status="drop",
                    notes=notes,
                )
            )
            continue

        if (not adv_is_allowed(proposed)) and proposed.endswith("_adv"):
            proposed = drop_adv_suffix(proposed)
            notes = f"adv removed by naming rule -> `{proposed}`"
        out.append(
            replace(
                row,
                proposed_name=proposed,
                keep_alias=keep_alias,
                status=status,
                notes=notes,
            )
        )
    return tuple(out)


def active_rows(rows: Iterable[FetchMapping]) -> tuple[FetchMapping, ...]:
    return tuple(row for row in apply_user_policy(rows) if row.status != "drop")
