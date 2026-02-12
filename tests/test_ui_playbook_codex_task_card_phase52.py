from __future__ import annotations

import html
import re
from pathlib import Path

from fastapi.testclient import TestClient

from quant_eam.api.app import app


SECTION4_RE = re.compile(r"^##\s*4(?:\s|[.:：])")


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


def _extract_playbook_section4_codex_task_card(path: Path) -> tuple[str, str, str, list[tuple[str, str]], list[str], list[str], list[str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    in_template = False
    section = ""
    intro = ""
    template_section = ""
    field_rows: list[tuple[str, str]] = []
    must_rows: list[str] = []
    forbidden_rows: list[str] = []
    acceptance_rows: list[str] = []
    list_mode = ""

    for raw in lines:
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            in_section = bool(SECTION4_RE.match(line)) and (("任务卡" in line) or ("task card" in line.lower()))
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
            in_template = ("codex" in header.lower()) and (("task card" in header.lower()) or ("任务卡" in header))
            if in_template:
                template_section = header
            list_mode = ""
            continue

        if not in_template:
            continue

        row = re.match(r"^\*\*([^*]+)\*\*[:：]\s*(.*)$", line)
        if row:
            label = _clean_md(row.group(1))
            value = _clean_md(row.group(2))
            if "必须实现" in label:
                list_mode = "must"
            elif "禁止项" in label:
                list_mode = "forbidden"
            elif "验收命令" in label:
                list_mode = "acceptance"
            else:
                list_mode = ""
                field_rows.append((label, value))
            continue

        if not line.startswith("- "):
            continue

        item = _clean_md(line[2:])
        if not item:
            continue
        if list_mode == "must":
            must_rows.append(item)
        elif list_mode == "forbidden":
            forbidden_rows.append(item)
        elif list_mode == "acceptance":
            acceptance_rows.append(item)

    assert section, "Playbook section 4 heading extraction must not be empty"
    assert intro, "Playbook section 4 intro quote extraction must not be empty"
    assert template_section, "Playbook section 4 task-card heading extraction must not be empty"
    assert len(field_rows) >= 4, "Playbook section 4 task-card fields must include the four core fields"
    assert len(must_rows) >= 4, "Playbook section 4 must-implement list must include all required rows"
    assert len(forbidden_rows) >= 4, "Playbook section 4 forbidden list must include all required rows"
    assert len(acceptance_rows) >= 4, "Playbook section 4 acceptance list must include all required rows"

    expected_field_labels = ("任务名", "修改范围", "目标", "输入/输出 Contract")
    for key in expected_field_labels:
        assert any(key in label for label, _ in field_rows), f"section 4 fields must include {key}"

    expected_must_keywords = ("功能点 A/B/C", "CLI 命令", "单元测试", "README")
    for key in expected_must_keywords:
        assert any(key in row for row in must_rows), f"section 4 must-implement rows must include {key}"

    expected_forbidden_keywords = ("不得修改 policies/", "不得引入网络请求", "不得绕过 DataCatalog", "不得输出")
    for key in expected_forbidden_keywords:
        assert any(key in row for row in forbidden_rows), f"section 4 forbidden rows must include {key}"

    expected_acceptance_keywords = ("docker compose up -d", "pytest -q", "python -m", "dossiers/<run_id>/")
    for key in expected_acceptance_keywords:
        assert any(key in row for row in acceptance_rows), f"section 4 acceptance rows must include {key}"

    return section, intro, template_section, field_rows, must_rows, forbidden_rows, acceptance_rows


def test_playbook_codex_task_card_page_renders_section4_structure_readonly_evidence() -> None:
    playbook_doc = _find_doc(suffix="Implementation Phases Playbook.md")
    section, intro, template_section, field_rows, must_rows, forbidden_rows, acceptance_rows = _extract_playbook_section4_codex_task_card(
        playbook_doc
    )

    client = TestClient(app)
    r = client.get("/ui/playbook-codex-task-card")
    assert r.status_code == 200
    text = r.text
    unescaped = html.unescape(text)

    assert "Playbook Codex Task Card Template Read-Only Evidence" in text
    assert "GET/HEAD only" in text
    assert "no write actions" in text
    assert "section 4 evidence only" in text
    assert "Playbook Section 4 Codex Task Card Template" in text
    assert section in unescaped
    assert intro in unescaped
    assert template_section in unescaped
    assert "/ui/playbook-codex-task-card" in text
    assert "docs/00_overview" in text
    assert "Implementation Phases Playbook.md" in text
    assert "<form" not in text.lower()
    assert 'method="post"' not in text.lower()

    for label, value in field_rows:
        assert label in unescaped
        assert value in unescaped

    for row in must_rows:
        assert row in unescaped
    for row in forbidden_rows:
        assert row in unescaped
    for row in acceptance_rows:
        assert row in unescaped

    assert re.search(rf'data-testid="playbook-codex-field-total">\s*{len(field_rows)}\s*<', text)
    assert re.search(rf'data-testid="playbook-codex-must-total">\s*{len(must_rows)}\s*<', text)
    assert re.search(rf'data-testid="playbook-codex-forbidden-total">\s*{len(forbidden_rows)}\s*<', text)
    assert re.search(rf'data-testid="playbook-codex-acceptance-total">\s*{len(acceptance_rows)}\s*<', text)
    assert 'data-testid="playbook-codex-field-row-1"' in text
    assert 'data-testid="playbook-codex-must-row-1"' in text
    assert 'data-testid="playbook-codex-forbidden-row-1"' in text
    assert 'data-testid="playbook-codex-acceptance-row-1"' in text


def test_playbook_codex_task_card_page_head_and_post_semantics() -> None:
    client = TestClient(app)
    assert client.head("/ui/playbook-codex-task-card").status_code == 200
    assert client.post("/ui/playbook-codex-task-card").status_code == 405
