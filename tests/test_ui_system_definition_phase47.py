from __future__ import annotations

import html
import re
from pathlib import Path

from fastapi.testclient import TestClient

from quant_eam.api.app import app


SECTION0_RE = re.compile(r"^##\s*0(?:\s|[.:：])")
SECTION2_RE = re.compile(r"^##\s*2(?:\s|[.:：])")
PLANE_ROW_RE = re.compile(r"^\*\*([^*]+)\*\*\s*[：:]\s*(.+)$")


def _clean_md(text: str) -> str:
    s = str(text).strip()
    s = re.sub(r"`([^`]+)`", r"\1", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
    s = re.sub(r"\*([^*]+)\*", r"\1", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _find_whole_view_root_doc() -> Path:
    root_matches = sorted(p for p in Path(".").glob("*Whole View Framework.md") if p.is_file())
    if root_matches:
        return root_matches[0]
    assert False, "required root Whole View framework markdown is missing"


def _extract_whole_view_section0_definition(path: Path) -> tuple[str, list[str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    statement = ""
    rules: list[str] = []

    for raw in lines:
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            in_section = bool(SECTION0_RE.match(line)) and (("Definition" in line) or ("系统" in line))
            continue
        if (not in_section) or (not line) or (line == "---"):
            continue

        if line.startswith("- "):
            item = _clean_md(line[2:])
            if item:
                rules.append(item)
            continue

        if (not statement) and ("Experience Asset Machine" in line or "可审计" in line):
            statement = _clean_md(line)

    assert statement, "Whole View section 0 definition statement must not be empty"
    assert rules, "Whole View section 0 definition rules must not be empty"
    assert any("Web UI" in row for row in rules), "section 0 rules must include Web UI review flow"
    assert any("GateRunner" in row for row in rules), "section 0 rules must include GateRunner deterministic verdict"
    return statement, rules


def _extract_whole_view_section2_planes(path: Path) -> list[dict[str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    rows: list[dict[str, str]] = []

    for raw in lines:
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            in_section = bool(SECTION2_RE.match(line)) and (("平面" in line) or ("Planes" in line))
            continue
        if (not in_section) or (not line) or (line == "---"):
            continue
        if not line.startswith("- "):
            continue

        body = line[2:].strip()
        m = PLANE_ROW_RE.match(body)
        if not m:
            continue
        rows.append({"plane": _clean_md(m.group(1)), "detail": _clean_md(m.group(2))})

    assert rows, "Whole View section 2 plane extraction must not be empty"
    assert len(rows) == 5, "Whole View section 2 must provide exactly five planes"
    plane_names = [row["plane"] for row in rows]
    for expected in ("Data Plane", "Backtest Plane", "Deterministic Kernel（真理层）", "Agents Plane", "UI Plane"):
        assert expected in plane_names, f"section 2 must include {expected}"
    return rows


def test_system_definition_page_renders_sections0_and2_readonly_evidence() -> None:
    whole_view_doc = _find_whole_view_root_doc()
    definition_statement, definition_rules = _extract_whole_view_section0_definition(whole_view_doc)
    plane_rows = _extract_whole_view_section2_planes(whole_view_doc)

    client = TestClient(app)
    r = client.get("/ui/system-definition")
    assert r.status_code == 200
    text = r.text
    unescaped = html.unescape(text)

    assert "Whole View System Definition and Five Planes Read-Only Evidence" in text
    assert "GET/HEAD only" in text
    assert "no write actions" in text
    assert "section 0/2 evidence only" in text
    assert "Whole View Section 0 System Definition" in text
    assert "Whole View Section 2 Five Planes Architecture" in text
    assert "/ui/system-definition" in text
    assert "Quant‑EAM Whole View Framework.md" in unescaped
    assert "<form" not in text.lower()
    assert 'method="post"' not in text.lower()

    assert definition_statement in unescaped
    for rule in definition_rules:
        assert rule in unescaped
    for row in plane_rows:
        assert row["plane"] in unescaped
        assert row["detail"] in unescaped

    assert re.search(rf'data-testid="system-definition-rule-total">\s*{len(definition_rules)}\s*<', text)
    assert re.search(rf'data-testid="system-definition-plane-total">\s*{len(plane_rows)}\s*<', text)
    assert 'data-testid="system-definition-rule-row-1"' in text
    assert 'data-testid="system-definition-plane-row-1"' in text


def test_system_definition_page_head_and_post_semantics() -> None:
    client = TestClient(app)
    assert client.head("/ui/system-definition").status_code == 200
    assert client.post("/ui/system-definition").status_code == 405
