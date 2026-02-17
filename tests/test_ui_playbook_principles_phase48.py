from __future__ import annotations

import html
import re
from pathlib import Path

from fastapi.testclient import TestClient

from quant_eam.api.app import app


SECTION0_RE = re.compile(r"^##\s*0(?:\s|[.:：])")
SUBSECTION01_RE = re.compile(r"^###\s*0\.1(?:\s|[.:：])")
SUBSECTION02_RE = re.compile(r"^###\s*0\.2(?:\s|[.:：])")


def _clean_md(text: str) -> str:
    s = str(text).strip()
    s = re.sub(r"`([^`]+)`", r"\1", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
    s = re.sub(r"\*([^*]+)\*", r"\1", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _find_doc(*, suffix: str) -> Path:
    for base in (Path("docs/00_overview"), Path(".")):
        matches = sorted(p for p in base.glob(f"*{suffix}") if p.is_file())
        if matches:
            return matches[0]
    assert False, f"required source doc missing: *{suffix}"


def _extract_playbook_section0_and_02(path: Path) -> tuple[str, str, list[str], list[str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    in_quality = False
    section = ""
    quality_section = ""
    principles: list[str] = []
    quality_gates: list[str] = []

    for raw in lines:
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            in_section = bool(SECTION0_RE.match(line)) and ("施工总原则" in line or "Codex" in line)
            if in_section:
                section = _clean_md(line[3:])
            continue
        if (not in_section) or (not line) or (line == "---"):
            continue
        if line.startswith("### "):
            if SUBSECTION02_RE.match(line):
                in_quality = True
                quality_section = _clean_md(line[4:])
            elif SUBSECTION01_RE.match(line):
                in_quality = False
            continue
        if not line.startswith("- "):
            continue

        item = _clean_md(line[2:])
        if not item:
            continue
        if in_quality:
            quality_gates.append(item)
        else:
            principles.append(item)

    assert section, "Playbook section 0 heading extraction must not be empty"
    assert quality_section, "Playbook section 0.2 heading extraction must not be empty"
    assert principles, "Playbook section 0.1 principle extraction must not be empty"
    assert quality_gates, "Playbook section 0.2 quality gate extraction must not be empty"
    assert any("一个模块目录" in row for row in principles), "section 0.1 must include single-module boundary rule"
    assert any("pytest -q" in row for row in quality_gates), "section 0.2 must include pytest quality gate"
    assert any("schema" in row.lower() for row in quality_gates), "section 0.2 must include schema validation gate"
    return section, quality_section, principles, quality_gates


def test_playbook_principles_page_renders_playbook_sections0_and02_readonly_evidence() -> None:
    playbook_doc = _find_doc(suffix="Implementation Phases Playbook.md")
    section, quality_section, principles, quality_gates = _extract_playbook_section0_and_02(playbook_doc)

    client = TestClient(app)
    r = client.get("/ui/playbook-principles")
    assert r.status_code == 200
    text = r.text
    unescaped = html.unescape(text)

    assert "Playbook Construction Principles and Quality Gates Read-Only Evidence" in text
    assert "GET/HEAD only" in text
    assert "no write actions" in text
    assert "section 0/0.2 evidence only" in text
    assert "Playbook Section 0 Construction Principles" in text
    assert "Playbook Section 0.2 Global Quality Gates" in text
    assert section in unescaped
    assert quality_section in unescaped
    assert "/ui/playbook-principles" in text
    assert "docs/00_overview" in text
    assert "Implementation Phases Playbook.md" in text
    assert "<form" not in text.lower()
    assert 'method="post"' not in text.lower()

    for row in principles:
        assert row in unescaped
    for row in quality_gates:
        assert row in unescaped

    assert re.search(rf'data-testid="playbook-principles-total">\s*{len(principles)}\s*<', text)
    assert re.search(rf'data-testid="playbook-quality-total">\s*{len(quality_gates)}\s*<', text)
    assert 'data-testid="playbook-principles-row-1"' in text
    assert 'data-testid="playbook-quality-row-1"' in text


def test_playbook_principles_page_head_and_post_semantics() -> None:
    client = TestClient(app)
    assert client.head("/ui/playbook-principles").status_code == 200
    assert client.post("/ui/playbook-principles").status_code == 405
