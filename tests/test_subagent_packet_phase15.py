from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml


REQUIRED_CHECKS = [
    "task_card_published",
    "executor_is_codex_cli",
    "codex_invoked",
    "changed_files_non_empty",
    "changed_files_within_allowed_paths",
    "allowed_paths_only",
    "acceptance_commands_executed",
    "ssot_updated",
]
SKILL_CHECKS = [
    "skills_declared",
    "skills_available",
    "skills_invoked",
    "reasoning_tier_applied",
]


def _checker_script() -> Path:
    return Path(__file__).resolve().parents[1] / "scripts" / "check_subagent_packet.py"


def _write_yaml(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")


def _base_packet_docs(
    *,
    phase_id: str,
    hardened: bool,
    external_noise_paths: list[str] | None = None,
) -> tuple[dict, dict, dict]:
    task: dict = {
        "schema_version": "subagent_task_card_v1",
        "phase_id": phase_id,
        "goal_ids": ["G15"],
        "published_at": "2026-02-11T12:00:00+08:00",
        "published_by": "orchestrator_codex",
        "executor_required": "codex_cli_subagent",
        "subagent": {"execution_mode": "codex_exec", "prompt_file": f"artifacts/subagent_control/{phase_id}/task_prompt.md"},
        "allowed_paths": [
            "src/**",
            "docs/**",
            f"artifacts/subagent_control/{phase_id}/**",
        ],
        "acceptance_commands": [
            "python3 -m pytest -q tests/test_subagent_packet_phase15.py",
            "python3 scripts/check_docs_tree.py",
        ],
    }
    if hardened:
        task["evidence_policy"] = "hardened"
        task["evidence_files"] = {
            "workspace_before": f"artifacts/subagent_control/{phase_id}/workspace_before.json",
            "workspace_after": f"artifacts/subagent_control/{phase_id}/workspace_after.json",
            "acceptance_log": f"artifacts/subagent_control/{phase_id}/acceptance_run_log.jsonl",
        }
    if external_noise_paths is not None:
        task["external_noise_paths"] = external_noise_paths

    exe = {
        "schema_version": "subagent_executor_report_v1",
        "phase_id": phase_id,
        "reported_at": "2026-02-11T12:01:00+08:00",
        "executor": {
            "role": "codex_cli_subagent",
            "runtime": "codex_cli",
        },
        "status": "completed",
        "changed_files": ["src/app.py"],
        "commands_run": [
            "codex exec --cd /tmp/repo --full-auto -",
            "python3 -m pytest -q tests/test_subagent_packet_phase15.py",
            "python3 scripts/check_docs_tree.py",
        ],
    }

    val = {
        "schema_version": "subagent_validator_report_v1",
        "phase_id": phase_id,
        "reported_at": "2026-02-11T12:02:00+08:00",
        "validator": {"role": "orchestrator_codex"},
        "status": "pass",
        "checks": [{"name": name, "pass": True, "detail": "ok"} for name in REQUIRED_CHECKS],
    }
    return task, exe, val


def _write_snapshots(
    packet_dir: Path,
    *,
    before_files: dict[str, str],
    after_files: dict[str, str],
) -> None:
    before = {
        "schema_version": "subagent_workspace_snapshot_v1",
        "captured_at": "2026-02-11T12:00:00+08:00",
        "files": before_files,
    }
    after = {
        "schema_version": "subagent_workspace_snapshot_v1",
        "captured_at": "2026-02-11T12:03:00+08:00",
        "files": after_files,
    }
    (packet_dir / "workspace_before.json").write_text(
        json.dumps(before, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (packet_dir / "workspace_after.json").write_text(
        json.dumps(after, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_acceptance_log(packet_dir: Path, rows: list[dict]) -> None:
    lines = [json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows]
    (packet_dir / "acceptance_run_log.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run_checker(repo_root: Path, phase_id: str) -> subprocess.CompletedProcess[str]:
    cmd = [
        sys.executable,
        str(_checker_script()),
        "--phase-id",
        phase_id,
        "--packet-root",
        "artifacts/subagent_control",
    ]
    return subprocess.run(cmd, cwd=repo_root, text=True, capture_output=True, check=False)


def _mk_repo(
    tmp_path: Path,
    *,
    phase_id: str,
    hardened: bool,
    external_noise_paths: list[str] | None = None,
) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    packet = repo / "artifacts" / "subagent_control" / phase_id
    packet.mkdir(parents=True)
    task, exe, val = _base_packet_docs(
        phase_id=phase_id,
        hardened=hardened,
        external_noise_paths=external_noise_paths,
    )
    _write_yaml(packet / "task_card.yaml", task)
    _write_yaml(packet / "executor_report.yaml", exe)
    _write_yaml(packet / "validator_report.yaml", val)
    return repo, packet


def test_phase15_legacy_packet_still_passes(tmp_path: Path) -> None:
    phase_id = "phase_34"
    repo, _packet = _mk_repo(tmp_path, phase_id=phase_id, hardened=False)
    r = _run_checker(repo, phase_id)
    assert r.returncode == 0, r.stderr
    assert "subagent packet: OK" in r.stdout


def test_phase15_hardened_missing_evidence_fails(tmp_path: Path) -> None:
    phase_id = "phase_34"
    repo, _packet = _mk_repo(tmp_path, phase_id=phase_id, hardened=True)
    r = _run_checker(repo, phase_id)
    assert r.returncode != 0
    assert "missing hardened evidence file" in r.stderr


def test_phase15_hardened_changed_files_mismatch_fails(tmp_path: Path) -> None:
    phase_id = "phase_34"
    repo, packet = _mk_repo(tmp_path, phase_id=phase_id, hardened=True)
    _write_snapshots(
        packet,
        before_files={"src/app.py": "1" * 64, "src/removed.py": "2" * 64},
        after_files={"src/app.py": "3" * 64},
    )
    _write_acceptance_log(
        packet,
        rows=[
            {
                "command": "python3 -m pytest -q tests/test_subagent_packet_phase15.py",
                "exit_code": 0,
                "started_at": "2026-02-11T12:03:01+08:00",
                "ended_at": "2026-02-11T12:03:02+08:00",
            },
            {
                "command": "python3 scripts/check_docs_tree.py",
                "exit_code": 0,
                "started_at": "2026-02-11T12:03:03+08:00",
                "ended_at": "2026-02-11T12:03:04+08:00",
            },
        ],
    )

    r = _run_checker(repo, phase_id)
    assert r.returncode != 0
    assert "hardened changed_files mismatch" in r.stderr


def test_phase15_hardened_acceptance_not_successful_fails(tmp_path: Path) -> None:
    phase_id = "phase_34"
    repo, packet = _mk_repo(tmp_path, phase_id=phase_id, hardened=True)
    _write_snapshots(
        packet,
        before_files={"src/app.py": "1" * 64},
        after_files={"src/app.py": "2" * 64},
    )
    _write_acceptance_log(
        packet,
        rows=[
            {
                "command": "python3 -m pytest -q tests/test_subagent_packet_phase15.py",
                "exit_code": 1,
                "started_at": "2026-02-11T12:03:01+08:00",
                "ended_at": "2026-02-11T12:03:02+08:00",
            },
            {
                "command": "python3 scripts/check_docs_tree.py",
                "exit_code": 0,
                "started_at": "2026-02-11T12:03:03+08:00",
                "ended_at": "2026-02-11T12:03:04+08:00",
            },
        ],
    )

    r = _run_checker(repo, phase_id)
    assert r.returncode != 0
    assert "required acceptance command missing successful log entry" in r.stderr


def test_phase15_hardened_full_evidence_passes(tmp_path: Path) -> None:
    phase_id = "phase_34"
    repo, packet = _mk_repo(tmp_path, phase_id=phase_id, hardened=True)
    _write_snapshots(
        packet,
        before_files={"src/app.py": "1" * 64},
        after_files={"src/app.py": "4" * 64},
    )
    _write_acceptance_log(
        packet,
        rows=[
            {
                "command": "python3 -m pytest -q tests/test_subagent_packet_phase15.py",
                "exit_code": 0,
                "started_at": "2026-02-11T12:03:01+08:00",
                "ended_at": "2026-02-11T12:03:02+08:00",
                "stdout_tail": "ok",
            },
            {
                "command": "python3 scripts/check_docs_tree.py",
                "exit_code": 0,
                "started_at": "2026-02-11T12:03:03+08:00",
                "ended_at": "2026-02-11T12:03:04+08:00",
            },
        ],
    )

    r = _run_checker(repo, phase_id)
    assert r.returncode == 0, r.stderr
    assert "subagent packet: OK" in r.stdout


def test_phase15_hardened_external_noise_paths_ignored(tmp_path: Path) -> None:
    phase_id = "phase_34"
    repo, packet = _mk_repo(
        tmp_path,
        phase_id=phase_id,
        hardened=True,
        external_noise_paths=["external_data/**"],
    )
    _write_snapshots(
        packet,
        before_files={"src/app.py": "1" * 64, "external_data/noise.txt": "2" * 64},
        after_files={"src/app.py": "4" * 64, "external_data/noise.txt": "3" * 64},
    )
    _write_acceptance_log(
        packet,
        rows=[
            {
                "command": "python3 -m pytest -q tests/test_subagent_packet_phase15.py",
                "exit_code": 0,
                "started_at": "2026-02-11T12:03:01+08:00",
                "ended_at": "2026-02-11T12:03:02+08:00",
            },
            {
                "command": "python3 scripts/check_docs_tree.py",
                "exit_code": 0,
                "started_at": "2026-02-11T12:03:03+08:00",
                "ended_at": "2026-02-11T12:03:04+08:00",
            },
        ],
    )
    r = _run_checker(repo, phase_id)
    assert r.returncode == 0, r.stderr
    assert "subagent packet: OK" in r.stdout


def test_phase15_hardened_git_quoted_unicode_changed_file_passes(tmp_path: Path) -> None:
    phase_id = "phase_34"
    repo, packet = _mk_repo(tmp_path, phase_id=phase_id, hardened=True)
    exe = yaml.safe_load((packet / "executor_report.yaml").read_text(encoding="utf-8"))
    assert isinstance(exe, dict)
    exe["changed_files"] = [
        '"docs/00_overview/Quant\\342\\200\\221EAM Whole View Framework.md\\357\\274\\210v0.5\\342\\200\\221draft\\357\\274\\211.md"'
    ]
    _write_yaml(packet / "executor_report.yaml", exe)
    changed_path = "docs/00_overview/Quant‑EAM Whole View Framework.md（v0.5‑draft）.md"
    _write_snapshots(
        packet,
        before_files={changed_path: "1" * 64},
        after_files={changed_path: "2" * 64},
    )
    _write_acceptance_log(
        packet,
        rows=[
            {
                "command": "python3 -m pytest -q tests/test_subagent_packet_phase15.py",
                "exit_code": 0,
                "started_at": "2026-02-11T12:03:01+08:00",
                "ended_at": "2026-02-11T12:03:02+08:00",
            },
            {
                "command": "python3 scripts/check_docs_tree.py",
                "exit_code": 0,
                "started_at": "2026-02-11T12:03:03+08:00",
                "ended_at": "2026-02-11T12:03:04+08:00",
            },
        ],
    )
    r = _run_checker(repo, phase_id)
    assert r.returncode == 0, r.stderr
    assert "subagent packet: OK" in r.stdout


def test_phase15_validator_milestone_eval_optional_passes(tmp_path: Path) -> None:
    phase_id = "phase_34"
    repo, packet = _mk_repo(tmp_path, phase_id=phase_id, hardened=False)
    val = yaml.safe_load((packet / "validator_report.yaml").read_text(encoding="utf-8"))
    assert isinstance(val, dict)
    val["milestone_eval"] = {
        "milestone_id": "cl_fetch_081-20260213095103",
        "cluster_id": "CL_FETCH_081",
        "gate_ok": True,
        "push_mode": "direct_master",
        "recorded_at": "2026-02-13T09:51:03Z",
    }
    _write_yaml(packet / "validator_report.yaml", val)
    r = _run_checker(repo, phase_id)
    assert r.returncode == 0, r.stderr
    assert "subagent packet: OK" in r.stdout


def test_phase15_validator_milestone_eval_invalid_fails(tmp_path: Path) -> None:
    phase_id = "phase_34"
    repo, packet = _mk_repo(tmp_path, phase_id=phase_id, hardened=False)
    val = yaml.safe_load((packet / "validator_report.yaml").read_text(encoding="utf-8"))
    assert isinstance(val, dict)
    val["milestone_eval"] = "invalid"
    _write_yaml(packet / "validator_report.yaml", val)
    r = _run_checker(repo, phase_id)
    assert r.returncode != 0
    assert "milestone_eval" in r.stderr


def test_phase15_acceptance_only_mode_allows_no_codex_and_noop(tmp_path: Path) -> None:
    phase_id = "phase_34"
    repo, packet = _mk_repo(tmp_path, phase_id=phase_id, hardened=False)
    task = yaml.safe_load((packet / "task_card.yaml").read_text(encoding="utf-8"))
    exe = yaml.safe_load((packet / "executor_report.yaml").read_text(encoding="utf-8"))
    val = yaml.safe_load((packet / "validator_report.yaml").read_text(encoding="utf-8"))
    assert isinstance(task, dict)
    assert isinstance(exe, dict)
    assert isinstance(val, dict)
    task["subagent"]["execution_mode"] = "acceptance_only"
    task["allow_noop"] = True
    exe["changed_files"] = []
    exe["commands_run"] = [
        "python3 -m pytest -q tests/test_subagent_packet_phase15.py",
        "python3 scripts/check_docs_tree.py",
    ]
    _write_yaml(packet / "task_card.yaml", task)
    _write_yaml(packet / "executor_report.yaml", exe)
    _write_yaml(packet / "validator_report.yaml", val)
    r = _run_checker(repo, phase_id)
    assert r.returncode == 0, r.stderr
    assert "subagent packet: OK" in r.stdout


def test_phase15_skill_warn_mode_allows_missing_skill_invocation(tmp_path: Path) -> None:
    phase_id = "phase_34"
    repo, packet = _mk_repo(tmp_path, phase_id=phase_id, hardened=False)
    task = yaml.safe_load((packet / "task_card.yaml").read_text(encoding="utf-8"))
    exe = yaml.safe_load((packet / "executor_report.yaml").read_text(encoding="utf-8"))
    val = yaml.safe_load((packet / "validator_report.yaml").read_text(encoding="utf-8"))
    assert isinstance(task, dict)
    assert isinstance(exe, dict)
    assert isinstance(val, dict)
    task["required_skills"] = ["ssot-goal-planner"]
    task["skill_enforcement_mode"] = "warn"
    task["skill_registry_snapshot"] = {"ssot-goal-planner": "skills/ssot-goal-planner"}
    task["reasoning_tier"] = "high"
    task["reasoning_profile"] = {"model": "", "timeout_sec": 3600, "retry": 2}
    exe["skills_required"] = ["ssot-goal-planner"]
    exe["skills_used"] = []
    exe["skill_usage_evidence"] = []
    exe["reasoning_tier"] = "high"
    exe["reasoning_runtime"] = {"model": "", "timeout_sec": 3600, "retry": 2, "attempt": 1}
    val["checks"].extend([{"name": x, "pass": False, "detail": "warn"} for x in SKILL_CHECKS])
    _write_yaml(packet / "task_card.yaml", task)
    _write_yaml(packet / "executor_report.yaml", exe)
    _write_yaml(packet / "validator_report.yaml", val)
    r = _run_checker(repo, phase_id)
    assert r.returncode == 0, r.stderr
    assert "WARN:" in r.stderr


def test_phase15_skill_enforce_mode_blocks_missing_skill_invocation(tmp_path: Path) -> None:
    phase_id = "phase_34"
    repo, packet = _mk_repo(tmp_path, phase_id=phase_id, hardened=False)
    task = yaml.safe_load((packet / "task_card.yaml").read_text(encoding="utf-8"))
    exe = yaml.safe_load((packet / "executor_report.yaml").read_text(encoding="utf-8"))
    val = yaml.safe_load((packet / "validator_report.yaml").read_text(encoding="utf-8"))
    assert isinstance(task, dict)
    assert isinstance(exe, dict)
    assert isinstance(val, dict)
    task["required_skills"] = ["ssot-goal-planner"]
    task["skill_enforcement_mode"] = "enforce"
    task["skill_registry_snapshot"] = {"ssot-goal-planner": "skills/ssot-goal-planner"}
    task["reasoning_tier"] = "high"
    task["reasoning_profile"] = {"model": "", "timeout_sec": 3600, "retry": 2}
    exe["skills_required"] = ["ssot-goal-planner"]
    exe["skills_used"] = []
    exe["skill_usage_evidence"] = []
    exe["reasoning_tier"] = "medium"
    exe["reasoning_runtime"] = {"model": "", "timeout_sec": 1800, "retry": 2, "attempt": 1}
    val["checks"].extend([{"name": x, "pass": False, "detail": "missing"} for x in SKILL_CHECKS])
    _write_yaml(packet / "task_card.yaml", task)
    _write_yaml(packet / "executor_report.yaml", exe)
    _write_yaml(packet / "validator_report.yaml", val)
    r = _run_checker(repo, phase_id)
    assert r.returncode != 0
    assert "skills_used missing required skills" in r.stderr or "reasoning_tier" in r.stderr
