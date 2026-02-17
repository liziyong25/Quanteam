from __future__ import annotations

from pathlib import Path

from scripts.requirement_splitter import extract_requirement_clauses, load_splitter_profiles


def test_splitter_profile_compresses_workbench_doc() -> None:
    repo = Path(__file__).resolve().parents[1]
    cfg = repo / "docs/12_workflows/requirement_splitter_profiles_v1.yaml"
    src = repo / "docs/00_overview/workbench_ui_productization_v1.md"
    profiles = load_splitter_profiles(cfg)
    rows = extract_requirement_clauses(
        source_path=src,
        prefix="WB",
        source_document="docs/00_overview/workbench_ui_productization_v1.md",
        profiles=profiles,
    )
    assert rows
    assert len(rows) <= 72
    assert any("FR-001" in str(x.get("clause") or "") for x in rows)


def test_splitter_deduplicates_repeated_clauses(tmp_path: Path) -> None:
    source = tmp_path / "demo.md"
    source.write_text(
        "# Section\n- Same requirement clause appears here.\n- Same requirement clause appears here.\n",
        encoding="utf-8",
    )
    rows = extract_requirement_clauses(
        source_path=source,
        prefix="TST",
        profiles={"default": {"keep_headings": True, "keep_bullets": True, "dedup": True, "min_clause_len": 10}},
    )
    clauses = [str(x.get("clause") or "") for x in rows]
    assert clauses.count("Same requirement clause appears here.") == 1
