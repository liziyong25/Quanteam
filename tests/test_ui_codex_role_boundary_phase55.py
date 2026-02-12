from __future__ import annotations

import html
import re
from pathlib import Path

from fastapi.testclient import TestClient

from quant_eam.api.app import app


WHOLE_VIEW_SECTION7_RE = re.compile(r"^##\s*7(?:\s|[.:：])")
WHOLE_VIEW_SECTION71_RE = re.compile(r"^###\s*7\.1(?:\s|[.:：])")
WHOLE_VIEW_SECTION72_RE = re.compile(r"^###\s*7\.2(?:\s|[.:：])")


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


def _extract_whole_view_section7_codex_role_boundary(path: Path) -> tuple[str, str, list[str], list[str], str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    active = ""
    section = ""
    role_positioning = ""
    temporary_rows: list[str] = []
    promotion_rows: list[str] = []
    governance_note = ""

    for raw in lines:
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            in_section = bool(WHOLE_VIEW_SECTION7_RE.match(line)) and (
                ("Codex CLI" in line) or ("探索者" in line) or ("裁判" in line)
            )
            if in_section:
                section = _clean_md(line[3:])
            continue
        if not in_section:
            continue

        if WHOLE_VIEW_SECTION71_RE.match(line):
            active = "temporary"
            continue
        if WHOLE_VIEW_SECTION72_RE.match(line):
            active = "promotion"
            continue

        if line.startswith("- "):
            item = _clean_md(line[2:])
            if not item:
                continue
            if active == "temporary":
                temporary_rows.append(item)
            elif active == "promotion":
                promotion_rows.append(item)
                if (not governance_note) and (
                    ("治理流程" in item) or ("gate_suite" in item.lower()) or ("版本化" in item)
                ):
                    governance_note = item
            continue

        if (not active) and (not role_positioning):
            cleaned = _clean_md(line)
            if cleaned:
                role_positioning = cleaned

    assert section, "Whole View section 7 title must not be empty"
    assert role_positioning, "Whole View section 7 role positioning statement must not be empty"
    assert temporary_rows, "Whole View section 7.1 temporary diagnostics rows must not be empty"
    assert promotion_rows, "Whole View section 7.2 promotion rows must not be empty"
    if not governance_note:
        governance_note = promotion_rows[-1]
    assert governance_note, "Whole View section 7 promote-to-gate governance note must not be empty"
    return section, role_positioning, temporary_rows, promotion_rows, governance_note


def test_codex_role_boundary_page_renders_whole_view_section7_readonly_evidence() -> None:
    whole_view_doc = _find_whole_view_root_doc()
    section, role_positioning, temporary_rows, promotion_rows, governance_note = _extract_whole_view_section7_codex_role_boundary(
        whole_view_doc
    )

    client = TestClient(app)
    r = client.get("/ui/codex-role-boundary")
    assert r.status_code == 200
    text = r.text
    unescaped = html.unescape(text)

    assert "Whole View Codex Role Boundary Read-Only Evidence" in text
    assert "GET/HEAD only" in text
    assert "no write actions" in text
    assert "section 7 evidence only" in text
    assert "Codex Role Positioning (Explorer / Tool Worker, Not Arbitrator)" in text
    assert "Ephemeral Diagnostics Boundary" in text
    assert "Promote-to-Gate Governance Note" in text
    assert "Quant‑EAM Whole View Framework.md" in unescaped
    assert "/ui/codex-role-boundary" in text
    assert "<form" not in text.lower()
    assert 'method="post"' not in text.lower()

    assert section in unescaped
    assert role_positioning in unescaped
    for row in temporary_rows:
        assert row in unescaped
    for row in promotion_rows:
        assert row in unescaped
    assert governance_note in unescaped

    assert re.search(r'data-testid="codex-role-positioning-present">\s*1\s*<', text)
    assert re.search(rf'data-testid="codex-role-temporary-total">\s*{len(temporary_rows)}\s*<', text)
    assert re.search(rf'data-testid="codex-role-promotion-total">\s*{len(promotion_rows)}\s*<', text)
    assert re.search(r'data-testid="codex-role-governance-note-present">\s*1\s*<', text)
    assert 'data-testid="codex-role-positioning"' in text
    assert 'data-testid="codex-role-temporary-row-1"' in text
    assert 'data-testid="codex-role-governance-note"' in text
    assert 'data-testid="codex-role-promotion-row-1"' in text


def test_codex_role_boundary_page_head_and_post_semantics() -> None:
    client = TestClient(app)
    assert client.head("/ui/codex-role-boundary").status_code == 200
    assert client.post("/ui/codex-role-boundary").status_code == 405
