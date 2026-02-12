from __future__ import annotations

import html
import re
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from quant_eam.api.app import app


WHOLE_VIEW_SECTION64_RE = re.compile(r"^###\s*6\.4(?:\s|[.:：])")
PLAYBOOK_PHASE8_RE = re.compile(r"^###\s*Phase[\u2010-\u2015-]8\s*[：:].*$")


def _find_whole_view_doc() -> Path:
    matches = sorted(p for p in Path("docs/00_overview").glob("*Whole View Framework.md") if p.is_file())
    assert matches, "Whole View framework markdown is required for G38 agent roles page"
    return matches[0]


def _find_playbook_doc() -> Path:
    matches = sorted(p for p in Path("docs/00_overview").glob("*Implementation Phases Playbook.md") if p.is_file())
    assert matches, "Implementation Playbook markdown is required for G38 agent roles page"
    return matches[0]


def _clean_md(text: str) -> str:
    s = str(text).strip()
    s = re.sub(r"`([^`]+)`", r"\1", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
    s = re.sub(r"\*([^*]+)\*", r"\1", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _extract_whole_view_role_names(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    out: list[str] = []
    for raw in lines:
        line = raw.strip()
        if line.startswith("### "):
            if in_section:
                break
            in_section = bool(WHOLE_VIEW_SECTION64_RE.match(line)) and ("Agents Plane" in line)
            continue
        if (not in_section) or (not line.startswith("- ")):
            continue
        text = _clean_md(line[2:])
        role_name = text.split("：", 1)[0].split(":", 1)[0].strip()
        if role_name:
            out.append(role_name)
    assert out, "Whole View section 6.4 roles extraction must not be empty"
    return out


def _extract_phase8_agent_modules(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    current_heading = ""
    out: list[str] = []
    for raw in lines:
        line = raw.strip()
        if line.startswith("### "):
            if in_section:
                break
            in_section = bool(PLAYBOOK_PHASE8_RE.match(line))
            continue
        if line.startswith("**") and line.endswith("**"):
            current_heading = _clean_md(line.strip("*"))
            continue
        if (not in_section) or (not line.startswith("- ")):
            continue
        item = _clean_md(line[2:])
        if ("编码内容" in current_heading) and item.startswith("agents/"):
            out.append(item)
    assert out, "Playbook phase-8 module extraction must not be empty"
    return out


def _pipeline_agent_ids() -> list[str]:
    ssot_path = Path("docs/12_workflows/agents_ui_ssot_v1.yaml")
    assert ssot_path.is_file(), "SSOT yaml is required for G38 mapping validation"
    loaded = yaml.safe_load(ssot_path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), "SSOT yaml root must be map"
    pipeline = loaded.get("agents_pipeline_v1")
    assert isinstance(pipeline, dict), "SSOT agents_pipeline_v1 must be map"
    rows = pipeline.get("steps")
    assert isinstance(rows, list), "SSOT agents_pipeline_v1.steps must be list"
    out: list[str] = []
    for row in rows:
        if isinstance(row, dict):
            agent_id = str(row.get("agent_id") or "").strip()
            if agent_id:
                out.append(agent_id)
    assert out, "SSOT agents_pipeline_v1 agent_ids must not be empty"
    return out


def test_agent_roles_page_renders_roles_boundaries_and_pipeline_evidence() -> None:
    whole_view_roles = _extract_whole_view_role_names(_find_whole_view_doc())
    phase8_modules = _extract_phase8_agent_modules(_find_playbook_doc())
    pipeline_agent_ids = _pipeline_agent_ids()

    client = TestClient(app)
    r = client.get("/ui/agent-roles")
    assert r.status_code == 200
    text = r.text
    unescaped = html.unescape(text)

    assert "Agents Roles and Harness Boundary Evidence" in text
    assert "6.4 Agents Plane" in text
    assert "Phase-8" in text
    assert "agents_pipeline_v1" in text
    assert "GET/HEAD only" in text
    assert "no write actions" in text
    assert "no holdout expansion" in text
    assert "Playbook Phase-8 Harness Requirements" in text
    assert "Playbook Phase-8 Acceptance Boundaries" in text
    assert "SSOT Global Read Rules" in text
    assert "Agents must not read holdout internals beyond minimal summary." in unescaped
    assert "Agents must not write policies/** or contracts/**." in unescaped
    assert "<form" not in text.lower()
    assert "method=\"post\"" not in text.lower()

    for role_name in whole_view_roles:
        assert role_name in unescaped
    for module in phase8_modules:
        assert module in unescaped
    for agent_id in pipeline_agent_ids:
        assert agent_id in text

    assert re.search(rf'data-testid="agent-role-total">\s*{len(whole_view_roles)}\s*<', text)
    assert re.search(rf'data-testid="phase8-module-total">\s*{len(phase8_modules)}\s*<', text)
    assert re.search(rf'data-testid="pipeline-step-total">\s*{len(pipeline_agent_ids)}\s*<', text)
    assert "data-testid=\"whole-view-role-1\"" in text
    assert "data-testid=\"pipeline-step-1\"" in text


def test_agent_roles_page_head_and_post_semantics() -> None:
    client = TestClient(app)
    assert client.head("/ui/agent-roles").status_code == 200
    assert client.post("/ui/agent-roles").status_code == 405
