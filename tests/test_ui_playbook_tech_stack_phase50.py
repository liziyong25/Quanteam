from __future__ import annotations

import html
import re
from pathlib import Path

from fastapi.testclient import TestClient

from quant_eam.api.app import app


SECTION1_RE = re.compile(r"^##\s*1(?:\s|[.:：])")
SUBSECTION11_RE = re.compile(r"^###\s*1\.1(?:\s|[.:：])")
SUBSECTION12_RE = re.compile(r"^###\s*1\.2(?:\s|[.:：])")


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


def _extract_playbook_section1_rows(path: Path) -> tuple[str, str, str, list[str], list[str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    section = ""
    foundation_section = ""
    service_section = ""
    active = ""
    foundation_rows: list[str] = []
    service_rows: list[str] = []

    for raw in lines:
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            in_section = bool(SECTION1_RE.match(line)) and (("技术栈" in line) or ("stack" in line.lower()))
            if in_section:
                section = _clean_md(line[3:])
            continue
        if not in_section:
            continue

        if line.startswith("### "):
            header = _clean_md(line[4:])
            if SUBSECTION11_RE.match(line):
                active = "foundation"
                foundation_section = header
            elif SUBSECTION12_RE.match(line):
                active = "service"
                service_section = header
            else:
                active = ""
            continue

        if not line.startswith("- "):
            continue

        item = _clean_md(line[2:])
        if not item:
            continue
        if active == "foundation":
            foundation_rows.append(item)
        elif active == "service":
            service_rows.append(item)

    assert section, "Playbook section 1 heading extraction must not be empty"
    assert foundation_section, "Playbook section 1.1 heading extraction must not be empty"
    assert service_section, "Playbook section 1.2 heading extraction must not be empty"
    assert foundation_rows, "Playbook section 1.1 foundation rows must not be empty"
    assert service_rows, "Playbook section 1.2 service rows must not be empty"
    assert any("Python 3.11+" in row for row in foundation_rows), "section 1.1 must include Python baseline"
    assert any("pytest" in row.lower() for row in foundation_rows), "section 1.1 must include pytest baseline"
    assert any("fastapi" in row.lower() for row in service_rows), "section 1.2 must include FastAPI service baseline"
    return section, foundation_section, service_section, foundation_rows, service_rows


def test_playbook_tech_stack_page_renders_playbook_sections1_11_12_readonly_evidence() -> None:
    playbook_doc = _find_doc(suffix="Implementation Phases Playbook.md")
    section, foundation_section, service_section, foundation_rows, service_rows = _extract_playbook_section1_rows(
        playbook_doc
    )

    client = TestClient(app)
    r = client.get("/ui/playbook-tech-stack")
    assert r.status_code == 200
    text = r.text
    unescaped = html.unescape(text)

    assert "Playbook Technical Stack Baseline Read-Only Evidence" in text
    assert "GET/HEAD only" in text
    assert "no write actions" in text
    assert "section 1/1.1/1.2 evidence only" in text
    assert "Playbook Section 1 Technical Stack Baseline" in text
    assert "Playbook Section 1.1 Foundation Stack" in text
    assert "Playbook Section 1.2 Service Stack" in text
    assert section in unescaped
    assert foundation_section in unescaped
    assert service_section in unescaped
    assert "/ui/playbook-tech-stack" in text
    assert "docs/00_overview" in text
    assert "Implementation Phases Playbook.md" in text
    assert "<form" not in text.lower()
    assert 'method="post"' not in text.lower()

    for row in foundation_rows:
        assert row in unescaped
    for row in service_rows:
        assert row in unescaped

    assert re.search(rf'data-testid="playbook-tech-stack-foundation-total">\s*{len(foundation_rows)}\s*<', text)
    assert re.search(rf'data-testid="playbook-tech-stack-service-total">\s*{len(service_rows)}\s*<', text)
    assert 'data-testid="playbook-tech-stack-foundation-row-1"' in text
    assert 'data-testid="playbook-tech-stack-service-row-1"' in text


def test_playbook_tech_stack_page_head_and_post_semantics() -> None:
    client = TestClient(app)
    assert client.head("/ui/playbook-tech-stack").status_code == 200
    assert client.post("/ui/playbook-tech-stack").status_code == 405
