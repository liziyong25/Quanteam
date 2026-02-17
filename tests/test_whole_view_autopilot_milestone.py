from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "whole_view_autopilot.py"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_requirement_docs(repo: Path) -> None:
    _write(repo / "Quant‑EAM Whole View Framework.md（v0.5‑draft）.md", "# Whole View Requirement Root\n")
    _write(repo / "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md", "# QA Fetch Requirement Root\n")
    _write(repo / "docs/00_overview/workbench_ui_productization_v1.md", "# Workbench Requirement Root\n")


def _seed_ssot(
    repo: Path,
    *,
    statuses: tuple[str, str],
    requirements_trace: list[dict] | None = None,
    impl_depends_on: list[str] | None = None,
) -> Path:
    g1, g2 = statuses
    req_rows = requirements_trace or [
        {
            "req_id": "WV-001",
            "source_document": "Quant‑EAM Whole View Framework.md（v0.5‑draft）.md",
            "source_line": 1,
            "owner_track": "skeleton",
            "clause": "Whole View Requirement Root",
            "depends_on_req_ids": [],
            "status_now": "implemented" if g1 == "implemented" else "planned",
            "mapped_goal_ids": ["G01"],
            "acceptance_commands": [],
            "acceptance_verified": g1 == "implemented",
            "capability_cluster_id": "",
        },
        {
            "req_id": "QF-001",
            "source_document": "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md",
            "source_line": 1,
            "owner_track": "impl_fetchdata",
            "clause": "QA Fetch Requirement Root",
            "depends_on_req_ids": ["WV-001"],
            "status_now": "implemented" if g2 == "implemented" else "planned",
            "mapped_goal_ids": ["G02"],
            "acceptance_commands": [],
            "acceptance_verified": g2 == "implemented",
            "capability_cluster_id": "",
        },
        {
            "req_id": "WB-001",
            "source_document": "docs/00_overview/workbench_ui_productization_v1.md",
            "source_line": 1,
            "owner_track": "impl_workbench",
            "clause": "Workbench Requirement Root",
            "depends_on_req_ids": ["WV-001"],
            "status_now": "implemented",
            "mapped_goal_ids": [],
            "acceptance_commands": [],
            "acceptance_verified": True,
            "capability_cluster_id": "",
        },
    ]
    ssot: dict = {
        "schema_version": "skeleton_ssot_v1",
        "goal_checklist": [
            {
                "id": "G01",
                "title": "Skeleton requirement implementation",
                "status_now": g1,
                "track": "skeleton",
                "depends_on": [],
                "requirement_ids": ["WV-001"],
                "phase_doc_path": "docs/08_phases/00_skeleton/phase_skel_g01.md",
                "allowed_paths": ["docs/08_phases/00_skeleton/phase_skel_g01.md"],
                "acceptance_commands": ["python3 scripts/check_docs_tree.py"],
            },
            {
                "id": "G02",
                "title": "Impl requirement implementation",
                "status_now": g2,
                "track": "impl_fetchdata",
                "depends_on": impl_depends_on if impl_depends_on is not None else ["G01"],
                "requirement_ids": ["QF-001"],
                "phase_doc_path": "docs/08_phases/10_impl_fetchdata/phase_fetch_g02.md",
                "allowed_paths": ["docs/08_phases/10_impl_fetchdata/phase_fetch_g02.md"],
                "acceptance_commands": ["python3 scripts/check_docs_tree.py"],
            },
        ],
        "requirements_trace_v1": req_rows,
        "whole_view_autopilot_v1": {
            "done_criteria": {"goal_checklist_all_implemented": True},
            "rolling_goal_policy": {
                "enabled": True,
                "trigger_when_no_planned_or_partial": True,
            },
        },
        "queue_empty_generation_protocol_v1": {
            "status_now": "active",
            "enabled": False,
            "trigger_when_goal_queue_empty": True,
            "allow_generate_after_done": False,
        },
    }
    out = repo / "docs/12_workflows/skeleton_ssot_v1.yaml"
    _write(out, yaml.safe_dump(ssot, sort_keys=False, allow_unicode=True))
    return out


def _run_autopilot(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(SCRIPT), *args]
    return subprocess.run(cmd, cwd=repo, text=True, capture_output=True, check=False)


def test_autopilot_migrate_adds_required_sections(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _seed_requirement_docs(repo)
    ssot_path = _seed_ssot(repo, statuses=("implemented", "planned"))
    r = _run_autopilot(repo, "--mode", "migrate", "--skip-gates", "--dry-run", "--disable-push")
    assert r.returncode == 0, r.stderr
    doc = yaml.safe_load(ssot_path.read_text(encoding="utf-8"))
    assert isinstance(doc.get("requirements_trace_v1"), list)
    assert isinstance(doc.get("capability_clusters_v1"), list)
    assert isinstance(doc.get("milestone_policy_v1"), dict)
    assert isinstance(doc.get("milestone_history_v1"), list)
    assert isinstance(doc.get("interface_contracts_v1"), list)
    assert isinstance(doc.get("planning_policy_v2"), dict)
    assert isinstance(doc.get("requirement_splitter_v1"), dict)
    assert isinstance(doc.get("skill_registry_v1"), dict)
    assert isinstance(doc.get("skill_binding_policy_v1"), dict)
    assert isinstance(doc.get("skill_enforcement_v1"), dict)
    assert isinstance(doc.get("difficulty_scoring_v1"), dict)
    assert isinstance(doc.get("reasoning_tiers_v1"), dict)
    assert doc["planning_policy_v2"]["generation_mode"] == "requirement_gap_only"
    assert isinstance(doc["planning_policy_v2"].get("goal_todo_planner_v1"), dict)
    assert isinstance(doc["planning_policy_v2"].get("architect_preplan_v1"), dict)
    registry_ids = {
        str(x.get("id") or "")
        for x in (doc.get("skill_registry_v1", {}).get("skills") or [])
        if isinstance(x, dict)
    }
    assert "architect-planner" in registry_ids
    assert "controller_preplan_skills" in (doc.get("skill_binding_policy_v1") or {})
    assert all("requirement_ids" in row for row in doc.get("goal_checklist", []))
    assert all("required_skills" in row for row in doc.get("goal_checklist", []))
    assert all("difficulty_score" in row for row in doc.get("goal_checklist", []))
    assert all("reasoning_tier" in row for row in doc.get("goal_checklist", []))
    assert all("owner_track" in row for row in doc.get("requirements_trace_v1", []))


def test_architect_preplan_runs_before_generation(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _seed_requirement_docs(repo)
    ssot_path = _seed_ssot(
        repo,
        statuses=("implemented", "implemented"),
        requirements_trace=[
            {
                "req_id": "WV-001",
                "source_document": "Quant‑EAM Whole View Framework.md（v0.5‑draft）.md",
                "source_line": 1,
                "owner_track": "skeleton",
                "clause": "Whole View Requirement Root",
                "depends_on_req_ids": [],
                "status_now": "implemented",
                "mapped_goal_ids": ["G01"],
                "acceptance_verified": True,
                "capability_cluster_id": "",
            },
            {
                "req_id": "QF-001",
                "source_document": "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md",
                "source_line": 1,
                "owner_track": "impl_fetchdata",
                "clause": "QA Fetch Requirement Root",
                "depends_on_req_ids": ["WV-001"],
                "status_now": "implemented",
                "mapped_goal_ids": ["G02"],
                "acceptance_verified": True,
                "capability_cluster_id": "",
            },
            {
                "req_id": "WV-900",
                "source_document": "Quant‑EAM Whole View Framework.md（v0.5‑draft）.md",
                "source_line": 10,
                "owner_track": "skeleton",
                "clause": "Architect preplan requirement gap skeleton",
                "depends_on_req_ids": [],
                "status_now": "planned",
                "mapped_goal_ids": [],
                "acceptance_verified": False,
                "capability_cluster_id": "",
            },
            {
                "req_id": "QF-900",
                "source_document": "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md",
                "source_line": 12,
                "owner_track": "impl_fetchdata",
                "clause": "Architect preplan requirement gap impl",
                "depends_on_req_ids": ["WV-900"],
                "status_now": "planned",
                "mapped_goal_ids": [],
                "acceptance_verified": False,
                "capability_cluster_id": "",
            },
        ],
    )
    r = _run_autopilot(repo, "--mode", "plan", "--skip-gates", "--dry-run", "--disable-push")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert isinstance(out.get("architect_preplan"), dict), out
    assert (out.get("architect_preplan") or {}).get("requirement_priority"), out
    doc = yaml.safe_load(ssot_path.read_text(encoding="utf-8"))
    policy = (doc.get("planning_policy_v2") or {}).get("architect_preplan_v1") or {}
    latest = policy.get("latest_plan") if isinstance(policy.get("latest_plan"), dict) else {}
    assert latest.get("requirement_priority"), doc


def test_autopilot_plan_selection_enforces_interface_gate(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _seed_requirement_docs(repo)
    _seed_ssot(
        repo,
        statuses=("planned", "planned"),
        impl_depends_on=[],
        requirements_trace=[
            {
                "req_id": "WV-001",
                "source_document": "Quant‑EAM Whole View Framework.md（v0.5‑draft）.md",
                "source_line": 1,
                "owner_track": "skeleton",
                "clause": "Whole View Requirement Root",
                "depends_on_req_ids": [],
                "status_now": "planned",
                "mapped_goal_ids": ["G01"],
                "acceptance_verified": False,
                "capability_cluster_id": "",
            },
            {
                "req_id": "QF-001",
                "source_document": "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md",
                "source_line": 1,
                "owner_track": "impl_fetchdata",
                "clause": "QA Fetch Requirement Root",
                "depends_on_req_ids": ["WV-001"],
                "status_now": "planned",
                "mapped_goal_ids": ["G02"],
                "acceptance_verified": False,
                "capability_cluster_id": "",
            },
        ],
    )
    r = _run_autopilot(repo, "--mode", "plan", "--skip-gates", "--dry-run", "--disable-push")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    selected = out.get("selected_goal_ids") or []
    assert selected == ["G01"], out


def test_autopilot_plan_selection_enforces_interface_gate_for_workbench(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _seed_requirement_docs(repo)
    ssot = {
        "schema_version": "skeleton_ssot_v1",
        "goal_checklist": [
            {
                "id": "G01",
                "title": "Skeleton requirement implementation",
                "status_now": "planned",
                "track": "skeleton",
                "depends_on": [],
                "requirement_ids": ["WV-001"],
                "phase_doc_path": "docs/08_phases/00_skeleton/phase_skel_g01.md",
                "allowed_paths": ["docs/08_phases/00_skeleton/phase_skel_g01.md"],
                "acceptance_commands": ["python3 scripts/check_docs_tree.py"],
            },
            {
                "id": "G03",
                "title": "Workbench requirement implementation",
                "status_now": "planned",
                "track": "impl_workbench",
                "depends_on": [],
                "requirement_ids": ["WB-010"],
                "phase_doc_path": "docs/08_phases/10_impl_workbench/phase_workbench_g03.md",
                "allowed_paths": ["docs/08_phases/10_impl_workbench/phase_workbench_g03.md"],
                "acceptance_commands": ["python3 scripts/check_docs_tree.py"],
            },
        ],
        "requirements_trace_v1": [
            {
                "req_id": "WV-001",
                "source_document": "Quant‑EAM Whole View Framework.md（v0.5‑draft）.md",
                "source_line": 1,
                "owner_track": "skeleton",
                "clause": "Whole View Requirement Root",
                "depends_on_req_ids": [],
                "status_now": "planned",
                "mapped_goal_ids": ["G01"],
                "acceptance_verified": False,
                "capability_cluster_id": "",
            },
            {
                "req_id": "WB-010",
                "source_document": "docs/00_overview/workbench_ui_productization_v1.md",
                "source_line": 1,
                "owner_track": "impl_workbench",
                "clause": "Workbench Requirement Root",
                "depends_on_req_ids": ["WV-001"],
                "status_now": "planned",
                "mapped_goal_ids": ["G03"],
                "acceptance_verified": False,
                "capability_cluster_id": "",
            },
        ],
        "whole_view_autopilot_v1": {
            "done_criteria": {"goal_checklist_all_implemented": True},
            "rolling_goal_policy": {
                "enabled": True,
                "trigger_when_no_planned_or_partial": True,
            },
        },
        "queue_empty_generation_protocol_v1": {
            "status_now": "active",
            "enabled": False,
            "trigger_when_goal_queue_empty": True,
            "allow_generate_after_done": False,
        },
    }
    ssot_path = repo / "docs/12_workflows/skeleton_ssot_v1.yaml"
    _write(ssot_path, yaml.safe_dump(ssot, sort_keys=False, allow_unicode=True))
    r = _run_autopilot(repo, "--mode", "plan", "--skip-gates", "--dry-run", "--disable-push")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    selected = out.get("selected_goal_ids") or []
    assert selected == ["G01"], out


def test_autopilot_requirement_gap_generation_creates_bound_goals(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _seed_requirement_docs(repo)
    ssot_path = _seed_ssot(
        repo,
        statuses=("implemented", "implemented"),
        requirements_trace=[
            {
                "req_id": "WV-001",
                "source_document": "Quant‑EAM Whole View Framework.md（v0.5‑draft）.md",
                "source_line": 1,
                "owner_track": "skeleton",
                "clause": "Whole View Requirement Root",
                "depends_on_req_ids": [],
                "status_now": "implemented",
                "mapped_goal_ids": ["G01"],
                "acceptance_verified": True,
                "capability_cluster_id": "",
            },
            {
                "req_id": "QF-001",
                "source_document": "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md",
                "source_line": 1,
                "owner_track": "impl_fetchdata",
                "clause": "QA Fetch Requirement Root",
                "depends_on_req_ids": ["WV-001"],
                "status_now": "implemented",
                "mapped_goal_ids": ["G02"],
                "acceptance_verified": True,
                "capability_cluster_id": "",
            },
            {
                "req_id": "WV-900",
                "source_document": "Quant‑EAM Whole View Framework.md（v0.5‑draft）.md",
                "source_line": 1,
                "owner_track": "skeleton",
                "clause": "Interface requirement gap",
                "depends_on_req_ids": [],
                "status_now": "planned",
                "mapped_goal_ids": [],
                "acceptance_verified": False,
                "capability_cluster_id": "",
            },
            {
                "req_id": "QF-900",
                "source_document": "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md",
                "source_line": 1,
                "owner_track": "impl_fetchdata",
                "clause": "Runtime requirement gap",
                "depends_on_req_ids": ["WV-900"],
                "status_now": "planned",
                "mapped_goal_ids": [],
                "acceptance_verified": False,
                "capability_cluster_id": "",
            },
        ],
    )
    r = _run_autopilot(repo, "--mode", "plan", "--skip-gates", "--dry-run", "--disable-push")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    generated = out.get("generated_goal_ids") or []
    assert len(generated) >= 2, out

    doc = yaml.safe_load(ssot_path.read_text(encoding="utf-8"))
    goals = [x for x in (doc.get("goal_checklist") or []) if isinstance(x, dict)]
    generated_rows = [x for x in goals if x.get("id") in set(generated)]
    tracks = {str(x.get("track") or "") for x in generated_rows}
    assert {"skeleton", "impl_fetchdata"}.issubset(tracks), tracks
    assert all(isinstance(x.get("requirement_ids"), list) and x.get("requirement_ids") for x in generated_rows)
    assert all(isinstance(x.get("todo_checklist"), list) and x.get("todo_checklist") for x in generated_rows)
    assert all(isinstance(x.get("risk_notes"), list) and x.get("risk_notes") for x in generated_rows)
    assert all(isinstance(x.get("parallel_hints"), list) and x.get("parallel_hints") for x in generated_rows)
    for row in generated_rows:
        phase_doc = str(row.get("phase_doc_path") or "")
        if str(row.get("track")) == "skeleton":
            assert phase_doc.startswith("docs/08_phases/00_skeleton/")
        if str(row.get("track")) == "impl_fetchdata":
            assert phase_doc.startswith("docs/08_phases/10_impl_fetchdata/")
            assert "python3 -m pytest -q tests/test_fetch_contracts_phase77.py tests/test_qa_fetch_probe.py tests/test_qa_fetch_resolver.py" in (
                row.get("acceptance_commands") or []
            )
            assert "python3 -m pytest -q tests/test_qa_fetch_runtime.py" not in (row.get("acceptance_commands") or [])
        assert (repo / phase_doc).is_file()


def test_autopilot_requirement_gap_generation_bundles_adjacent_impl_requirements(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _seed_requirement_docs(repo)
    ssot = {
        "schema_version": "skeleton_ssot_v1",
        "goal_checklist": [
            {
                "id": "G01",
                "title": "Skeleton requirement implementation",
                "status_now": "implemented",
                "track": "skeleton",
                "depends_on": [],
                "requirement_ids": ["WV-001"],
                "phase_doc_path": "docs/08_phases/00_skeleton/phase_skel_g01.md",
                "allowed_paths": ["docs/08_phases/00_skeleton/phase_skel_g01.md"],
                "acceptance_commands": ["python3 scripts/check_docs_tree.py"],
            },
            {
                "id": "G02",
                "title": "Impl requirement implementation",
                "status_now": "implemented",
                "track": "impl_fetchdata",
                "depends_on": ["G01"],
                "requirement_ids": ["QF-001"],
                "phase_doc_path": "docs/08_phases/10_impl_fetchdata/phase_fetch_g02.md",
                "allowed_paths": ["docs/08_phases/10_impl_fetchdata/phase_fetch_g02.md"],
                "acceptance_commands": ["python3 scripts/check_docs_tree.py"],
            },
        ],
        "requirements_trace_v1": [
            {
                "req_id": "WV-001",
                "source_document": "Quant‑EAM Whole View Framework.md（v0.5‑draft）.md",
                "source_line": 1,
                "owner_track": "skeleton",
                "clause": "Whole View Requirement Root",
                "depends_on_req_ids": [],
                "status_now": "implemented",
                "mapped_goal_ids": ["G01"],
                "acceptance_verified": True,
                "capability_cluster_id": "",
            },
            {
                "req_id": "QF-001",
                "source_document": "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md",
                "source_line": 1,
                "owner_track": "impl_fetchdata",
                "clause": "QA Fetch Requirement Root",
                "depends_on_req_ids": ["WV-001"],
                "status_now": "implemented",
                "mapped_goal_ids": ["G02"],
                "acceptance_verified": True,
                "capability_cluster_id": "",
            },
            {
                "req_id": "QF-001",
                "source_document": "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md",
                "source_line": 1,
                "owner_track": "impl_fetchdata",
                "clause": "QA Fetch Requirement Root",
                "depends_on_req_ids": ["WV-001"],
                "status_now": "implemented",
                "mapped_goal_ids": ["G02"],
                "acceptance_verified": True,
                "capability_cluster_id": "",
            },
            {
                "req_id": "QF-032",
                "source_document": "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md",
                "source_line": 62,
                "owner_track": "impl_fetchdata",
                "clause": "Data structural sanity checks",
                "depends_on_req_ids": ["WV-001"],
                "status_now": "planned",
                "mapped_goal_ids": [],
                "acceptance_verified": False,
                "capability_cluster_id": "",
            },
            {
                "req_id": "QF-033",
                "source_document": "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md",
                "source_line": 63,
                "owner_track": "impl_fetchdata",
                "clause": "Golden query regression and drift report",
                "depends_on_req_ids": ["WV-001"],
                "status_now": "planned",
                "mapped_goal_ids": [],
                "acceptance_verified": False,
                "capability_cluster_id": "",
            },
        ],
        "whole_view_autopilot_v1": {
            "done_criteria": {"goal_checklist_all_implemented": True},
            "rolling_goal_policy": {"enabled": True, "trigger_when_no_planned_or_partial": True},
        },
        "planning_policy_v2": {
            "generation_mode": "requirement_gap_only",
            "goal_bundle_policy": {
                "enabled": True,
                "max_requirements_per_goal": 3,
                "minimum_bundle_size": 2,
                "source_line_window": 8,
                "require_same_source_document": True,
                "require_same_parent_requirement": True,
            },
        },
        "queue_empty_generation_protocol_v1": {
            "status_now": "active",
            "enabled": False,
            "trigger_when_goal_queue_empty": True,
            "allow_generate_after_done": False,
        },
    }
    ssot_path = repo / "docs/12_workflows/skeleton_ssot_v1.yaml"
    _write(ssot_path, yaml.safe_dump(ssot, sort_keys=False, allow_unicode=True))

    r = _run_autopilot(repo, "--mode", "plan", "--skip-gates", "--dry-run", "--disable-push")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    generated = out.get("generated_goal_ids") or []
    assert generated, out

    doc = yaml.safe_load(ssot_path.read_text(encoding="utf-8"))
    goals = [x for x in (doc.get("goal_checklist") or []) if isinstance(x, dict)]
    generated_rows = [x for x in goals if x.get("id") in set(generated)]
    row = next(x for x in generated_rows if str(x.get("track") or "") == "impl_fetchdata")
    req_ids = [str(x) for x in (row.get("requirement_ids") or [])]
    assert "QF-032" in req_ids and "QF-033" in req_ids


def test_autopilot_bundle_exact_parent_signature_prevents_mixed_parent_bundle(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _seed_requirement_docs(repo)
    ssot = {
        "schema_version": "skeleton_ssot_v1",
        "goal_checklist": [
            {
                "id": "G01",
                "title": "Skeleton requirement implementation",
                "status_now": "implemented",
                "track": "skeleton",
                "depends_on": [],
                "requirement_ids": ["WV-001"],
                "phase_doc_path": "docs/08_phases/00_skeleton/phase_skel_g01.md",
                "allowed_paths": ["docs/08_phases/00_skeleton/phase_skel_g01.md"],
                "acceptance_commands": ["python3 scripts/check_docs_tree.py"],
            },
            {
                "id": "G02",
                "title": "Impl requirement implementation",
                "status_now": "implemented",
                "track": "impl_fetchdata",
                "depends_on": ["G01"],
                "requirement_ids": ["QF-001"],
                "phase_doc_path": "docs/08_phases/10_impl_fetchdata/phase_fetch_g02.md",
                "allowed_paths": ["docs/08_phases/10_impl_fetchdata/phase_fetch_g02.md"],
                "acceptance_commands": ["python3 scripts/check_docs_tree.py"],
            },
        ],
        "requirements_trace_v1": [
            {
                "req_id": "WV-001",
                "source_document": "Quant‑EAM Whole View Framework.md（v0.5‑draft）.md",
                "source_line": 1,
                "owner_track": "skeleton",
                "clause": "Whole View Requirement Root",
                "depends_on_req_ids": [],
                "status_now": "implemented",
                "mapped_goal_ids": ["G01"],
                "acceptance_verified": True,
                "capability_cluster_id": "",
            },
            {
                "req_id": "QF-001",
                "source_document": "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md",
                "source_line": 1,
                "owner_track": "impl_fetchdata",
                "clause": "QA Fetch Requirement Root",
                "depends_on_req_ids": ["WV-001"],
                "status_now": "implemented",
                "mapped_goal_ids": ["G02"],
                "acceptance_verified": True,
                "capability_cluster_id": "",
            },
            {
                "req_id": "QF-032",
                "source_document": "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md",
                "source_line": 62,
                "owner_track": "impl_fetchdata",
                "clause": "Data structural sanity checks",
                "depends_on_req_ids": ["WV-001"],
                "status_now": "planned",
                "mapped_goal_ids": [],
                "acceptance_verified": False,
                "capability_cluster_id": "",
            },
            {
                "req_id": "QF-033",
                "source_document": "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md",
                "source_line": 63,
                "owner_track": "impl_fetchdata",
                "clause": "Golden query regression and drift report",
                "depends_on_req_ids": ["WV-001", "QF-001"],
                "status_now": "planned",
                "mapped_goal_ids": [],
                "acceptance_verified": False,
                "capability_cluster_id": "",
            },
        ],
        "whole_view_autopilot_v1": {
            "done_criteria": {"goal_checklist_all_implemented": True},
            "rolling_goal_policy": {"enabled": True, "trigger_when_no_planned_or_partial": True},
        },
        "planning_policy_v2": {
            "generation_mode": "requirement_gap_only",
            "goal_bundle_policy": {
                "enabled": True,
                "max_requirements_per_goal": 6,
                "minimum_bundle_size": 2,
                "source_line_window": 10,
                "require_same_source_document": True,
                "require_same_parent_requirement": True,
                "require_exact_parent_signature": False,
                "track_overrides": {
                    "impl_fetchdata": {
                        "max_requirements_per_goal": 4,
                        "minimum_bundle_size": 2,
                        "source_line_window": 10,
                        "require_same_source_document": True,
                        "require_same_parent_requirement": True,
                        "require_exact_parent_signature": True,
                    }
                },
            },
        },
        "queue_empty_generation_protocol_v1": {
            "status_now": "active",
            "enabled": False,
            "trigger_when_goal_queue_empty": True,
            "allow_generate_after_done": False,
        },
    }
    ssot_path = repo / "docs/12_workflows/skeleton_ssot_v1.yaml"
    _write(ssot_path, yaml.safe_dump(ssot, sort_keys=False, allow_unicode=True))

    r = _run_autopilot(repo, "--mode", "plan", "--skip-gates", "--dry-run", "--disable-push")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    generated = out.get("generated_goal_ids") or []
    assert generated, out

    doc = yaml.safe_load(ssot_path.read_text(encoding="utf-8"))
    goals = [x for x in (doc.get("goal_checklist") or []) if isinstance(x, dict)]
    generated_rows = [x for x in goals if x.get("id") in set(generated)]
    row = next(x for x in generated_rows if str(x.get("track") or "") == "impl_fetchdata")
    req_ids = [str(x) for x in (row.get("requirement_ids") or [])]
    assert req_ids == ["QF-032"], req_ids


def test_autopilot_migrate_includes_workbench_requirements(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _seed_requirement_docs(repo)
    ssot_path = _seed_ssot(repo, statuses=("implemented", "implemented"))
    r = _run_autopilot(repo, "--mode", "migrate", "--skip-gates", "--dry-run", "--disable-push")
    assert r.returncode == 0, r.stderr
    doc = yaml.safe_load(ssot_path.read_text(encoding="utf-8"))
    req_rows = [x for x in (doc.get("requirements_trace_v1") or []) if isinstance(x, dict)]
    wb_rows = [x for x in req_rows if str(x.get("req_id") or "").startswith("WB-")]
    assert wb_rows, req_rows
    assert all(str(x.get("owner_track") or "") == "impl_workbench" for x in wb_rows)


def test_autopilot_requirement_gap_generation_creates_workbench_goal(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _seed_requirement_docs(repo)
    ssot_path = _seed_ssot(
        repo,
        statuses=("implemented", "implemented"),
        requirements_trace=[
            {
                "req_id": "WV-001",
                "source_document": "Quant‑EAM Whole View Framework.md（v0.5‑draft）.md",
                "source_line": 1,
                "owner_track": "skeleton",
                "clause": "Whole View Requirement Root",
                "depends_on_req_ids": [],
                "status_now": "implemented",
                "mapped_goal_ids": ["G01"],
                "acceptance_verified": True,
                "capability_cluster_id": "",
            },
            {
                "req_id": "QF-001",
                "source_document": "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md",
                "source_line": 1,
                "owner_track": "impl_fetchdata",
                "clause": "QA Fetch Requirement Root",
                "depends_on_req_ids": ["WV-001"],
                "status_now": "implemented",
                "mapped_goal_ids": ["G02"],
                "acceptance_verified": True,
                "capability_cluster_id": "",
            },
            {
                "req_id": "WB-001",
                "source_document": "docs/00_overview/workbench_ui_productization_v1.md",
                "source_line": 1,
                "owner_track": "impl_workbench",
                "clause": "Workbench Requirement Root",
                "depends_on_req_ids": ["WV-001"],
                "status_now": "implemented",
                "mapped_goal_ids": [],
                "acceptance_verified": True,
                "capability_cluster_id": "",
            },
            {
                "req_id": "WB-900",
                "source_document": "docs/00_overview/workbench_ui_productization_v1.md",
                "source_line": 10,
                "owner_track": "impl_workbench",
                "clause": "Workbench requirement gap",
                "depends_on_req_ids": ["WV-001"],
                "status_now": "planned",
                "mapped_goal_ids": [],
                "acceptance_verified": False,
                "capability_cluster_id": "",
            },
        ],
    )
    r = _run_autopilot(repo, "--mode", "plan", "--skip-gates", "--dry-run", "--disable-push")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    generated = out.get("generated_goal_ids") or []
    assert len(generated) == 1, out

    doc = yaml.safe_load(ssot_path.read_text(encoding="utf-8"))
    goals = [x for x in (doc.get("goal_checklist") or []) if isinstance(x, dict)]
    row = next(x for x in goals if x.get("id") == generated[0])
    assert str(row.get("track") or "") == "impl_workbench"
    assert str(row.get("phase_doc_path") or "").startswith("docs/08_phases/10_impl_workbench/phase_workbench_g")
    assert "src/quant_eam/ui/**" in (row.get("allowed_paths") or [])
    assert "python3 -m pytest -q tests/test_ui_mvp.py" in (row.get("acceptance_commands") or [])


def test_autopilot_requirement_gap_generation_generates_one_impl_goal_per_track(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _seed_requirement_docs(repo)
    ssot_path = _seed_ssot(
        repo,
        statuses=("implemented", "implemented"),
        requirements_trace=[
            {
                "req_id": "WV-001",
                "source_document": "Quant‑EAM Whole View Framework.md（v0.5‑draft）.md",
                "source_line": 1,
                "owner_track": "skeleton",
                "clause": "Whole View Requirement Root",
                "depends_on_req_ids": [],
                "status_now": "implemented",
                "mapped_goal_ids": ["G01"],
                "acceptance_verified": True,
                "capability_cluster_id": "",
            },
            {
                "req_id": "QF-001",
                "source_document": "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md",
                "source_line": 1,
                "owner_track": "impl_fetchdata",
                "clause": "QA Fetch Requirement Root",
                "depends_on_req_ids": ["WV-001"],
                "status_now": "implemented",
                "mapped_goal_ids": ["G02"],
                "acceptance_verified": True,
                "capability_cluster_id": "",
            },
            {
                "req_id": "WB-001",
                "source_document": "docs/00_overview/workbench_ui_productization_v1.md",
                "source_line": 1,
                "owner_track": "impl_workbench",
                "clause": "Workbench Requirement Root",
                "depends_on_req_ids": ["WV-001"],
                "status_now": "implemented",
                "mapped_goal_ids": [],
                "acceptance_verified": True,
                "capability_cluster_id": "",
            },
            {
                "req_id": "QF-900",
                "source_document": "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md",
                "source_line": 50,
                "owner_track": "impl_fetchdata",
                "clause": "Fetch track requirement gap",
                "depends_on_req_ids": ["WV-001"],
                "status_now": "planned",
                "mapped_goal_ids": [],
                "acceptance_verified": False,
                "capability_cluster_id": "",
            },
            {
                "req_id": "WB-900",
                "source_document": "docs/00_overview/workbench_ui_productization_v1.md",
                "source_line": 50,
                "owner_track": "impl_workbench",
                "clause": "Workbench track requirement gap",
                "depends_on_req_ids": ["WV-001"],
                "status_now": "planned",
                "mapped_goal_ids": [],
                "acceptance_verified": False,
                "capability_cluster_id": "",
            },
        ],
    )
    r = _run_autopilot(repo, "--mode", "plan", "--skip-gates", "--dry-run", "--disable-push")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    generated = out.get("generated_goal_ids") or []
    assert len(generated) == 2, out

    doc = yaml.safe_load(ssot_path.read_text(encoding="utf-8"))
    goals = [x for x in (doc.get("goal_checklist") or []) if isinstance(x, dict)]
    generated_rows = [x for x in goals if x.get("id") in set(generated)]
    assert {str(x.get("track") or "") for x in generated_rows} == {"impl_fetchdata", "impl_workbench"}


def test_autopilot_done_no_generation_when_requirements_all_implemented(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _seed_requirement_docs(repo)
    _seed_ssot(repo, statuses=("implemented", "implemented"))
    r = _run_autopilot(repo, "--mode", "plan", "--skip-gates", "--dry-run", "--disable-push")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert (out.get("generated_goal_ids") or []) == []
    done_flags = out.get("done_flags") or {}
    assert all(bool(v) for v in done_flags.values()), out


def test_autopilot_plan_no_generation_when_blocked_goal_exists(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _seed_requirement_docs(repo)
    _seed_ssot(repo, statuses=("blocked", "implemented"))
    r = _run_autopilot(repo, "--mode", "plan", "--skip-gates", "--dry-run", "--disable-push")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert (out.get("generated_goal_ids") or []) == []
    assert (out.get("selected_goal_ids") or []) == []


def test_autopilot_plan_dedups_same_requirement_depends_track_signature(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _seed_requirement_docs(repo)
    ssot = {
        "schema_version": "skeleton_ssot_v1",
        "goal_checklist": [
            {
                "id": "G01",
                "title": "Skeleton requirement implementation",
                "status_now": "implemented",
                "track": "skeleton",
                "depends_on": [],
                "requirement_ids": ["WV-001"],
                "phase_doc_path": "docs/08_phases/00_skeleton/phase_skel_g01.md",
                "allowed_paths": ["docs/08_phases/00_skeleton/phase_skel_g01.md"],
                "acceptance_commands": ["python3 scripts/check_docs_tree.py"],
            },
            {
                "id": "G02",
                "title": "Impl requirement implementation",
                "status_now": "implemented",
                "track": "impl_fetchdata",
                "depends_on": ["G01"],
                "requirement_ids": ["QF-001"],
                "phase_doc_path": "docs/08_phases/10_impl_fetchdata/phase_fetch_g02.md",
                "allowed_paths": ["docs/08_phases/10_impl_fetchdata/phase_fetch_g02.md"],
                "acceptance_commands": ["python3 scripts/check_docs_tree.py"],
            },
            {
                "id": "G03",
                "title": "Impl requirement execution for QF-900",
                "status_now": "blocked",
                "track": "impl_fetchdata",
                "depends_on": ["G01"],
                "requirement_ids": ["QF-900"],
                "phase_doc_path": "docs/08_phases/10_impl_fetchdata/phase_fetch_g03.md",
                "allowed_paths": ["docs/08_phases/10_impl_fetchdata/phase_fetch_g03.md"],
                "acceptance_commands": ["python3 scripts/check_docs_tree.py"],
            },
        ],
        "requirements_trace_v1": [
            {
                "req_id": "WV-001",
                "source_document": "Quant‑EAM Whole View Framework.md（v0.5‑draft）.md",
                "source_line": 1,
                "owner_track": "skeleton",
                "clause": "Whole View Requirement Root",
                "depends_on_req_ids": [],
                "status_now": "implemented",
                "mapped_goal_ids": ["G01"],
                "acceptance_verified": True,
                "capability_cluster_id": "",
            },
            {
                "req_id": "QF-001",
                "source_document": "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md",
                "source_line": 1,
                "owner_track": "impl_fetchdata",
                "clause": "QA Fetch Requirement Root",
                "depends_on_req_ids": ["WV-001"],
                "status_now": "implemented",
                "mapped_goal_ids": ["G02"],
                "acceptance_verified": True,
                "capability_cluster_id": "",
            },
            {
                "req_id": "QF-900",
                "source_document": "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md",
                "source_line": 10,
                "owner_track": "impl_fetchdata",
                "clause": "Repeated requirement should not regenerate with same signature",
                "depends_on_req_ids": ["WV-001"],
                "status_now": "planned",
                "mapped_goal_ids": ["G03"],
                "acceptance_verified": False,
                "capability_cluster_id": "",
            },
        ],
        "whole_view_autopilot_v1": {
            "done_criteria": {"goal_checklist_all_implemented": True},
            "rolling_goal_policy": {
                "enabled": True,
                "trigger_when_no_planned_or_partial": True,
            },
        },
        "queue_empty_generation_protocol_v1": {
            "status_now": "active",
            "enabled": False,
            "trigger_when_goal_queue_empty": True,
            "allow_generate_after_done": False,
        },
    }
    ssot_path = repo / "docs/12_workflows/skeleton_ssot_v1.yaml"
    _write(ssot_path, yaml.safe_dump(ssot, sort_keys=False, allow_unicode=True))

    r = _run_autopilot(repo, "--mode", "plan", "--skip-gates", "--dry-run", "--disable-push")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert (out.get("generated_goal_ids") or []) == []


def test_autopilot_run_writes_milestone_artifacts_and_history(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _seed_requirement_docs(repo)
    ssot_path = _seed_ssot(repo, statuses=("implemented", "implemented"))
    r = _run_autopilot(repo, "--mode", "run", "--skip-gates", "--dry-run", "--disable-push")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    milestones = out.get("milestones") or []
    assert milestones, out

    doc = yaml.safe_load(ssot_path.read_text(encoding="utf-8"))
    history = doc.get("milestone_history_v1") or []
    assert history, doc
    row = history[-1]
    summary_path = repo / row["artifact_paths"]["milestone_summary"]
    manifest_path = repo / row["artifact_paths"]["commit_manifest"]
    assert summary_path.is_file()
    assert manifest_path.is_file()


def test_autopilot_run_skips_reprocessing_blocked_milestones_by_default(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _seed_requirement_docs(repo)
    ssot_path = _seed_ssot(repo, statuses=("implemented", "implemented"))

    # First migrate to populate capability_clusters_v1 in a stable shape.
    r1 = _run_autopilot(repo, "--mode", "migrate", "--skip-gates", "--dry-run", "--disable-push")
    assert r1.returncode == 0, r1.stderr
    doc = yaml.safe_load(ssot_path.read_text(encoding="utf-8"))
    clusters = [x for x in (doc.get("capability_clusters_v1") or []) if isinstance(x, dict)]
    assert clusters, doc
    # Mark all clusters as previously blocked in milestone history.
    doc["milestone_history_v1"] = [
        {
            "milestone_id": f"{str(c.get('cluster_id') or '').lower()}-seed",
            "cluster_id": str(c.get("cluster_id") or ""),
            "status_now": "blocked",
            "recorded_at": "2026-02-17T00:00:00Z",
            "latest_phase_id": "",
            "push_mode": "blocked_by_gate",
            "branch": "",
            "commit_sha": "",
            "artifact_paths": {},
            "notes": ["seeded blocked milestone"],
        }
        for c in clusters
    ]
    ssot_path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")

    r2 = _run_autopilot(repo, "--mode", "run", "--dry-run", "--disable-push")
    assert r2.returncode == 0, r2.stderr
    out = json.loads(r2.stdout)
    assert (out.get("milestones") or []) == [], out


def test_autopilot_plan_populates_goal_skill_and_reasoning_fields(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _seed_requirement_docs(repo)
    ssot_path = _seed_ssot(repo, statuses=("planned", "planned"))
    r = _run_autopilot(repo, "--mode", "plan", "--skip-gates", "--dry-run", "--disable-push")
    assert r.returncode == 0, r.stderr
    doc = yaml.safe_load(ssot_path.read_text(encoding="utf-8"))
    goals = [x for x in (doc.get("goal_checklist") or []) if isinstance(x, dict)]
    assert goals
    for row in goals:
        assert isinstance(row.get("required_skills"), list)
        assert row.get("required_skills")
        assert isinstance(row.get("difficulty_score"), int)
        assert 0 <= int(row.get("difficulty_score")) <= 100
        assert str(row.get("reasoning_tier") or "") in {"medium", "high", "super_high"}
