from __future__ import annotations

import re
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from quant_eam.api.app import app


PHASE_SECTION_RE = re.compile(r"^##\s*3(?:\s|[.:：])")
PHASE_HEADER_RE = re.compile(r"^###\s*Phase[\u2010-\u2015-](\d+)\s*[：:]")


def _find_playbook_doc() -> Path:
    matches = sorted(p for p in Path("docs/00_overview").glob("*Implementation Phases Playbook.md") if p.is_file())
    assert matches, "Implementation Playbook markdown is required for G36 playbook phase matrix page"
    return matches[0]


def _extract_phase_labels(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    out: list[str] = []
    for raw in lines:
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            in_section = bool(PHASE_SECTION_RE.match(line)) and ("Phase" in line)
            continue
        if not in_section:
            continue
        m = PHASE_HEADER_RE.match(line)
        if m:
            out.append(f"Phase-{int(m.group(1))}")
    assert out, "Playbook section 3 phase extraction must not be empty"
    return out


def _goal_status(goal_id: str) -> str:
    ssot_path = Path("docs/12_workflows/agents_ui_ssot_v1.yaml")
    assert ssot_path.is_file(), "SSOT yaml is required for G36 mapping validation"
    loaded = yaml.safe_load(ssot_path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), "SSOT yaml root must be map"
    rows = loaded.get("goal_checklist")
    assert isinstance(rows, list), "SSOT goal_checklist must be list"
    for row in rows:
        if isinstance(row, dict) and str(row.get("id") or "") == goal_id:
            return str(row.get("status_now") or "unknown")
    return "unknown"


def test_playbook_phases_page_renders_matrix_and_ssot_mapping() -> None:
    phase_labels = _extract_phase_labels(_find_playbook_doc())
    g36_status = _goal_status("G36")

    client = TestClient(app)
    r = client.get("/ui/playbook-phases")
    assert r.status_code == 200
    text = r.text

    assert "Playbook Phase Matrix Read-Only Evidence" in text
    assert "GET/HEAD only" in text
    assert "no write actions" in text
    assert "no holdout expansion" in text
    assert "phase_dispatch_plan_v2" in text
    assert "goal_checklist" in text
    assert "Playbook Section 3 Phase Matrix" in text
    assert "SSOT Dispatch-to-Playbook Mapping" in text
    assert "G36" in text
    assert "/ui/playbook-phases" in text
    assert g36_status in text
    assert "phase_56" in text
    assert "<form" not in text.lower()
    assert "method=\"post\"" not in text.lower()

    for label in phase_labels:
        assert label in text

    assert re.search(rf'data-testid="playbook-phase-total">\s*{len(phase_labels)}\s*<', text)
    assert "data-testid=\"playbook-phase-row-1\"" in text
    assert "data-testid=\"dispatch-row-1\"" in text


def test_playbook_phases_page_head_and_post_semantics() -> None:
    client = TestClient(app)
    assert client.head("/ui/playbook-phases").status_code == 200
    assert client.post("/ui/playbook-phases").status_code == 405
