from __future__ import annotations

import html
import re
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from quant_eam.api.app import app


WHOLE_VIEW_SECTION6_RE = re.compile(r"^##\s*6(?:\s|[.:：])")
WHOLE_VIEW_MODULE_HEADER_RE = re.compile(r"^###\s*6\.(\d+)\s*(.+)$")
PLAYBOOK_SECTION3_RE = re.compile(r"^##\s*3(?:\s|[.:：])")
PLAYBOOK_PHASE_HEADER_RE = re.compile(r"^###\s*Phase[\u2010-\u2015-](\d+)\s*[：:]")


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


def _extract_whole_view_module_meta(path: Path) -> tuple[list[str], int, int, int]:
    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    module_labels: list[str] = []
    boundary_entry_total = 0
    deterministic_total = 0
    agent_total = 0
    has_current = False

    for raw in lines:
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            in_section = bool(WHOLE_VIEW_SECTION6_RE.match(line)) and (("模块" in line) or ("Modules" in line))
            continue
        if not in_section:
            continue

        m = WHOLE_VIEW_MODULE_HEADER_RE.match(line)
        if m:
            module_index = int(m.group(1))
            label = _clean_md(m.group(2))
            for sep in ("（", "(", "：", ":"):
                if sep in label:
                    label = label.split(sep, 1)[0].strip()
            if label:
                module_labels.append(label)
            if module_index >= 4:
                agent_total += 1
            else:
                deterministic_total += 1
            has_current = True
            continue

        if has_current and line.startswith("- "):
            boundary_entry_total += 1

    assert module_labels, "Whole View section 6 module extraction must not be empty"
    assert boundary_entry_total > 0, "Whole View section 6 boundary entry extraction must not be empty"
    return module_labels, boundary_entry_total, deterministic_total, agent_total


def _extract_playbook_phase_labels(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    labels: list[str] = []

    for raw in lines:
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            in_section = bool(PLAYBOOK_SECTION3_RE.match(line)) and ("Phase" in line)
            continue
        if not in_section:
            continue

        m = PLAYBOOK_PHASE_HEADER_RE.match(line)
        if m:
            labels.append(f"Phase-{int(m.group(1))}")

    assert labels, "Playbook section 3 phase extraction must not be empty"
    return labels


def _ssot_module_boundary_meta() -> dict[str, object]:
    ssot_path = Path("docs/12_workflows/skeleton_ssot_v1.yaml")
    assert ssot_path.is_file(), "SSOT yaml is required for G41 module-boundary evidence validation"
    loaded = yaml.safe_load(ssot_path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), "SSOT yaml root must be map"

    g41_status = "unknown"
    goal_rows = loaded.get("goal_checklist")
    assert isinstance(goal_rows, list), "SSOT goal_checklist must be list"
    for row in goal_rows:
        if isinstance(row, dict) and str(row.get("id") or "") == "G41":
            g41_status = str(row.get("status_now") or "unknown")
            break

    dispatch = loaded.get("phase_dispatch_plan_v2")
    assert isinstance(dispatch, dict), "SSOT phase_dispatch_plan_v2 must be map"
    phase_rows = dispatch.get("phases")
    assert isinstance(phase_rows, list), "SSOT phase_dispatch_plan_v2.phases must be list"
    assert any(
        isinstance(row, dict)
        and str(row.get("phase_id") or "") == "phase_61"
        and str(row.get("goal_id") or "") == "G41"
        for row in phase_rows
    ), "SSOT dispatch must include phase_61 -> G41"

    exceptions = loaded.get("autopilot_stop_condition_exceptions_v1")
    assert isinstance(exceptions, list), "SSOT autopilot_stop_condition_exceptions_v1 must be list"
    g41_exception: dict[str, object] = {}
    for row in exceptions:
        if isinstance(row, dict) and str(row.get("exception_id") or "") == "g41_module_boundaries_ui_scope":
            g41_exception = row
            break
    assert g41_exception, "SSOT must include g41_module_boundaries_ui_scope exception"

    preauth = g41_exception.get("preauthorized_scope") if isinstance(g41_exception.get("preauthorized_scope"), dict) else {}
    required_guards = [str(x) for x in (preauth.get("required_guards") or []) if isinstance(x, str)]
    assert required_guards, "G41 preauthorized_scope.required_guards must not be empty"

    pipeline = loaded.get("agents_pipeline_v1")
    assert isinstance(pipeline, dict), "SSOT agents_pipeline_v1 must be map"
    global_read_rules = [str(x) for x in (pipeline.get("global_read_rules") or []) if isinstance(x, str)]
    assert global_read_rules, "SSOT agents_pipeline_v1.global_read_rules must not be empty"

    return {
        "g41_status": g41_status,
        "required_guard_total": len(required_guards),
        "required_guards": required_guards,
        "global_read_rule_total": len(global_read_rules),
        "global_read_rules": global_read_rules,
    }


def test_module_boundaries_page_renders_whole_view_playbook_and_ssot_evidence() -> None:
    whole_view_doc = _find_doc(suffix="Whole View Framework.md")
    playbook_doc = _find_doc(suffix="Implementation Phases Playbook.md")
    module_labels, boundary_entry_total, deterministic_total, agent_total = _extract_whole_view_module_meta(whole_view_doc)
    phase_labels = _extract_playbook_phase_labels(playbook_doc)
    ssot_meta = _ssot_module_boundary_meta()

    client = TestClient(app)
    r = client.get("/ui/module-boundaries")
    assert r.status_code == 200
    text = r.text
    unescaped = html.unescape(text)

    assert "Whole View Modules Deterministic-Agent Boundary Evidence" in text
    assert "GET/HEAD only" in text
    assert "no write actions" in text
    assert "no holdout expansion" in text
    assert "Whole View Section 6 Module Responsibilities" in text
    assert "Playbook Phase Flow/Context (Section 3)" in text
    assert "SSOT Module Boundary Governance Evidence" in text
    assert "6. 模块（Modules）与职责边界（Deterministic vs Agent）" in unescaped
    assert "phase_dispatch_plan_v2" in text
    assert "g41_module_boundaries_ui_scope" in text
    assert "agents_pipeline_v1" in text
    assert "G41" in text
    assert "phase_61" in text
    assert "/ui/module-boundaries" in text
    assert str(ssot_meta["g41_status"]) in text
    assert "<form" not in text.lower()
    assert "method=\"post\"" not in text.lower()

    for module_label in module_labels:
        assert module_label in unescaped
    for phase_label in phase_labels:
        assert phase_label in text
    for guard in ssot_meta["required_guards"]:
        assert guard in unescaped
    for rule in ssot_meta["global_read_rules"]:
        assert rule in unescaped

    assert re.search(rf'data-testid="module-boundary-module-total">\s*{len(module_labels)}\s*<', text)
    assert re.search(rf'data-testid="module-boundary-deterministic-total">\s*{deterministic_total}\s*<', text)
    assert re.search(rf'data-testid="module-boundary-agent-total">\s*{agent_total}\s*<', text)
    assert re.search(rf'data-testid="module-boundary-entry-total">\s*{boundary_entry_total}\s*<', text)
    assert re.search(rf'data-testid="module-boundary-playbook-phase-total">\s*{len(phase_labels)}\s*<', text)
    assert re.search(
        rf'data-testid="module-boundary-required-guard-total">\s*{int(ssot_meta["required_guard_total"])}\s*<',
        text,
    )
    assert re.search(
        rf'data-testid="module-boundary-global-rule-total">\s*{int(ssot_meta["global_read_rule_total"])}\s*<',
        text,
    )
    assert "data-testid=\"module-boundary-row-1\"" in text
    assert "data-testid=\"module-boundary-playbook-row-1\"" in text


def test_module_boundaries_page_head_and_post_semantics() -> None:
    client = TestClient(app)
    assert client.head("/ui/module-boundaries").status_code == 200
    assert client.post("/ui/module-boundaries").status_code == 405
