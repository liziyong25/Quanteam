from __future__ import annotations

import html
import re
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from quant_eam.api.app import app


WHOLE_VIEW_SECTION7_RE = re.compile(r"^##\s*7(?:\s|[.:：])")
WHOLE_VIEW_SECTION71_RE = re.compile(r"^###\s*7\.1(?:\s|[.:：])")
WHOLE_VIEW_SECTION72_RE = re.compile(r"^###\s*7\.2(?:\s|[.:：])")
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


def _extract_whole_view_diagnostics_rows(path: Path) -> tuple[list[str], list[str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    active = ""
    temporary_rows: list[str] = []
    promotion_rows: list[str] = []

    for raw in lines:
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            in_section = bool(WHOLE_VIEW_SECTION7_RE.match(line)) and (
                ("Codex CLI" in line) or ("探索者" in line) or ("诊断" in line)
            )
            continue
        if not in_section:
            continue

        if WHOLE_VIEW_SECTION71_RE.match(line):
            active = "temporary"
            continue
        if WHOLE_VIEW_SECTION72_RE.match(line):
            active = "promotion"
            continue
        if not line.startswith("- "):
            continue

        item = _clean_md(line[2:])
        if not item:
            continue
        if active == "temporary":
            temporary_rows.append(item)
        elif active == "promotion":
            promotion_rows.append(item)

    assert temporary_rows, "Whole View section 7.1 diagnostics rows must not be empty"
    assert promotion_rows, "Whole View section 7.2 promotion rows must not be empty"
    return temporary_rows, promotion_rows


def _extract_playbook_phase12_rows(path: Path) -> dict[str, list[str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    current_heading = ""
    goal_rows: list[str] = []
    code_rows: list[str] = []
    acceptance_rows: list[str] = []

    for raw in lines:
        line = raw.strip()
        if line.startswith("### "):
            if in_section:
                break
            m = PLAYBOOK_PHASE_HEADER_RE.match(line)
            in_section = bool(m and int(m.group(1)) == 12)
            continue
        if not in_section:
            continue

        if line.startswith("**") and line.endswith("**"):
            current_heading = _clean_md(line.strip("*"))
            continue
        if not line.startswith("- "):
            continue

        item = _clean_md(line[2:])
        if not item:
            continue
        if "目标" in current_heading:
            goal_rows.append(item)
        elif "编码内容" in current_heading:
            code_rows.append(item)
        elif "验收" in current_heading:
            acceptance_rows.append(item)

    assert goal_rows, "Playbook phase-12 goal rows must not be empty"
    assert code_rows, "Playbook phase-12 code rows must not be empty"
    assert acceptance_rows, "Playbook phase-12 acceptance rows must not be empty"
    return {
        "goal_rows": goal_rows,
        "code_rows": code_rows,
        "acceptance_rows": acceptance_rows,
    }


def _ssot_diagnostics_promotion_meta() -> dict[str, object]:
    ssot_path = Path("docs/12_workflows/agents_ui_ssot_v1.yaml")
    assert ssot_path.is_file(), "SSOT yaml is required for G42 diagnostics-promotion evidence validation"
    loaded = yaml.safe_load(ssot_path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), "SSOT yaml root must be map"

    goal_rows = loaded.get("goal_checklist")
    assert isinstance(goal_rows, list), "SSOT goal_checklist must be list"
    g42_row: dict[str, object] = {}
    for row in goal_rows:
        if isinstance(row, dict) and str(row.get("id") or "") == "G42":
            g42_row = row
            break
    assert g42_row, "SSOT goal_checklist must include G42"

    dispatch = loaded.get("phase_dispatch_plan_v2")
    assert isinstance(dispatch, dict), "SSOT phase_dispatch_plan_v2 must be map"
    phase_rows = dispatch.get("phases")
    assert isinstance(phase_rows, list), "SSOT phase_dispatch_plan_v2.phases must be list"
    assert any(
        isinstance(row, dict)
        and str(row.get("phase_id") or "") == "phase_62"
        and str(row.get("goal_id") or "") == "G42"
        for row in phase_rows
    ), "SSOT dispatch must include phase_62 -> G42"

    exceptions = loaded.get("autopilot_stop_condition_exceptions_v1")
    assert isinstance(exceptions, list), "SSOT autopilot_stop_condition_exceptions_v1 must be list"
    g42_exception: dict[str, object] = {}
    for row in exceptions:
        if isinstance(row, dict) and str(row.get("exception_id") or "") == "g42_diagnostics_promotion_ui_scope":
            g42_exception = row
            break
    assert g42_exception, "SSOT must include g42_diagnostics_promotion_ui_scope exception"

    preauth = g42_exception.get("preauthorized_scope") if isinstance(g42_exception.get("preauthorized_scope"), dict) else {}
    required_guards = [str(x) for x in (preauth.get("required_guards") or []) if isinstance(x, str)]
    assert required_guards, "G42 preauthorized_scope.required_guards must not be empty"

    pipeline = loaded.get("agents_pipeline_v1")
    assert isinstance(pipeline, dict), "SSOT agents_pipeline_v1 must be map"
    global_read_rules = [str(x) for x in (pipeline.get("global_read_rules") or []) if isinstance(x, str)]
    assert global_read_rules, "SSOT agents_pipeline_v1.global_read_rules must not be empty"

    acceptance_commands = [str(x) for x in (g42_row.get("acceptance_commands") or []) if isinstance(x, str)]
    assert acceptance_commands, "G42 acceptance_commands must not be empty"

    expected_artifacts = [str(x) for x in (g42_row.get("expected_artifacts") or []) if isinstance(x, str)]
    assert expected_artifacts, "G42 expected_artifacts must not be empty"

    return {
        "g42_status": str(g42_row.get("status_now") or "unknown"),
        "required_guards": required_guards,
        "global_read_rules": global_read_rules,
        "acceptance_commands": acceptance_commands,
        "expected_artifacts": expected_artifacts,
    }


def test_diagnostics_promotion_page_renders_whole_view_playbook_and_ssot_evidence() -> None:
    whole_view_doc = _find_doc(suffix="Whole View Framework.md")
    playbook_doc = _find_doc(suffix="Implementation Phases Playbook.md")
    temporary_rows, promotion_rows = _extract_whole_view_diagnostics_rows(whole_view_doc)
    phase12_rows = _extract_playbook_phase12_rows(playbook_doc)
    ssot_meta = _ssot_diagnostics_promotion_meta()

    client = TestClient(app)
    r = client.get("/ui/diagnostics-promotion")
    assert r.status_code == 200
    text = r.text
    unescaped = html.unescape(text)

    assert "Codex Diagnostics Promotion Chain Read-Only Evidence" in text
    assert "GET/HEAD only" in text
    assert "no write actions" in text
    assert "no holdout expansion" in text
    assert "Whole View Section 7 Diagnostics Promotion Chain" in text
    assert "Playbook Phase-12 Diagnostics Promote Evidence" in text
    assert "SSOT Diagnostics Promotion Governance Evidence" in text
    assert "phase_dispatch_plan_v2" in text
    assert "g42_diagnostics_promotion_ui_scope" in text
    assert "agents_pipeline_v1" in text
    assert "G42" in text
    assert "phase_62" in text
    assert "/ui/diagnostics-promotion" in text
    assert str(ssot_meta["g42_status"]) in text
    assert "<form" not in text.lower()
    assert 'method="post"' not in text.lower()

    for row in temporary_rows:
        assert row in unescaped
    for row in promotion_rows:
        assert row in unescaped
    for row in phase12_rows["goal_rows"]:
        assert row in unescaped
    for row in phase12_rows["code_rows"]:
        assert row in unescaped
    for row in phase12_rows["acceptance_rows"]:
        assert row in unescaped

    for guard in ssot_meta["required_guards"]:
        assert guard in unescaped
    for rule in ssot_meta["global_read_rules"]:
        assert rule in unescaped
    for cmd in ssot_meta["acceptance_commands"]:
        assert cmd in unescaped
    for artifact in ssot_meta["expected_artifacts"]:
        assert artifact in unescaped

    assert re.search(rf'data-testid="diagnostics-whole-view-temporary-total">\s*{len(temporary_rows)}\s*<', text)
    assert re.search(rf'data-testid="diagnostics-whole-view-promotion-total">\s*{len(promotion_rows)}\s*<', text)
    assert re.search(rf'data-testid="diagnostics-playbook-goal-total">\s*{len(phase12_rows["goal_rows"])}\s*<', text)
    assert re.search(rf'data-testid="diagnostics-playbook-code-total">\s*{len(phase12_rows["code_rows"])}\s*<', text)
    assert re.search(
        rf'data-testid="diagnostics-playbook-acceptance-total">\s*{len(phase12_rows["acceptance_rows"])}\s*<',
        text,
    )
    assert re.search(rf'data-testid="diagnostics-required-guard-total">\s*{len(ssot_meta["required_guards"])}\s*<', text)
    assert re.search(
        rf'data-testid="diagnostics-global-read-rule-total">\s*{len(ssot_meta["global_read_rules"])}\s*<',
        text,
    )

    assert "data-testid=\"diagnostics-whole-view-temporary-1\"" in text
    assert "data-testid=\"diagnostics-whole-view-promotion-1\"" in text
    assert "data-testid=\"diagnostics-playbook-code-1\"" in text
    assert "data-testid=\"diagnostics-playbook-acceptance-1\"" in text
    assert "data-testid=\"diagnostics-required-guard-1\"" in text


def test_diagnostics_promotion_page_head_and_post_semantics() -> None:
    client = TestClient(app)
    assert client.head("/ui/diagnostics-promotion").status_code == 200
    assert client.post("/ui/diagnostics-promotion").status_code == 405
