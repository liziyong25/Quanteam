from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "whole_view_autopilot.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("whole_view_autopilot", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _build_engine(module, repo: Path):
    ssot = repo / "docs/12_workflows/skeleton_ssot_v1.yaml"
    ssot.parent.mkdir(parents=True, exist_ok=True)
    ssot.write_text("schema_version: skeleton_ssot_v1\n", encoding="utf-8")
    return module.WholeViewAutopilot(
        ssot_path=ssot,
        packet_root=repo / "artifacts/subagent_control",
        milestone_root=repo / "artifacts/autopilot/milestones",
        max_parallel=2,
        dry_run=True,
        run_gates=False,
        enable_push=False,
        latest_phase_id=None,
        subagent_mode="acceptance_only",
        codex_model=None,
        codex_timeout_sec=60,
        codex_json_log=False,
        skill_enforcement_mode="warn",
        reasoning_tier_override=None,
        skill_registry_path=None,
        splitter_config_path=repo / "docs/12_workflows/requirement_splitter_profiles_v1.yaml",
    )


def _build_goal(module):
    return module.Goal(
        goal_id="G999",
        status_now="planned",
        track="skeleton",
        title="test",
        depends_on=[],
        requirement_ids=[],
        allowed_paths=["docs/**"],
        acceptance_commands=[],
        stop_scope={},
        phase_doc_path="docs/08_phases/00_skeleton/phase_skel_g999.md",
        capability_cluster_id="CL_TEST",
        required_skills=["requirement-splitter"],
        difficulty_score=10,
        reasoning_tier="medium",
        todo_checklist=[],
        risk_notes=[],
        parallel_hints=[],
        todo_planner={},
        allow_noop=False,
        raw={},
    )


def test_auto_waive_contract_stop_condition(tmp_path: Path) -> None:
    module = _load_module()
    engine = _build_engine(module, tmp_path / "repo")
    goal = _build_goal(module)
    doc = {
        "whole_view_autopilot_v1": {
            "autonomous_decision_policy_v1": {
                "status_now": "active",
                "stop_condition_override_decision": "controller_auto_with_audit",
                "auto_waivable_stop_conditions": ["Any change touching contracts/**"],
            }
        }
    }
    report = engine._evaluate_stop_conditions(
        doc=doc,
        changed_files=["contracts/fetch_request_schema_v1.json"],
        goals=[goal],
        context={"stage": "unit_test"},
    )
    assert report["pass"] is True
    assert report["violations"] == []
    assert any(x.get("condition") == "Any change touching contracts/**" for x in report.get("waivers", []))
    assert any(x.get("decision_type") == "auto_stop_condition_waiver" for x in report.get("decision_entries", []))


def test_block_when_no_auto_waiver_policy(tmp_path: Path) -> None:
    module = _load_module()
    engine = _build_engine(module, tmp_path / "repo")
    goal = _build_goal(module)
    doc = {
        "whole_view_autopilot_v1": {
            "autonomous_decision_policy_v1": {
                "status_now": "disabled",
                "stop_condition_override_decision": "controller_auto_with_audit",
                "auto_waivable_stop_conditions": ["Any change touching contracts/**"],
            }
        }
    }
    report = engine._evaluate_stop_conditions(
        doc=doc,
        changed_files=["contracts/fetch_request_schema_v1.json"],
        goals=[goal],
        context={"stage": "unit_test"},
    )
    assert report["pass"] is False
    assert any(x.get("condition") == "Any change touching contracts/**" for x in report.get("violations", []))
    assert any(x.get("decision_type") == "stop_condition_blocked" for x in report.get("decision_entries", []))


def test_extract_changed_files_decodes_git_quoted_unicode_paths() -> None:
    module = _load_module()
    status = (
        'A  "docs/00_overview/Quant\\342\\200\\221EAM Whole View Framework.md'
        '\\357\\274\\210v0.5\\342\\200\\221draft\\357\\274\\211.md"\n'
        "M  docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md\n"
    )
    changed = module.WholeViewAutopilot._extract_changed_files(status)
    assert "docs/00_overview/Quant‑EAM Whole View Framework.md（v0.5‑draft）.md" in changed
    assert "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md" in changed
