from __future__ import annotations

import html
import re
from pathlib import Path

from fastapi.testclient import TestClient

from quant_eam.api.app import app


SECTION8_RE = re.compile(r"^##\s*8(?:\s|[.:：])")
ITEM_RE = re.compile(r"^(\d+)\)\s*(.+)$")
EXPECTED_ROUTES = [
    "/ui",
    "/ui/jobs",
    "/ui/jobs/{job_id}",
    "/ui/runs/{run_id}",
    "/ui/runs/{run_id}/gates",
    "/ui/cards/{card_id}",
    "/ui/composer",
]
EXPECTED_TEMPLATES = [
    "index.html",
    "jobs.html",
    "job.html",
    "run.html",
    "run_gates.html",
    "card.html",
    "composer.html",
]


def _find_whole_view_doc() -> Path:
    matches = sorted(p for p in Path("docs/00_overview").glob("*Whole View Framework.md") if p.is_file())
    assert matches, "Whole View framework markdown is required for G37 IA coverage page"
    return matches[0]


def _clean_md(text: str) -> str:
    s = str(text).strip()
    s = re.sub(r"`([^`]+)`", r"\1", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
    s = re.sub(r"\*([^*]+)\*", r"\1", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _extract_ia_checklist(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    out: list[str] = []
    for raw in lines:
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            in_section = bool(SECTION8_RE.match(line)) and ("UI" in line)
            continue
        if not in_section or not line:
            continue
        m = ITEM_RE.match(line)
        if m:
            out.append(_clean_md(m.group(2)))
    assert len(out) == 8, "Whole View section 8 checklist extraction must return 8 rows"
    return out


def test_ia_coverage_page_renders_whole_view_checklist_and_route_evidence() -> None:
    client = TestClient(app)
    checklist = _extract_ia_checklist(_find_whole_view_doc())

    r = client.get("/ui/ia-coverage")
    assert r.status_code == 200
    text = r.text
    unescaped = html.unescape(text)

    assert "UI Information Architecture Coverage" in text
    assert "8. UI 信息架构（不看源码的审阅体验）" in text
    assert "GET/HEAD only" in text
    assert "no write actions" in text
    assert "no holdout expansion" in text
    assert "Whole View IA Checklist Mapping" in text
    assert "Route/View Evidence" in text
    assert "Whole View Framework.md" in text
    assert "<form" not in text.lower()
    assert "method=\"post\"" not in text.lower()

    for item in checklist:
        assert item in unescaped
    for route in EXPECTED_ROUTES:
        assert route in text
    for template_name in EXPECTED_TEMPLATES:
        assert template_name in text

    assert re.search(rf'data-testid="ia-checklist-total">\s*{len(checklist)}\s*<', text)
    assert re.search(rf'data-testid="ia-mapped-total">\s*{len(checklist)}\s*<', text)
    assert re.search(rf'data-testid="ia-route-total">\s*{len(EXPECTED_ROUTES)}\s*<', text)
    assert "data-testid=\"ia-row-1\"" in text
    assert "data-testid=\"ia-route-row-1\"" in text


def test_ia_coverage_page_head_and_post_semantics() -> None:
    client = TestClient(app)
    assert client.head("/ui/ia-coverage").status_code == 200
    assert client.post("/ui/ia-coverage").status_code == 405
