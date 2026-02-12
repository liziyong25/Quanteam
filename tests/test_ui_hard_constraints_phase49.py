from __future__ import annotations

import html
import re
from pathlib import Path

from fastapi.testclient import TestClient

from quant_eam.api.app import app


SECTION1_RE = re.compile(r"^##\s*1(?:\s|[.:：])")


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


def _extract_whole_view_section1_constraints(path: Path) -> list[dict[str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    rows: list[dict[str, str]] = []
    current: dict[str, str] | None = None

    for raw in lines:
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            in_section = bool(SECTION1_RE.match(line)) and (("系统硬约束" in line) or ("Hard Constraints" in line))
            continue
        if (not in_section) or (not line) or (line == "---"):
            continue

        m = re.match(r"^(\d+)\)\s*(.+)$", line)
        if m:
            if current:
                rows.append(current)
            current = {
                "check_id": f"WV-{m.group(1)}",
                "item": _clean_md(m.group(2)),
                "detail": "",
            }
            continue

        if current and line.startswith("- "):
            detail = _clean_md(line[2:])
            if detail:
                current["detail"] = f"{current['detail']} {detail}".strip()

    if current:
        rows.append(current)

    assert rows, "Whole View section 1 hard constraints extraction must not be empty"
    assert len(rows) == 6, "Whole View section 1 must provide six hard constraints"
    items = [row["item"] for row in rows]
    for expected in ("Policies 只读", "裁决只允许 Gate + Dossier", "Final Holdout 不可污染"):
        assert expected in items, f"section 1 must include {expected}"
    return rows


def test_hard_constraints_page_renders_whole_view_section1_readonly_evidence() -> None:
    whole_view_doc = _find_whole_view_root_doc()
    constraints = _extract_whole_view_section1_constraints(whole_view_doc)

    client = TestClient(app)
    r = client.get("/ui/hard-constraints")
    assert r.status_code == 200
    text = r.text
    unescaped = html.unescape(text)

    assert "Whole View Hard Constraints Governance Evidence" in text
    assert "GET/HEAD only" in text
    assert "no write actions" in text
    assert "section 1 evidence only" in text
    assert "Whole View Section 1 Hard Constraints" in text
    assert "Quant‑EAM Whole View Framework.md" in unescaped
    assert "/ui/hard-constraints" in text
    assert "<form" not in text.lower()
    assert 'method="post"' not in text.lower()

    for row in constraints:
        assert row["check_id"] in text
        assert row["item"] in unescaped
        if row["detail"]:
            assert row["detail"] in unescaped

    assert re.search(rf'data-testid="hard-constraints-total">\s*{len(constraints)}\s*<', text)
    assert 'data-testid="hard-constraint-row-1"' in text


def test_hard_constraints_page_head_and_post_semantics() -> None:
    client = TestClient(app)
    assert client.head("/ui/hard-constraints").status_code == 200
    assert client.post("/ui/hard-constraints").status_code == 405
