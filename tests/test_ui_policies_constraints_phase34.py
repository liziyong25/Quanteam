from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from quant_eam.api.app import app


def _find_wequant_doc(suffix: str) -> Path:
    matches = sorted(p for p in Path("docs/00_overview").glob(f"*{suffix}") if p.is_file())
    assert matches, f"required source doc missing: *{suffix}"
    return matches[0]


def _clean_md(text: str) -> str:
    s = str(text).strip()
    s = re.sub(r"`([^`]+)`", r"\1", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
    s = re.sub(r"\*([^*]+)\*", r"\1", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _extract_whole_view_constraints(path: Path) -> list[dict[str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    rows: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw in lines:
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            in_section = ("系统硬约束" in line) or ("Hard Constraints" in line)
            continue
        if not in_section or not line or line == "---":
            continue
        m = re.match(r"^(\d+)\)\s*(.+)$", line)
        if m:
            if current:
                rows.append(current)
            current = {"item": _clean_md(m.group(2)), "detail": ""}
            continue
        if current and line.startswith("- "):
            detail = _clean_md(line[2:])
            if detail:
                current["detail"] = (current["detail"] + " " + detail).strip()
    if current:
        rows.append(current)
    assert rows, "whole view section 1 constraints extraction must not be empty"
    return rows


def _extract_playbook_rules(path: Path, section: str) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    start = -1
    for i, raw in enumerate(lines):
        line = raw.strip()
        if line.startswith("### ") and section in line:
            start = i + 1
            break
    assert start >= 0, f"playbook section {section} not found"

    out: list[str] = []
    for raw in lines[start:]:
        line = raw.strip()
        if line.startswith("### ") or line.startswith("## "):
            break
        if line.startswith("- "):
            out.append(_clean_md(line[2:]))
    assert out, f"playbook section {section} extraction must not be empty"
    return out


def test_policies_constraints_page_renders_section_rules_as_readonly_evidence() -> None:
    client = TestClient(app)
    whole_view = _find_wequant_doc("Whole View Framework.md")
    playbook = _find_wequant_doc("Implementation Phases Playbook.md")
    constraints = _extract_whole_view_constraints(whole_view)
    task_rules = _extract_playbook_rules(playbook, "0.1")
    quality_rules = _extract_playbook_rules(playbook, "0.2")

    r = client.get("/ui/policies-constraints")
    assert r.status_code == 200
    text = r.text

    assert "Policies and Constraints Evidence" in text
    assert "GET/HEAD only" in text
    assert "no write actions" in text
    assert "no holdout expansion" in text
    assert "Whole View Hard Constraints" in text
    assert "Playbook Task Rules (0.1)" in text
    assert "Playbook Quality Gates (0.2)" in text
    assert "Whole View Framework.md" in text
    assert "Implementation Phases Playbook.md" in text
    assert "<form" not in text.lower()
    assert "method=\"post\"" not in text.lower()

    for row in constraints:
        assert row["item"] in text
        if row["detail"]:
            assert row["detail"] in text
    for item in task_rules:
        assert item in text
    for item in quality_rules:
        assert item in text

    assert "data-testid=\"whole-view-hard-constraint-1\"" in text
    assert "data-testid=\"combined-row-1\"" in text
    assert re.search(r'data-testid="whole-view-count">\s*6\s*<', text)
    assert re.search(rf'data-testid="playbook-task-count">\s*{len(task_rules)}\s*<', text)
    assert re.search(rf'data-testid="playbook-quality-count">\s*{len(quality_rules)}\s*<', text)


def test_policies_constraints_page_head_and_post_semantics() -> None:
    client = TestClient(app)
    assert client.head("/ui/policies-constraints").status_code == 200
    assert client.post("/ui/policies-constraints").status_code == 405
