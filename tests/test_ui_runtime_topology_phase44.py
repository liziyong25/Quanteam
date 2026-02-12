from __future__ import annotations

import html
import re
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from quant_eam.api.app import app


WHOLE_VIEW_SECTION9_RE = re.compile(r"^##\s*9(?:\s|[.:：])")
PLAYBOOK_SECTION1_RE = re.compile(r"^##\s*1(?:\s|[.:：])")
PLAYBOOK_SECTION3_RE = re.compile(r"^##\s*3(?:\s|[.:：])")
PLAYBOOK_PHASE_HEADER_RE = re.compile(r"^###\s*Phase[\u2010-\u2015-](\d+)\s*[：:]\s*(.+)$")
RUNTIME_KEYWORDS = ("docker", "compose", "api", "worker", "ui", "service", "orchestrator")


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


def _extract_whole_view_section9_entries(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    entries: list[str] = []

    for raw in lines:
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            in_section = bool(WHOLE_VIEW_SECTION9_RE.match(line)) and (
                ("仓库" in line) or ("运行形态" in line) or ("Docker" in line)
            )
            continue
        if (not in_section) or (not line) or (line == "---"):
            continue

        item = _clean_md(line)
        if item.endswith("：") and ("推荐仓库结构" in item):
            continue
        if item:
            entries.append(item)

    assert entries, "Whole View section 9 runtime topology entries must not be empty"
    assert any("docker-compose.yml" in row for row in entries), "Whole View section 9 must include docker-compose.yml entry"
    return entries


def _extract_playbook_section1_rows(path: Path) -> dict[str, list[str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    active = ""
    foundation_rows: list[str] = []
    service_rows: list[str] = []

    for raw in lines:
        line = raw.strip()
        if line.startswith("## "):
            if in_section:
                break
            in_section = bool(PLAYBOOK_SECTION1_RE.match(line)) and (("技术栈" in line) or ("stack" in line.lower()))
            continue
        if not in_section:
            continue
        if line.startswith("### "):
            if line.startswith("### 1.1"):
                active = "foundation"
                continue
            if line.startswith("### 1.2"):
                active = "service"
                continue
            active = ""
            continue
        if not line.startswith("- "):
            continue

        item = _clean_md(line[2:])
        if not item:
            continue
        if active == "foundation":
            foundation_rows.append(item)
        elif active == "service":
            service_rows.append(item)

    assert foundation_rows, "Playbook section 1.1 foundation rows must not be empty"
    assert service_rows, "Playbook section 1.2 service rows must not be empty"
    return {"foundation_rows": foundation_rows, "service_rows": service_rows}


def _extract_playbook_runtime_phase_labels(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    rows: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    current_heading = ""

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
            if current:
                rows.append(current)
            phase_no = int(m.group(1))
            current = {
                "phase_label": f"Phase-{phase_no}",
                "title": _clean_md(m.group(2)),
                "goal_rows": [],
                "acceptance_rows": [],
                "flow_rows": [],
            }
            current_heading = ""
            continue

        if current is None:
            continue
        if line.startswith("**") and line.endswith("**"):
            current_heading = _clean_md(line.strip("*"))
            continue
        if not line.startswith("- "):
            continue

        item = _clean_md(line[2:])
        if not item:
            continue
        flow_rows = current.get("flow_rows")
        if isinstance(flow_rows, list):
            flow_rows.append(item)
        if "目标" in current_heading:
            goal_rows = current.get("goal_rows")
            if isinstance(goal_rows, list) and len(goal_rows) < 3:
                goal_rows.append(item)
        if "验收" in current_heading:
            acceptance_rows = current.get("acceptance_rows")
            if isinstance(acceptance_rows, list) and len(acceptance_rows) < 3:
                acceptance_rows.append(item)

    if current:
        rows.append(current)

    labels: list[str] = []
    for row in rows:
        hay_parts = [
            str(row.get("title") or ""),
            *[str(x) for x in (row.get("goal_rows") or []) if isinstance(x, str)],
            *[str(x) for x in (row.get("acceptance_rows") or []) if isinstance(x, str)],
            *[str(x) for x in (row.get("flow_rows") or []) if isinstance(x, str)],
        ]
        haystack = " ".join(hay_parts).lower()
        if any(keyword in haystack for keyword in RUNTIME_KEYWORDS):
            labels.append(str(row.get("phase_label") or ""))

    labels = [x for x in labels if x]
    assert labels, "Playbook section 3 runtime phase labels must not be empty"
    return labels


def _ssot_runtime_topology_meta() -> dict[str, object]:
    ssot_path = Path("docs/12_workflows/skeleton_ssot_v1.yaml")
    assert ssot_path.is_file(), "SSOT yaml is required for G44 runtime-topology evidence validation"
    loaded = yaml.safe_load(ssot_path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), "SSOT yaml root must be map"

    goal_rows = loaded.get("goal_checklist")
    assert isinstance(goal_rows, list), "SSOT goal_checklist must be list"
    g44_row: dict[str, object] = {}
    for row in goal_rows:
        if isinstance(row, dict) and str(row.get("id") or "") == "G44":
            g44_row = row
            break
    assert g44_row, "SSOT goal_checklist must include G44"

    dispatch = loaded.get("phase_dispatch_plan_v2")
    assert isinstance(dispatch, dict), "SSOT phase_dispatch_plan_v2 must be map"
    phase_rows = dispatch.get("phases")
    assert isinstance(phase_rows, list), "SSOT phase_dispatch_plan_v2.phases must be list"
    assert any(
        isinstance(row, dict)
        and str(row.get("phase_id") or "") == "phase_64"
        and str(row.get("goal_id") or "") == "G44"
        for row in phase_rows
    ), "SSOT dispatch must include phase_64 -> G44"

    exceptions = loaded.get("autopilot_stop_condition_exceptions_v1")
    assert isinstance(exceptions, list), "SSOT autopilot_stop_condition_exceptions_v1 must be list"
    g44_exception: dict[str, object] = {}
    for row in exceptions:
        if isinstance(row, dict) and str(row.get("exception_id") or "") == "g44_runtime_topology_ui_scope":
            g44_exception = row
            break
    assert g44_exception, "SSOT must include g44_runtime_topology_ui_scope exception"

    preauth = g44_exception.get("preauthorized_scope") if isinstance(g44_exception.get("preauthorized_scope"), dict) else {}
    required_guards = [str(x) for x in (preauth.get("required_guards") or []) if isinstance(x, str)]
    assert required_guards, "G44 preauthorized_scope.required_guards must not be empty"

    ui_requirements = loaded.get("ui_requirements_v1")
    assert isinstance(ui_requirements, dict), "SSOT ui_requirements_v1 must be map"
    ui_ports = ui_requirements.get("ui_ports")
    assert isinstance(ui_ports, dict), "SSOT ui_requirements_v1.ui_ports must be map"
    assert "backend_api_host_port" in ui_ports, "SSOT ui_ports must include backend_api_host_port"
    assert "frontend_ui_host_port" in ui_ports, "SSOT ui_ports must include frontend_ui_host_port"

    runtime_pref = loaded.get("runtime_preferences_v1")
    assert isinstance(runtime_pref, dict), "SSOT runtime_preferences_v1 must be map"
    min_set = runtime_pref.get("acceptance_evidence_min_set")
    assert isinstance(min_set, dict), "SSOT runtime_preferences_v1.acceptance_evidence_min_set must be map"
    required_commands = [str(x) for x in (min_set.get("required_commands") or []) if isinstance(x, str)]
    assert required_commands, "SSOT runtime required commands must not be empty"

    expected_artifacts = [str(x) for x in (g44_row.get("expected_artifacts") or []) if isinstance(x, str)]
    assert expected_artifacts, "G44 expected_artifacts must not be empty"

    acceptance_commands = [str(x) for x in (g44_row.get("acceptance_commands") or []) if isinstance(x, str)]
    assert acceptance_commands, "G44 acceptance_commands must not be empty"

    return {
        "g44_status": str(g44_row.get("status_now") or "unknown"),
        "required_guards": required_guards,
        "ui_ports": {str(k): str(v) for k, v in ui_ports.items()},
        "ui_port_total": len(ui_ports),
        "required_commands": required_commands,
        "expected_artifacts": expected_artifacts,
        "acceptance_commands": acceptance_commands,
    }


def test_runtime_topology_page_renders_whole_view_playbook_and_ssot_evidence() -> None:
    whole_view_doc = _find_doc(suffix="Whole View Framework.md")
    playbook_doc = _find_doc(suffix="Implementation Phases Playbook.md")
    whole_view_entries = _extract_whole_view_section9_entries(whole_view_doc)
    section1_rows = _extract_playbook_section1_rows(playbook_doc)
    runtime_phase_labels = _extract_playbook_runtime_phase_labels(playbook_doc)
    ssot_meta = _ssot_runtime_topology_meta()

    client = TestClient(app)
    r = client.get("/ui/runtime-topology")
    assert r.status_code == 200
    text = r.text
    unescaped = html.unescape(text)

    assert "Whole View Runtime Topology and Service Ports Read-Only Evidence" in text
    assert "GET/HEAD only" in text
    assert "no write actions" in text
    assert "no holdout expansion" in text
    assert "Whole View Section 9 Runtime Topology" in text
    assert "Playbook Section 1 Service Context" in text
    assert "Playbook Phase Flow/Context (Section 3)" in text
    assert "SSOT Runtime Topology Governance Evidence" in text
    assert "9. 仓库与运行形态（Linux + Docker + Python）" in unescaped
    assert "phase_dispatch_plan_v2" in text
    assert "g44_runtime_topology_ui_scope" in text
    assert "G44" in text
    assert "phase_64" in text
    assert "/ui/runtime-topology" in text
    assert str(ssot_meta["g44_status"]) in text
    assert "<form" not in text.lower()
    assert 'method="post"' not in text.lower()

    for row in whole_view_entries:
        assert row in unescaped
    for row in section1_rows["foundation_rows"]:
        assert row in unescaped
    for row in section1_rows["service_rows"]:
        assert row in unescaped
    for label in runtime_phase_labels:
        assert label in text

    for row in ssot_meta["required_guards"]:
        assert row in unescaped
    for row in ssot_meta["required_commands"]:
        assert row in unescaped
    for row in ssot_meta["expected_artifacts"]:
        assert row in unescaped
    for row in ssot_meta["acceptance_commands"]:
        assert row in unescaped
    for key, value in ssot_meta["ui_ports"].items():
        assert key in text
        assert value in text

    assert re.search(rf'data-testid="runtime-topology-structure-total">\s*{len(whole_view_entries)}\s*<', text)
    assert re.search(
        rf'data-testid="runtime-topology-playbook-foundation-total">\s*{len(section1_rows["foundation_rows"])}\s*<',
        text,
    )
    assert re.search(
        rf'data-testid="runtime-topology-playbook-service-total">\s*{len(section1_rows["service_rows"])}\s*<',
        text,
    )
    assert re.search(rf'data-testid="runtime-topology-playbook-phase-total">\s*{len(runtime_phase_labels)}\s*<', text)
    assert re.search(rf'data-testid="runtime-topology-ui-port-total">\s*{int(ssot_meta["ui_port_total"])}\s*<', text)
    assert re.search(
        rf'data-testid="runtime-topology-required-guard-total">\s*{len(ssot_meta["required_guards"])}\s*<',
        text,
    )
    assert re.search(
        rf'data-testid="runtime-topology-required-command-total">\s*{len(ssot_meta["required_commands"])}\s*<',
        text,
    )
    assert re.search(
        rf'data-testid="runtime-topology-expected-artifact-total">\s*{len(ssot_meta["expected_artifacts"])}\s*<',
        text,
    )
    assert re.search(
        rf'data-testid="runtime-topology-acceptance-command-total">\s*{len(ssot_meta["acceptance_commands"])}\s*<',
        text,
    )
    assert "data-testid=\"runtime-topology-row-1\"" in text
    assert "data-testid=\"runtime-topology-phase-row-1\"" in text
    assert "data-testid=\"runtime-topology-port-row-1\"" in text
    assert "data-testid=\"runtime-topology-required-guard-1\"" in text


def test_runtime_topology_page_head_and_post_semantics() -> None:
    client = TestClient(app)
    assert client.head("/ui/runtime-topology").status_code == 200
    assert client.post("/ui/runtime-topology").status_code == 405
