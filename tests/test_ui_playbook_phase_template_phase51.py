from __future__ import annotations

import html
import re
from pathlib import Path

from fastapi.testclient import TestClient

from quant_eam.api.app import app


SECTION2_RE = re.compile(r"^##\s*2(?:\s|[.:：])")


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


def _extract_playbook_section2_phase_template(path: Path) -> tuple[str, str, str, list[str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    in_template = False
    section = ""
    intro = ""
    template_section = ""
    template_rows: list[str] = []

    for raw in lines:
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            in_section = bool(SECTION2_RE.match(line)) and ("phase" in line.lower()) and (
                ("模板" in line) or ("template" in line.lower())
            )
            if in_section:
                section = _clean_md(line[3:])
            continue
        if (not in_section) or (not line) or (line == "---"):
            continue

        if line.startswith(">"):
            quote = _clean_md(line.lstrip(">").strip())
            if quote and not intro:
                intro = quote
            continue

        if line.startswith("### "):
            header = _clean_md(line[4:])
            in_template = ("phase" in header.lower()) and (("标准输出结构" in header) or ("template" in header.lower()))
            if in_template:
                template_section = header
            continue

        if not in_template:
            continue

        m = re.match(r"^([1-9][0-9]*)[.)]\s*(.+)$", line)
        if not m:
            continue
        item = _clean_md(m.group(2))
        if item:
            template_rows.append(item)

    assert section, "Playbook section 2 heading extraction must not be empty"
    assert intro, "Playbook section 2 intro quote extraction must not be empty"
    assert template_section, "Playbook section 2 template heading extraction must not be empty"
    assert len(template_rows) >= 8, "Playbook section 2 template rows must include the full Phase-X structure"
    expected_keywords = (
        "目标（Goal）",
        "背景（Background）",
        "范围（Scope / Out‑of‑Scope）",
        "实施方案（Implementation Plan）",
        "编码内容（Code Deliverables）",
        "文档编写（Docs Deliverables）",
        "验收标准（Acceptance / DoD）",
        "Codex 任务卡（Task Card）",
    )
    for key in expected_keywords:
        assert any(key in row for row in template_rows), f"section 2 template rows must include {key}"
    return section, intro, template_section, template_rows


def test_playbook_phase_template_page_renders_section2_structure_readonly_evidence() -> None:
    playbook_doc = _find_doc(suffix="Implementation Phases Playbook.md")
    section, intro, template_section, template_rows = _extract_playbook_section2_phase_template(playbook_doc)

    client = TestClient(app)
    r = client.get("/ui/playbook-phase-template")
    assert r.status_code == 200
    text = r.text
    unescaped = html.unescape(text)

    assert "Playbook Phase Template Structure Read-Only Evidence" in text
    assert "GET/HEAD only" in text
    assert "no write actions" in text
    assert "section 2 evidence only" in text
    assert "Playbook Section 2 Phase Template Structure" in text
    assert section in unescaped
    assert intro in unescaped
    assert template_section in unescaped
    assert "/ui/playbook-phase-template" in text
    assert "docs/00_overview" in text
    assert "Implementation Phases Playbook.md" in text
    assert "<form" not in text.lower()
    assert 'method="post"' not in text.lower()

    for row in template_rows:
        assert row in unescaped

    assert re.search(rf'data-testid="playbook-phase-template-total">\s*{len(template_rows)}\s*<', text)
    assert 'data-testid="playbook-phase-template-row-1"' in text


def test_playbook_phase_template_page_head_and_post_semantics() -> None:
    client = TestClient(app)
    assert client.head("/ui/playbook-phase-template").status_code == 200
    assert client.post("/ui/playbook-phase-template").status_code == 405
