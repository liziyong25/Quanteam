from __future__ import annotations

import html
import re
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from quant_eam.api.app import app


SECTION8_RE = re.compile(r"^##\s*8(?:\s|[.:：])")
ITEM_RE = re.compile(r"^(\d+)\)\s*(.+)$")
EXPECTED_ROUTE_VIEW_ROWS = [
    ("/ui", "Idea input", "index.html"),
    ("/ui/jobs", "Runs queue", "jobs.html"),
    ("/ui/jobs/{job_id}", "Blueprint and review checkpoints", "job.html"),
    ("/ui/runs/{run_id}", "Dossier detail", "run.html"),
    ("/ui/runs/{run_id}/gates", "Gate detail", "run_gates.html"),
    ("/ui/cards/{card_id}", "Registry card detail", "card.html"),
    ("/ui/composer", "Composer", "composer.html"),
]
EXPECTED_MAPPED_ROUTES = sorted({row[0] for row in EXPECTED_ROUTE_VIEW_ROWS})


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


def _extract_whole_view_section8_checklist(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    out: list[str] = []

    for raw in lines:
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            in_section = bool(SECTION8_RE.match(line)) and ("UI" in line)
            continue
        if not in_section or not line:
            continue

        m = ITEM_RE.match(line)
        if not m:
            continue
        out.append(_clean_md(m.group(2)))

    assert len(out) == 8, "Whole View section 8 checklist extraction must return 8 rows"
    return out


def _ssot_ui_coverage_meta() -> dict[str, object]:
    ssot_path = Path("docs/12_workflows/agents_ui_ssot_v1.yaml")
    assert ssot_path.is_file(), "SSOT yaml is required for G43 UI coverage matrix validation"
    loaded = yaml.safe_load(ssot_path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), "SSOT yaml root must be map"

    goal_rows = loaded.get("goal_checklist")
    assert isinstance(goal_rows, list), "SSOT goal_checklist must be list"
    g43_row: dict[str, object] = {}
    for row in goal_rows:
        if isinstance(row, dict) and str(row.get("id") or "") == "G43":
            g43_row = row
            break
    assert g43_row, "SSOT goal_checklist must include G43"

    dispatch = loaded.get("phase_dispatch_plan_v2")
    assert isinstance(dispatch, dict), "SSOT phase_dispatch_plan_v2 must be map"
    phase_rows = dispatch.get("phases")
    assert isinstance(phase_rows, list), "SSOT phase_dispatch_plan_v2.phases must be list"
    assert any(
        isinstance(row, dict)
        and str(row.get("phase_id") or "") == "phase_63"
        and str(row.get("goal_id") or "") == "G43"
        for row in phase_rows
    ), "SSOT dispatch must include phase_63 -> G43"

    exceptions = loaded.get("autopilot_stop_condition_exceptions_v1")
    assert isinstance(exceptions, list), "SSOT autopilot_stop_condition_exceptions_v1 must be list"
    g43_exception: dict[str, object] = {}
    for row in exceptions:
        if isinstance(row, dict) and str(row.get("exception_id") or "") == "g43_ui_coverage_matrix_scope":
            g43_exception = row
            break
    assert g43_exception, "SSOT must include g43_ui_coverage_matrix_scope exception"

    preauth = g43_exception.get("preauthorized_scope") if isinstance(g43_exception.get("preauthorized_scope"), dict) else {}
    required_guards = [str(x) for x in (preauth.get("required_guards") or []) if isinstance(x, str)]
    assert required_guards, "G43 preauthorized_scope.required_guards must not be empty"

    expected_artifacts = [str(x) for x in (g43_row.get("expected_artifacts") or []) if isinstance(x, str)]
    assert expected_artifacts, "G43 expected_artifacts must not be empty"

    acceptance_commands = [str(x) for x in (g43_row.get("acceptance_commands") or []) if isinstance(x, str)]
    assert acceptance_commands, "G43 acceptance_commands must not be empty"

    return {
        "g43_status": str(g43_row.get("status_now") or "unknown"),
        "required_guards": required_guards,
        "expected_artifacts": expected_artifacts,
        "acceptance_commands": acceptance_commands,
    }


def test_ui_coverage_matrix_page_renders_whole_view_route_inventory_and_ssot_evidence() -> None:
    whole_view_doc = _find_doc(suffix="Whole View Framework.md")
    checklist_rows = _extract_whole_view_section8_checklist(whole_view_doc)
    ssot_meta = _ssot_ui_coverage_meta()

    client = TestClient(app)
    r = client.get("/ui/ui-coverage-matrix")
    assert r.status_code == 200
    text = r.text
    unescaped = html.unescape(text)

    assert "Whole View UI Eight-Page Coverage Matrix" in text
    assert "GET/HEAD only" in text
    assert "no write actions" in text
    assert "no holdout expansion" in text
    assert "Whole View Section 8 Checklist Coverage Matrix" in text
    assert "Current UI Route Inventory" in text
    assert "SSOT G43 Governance Evidence" in text
    assert "8. UI 信息架构（不看源码的审阅体验）" in unescaped
    assert "phase_dispatch_plan_v2" in text
    assert "g43_ui_coverage_matrix_scope" in text
    assert "G43" in text
    assert "phase_63" in text
    assert "/ui/ui-coverage-matrix" in text
    assert str(ssot_meta["g43_status"]) in text
    assert "<form" not in text.lower()
    assert 'method="post"' not in text.lower()

    for row in checklist_rows:
        assert row in unescaped
    for route, view_name, template_name in EXPECTED_ROUTE_VIEW_ROWS:
        assert route in text
        assert view_name in unescaped
        assert template_name in text

    assert "/ui/jobs/idea" in text

    for row in ssot_meta["required_guards"]:
        assert row in unescaped
    for row in ssot_meta["expected_artifacts"]:
        assert row in unescaped
    for row in ssot_meta["acceptance_commands"]:
        assert row in unescaped

    assert re.search(rf'data-testid="ui-coverage-checklist-total">\s*{len(checklist_rows)}\s*<', text)
    assert re.search(rf'data-testid="ui-coverage-mapped-route-total">\s*{len(EXPECTED_MAPPED_ROUTES)}\s*<', text)
    assert re.search(rf'data-testid="ui-coverage-required-guard-total">\s*{len(ssot_meta["required_guards"])}\s*<', text)
    assert re.search(rf'data-testid="ui-coverage-expected-artifact-total">\s*{len(ssot_meta["expected_artifacts"])}\s*<', text)
    assert re.search(rf'data-testid="ui-coverage-acceptance-command-total">\s*{len(ssot_meta["acceptance_commands"])}\s*<', text)

    assert "data-testid=\"ui-coverage-row-1\"" in text
    assert "data-testid=\"ui-coverage-route-row-1\"" in text
    assert "data-testid=\"ui-coverage-required-guard-1\"" in text


def test_ui_coverage_matrix_page_head_and_post_semantics() -> None:
    client = TestClient(app)
    assert client.head("/ui/ui-coverage-matrix").status_code == 200
    assert client.post("/ui/ui-coverage-matrix").status_code == 405
