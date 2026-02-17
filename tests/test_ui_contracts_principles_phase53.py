from __future__ import annotations

import html
import re
from pathlib import Path

from fastapi.testclient import TestClient

from quant_eam.api.app import app


SECTION5_RE = re.compile(r"^##\s*5(?:\s|[.:：])")
CONTRACT_ROW_RE = re.compile(r"^(\d+)\)\s*([A-Za-z0-9_.-]+\.json)\b")


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


def _extract_whole_view_section5_principles_and_trace(path: Path) -> tuple[list[str], str, list[str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    in_contracts = False
    principles: list[str] = []
    trace_boundary_note = ""
    contract_files: list[str] = []

    for raw in lines:
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            in_section = bool(SECTION5_RE.match(line)) and (
                ("Contract" in line) or ("Schema" in line) or ("体系" in line)
            )
            continue
        if (not in_section) or (not line) or (line == "---"):
            continue

        if line.startswith("### "):
            if ("5.1" in line) and ("Contract" in line):
                in_contracts = True
                continue
            if in_contracts:
                break

        if line.startswith(">"):
            quote = _clean_md(line.lstrip(">").strip())
            if ("原则" in quote) and (not principles):
                principle_blob = quote
                for sep in ("：", ":"):
                    if sep in principle_blob:
                        principle_blob = principle_blob.split(sep, 1)[1].strip()
                        break
                principles = [
                    p
                    for p in (_clean_md(x).strip("。.;；") for x in principle_blob.split("+"))
                    if p
                ]
                continue

            if (
                ("trace" in quote.lower())
                and ("计划" in quote)
                and ("结果" in quote)
                and (not trace_boundary_note)
            ):
                note = quote
                for sep in ("：", ":"):
                    if sep not in note:
                        continue
                    left, right = note.split(sep, 1)
                    if "说明" in left:
                        note = right.strip()
                    break
                trace_boundary_note = note
                continue

        if not in_contracts:
            continue
        m = CONTRACT_ROW_RE.match(line)
        if m:
            contract_files.append(m.group(2))

    assert principles, "Whole View section 5 principles extraction must not be empty"
    assert len(principles) == 4, "Whole View section 5 principles must include four core principles"
    for expected in ("版本化", "可静态分析", "对齐显式化", "trace 计划/结果分离"):
        assert expected in principles, f"section 5 principles must include {expected}"

    assert trace_boundary_note, "Whole View section 5 trace boundary note must not be empty"
    assert "trace 计划由 LLM/Codex 生成" in trace_boundary_note
    assert "trace 结果由 Runner（确定性）生成" in trace_boundary_note

    assert contract_files, "Whole View section 5.1 required contracts extraction must not be empty"
    assert len(contract_files) == 9, "Whole View section 5.1 must provide nine required contracts"
    for expected in (
        "blueprint_schema_v1.json",
        "calc_trace_plan_v1.json",
        "gate_spec_v1.json",
        "experience_card_schema_v1.json",
    ):
        assert expected in contract_files, f"section 5.1 required contracts must include {expected}"

    return principles, trace_boundary_note, contract_files


def test_contracts_principles_page_renders_whole_view_section5_readonly_evidence() -> None:
    whole_view_doc = _find_whole_view_root_doc()
    principles, trace_boundary_note, contract_files = _extract_whole_view_section5_principles_and_trace(
        whole_view_doc
    )

    client = TestClient(app)
    r = client.get("/ui/contracts-principles")
    assert r.status_code == 200
    text = r.text
    unescaped = html.unescape(text)

    assert "Whole View Contracts-System Principles and Trace Plan/Result Boundary Evidence" in text
    assert "GET/HEAD only" in text
    assert "no write actions" in text
    assert "section 5 evidence only" in text
    assert "Contracts-System Principles" in text
    assert "Trace Plan/Result Boundary Note" in text
    assert "Section 5.1 Required Contracts" in text
    assert "Quant‑EAM Whole View Framework.md" in unescaped
    assert "/ui/contracts-principles" in text
    assert "<form" not in text.lower()
    assert 'method="post"' not in text.lower()

    for row in principles:
        assert row in unescaped

    assert trace_boundary_note in unescaped

    for contract_file in contract_files:
        assert contract_file in text

    assert re.search(rf'data-testid="contracts-principles-total">\s*{len(principles)}\s*<', text)
    assert re.search(rf'data-testid="contracts-required-total">\s*{len(contract_files)}\s*<', text)
    assert re.search(r'data-testid="contracts-trace-note-present">\s*1\s*<', text)
    assert 'data-testid="contracts-principle-row-1"' in text
    assert 'data-testid="contracts-required-row-1"' in text


def test_contracts_principles_page_head_and_post_semantics() -> None:
    client = TestClient(app)
    assert client.head("/ui/contracts-principles").status_code == 200
    assert client.post("/ui/contracts-principles").status_code == 405
