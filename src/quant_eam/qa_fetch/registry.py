from __future__ import annotations

import ast
import re
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from .source import SOURCE_MONGO, SOURCE_MYSQL


@dataclass(frozen=True)
class FetchMapping:
    source: str
    source_file: str
    old_name: str
    proposed_name: str
    domain: str
    collision: bool
    keep_alias: bool
    status: str
    notes: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _to_repo_rel(path: Path) -> str:
    return path.resolve().relative_to(_repo_root()).as_posix()


def _snake_case(name: str) -> str:
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    return s2.lower()


def _domain_from_name(name: str) -> str:
    n = _snake_case(name)
    if "dk" in n:
        return "dk"
    if "crypto" in n:
        return "crypto"
    if "ctp_" in n:
        return "future"
    if (
        "bond" in n
        or "valuation" in n
        or "cfets" in n
        or "repo" in n
        or "credit" in n
        or "issue" in n
        or "quote" in n
        or "clean_transaction" in n
        or "realtime_transaction" in n
        or "realtime_min" in n
        or "settlement" in n
        or "realtime_bid" in n
        or "wind_" in n
    ):
        return "bond"
    if "stock" in n or "hkstock" in n or "xdxr" in n:
        return "stock"
    if "etf" in n:
        return "etf"
    if "future" in n:
        return "future"
    if "index" in n:
        return "index"
    if "financial" in n:
        return "financial"
    return "generic"


def _iter_fetch_defs(paths: Iterable[Path], *, allow_prefixes: tuple[str, ...]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for path in paths:
        if not path.is_file():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name.startswith(allow_prefixes):
                out.append((node.name, _to_repo_rel(path)))
    return out


def _wequant_sources() -> list[Path]:
    root = _repo_root()
    return [
        root
        / "src"
        / "quant_eam"
        / "qa_fetch"
        / "providers"
        / "mongo_fetch"
        / "wefetch"
        / "query.py",
        root
        / "src"
        / "quant_eam"
        / "qa_fetch"
        / "providers"
        / "mongo_fetch"
        / "wefetch"
        / "query_advance.py",
    ]


def _wbdata_sources() -> list[Path]:
    root = _repo_root()
    return [
        root
        / "src"
        / "quant_eam"
        / "qa_fetch"
        / "providers"
        / "mysql_fetch"
        / "bond_fetch.py",
        root
        / "src"
        / "quant_eam"
        / "qa_fetch"
        / "providers"
        / "mysql_fetch"
        / "report_fetch.py",
    ]


@lru_cache(maxsize=1)
def build_fetch_mappings() -> tuple[FetchMapping, ...]:
    wequant_defs = sorted(_iter_fetch_defs(_wequant_sources(), allow_prefixes=("fetch_",)))
    wbdata_defs = sorted(_iter_fetch_defs(_wbdata_sources(), allow_prefixes=("fetch_",)))

    wq_keys = {_snake_case(name) for name, _ in wequant_defs}
    wb_keys = {_snake_case(name) for name, _ in wbdata_defs}
    collisions = wq_keys.intersection(wb_keys)

    rows: list[FetchMapping] = []

    for old_name, source_file in wequant_defs:
        old_key = _snake_case(old_name)
        collision = old_key in collisions
        notes = "mongo_fetch priority for fetch_* (collision with mysql_fetch)" if collision else "standard mapping"
        rows.append(
            FetchMapping(
                source=SOURCE_MONGO,
                source_file=source_file,
                old_name=old_name,
                proposed_name=old_key,
                domain=_domain_from_name(old_name),
                collision=collision,
                keep_alias=True,
                status="review",
                notes=notes,
            )
        )

    for old_name, source_file in wbdata_defs:
        old_key = _snake_case(old_name)
        collision = old_key in collisions
        notes = (
            "collision with mongo_fetch; keep wb_fetch_* alias during migration"
            if collision
            else "standard mapping"
        )
        rows.append(
            FetchMapping(
                source=SOURCE_MYSQL,
                source_file=source_file,
                old_name=old_name,
                proposed_name=old_key,
                domain=_domain_from_name(old_name),
                collision=collision,
                keep_alias=True,
                status="review",
                notes=notes,
            )
        )

    rows.sort(key=lambda r: (r.source, _snake_case(r.old_name)))
    return tuple(rows)


def collision_keys() -> tuple[str, ...]:
    rows = build_fetch_mappings()
    keys = {_snake_case(r.old_name) for r in rows if r.collision}
    return tuple(sorted(keys))


def mapping_dicts() -> list[dict[str, object]]:
    return [asdict(r) for r in build_fetch_mappings()]


def render_rename_matrix_markdown(rows: Iterable[FetchMapping] | None = None) -> str:
    items = list(rows if rows is not None else build_fetch_mappings())
    wq_count = sum(1 for r in items if r.source == SOURCE_MONGO)
    wb_count = sum(1 for r in items if r.source == SOURCE_MYSQL)
    wq_keys = {_snake_case(r.old_name) for r in items if r.source == SOURCE_MONGO}
    wb_keys = {_snake_case(r.old_name) for r in items if r.source == SOURCE_MYSQL}
    collision_keys = wq_keys.intersection(wb_keys)
    collisions = sorted(collision_keys)

    lines: list[str] = []
    lines.append("# QA Fetch Rename Matrix (Draft v1)")
    lines.append("")
    lines.append("This document is auto-generated for review before bulk rename.")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- mongo_fetch functions: `{wq_count}`")
    lines.append(f"- mysql_fetch functions: `{wb_count}`")
    if collisions:
        lines.append(f"- collisions: `{len(collisions)}` (`{', '.join(collisions)}`)")
    else:
        lines.append("- collisions: `0`")
    lines.append("- collision rule: `mongo_fetch` keeps canonical `fetch_*`; mysql keeps `wb_fetch_*` alias")
    lines.append("")
    lines.append("## Review Status Values")
    lines.append("- `accepted`: use proposed name as-is")
    lines.append("- `modify`: rename manually")
    lines.append("- `drop`: exclude from unified qa_fetch API")
    lines.append("")
    lines.append("## Matrix")
    lines.append("")
    lines.append("| source | old_name | proposed_name | domain | collision | keep_alias | status | notes |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for r in items:
        row_collision = "yes" if _snake_case(r.old_name) in collision_keys else "no"
        lines.append(
            "| "
            + " | ".join(
                [
                    r.source,
                    f"`{r.old_name}`",
                    f"`{r.proposed_name}`",
                    r.domain,
                    row_collision,
                    "yes" if r.keep_alias else "no",
                    r.status,
                    f"{r.notes}; source=`{r.source_file}`",
                ]
            )
            + " |"
        )
    lines.append("")
    lines.append("## Deprecation Plan (Migration Phase)")
    lines.append("- keep old names as aliases until dual-DB smoke + notebook validation are stable")
    lines.append("- after approval, remove old aliases in final cutover")
    lines.append("")
    return "\n".join(lines)
