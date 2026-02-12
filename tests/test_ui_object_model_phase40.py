from __future__ import annotations

import html
import re
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from quant_eam.api.app import app


WHOLE_VIEW_SECTION4_RE = re.compile(r"^##\s*4(?:\s|[.:：])")
WHOLE_VIEW_OBJECT_HEADER_RE = re.compile(r"^###\s*4\.(\d+)\s*(.+)$")
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


def _extract_whole_view_object_names(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    out: list[str] = []

    for raw in lines:
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            in_section = bool(WHOLE_VIEW_SECTION4_RE.match(line)) and (("对象模型" in line) or ("I/O" in line))
            continue
        if not in_section:
            continue

        m = WHOLE_VIEW_OBJECT_HEADER_RE.match(line)
        if not m:
            continue
        obj = _clean_md(m.group(2))
        obj = obj.split("（", 1)[0].split("(", 1)[0].split("：", 1)[0].split(":", 1)[0].strip()
        if obj:
            out.append(obj)

    assert out, "Whole View section 4 object extraction must not be empty"
    return out


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


def _ssot_object_model_meta() -> dict[str, object]:
    ssot_path = Path("docs/12_workflows/agents_ui_ssot_v1.yaml")
    assert ssot_path.is_file(), "SSOT yaml is required for G40 object-model evidence validation"
    loaded = yaml.safe_load(ssot_path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), "SSOT yaml root must be map"

    g40_status = "unknown"
    goal_rows = loaded.get("goal_checklist")
    assert isinstance(goal_rows, list), "SSOT goal_checklist must be list"
    for row in goal_rows:
        if isinstance(row, dict) and str(row.get("id") or "") == "G40":
            g40_status = str(row.get("status_now") or "unknown")
            break

    dispatch = loaded.get("phase_dispatch_plan_v2")
    assert isinstance(dispatch, dict), "SSOT phase_dispatch_plan_v2 must be map"
    phase_rows = dispatch.get("phases")
    assert isinstance(phase_rows, list), "SSOT phase_dispatch_plan_v2.phases must be list"
    assert any(
        isinstance(row, dict)
        and str(row.get("phase_id") or "") == "phase_60"
        and str(row.get("goal_id") or "") == "G40"
        for row in phase_rows
    ), "SSOT dispatch must include phase_60 -> G40"

    exceptions = loaded.get("autopilot_stop_condition_exceptions_v1")
    assert isinstance(exceptions, list), "SSOT autopilot_stop_condition_exceptions_v1 must be list"
    g40_exception: dict[str, object] = {}
    for row in exceptions:
        if isinstance(row, dict) and str(row.get("exception_id") or "") == "g40_object_model_ui_scope":
            g40_exception = row
            break
    assert g40_exception, "SSOT must include g40_object_model_ui_scope exception"

    preauth = g40_exception.get("preauthorized_scope") if isinstance(g40_exception.get("preauthorized_scope"), dict) else {}
    required_guards = [str(x) for x in (preauth.get("required_guards") or []) if isinstance(x, str)]
    assert required_guards, "G40 preauthorized_scope.required_guards must not be empty"

    return {
        "g40_status": g40_status,
        "required_guard_total": len(required_guards),
        "required_guards": required_guards,
    }


def test_object_model_page_renders_whole_view_playbook_and_ssot_evidence() -> None:
    whole_view_doc = _find_doc(suffix="Whole View Framework.md")
    playbook_doc = _find_doc(suffix="Implementation Phases Playbook.md")

    object_names = _extract_whole_view_object_names(whole_view_doc)
    phase_labels = _extract_playbook_phase_labels(playbook_doc)
    ssot_meta = _ssot_object_model_meta()

    client = TestClient(app)
    r = client.get("/ui/object-model")
    assert r.status_code == 200
    text = r.text
    unescaped = html.unescape(text)

    assert "Whole View Object Model I/O Coverage" in text
    assert "GET/HEAD only" in text
    assert "no write actions" in text
    assert "no holdout expansion" in text
    assert "Whole View Section 4 Object Model I/O Definitions" in text
    assert "Playbook Phase Flow/Context (Section 3)" in text
    assert "SSOT Object Model Governance Evidence" in text
    assert "phase_dispatch_plan_v2" in text
    assert "g40_object_model_ui_scope" in text
    assert "G40" in text
    assert "phase_60" in text
    assert "/ui/object-model" in text
    assert str(ssot_meta["g40_status"]) in text
    assert "<form" not in text.lower()
    assert 'method="post"' not in text.lower()

    for name in object_names:
        assert name in unescaped
    for label in phase_labels:
        assert label in text

    assert re.search(rf'data-testid="object-model-object-total">\s*{len(object_names)}\s*<', text)
    assert re.search(rf'data-testid="object-model-playbook-phase-total">\s*{len(phase_labels)}\s*<', text)
    assert re.search(
        rf'data-testid="object-model-required-guard-total">\s*{int(ssot_meta["required_guard_total"])}\s*<',
        text,
    )
    assert "data-testid=\"object-model-row-1\"" in text
    assert "data-testid=\"object-model-playbook-row-1\"" in text

    for guard in ssot_meta["required_guards"]:
        assert guard in unescaped


def test_object_model_page_head_and_post_semantics() -> None:
    client = TestClient(app)
    assert client.head("/ui/object-model").status_code == 200
    assert client.post("/ui/object-model").status_code == 405
