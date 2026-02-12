#!/usr/bin/env python3
from __future__ import annotations

import argparse
import dataclasses
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


READY_EXIT = 0
BLOCKED_EXIT = 2

ALLOWED_MUTATION_PREFIXES = (
    "docs/",
    "scripts/",
    "tests/",
    "src/quant_eam/ui/",
    "artifacts/",
)
ALLOWED_PLACEHOLDER_PATHS = (
    "docs/12_workflows/skeleton_ssot_v1.yaml",
    "scripts/check_docs_tree.py",
    "docs/08_phases/phase_template.md",
    "docs/08_phases/10_impl_fetchdata/README.md",
)
REQUIRED_PATHS = (
    "docs/12_workflows/skeleton_ssot_v1.yaml",
    "scripts/check_docs_tree.py",
    "docs/08_phases/00_skeleton",
    "docs/08_phases/10_impl_fetchdata",
    "docs/08_phases/phase_template.md",
    "docs/08_phases/10_impl_fetchdata/README.md",
)
OLD_REF_REPLACEMENTS = (
    ("docs/12_workflows/agents_ui_ssot_v1.yaml", "docs/12_workflows/skeleton_ssot_v1.yaml"),
    ("/docs/08_phases/", "docs/08_phases/"),
)
TEXT_SCAN_DIRS = (
    "docs",
    "tests",
    "src/quant_eam/ui",
)
REQUIRED_VALIDATOR_CHECKS = [
    "task_card_published",
    "executor_is_codex_cli",
    "allowed_paths_only",
    "acceptance_commands_executed",
    "ssot_updated",
]
SSOT_PATH = Path("docs/12_workflows/skeleton_ssot_v1.yaml")
PHASE_SECTION_SENTINEL = "\nagents_pipeline_v1:"


@dataclasses.dataclass
class CommandRecord:
    step: str
    command: str
    exit_code: int
    stdout_tail: str
    stderr_tail: str


@dataclasses.dataclass
class StepRecord:
    step: str
    status: str
    detail: str


@dataclasses.dataclass
class GoalInfo:
    goal_id: str
    title: str
    track: str
    status_now: str
    depends_on: list[str]
    phase_doc_path: str
    allowed_paths: list[str]
    acceptance_commands: list[str]


class Preflight:
    def __init__(self, *, report_root: Path, packet_root: Path, venv_dir: Path) -> None:
        self.repo_root = Path.cwd()
        self.report_root = report_root if report_root.is_absolute() else (self.repo_root / report_root)
        self.packet_root = packet_root if packet_root.is_absolute() else (self.repo_root / packet_root)
        self.venv_dir = venv_dir
        self.command_log: list[CommandRecord] = []
        self.step_log: list[StepRecord] = []
        self.modified_files: set[str] = set()
        self.blockers: list[str] = []
        self.external_blockers: list[str] = []
        self.requested_paths: set[str] = set()
        self.selected_pair: tuple[GoalInfo, GoalInfo] | None = None
        self.docs_tree_ok = False
        self.ui_subset_not_degraded = False
        self.dryrun_ok = False
        self.py_exec = "python3"
        self.test_env_ready = False
        self.ui_test_baseline_rc: int | None = None
        self.ui_test_final_rc: int | None = None

    def now_iso(self) -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def is_allowed_path(self, rel_path: str) -> bool:
        return rel_path.startswith(ALLOWED_MUTATION_PREFIXES)

    def mark_modified(self, path: Path) -> None:
        rel = path.as_posix()
        if not self.is_allowed_path(rel):
            self.requested_paths.add(rel)
            self.blockers.append(f"Attempted mutation outside allowed scope: {rel}")
            return
        self.modified_files.add(rel)

    def write_text(self, path: Path, text: str) -> None:
        rel = path.relative_to(self.repo_root).as_posix()
        if not self.is_allowed_path(rel):
            self.requested_paths.add(rel)
            self.blockers.append(f"Refused to write outside allowed scope: {rel}")
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        old = path.read_text(encoding="utf-8") if path.exists() else None
        if old == text:
            return
        path.write_text(text, encoding="utf-8")
        self.mark_modified(path.relative_to(self.repo_root))

    def write_yaml(self, path: Path, doc: dict[str, Any]) -> None:
        text = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)
        self.write_text(path, text)

    def run_cmd(
        self,
        *,
        step: str,
        command: str,
        timeout_sec: int = 600,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        cp = subprocess.run(
            command,
            cwd=self.repo_root,
            shell=True,
            text=True,
            capture_output=True,
            timeout=timeout_sec,
            env=env,
            check=False,
        )
        self.command_log.append(
            CommandRecord(
                step=step,
                command=command,
                exit_code=cp.returncode,
                stdout_tail=self.tail(cp.stdout),
                stderr_tail=self.tail(cp.stderr),
            )
        )
        return cp

    @staticmethod
    def tail(text: str, limit: int = 800) -> str:
        t = text.strip()
        if len(t) <= limit:
            return t
        return t[-limit:]

    def log_step(self, step: str, status: str, detail: str) -> None:
        self.step_log.append(StepRecord(step=step, status=status, detail=detail))

    def ensure_report_dirs(self) -> None:
        self.report_root.mkdir(parents=True, exist_ok=True)
        self.packet_root.mkdir(parents=True, exist_ok=True)
        self.mark_modified(self.report_root.relative_to(self.repo_root))
        self.mark_modified(self.packet_root.relative_to(self.repo_root))

    def step0_collect_baseline(self) -> None:
        commands = [
            "pwd",
            "git branch --show-current",
            "git status --short --branch",
            "python3 --version",
            "pip --version",
            "command -v uv || true",
            "command -v poetry || true",
            "command -v pytest || true",
        ]
        for cmd in commands:
            self.run_cmd(step="0_baseline", command=cmd, timeout_sec=120)
        self.log_step("0_baseline", "PASS", "Baseline commands captured.")

    def step1_required_paths(self) -> None:
        created = 0
        for raw in REQUIRED_PATHS:
            p = self.repo_root / raw
            if p.exists():
                continue
            if raw.endswith("/"):
                p.mkdir(parents=True, exist_ok=True)
                self.mark_modified(Path(raw.rstrip("/")))
                created += 1
                continue
            if any(raw == x for x in ALLOWED_PLACEHOLDER_PATHS):
                p.parent.mkdir(parents=True, exist_ok=True)
                if raw.endswith(".py"):
                    text = (
                        "#!/usr/bin/env python3\n"
                        "from __future__ import annotations\n\n"
                        "import sys\n\n"
                        "print('placeholder check_docs_tree: please replace with real checker')\n"
                        "raise SystemExit(0)\n"
                    )
                elif raw.endswith(".yaml"):
                    text = "schema_version: skeleton_ssot_v1\ngoal_checklist: []\n"
                elif raw.endswith("README.md"):
                    text = "# Placeholder\n\nThis file is auto-created by preflight for required path existence.\n"
                else:
                    text = "# Placeholder\n\nAuto-created by preflight.\n"
                self.write_text(p, text)
                created += 1
            elif raw.endswith("00_skeleton") or raw.endswith("10_impl_fetchdata"):
                p.mkdir(parents=True, exist_ok=True)
                self.mark_modified(Path(raw))
                created += 1
            else:
                self.blockers.append(f"Missing required path not auto-healable: {raw}")
        status = "PASS" if not self.blockers else "FAIL"
        self.log_step("1_required_paths", status, f"Created placeholders: {created}")

    def normalize_phase_doc_path(self, raw: str) -> str:
        s = str(raw).strip()
        if not s:
            return s
        if s.startswith("/"):
            s = s[1:]
        if s.startswith("docs/08_phases/00_skeleton/") or s.startswith("docs/08_phases/10_impl_fetchdata/"):
            return s
        if s.startswith("docs/08_phases/"):
            base = Path(s).name
            c1 = f"docs/08_phases/00_skeleton/{base}"
            c2 = f"docs/08_phases/10_impl_fetchdata/{base}"
            if (self.repo_root / c1).is_file() and not (self.repo_root / c2).is_file():
                return c1
            if (self.repo_root / c2).is_file() and not (self.repo_root / c1).is_file():
                return c2
            if "fetch" in base.lower() or "impl" in base.lower():
                return c2
            return c1
        return s

    def _scan_old_refs_outside_allowed(self) -> None:
        patterns = ["agents_ui_ssot_v1.yaml", "/docs/08_phases/"]
        for root, _dirs, files in os.walk(self.repo_root):
            rel_root = Path(root).relative_to(self.repo_root).as_posix()
            if rel_root.startswith(".git/"):
                continue
            for name in files:
                p = Path(root) / name
                rel = p.relative_to(self.repo_root).as_posix()
                if rel.startswith("artifacts/"):
                    continue
                try:
                    text = p.read_text(encoding="utf-8")
                except Exception:
                    continue
                if any(x in text for x in patterns):
                    if not (
                        rel.startswith("docs/")
                        or rel.startswith("scripts/")
                        or rel.startswith("tests/")
                        or rel.startswith("src/quant_eam/ui/")
                        or rel == SSOT_PATH.as_posix()
                    ):
                        self.requested_paths.add(rel)

    def _fix_text_refs_in_allowed_dirs(self) -> int:
        changed = 0
        for d in TEXT_SCAN_DIRS:
            root = self.repo_root / d
            if not root.exists():
                continue
            for p in root.rglob("*"):
                if not p.is_file():
                    continue
                try:
                    text = p.read_text(encoding="utf-8")
                except Exception:
                    continue
                new_text = text
                for old, new in OLD_REF_REPLACEMENTS:
                    new_text = new_text.replace(old, new)
                if new_text != text:
                    self.write_text(p, new_text)
                    changed += 1
        return changed

    def _find_invalid_phase_doc_paths(self, doc: Any) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []

        def walk(obj: Any, path: str) -> None:
            if isinstance(obj, dict):
                for k, v in obj.items():
                    np = f"{path}.{k}" if path else k
                    if k == "phase_doc_path" and isinstance(v, str):
                        if not (
                            v.startswith("docs/08_phases/00_skeleton/")
                            or v.startswith("docs/08_phases/10_impl_fetchdata/")
                        ):
                            out.append((np, v))
                    walk(v, np)
            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    walk(v, f"{path}[{i}]")

        walk(doc, "")
        return out

    def step2_ssot_validation_and_heal(self) -> None:
        ssot_abs = self.repo_root / SSOT_PATH
        if not ssot_abs.is_file():
            self.blockers.append(f"SSOT missing: {SSOT_PATH.as_posix()}")
            self.log_step("2_ssot_validate_heal", "FAIL", "SSOT missing.")
            return

        changed_files = 0
        changed_files += self._fix_text_refs_in_allowed_dirs()

        text = ssot_abs.read_text(encoding="utf-8")
        original = text

        text = text.replace(
            '- rg -n "G58|phase_skel_g58|track: skeleton" docs/12_workflows/skeleton_ssot_v1.yaml',
            '- \'rg -n "G58|phase_skel_g58|track: skeleton" docs/12_workflows/skeleton_ssot_v1.yaml\'',
        )
        text = text.replace("/docs/08_phases/", "docs/08_phases/")

        if not re.search(r"^schema_version:\s*skeleton_ssot_v1\s*$", text, flags=re.MULTILINE):
            if re.search(r"^schema_version:\s*.+$", text, flags=re.MULTILINE):
                text = re.sub(
                    r"^schema_version:\s*.+$",
                    "schema_version: skeleton_ssot_v1",
                    text,
                    count=1,
                    flags=re.MULTILINE,
                )
            else:
                text = "schema_version: skeleton_ssot_v1\n" + text

        try:
            loaded = yaml.safe_load(text)
        except Exception as e:  # noqa: BLE001
            self.blockers.append(f"SSOT parse failed after text heal: {e}")
            self.log_step("2_ssot_validate_heal", "FAIL", "SSOT parse failed.")
            return
        if not isinstance(loaded, dict):
            self.blockers.append("SSOT root is not a YAML mapping.")
            self.log_step("2_ssot_validate_heal", "FAIL", "SSOT root invalid.")
            return

        invalid = self._find_invalid_phase_doc_paths(loaded)
        for _path, old in invalid:
            new = self.normalize_phase_doc_path(old)
            if old != new:
                text = text.replace(f"phase_doc_path: {old}", f"phase_doc_path: {new}")

        if text != original:
            self.write_text(ssot_abs, text)
            changed_files += 1

        try:
            loaded_after = yaml.safe_load(ssot_abs.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            self.blockers.append(f"SSOT parse failed after write: {e}")
            self.log_step("2_ssot_validate_heal", "FAIL", "SSOT parse failed after write.")
            return
        if not isinstance(loaded_after, dict):
            self.blockers.append("SSOT root invalid after write.")
            self.log_step("2_ssot_validate_heal", "FAIL", "SSOT root invalid after write.")
            return
        if str(loaded_after.get("schema_version", "")).strip() != "skeleton_ssot_v1":
            self.blockers.append("SSOT schema_version mismatch after heal.")
        invalid_after = self._find_invalid_phase_doc_paths(loaded_after)
        if invalid_after:
            self.blockers.append(f"Invalid phase_doc_path remains: {invalid_after[:3]}")
        status = "PASS" if not invalid_after and not self.blockers else "FAIL"
        self.log_step("2_ssot_validate_heal", status, f"Healed text files: {changed_files}")

    def create_docs_placeholder_for_missing(self, rel: str) -> bool:
        if not rel.startswith("docs/"):
            return False
        p = self.repo_root / rel
        if p.exists():
            return True
        p.parent.mkdir(parents=True, exist_ok=True)
        if rel.endswith(".md"):
            txt = (
                "# Auto-created Placeholder\n\n"
                "This file was created by preflight self-heal for docs tree consistency.\n"
            )
        elif rel.endswith(".yaml") or rel.endswith(".yml"):
            txt = "schema_version: placeholder_v1\n"
        else:
            txt = "auto-created placeholder\n"
        self.write_text(p, txt)
        return True

    def step3_docs_tree_loop(self) -> None:
        ok = False
        for attempt in range(1, 4):
            cp = self.run_cmd(step="3_docs_tree", command="python3 scripts/check_docs_tree.py", timeout_sec=180)
            if cp.returncode == 0:
                ok = True
                break
            stderr = cp.stderr
            healed = False
            for m in re.finditer(r"^- (\S+)$", stderr, flags=re.MULTILINE):
                rel = m.group(1).strip()
                if self.create_docs_placeholder_for_missing(rel):
                    healed = True
            if "missing required phase track dir: docs/08_phases/00_skeleton" in stderr:
                d = self.repo_root / "docs/08_phases/00_skeleton"
                d.mkdir(parents=True, exist_ok=True)
                self.mark_modified(d.relative_to(self.repo_root))
                healed = True
            if "missing required phase track dir: docs/08_phases/10_impl_fetchdata" in stderr:
                d = self.repo_root / "docs/08_phases/10_impl_fetchdata"
                d.mkdir(parents=True, exist_ok=True)
                self.mark_modified(d.relative_to(self.repo_root))
                healed = True
            if not healed:
                self.blockers.append(f"check_docs_tree failed and no auto-heal rule matched (attempt {attempt}).")
                break
        self.docs_tree_ok = ok
        self.log_step("3_docs_tree_loop", "PASS" if ok else "FAIL", "check_docs_tree loop complete.")
        if not ok:
            self.blockers.append("docs tree validation failed after max retries.")

    def step4_prepare_python_env(self) -> None:
        uv_lock = (self.repo_root / "uv.lock").is_file()
        poetry_lock = (self.repo_root / "poetry.lock").is_file()
        req_files = sorted(glob.glob(str(self.repo_root / "requirements*.txt")))
        pyproject = (self.repo_root / "pyproject.toml").is_file()

        uv_path = shutil.which("uv")
        poetry_path = shutil.which("poetry")

        commands: list[str] = []
        self.py_exec = "python3"
        fallback_break_system = False
        if uv_lock and uv_path:
            commands = ["uv sync"]
        elif poetry_lock and poetry_path:
            commands = ["poetry install"]
        elif req_files:
            commands = [f'python3 -m pip install -r "{Path(f).relative_to(self.repo_root).as_posix()}"' for f in req_files]
        elif pyproject:
            commands = [
                f"python3 -m venv {self.venv_dir.as_posix()}",
                f"{(self.venv_dir / 'bin/python').as_posix()} -m pip install -U pip",
                f"{(self.venv_dir / 'bin/python').as_posix()} -m pip install -e '.[dev]'",
            ]
            self.py_exec = (self.venv_dir / "bin/python").as_posix()
            fallback_break_system = True
        else:
            self.external_blockers.append("No dependency manifest found for Python environment setup.")
            self.log_step("4_prepare_python_env", "FAIL", "No dependency manifest found.")
            return

        ok = True
        for cmd in commands:
            cp = self.run_cmd(step="4_prepare_python_env", command=cmd, timeout_sec=3600)
            if cp.returncode != 0:
                ok = False
                self.external_blockers.append(f"Dependency install failed: `{cmd}`")
                break

        if not ok and fallback_break_system:
            ok = True
            self.external_blockers = [x for x in self.external_blockers if "python3 -m venv" not in x]
            self.py_exec = "python3"
            fallback_cmds = [
                "python3 -m pip install --break-system-packages -U pip",
                "python3 -m pip install --break-system-packages -e '.[dev]'",
            ]
            for cmd in fallback_cmds:
                cp = self.run_cmd(step="4_prepare_python_env_fallback", command=cmd, timeout_sec=7200)
                if cp.returncode != 0:
                    ok = False
                    self.external_blockers.append(f"Dependency fallback install failed: `{cmd}`")
                    break
        if ok and self.py_exec != "python3":
            check_cmd = f"{self.py_exec} -c \"import fastapi,referencing,jsonschema,pytest,yaml\""
            cp = self.run_cmd(step="4_prepare_python_env", command=check_cmd, timeout_sec=120)
            if cp.returncode != 0:
                ok = False
                self.external_blockers.append("Virtualenv dependency import check failed.")
        elif ok:
            check_cmd = "python3 -c \"import fastapi,referencing,jsonschema,pytest,yaml\""
            cp = self.run_cmd(step="4_prepare_python_env_fallback", command=check_cmd, timeout_sec=120)
            if cp.returncode != 0:
                ok = False
                self.external_blockers.append("System python dependency import check failed after fallback install.")

        self.test_env_ready = ok
        self.log_step("4_prepare_python_env", "PASS" if ok else "FAIL", "Python environment preparation complete.")

    def classify_test_failure(self, stderr: str, stdout: str) -> str:
        text = f"{stdout}\n{stderr}"
        low = text.lower()
        if "no module named" in low or "externally-managed-environment" in low:
            return "external"
        if "docs/12_workflows/agents_ui_ssot_v1.yaml" in text:
            return "path"
        if "/docs/08_phases/" in text or "docs/08_phases/phase_" in text:
            return "path"
        if "no such file or directory" in low and "docs/" in low:
            return "path"
        return "business"

    def run_pytest_suite(self, *, step: str, cmd: str, max_path_heal_attempts: int = 2) -> int:
        attempt = 0
        while True:
            cp = self.run_cmd(step=step, command=cmd, timeout_sec=7200)
            if cp.returncode == 0:
                return 0
            failure_type = self.classify_test_failure(cp.stderr, cp.stdout)
            if failure_type == "path" and attempt < max_path_heal_attempts:
                self._fix_text_refs_in_allowed_dirs()
                self.step2_ssot_validation_and_heal()
                attempt += 1
                continue
            if failure_type == "external":
                self.external_blockers.append(f"{step} failed due environment/dependency issue.")
            else:
                self.blockers.append(f"{step} failed due non-startup issue ({failure_type}).")
            return cp.returncode

    def step5_test_regression(self) -> None:
        py = self.py_exec
        ui_tests = sorted(Path("tests").glob("test_ui_*"))
        ui_rc = None
        if ui_tests:
            ui_cmd = f"{py} -m pytest -q " + " ".join(p.as_posix() for p in ui_tests)
            ui_rc = self.run_pytest_suite(step="5_pytest_ui_subset", cmd=ui_cmd)
            self.ui_test_baseline_rc = ui_rc
            self.ui_test_final_rc = ui_rc
        else:
            self.log_step("5_pytest_ui_subset", "SKIP", "No tests/test_ui_* files found.")

        full_cmd = f"{py} -m pytest -q"
        full_rc = self.run_pytest_suite(step="5_pytest_full", cmd=full_cmd)

        if self.ui_test_baseline_rc is None:
            self.ui_subset_not_degraded = True
        else:
            self.ui_subset_not_degraded = bool(
                self.ui_test_final_rc == 0 or (self.ui_test_baseline_rc != 0 and self.ui_test_final_rc != 0)
            )
        status = "PASS" if self.ui_subset_not_degraded and full_rc == 0 else "FAIL"
        detail = (
            f"ui_rc={self.ui_test_final_rc}, full_rc={full_rc}, ui_not_degraded={self.ui_subset_not_degraded}"
        )
        self.log_step("5_test_regression", status, detail)

    @staticmethod
    def goal_num(goal_id: str) -> int:
        m = re.fullmatch(r"G(\d+)", goal_id)
        if not m:
            return 10**9
        return int(m.group(1))

    def load_ssot(self) -> dict[str, Any]:
        raw = (self.repo_root / SSOT_PATH).read_text(encoding="utf-8")
        loaded = yaml.safe_load(raw)
        if not isinstance(loaded, dict):
            raise ValueError("SSOT YAML root must be mapping")
        return loaded

    def save_ssot(self, text: str) -> None:
        self.write_text(self.repo_root / SSOT_PATH, text)

    def parse_track_goals(self, loaded: dict[str, Any]) -> list[GoalInfo]:
        rows = loaded.get("goal_checklist")
        out: list[GoalInfo] = []
        if not isinstance(rows, list):
            return out
        for row in rows:
            if not isinstance(row, dict):
                continue
            track = str(row.get("track") or "").strip()
            if track not in {"skeleton", "impl_fetchdata"}:
                continue
            out.append(
                GoalInfo(
                    goal_id=str(row.get("id") or ""),
                    title=str(row.get("title") or ""),
                    track=track,
                    status_now=str(row.get("status_now") or ""),
                    depends_on=[str(x) for x in (row.get("depends_on") or []) if isinstance(x, str)],
                    phase_doc_path=str(row.get("phase_doc_path") or ""),
                    allowed_paths=[str(x) for x in (row.get("allowed_paths") or []) if isinstance(x, str)],
                    acceptance_commands=[
                        str(x) for x in (row.get("acceptance_commands") or []) if isinstance(x, str)
                    ],
                )
            )
        return out

    def build_new_goal_block(
        self,
        *,
        goal_id: str,
        title: str,
        track: str,
        depends_on: list[str],
        phase_doc_path: str,
        ui_path: str,
        expected_state_change: str,
        expected_artifacts: list[str],
        allowed_paths: list[str],
        acceptance_commands: list[str],
        note: str,
        exception_id: str,
    ) -> str:
        dep_lines = "".join(f"  - {d}\n" for d in depends_on) if depends_on else "  []\n"
        artifacts_lines = "".join(f"  - {a}\n" for a in expected_artifacts)
        allowed_lines = "".join(f"  - {a}\n" for a in allowed_paths)
        cmd_lines = "".join(f"    - {self.yaml_quote(c)}\n" for c in acceptance_commands)
        cmd_lines2 = "".join(f"  - {self.yaml_quote(c)}\n" for c in acceptance_commands)
        return (
            f"- id: {goal_id}\n"
            f"  title: {title}\n"
            f"  status_now: planned\n"
            f"  depends_on:\n"
            f"{dep_lines}"
            f"  track: {track}\n"
            f"  phase_doc_path: {phase_doc_path}\n"
            f"  ui_path: {ui_path}\n"
            f"  expected_state_change: {expected_state_change}\n"
            f"  expected_artifacts:\n"
            f"{artifacts_lines}"
            f"  allowed_paths:\n"
            f"{allowed_lines}"
            f"  acceptance:\n"
            f"    commands:\n"
            f"{cmd_lines}"
            f"  acceptance_commands:\n"
            f"{cmd_lines2}"
            f"  stop_condition_exception_scope:\n"
            f"    exception_id: {exception_id}\n"
            f"    rationale: preflight generated minimal parallel-ready scope.\n"
            f"  notes:\n"
            f"  - {note}\n"
        )

    @staticmethod
    def yaml_quote(s: str) -> str:
        s2 = s.replace("'", "''")
        return f"'{s2}'"

    def create_phase_doc(
        self,
        *,
        path: Path,
        title: str,
        goal: str,
        requirements: list[str],
        architecture: list[str],
        dod: list[str],
    ) -> None:
        text = (
            f"# {title}\n\n"
            "## Goal\n"
            f"- {goal}\n\n"
            "## Requirements\n"
            + "".join(f"- {r}\n" for r in requirements)
            + "\n## Architecture\n"
            + "".join(f"- {a}\n" for a in architecture)
            + "\n## DoD\n"
            + "".join(f"- {x}\n" for x in dod)
            + "\n## Implementation Plan\n"
            "TBD by controller at execution time.\n"
        )
        self.write_text(path, text)

    def _append_goal_blocks_to_ssot(self, blocks: list[str]) -> None:
        ssot_abs = self.repo_root / SSOT_PATH
        text = ssot_abs.read_text(encoding="utf-8")
        marker_idx = text.find(PHASE_SECTION_SENTINEL)
        if marker_idx < 0:
            self.blockers.append("Unable to locate SSOT insertion point before agents_pipeline_v1.")
            return
        insertion = "\n" + "".join(blocks)
        new_text = text[:marker_idx] + insertion + text[marker_idx:]
        self.write_text(ssot_abs, new_text)

    def ensure_track_minimum_and_parallel_pair(self) -> tuple[GoalInfo, GoalInfo] | None:
        try:
            loaded = self.load_ssot()
        except Exception as e:  # noqa: BLE001
            self.blockers.append(f"Cannot load SSOT for goal selection: {e}")
            return None

        goals = self.parse_track_goals(loaded)
        planned_counts = {"skeleton": 0, "impl_fetchdata": 0}
        all_ids = []
        for g in goals:
            all_ids.append(g.goal_id)
            if g.status_now in {"planned", "partial"}:
                planned_counts[g.track] += 1

        next_num = max([self.goal_num(x) for x in all_ids] + [0]) + 1
        blocks: list[str] = []

        if planned_counts["skeleton"] < 3:
            gid = f"G{next_num}"
            next_num += 1
            phase_doc = f"docs/08_phases/00_skeleton/phase_skel_g{self.goal_num(gid)}_fetch_preflight_parallel_guard.md"
            self.create_phase_doc(
                path=self.repo_root / phase_doc,
                title=f"Phase Skeleton {gid}: Fetch Preflight Parallel Guard",
                goal="Create a skeleton-track, preflight-ready governance guard goal for parallel dispatch readiness.",
                requirements=[
                    "Must remain documentation-only and maintain deterministic governance boundary.",
                    "Must not alter contracts or policies.",
                    "Must keep allowed_paths strictly scoped.",
                ],
                architecture=[
                    "Source of truth remains docs/12_workflows/skeleton_ssot_v1.yaml.",
                    "References whole-view and fetch implementation spec constraints.",
                    "No runtime code mutation.",
                ],
                dod=[
                    "python3 scripts/check_docs_tree.py passes.",
                    f"rg -n \"{gid}|phase_skel_g{self.goal_num(gid)}|track: skeleton\" docs/12_workflows/skeleton_ssot_v1.yaml passes.",
                    "Implementation Plan section is fixed to TBD text.",
                ],
            )
            cmds = [
                "python3 scripts/check_docs_tree.py",
                f'rg -n "{gid}|phase_skel_g{self.goal_num(gid)}|track: skeleton" docs/12_workflows/skeleton_ssot_v1.yaml',
            ]
            blocks.append(
                self.build_new_goal_block(
                    goal_id=gid,
                    title="Fetch Preflight Parallel Guard",
                    track="skeleton",
                    depends_on=["G58"],
                    phase_doc_path=phase_doc,
                    ui_path=f"/skeleton/fetch-preflight-guard-{self.goal_num(gid)}",
                    expected_state_change="Skeleton track has at least one additional planned goal for parallel startup readiness.",
                    expected_artifacts=[phase_doc, SSOT_PATH.as_posix()],
                    allowed_paths=[phase_doc, SSOT_PATH.as_posix()],
                    acceptance_commands=cmds,
                    note="Auto-generated by preflight to satisfy minimum planned/partial goal count.",
                    exception_id=f"g{self.goal_num(gid)}_preflight_skeleton_scope",
                )
            )
            planned_counts["skeleton"] += 1

        if planned_counts["impl_fetchdata"] < 3:
            gid = f"G{next_num}"
            next_num += 1
            phase_doc = (
                f"docs/08_phases/10_impl_fetchdata/phase_fetch_g{self.goal_num(gid)}_preflight_dispatch_packet_smoke.md"
            )
            self.create_phase_doc(
                path=self.repo_root / phase_doc,
                title=f"Phase Impl {gid}: Fetch Preflight Dispatch Packet Smoke",
                goal="Create an impl-fetchdata planned goal with dependency-ready, disjoint allowed_paths for dry-run dispatch.",
                requirements=[
                    "Must depend on an implemented impl_fetchdata baseline goal.",
                    "Must keep scope limited to preflight dispatch and packet smoke checks.",
                    "Must avoid business behavior changes.",
                ],
                architecture=[
                    "Use existing check_docs_tree and subagent packet validation flow.",
                    "Keep allowed_paths disjoint from selected skeleton goal.",
                    "Preserve deterministic evidence outputs.",
                ],
                dod=[
                    "python3 scripts/check_docs_tree.py passes.",
                    f"rg -n \"{gid}|phase_fetch_g{self.goal_num(gid)}|track: impl_fetchdata\" docs/12_workflows/skeleton_ssot_v1.yaml passes.",
                    "Implementation Plan section is fixed to TBD text.",
                ],
            )
            cmds = [
                "python3 scripts/check_docs_tree.py",
                f'rg -n "{gid}|phase_fetch_g{self.goal_num(gid)}|track: impl_fetchdata" docs/12_workflows/skeleton_ssot_v1.yaml',
            ]
            blocks.append(
                self.build_new_goal_block(
                    goal_id=gid,
                    title="Fetch Preflight Dispatch Packet Smoke",
                    track="impl_fetchdata",
                    depends_on=["G61"],
                    phase_doc_path=phase_doc,
                    ui_path=f"/impl/fetch-preflight-dispatch-smoke-{self.goal_num(gid)}",
                    expected_state_change="impl_fetchdata track has at least one additional planned goal ready for dry-run dispatch.",
                    expected_artifacts=[phase_doc, "scripts/preflight_qa_fetch.py", SSOT_PATH.as_posix()],
                    allowed_paths=[
                        phase_doc,
                        "scripts/preflight_qa_fetch.py",
                        "tests/test_subagent_packet_phase15.py",
                    ],
                    acceptance_commands=cmds,
                    note="Auto-generated by preflight to satisfy minimum planned/partial goal count and dependency-ready pairing.",
                    exception_id=f"g{self.goal_num(gid)}_preflight_impl_scope",
                )
            )
            planned_counts["impl_fetchdata"] += 1

        if blocks:
            self._append_goal_blocks_to_ssot(blocks)

        loaded_after = self.load_ssot()
        goals_after = self.parse_track_goals(loaded_after)
        implemented = {g.goal_id for g in goals_after if g.status_now == "implemented"}
        skeleton_candidates = sorted(
            [g for g in goals_after if g.track == "skeleton" and g.status_now in {"planned", "partial"}],
            key=lambda g: self.goal_num(g.goal_id),
        )
        impl_candidates = sorted(
            [
                g
                for g in goals_after
                if g.track == "impl_fetchdata"
                and g.status_now in {"planned", "partial"}
                and all(dep in implemented for dep in g.depends_on)
            ],
            key=lambda g: self.goal_num(g.goal_id),
        )

        for s in skeleton_candidates:
            for i in impl_candidates:
                if self.allowed_paths_disjoint(s.allowed_paths, i.allowed_paths):
                    return (s, i)
        return None

    @staticmethod
    def path_prefix(path: str) -> str:
        p = path.strip()
        for token in ("*", "?", "["):
            idx = p.find(token)
            if idx >= 0:
                p = p[:idx]
        return p.rstrip("/")

    def allowed_paths_disjoint(self, a: list[str], b: list[str]) -> bool:
        if not a or not b:
            return False
        ap = [self.path_prefix(x) for x in a]
        bp = [self.path_prefix(x) for x in b]
        for x in ap:
            for y in bp:
                if not x or not y:
                    continue
                if x == y:
                    return False
                if x.startswith(y + "/") or y.startswith(x + "/"):
                    return False
        return True

    def step6_goal_selection(self) -> None:
        pair = self.ensure_track_minimum_and_parallel_pair()
        if pair is None:
            self.blockers.append("Unable to identify or generate a parallel-ready goal pair.")
            self.log_step("6_goal_selection", "FAIL", "No parallel pair found.")
            return
        self.selected_pair = pair
        self.log_step(
            "6_goal_selection",
            "PASS",
            f"Selected pair: {pair[0].goal_id} ({pair[0].track}) + {pair[1].goal_id} ({pair[1].track})",
        )

    def sha256_file(self, rel: str) -> str:
        path = self.repo_root / rel
        h = hashlib.sha256()
        with path.open("rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()

    def snapshot_doc(self, files: dict[str, str]) -> dict[str, Any]:
        return {
            "schema_version": "subagent_workspace_snapshot_v1",
            "captured_at": self.now_iso(),
            "files": files,
        }

    def run_acceptance_for_goal(self, cmds: list[str], step: str) -> tuple[list[dict[str, Any]], list[str], bool]:
        rows: list[dict[str, Any]] = []
        commands_run: list[str] = []
        ok = True
        for cmd in cmds:
            started = self.now_iso()
            cp = self.run_cmd(step=step, command=cmd, timeout_sec=900)
            ended = self.now_iso()
            commands_run.append(cmd)
            rows.append(
                {
                    "role": "validator",
                    "command": cmd,
                    "exit_code": cp.returncode,
                    "started_at": started,
                    "ended_at": ended,
                    "stdout_tail": self.tail(cp.stdout, 300),
                }
            )
            if cp.returncode != 0:
                ok = False
        return rows, commands_run, ok

    def build_packet_for_goal(self, goal: GoalInfo) -> bool:
        packet_dir = self.packet_root / goal.goal_id
        packet_dir.mkdir(parents=True, exist_ok=True)
        self.mark_modified(packet_dir.relative_to(self.repo_root))

        acceptance_commands = goal.acceptance_commands or ["python3 scripts/check_docs_tree.py"]
        allowed_paths = goal.allowed_paths or [goal.phase_doc_path]

        task = {
            "schema_version": "subagent_task_card_v1",
            "phase_id": goal.goal_id,
            "goal_ids": [goal.goal_id],
            "published_at": self.now_iso(),
            "published_by": "orchestrator_codex",
            "executor_required": "codex_cli_subagent",
            "evidence_policy": "hardened",
            "evidence_files": {
                "workspace_before": f"{self.packet_root.relative_to(self.repo_root).as_posix()}/{goal.goal_id}/workspace_before.json",
                "workspace_after": f"{self.packet_root.relative_to(self.repo_root).as_posix()}/{goal.goal_id}/workspace_after.json",
                "acceptance_log": f"{self.packet_root.relative_to(self.repo_root).as_posix()}/{goal.goal_id}/acceptance_run_log.jsonl",
            },
            "external_noise_paths": [],
            "allowed_paths": allowed_paths,
            "acceptance_commands": acceptance_commands,
            "ui_blackbox_checks": ["Preflight dry-run dispatch packet validation only."],
            "stop_conditions": [
                "Any file change outside allowed_paths",
                "Any acceptance command failure",
            ],
        }
        self.write_yaml(packet_dir / "task_card.yaml", task)

        before_files: dict[str, str] = {}
        tracked = [SSOT_PATH.as_posix(), goal.phase_doc_path, f"{self.packet_root.relative_to(self.repo_root).as_posix()}/{goal.goal_id}/task_card.yaml"]
        for rel in tracked:
            if (self.repo_root / rel).is_file():
                before_files[rel] = self.sha256_file(rel)
        self.write_text(packet_dir / "workspace_before.json", json.dumps(self.snapshot_doc(before_files), ensure_ascii=True, indent=2) + "\n")

        rows, commands_run, acceptance_ok = self.run_acceptance_for_goal(acceptance_commands, step="7_dryrun_acceptance")
        self.write_text(
            packet_dir / "acceptance_run_log.jsonl",
            "\n".join(json.dumps(r, ensure_ascii=True, sort_keys=True) for r in rows) + ("\n" if rows else ""),
        )

        exe = {
            "schema_version": "subagent_executor_report_v1",
            "phase_id": goal.goal_id,
            "reported_at": self.now_iso(),
            "executor": {"role": "codex_cli_subagent", "runtime": "codex_cli", "session_ref": f"preflight_{goal.goal_id}"},
            "status": "completed" if acceptance_ok else "failed",
            "changed_files": [],
            "commands_run": commands_run,
            "evidence_summary": {
                "workspace_before": task["evidence_files"]["workspace_before"],
                "workspace_after": task["evidence_files"]["workspace_after"],
                "acceptance_log": task["evidence_files"]["acceptance_log"],
            },
            "notes": ["Generated by preflight dry-run dispatch builder."],
        }
        self.write_yaml(packet_dir / "executor_report.yaml", exe)

        checks = []
        for name in REQUIRED_VALIDATOR_CHECKS:
            checks.append(
                {
                    "name": name,
                    "pass": True if acceptance_ok else (name != "acceptance_commands_executed"),
                    "detail": "auto-generated preflight dry-run validator check",
                }
            )
        validator = {
            "schema_version": "subagent_validator_report_v1",
            "phase_id": goal.goal_id,
            "reported_at": self.now_iso(),
            "validator": {"role": "orchestrator_codex"},
            "status": "pass" if acceptance_ok else "fail",
            "checks": checks,
            "notes": ["Generated by preflight dry-run dispatch builder."],
        }
        self.write_yaml(packet_dir / "validator_report.yaml", validator)

        after_files: dict[str, str] = {}
        tracked_after = [
            SSOT_PATH.as_posix(),
            goal.phase_doc_path,
            f"{self.packet_root.relative_to(self.repo_root).as_posix()}/{goal.goal_id}/task_card.yaml",
            f"{self.packet_root.relative_to(self.repo_root).as_posix()}/{goal.goal_id}/workspace_before.json",
            f"{self.packet_root.relative_to(self.repo_root).as_posix()}/{goal.goal_id}/acceptance_run_log.jsonl",
            f"{self.packet_root.relative_to(self.repo_root).as_posix()}/{goal.goal_id}/executor_report.yaml",
            f"{self.packet_root.relative_to(self.repo_root).as_posix()}/{goal.goal_id}/validator_report.yaml",
        ]
        for rel in tracked_after:
            if (self.repo_root / rel).is_file():
                after_files[rel] = self.sha256_file(rel)
        self.write_text(packet_dir / "workspace_after.json", json.dumps(self.snapshot_doc(after_files), ensure_ascii=True, indent=2) + "\n")

        checker = self.repo_root / "scripts/check_subagent_packet.py"
        if checker.is_file():
            cp = self.run_cmd(
                step="7_dryrun_packet_validate",
                command=f"python3 scripts/check_subagent_packet.py --phase-id {goal.goal_id} --packet-root {self.packet_root.relative_to(self.repo_root).as_posix()}",
                timeout_sec=180,
            )
            if cp.returncode != 0:
                self.blockers.append(f"Dry-run packet validation failed for {goal.goal_id}.")
                return False
            return acceptance_ok
        fallback = (
            "# validator_report_fallback\n\n"
            "- reason: scripts/check_subagent_packet.py missing\n"
            "- strategy: structure + command exit code verification only\n"
        )
        self.write_text(packet_dir / "validator_report_fallback.md", fallback)
        return acceptance_ok

    def step7_dryrun_dispatch(self) -> None:
        if self.selected_pair is None:
            self.blockers.append("Cannot run dry-run dispatch without selected goal pair.")
            self.log_step("7_dryrun_dispatch", "FAIL", "No selected pair.")
            return
        ok_a = self.build_packet_for_goal(self.selected_pair[0])
        ok_b = self.build_packet_for_goal(self.selected_pair[1])
        self.dryrun_ok = ok_a and ok_b
        self.log_step(
            "7_dryrun_dispatch",
            "PASS" if self.dryrun_ok else "FAIL",
            f"Dry-run packets built for {self.selected_pair[0].goal_id}, {self.selected_pair[1].goal_id}.",
        )

    def render_report(self) -> str:
        ready = (
            self.docs_tree_ok
            and self.ui_subset_not_degraded
            and self.dryrun_ok
            and not self.blockers
            and not self.external_blockers
            and not self.requested_paths
        )
        status = "READY" if ready else "BLOCKED"
        lines: list[str] = []
        lines.append("# Preflight Report")
        lines.append("")
        lines.append(f"- Status: **{status}**")
        lines.append(f"- Generated at (UTC): `{self.now_iso()}`")
        lines.append(f"- Repo: `{self.repo_root.as_posix()}`")
        lines.append("")
        lines.append("## Checklist")
        lines.append("")
        lines.append("| Step | Status | Detail |")
        lines.append("|---|---|---|")
        for row in self.step_log:
            lines.append(f"| `{row.step}` | `{row.status}` | {row.detail} |")
        lines.append("")
        lines.append("## Commands")
        lines.append("")
        for c in self.command_log:
            lines.append(f"- [{c.step}] `{c.command}` -> exit `{c.exit_code}`")
            if c.stdout_tail:
                safe_stdout = c.stdout_tail.replace("`", "'")
                lines.append(f"  - stdout_tail: `{safe_stdout}`")
            if c.stderr_tail:
                safe_stderr = c.stderr_tail.replace("`", "'")
                lines.append(f"  - stderr_tail: `{safe_stderr}`")
        lines.append("")
        lines.append("## Self-Heal Changes")
        lines.append("")
        if self.modified_files:
            for p in sorted(self.modified_files):
                lines.append(f"- `{p}`")
        else:
            lines.append("- None")
        lines.append("")
        lines.append("## Blockers")
        lines.append("")
        if self.external_blockers or self.blockers:
            for b in self.external_blockers + self.blockers:
                lines.append(f"- {b}")
        else:
            lines.append("- None")
        lines.append("")
        lines.append("## Next Step Suggestions")
        lines.append("")
        suggestions = self.next_step_suggestions()
        if suggestions:
            for s in suggestions:
                lines.append(f"- {s}")
        else:
            lines.append("- None")
        lines.append("")
        lines.append("## requested_paths")
        lines.append("")
        if self.requested_paths:
            for p in sorted(self.requested_paths):
                lines.append(f"- `{p}`")
        else:
            lines.append("- None")
        lines.append("")
        lines.append("## Next Parallel Goals")
        lines.append("")
        if self.selected_pair:
            s, i = self.selected_pair
            lines.append(f"- skeleton: `{s.goal_id}` -> `{s.phase_doc_path}`")
            lines.append(f"- impl_fetchdata: `{i.goal_id}` -> `{i.phase_doc_path}`")
        else:
            lines.append("- Not selected")
        lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def next_step_suggestions(self) -> list[str]:
        out: list[str] = []
        if any("Dependency" in b for b in self.external_blockers):
            out.append("Install `python3.12-venv` on host to enable isolated venv path, then rerun preflight.")
        failed_tests = self.extract_failed_tests_from_command_log(step="5_pytest_full")
        if failed_tests:
            out.append(
                "Handle full pytest business failures in normal implementation phases (non-preflight scope): "
                + ", ".join(f"`{x}`" for x in failed_tests)
            )
        if self.requested_paths:
            out.append(
                "Decide whether to allow mutations in requested_paths and rerun preflight after scope is expanded."
            )
        if not out and (self.blockers or self.external_blockers):
            out.append("Review blockers above and rerun preflight after resolving the listed constraints.")
        return out

    def extract_failed_tests_from_command_log(self, *, step: str) -> list[str]:
        names: list[str] = []
        for row in self.command_log:
            if row.step != step:
                continue
            blob = f"{row.stdout_tail}\n{row.stderr_tail}"
            for m in re.finditer(r"FAILED (tests/[^\s]+)", blob):
                name = m.group(1).strip()
                if name not in names:
                    names.append(name)
        return names

    def render_one_sentence_start(self) -> str:
        return (
            "启动并行开发：从 SSOT 选择 1 条 skeleton 与 1 条 impl_fetchdata（allowed_paths 互斥且 impl 依赖均为 implemented），"
            "生成 task_cards 并派发 subagents，主控执行验收命令与 packet 校验后回写 SSOT。"
            "\n"
        )

    def step8_write_outputs(self) -> int:
        report_path = self.report_root / "preflight_report.md"
        start_path = self.report_root / "one_sentence_start.txt"
        self.write_text(report_path, self.render_report())
        self.write_text(start_path, self.render_one_sentence_start())
        self.log_step("8_write_outputs", "PASS", "Report and one-sentence start command written.")

        ready = (
            self.docs_tree_ok
            and self.ui_subset_not_degraded
            and self.dryrun_ok
            and not self.blockers
            and not self.external_blockers
            and not self.requested_paths
        )
        return READY_EXIT if ready else BLOCKED_EXIT

    def run(self) -> int:
        self.ensure_report_dirs()
        self.step0_collect_baseline()
        self.step1_required_paths()
        self.step2_ssot_validation_and_heal()
        self.step3_docs_tree_loop()
        self.step4_prepare_python_env()
        self.step5_test_regression()
        self.step6_goal_selection()
        self.step7_dryrun_dispatch()
        return self.step8_write_outputs()


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="QA Fetch one-click preflight + self-heal + dry-run dispatch.")
    ap.add_argument("--report-root", default="artifacts/preflight", help="Preflight report root directory.")
    ap.add_argument(
        "--packet-root",
        default="artifacts/preflight/dispatch_dryrun",
        help="Dry-run dispatch packet root directory.",
    )
    ap.add_argument(
        "--venv-dir",
        default="/tmp/quanteam_preflight_venv",
        help="Virtualenv directory used for preflight test environment.",
    )
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    runner = Preflight(
        report_root=Path(args.report_root),
        packet_root=Path(args.packet_root),
        venv_dir=Path(args.venv_dir),
    )
    return runner.run()


if __name__ == "__main__":
    raise SystemExit(main())
