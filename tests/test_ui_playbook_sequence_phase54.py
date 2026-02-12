from __future__ import annotations

import html
import re
from pathlib import Path

from fastapi.testclient import TestClient

from quant_eam.api.app import app


SECTION5_RE = re.compile(r"^##\s*5(?:\s|[.:：])")
PHASE_TOKEN_RE = re.compile(r"Phase[\u2010-\u2015-](\d+)", re.IGNORECASE)


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


def _extract_playbook_section5_sequence(path: Path) -> tuple[str, str, list[str], list[int], str, list[str], str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    section = ""
    intro = ""
    sequence_rows: list[str] = []
    phase_numbers: list[int] = []
    loop_first_note = ""
    loop_components: list[str] = []
    automation_note = ""

    for raw in lines:
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            in_section = bool(SECTION5_RE.match(line)) and (
                ("施工顺序" in line) or ("结束语" in line) or ("sequence" in line.lower())
            )
            if in_section:
                section = _clean_md(line[3:])
            continue
        if (not in_section) or (not line) or (line == "---"):
            continue

        if line.startswith("- "):
            item = _clean_md(line[2:])
            if not item:
                continue
            sequence_rows.append(item)
            for raw_no in PHASE_TOKEN_RE.findall(item):
                phase_numbers.append(int(raw_no))
            continue

        item = _clean_md(line)
        if not item:
            continue
        if not intro:
            intro = item
        if ("先闭环" in item) and (not loop_first_note):
            loop_first_note = item
            m = re.search(r"(?:即[:：])?\s*(.+?)\s*先闭环", item)
            component_blob = m.group(1).strip() if m else ""
            loop_components = [x.strip() for x in component_blob.split("/") if x.strip()]
        if (("自动化放在闭环之后" in item) or ("不可审计" in item)) and (not automation_note):
            automation_note = item

    assert section, "Playbook section 5 heading extraction must not be empty"
    assert intro, "Playbook section 5 intro extraction must not be empty"
    assert sequence_rows, "Playbook section 5 sequence row extraction must not be empty"
    assert phase_numbers == [0, 1, 2, 3, 4, 5, 6], "section 5 sequence must enumerate Phase-0~Phase-6"
    assert loop_first_note, "Playbook section 5 loop-first rationale extraction must not be empty"
    assert "Contracts/Policies/DataCatalog/Runner/Dossier/Gates/UI" in loop_first_note
    assert loop_components == [
        "Contracts",
        "Policies",
        "DataCatalog",
        "Runner",
        "Dossier",
        "Gates",
        "UI",
    ], "section 5 loop-first rationale must expose the full closed-loop chain"
    assert automation_note, "Playbook section 5 automation note extraction must not be empty"
    assert "自动化放在闭环之后" in automation_note
    assert "不可审计" in automation_note
    assert re.search(r"Phase[\u2010-\u2015-]7/8/12", automation_note)
    return section, intro, sequence_rows, phase_numbers, loop_first_note, loop_components, automation_note


def test_playbook_sequence_page_renders_section5_sequence_readonly_evidence() -> None:
    playbook_doc = _find_doc(suffix="Implementation Phases Playbook.md")
    section, intro, sequence_rows, phase_numbers, loop_first_note, loop_components, automation_note = _extract_playbook_section5_sequence(
        playbook_doc
    )

    client = TestClient(app)
    r = client.get("/ui/playbook-sequence")
    assert r.status_code == 200
    text = r.text
    unescaped = html.unescape(text)

    assert "Playbook Construction Sequence Recommendation Read-Only Evidence" in text
    assert "GET/HEAD only" in text
    assert "no write actions" in text
    assert "section 5 evidence only" in text
    assert "Playbook Section 5 Construction Sequence Recommendation" in text
    assert "Loop-First Rationale" in text
    assert "Agents Automation Positioning" in text
    assert section in unescaped
    assert intro in unescaped
    assert loop_first_note in unescaped
    assert automation_note in unescaped
    assert "/ui/playbook-sequence" in text
    assert "docs/00_overview" in text
    assert "Implementation Phases Playbook.md" in text
    assert "<form" not in text.lower()
    assert 'method="post"' not in text.lower()

    for row in sequence_rows:
        assert row in unescaped

    for phase_no in phase_numbers:
        assert f"Phase-{phase_no}" in text

    for component in loop_components:
        assert component in unescaped

    assert re.search(rf'data-testid="playbook-sequence-total">\s*{len(sequence_rows)}\s*<', text)
    assert re.search(rf'data-testid="playbook-sequence-phase-total">\s*{len(phase_numbers)}\s*<', text)
    assert re.search(rf'data-testid="playbook-sequence-loop-total">\s*{len(loop_components)}\s*<', text)
    assert re.search(r'data-testid="playbook-sequence-automation-note-present">\s*1\s*<', text)
    assert 'data-testid="playbook-sequence-row-1"' in text
    assert 'data-testid="playbook-sequence-phase-row-1"' in text
    assert 'data-testid="playbook-sequence-loop-row-1"' in text


def test_playbook_sequence_page_head_and_post_semantics() -> None:
    client = TestClient(app)
    assert client.head("/ui/playbook-sequence").status_code == 200
    assert client.post("/ui/playbook-sequence").status_code == 405
