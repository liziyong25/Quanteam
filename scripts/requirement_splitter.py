#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml


HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*$")
BULLET_RE = re.compile(r"^\s*[-*]\s+(.+?)\s*$")
ENUM_RE = re.compile(r"^\s*\d+[.)]\s+(.+?)\s*$")
INLINE_CODE_RE = re.compile(r"`([^`]+)`")

DEFAULT_CLAUSE_KEEP_RE = (
    r"(?i)\b(?:FR|NFR|DOD|API|REQ|RISK|GATE)-?\d{1,4}\b",
    r"(?i)\b(?:must|shall|required|禁止|必须|应当|验收|接口|路由|e2e|集成测试)\b",
)


def load_splitter_profiles(config_path: Path) -> dict[str, dict[str, Any]]:
    if not config_path.is_file():
        return {}
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {}
    rows = raw.get("profiles")
    if not isinstance(rows, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for key, val in rows.items():
        if isinstance(key, str) and isinstance(val, dict):
            out[key] = val
    return out


def _compile_regex_list(patterns: list[str]) -> list[re.Pattern[str]]:
    out: list[re.Pattern[str]] = []
    for raw in patterns:
        try:
            out.append(re.compile(str(raw)))
        except re.error:
            continue
    return out


def _match_any(text: str, regs: list[re.Pattern[str]]) -> bool:
    if not regs:
        return False
    return any(r.search(text) for r in regs)


def _normalize_clause(text: str) -> str:
    s = INLINE_CODE_RE.sub(r"\1", str(text))
    s = s.replace("**", " ").replace("__", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _merge_profile(prefix: str, profiles: dict[str, dict[str, Any]] | None) -> dict[str, Any]:
    if not profiles:
        return {}
    merged: dict[str, Any] = {}
    default = profiles.get("default", {})
    if isinstance(default, dict):
        merged.update(default)
    specific = profiles.get(prefix, {})
    if isinstance(specific, dict):
        merged.update(specific)
    return merged


def extract_requirement_clauses(
    *,
    source_path: Path,
    prefix: str,
    source_document: str | None = None,
    profiles: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if not source_path.is_file():
        raise FileNotFoundError(source_path.as_posix())

    profile = _merge_profile(prefix, profiles)
    include_heading_re = _compile_regex_list(
        [str(x) for x in (profile.get("include_heading_regex") or []) if isinstance(x, str)]
    )
    exclude_heading_re = _compile_regex_list(
        [str(x) for x in (profile.get("exclude_heading_regex") or []) if isinstance(x, str)]
    )
    include_clause_re = _compile_regex_list(
        [str(x) for x in (profile.get("include_clause_regex") or []) if isinstance(x, str)]
    )
    exclude_clause_re = _compile_regex_list(
        [str(x) for x in (profile.get("exclude_clause_regex") or []) if isinstance(x, str)]
    )
    keep_tag_patterns = [str(x) for x in (profile.get("keep_clause_regex") or []) if isinstance(x, str)]
    if not keep_tag_patterns:
        keep_tag_patterns = list(DEFAULT_CLAUSE_KEEP_RE)
    keep_clause_re = _compile_regex_list(keep_tag_patterns)

    min_len = int(profile.get("min_clause_len") or 10)
    max_requirements = int(profile.get("max_requirements") or 0)
    keep_headings = bool(profile.get("keep_headings", True))
    keep_bullets = bool(profile.get("keep_bullets", True))
    dedup = bool(profile.get("dedup", True))
    chain_dependencies = bool(profile.get("chain_dependencies", True))

    lines = source_path.read_text(encoding="utf-8").splitlines()
    rows: list[dict[str, Any]] = []
    heading_stack: list[str] = []
    last_heading_level = 0
    last_section_req_id = ""
    last_doc_req_id = ""
    seen: set[str] = set()
    idx = 1
    doc_label = source_document or source_path.as_posix()

    def section_allowed(section_title: str) -> bool:
        if _match_any(section_title, exclude_heading_re):
            return False
        if not include_heading_re:
            return True
        return _match_any(section_title, include_heading_re)

    def clause_allowed(clause: str, *, in_allowed_section: bool) -> bool:
        if len(clause) < min_len:
            return False
        if _match_any(clause, exclude_clause_re):
            return False
        if in_allowed_section:
            return True
        if _match_any(clause, include_clause_re):
            return True
        return _match_any(clause, keep_clause_re)

    def append_row(*, lineno: int, clause: str, depends_on: list[str]) -> str:
        nonlocal idx, last_doc_req_id
        norm = _normalize_clause(clause)
        if dedup:
            key = norm.casefold()
            if key in seen:
                return ""
            seen.add(key)
        req_id = f"{prefix}-{idx:03d}"
        idx += 1
        rows.append(
            {
                "req_id": req_id,
                "source_document": doc_label,
                "source_line": lineno,
                "clause": norm,
                "depends_on_req_ids": [x for x in depends_on if x],
                "status_now": "planned",
                "mapped_goal_ids": [],
                "capability_cluster_id": "",
            }
        )
        last_doc_req_id = req_id
        return req_id

    for lineno, line in enumerate(lines, start=1):
        if max_requirements > 0 and len(rows) >= max_requirements:
            break

        h = HEADING_RE.match(line)
        if h:
            level = len(h.group(1))
            title = _normalize_clause(h.group(2))
            if not title:
                continue
            if level <= last_heading_level:
                heading_stack = heading_stack[: level - 1]
            heading_stack.append(title)
            last_heading_level = level

            section_title = " / ".join(heading_stack)
            sec_allowed = section_allowed(section_title)
            if keep_headings and clause_allowed(section_title, in_allowed_section=sec_allowed):
                depends = [last_doc_req_id] if chain_dependencies and last_doc_req_id else []
                rid = append_row(lineno=lineno, clause=section_title, depends_on=depends)
                if rid:
                    last_section_req_id = rid
            continue

        m = BULLET_RE.match(line) or ENUM_RE.match(line)
        if not m or not keep_bullets:
            continue
        clause = _normalize_clause(m.group(1))
        if not clause:
            continue
        section_title = " / ".join(heading_stack)
        sec_allowed = section_allowed(section_title) if section_title else False
        if not clause_allowed(clause, in_allowed_section=sec_allowed):
            continue
        depends = [last_section_req_id] if last_section_req_id else ([last_doc_req_id] if chain_dependencies and last_doc_req_id else [])
        append_row(lineno=lineno, clause=clause, depends_on=depends)

    return rows


def _cli() -> int:
    ap = argparse.ArgumentParser(description="Split requirement markdown into compact, machine-readable clause rows.")
    ap.add_argument("--source", required=True, help="Source markdown file path.")
    ap.add_argument("--prefix", required=True, help="Requirement id prefix, e.g. WV/QF/WB.")
    ap.add_argument(
        "--config",
        default="docs/12_workflows/requirement_splitter_profiles_v1.yaml",
        help="Splitter profile YAML path.",
    )
    ap.add_argument("--show", type=int, default=10, help="How many rows to print in preview output.")
    ap.add_argument("--json", action="store_true", help="Print rows as JSON.")
    args = ap.parse_args()

    cfg = Path(args.config)
    profiles = load_splitter_profiles(cfg)
    source = Path(args.source)
    rows = extract_requirement_clauses(
        source_path=source,
        prefix=str(args.prefix).strip(),
        source_document=source.as_posix(),
        profiles=profiles,
    )
    if args.json:
        print(json.dumps({"count": len(rows), "rows": rows[: max(0, int(args.show))]}, ensure_ascii=False, indent=2))
        return 0

    print(f"source={source.as_posix()}")
    print(f"prefix={args.prefix}")
    print(f"count={len(rows)}")
    for row in rows[: max(0, int(args.show))]:
        print(f"{row['req_id']}:{row['source_line']} {row['clause']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
