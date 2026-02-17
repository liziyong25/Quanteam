from __future__ import annotations

import html
import re
from pathlib import Path

from fastapi.testclient import TestClient

from quant_eam.api.app import app


SECTION10_RE = re.compile(r"^##\s*10(?:\s|[.:：])")


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


def _extract_whole_view_section10_checklist(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    out: list[str] = []

    for raw in lines:
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            in_section = bool(SECTION10_RE.match(line)) and (("不跑偏" in line) or ("检查清单" in line))
            continue
        if (not in_section) or (not line) or (line == "---"):
            continue
        if not line.startswith("- "):
            continue

        item = _clean_md(line[2:])
        if item:
            out.append(item)

    assert out, "Whole View section 10 anti-drift checklist extraction must not be empty"
    assert any("contract" in row.lower() for row in out), "section 10 checklist must include contract check"
    assert any("policies" in row.lower() for row in out), "section 10 checklist must include policies check"
    assert any("holdout" in row.lower() for row in out), "section 10 checklist must include holdout check"
    return out


def test_preflight_checklist_page_renders_whole_view_section10_readonly_evidence() -> None:
    whole_view_doc = _find_doc(suffix="Whole View Framework.md")
    checklist_rows = _extract_whole_view_section10_checklist(whole_view_doc)

    client = TestClient(app)
    r = client.get("/ui/preflight-checklist")
    assert r.status_code == 200
    text = r.text
    unescaped = html.unescape(text)

    assert "Whole View Anti-Drift Preflight Checklist Read-Only Evidence" in text
    assert "GET/HEAD only" in text
    assert "no write actions" in text
    assert "no holdout expansion" in text
    assert "Whole View Section 10 Anti-Drift Checklist" in text
    assert "10. “不跑偏”检查清单（每次新增功能前先对齐）" in unescaped
    assert "/ui/preflight-checklist" in text
    assert "docs/00_overview" in text
    assert "Whole View Framework.md" in text
    assert "<form" not in text.lower()
    assert 'method="post"' not in text.lower()

    for row in checklist_rows:
        assert row in unescaped

    assert re.search(rf'data-testid="preflight-checklist-total">\s*{len(checklist_rows)}\s*<', text)
    assert "data-testid=\"preflight-checklist-row-1\"" in text


def test_preflight_checklist_page_head_and_post_semantics() -> None:
    client = TestClient(app)
    assert client.head("/ui/preflight-checklist").status_code == 200
    assert client.post("/ui/preflight-checklist").status_code == 405
