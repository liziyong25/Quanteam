from __future__ import annotations

import html
import re
from pathlib import Path

from fastapi.testclient import TestClient

from quant_eam.api.app import app


SECTION11_RE = re.compile(r"^##\s*11(?:\s|[.:：])")
MILESTONE_RE = re.compile(r"^v([0-9]+(?:\.[0-9]+)?)\s*[：:]\s*(.+)$", re.IGNORECASE)


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


def _extract_whole_view_section11_roadmap(path: Path) -> list[dict[str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    out: list[dict[str, str]] = []

    for raw in lines:
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            in_section = bool(SECTION11_RE.match(line)) and (("版本路线" in line) or ("roadmap" in line.lower()))
            continue
        if (not in_section) or (not line) or (line == "---"):
            continue
        if not line.startswith("- "):
            continue

        item = _clean_md(line[2:])
        m = MILESTONE_RE.match(item)
        if not m:
            continue
        out.append(
            {
                "version": f"v{str(m.group(1)).strip()}",
                "milestones": _clean_md(m.group(2)),
            }
        )

    assert out, "Whole View section 11 roadmap milestone extraction must not be empty"
    versions = [str(row.get("version") or "") for row in out]
    assert "v0.4" in versions, "section 11 roadmap must include v0.4"
    assert "v0.5" in versions, "section 11 roadmap must include v0.5"
    assert "v0.6" in versions, "section 11 roadmap must include v0.6"
    return out


def test_version_roadmap_page_renders_whole_view_section11_readonly_evidence() -> None:
    whole_view_doc = _find_doc(suffix="Whole View Framework.md")
    milestone_rows = _extract_whole_view_section11_roadmap(whole_view_doc)

    client = TestClient(app)
    r = client.get("/ui/version-roadmap")
    assert r.status_code == 200
    text = r.text
    unescaped = html.unescape(text)

    assert "Whole View Version Roadmap Milestones Read-Only Evidence" in text
    assert "GET/HEAD only" in text
    assert "no write actions" in text
    assert "governance evidence" in text
    assert "Whole View Section 11 Version Roadmap Milestones" in text
    assert "11. 版本路线（建议）" in unescaped
    assert "/ui/version-roadmap" in text
    assert "docs/00_overview" in text
    assert "Whole View Framework.md" in text
    assert "<form" not in text.lower()
    assert 'method="post"' not in text.lower()

    for row in milestone_rows:
        assert row["version"] in unescaped
        assert row["milestones"] in unescaped

    assert re.search(rf'data-testid="version-roadmap-total">\s*{len(milestone_rows)}\s*<', text)
    assert 'data-testid="version-roadmap-row-1"' in text


def test_version_roadmap_page_head_and_post_semantics() -> None:
    client = TestClient(app)
    assert client.head("/ui/version-roadmap").status_code == 200
    assert client.post("/ui/version-roadmap").status_code == 405
