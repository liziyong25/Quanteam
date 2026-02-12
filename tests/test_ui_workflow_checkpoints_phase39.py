from __future__ import annotations

import html
import re
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from quant_eam.api.app import app


WHOLE_VIEW_SECTION3_RE = re.compile(r"^##\s*3(?:\s|[.:：])")
WHOLE_VIEW_PHASE_HEADER_RE = re.compile(r"^###\s*Phase[\u2010-\u2015-](\d+)\s*[：:]")
WHOLE_VIEW_CHECKPOINT_RE = re.compile(r"^审阅点\s*#\s*(\d+)")
PLAYBOOK_SECTION3_RE = re.compile(r"^##\s*3(?:\s|[.:：])")
PLAYBOOK_PHASE_HEADER_RE = re.compile(r"^###\s*Phase[\u2010-\u2015-](\d+)\s*[：:]")


def _find_whole_view_doc() -> Path:
    matches = sorted(p for p in Path("docs/00_overview").glob("*Whole View Framework.md") if p.is_file())
    assert matches, "Whole View framework markdown is required for G39 workflow checkpoints page"
    return matches[0]


def _find_playbook_doc() -> Path:
    matches = sorted(p for p in Path("docs/00_overview").glob("*Implementation Phases Playbook.md") if p.is_file())
    assert matches, "Implementation Playbook markdown is required for G39 workflow checkpoints page"
    return matches[0]


def _clean_md(text: str) -> str:
    s = str(text).strip()
    s = re.sub(r"`([^`]+)`", r"\1", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
    s = re.sub(r"\*([^*]+)\*", r"\1", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _extract_whole_view_phase_labels_and_checkpoint_total(path: Path) -> tuple[list[str], int]:
    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    labels: list[str] = []
    checkpoint_total = 0

    for raw in lines:
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            in_section = bool(WHOLE_VIEW_SECTION3_RE.match(line)) and ("工作流" in line or "Workflow" in line)
            continue
        if not in_section:
            continue

        m = WHOLE_VIEW_PHASE_HEADER_RE.match(line)
        if m:
            labels.append(f"Phase-{int(m.group(1))}")
            continue

        if not line.startswith("- "):
            continue
        item = _clean_md(line[2:])
        if WHOLE_VIEW_CHECKPOINT_RE.match(item):
            checkpoint_total += 1

    assert labels, "Whole View section 3 phase extraction must not be empty"
    assert checkpoint_total > 0, "Whole View section 3 checkpoint extraction must not be empty"
    return labels, checkpoint_total


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


def _ssot_workflow_meta() -> dict[str, object]:
    ssot_path = Path("docs/12_workflows/skeleton_ssot_v1.yaml")
    assert ssot_path.is_file(), "SSOT yaml is required for G39 workflow mapping validation"
    loaded = yaml.safe_load(ssot_path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), "SSOT yaml root must be map"

    g39_status = "unknown"
    goal_rows = loaded.get("goal_checklist")
    assert isinstance(goal_rows, list), "SSOT goal_checklist must be list"
    for row in goal_rows:
        if isinstance(row, dict) and str(row.get("id") or "") == "G39":
            g39_status = str(row.get("status_now") or "unknown")
            break

    dispatch = loaded.get("phase_dispatch_plan_v2")
    assert isinstance(dispatch, dict), "SSOT phase_dispatch_plan_v2 must be map"
    phase_rows = dispatch.get("phases")
    assert isinstance(phase_rows, list), "SSOT phase_dispatch_plan_v2.phases must be list"
    assert any(
        isinstance(row, dict)
        and str(row.get("phase_id") or "") == "phase_59"
        and str(row.get("goal_id") or "") == "G39"
        for row in phase_rows
    ), "SSOT dispatch must include phase_59 -> G39"

    autopilot = loaded.get("orchestrator_autopilot_v1")
    assert isinstance(autopilot, dict), "SSOT orchestrator_autopilot_v1 must be map"
    cycle_rows = [str(x) for x in (autopilot.get("cycle") or []) if isinstance(x, str)]
    assert cycle_rows, "SSOT orchestrator_autopilot_v1.cycle must not be empty"

    pipeline = loaded.get("agents_pipeline_v1")
    assert isinstance(pipeline, dict), "SSOT agents_pipeline_v1 must be map"
    execution_model = str(pipeline.get("execution_model") or "")
    assert execution_model, "SSOT agents_pipeline_v1.execution_model must not be empty"

    step_rows = pipeline.get("steps")
    assert isinstance(step_rows, list), "SSOT agents_pipeline_v1.steps must be list"
    checkpoint_total = 0
    for row in step_rows:
        if not isinstance(row, dict):
            continue
        checkpoint_step = str(row.get("checkpoint_step") or "").strip().lower()
        planned_checkpoint_step = str(row.get("planned_checkpoint_step") or "").strip().lower()
        if checkpoint_step and checkpoint_step not in ("none", "null"):
            checkpoint_total += 1
        elif planned_checkpoint_step and planned_checkpoint_step not in ("none", "null"):
            checkpoint_total += 1
    assert checkpoint_total > 0, "SSOT agents_pipeline_v1 checkpoint steps must not be empty"

    return {
        "g39_status": g39_status,
        "autopilot_cycle_total": len(cycle_rows),
        "execution_model": execution_model,
        "pipeline_checkpoint_total": checkpoint_total,
    }


def test_workflow_checkpoints_page_renders_whole_view_playbook_and_ssot_evidence() -> None:
    whole_view_labels, checkpoint_total = _extract_whole_view_phase_labels_and_checkpoint_total(_find_whole_view_doc())
    playbook_labels = _extract_playbook_phase_labels(_find_playbook_doc())
    ssot_meta = _ssot_workflow_meta()

    client = TestClient(app)
    r = client.get("/ui/workflow-checkpoints")
    assert r.status_code == 200
    text = r.text
    unescaped = html.unescape(text)

    assert "Whole View Workflow Checkpoints Matrix" in text
    assert "GET/HEAD only" in text
    assert "no write actions" in text
    assert "no holdout expansion" in text
    assert "Whole View Section 3 Workflow Matrix" in text
    assert "Playbook Phase Flow (Section 3)" in text
    assert "SSOT Orchestration/Workflow Evidence" in text
    assert "orchestrator_autopilot_v1" in text
    assert "phase_dispatch_plan_v2" in text
    assert "agents_pipeline_v1" in text
    assert "G39" in text
    assert "phase_59" in text
    assert "/ui/workflow-checkpoints" in text
    assert str(ssot_meta["g39_status"]) in text
    assert str(ssot_meta["execution_model"]) in text
    assert "<form" not in text.lower()
    assert "method=\"post\"" not in text.lower()

    for label in whole_view_labels:
        assert label in text
    for label in playbook_labels:
        assert label in text

    assert re.search(rf'data-testid="workflow-whole-view-phase-total">\s*{len(whole_view_labels)}\s*<', text)
    assert re.search(rf'data-testid="workflow-whole-view-checkpoint-total">\s*{checkpoint_total}\s*<', text)
    assert re.search(rf'data-testid="workflow-playbook-phase-total">\s*{len(playbook_labels)}\s*<', text)
    assert re.search(
        rf'data-testid="workflow-autopilot-cycle-total">\s*{int(ssot_meta["autopilot_cycle_total"])}\s*<',
        text,
    )
    assert re.search(
        rf'data-testid="workflow-pipeline-checkpoint-total">\s*{int(ssot_meta["pipeline_checkpoint_total"])}\s*<',
        text,
    )
    assert "data-testid=\"workflow-whole-view-row-1\"" in text
    assert "data-testid=\"workflow-playbook-row-1\"" in text
    assert "data-testid=\"workflow-ssot-checkpoint-row-1\"" in text

    # Whole View section-3 checkpoint text should survive render.
    assert "审阅点 #1（UI）" in unescaped


def test_workflow_checkpoints_page_head_and_post_semantics() -> None:
    client = TestClient(app)
    assert client.head("/ui/workflow-checkpoints").status_code == 200
    assert client.post("/ui/workflow-checkpoints").status_code == 405
