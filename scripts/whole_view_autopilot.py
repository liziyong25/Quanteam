#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import dataclasses
import fnmatch
import hashlib
import json
import re
import shlex
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

# Ensure helper modules in scripts/ are importable when this file is loaded via spec.
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

try:
    from requirement_splitter import extract_requirement_clauses, load_splitter_profiles
except Exception:
    extract_requirement_clauses = None
    load_splitter_profiles = None


SSOT_DEFAULT = Path("docs/12_workflows/skeleton_ssot_v1.yaml")
PACKET_ROOT_DEFAULT = Path("artifacts/subagent_control")
MILESTONE_ROOT_DEFAULT = Path("artifacts/autopilot/milestones")
ARCHITECT_PREPLAN_ROOT_DEFAULT = Path("artifacts/autopilot/preplan")
SPLITTER_CONFIG_DEFAULT = Path("docs/12_workflows/requirement_splitter_profiles_v1.yaml")
REPO_ROOT = Path.cwd()
STOP_CONDITION_REDLINES = ("contracts/**", "policies/**", "*holdout*")
GOAL_ACTIVE_STATUS = {"planned", "partial"}
STOP_CONDITION_CONTRACTS = "Any change touching contracts/**"
STOP_CONDITION_POLICIES = "Any change touching policies/**"
STOP_CONDITION_API = "Any API schema or route behavior change"
STOP_CONDITION_HOLDOUT = "Any holdout visibility rule change"
STOP_CONDITION_LABELS = (
    STOP_CONDITION_CONTRACTS,
    STOP_CONDITION_POLICIES,
    STOP_CONDITION_API,
    STOP_CONDITION_HOLDOUT,
)
API_ROUTE_TOUCH_PATTERNS = (
    "src/quant_eam/api/**",
    "src/quant_eam/ui/templates/**",
    "src/quant_eam/ui/static/**",
)

REQ_SOURCE_CANDIDATES: tuple[tuple[str, tuple[Path, ...]], ...] = (
    (
        "WV",
        (
            Path("Quant‑EAM Whole View Framework.md（v0.5‑draft）.md"),
            Path("Quant‑EAM Whole View Framework.md"),
            Path("docs/00_overview/Quant‑EAM Whole View Framework.md"),
        ),
    ),
    ("QF", (Path("docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"),)),
    ("WB", (Path("docs/00_overview/workbench_ui_productization_v1.md"),)),
)
REQ_PREFIX_OWNER_TRACK: dict[str, str] = {
    "WV": "skeleton",
    "QF": "impl_fetchdata",
    "WB": "impl_workbench",
}
IMPLEMENT_TRACKS = {"impl_fetchdata", "impl_workbench"}
ALL_TRACKS = {"skeleton", *IMPLEMENT_TRACKS}

DEFAULT_TRACK_SKILLS: dict[str, list[str]] = {
    "skeleton": [
        "requirement-splitter",
        "ssot-goal-planner",
        "phase-authoring",
        "packet-evidence-guard",
    ],
    "impl_fetchdata": [
        "requirement-splitter",
        "ssot-goal-planner",
        "phase-authoring",
        "packet-evidence-guard",
    ],
    "impl_workbench": [
        "requirement-splitter",
        "ssot-goal-planner",
        "phase-authoring",
        "packet-evidence-guard",
    ],
}
DEFAULT_SKILL_REGISTRY: dict[str, str] = {
    "architect-planner": "skills/architect-planner",
    "requirement-splitter": "skills/requirement-splitter",
    "ssot-goal-planner": "skills/ssot-goal-planner",
    "phase-authoring": "skills/phase-authoring",
    "packet-evidence-guard": "skills/packet-evidence-guard",
    "milestone-gate": "skills/milestone-gate",
}
DEFAULT_DIFFICULTY_WEIGHTS: dict[str, int] = {
    "dependency_depth": 25,
    "path_complexity": 20,
    "acceptance_cost": 20,
    "redline_proximity": 20,
    "history_instability": 15,
}
DEFAULT_REASONING_TIERS: dict[str, dict[str, Any]] = {
    "medium": {"model": "", "timeout_sec": 1800, "retry": 2},
    "high": {"model": "", "timeout_sec": 3600, "retry": 2},
    "super_high": {"model": "", "timeout_sec": 5400, "retry": 3},
}
DEFAULT_REASONING_THRESHOLDS: dict[str, int] = {
    "medium_max": 39,
    "high_max": 69,
}
FETCH_IMPL_REQUIREMENT_ACCEPTANCE_COMMANDS: tuple[str, ...] = (
    "python3 -m pytest -q tests/test_fetch_contracts_phase77.py tests/test_qa_fetch_probe.py tests/test_qa_fetch_resolver.py",
)

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "must",
    "should",
    "when",
    "into",
    "then",
    "have",
    "has",
    "all",
    "are",
    "not",
    "only",
    "any",
    "can",
    "will",
    "its",
    "use",
    "uses",
}


@dataclasses.dataclass
class CommandResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str


@dataclasses.dataclass
class Goal:
    goal_id: str
    status_now: str
    track: str
    title: str
    depends_on: list[str]
    requirement_ids: list[str]
    allowed_paths: list[str]
    acceptance_commands: list[str]
    stop_scope: dict[str, Any]
    phase_doc_path: str
    capability_cluster_id: str
    required_skills: list[str]
    difficulty_score: int
    reasoning_tier: str
    todo_checklist: list[str]
    risk_notes: list[str]
    parallel_hints: list[str]
    todo_planner: dict[str, Any]
    allow_noop: bool
    raw: dict[str, Any]


@dataclasses.dataclass
class Requirement:
    req_id: str
    source_document: str
    source_line: int
    owner_track: str
    clause: str
    depends_on_req_ids: list[str]
    status_now: str
    mapped_goal_ids: list[str]
    acceptance_commands: list[str]
    acceptance_verified: bool
    capability_cluster_id: str
    raw: dict[str, Any]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _goal_num(goal_id: str) -> int:
    m = re.fullmatch(r"G(\d+)", str(goal_id).strip())
    return int(m.group(1)) if m else 10**9


def _decode_git_quoted_path(path: str) -> str:
    s = str(path).strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        try:
            parsed = ast.literal_eval(s)
            if isinstance(parsed, str):
                s = parsed
            else:
                s = str(parsed)
        except Exception:
            s = s[1:-1]
    try:
        s = s.encode("latin-1").decode("utf-8")
    except UnicodeError:
        pass
    return s


def _norm_path(path: str) -> str:
    p = _decode_git_quoted_path(path).replace("\\", "/").strip().strip('"').strip("'")
    while p.startswith("./"):
        p = p[2:]
    return p


def _path_str_for_doc(path: Path, *, repo_root: Path) -> str:
    p = Path(path)
    if not p.is_absolute():
        return p.as_posix()
    try:
        return p.relative_to(repo_root).as_posix()
    except Exception:
        return p.as_posix()


def _match_rule(path: str, rule: str) -> bool:
    p = _norm_path(path)
    r = _norm_path(rule)
    if not r:
        return False
    if "*" in r or "?" in r or "[" in r:
        return fnmatch.fnmatch(p, r)
    return p == r or p.startswith(r.rstrip("/") + "/")


def _path_rules_conflict(left: list[str], right: list[str]) -> bool:
    for a in left:
        for b in right:
            aa = _norm_path(a).rstrip("/")
            bb = _norm_path(b).rstrip("/")
            if not aa or not bb:
                continue
            if _match_rule(aa, bb) or _match_rule(bb, aa):
                return True
    return False


def _parallel_scope_paths(paths: list[str]) -> list[str]:
    """Return business-change paths used for parallel conflict checks.

    Shared controller-managed paths (SSOT and packet evidence folders) are
    excluded so that implementation tracks can still be scheduled together when
    their code/doc scopes are disjoint.
    """
    out: list[str] = []
    for rule in paths:
        norm = _norm_path(rule).rstrip("/")
        if not norm:
            continue
        if norm == "docs/12_workflows/skeleton_ssot_v1.yaml":
            continue
        if norm.startswith("artifacts/subagent_control/"):
            continue
        out.append(rule)
    return out


def _tokenize(text: str) -> set[str]:
    toks = {x.lower() for x in re.findall(r"[A-Za-z0-9_]{3,}", str(text))}
    return {x for x in toks if x not in STOPWORDS}


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _requirement_doc_path(prefix: str) -> Path:
    candidates = dict(REQ_SOURCE_CANDIDATES).get(prefix, ())
    for rel in candidates:
        if (REPO_ROOT / rel).is_file():
            return rel
    raise FileNotFoundError(f"requirement source document missing for {prefix}: {candidates}")


def _parse_markdown_clauses(
    path: Path,
    prefix: str,
    *,
    splitter_profiles: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if extract_requirement_clauses is not None and splitter_profiles:
        try:
            rows = extract_requirement_clauses(
                source_path=(REPO_ROOT / path),
                prefix=prefix,
                source_document=path.as_posix(),
                profiles=splitter_profiles,
            )
            if rows:
                return rows
        except Exception:
            pass

    text = (REPO_ROOT / path).read_text(encoding="utf-8")
    lines = text.splitlines()
    heading_re = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*$")
    bullet_re = re.compile(r"^\s*[-*]\s+(.+?)\s*$")
    enum_re = re.compile(r"^\s*\d+[.)]\s+(.+?)\s*$")

    rows: list[dict[str, Any]] = []
    last_section_req_id = ""
    last_doc_req_id = ""
    heading_stack: list[str] = []
    last_heading_level = 0
    idx = 1

    for lineno, line in enumerate(lines, start=1):
        h = heading_re.match(line)
        if h:
            level = len(h.group(1))
            title = h.group(2).strip()
            if not title:
                continue
            if level <= last_heading_level:
                heading_stack = heading_stack[: level - 1]
            heading_stack.append(title)
            last_heading_level = level
            req_id = f"{prefix}-{idx:03d}"
            idx += 1
            rows.append(
                {
                    "req_id": req_id,
                    "source_document": path.as_posix(),
                    "source_line": lineno,
                    "clause": " / ".join(heading_stack),
                    "depends_on_req_ids": [last_doc_req_id] if last_doc_req_id else [],
                    "status_now": "planned",
                    "mapped_goal_ids": [],
                    "capability_cluster_id": "",
                }
            )
            last_section_req_id = req_id
            last_doc_req_id = req_id
            continue

        m = bullet_re.match(line) or enum_re.match(line)
        if m and last_section_req_id:
            clause = m.group(1).strip()
            if len(clause) < 10:
                continue
            req_id = f"{prefix}-{idx:03d}"
            idx += 1
            rows.append(
                {
                    "req_id": req_id,
                    "source_document": path.as_posix(),
                    "source_line": lineno,
                    "clause": clause,
                    "depends_on_req_ids": [last_section_req_id],
                    "status_now": "planned",
                    "mapped_goal_ids": [],
                    "capability_cluster_id": "",
                }
            )
            last_doc_req_id = req_id

    if not rows:
        raise ValueError(f"no markdown clauses extracted: {path.as_posix()}")
    return rows


class WholeViewAutopilot:
    def __init__(
        self,
        *,
        ssot_path: Path,
        packet_root: Path,
        milestone_root: Path,
        max_parallel: int,
        dry_run: bool,
        run_gates: bool,
        enable_push: bool,
        latest_phase_id: str | None,
        subagent_mode: str,
        codex_model: str | None,
        codex_timeout_sec: int,
        codex_json_log: bool,
        skill_enforcement_mode: str,
        reasoning_tier_override: str | None,
        skill_registry_path: Path | None,
        splitter_config_path: Path,
    ) -> None:
        self.repo_root = REPO_ROOT
        self.ssot_path = ssot_path if ssot_path.is_absolute() else (self.repo_root / ssot_path)
        self.packet_root = packet_root if packet_root.is_absolute() else (self.repo_root / packet_root)
        self.milestone_root = milestone_root if milestone_root.is_absolute() else (self.repo_root / milestone_root)
        self.max_parallel = max(1, int(max_parallel))
        self.dry_run = dry_run
        self.run_gates = run_gates
        self.enable_push = enable_push
        self.latest_phase_id_override = latest_phase_id
        self.subagent_mode = subagent_mode if subagent_mode in {"codex_exec", "acceptance_only"} else "codex_exec"
        self.codex_model = (codex_model or "").strip() or None
        self.codex_timeout_sec = max(60, int(codex_timeout_sec))
        self.codex_json_log = bool(codex_json_log)
        self.skill_enforcement_mode = (
            skill_enforcement_mode
            if skill_enforcement_mode in {"warn", "enforce"}
            else "warn"
        )
        self.reasoning_tier_override = (
            reasoning_tier_override
            if reasoning_tier_override in {"medium", "high", "super_high"}
            else None
        )
        self.skill_registry_path = (
            skill_registry_path
            if (skill_registry_path and skill_registry_path.is_absolute())
            else (self.repo_root / skill_registry_path if skill_registry_path else None)
        )
        self.external_skill_registry: dict[str, str] = {}
        if self.skill_registry_path and self.skill_registry_path.is_file():
            try:
                loaded_registry = yaml.safe_load(self.skill_registry_path.read_text(encoding="utf-8"))
                if isinstance(loaded_registry, dict):
                    if isinstance(loaded_registry.get("skill_registry_v1"), dict):
                        loaded_registry = loaded_registry["skill_registry_v1"]
                    registry_rows = loaded_registry.get("skills") if isinstance(loaded_registry.get("skills"), list) else []
                    for row in registry_rows:
                        if not isinstance(row, dict):
                            continue
                        sid = str(row.get("id") or "").strip()
                        spath = str(row.get("path") or "").strip()
                        if sid and spath:
                            self.external_skill_registry[sid] = spath
            except Exception:
                self.external_skill_registry = {}
        self.splitter_config_path = (
            splitter_config_path if splitter_config_path.is_absolute() else (self.repo_root / splitter_config_path)
        )
        self.splitter_profiles: dict[str, dict[str, Any]] = {}
        if load_splitter_profiles is not None and self.splitter_config_path.is_file():
            try:
                loaded = load_splitter_profiles(self.splitter_config_path)
                if isinstance(loaded, dict):
                    self.splitter_profiles = loaded
            except Exception:
                self.splitter_profiles = {}
        self.commands: list[CommandResult] = []

    @staticmethod
    def _snapshot_payload(files: dict[str, str]) -> dict[str, Any]:
        return {
            "schema_version": "subagent_workspace_snapshot_v1",
            "captured_at": _utc_now(),
            "files": files,
        }

    def run_command(self, command: str, *, timeout_sec: int = 900) -> CommandResult:
        cp = subprocess.run(
            command,
            cwd=self.repo_root,
            shell=True,
            text=True,
            capture_output=True,
            timeout=timeout_sec,
            check=False,
        )
        result = CommandResult(command=command, exit_code=cp.returncode, stdout=cp.stdout, stderr=cp.stderr)
        self.commands.append(result)
        return result

    def run_command_argv(
        self,
        argv: list[str],
        *,
        timeout_sec: int = 900,
        input_text: str | None = None,
    ) -> CommandResult:
        command = " ".join(shlex.quote(x) for x in argv)
        try:
            cp = subprocess.run(
                argv,
                cwd=self.repo_root,
                text=True,
                input=input_text,
                capture_output=True,
                timeout=timeout_sec,
                check=False,
            )
            result = CommandResult(command=command, exit_code=cp.returncode, stdout=cp.stdout, stderr=cp.stderr)
        except Exception as e:
            result = CommandResult(command=command, exit_code=127, stdout="", stderr=str(e))
        self.commands.append(result)
        return result

    def load_ssot(self) -> dict[str, Any]:
        doc = yaml.safe_load(self.ssot_path.read_text(encoding="utf-8"))
        if not isinstance(doc, dict):
            raise ValueError("SSOT root must be mapping")
        return doc

    def save_ssot(self, doc: dict[str, Any]) -> None:
        text = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)
        self.ssot_path.write_text(text, encoding="utf-8")

    @staticmethod
    def parse_goals(doc: dict[str, Any]) -> list[Goal]:
        rows = doc.get("goal_checklist")
        out: list[Goal] = []
        if not isinstance(rows, list):
            return out
        for row in rows:
            if not isinstance(row, dict):
                continue
            out.append(
                Goal(
                    goal_id=str(row.get("id") or ""),
                    status_now=str(row.get("status_now") or "").strip(),
                    track=str(row.get("track") or "").strip(),
                    title=str(row.get("title") or "").strip(),
                    depends_on=[str(x) for x in (row.get("depends_on") or []) if isinstance(x, str)],
                    requirement_ids=[str(x) for x in (row.get("requirement_ids") or []) if isinstance(x, str)],
                    allowed_paths=[str(x) for x in (row.get("allowed_paths") or []) if isinstance(x, str)],
                    acceptance_commands=[
                        str(x) for x in (row.get("acceptance_commands") or row.get("acceptance", {}).get("commands") or []) if isinstance(x, str)
                    ],
                    stop_scope=row.get("stop_condition_exception_scope")
                    if isinstance(row.get("stop_condition_exception_scope"), dict)
                    else {},
                    phase_doc_path=str(row.get("phase_doc_path") or ""),
                    capability_cluster_id=str(row.get("capability_cluster_id") or ""),
                    required_skills=[str(x) for x in (row.get("required_skills") or []) if isinstance(x, str)],
                    difficulty_score=int(row.get("difficulty_score") or 0)
                    if str(row.get("difficulty_score") or "").strip().lstrip("-").isdigit()
                    else 0,
                    reasoning_tier=str(row.get("reasoning_tier") or "").strip(),
                    todo_checklist=[str(x) for x in (row.get("todo_checklist") or []) if isinstance(x, str)],
                    risk_notes=[str(x) for x in (row.get("risk_notes") or []) if isinstance(x, str)],
                    parallel_hints=[str(x) for x in (row.get("parallel_hints") or []) if isinstance(x, str)],
                    todo_planner=row.get("todo_planner") if isinstance(row.get("todo_planner"), dict) else {},
                    allow_noop=bool(row.get("allow_noop", False)),
                    raw=row,
                )
            )
        return out

    @staticmethod
    def parse_requirements(doc: dict[str, Any]) -> list[Requirement]:
        rows = doc.get("requirements_trace_v1")
        out: list[Requirement] = []
        if not isinstance(rows, list):
            return out
        for row in rows:
            if not isinstance(row, dict):
                continue
            out.append(
                Requirement(
                    req_id=str(row.get("req_id") or ""),
                    source_document=str(row.get("source_document") or ""),
                    source_line=int(row.get("source_line") or 0),
                    owner_track=WholeViewAutopilot._normalize_owner_track(
                        source_document=str(row.get("source_document") or ""),
                        owner_track=str(row.get("owner_track") or ""),
                        req_id=str(row.get("req_id") or ""),
                    ),
                    clause=str(row.get("clause") or ""),
                    depends_on_req_ids=[str(x) for x in (row.get("depends_on_req_ids") or []) if isinstance(x, str)],
                    status_now=str(row.get("status_now") or ""),
                    mapped_goal_ids=[str(x) for x in (row.get("mapped_goal_ids") or []) if isinstance(x, str)],
                    acceptance_commands=[str(x) for x in (row.get("acceptance_commands") or []) if isinstance(x, str)],
                    acceptance_verified=bool(row.get("acceptance_verified", str(row.get("status_now") or "") == "implemented")),
                    capability_cluster_id=str(row.get("capability_cluster_id") or ""),
                    raw=row,
                )
            )
        return out

    @staticmethod
    def _normalize_owner_track(*, source_document: str, owner_track: str, req_id: str) -> str:
        track = str(owner_track or "").strip()
        if track in {"skeleton", *IMPLEMENT_TRACKS}:
            return track
        req = str(req_id or "").strip().upper()
        if req.startswith("QF-"):
            return "impl_fetchdata"
        if req.startswith("WB-"):
            return "impl_workbench"
        if req.startswith("WV-"):
            return "skeleton"
        src = str(source_document or "").lower()
        if "workbench_ui_productization" in src:
            return "impl_workbench"
        if "qa_fetch" in src or "/05_data_plane/" in src:
            return "impl_fetchdata"
        return "skeleton"

    def _build_requirements_trace(self, doc: dict[str, Any], goals: list[Goal]) -> list[dict[str, Any]]:
        existing_rows = doc.get("requirements_trace_v1") if isinstance(doc.get("requirements_trace_v1"), list) else []
        existing_by_id = {
            str(row.get("req_id") or ""): row
            for row in existing_rows
            if isinstance(row, dict) and str(row.get("req_id") or "").strip()
        }
        required_from_docs: list[dict[str, Any]] = []
        for prefix, _candidates in REQ_SOURCE_CANDIDATES:
            source_rows = _parse_markdown_clauses(
                _requirement_doc_path(prefix),
                prefix,
                splitter_profiles=self.splitter_profiles,
            )
            for row in source_rows:
                row["owner_track"] = REQ_PREFIX_OWNER_TRACK.get(prefix, "skeleton")
            required_from_docs.extend(source_rows)
        parsed_source_docs = {str(x.get("source_document") or "") for x in required_from_docs if isinstance(x, dict)}
        parsed_prefixes = set(REQ_PREFIX_OWNER_TRACK.keys())
        compact_existing_rows = bool(self.splitter_profiles)

        merged: list[dict[str, Any]] = []
        seen_req_ids: set[str] = set()
        for base in required_from_docs:
            req_id = str(base.get("req_id") or "").strip()
            if not req_id:
                continue
            old = existing_by_id.get(req_id, {})
            # Parsed source requirements never inherit heuristic mapping by default.
            # Only explicit goal.requirement_ids linkage participates in implementation state.
            old_mapped: list[str] = [str(x) for x in (old.get("mapped_goal_ids") or []) if isinstance(x, str)] if bool(old.get("mapping_explicit", False)) else []
            row = {
                "req_id": req_id,
                "source_document": str(base.get("source_document") or old.get("source_document") or ""),
                "source_line": int(base.get("source_line") or old.get("source_line") or 0),
                "owner_track": self._normalize_owner_track(
                    source_document=str(base.get("source_document") or old.get("source_document") or ""),
                    owner_track=str(old.get("owner_track") or base.get("owner_track") or ""),
                    req_id=req_id,
                ),
                "clause": str(base.get("clause") or old.get("clause") or ""),
                "depends_on_req_ids": [str(x) for x in (base.get("depends_on_req_ids") or old.get("depends_on_req_ids") or []) if isinstance(x, str)],
                "status_now": str(old.get("status_now") or "planned"),
                "mapped_goal_ids": old_mapped,
                "acceptance_commands": [str(x) for x in (old.get("acceptance_commands") or []) if isinstance(x, str)],
                "acceptance_verified": bool(old.get("acceptance_verified", False)),
                "capability_cluster_id": str(old.get("capability_cluster_id") or ""),
            }
            merged.append(row)
            seen_req_ids.add(req_id)

        # Preserve manually maintained requirement rows outside the parsed requirement docs.
        for row in existing_rows:
            if not isinstance(row, dict):
                continue
            req_id = str(row.get("req_id") or "").strip()
            if not req_id or req_id in seen_req_ids:
                continue
            source_document = str(row.get("source_document") or "").strip()
            req_prefix = req_id.split("-", 1)[0] if "-" in req_id else ""
            if compact_existing_rows and (source_document in parsed_source_docs or req_prefix in parsed_prefixes):
                continue
            merged.append(
                {
                    "req_id": req_id,
                    "source_document": str(row.get("source_document") or ""),
                    "source_line": int(row.get("source_line") or 0),
                    "owner_track": self._normalize_owner_track(
                        source_document=str(row.get("source_document") or ""),
                        owner_track=str(row.get("owner_track") or ""),
                        req_id=req_id,
                    ),
                    "clause": str(row.get("clause") or ""),
                    "depends_on_req_ids": [str(x) for x in (row.get("depends_on_req_ids") or []) if isinstance(x, str)],
                    "status_now": str(row.get("status_now") or "planned"),
                    "mapped_goal_ids": [str(x) for x in (row.get("mapped_goal_ids") or []) if isinstance(x, str)],
                    "acceptance_commands": [str(x) for x in (row.get("acceptance_commands") or []) if isinstance(x, str)],
                    "acceptance_verified": bool(
                        row.get("acceptance_verified", str(row.get("status_now") or "") == "implemented")
                    ),
                    "capability_cluster_id": str(row.get("capability_cluster_id") or ""),
                }
            )

        goals_by_id = {g.goal_id: g for g in goals}
        explicit_map: dict[str, list[str]] = defaultdict(list)
        for g in goals:
            for req_id in g.requirement_ids:
                explicit_map[req_id].append(g.goal_id)

        for row in merged:
            req_id = str(row.get("req_id") or "")
            current = [str(x) for x in (row.get("mapped_goal_ids") or []) if isinstance(x, str)]
            merged_goal_ids = sorted(set(current + explicit_map.get(req_id, [])), key=_goal_num)
            row["mapped_goal_ids"] = merged_goal_ids
            acceptance_verified = bool(row.get("acceptance_verified", False))
            if merged_goal_ids:
                goals_done = all(goals_by_id.get(gid) and goals_by_id[gid].status_now == "implemented" for gid in merged_goal_ids)
                row["status_now"] = "implemented" if (goals_done and acceptance_verified) else "planned"
            else:
                row["status_now"] = "implemented" if (acceptance_verified and str(row.get("status_now") or "") == "implemented") else "planned"

        return merged

    @staticmethod
    def _cluster_goals(goals: list[Goal]) -> tuple[dict[str, str], list[dict[str, Any]]]:
        goal_to_cluster: dict[str, str] = {}
        clusters: dict[str, dict[str, Any]] = {}

        skeleton = sorted([g for g in goals if g.track == "skeleton"], key=lambda x: _goal_num(x.goal_id))
        impl = sorted([g for g in goals if g.track in IMPLEMENT_TRACKS], key=lambda x: _goal_num(x.goal_id))
        skeleton_ids = {g.goal_id for g in skeleton}

        for impl_goal in impl:
            dep_skeleton = [x for x in impl_goal.depends_on if x in skeleton_ids]
            if dep_skeleton:
                skel_id = dep_skeleton[0]
            elif skeleton:
                impl_num = _goal_num(impl_goal.goal_id)
                skel_id = min(skeleton, key=lambda s: abs(_goal_num(s.goal_id) - impl_num)).goal_id
            else:
                skel_id = ""
            cid = f"CL_FETCH_{_goal_num(impl_goal.goal_id):03d}"
            cluster = clusters.setdefault(
                cid,
                {
                    "cluster_id": cid,
                    "title": f"Fetch capability cluster for {impl_goal.goal_id}",
                    "status_now": "planned",
                    "goal_ids": [],
                    "requirement_ids": [],
                    "latest_phase_id": impl_goal.goal_id,
                    "acceptance_commands": [],
                    "required_tests": [],
                    "notes": ["auto-clustered from goal dependency graph"],
                },
            )
            if skel_id:
                cluster["goal_ids"].append(skel_id)
            cluster["goal_ids"].append(impl_goal.goal_id)
            cluster["acceptance_commands"].extend(impl_goal.acceptance_commands)
            goal_to_cluster[impl_goal.goal_id] = cid
            if skel_id and skel_id not in goal_to_cluster:
                goal_to_cluster[skel_id] = cid

        # Keep every goal addressable by capability cluster id.
        legacy_cluster_id = "CL_LEGACY_CORE"
        if goals:
            legacy = clusters.setdefault(
                legacy_cluster_id,
                {
                    "cluster_id": legacy_cluster_id,
                    "title": "Legacy/core goal cluster",
                    "status_now": "planned",
                    "goal_ids": [],
                    "requirement_ids": [],
                    "latest_phase_id": "",
                    "acceptance_commands": ["python3 scripts/check_docs_tree.py"],
                    "required_tests": [],
                    "notes": ["covers goals not auto-paired by fetch track"],
                },
            )
            for g in goals:
                if g.goal_id not in goal_to_cluster:
                    goal_to_cluster[g.goal_id] = legacy_cluster_id
                legacy["goal_ids"].append(g.goal_id)

        for cid, row in clusters.items():
            row["goal_ids"] = sorted(set(row["goal_ids"]), key=_goal_num)
            if row["goal_ids"]:
                row["latest_phase_id"] = max(row["goal_ids"], key=_goal_num)
            row["acceptance_commands"] = sorted(set([str(x) for x in row["acceptance_commands"] if str(x).strip()]))
            if cid == legacy_cluster_id and not row["acceptance_commands"]:
                row["acceptance_commands"] = ["python3 scripts/check_docs_tree.py"]

        cluster_rows = sorted(clusters.values(), key=lambda x: str(x.get("cluster_id", "")))
        return goal_to_cluster, cluster_rows

    @staticmethod
    def _apply_goal_cluster_backfill(doc: dict[str, Any], goal_to_cluster: dict[str, str]) -> None:
        rows = doc.get("goal_checklist")
        if not isinstance(rows, list):
            return
        for row in rows:
            if not isinstance(row, dict):
                continue
            gid = str(row.get("id") or "")
            row["capability_cluster_id"] = goal_to_cluster.get(gid, "CL_LEGACY_CORE")

    @staticmethod
    def _apply_requirements_cluster_backfill(
        requirements: list[dict[str, Any]],
        goal_to_cluster: dict[str, str],
    ) -> None:
        for req in requirements:
            mapped = [str(x) for x in (req.get("mapped_goal_ids") or []) if isinstance(x, str)]
            clusters = [goal_to_cluster.get(gid, "") for gid in mapped if goal_to_cluster.get(gid)]
            if clusters:
                req["capability_cluster_id"] = Counter(clusters).most_common(1)[0][0]
            else:
                req["capability_cluster_id"] = "CL_LEGACY_CORE"

    @staticmethod
    def _populate_cluster_rows(
        cluster_rows: list[dict[str, Any]],
        *,
        requirements: list[dict[str, Any]],
        goals: list[Goal],
    ) -> None:
        req_by_cluster: dict[str, list[str]] = defaultdict(list)
        for req in requirements:
            cid = str(req.get("capability_cluster_id") or "")
            rid = str(req.get("req_id") or "")
            if cid and rid:
                req_by_cluster[cid].append(rid)

        goal_by_id = {g.goal_id: g for g in goals}
        for row in cluster_rows:
            cid = str(row.get("cluster_id") or "")
            row["requirement_ids"] = sorted(set(req_by_cluster.get(cid, [])))
            goal_ids = [str(x) for x in (row.get("goal_ids") or []) if isinstance(x, str)]
            g_status = [goal_by_id.get(gid).status_now for gid in goal_ids if goal_by_id.get(gid)]
            req_rows = [r for r in requirements if r.get("req_id") in set(row["requirement_ids"])]
            req_status = [str(r.get("status_now") or "") for r in req_rows]
            if goal_ids and g_status and all(x == "implemented" for x in g_status) and (
                not req_rows or all(x == "implemented" for x in req_status)
            ):
                row["status_now"] = "implemented"
            elif any(x == "implemented" for x in g_status + req_status):
                row["status_now"] = "partial"
            else:
                row["status_now"] = "planned"

            # Lightweight default test targets.
            if not row.get("required_tests"):
                cluster_tracks = {
                    str(goal_by_id.get(gid).track or "")
                    for gid in goal_ids
                    if goal_by_id.get(gid)
                }
                if "impl_workbench" in cluster_tracks:
                    row["required_tests"] = [
                        "python3 -m pytest -q tests/test_ui_mvp.py",
                    ]
                else:
                    row["required_tests"] = [
                        "python3 -m pytest -q tests/test_fetch_contracts_phase77.py",
                        "python3 -m pytest -q tests/test_qa_fetch_runtime.py",
                    ]

    def migrate_ssot(self, doc: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        goal_rows = doc.get("goal_checklist") if isinstance(doc.get("goal_checklist"), list) else []
        normalized_goal_rows: list[dict[str, Any]] = []
        archived_legacy: list[dict[str, Any]] = []
        for row in goal_rows:
            if not isinstance(row, dict):
                continue
            gid = str(row.get("id") or "").strip()
            track = str(row.get("track") or "").strip()
            phase_doc = str(row.get("phase_doc_path") or "").strip()
            if track not in ALL_TRACKS or not phase_doc:
                archived = dict(row)
                archived["archived_at"] = _utc_now()
                archived["archived_reason"] = "missing_or_invalid_track_or_phase_doc_path"
                archived_legacy.append(archived)
                continue
            row["depends_on"] = [str(x) for x in (row.get("depends_on") or []) if isinstance(x, str)]
            row["requirement_ids"] = [str(x) for x in (row.get("requirement_ids") or []) if isinstance(x, str)]
            row["allowed_paths"] = [str(x) for x in (row.get("allowed_paths") or []) if isinstance(x, str)]
            acc = row.get("acceptance_commands")
            if not isinstance(acc, list):
                acc = (row.get("acceptance") or {}).get("commands") if isinstance(row.get("acceptance"), dict) else []
            row["acceptance_commands"] = [str(x) for x in (acc or []) if isinstance(x, str)]
            row["phase_doc_path"] = phase_doc
            row["track"] = track
            row["required_skills"] = [str(x) for x in (row.get("required_skills") or []) if isinstance(x, str)]
            row["difficulty_score"] = (
                int(row.get("difficulty_score") or 0)
                if str(row.get("difficulty_score") or "").strip().lstrip("-").isdigit()
                else 0
            )
            row["reasoning_tier"] = self._normalize_reasoning_tier(str(row.get("reasoning_tier") or ""))
            row["todo_checklist"] = [str(x) for x in (row.get("todo_checklist") or []) if isinstance(x, str)]
            row["risk_notes"] = [str(x) for x in (row.get("risk_notes") or []) if isinstance(x, str)]
            row["parallel_hints"] = [str(x) for x in (row.get("parallel_hints") or []) if isinstance(x, str)]
            row["todo_planner"] = row.get("todo_planner") if isinstance(row.get("todo_planner"), dict) else {}
            if gid:
                normalized_goal_rows.append(row)
        self._apply_goal_skill_reasoning_fields(doc, normalized_goal_rows)
        doc["goal_checklist"] = normalized_goal_rows
        if archived_legacy:
            legacy_rows = doc.get("legacy_goals_v1") if isinstance(doc.get("legacy_goals_v1"), list) else []
            known = {
                (str(x.get("id") or ""), str(x.get("phase_doc_path") or ""))
                for x in legacy_rows
                if isinstance(x, dict)
            }
            for row in archived_legacy:
                k = (str(row.get("id") or ""), str(row.get("phase_doc_path") or ""))
                if k in known:
                    continue
                known.add(k)
                legacy_rows.append(row)
            doc["legacy_goals_v1"] = legacy_rows

        goals = self.parse_goals(doc)
        requirements = self._build_requirements_trace(doc, goals)

        # Backfill missing goal.requirement_ids from explicit requirement->goal links.
        req_to_goals: dict[str, list[str]] = defaultdict(list)
        for req in requirements:
            rid = str(req.get("req_id") or "")
            for gid in [str(x) for x in (req.get("mapped_goal_ids") or []) if isinstance(x, str)]:
                req_to_goals[gid].append(rid)
        for row in normalized_goal_rows:
            if row.get("requirement_ids"):
                continue
            gid = str(row.get("id") or "")
            backfill = sorted(set(req_to_goals.get(gid, [])))
            if backfill:
                row["requirement_ids"] = backfill
        doc["goal_checklist"] = normalized_goal_rows

        goals = self.parse_goals(doc)
        requirements = self._build_requirements_trace(doc, goals)
        doc["requirements_trace_v1"] = requirements
        req_rows = self.parse_requirements(doc)
        req_lookup = {r.req_id: r for r in req_rows if r.req_id}
        self._backfill_goal_todo_plans(doc=doc, goal_rows=normalized_goal_rows, req_by_id=req_lookup)
        doc["goal_checklist"] = normalized_goal_rows
        goals = self.parse_goals(doc)
        requirements = self._build_requirements_trace(doc, goals)
        req_by_id = {str(r.get("req_id") or ""): r for r in requirements if isinstance(r, dict)}

        interface_contract_map: dict[tuple[str, str], dict[str, Any]] = {}
        for req in requirements:
            if not isinstance(req, dict):
                continue
            impl_req_id = str(req.get("req_id") or "")
            if str(req.get("owner_track") or "") not in IMPLEMENT_TRACKS:
                continue
            dep_req_ids = [str(x) for x in (req.get("depends_on_req_ids") or []) if isinstance(x, str)]
            for skeleton_req_id in dep_req_ids:
                dep_req = req_by_id.get(skeleton_req_id)
                if not dep_req or str(dep_req.get("owner_track") or "") != "skeleton":
                    continue
                contract_id = (
                    "IFC-"
                    + re.sub(r"[^A-Za-z0-9]+", "_", skeleton_req_id).strip("_")
                    + "-"
                    + re.sub(r"[^A-Za-z0-9]+", "_", impl_req_id).strip("_")
                )
                skeleton_goal_ids = sorted(
                    set([str(x) for x in (dep_req.get("mapped_goal_ids") or []) if isinstance(x, str)]),
                    key=_goal_num,
                )
                impl_goal_ids = sorted(
                    set([str(x) for x in (req.get("mapped_goal_ids") or []) if isinstance(x, str)]),
                    key=_goal_num,
                )
                interface_contract_map[(skeleton_req_id, impl_req_id)] = {
                    "contract_id": contract_id,
                    "skeleton_requirement_id": skeleton_req_id,
                    "impl_requirement_id": impl_req_id,
                    "skeleton_goal_ids": skeleton_goal_ids,
                    "impl_goal_ids": impl_goal_ids,
                    "status_now": "implemented"
                    if str(dep_req.get("status_now") or "") == "implemented"
                    and str(req.get("status_now") or "") == "implemented"
                    else "planned",
                }

        # Fallback: derive interface contracts from goal dependencies when requirement-level depends_on is missing.
        goals_by_id = {g.goal_id: g for g in goals}
        for impl_goal in goals:
            if impl_goal.track not in IMPLEMENT_TRACKS:
                continue
            for dep_gid in impl_goal.depends_on:
                skel_goal = goals_by_id.get(dep_gid)
                if not skel_goal or skel_goal.track != "skeleton":
                    continue
                for skel_req_id in skel_goal.requirement_ids:
                    for impl_req_id in impl_goal.requirement_ids:
                        contract_id = (
                            "IFC-"
                            + re.sub(r"[^A-Za-z0-9]+", "_", skel_req_id).strip("_")
                            + "-"
                            + re.sub(r"[^A-Za-z0-9]+", "_", impl_req_id).strip("_")
                        )
                        dep_req = req_by_id.get(skel_req_id, {})
                        impl_req = req_by_id.get(impl_req_id, {})
                        existing = interface_contract_map.get((skel_req_id, impl_req_id))
                        skel_goal_ids = sorted(
                            set((existing or {}).get("skeleton_goal_ids", []) + [skel_goal.goal_id]),
                            key=_goal_num,
                        )
                        impl_goal_ids = sorted(
                            set((existing or {}).get("impl_goal_ids", []) + [impl_goal.goal_id]),
                            key=_goal_num,
                        )
                        interface_contract_map[(skel_req_id, impl_req_id)] = {
                            "contract_id": contract_id,
                            "skeleton_requirement_id": skel_req_id,
                            "impl_requirement_id": impl_req_id,
                            "skeleton_goal_ids": skel_goal_ids,
                            "impl_goal_ids": impl_goal_ids,
                            "status_now": "implemented"
                            if str(dep_req.get("status_now") or "") == "implemented"
                            and str(impl_req.get("status_now") or "") == "implemented"
                            else "planned",
                        }

        interface_contracts = sorted(interface_contract_map.values(), key=lambda x: str(x.get("contract_id") or ""))
        doc["interface_contracts_v1"] = interface_contracts

        # Enforce impl goal depends_on to include interface skeleton goal dependencies.
        interface_skeleton_by_impl_req: dict[str, list[str]] = defaultdict(list)
        for c in interface_contracts:
            if not isinstance(c, dict):
                continue
            impl_req_id = str(c.get("impl_requirement_id") or "")
            skeleton_goal_ids = [str(x) for x in (c.get("skeleton_goal_ids") or []) if isinstance(x, str)]
            interface_skeleton_by_impl_req[impl_req_id].extend(skeleton_goal_ids)
        for row in normalized_goal_rows:
            if str(row.get("track") or "") not in IMPLEMENT_TRACKS:
                continue
            req_ids = [str(x) for x in (row.get("requirement_ids") or []) if isinstance(x, str)]
            required_deps = sorted(
                set([gid for rid in req_ids for gid in interface_skeleton_by_impl_req.get(rid, [])]),
                key=_goal_num,
            )
            if not required_deps:
                continue
            deps = [str(x) for x in (row.get("depends_on") or []) if isinstance(x, str)]
            row["depends_on"] = sorted(set(deps + required_deps), key=_goal_num)
        self._apply_goal_skill_reasoning_fields(doc, normalized_goal_rows)
        doc["goal_checklist"] = normalized_goal_rows

        goals = self.parse_goals(doc)
        requirements = self._build_requirements_trace(doc, goals)
        goal_to_cluster, cluster_rows = self._cluster_goals(goals)
        self._apply_goal_cluster_backfill(doc, goal_to_cluster)
        self._apply_requirements_cluster_backfill(requirements, goal_to_cluster)
        self._populate_cluster_rows(cluster_rows, requirements=requirements, goals=goals)

        doc["requirements_trace_v1"] = requirements
        doc["capability_clusters_v1"] = cluster_rows

        policy = doc.get("milestone_policy_v1")
        if not isinstance(policy, dict):
            policy = {}
        policy.update(
            {
                "status_now": "active",
                "dependency_granularity": "requirement_clause_dag",
                "scheduler_policy": "critical_path_first",
                "parallel_limit": min(self.max_parallel, 2),
                "waiver_policy": "minimal",
                "milestone_trigger": "capability_cluster_completed",
                "retry_blocked_clusters": bool(policy.get("retry_blocked_clusters", False)),
                "strict_gate": {
                    "required_commands": [
                        "python3 scripts/check_docs_tree.py",
                        "python3 scripts/check_subagent_packet.py --phase-id <latest_phase_id>",
                    ],
                    "redlines": [
                        "contracts/**",
                        "policies/**",
                        "Holdout visibility expansion",
                    ],
                    "dirty_workspace_isolation": "whitelist_only",
                },
                "push_policy": {
                    "preferred": "origin/master",
                    "fallback_branch_prefix": "autopilot/milestone-",
                    "on_master_reject": "fallback_branch",
                },
                "commit_policy": {
                    "message_format": "milestone(<cluster_id>): <capability_summary>",
                    "body_required_fields": [
                        "Goals",
                        "Requirements",
                        "Acceptance",
                        "Packet",
                    ],
                    "path_stage_mode": "explicit_path_add_only",
                },
                "done_criteria": {
                    "goal_checklist_all_implemented": True,
                    "requirements_trace_all_implemented": True,
                    "capability_clusters_all_implemented": True,
                },
                "blocked_conditions": [
                    "milestone_gate_failed_retry_exhausted",
                    "push_master_and_fallback_failed",
                ],
            }
        )
        doc["milestone_policy_v1"] = policy
        existing_planning_policy = (
            doc.get("planning_policy_v2")
            if isinstance(doc.get("planning_policy_v2"), dict)
            else {}
        )
        bundle_policy = (
            existing_planning_policy.get("goal_bundle_policy")
            if isinstance(existing_planning_policy.get("goal_bundle_policy"), dict)
            else {}
        )
        track_overrides_raw = bundle_policy.get("track_overrides") if isinstance(bundle_policy.get("track_overrides"), dict) else {}
        track_overrides: dict[str, dict[str, Any]] = {}
        for track in ("skeleton", *sorted(IMPLEMENT_TRACKS)):
            tr = track_overrides_raw.get(track) if isinstance(track_overrides_raw.get(track), dict) else {}
            if not tr and track == "skeleton":
                continue
            track_overrides[track] = {
                "max_requirements_per_goal": max(1, int(tr.get("max_requirements_per_goal", 4))),
                "minimum_bundle_size": max(1, int(tr.get("minimum_bundle_size", 2))),
                "source_line_window": max(0, int(tr.get("source_line_window", 6))),
                "require_same_source_document": bool(tr.get("require_same_source_document", True)),
                "require_same_parent_requirement": bool(tr.get("require_same_parent_requirement", True)),
                "require_exact_parent_signature": bool(tr.get("require_exact_parent_signature", track in IMPLEMENT_TRACKS)),
            }
        if "impl_fetchdata" not in track_overrides:
            track_overrides["impl_fetchdata"] = {
                "max_requirements_per_goal": 4,
                "minimum_bundle_size": 3,
                "source_line_window": 10,
                "require_same_source_document": True,
                "require_same_parent_requirement": True,
                "require_exact_parent_signature": True,
            }
        if "impl_workbench" not in track_overrides:
            track_overrides["impl_workbench"] = {
                "max_requirements_per_goal": 4,
                "minimum_bundle_size": 3,
                "source_line_window": 10,
                "require_same_source_document": True,
                "require_same_parent_requirement": True,
                "require_exact_parent_signature": True,
            }

        bundle_policy = {
            "enabled": bool(bundle_policy.get("enabled", True)),
            "max_requirements_per_goal": max(1, int(bundle_policy.get("max_requirements_per_goal", 4))),
            "minimum_bundle_size": max(1, int(bundle_policy.get("minimum_bundle_size", 2))),
            "source_line_window": max(0, int(bundle_policy.get("source_line_window", 6))),
            "require_same_source_document": bool(bundle_policy.get("require_same_source_document", True)),
            "require_same_parent_requirement": bool(bundle_policy.get("require_same_parent_requirement", True)),
            "require_exact_parent_signature": bool(bundle_policy.get("require_exact_parent_signature", False)),
            "track_overrides": track_overrides,
            "notes": (
                "Bundle unmet requirements into one goal when same track + same parent requirement "
                "+ same source document + source-line neighborhood are satisfied."
            ),
        }
        todo_planner = (
            existing_planning_policy.get("goal_todo_planner_v1")
            if isinstance(existing_planning_policy.get("goal_todo_planner_v1"), dict)
            else {}
        )
        todo_planner = {
            "status_now": "active",
            "enabled": bool(todo_planner.get("enabled", True)),
            "mode": str(todo_planner.get("mode") or "codex_assisted"),
            "codex_timeout_sec": max(60, int(todo_planner.get("codex_timeout_sec", 240))),
            "max_items_per_section": max(3, int(todo_planner.get("max_items_per_section", 6))),
            "fallback_mode": str(todo_planner.get("fallback_mode") or "rule_only"),
            "require_codex_for_planning": bool(todo_planner.get("require_codex_for_planning", False)),
        }
        architect_preplan = (
            existing_planning_policy.get("architect_preplan_v1")
            if isinstance(existing_planning_policy.get("architect_preplan_v1"), dict)
            else {}
        )
        architect_source_docs = [str(x) for x in (architect_preplan.get("source_documents") or []) if isinstance(x, str)]
        default_architect_source_docs = [
            _path_str_for_doc(_requirement_doc_path(prefix), repo_root=self.repo_root)
            for prefix, _ in REQ_SOURCE_CANDIDATES
        ]
        for doc_path in default_architect_source_docs:
            if doc_path not in architect_source_docs:
                architect_source_docs.append(doc_path)
        architect_preplan = {
            "status_now": "active",
            "enabled": bool(architect_preplan.get("enabled", True)),
            "mode": str(architect_preplan.get("mode") or "codex_assisted"),
            "codex_timeout_sec": max(60, int(architect_preplan.get("codex_timeout_sec", 300))),
            "max_requirements": max(20, int(architect_preplan.get("max_requirements", 120))),
            "max_goal_candidates": max(10, int(architect_preplan.get("max_goal_candidates", 80))),
            "require_codex_for_preplan": bool(architect_preplan.get("require_codex_for_preplan", False)),
            "enforce_before_goal_generation": bool(architect_preplan.get("enforce_before_goal_generation", True)),
            "cache_by_signature": bool(architect_preplan.get("cache_by_signature", True)),
            "source_documents": architect_source_docs,
            "latest_plan": architect_preplan.get("latest_plan")
            if isinstance(architect_preplan.get("latest_plan"), dict)
            else {},
        }
        existing_planning_policy.update(
            {
                "status_now": "active",
                "generation_mode": "requirement_gap_only",
                "disable_template_goal_generation": True,
                "interface_first_dependency_gate": True,
                "goal_source": "requirements_trace_v1",
                "goal_bundle_policy": bundle_policy,
                "goal_todo_planner_v1": todo_planner,
                "architect_preplan_v1": architect_preplan,
            }
        )
        doc["planning_policy_v2"] = existing_planning_policy
        existing_skill_registry = (
            doc.get("skill_registry_v1")
            if isinstance(doc.get("skill_registry_v1"), dict)
            else {}
        )
        registry_rows = (
            existing_skill_registry.get("skills")
            if isinstance(existing_skill_registry.get("skills"), list)
            else []
        )
        registry_map: dict[str, dict[str, Any]] = {}
        for row in registry_rows:
            if not isinstance(row, dict):
                continue
            sid = str(row.get("id") or "").strip()
            if sid:
                registry_map[sid] = dict(row)
        for sid, spath in DEFAULT_SKILL_REGISTRY.items():
            row = registry_map.setdefault(sid, {})
            row["id"] = sid
            row["path"] = str(row.get("path") or spath)
            row["status_now"] = str(row.get("status_now") or "active")
        if self.external_skill_registry:
            for sid, spath in self.external_skill_registry.items():
                row = registry_map.setdefault(sid, {})
                row["id"] = sid
                row["path"] = spath
                row["status_now"] = str(row.get("status_now") or "active")
        doc["skill_registry_v1"] = {
            "status_now": "active",
            "skills": [registry_map[k] for k in sorted(registry_map.keys())],
        }

        existing_binding = (
            doc.get("skill_binding_policy_v1")
            if isinstance(doc.get("skill_binding_policy_v1"), dict)
            else {}
        )
        track_required = (
            existing_binding.get("track_required_skills")
            if isinstance(existing_binding.get("track_required_skills"), dict)
            else {}
        )
        for track, defaults in DEFAULT_TRACK_SKILLS.items():
            rows = [str(x) for x in (track_required.get(track) or []) if isinstance(x, str)]
            track_required[track] = rows or list(defaults)
        existing_binding.update(
            {
                "status_now": "active",
                "track_required_skills": track_required,
                "milestone_required_skills": ["milestone-gate"],
                "controller_preplan_skills": [
                    "architect-planner",
                    "requirement-splitter",
                    "ssot-goal-planner",
                ],
            }
        )
        doc["skill_binding_policy_v1"] = existing_binding

        existing_enforcement = (
            doc.get("skill_enforcement_v1")
            if isinstance(doc.get("skill_enforcement_v1"), dict)
            else {}
        )
        existing_enforcement["status_now"] = "active"
        existing_enforcement["mode"] = self._skill_enforcement_from_doc(doc)
        existing_enforcement["apply_to_new_goals_only"] = bool(
            existing_enforcement.get("apply_to_new_goals_only", True)
        )
        existing_enforcement["enforce_from_goal_id"] = str(existing_enforcement.get("enforce_from_goal_id") or "")
        doc["skill_enforcement_v1"] = existing_enforcement

        existing_difficulty = (
            doc.get("difficulty_scoring_v1")
            if isinstance(doc.get("difficulty_scoring_v1"), dict)
            else {}
        )
        existing_difficulty.update(
            {
                "status_now": "active",
                "formula": "dependency_depth + path_complexity + acceptance_cost + redline_proximity + history_instability",
                "weights": self._difficulty_weights_from_doc(doc),
                "score_range": [0, 100],
            }
        )
        doc["difficulty_scoring_v1"] = existing_difficulty

        existing_tiers = (
            doc.get("reasoning_tiers_v1")
            if isinstance(doc.get("reasoning_tiers_v1"), dict)
            else {}
        )
        existing_tiers.update(
            {
                "status_now": "active",
                "default_tier": "medium",
                "thresholds": self._reasoning_thresholds_from_doc(doc),
                "tiers": self._reasoning_tiers_from_doc(doc),
            }
        )
        doc["reasoning_tiers_v1"] = existing_tiers

        splitter_policy = (
            doc.get("requirement_splitter_v1") if isinstance(doc.get("requirement_splitter_v1"), dict) else {}
        )
        splitter_policy["status_now"] = "active"
        splitter_policy["mode"] = "compressed"
        splitter_policy["config_path"] = self.splitter_config_path.relative_to(self.repo_root).as_posix()
        splitter_policy["applies_to_prefixes"] = sorted(REQ_PREFIX_OWNER_TRACK.keys())
        splitter_policy["dedup"] = True
        splitter_policy["notes"] = (
            "Extract requirement-dense headings/bullets only; skip narrative sections to avoid over-splitting."
        )
        doc["requirement_splitter_v1"] = splitter_policy

        if not isinstance(doc.get("milestone_history_v1"), list):
            doc["milestone_history_v1"] = []

        whole_view = doc.get("whole_view_autopilot_v1")
        if isinstance(whole_view, dict):
            done_criteria = whole_view.get("done_criteria") if isinstance(whole_view.get("done_criteria"), dict) else {}
            done_criteria["requirements_trace_all_implemented"] = True
            done_criteria["capability_clusters_all_implemented"] = True
            whole_view["done_criteria"] = done_criteria

            rolling = whole_view.get("rolling_goal_policy") if isinstance(whole_view.get("rolling_goal_policy"), dict) else {}
            rolling["enabled"] = bool(rolling.get("enabled", True))
            rolling["trigger_when_no_planned_or_partial"] = bool(rolling.get("trigger_when_no_planned_or_partial", True))
            rolling["must_generate_before_done_check_when_queue_empty"] = False
            rolling["queue_empty_generation_protocol_ref"] = "docs/12_workflows/whole_view_autopilot_queue_empty_protocol_v1.md"
            rolling["generation_mode"] = "requirement_gap_only"
            source_docs = [str(x) for x in (rolling.get("source_documents") or []) if isinstance(x, str)]
            required_source_docs = [
                "Quant‑EAM Whole View Framework.md（v0.5‑draft）.md",
                "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md",
                "docs/00_overview/workbench_ui_productization_v1.md",
            ]
            for doc_path in required_source_docs:
                if doc_path not in source_docs:
                    source_docs.append(doc_path)
            rolling["source_documents"] = source_docs
            whole_view["rolling_goal_policy"] = rolling

        queue_proto = (
            doc.get("queue_empty_generation_protocol_v1")
            if isinstance(doc.get("queue_empty_generation_protocol_v1"), dict)
            else {}
        )
        queue_proto.setdefault("status_now", "active")
        queue_proto["enabled"] = False
        queue_proto.setdefault("trigger_when_goal_queue_empty", True)
        queue_proto["allow_generate_after_done"] = False
        queue_proto["generation_mode"] = "requirement_gap_only"
        queue_proto["done_guard_rule"] = "when enabled, generate only from non-implemented requirements"
        queue_proto["protocol_ref"] = "docs/12_workflows/whole_view_autopilot_queue_empty_protocol_v1.md"
        doc["queue_empty_generation_protocol_v1"] = queue_proto

        preview = {
            "requirements_total": len(requirements),
            "cluster_total": len(cluster_rows),
            "goals_with_cluster": len(goal_to_cluster),
            "interface_contract_total": len(interface_contracts),
        }
        return doc, preview

    @staticmethod
    def _critical_path_score(
        goal_id: str,
        successors: dict[str, list[str]],
        cache: dict[str, int],
    ) -> int:
        if goal_id in cache:
            return cache[goal_id]
        nxt = successors.get(goal_id, [])
        if not nxt:
            cache[goal_id] = 1
            return 1
        score = 1 + max(WholeViewAutopilot._critical_path_score(x, successors, cache) for x in nxt)
        cache[goal_id] = score
        return score

    def select_parallel_goals(self, doc: dict[str, Any], goals: list[Goal]) -> list[str]:
        by_id = {g.goal_id: g for g in goals}
        implemented = {g.goal_id for g in goals if g.status_now == "implemented"}
        successors: dict[str, list[str]] = defaultdict(list)
        for g in goals:
            for dep in g.depends_on:
                successors[dep].append(g.goal_id)

        req_by_id = {r.req_id: r for r in self.parse_requirements(doc)}
        interface_contracts = doc.get("interface_contracts_v1") if isinstance(doc.get("interface_contracts_v1"), list) else []

        def _impl_interface_ready(goal: Goal) -> bool:
            if goal.track not in IMPLEMENT_TRACKS:
                return True
            if not goal.requirement_ids:
                return False
            req_ids = set(goal.requirement_ids)
            for rid in req_ids:
                req = req_by_id.get(rid)
                if not req:
                    return False
                skel_dep_req_ids = [x for x in req.depends_on_req_ids if req_by_id.get(x) and req_by_id[x].owner_track == "skeleton"]
                if any(req_by_id[x].status_now != "implemented" for x in skel_dep_req_ids):
                    return False
            for row in interface_contracts:
                if not isinstance(row, dict):
                    continue
                impl_req = str(row.get("impl_requirement_id") or "")
                if impl_req not in req_ids:
                    continue
                skeleton_req = str(row.get("skeleton_requirement_id") or "")
                if not skeleton_req or not req_by_id.get(skeleton_req):
                    return False
                if req_by_id[skeleton_req].status_now != "implemented":
                    return False
                skel_goal_ids = [str(x) for x in (row.get("skeleton_goal_ids") or []) if isinstance(x, str)]
                if any(gid not in implemented for gid in skel_goal_ids):
                    return False
            return True

        ready = [
            g
            for g in goals
            if g.status_now in GOAL_ACTIVE_STATUS
            and all(dep in implemented for dep in g.depends_on)
            and _impl_interface_ready(g)
        ]
        cp_cache: dict[str, int] = {}
        planner_goal_priority = self._architect_goal_priority_map(doc)
        ready_sorted = sorted(
            ready,
            key=lambda g: (
                planner_goal_priority.get(g.goal_id, 10**9),
                -self._critical_path_score(g.goal_id, successors, cp_cache),
                _goal_num(g.goal_id),
            ),
        )

        selected: list[str] = []
        selected_paths: list[list[str]] = []
        for g in ready_sorted:
            if len(selected) >= self.max_parallel:
                break
            if not g.allowed_paths:
                continue
            scope_paths = _parallel_scope_paths(g.allowed_paths) or g.allowed_paths
            if any(_path_rules_conflict(scope_paths, p) for p in selected_paths):
                continue
            selected.append(g.goal_id)
            selected_paths.append(scope_paths)

        # fallback: allow serial if no disjoint pair exists.
        if not selected and ready_sorted:
            selected = [ready_sorted[0].goal_id]
        return selected

    @staticmethod
    def _next_goal_number(goals: list[Goal]) -> int:
        nums = [_goal_num(g.goal_id) for g in goals if g.goal_id]
        return max(nums) + 1 if nums else 1

    @staticmethod
    def _slugify_clause(clause: str, *, fallback: str) -> str:
        parts = re.findall(r"[A-Za-z0-9]+", str(clause))
        if not parts:
            return fallback
        out = "_".join(x.lower() for x in parts[:8]).strip("_")
        return out or fallback

    @staticmethod
    def _normalize_reasoning_tier(value: str) -> str:
        tier = str(value or "").strip().lower()
        return tier if tier in {"medium", "high", "super_high"} else ""

    def _skill_registry_from_doc(self, doc: dict[str, Any]) -> dict[str, str]:
        if self.external_skill_registry:
            return dict(self.external_skill_registry)
        registry = doc.get("skill_registry_v1") if isinstance(doc.get("skill_registry_v1"), dict) else {}
        rows = registry.get("skills") if isinstance(registry.get("skills"), list) else []
        out: dict[str, str] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            sid = str(row.get("id") or "").strip()
            spath = str(row.get("path") or "").strip()
            if sid and spath:
                out[sid] = spath
        return out or dict(DEFAULT_SKILL_REGISTRY)

    @staticmethod
    def _track_required_skills(doc: dict[str, Any], track: str) -> list[str]:
        policy = doc.get("skill_binding_policy_v1") if isinstance(doc.get("skill_binding_policy_v1"), dict) else {}
        track_rules = policy.get("track_required_skills") if isinstance(policy.get("track_required_skills"), dict) else {}
        from_doc = track_rules.get(track) if isinstance(track_rules.get(track), list) else []
        cleaned = [str(x) for x in from_doc if isinstance(x, str) and str(x).strip()]
        if cleaned:
            return cleaned
        return list(DEFAULT_TRACK_SKILLS.get(track, DEFAULT_TRACK_SKILLS["impl_fetchdata"]))

    def _skill_enforcement_from_doc(self, doc: dict[str, Any]) -> str:
        if self.skill_enforcement_mode in {"warn", "enforce"}:
            return self.skill_enforcement_mode
        policy = doc.get("skill_enforcement_v1") if isinstance(doc.get("skill_enforcement_v1"), dict) else {}
        mode = str(policy.get("mode") or "").strip().lower()
        return mode if mode in {"warn", "enforce"} else "warn"

    @staticmethod
    def _difficulty_weights_from_doc(doc: dict[str, Any]) -> dict[str, int]:
        raw = doc.get("difficulty_scoring_v1") if isinstance(doc.get("difficulty_scoring_v1"), dict) else {}
        weights = raw.get("weights") if isinstance(raw.get("weights"), dict) else {}
        out: dict[str, int] = {}
        for key, default in DEFAULT_DIFFICULTY_WEIGHTS.items():
            try:
                out[key] = max(0, int(weights.get(key, default)))
            except Exception:
                out[key] = default
        return out

    @staticmethod
    def _reasoning_tiers_from_doc(doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
        raw = doc.get("reasoning_tiers_v1") if isinstance(doc.get("reasoning_tiers_v1"), dict) else {}
        tiers = raw.get("tiers") if isinstance(raw.get("tiers"), dict) else {}
        out: dict[str, dict[str, Any]] = {}
        for tier in ("medium", "high", "super_high"):
            row = tiers.get(tier) if isinstance(tiers.get(tier), dict) else {}
            base = DEFAULT_REASONING_TIERS[tier]
            try:
                timeout = max(60, int(row.get("timeout_sec", base["timeout_sec"])))
            except Exception:
                timeout = int(base["timeout_sec"])
            try:
                retry = max(1, int(row.get("retry", base["retry"])))
            except Exception:
                retry = int(base["retry"])
            model = str(row.get("model", base["model"]) or "").strip()
            out[tier] = {
                "model": model,
                "timeout_sec": timeout,
                "retry": retry,
            }
        return out

    @staticmethod
    def _reasoning_thresholds_from_doc(doc: dict[str, Any]) -> dict[str, int]:
        raw = doc.get("reasoning_tiers_v1") if isinstance(doc.get("reasoning_tiers_v1"), dict) else {}
        thresholds = raw.get("thresholds") if isinstance(raw.get("thresholds"), dict) else {}
        out = dict(DEFAULT_REASONING_THRESHOLDS)
        try:
            out["medium_max"] = max(0, min(100, int(thresholds.get("medium_max", out["medium_max"]))))
        except Exception:
            pass
        try:
            out["high_max"] = max(out["medium_max"], min(100, int(thresholds.get("high_max", out["high_max"]))))
        except Exception:
            pass
        return out

    @staticmethod
    def _goal_dependency_depth_scores(goal_rows: list[dict[str, Any]]) -> dict[str, int]:
        deps_map: dict[str, list[str]] = {}
        for row in goal_rows:
            if not isinstance(row, dict):
                continue
            gid = str(row.get("id") or "").strip()
            if not gid:
                continue
            deps_map[gid] = [str(x) for x in (row.get("depends_on") or []) if isinstance(x, str)]

        memo: dict[str, int] = {}

        def _depth(gid: str, stack: set[str]) -> int:
            if gid in memo:
                return memo[gid]
            if gid in stack:
                return 0
            stack_next = set(stack)
            stack_next.add(gid)
            dep_scores = [_depth(dep, stack_next) for dep in deps_map.get(gid, []) if dep in deps_map]
            score = 1 + (max(dep_scores) if dep_scores else 0)
            memo[gid] = score
            return score

        for gid in deps_map:
            _depth(gid, set())
        return memo

    @staticmethod
    def _difficulty_to_tier(score: int, thresholds: dict[str, int]) -> str:
        v = max(0, min(100, int(score)))
        if v <= int(thresholds.get("medium_max", DEFAULT_REASONING_THRESHOLDS["medium_max"])):
            return "medium"
        if v <= int(thresholds.get("high_max", DEFAULT_REASONING_THRESHOLDS["high_max"])):
            return "high"
        return "super_high"

    def _goal_row_difficulty_score(
        self,
        row: dict[str, Any],
        *,
        depth_score_by_goal: dict[str, int],
        weights: dict[str, int],
    ) -> int:
        gid = str(row.get("id") or "").strip()
        allowed_paths = [str(x) for x in (row.get("allowed_paths") or []) if isinstance(x, str)]
        acceptance_commands = [str(x) for x in (row.get("acceptance_commands") or []) if isinstance(x, str)]
        notes = [str(x) for x in (row.get("notes") or []) if isinstance(x, str)]
        status_now = str(row.get("status_now") or "").strip().lower()

        dep_depth_raw = max(0, depth_score_by_goal.get(gid, 1) - 1)
        dependency_depth = min(weights["dependency_depth"], dep_depth_raw * 5)

        wildcard_cnt = sum(1 for p in allowed_paths if any(t in p for t in ("*", "?", "[")))
        top_dirs = {(_norm_path(p).split("/", 1)[0] if _norm_path(p) else "") for p in allowed_paths}
        top_dirs.discard("")
        path_complexity_raw = len(allowed_paths) * 2 + wildcard_cnt * 2 + len(top_dirs)
        path_complexity = min(weights["path_complexity"], path_complexity_raw)

        heavy_cmds = sum(
            1
            for cmd in acceptance_commands
            if any(tok in cmd for tok in ("pytest", "check_subagent_packet.py", "check_docs_tree.py"))
        )
        acceptance_raw = len(acceptance_commands) * 4 + heavy_cmds * 2
        acceptance_cost = min(weights["acceptance_cost"], acceptance_raw)

        lower_paths = [p.lower() for p in allowed_paths]
        if any(_match_rule(p, "contracts/**") or _match_rule(p, "policies/**") for p in lower_paths):
            redline_proximity = weights["redline_proximity"]
        elif any("holdout" in p for p in lower_paths):
            redline_proximity = min(weights["redline_proximity"], max(8, weights["redline_proximity"] - 2))
        elif any(any(_match_rule(p, x) for x in API_ROUTE_TOUCH_PATTERNS) for p in lower_paths):
            redline_proximity = min(weights["redline_proximity"], max(6, weights["redline_proximity"] - 4))
        elif any("src/quant_eam/ui/" in p or "src/quant_eam/api/" in p for p in lower_paths):
            redline_proximity = min(weights["redline_proximity"], 10)
        else:
            redline_proximity = min(weights["redline_proximity"], 4)

        notes_text = " ".join(notes).lower()
        instability_raw = (
            notes_text.count("retry") * 4
            + notes_text.count("failed") * 5
            + notes_text.count("blocked") * 6
            + (4 if status_now in {"partial", "blocked"} else 0)
        )
        history_instability = min(weights["history_instability"], instability_raw)

        total = (
            dependency_depth
            + path_complexity
            + acceptance_cost
            + redline_proximity
            + history_instability
        )
        return max(0, min(100, int(total)))

    def _apply_goal_skill_reasoning_fields(self, doc: dict[str, Any], goal_rows: list[dict[str, Any]]) -> None:
        weights = self._difficulty_weights_from_doc(doc)
        thresholds = self._reasoning_thresholds_from_doc(doc)
        depth_scores = self._goal_dependency_depth_scores(goal_rows)
        valid_tiers = {"medium", "high", "super_high"}
        for row in goal_rows:
            if not isinstance(row, dict):
                continue
            track = str(row.get("track") or "").strip()
            row["required_skills"] = self._track_required_skills(doc, track)
            score = self._goal_row_difficulty_score(
                row,
                depth_score_by_goal=depth_scores,
                weights=weights,
            )
            row["difficulty_score"] = score
            existing_tier = self._normalize_reasoning_tier(str(row.get("reasoning_tier") or ""))
            if self.reasoning_tier_override in valid_tiers:
                row["reasoning_tier"] = self.reasoning_tier_override
            elif existing_tier in valid_tiers:
                row["reasoning_tier"] = existing_tier
            else:
                row["reasoning_tier"] = self._difficulty_to_tier(score, thresholds)

    def _goal_reasoning_profile(self, doc: dict[str, Any], goal: Goal) -> dict[str, Any]:
        tiers = self._reasoning_tiers_from_doc(doc)
        thresholds = self._reasoning_thresholds_from_doc(doc)
        if self.reasoning_tier_override:
            tier = self.reasoning_tier_override
        else:
            tier = self._normalize_reasoning_tier(goal.reasoning_tier)
            if not tier:
                tier = self._difficulty_to_tier(goal.difficulty_score, thresholds)
        profile = tiers.get(tier, tiers["medium"])
        model = self.codex_model if self.codex_model else str(profile.get("model") or "").strip()
        profile_timeout = max(60, int(profile.get("timeout_sec") or self.codex_timeout_sec))
        # --codex-timeout-sec is a hard cap so high/super_high tiers cannot hang for hours.
        timeout_cap = max(60, int(self.codex_timeout_sec))
        timeout_sec = max(60, min(profile_timeout, timeout_cap))
        retry = max(1, int(profile.get("retry") or 2))
        return {
            "tier": tier,
            "model": model,
            "timeout_sec": timeout_sec,
            "retry": retry,
        }

    @staticmethod
    def _done_state_flags(doc: dict[str, Any]) -> dict[str, bool]:
        goals = doc.get("goal_checklist") if isinstance(doc.get("goal_checklist"), list) else []
        reqs = doc.get("requirements_trace_v1") if isinstance(doc.get("requirements_trace_v1"), list) else []
        clusters = doc.get("capability_clusters_v1") if isinstance(doc.get("capability_clusters_v1"), list) else []

        goal_rows = [g for g in goals if isinstance(g, dict)]
        req_rows = [r for r in reqs if isinstance(r, dict)]
        cluster_rows = [c for c in clusters if isinstance(c, dict)]

        return {
            "goal_checklist_all_implemented": bool(goal_rows) and all(str(g.get("status_now") or "") == "implemented" for g in goal_rows),
            "requirements_trace_all_implemented": bool(req_rows) and all(str(r.get("status_now") or "") == "implemented" for r in req_rows),
            "capability_clusters_all_implemented": bool(cluster_rows)
            and all(str(c.get("status_now") or "") == "implemented" for c in cluster_rows),
        }

    @classmethod
    def _done_state_all_true(cls, doc: dict[str, Any]) -> bool:
        flags = cls._done_state_flags(doc)
        return all(flags.values())

    @staticmethod
    def _latest_implemented_goal_id(goals: list[Goal], track: str) -> str:
        rows = [g.goal_id for g in goals if g.track == track and g.status_now == "implemented"]
        return max(rows, key=_goal_num) if rows else ""

    def _ensure_phase_doc(
        self,
        *,
        path: str,
        title: str,
        goal: str,
        requirements: list[str],
        architecture: list[str],
        dod: list[str],
    ) -> None:
        abs_path = self.repo_root / path
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        text = (
            f"# {title}\n\n"
            "## Goal\n"
            f"- {goal}\n\n"
            "## Requirements\n"
            + "".join(f"- {x}\n" for x in requirements)
            + "\n## Architecture\n"
            + "".join(f"- {x}\n" for x in architecture)
            + "\n## DoD\n"
            + "".join(f"- {x}\n" for x in dod)
            + "\n## Implementation Plan\n"
            "TBD by controller at execution time.\n"
        )
        abs_path.write_text(text, encoding="utf-8")

    def _latest_goal_for_requirement(self, goals: list[Goal], req_id: str) -> str:
        rows = [g.goal_id for g in goals if req_id in g.requirement_ids]
        return max(rows, key=_goal_num) if rows else ""

    @staticmethod
    def _goal_generation_signature(
        *,
        track: str,
        requirement_ids: list[str],
        depends_on: list[str],
    ) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
        req_sig = tuple(sorted({str(x).strip() for x in requirement_ids if str(x).strip()}))
        dep_sig = tuple(sorted({str(x).strip() for x in depends_on if str(x).strip()}, key=lambda x: (_goal_num(x), x)))
        return (str(track or "").strip(), req_sig, dep_sig)

    @staticmethod
    def _requirement_row(doc: dict[str, Any], req_id: str) -> dict[str, Any] | None:
        rows = doc.get("requirements_trace_v1")
        if not isinstance(rows, list):
            return None
        for row in rows:
            if isinstance(row, dict) and str(row.get("req_id") or "") == req_id:
                return row
        return None

    def _build_requirement_goal_row(
        self,
        *,
        req: Requirement,
        goal_id: str,
        depends_on: list[str],
        cluster_id: str,
        req_bundle: list[Requirement] | None = None,
        ensure_phase_doc: bool = True,
    ) -> dict[str, Any]:
        bundle = req_bundle or [req]
        bundle = [x for x in bundle if isinstance(x, Requirement)]
        if not bundle:
            bundle = [req]
        primary = bundle[0]
        req_ids = [x.req_id for x in bundle]
        req_ref = "/".join(req_ids)
        goal_num = _goal_num(goal_id)
        slug_seed = f"{primary.clause} bundle" if len(bundle) > 1 else primary.clause
        slug = self._slugify_clause(slug_seed, fallback=f"req_{goal_num}")
        if primary.owner_track == "skeleton":
            phase_doc_path = f"docs/08_phases/00_skeleton/phase_skel_g{goal_num}_{slug}.md"
            title = (
                f"Skeleton requirement bundle execution for {req_ref}"
                if len(req_ids) > 1
                else f"Skeleton requirement execution for {primary.req_id}"
            )
            allowed_paths = [
                phase_doc_path,
                "docs/12_workflows/skeleton_ssot_v1.yaml",
                "docs/05_data_plane/**",
                f"artifacts/subagent_control/{goal_id}/**",
            ]
            acceptance_commands = [
                "python3 scripts/check_docs_tree.py",
                f'rg -n "{goal_id}|{"|".join(req_ids)}" docs/12_workflows/skeleton_ssot_v1.yaml',
            ]
            ui_path = f"/skeleton/req/{primary.req_id.lower()}"
        elif primary.owner_track == "impl_fetchdata":
            phase_doc_path = f"docs/08_phases/10_impl_fetchdata/phase_fetch_g{goal_num}_{slug}.md"
            title = (
                f"Impl fetch requirement bundle execution for {req_ref}"
                if len(req_ids) > 1
                else f"Impl fetch requirement execution for {primary.req_id}"
            )
            allowed_paths = [
                phase_doc_path,
                "docs/12_workflows/skeleton_ssot_v1.yaml",
                "docs/05_data_plane/**",
                "src/quant_eam/qa_fetch/**",
                "tests/test_qa_fetch_*.py",
                f"artifacts/subagent_control/{goal_id}/**",
            ]
            acceptance_commands = [
                "python3 scripts/check_docs_tree.py",
                *FETCH_IMPL_REQUIREMENT_ACCEPTANCE_COMMANDS,
                f'rg -n "{goal_id}|{"|".join(req_ids)}" docs/12_workflows/skeleton_ssot_v1.yaml',
            ]
            ui_path = f"/qa-fetch/req/{primary.req_id.lower()}"
        elif primary.owner_track == "impl_workbench":
            phase_doc_path = f"docs/08_phases/10_impl_workbench/phase_workbench_g{goal_num}_{slug}.md"
            title = (
                f"Impl workbench requirement bundle execution for {req_ref}"
                if len(req_ids) > 1
                else f"Impl workbench requirement execution for {primary.req_id}"
            )
            allowed_paths = [
                phase_doc_path,
                "docs/12_workflows/skeleton_ssot_v1.yaml",
                "docs/00_overview/workbench_ui_productization_v1.md",
                "src/quant_eam/ui/**",
                "src/quant_eam/api/**",
                "tests/test_ui_*.py",
                f"artifacts/subagent_control/{goal_id}/**",
            ]
            acceptance_commands = [
                "python3 scripts/check_docs_tree.py",
                "python3 -m pytest -q tests/test_ui_mvp.py",
                f'rg -n "{goal_id}|{"|".join(req_ids)}" docs/12_workflows/skeleton_ssot_v1.yaml',
            ]
            ui_path = f"/ui/workbench/req/{primary.req_id.lower()}"
        else:
            phase_doc_path = f"docs/08_phases/10_impl_fetchdata/phase_fetch_g{goal_num}_{slug}.md"
            title = (
                f"Impl requirement bundle execution for {req_ref}"
                if len(req_ids) > 1
                else f"Impl requirement execution for {primary.req_id}"
            )
            allowed_paths = [
                phase_doc_path,
                "docs/12_workflows/skeleton_ssot_v1.yaml",
                f"artifacts/subagent_control/{goal_id}/**",
            ]
            acceptance_commands = [
                "python3 scripts/check_docs_tree.py",
                f'rg -n "{goal_id}|{"|".join(req_ids)}" docs/12_workflows/skeleton_ssot_v1.yaml',
            ]
            ui_path = f"/impl/req/{primary.req_id.lower()}"

        if ensure_phase_doc:
            self._ensure_phase_doc(
                path=phase_doc_path,
                title=f"Phase {goal_id}: Requirement Gap Closure ({req_ref})",
                goal=(
                    f"Close requirement gap bundle `{req_ref}` from `{primary.source_document}:{primary.source_line}`."
                    if len(req_ids) > 1
                    else f"Close requirement gap `{primary.req_id}` from `{primary.source_document}:{primary.source_line}`."
                ),
                requirements=(
                    [f"Requirement IDs: {req_ref}", f"Owner Track: {primary.owner_track}"]
                    + [f"Clause[{x.req_id}]: {x.clause}" for x in bundle]
                ),
                architecture=[
                    "Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml",
                    "Requirement-gap-only planning path.",
                    "Interface-first dependency gate for impl goals.",
                    (
                        "Bundling criterion: same owner track + same source document + same parent requirement"
                        " + near-adjacent source lines."
                    ),
                ],
                dod=[
                    "Acceptance commands pass.",
                    "Packet validator passes.",
                    "SSOT writeback marks linked requirement implemented.",
                ],
            )

        return {
            "id": goal_id,
            "title": title,
            "status_now": "planned",
            "depends_on": sorted(set(depends_on), key=_goal_num),
            "track": primary.owner_track,
            "requirement_ids": req_ids,
            "phase_doc_path": phase_doc_path,
            "required_skills": list(DEFAULT_TRACK_SKILLS.get(primary.owner_track, DEFAULT_TRACK_SKILLS["impl_fetchdata"])),
            "difficulty_score": 0,
            "reasoning_tier": "",
            "todo_checklist": [],
            "risk_notes": [],
            "parallel_hints": [],
            "todo_planner": {},
            "ui_path": ui_path,
            "expected_state_change": (
                f"Requirement bundle `{req_ref}` transitions to implemented after acceptance."
                if len(req_ids) > 1
                else f"Requirement `{primary.req_id}` transitions to implemented after acceptance."
            ),
            "expected_artifacts": [phase_doc_path, "docs/12_workflows/skeleton_ssot_v1.yaml"],
            "allowed_paths": allowed_paths,
            "acceptance_commands": acceptance_commands,
            "stop_condition_exception_scope": {
                "exception_id": f"{goal_id.lower()}_requirement_gap_scope",
                "rationale": "requirement-gap driven goal",
                "preauthorized_scope": {
                    "allowed_route_prefixes": [ui_path],
                    "allowed_code_paths": allowed_paths,
                    "still_forbidden": [
                        "contracts/**",
                        "policies/**",
                        "Holdout visibility expansion",
                    ],
                },
            },
            "capability_cluster_id": cluster_id,
            "allow_noop": False,
            "notes": [
                (
                    f"Auto-generated from unmet requirement bundle {req_ref} at {_utc_now()}"
                    if len(req_ids) > 1
                    else f"Auto-generated from unmet requirement {primary.req_id} at {_utc_now()}"
                )
            ],
        }

    @staticmethod
    def _goal_bundle_policy(doc: dict[str, Any], *, track: str = "") -> dict[str, Any]:
        planning = doc.get("planning_policy_v2") if isinstance(doc.get("planning_policy_v2"), dict) else {}
        raw = planning.get("goal_bundle_policy") if isinstance(planning.get("goal_bundle_policy"), dict) else {}
        override = {}
        if track:
            overrides = raw.get("track_overrides") if isinstance(raw.get("track_overrides"), dict) else {}
            override = overrides.get(track) if isinstance(overrides.get(track), dict) else {}
        enabled = bool(override.get("enabled", raw.get("enabled", True)))
        max_per_goal = max(1, int(override.get("max_requirements_per_goal", raw.get("max_requirements_per_goal", 4))))
        line_window = max(0, int(override.get("source_line_window", raw.get("source_line_window", 6))))
        minimum_bundle_size = max(1, int(override.get("minimum_bundle_size", raw.get("minimum_bundle_size", 2))))
        require_same_source_document = bool(
            override.get("require_same_source_document", raw.get("require_same_source_document", True))
        )
        require_same_parent_requirement = bool(
            override.get("require_same_parent_requirement", raw.get("require_same_parent_requirement", True))
        )
        require_exact_parent_signature = bool(
            override.get("require_exact_parent_signature", raw.get("require_exact_parent_signature", False))
        )
        return {
            "enabled": enabled,
            "max_requirements_per_goal": max_per_goal,
            "source_line_window": line_window,
            "minimum_bundle_size": minimum_bundle_size,
            "require_same_source_document": require_same_source_document,
            "require_same_parent_requirement": require_same_parent_requirement,
            "require_exact_parent_signature": require_exact_parent_signature,
        }

    @staticmethod
    def _pick_requirement_bundle(
        *,
        chosen: Requirement,
        unmet_sorted: list[Requirement],
        req_by_id: dict[str, Requirement],
        ready_req_ids: set[str],
        policy: dict[str, Any],
    ) -> list[Requirement]:
        if not bool(policy.get("enabled", True)):
            return [chosen]

        parent_ids = [rid for rid in chosen.depends_on_req_ids if rid in req_by_id]
        parent_id = parent_ids[0] if parent_ids else ""
        require_same_parent = bool(policy.get("require_same_parent_requirement", True))
        if require_same_parent and not parent_id:
            return [chosen]

        max_per_goal = max(1, int(policy.get("max_requirements_per_goal", 4)))
        source_line_window = max(0, int(policy.get("source_line_window", 6)))
        min_bundle_size = max(1, int(policy.get("minimum_bundle_size", 2)))
        require_same_source_doc = bool(policy.get("require_same_source_document", True))
        require_exact_parent_signature = bool(policy.get("require_exact_parent_signature", False))
        chosen_parent_signature = sorted([rid for rid in chosen.depends_on_req_ids if rid in req_by_id])

        siblings: list[Requirement] = []
        for r in unmet_sorted:
            if r.owner_track != chosen.owner_track:
                continue
            if require_same_source_doc and r.source_document != chosen.source_document:
                continue
            if require_same_parent and parent_id and parent_id not in r.depends_on_req_ids:
                continue
            if require_exact_parent_signature:
                sig = sorted([rid for rid in r.depends_on_req_ids if rid in req_by_id])
                if sig != chosen_parent_signature:
                    continue
            if abs(int(r.source_line) - int(chosen.source_line)) > source_line_window:
                continue
            if r.owner_track in IMPLEMENT_TRACKS:
                dep_skeleton_req_ids = [
                    rid
                    for rid in r.depends_on_req_ids
                    if req_by_id.get(rid) and req_by_id[rid].owner_track == "skeleton"
                ]
                if any(rid not in ready_req_ids for rid in dep_skeleton_req_ids):
                    continue
            siblings.append(r)

        siblings_sorted = sorted(
            {r.req_id: r for r in siblings}.values(),
            key=lambda x: (int(x.source_line), x.req_id),
        )
        if not siblings_sorted:
            return [chosen]

        picked = siblings_sorted[:max_per_goal]
        if chosen.req_id not in {x.req_id for x in picked}:
            picked = [chosen] + [x for x in picked if x.req_id != chosen.req_id]
        picked = sorted({x.req_id: x for x in picked}.values(), key=lambda x: (int(x.source_line), x.req_id))
        if len(picked) < min_bundle_size:
            return [chosen]
        return picked

    @staticmethod
    def _goal_todo_planner_policy(doc: dict[str, Any]) -> dict[str, Any]:
        planning = doc.get("planning_policy_v2") if isinstance(doc.get("planning_policy_v2"), dict) else {}
        raw = planning.get("goal_todo_planner_v1") if isinstance(planning.get("goal_todo_planner_v1"), dict) else {}
        mode = str(raw.get("mode") or "codex_assisted").strip().lower()
        if mode not in {"codex_assisted", "rule_only"}:
            mode = "rule_only"
        fallback_mode = str(raw.get("fallback_mode") or "rule_only").strip().lower()
        if fallback_mode not in {"rule_only"}:
            fallback_mode = "rule_only"
        return {
            "enabled": bool(raw.get("enabled", True)),
            "mode": mode,
            "codex_timeout_sec": max(60, int(raw.get("codex_timeout_sec", 240))),
            "max_items_per_section": max(3, int(raw.get("max_items_per_section", 6))),
            "fallback_mode": fallback_mode,
            "require_codex_for_planning": bool(raw.get("require_codex_for_planning", False)),
        }

    @staticmethod
    def _architect_preplan_policy(doc: dict[str, Any]) -> dict[str, Any]:
        planning = doc.get("planning_policy_v2") if isinstance(doc.get("planning_policy_v2"), dict) else {}
        raw = planning.get("architect_preplan_v1") if isinstance(planning.get("architect_preplan_v1"), dict) else {}
        mode = str(raw.get("mode") or "codex_assisted").strip().lower()
        if mode not in {"codex_assisted", "rule_only"}:
            mode = "rule_only"
        source_documents = [str(x) for x in (raw.get("source_documents") or []) if isinstance(x, str) and str(x).strip()]
        if not source_documents:
            source_documents = [
                _path_str_for_doc(_requirement_doc_path(prefix), repo_root=REPO_ROOT)
                for prefix, _ in REQ_SOURCE_CANDIDATES
            ]
        latest_plan = raw.get("latest_plan") if isinstance(raw.get("latest_plan"), dict) else {}
        return {
            "status_now": str(raw.get("status_now") or "active"),
            "enabled": bool(raw.get("enabled", True)),
            "mode": mode,
            "codex_timeout_sec": max(60, int(raw.get("codex_timeout_sec", 300))),
            "max_requirements": max(20, int(raw.get("max_requirements", 120))),
            "max_goal_candidates": max(10, int(raw.get("max_goal_candidates", 80))),
            "require_codex_for_preplan": bool(raw.get("require_codex_for_preplan", False)),
            "enforce_before_goal_generation": bool(raw.get("enforce_before_goal_generation", True)),
            "source_documents": source_documents,
            "cache_by_signature": bool(raw.get("cache_by_signature", True)),
            "latest_plan": latest_plan,
        }

    @staticmethod
    def _architect_requirement_priority_map(doc: dict[str, Any]) -> dict[str, int]:
        policy = WholeViewAutopilot._architect_preplan_policy(doc)
        latest = policy.get("latest_plan") if isinstance(policy.get("latest_plan"), dict) else {}
        rows = [str(x) for x in (latest.get("requirement_priority") or []) if isinstance(x, str)]
        return {rid: idx for idx, rid in enumerate(rows)}

    @staticmethod
    def _architect_goal_priority_map(doc: dict[str, Any]) -> dict[str, int]:
        policy = WholeViewAutopilot._architect_preplan_policy(doc)
        latest = policy.get("latest_plan") if isinstance(policy.get("latest_plan"), dict) else {}
        rows = [str(x) for x in (latest.get("goal_priority") or []) if isinstance(x, str)]
        return {gid: idx for idx, gid in enumerate(rows)}

    @staticmethod
    def _architect_preplan_signature(requirements: list[Requirement], goals: list[Goal]) -> str:
        req_rows = sorted(
            [
                "|".join(
                    [
                        r.req_id,
                        r.status_now,
                        r.owner_track,
                        str(r.source_line),
                        ",".join(sorted([str(x) for x in r.depends_on_req_ids])),
                    ]
                )
                for r in requirements
                if r.req_id
            ]
        )
        goal_rows = sorted(
            [
                "|".join(
                    [
                        g.goal_id,
                        g.status_now,
                        g.track,
                        ",".join(sorted([str(x) for x in g.depends_on])),
                        ",".join(sorted([str(x) for x in g.requirement_ids])),
                    ]
                )
                for g in goals
                if g.goal_id
            ]
        )
        h = hashlib.sha256()
        h.update("\n".join(req_rows + goal_rows).encode("utf-8", errors="ignore"))
        return h.hexdigest()[:20]

    def _rule_based_architect_preplan(
        self,
        *,
        requirements: list[Requirement],
        goals: list[Goal],
        signature: str,
        max_requirements: int,
        max_goal_candidates: int,
    ) -> dict[str, Any]:
        req_by_id = {r.req_id: r for r in requirements if r.req_id}
        unmet = [r for r in requirements if r.status_now != "implemented" and r.req_id]
        implemented_req_ids = {r.req_id for r in requirements if r.status_now == "implemented"}

        def _req_priority_key(r: Requirement) -> tuple[int, int, int, str]:
            track_rank = 0 if r.owner_track == "skeleton" else (1 if r.owner_track == "impl_fetchdata" else 2)
            skel_deps = [rid for rid in r.depends_on_req_ids if req_by_id.get(rid) and req_by_id[rid].owner_track == "skeleton"]
            dep_ready = all(rid in implemented_req_ids for rid in skel_deps)
            dep_penalty = 0 if dep_ready else 1
            return (track_rank, dep_penalty, int(r.source_line or 0), r.req_id)

        req_priority = [r.req_id for r in sorted(unmet, key=_req_priority_key)][:max_requirements]

        active_goals = [g for g in goals if g.status_now in {"planned", "partial", "in_progress"}]
        goal_priority = [
            g.goal_id
            for g in sorted(
                active_goals,
                key=lambda g: (
                    0 if g.track == "skeleton" else (1 if g.track == "impl_fetchdata" else 2),
                    _goal_num(g.goal_id),
                ),
            )
        ][:max_goal_candidates]

        bundle_hints: list[dict[str, Any]] = []
        if req_priority:
            ordered_reqs = [req_by_id[rid] for rid in req_priority if rid in req_by_id]
            current: list[Requirement] = []
            for req in ordered_reqs:
                if not current:
                    current = [req]
                    continue
                first = current[0]
                same_track = req.owner_track == first.owner_track
                same_doc = req.source_document == first.source_document
                same_parent = sorted([x for x in req.depends_on_req_ids if x in req_by_id]) == sorted(
                    [x for x in first.depends_on_req_ids if x in req_by_id]
                )
                close_line = abs(int(req.source_line) - int(first.source_line)) <= 10
                if same_track and same_doc and same_parent and close_line and len(current) < 4:
                    current.append(req)
                else:
                    if len(current) >= 2:
                        bundle_hints.append(
                            {
                                "track": first.owner_track,
                                "requirement_ids": [x.req_id for x in current],
                                "reason": "same_track+same_document+same_parent_signature+line_window",
                            }
                        )
                    current = [req]
            if len(current) >= 2:
                bundle_hints.append(
                    {
                        "track": current[0].owner_track,
                        "requirement_ids": [x.req_id for x in current],
                        "reason": "same_track+same_document+same_parent_signature+line_window",
                    }
                )

        skeleton_open = [rid for rid in req_priority if req_by_id.get(rid) and req_by_id[rid].owner_track == "skeleton"]
        impl_open = [rid for rid in req_priority if req_by_id.get(rid) and req_by_id[rid].owner_track in IMPLEMENT_TRACKS]
        parallel_hints: list[str] = []
        if skeleton_open and impl_open:
            parallel_hints.append(
                f"Parallel candidate: skeleton {skeleton_open[0]} + impl {impl_open[0]} when allowed_paths are disjoint."
            )
        parallel_hints.append("Keep skeleton interface goals ahead of dependent impl goals.")
        parallel_hints.append("Prefer bundle goals with 2-4 requirements when parent signature is identical.")

        return {
            "mode": "rule_only",
            "source": "controller_architect_rules",
            "generated_at": _utc_now(),
            "signature": signature,
            "requirement_priority": req_priority,
            "goal_priority": goal_priority,
            "bundle_hints": bundle_hints[:12],
            "parallel_hints": parallel_hints[:8],
            "rationale": [
                "Applied skeleton-first dependency gate across all requirement tracks.",
                "Applied parent-signature-preserving bundle hints for denser phases.",
                "Produced stable priority list for pre-plan before goal publish.",
            ],
            "skills_used": ["architect-planner", "requirement-splitter", "ssot-goal-planner"],
        }

    def _codex_architect_preplan(
        self,
        *,
        requirements: list[Requirement],
        goals: list[Goal],
        signature: str,
        timeout_sec: int,
        max_requirements: int,
        max_goal_candidates: int,
    ) -> tuple[dict[str, Any], str]:
        if not shutil.which("codex"):
            return {}, "codex_cli_missing"
        req_by_id = {r.req_id: r for r in requirements if r.req_id}
        goal_by_id = {g.goal_id: g for g in goals if g.goal_id}
        unmet = [r for r in requirements if r.status_now != "implemented" and r.req_id]
        active_goals = [g for g in goals if g.status_now in {"planned", "partial", "in_progress"}]
        req_lines = "\n".join(
            f"- {r.req_id} | track={r.owner_track} | line={r.source_line} | deps={','.join(r.depends_on_req_ids) or '-'} | {r.clause}"
            for r in sorted(unmet, key=lambda x: (x.owner_track, int(x.source_line or 0), x.req_id))[:max_requirements]
        )
        goal_lines = "\n".join(
            f"- {g.goal_id} | track={g.track} | status={g.status_now} | deps={','.join(g.depends_on) or '-'} | reqs={','.join(g.requirement_ids) or '-'}"
            for g in sorted(active_goals, key=lambda x: _goal_num(x.goal_id))[:max_goal_candidates]
        )

        preplan_dir = self.repo_root / ARCHITECT_PREPLAN_ROOT_DEFAULT / signature
        preplan_dir.mkdir(parents=True, exist_ok=True)
        planner_out = preplan_dir / "architect_preplan_last_message.txt"
        prompt = (
            "You are the architect-planner for whole_view_autopilot pre-plan.\n"
            "Return strict JSON only with keys:\n"
            "requirement_priority (array req_id), goal_priority (array goal_id), "
            "bundle_hints (array of {track, requirement_ids, reason}), "
            "parallel_hints (array string), rationale (array string).\n"
            "Rules: skeleton interface requirements must be ordered before dependent impl requirements.\n"
            "Keep requirement_priority deterministic and finite.\n\n"
            f"Unmet requirements:\n{req_lines or '- (none)'}\n\n"
            f"Active goals:\n{goal_lines or '- (none)'}\n"
        )
        argv = ["codex", "exec", "--cd", str(self.repo_root), "--full-auto"]
        if self.codex_model:
            argv.extend(["--model", self.codex_model])
        argv.extend(["-o", str(planner_out)])
        res = self.run_command_argv(argv, timeout_sec=timeout_sec, input_text=prompt)
        raw = planner_out.read_text(encoding="utf-8") if planner_out.exists() else (res.stdout or "")
        json_text = self._extract_json_object(raw)
        if not json_text:
            return {}, "architect_preplan_json_missing"
        try:
            payload = json.loads(json_text)
        except Exception:
            return {}, "architect_preplan_json_parse_failed"
        if not isinstance(payload, dict):
            return {}, "architect_preplan_json_invalid"
        req_priority = [str(x) for x in (payload.get("requirement_priority") or []) if isinstance(x, str)]
        req_priority = [rid for rid in req_priority if rid in req_by_id and req_by_id[rid].status_now != "implemented"]
        goal_priority = [str(x) for x in (payload.get("goal_priority") or []) if isinstance(x, str)]
        goal_priority = [gid for gid in goal_priority if gid in goal_by_id and goal_by_id[gid].status_now in {"planned", "partial", "in_progress"}]

        bundle_hints: list[dict[str, Any]] = []
        for row in payload.get("bundle_hints") or []:
            if not isinstance(row, dict):
                continue
            track = str(row.get("track") or "")
            req_ids = [str(x) for x in (row.get("requirement_ids") or []) if isinstance(x, str) and x in req_by_id]
            reason = str(row.get("reason") or "")
            if track and req_ids:
                bundle_hints.append({"track": track, "requirement_ids": req_ids, "reason": reason})

        parallel_hints = [str(x) for x in (payload.get("parallel_hints") or []) if isinstance(x, str) and str(x).strip()]
        rationale = [str(x) for x in (payload.get("rationale") or []) if isinstance(x, str) and str(x).strip()]
        if not req_priority and not goal_priority:
            return {}, "architect_preplan_empty_priorities"
        return {
            "mode": "codex_assisted",
            "source": "codex_cli_architect_planner",
            "generated_at": _utc_now(),
            "signature": signature,
            "requirement_priority": req_priority[:max_requirements],
            "goal_priority": goal_priority[:max_goal_candidates],
            "bundle_hints": bundle_hints[:12],
            "parallel_hints": parallel_hints[:8],
            "rationale": rationale[:8],
            "skills_used": ["architect-planner", "requirement-splitter", "ssot-goal-planner"],
            "artifact_path": planner_out.relative_to(self.repo_root).as_posix(),
        }, ""

    def _run_architect_preplan(self, doc: dict[str, Any], goals: list[Goal]) -> dict[str, Any]:
        policy = self._architect_preplan_policy(doc)
        planning = doc.get("planning_policy_v2") if isinstance(doc.get("planning_policy_v2"), dict) else {}
        requirements = self.parse_requirements(doc)
        signature = self._architect_preplan_signature(requirements, goals)
        latest_plan = policy.get("latest_plan") if isinstance(policy.get("latest_plan"), dict) else {}
        if (
            bool(policy.get("enabled", True))
            and bool(policy.get("cache_by_signature", True))
            and str(latest_plan.get("signature") or "") == signature
            and (
                (latest_plan.get("requirement_priority") and isinstance(latest_plan.get("requirement_priority"), list))
                or (latest_plan.get("goal_priority") and isinstance(latest_plan.get("goal_priority"), list))
            )
        ):
            latest_plan = dict(latest_plan)
            latest_plan["cache_hit"] = True
            policy["latest_plan"] = latest_plan
            planning["architect_preplan_v1"] = policy
            doc["planning_policy_v2"] = planning
            return latest_plan

        if not bool(policy.get("enabled", True)):
            plan = {
                "mode": "disabled",
                "source": "architect_preplan_disabled",
                "generated_at": _utc_now(),
                "signature": signature,
                "requirement_priority": [],
                "goal_priority": [],
                "bundle_hints": [],
                "parallel_hints": [],
                "rationale": ["architect_preplan_v1 disabled"],
                "skills_used": [],
            }
            policy["latest_plan"] = plan
            planning["architect_preplan_v1"] = policy
            doc["planning_policy_v2"] = planning
            return plan

        plan = self._rule_based_architect_preplan(
            requirements=requirements,
            goals=goals,
            signature=signature,
            max_requirements=int(policy.get("max_requirements", 120)),
            max_goal_candidates=int(policy.get("max_goal_candidates", 80)),
        )
        if str(policy.get("mode") or "") == "codex_assisted":
            use_codex = (not self.dry_run) and self.subagent_mode == "codex_exec"
            if use_codex:
                codex_plan, fail_reason = self._codex_architect_preplan(
                    requirements=requirements,
                    goals=goals,
                    signature=signature,
                    timeout_sec=int(policy.get("codex_timeout_sec", 300)),
                    max_requirements=int(policy.get("max_requirements", 120)),
                    max_goal_candidates=int(policy.get("max_goal_candidates", 80)),
                )
                if codex_plan:
                    plan = codex_plan
                else:
                    plan["fallback_reason"] = fail_reason or "architect_preplan_codex_failed"
                    if bool(policy.get("require_codex_for_preplan", False)):
                        plan["blocked"] = True
                        plan["rationale"] = [f"architect preplan blocked: {plan['fallback_reason']}"]
            else:
                plan["fallback_reason"] = "dry_run_or_non_codex_mode"

        req_by_id = {r.req_id: r for r in requirements if r.req_id}
        unmet_ids = [r.req_id for r in requirements if r.status_now != "implemented" and r.req_id]
        ordered = [rid for rid in (plan.get("requirement_priority") or []) if rid in req_by_id and rid in unmet_ids]
        remaining = [rid for rid in unmet_ids if rid not in set(ordered)]
        plan["requirement_priority"] = ordered + sorted(remaining)

        goal_by_id = {g.goal_id: g for g in goals if g.goal_id}
        active_goal_ids = [g.goal_id for g in goals if g.status_now in {"planned", "partial", "in_progress"}]
        ordered_goals = [gid for gid in (plan.get("goal_priority") or []) if gid in goal_by_id and gid in active_goal_ids]
        remaining_goals = [gid for gid in active_goal_ids if gid not in set(ordered_goals)]
        plan["goal_priority"] = ordered_goals + sorted(remaining_goals, key=_goal_num)

        history = doc.get("architect_preplan_history_v1") if isinstance(doc.get("architect_preplan_history_v1"), list) else []
        history.append(
            {
                "generated_at": str(plan.get("generated_at") or _utc_now()),
                "signature": signature,
                "mode": str(plan.get("mode") or "rule_only"),
                "source": str(plan.get("source") or ""),
                "requirement_priority_count": len(plan.get("requirement_priority") or []),
                "goal_priority_count": len(plan.get("goal_priority") or []),
                "blocked": bool(plan.get("blocked", False)),
                "fallback_reason": str(plan.get("fallback_reason") or ""),
                "artifact_path": str(plan.get("artifact_path") or ""),
            }
        )
        doc["architect_preplan_history_v1"] = history[-80:]

        plan_dir = self.repo_root / ARCHITECT_PREPLAN_ROOT_DEFAULT
        plan_dir.mkdir(parents=True, exist_ok=True)
        plan_file = plan_dir / f"architect_preplan_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        plan_file.write_text(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        plan["artifact_path"] = plan_file.relative_to(self.repo_root).as_posix()

        policy["latest_plan"] = plan
        planning["architect_preplan_v1"] = policy
        doc["planning_policy_v2"] = planning
        return plan

    @staticmethod
    def _rule_based_goal_todo(
        *,
        goal_id: str,
        track: str,
        req_bundle: list[Requirement],
        depends_on: list[str],
        acceptance_commands: list[str],
        max_items: int,
    ) -> dict[str, Any]:
        req_ids = [r.req_id for r in req_bundle if r.req_id]
        checklist = [
            f"Verify requirement bundle scope: {', '.join(req_ids)}.",
            "Review dependency readiness and upstream artifacts before edits.",
            "Implement minimal changes only inside allowed_paths for this goal.",
            "Run acceptance commands and capture deterministic evidence.",
            "Write SSOT/phase updates consistent with executed changes.",
        ]
        risks = [
            "Dependency misread may cause false-ready dispatch.",
            "Allowed path overreach can trigger validator failure.",
            "Acceptance mismatch may leave requirement bundle partial.",
        ]
        if track in IMPLEMENT_TRACKS:
            risks.append("Interface drift against skeleton contract dependencies.")
        parallel_hints = [
            "Can run in parallel only with goals whose allowed_paths are disjoint.",
            "Avoid parallel run when sharing same requirement parent or upstream dependency chain.",
        ]
        if depends_on:
            parallel_hints.append(f"Must start after dependencies implemented: {', '.join(sorted(set(depends_on), key=_goal_num))}.")
        if acceptance_commands:
            parallel_hints.append(f"Acceptance gate count: {len(acceptance_commands)} commands.")
        return {
            "todo_checklist": checklist[:max_items],
            "risk_notes": risks[:max_items],
            "parallel_hints": parallel_hints[:max_items],
            "todo_planner": {
                "mode": "rule_only",
                "source": "controller_rules",
                "generated_at": _utc_now(),
                "goal_id": goal_id,
            },
        }

    @staticmethod
    def _extract_json_object(text: str) -> str:
        s = str(text or "").strip()
        if not s:
            return ""
        if s.startswith("{") and s.endswith("}"):
            return s
        start = s.find("{")
        end = s.rfind("}")
        if start >= 0 and end > start:
            return s[start : end + 1]
        return ""

    def _codex_goal_todo_plan(
        self,
        *,
        doc: dict[str, Any],
        goal_id: str,
        track: str,
        req_bundle: list[Requirement],
        depends_on: list[str],
        acceptance_commands: list[str],
        max_items: int,
        timeout_sec: int,
    ) -> tuple[dict[str, Any], str]:
        if not shutil.which("codex"):
            return {}, "codex_cli_missing"
        planner_dir = self.repo_root / "artifacts" / "autopilot" / "planner" / goal_id
        planner_dir.mkdir(parents=True, exist_ok=True)
        planner_out = planner_dir / "todo_planner_last_message.txt"
        req_lines = "\n".join(
            f"- {r.req_id} ({r.source_document}:{r.source_line}): {r.clause}"
            for r in req_bundle
        )
        dep_line = ", ".join(sorted(set(depends_on), key=_goal_num)) if depends_on else "(none)"
        acc_lines = "\n".join(f"- {x}" for x in acceptance_commands)
        prompt = (
            f"You are planning execution todo for goal {goal_id}.\n"
            "Output strict JSON only with keys: checklist, risks, parallel_hints.\n"
            f"Each key must be an array of concise strings, max {max_items} items.\n\n"
            f"Track: {track}\nDependencies: {dep_line}\n\nRequirement bundle:\n{req_lines}\n\n"
            f"Acceptance commands:\n{acc_lines}\n"
        )
        argv = ["codex", "exec", "--cd", str(self.repo_root), "--full-auto"]
        if self.codex_model:
            argv.extend(["--model", self.codex_model])
        argv.extend(["-o", str(planner_out)])
        res = self.run_command_argv(argv, timeout_sec=timeout_sec, input_text=prompt)
        raw = planner_out.read_text(encoding="utf-8") if planner_out.exists() else (res.stdout or "")
        json_text = self._extract_json_object(raw)
        if not json_text:
            return {}, "planner_json_missing"
        try:
            payload = json.loads(json_text)
        except Exception:
            return {}, "planner_json_parse_failed"
        if not isinstance(payload, dict):
            return {}, "planner_json_invalid"
        checklist = [str(x).strip() for x in (payload.get("checklist") or []) if str(x).strip()]
        risks = [str(x).strip() for x in (payload.get("risks") or []) if str(x).strip()]
        parallel = [str(x).strip() for x in (payload.get("parallel_hints") or []) if str(x).strip()]
        if not checklist or not risks or not parallel:
            return {}, "planner_json_incomplete"
        return {
            "todo_checklist": checklist[:max_items],
            "risk_notes": risks[:max_items],
            "parallel_hints": parallel[:max_items],
            "todo_planner": {
                "mode": "codex_assisted",
                "source": "codex_cli_planner",
                "generated_at": _utc_now(),
                "goal_id": goal_id,
                "artifact_path": planner_out.relative_to(self.repo_root).as_posix(),
            },
        }, ""

    def _backfill_goal_todo_plans(
        self,
        *,
        doc: dict[str, Any],
        goal_rows: list[dict[str, Any]],
        req_by_id: dict[str, Requirement],
    ) -> None:
        todo_policy = self._goal_todo_planner_policy(doc)
        max_items = int(todo_policy.get("max_items_per_section", 6))
        for row in goal_rows:
            if not isinstance(row, dict):
                continue
            existing_todo = [str(x) for x in (row.get("todo_checklist") or []) if isinstance(x, str)]
            existing_risks = [str(x) for x in (row.get("risk_notes") or []) if isinstance(x, str)]
            existing_parallel = [str(x) for x in (row.get("parallel_hints") or []) if isinstance(x, str)]
            if existing_todo and existing_risks and existing_parallel:
                continue
            req_ids = [str(x) for x in (row.get("requirement_ids") or []) if isinstance(x, str)]
            req_bundle = [req_by_id[rid] for rid in req_ids if rid in req_by_id]
            if not req_bundle:
                continue
            payload = self._rule_based_goal_todo(
                goal_id=str(row.get("id") or ""),
                track=str(row.get("track") or ""),
                req_bundle=req_bundle,
                depends_on=[str(x) for x in (row.get("depends_on") or []) if isinstance(x, str)],
                acceptance_commands=[str(x) for x in (row.get("acceptance_commands") or []) if isinstance(x, str)],
                max_items=max_items,
            )
            row["todo_checklist"] = payload["todo_checklist"]
            row["risk_notes"] = payload["risk_notes"]
            row["parallel_hints"] = payload["parallel_hints"]
            row["todo_planner"] = payload["todo_planner"]

    def maybe_generate_goals_when_queue_empty(self, doc: dict[str, Any], goals: list[Goal]) -> list[str]:
        whole_view = doc.get("whole_view_autopilot_v1")
        if not isinstance(whole_view, dict):
            return []
        if self._done_state_all_true(doc):
            return []
        planning_policy = doc.get("planning_policy_v2") if isinstance(doc.get("planning_policy_v2"), dict) else {}
        if str(planning_policy.get("generation_mode") or "") != "requirement_gap_only":
            return []
        rolling = whole_view.get("rolling_goal_policy") if isinstance(whole_view.get("rolling_goal_policy"), dict) else {}
        enabled = bool(rolling.get("enabled", False))
        trigger = bool(rolling.get("trigger_when_no_planned_or_partial", False))
        if not enabled or not trigger:
            return []

        active = [g for g in goals if g.status_now in {"planned", "partial", "in_progress"}]
        if active:
            return []
        # Fail-closed: if blocked goals exist, stop auto-generation and let controller surface blocked.
        if any(g.status_now == "blocked" for g in goals):
            return []

        requirements = self.parse_requirements(doc)
        if not requirements:
            return []
        goals_by_id = {g.goal_id: g for g in goals}
        req_by_id = {r.req_id: r for r in requirements}
        req_to_goal_ids: dict[str, list[str]] = defaultdict(list)
        active_req_ids: set[str] = set()
        for g in goals:
            req_ids = set(g.requirement_ids + [rid for rid, req in req_by_id.items() if g.goal_id in req.mapped_goal_ids])
            for rid in req_ids:
                req_to_goal_ids[rid].append(g.goal_id)
                if g.status_now in {"planned", "partial", "in_progress"}:
                    active_req_ids.add(rid)
        reserved_goal_signatures = {
            self._goal_generation_signature(
                track=g.track,
                requirement_ids=[str(x) for x in g.requirement_ids if str(x).strip()],
                depends_on=[str(x) for x in g.depends_on if str(x).strip()],
            )
            for g in goals
        }

        unmet = [r for r in requirements if r.status_now != "implemented" and r.req_id not in active_req_ids]
        if not unmet:
            return []
        planner_req_priority = self._architect_requirement_priority_map(doc)
        unmet_sorted = sorted(
            unmet,
            key=lambda r: (
                planner_req_priority.get(r.req_id, 10**9),
                0 if r.owner_track == "skeleton" else (1 if r.owner_track == "impl_fetchdata" else 2),
                int(r.source_line or 0),
                r.req_id,
            ),
        )
        implemented_req_ids = {r.req_id for r in requirements if r.status_now == "implemented"}
        bundle_policy_skeleton = self._goal_bundle_policy(doc, track="skeleton")
        skeleton_candidates = [r for r in unmet_sorted if r.owner_track == "skeleton"]
        impl_candidates = [r for r in unmet_sorted if r.owner_track in IMPLEMENT_TRACKS]

        chosen_skeleton = None
        chosen_skeleton_bundle: list[Requirement] = []
        chosen_skeleton_dep_goal_ids: list[str] = []
        for req in skeleton_candidates:
            bundle_reqs = self._pick_requirement_bundle(
                chosen=req,
                unmet_sorted=skeleton_candidates,
                req_by_id=req_by_id,
                ready_req_ids=set(implemented_req_ids),
                policy=bundle_policy_skeleton,
            )
            dep_req_ids = sorted({rid for item in bundle_reqs for rid in item.depends_on_req_ids})
            dep_goal_ids = sorted(
                set(
                    [
                        self._latest_goal_for_requirement(goals, rid)
                        for rid in dep_req_ids
                        if self._latest_goal_for_requirement(goals, rid)
                    ]
                ),
                key=_goal_num,
            )
            signature = self._goal_generation_signature(
                track="skeleton",
                requirement_ids=[x.req_id for x in bundle_reqs],
                depends_on=dep_goal_ids,
            )
            if signature in reserved_goal_signatures:
                continue
            chosen_skeleton = req
            chosen_skeleton_bundle = bundle_reqs
            chosen_skeleton_dep_goal_ids = dep_goal_ids
            reserved_goal_signatures.add(signature)
            break
        ready_req_ids = set(implemented_req_ids) | {x.req_id for x in chosen_skeleton_bundle}
        next_num = self._next_goal_number(goals)
        skeleton_goal_id = f"G{next_num}" if chosen_skeleton else ""
        impl_goal_cursor = next_num + (1 if chosen_skeleton else 0)
        chosen_impl_specs: list[dict[str, Any]] = []
        chosen_impl_parallel_paths: list[list[str]] = []
        for track in sorted(IMPLEMENT_TRACKS):
            track_candidates = [r for r in impl_candidates if r.owner_track == track]
            if not track_candidates:
                continue
            bundle_policy_impl = self._goal_bundle_policy(doc, track=track)
            for req in track_candidates:
                dep_skeleton_req_ids = [
                    rid
                    for rid in req.depends_on_req_ids
                    if req_by_id.get(rid) and req_by_id[rid].owner_track == "skeleton"
                ]
                deps_ready = all(rid in ready_req_ids for rid in dep_skeleton_req_ids)
                if not deps_ready:
                    continue

                bundle_reqs = self._pick_requirement_bundle(
                    chosen=req,
                    unmet_sorted=track_candidates,
                    req_by_id=req_by_id,
                    ready_req_ids=ready_req_ids,
                    policy=bundle_policy_impl,
                )
                dep_goal_ids: list[str] = []
                bundle_dep_ids = sorted({rid for r in bundle_reqs for rid in r.depends_on_req_ids}, key=lambda x: x)
                for rid in bundle_dep_ids:
                    dep_req = req_by_id.get(rid)
                    if not dep_req:
                        continue
                    latest_dep_goal = self._latest_goal_for_requirement(goals, rid)
                    if latest_dep_goal:
                        dep_goal_ids.append(latest_dep_goal)
                    if chosen_skeleton and rid == chosen_skeleton.req_id and skeleton_goal_id:
                        dep_goal_ids.append(skeleton_goal_id)
                dep_goal_ids = sorted(set(dep_goal_ids), key=_goal_num)
                signature = self._goal_generation_signature(
                    track=track,
                    requirement_ids=[x.req_id for x in bundle_reqs],
                    depends_on=dep_goal_ids,
                )
                if signature in reserved_goal_signatures:
                    continue

                trial_goal_id = f"G{impl_goal_cursor}"
                trial_row = self._build_requirement_goal_row(
                    req=req,
                    goal_id=trial_goal_id,
                    depends_on=dep_goal_ids,
                    cluster_id=f"CL_FETCH_{_goal_num(trial_goal_id):03d}",
                    req_bundle=bundle_reqs,
                    ensure_phase_doc=False,
                )
                trial_scope_paths = _parallel_scope_paths(
                    [str(x) for x in (trial_row.get("allowed_paths") or []) if isinstance(x, str)]
                ) or [str(x) for x in (trial_row.get("allowed_paths") or []) if isinstance(x, str)]
                if any(_path_rules_conflict(trial_scope_paths, p) for p in chosen_impl_parallel_paths):
                    continue

                chosen_impl_specs.append(
                    {
                        "goal_id": trial_goal_id,
                        "req": req,
                        "req_bundle": bundle_reqs,
                        "depends_on": dep_goal_ids,
                        "signature": signature,
                    }
                )
                chosen_impl_parallel_paths.append(trial_scope_paths)
                reserved_goal_signatures.add(signature)
                impl_goal_cursor += 1
                break

        if not chosen_skeleton and not chosen_impl_specs:
            return []

        goal_rows = doc.get("goal_checklist") if isinstance(doc.get("goal_checklist"), list) else []
        req_rows = doc.get("requirements_trace_v1") if isinstance(doc.get("requirements_trace_v1"), list) else []
        generated: list[str] = []
        generated_goal_rows: list[dict[str, Any]] = []
        generated_goal_bundle_map: dict[str, list[Requirement]] = {}

        if chosen_skeleton:
            skeleton_bundle_reqs = chosen_skeleton_bundle or [chosen_skeleton]
            dep_goal_ids = chosen_skeleton_dep_goal_ids
            cluster_id = f"CL_FETCH_{_goal_num(skeleton_goal_id):03d}"
            generated_goal_rows.append(
                self._build_requirement_goal_row(
                    req=chosen_skeleton,
                    goal_id=skeleton_goal_id,
                    depends_on=dep_goal_ids,
                    cluster_id=cluster_id,
                    req_bundle=skeleton_bundle_reqs,
                )
            )
            generated.append(skeleton_goal_id)
            generated_goal_bundle_map[skeleton_goal_id] = skeleton_bundle_reqs

        for spec in chosen_impl_specs:
            impl_goal_id = str(spec.get("goal_id") or "")
            req = spec.get("req")
            bundle_reqs = spec.get("req_bundle") or []
            dep_goal_ids = [str(x) for x in (spec.get("depends_on") or []) if isinstance(x, str)]
            if not impl_goal_id or not isinstance(req, Requirement):
                continue
            cluster_num = _goal_num(impl_goal_id)
            cluster_id = f"CL_FETCH_{cluster_num:03d}"
            generated_goal_rows.append(
                self._build_requirement_goal_row(
                    req=req,
                    goal_id=impl_goal_id,
                    depends_on=dep_goal_ids,
                    cluster_id=cluster_id,
                    req_bundle=[x for x in bundle_reqs if isinstance(x, Requirement)] or [req],
                )
            )
            generated.append(impl_goal_id)
            generated_goal_bundle_map[impl_goal_id] = [x for x in bundle_reqs if isinstance(x, Requirement)] or [req]

        if not generated_goal_rows:
            return []

        todo_policy = self._goal_todo_planner_policy(doc)
        for row in generated_goal_rows:
            if not isinstance(row, dict):
                continue
            gid = str(row.get("id") or "")
            bundle = generated_goal_bundle_map.get(gid, [])
            deps = [str(x) for x in (row.get("depends_on") or []) if isinstance(x, str)]
            acceptance_commands = [str(x) for x in (row.get("acceptance_commands") or []) if isinstance(x, str)]
            max_items = int(todo_policy.get("max_items_per_section", 6))
            todo_payload = self._rule_based_goal_todo(
                goal_id=gid,
                track=str(row.get("track") or ""),
                req_bundle=bundle,
                depends_on=deps,
                acceptance_commands=acceptance_commands,
                max_items=max_items,
            )
            if bool(todo_policy.get("enabled", True)) and str(todo_policy.get("mode") or "") == "codex_assisted":
                use_codex = (not self.dry_run) and self.subagent_mode == "codex_exec"
                if use_codex:
                    codex_payload, fail_reason = self._codex_goal_todo_plan(
                        doc=doc,
                        goal_id=gid,
                        track=str(row.get("track") or ""),
                        req_bundle=bundle,
                        depends_on=deps,
                        acceptance_commands=acceptance_commands,
                        max_items=max_items,
                        timeout_sec=int(todo_policy.get("codex_timeout_sec", 240)),
                    )
                    if codex_payload:
                        todo_payload = codex_payload
                    else:
                        if bool(todo_policy.get("require_codex_for_planning", False)):
                            row["status_now"] = "blocked"
                            row["notes"] = [f"todo planner blocked: {fail_reason or 'unknown'}"]
                        planner_meta = todo_payload.get("todo_planner", {})
                        if isinstance(planner_meta, dict):
                            planner_meta["fallback_reason"] = fail_reason or "codex_planner_failed"
                            todo_payload["todo_planner"] = planner_meta
                else:
                    planner_meta = todo_payload.get("todo_planner", {})
                    if isinstance(planner_meta, dict):
                        planner_meta["fallback_reason"] = "dry_run_or_non_codex_mode"
                        todo_payload["todo_planner"] = planner_meta
            row["todo_checklist"] = [str(x) for x in (todo_payload.get("todo_checklist") or []) if isinstance(x, str)]
            row["risk_notes"] = [str(x) for x in (todo_payload.get("risk_notes") or []) if isinstance(x, str)]
            row["parallel_hints"] = [str(x) for x in (todo_payload.get("parallel_hints") or []) if isinstance(x, str)]
            row["todo_planner"] = (
                todo_payload.get("todo_planner")
                if isinstance(todo_payload.get("todo_planner"), dict)
                else {}
            )

        for row in generated_goal_rows:
            goal_rows.append(row)
        self._apply_goal_skill_reasoning_fields(doc, goal_rows)
        doc["goal_checklist"] = goal_rows

        for gid, row in zip(generated, generated_goal_rows):
            req_ids = [str(x) for x in (row.get("requirement_ids") or []) if isinstance(x, str)]
            for req_id in req_ids:
                if not req_id:
                    continue
                req_row = self._requirement_row(doc, req_id)
                if not req_row:
                    continue
                mapped = [str(x) for x in (req_row.get("mapped_goal_ids") or []) if isinstance(x, str)]
                req_row["mapped_goal_ids"] = sorted(set(mapped + [gid]), key=_goal_num)
                req_row["status_now"] = "planned"
                req_row["acceptance_verified"] = bool(req_row.get("acceptance_verified", False))

        doc["requirements_trace_v1"] = req_rows
        return generated

    @staticmethod
    def _goal_row_by_id(doc: dict[str, Any], goal_id: str) -> dict[str, Any] | None:
        rows = doc.get("goal_checklist")
        if not isinstance(rows, list):
            return None
        for row in rows:
            if isinstance(row, dict) and str(row.get("id") or "") == goal_id:
                return row
        return None

    def _max_attempts_per_goal(self, doc: dict[str, Any], goal: Goal) -> int:
        wv = doc.get("whole_view_autopilot_v1") if isinstance(doc.get("whole_view_autopilot_v1"), dict) else {}
        fp = wv.get("failure_policy") if isinstance(wv.get("failure_policy"), dict) else {}
        retry = fp.get("retry") if isinstance(fp.get("retry"), dict) else {}
        base = max(1, int(retry.get("max_attempts_per_phase") or 2))
        reasoning_retry = max(1, int(self._goal_reasoning_profile(doc, goal).get("retry") or 2))
        return max(base, reasoning_retry)

    def _build_goal_from_row(self, row: dict[str, Any]) -> Goal:
        return Goal(
            goal_id=str(row.get("id") or ""),
            status_now=str(row.get("status_now") or "").strip(),
            track=str(row.get("track") or "").strip(),
            title=str(row.get("title") or "").strip(),
            depends_on=[str(x) for x in (row.get("depends_on") or []) if isinstance(x, str)],
            requirement_ids=[str(x) for x in (row.get("requirement_ids") or []) if isinstance(x, str)],
            allowed_paths=[str(x) for x in (row.get("allowed_paths") or []) if isinstance(x, str)],
            acceptance_commands=[
                str(x)
                for x in (
                    row.get("acceptance_commands")
                    or (row.get("acceptance", {}).get("commands") if isinstance(row.get("acceptance"), dict) else [])
                    or []
                )
                if isinstance(x, str)
            ],
            stop_scope=row.get("stop_condition_exception_scope")
            if isinstance(row.get("stop_condition_exception_scope"), dict)
            else {},
            phase_doc_path=str(row.get("phase_doc_path") or ""),
            capability_cluster_id=str(row.get("capability_cluster_id") or ""),
            required_skills=[str(x) for x in (row.get("required_skills") or []) if isinstance(x, str)],
            difficulty_score=int(row.get("difficulty_score") or 0)
            if str(row.get("difficulty_score") or "").strip().lstrip("-").isdigit()
            else 0,
            reasoning_tier=self._normalize_reasoning_tier(str(row.get("reasoning_tier") or "")),
            todo_checklist=[str(x) for x in (row.get("todo_checklist") or []) if isinstance(x, str)],
            risk_notes=[str(x) for x in (row.get("risk_notes") or []) if isinstance(x, str)],
            parallel_hints=[str(x) for x in (row.get("parallel_hints") or []) if isinstance(x, str)],
            todo_planner=row.get("todo_planner") if isinstance(row.get("todo_planner"), dict) else {},
            allow_noop=bool(row.get("allow_noop", False)),
            raw=row,
        )

    def _writeback_requirement_status_for_goal(self, doc: dict[str, Any], goal: Goal, *, accepted: bool) -> None:
        req_rows = doc.get("requirements_trace_v1")
        if not isinstance(req_rows, list):
            return
        goal_ids_by_req: dict[str, set[str]] = defaultdict(set)
        for g in self.parse_goals(doc):
            for rid in g.requirement_ids:
                goal_ids_by_req[rid].add(g.goal_id)
        goals_by_id = {g.goal_id: g for g in self.parse_goals(doc)}

        for row in req_rows:
            if not isinstance(row, dict):
                continue
            req_id = str(row.get("req_id") or "")
            if not req_id:
                continue
            mapped = [str(x) for x in (row.get("mapped_goal_ids") or []) if isinstance(x, str)]
            explicit = sorted(goal_ids_by_req.get(req_id, set()), key=_goal_num)
            row["mapped_goal_ids"] = sorted(set(mapped + explicit), key=_goal_num)
            if goal.goal_id not in row["mapped_goal_ids"]:
                continue
            if accepted:
                row["acceptance_verified"] = True
            all_done = bool(row["mapped_goal_ids"]) and all(
                goals_by_id.get(gid) and goals_by_id[gid].status_now == "implemented"
                for gid in row["mapped_goal_ids"]
            )
            row["status_now"] = "implemented" if all_done and bool(row.get("acceptance_verified", False)) else "planned"

    def _packet_prefix_for_goal(self, goal_id: str) -> str:
        p = self.packet_root / goal_id
        try:
            rel = p.relative_to(self.repo_root).as_posix()
        except ValueError:
            rel = p.as_posix()
        return _norm_path(rel)

    def _is_packet_internal_path(self, path: str, goal_id: str) -> bool:
        packet_prefix = self._packet_prefix_for_goal(goal_id)
        p = _norm_path(path)
        return bool(packet_prefix) and (p == packet_prefix or p.startswith(packet_prefix + "/"))

    def _git_dirty_file_hashes(self) -> dict[str, str]:
        res = self.run_command("git status --porcelain --untracked-files=all", timeout_sec=120)
        if res.exit_code != 0:
            return {}
        paths: set[str] = set()
        for line in res.stdout.splitlines():
            ln = line.rstrip()
            if len(ln) < 4:
                continue
            raw = ln[3:]
            if " -> " in raw:
                raw = raw.split(" -> ", 1)[1]
            p = _norm_path(raw)
            if p:
                paths.add(p)
        out: dict[str, str] = {}
        for rel in sorted(paths):
            abs_path = self.repo_root / rel
            if abs_path.is_file():
                try:
                    out[rel] = _sha256_file(abs_path)
                except Exception:
                    out[rel] = "<UNREADABLE>"
            elif abs_path.exists():
                out[rel] = "<NON_FILE>"
            else:
                out[rel] = "<MISSING>"
        return out

    @staticmethod
    def _dirty_delta_paths(before: dict[str, str], after: dict[str, str]) -> list[str]:
        keys = set(before) | set(after)
        return sorted([k for k in keys if before.get(k) != after.get(k)])

    def _build_subagent_prompt(
        self,
        goal: Goal,
        *,
        allowed_paths: list[str],
        acceptance_commands: list[str],
        required_skills: list[str],
        reasoning_profile: dict[str, Any],
    ) -> str:
        preauth = goal.stop_scope.get("preauthorized_scope") if isinstance(goal.stop_scope, dict) else {}
        still_forbidden = preauth.get("still_forbidden") if isinstance(preauth, dict) else []
        forbidden = [str(x) for x in still_forbidden if isinstance(x, str)] or [
            "contracts/**",
            "policies/**",
            "Holdout visibility expansion",
        ]
        lines = [
            f"You are the Codex CLI subagent for phase {goal.goal_id}.",
            "",
            "Task:",
            f"- Goal ID: {goal.goal_id}",
            f"- Title: {goal.title}",
            f"- Track: {goal.track}",
            f"- Phase Doc: {goal.phase_doc_path}",
            f"- Difficulty Score: {goal.difficulty_score}",
            f"- Reasoning Tier: {reasoning_profile.get('tier')}",
            "",
            "Scope constraints:",
            "- Modify files only under allowed_paths.",
            "- Do not commit, do not push, do not create branches.",
            "- Do not modify contracts/policies/Holdout scope.",
            "- Never rename/delete docs/12_workflows/skeleton_ssot_v1.yaml; edit in place only when needed.",
            "- If duplicate-named docs exist outside allowed_paths, do not touch them.",
            "",
            "allowed_paths:",
        ]
        lines.extend([f"- {x}" for x in allowed_paths])
        lines.extend(
            [
                "",
                "still_forbidden:",
            ]
        )
        lines.extend([f"- {x}" for x in forbidden])
        lines.extend(
            [
                "",
                "Required Skills (must apply and report in output):",
            ]
        )
        lines.extend([f"- {x}" for x in required_skills] or ["- (none declared)"])
        lines.extend(
            [
                "",
                "Reasoning profile:",
                f"- model: {reasoning_profile.get('model') or '(codex default)'}",
                f"- timeout_sec: {reasoning_profile.get('timeout_sec')}",
                f"- retry: {reasoning_profile.get('retry')}",
            ]
        )
        if goal.todo_checklist:
            lines.extend(["", "Execution TODO checklist:"])
            lines.extend([f"- {x}" for x in goal.todo_checklist])
        if goal.risk_notes:
            lines.extend(["", "Known risks to control:"])
            lines.extend([f"- {x}" for x in goal.risk_notes])
        if goal.parallel_hints:
            lines.extend(["", "Parallelization hints:"])
            lines.extend([f"- {x}" for x in goal.parallel_hints])
        lines.extend(["", "Acceptance commands that orchestrator will run after your edits:"])
        lines.extend([f"- {x}" for x in acceptance_commands])
        lines.extend(
            [
                "",
                "Expected output:",
                "- Apply concrete repository changes under allowed_paths.",
                "- Keep changes minimal and deterministic.",
                "- Include a line: `Skills Used: <comma-separated skill ids>`.",
                "- End with a short summary of changed files.",
            ]
        )
        return "\n".join(lines).rstrip() + "\n"

    def _build_codex_exec_argv(self, *, output_last_message_path: Path, model: str | None) -> list[str]:
        argv = ["codex", "exec", "--cd", str(self.repo_root), "--full-auto"]
        if model:
            argv.extend(["--model", model])
        if self.codex_json_log:
            argv.append("--json")
        argv.extend(["-o", str(output_last_message_path)])
        return argv

    @staticmethod
    def _extract_skill_usage(
        *,
        required_skills: list[str],
        codex_events: str,
        codex_last_message: str,
        changed_files: list[str],
    ) -> tuple[list[str], list[dict[str, Any]]]:
        text = "\n".join([codex_events or "", codex_last_message or ""])
        lines = text.splitlines()
        used: set[str] = set()
        evidence: list[dict[str, Any]] = []
        for skill in required_skills:
            pattern = re.compile(rf"\b{re.escape(skill)}\b", re.IGNORECASE)
            matched_line = next((ln.strip() for ln in lines if pattern.search(ln)), "")
            if matched_line:
                used.add(skill)
                evidence.append(
                    {
                        "skill": skill,
                        "source": "codex_output",
                        "snippet": matched_line[:240],
                    }
                )
                continue

            inferred = False
            if skill == "phase-authoring" and any(_match_rule(p, "docs/08_phases/**") for p in changed_files):
                inferred = True
            elif skill == "packet-evidence-guard" and any(
                _match_rule(p, "artifacts/subagent_control/**") for p in changed_files
            ):
                inferred = True
            elif skill == "requirement-splitter" and any(
                _match_rule(p, "docs/12_workflows/requirement_splitter_profiles_v1.yaml") for p in changed_files
            ):
                inferred = True
            elif skill == "ssot-goal-planner" and any(
                _match_rule(p, "docs/12_workflows/skeleton_ssot_v1.yaml") for p in changed_files
            ):
                inferred = True
            if inferred:
                used.add(skill)
                evidence.append(
                    {
                        "skill": skill,
                        "source": "changed_files_inference",
                        "snippet": "inferred from changed file set",
                    }
                )

        return sorted(used), evidence

    def _dispatch_goal_once(self, doc: dict[str, Any], goal: Goal, *, attempt: int) -> tuple[bool, dict[str, Any]]:
        packet_dir = self.packet_root / goal.goal_id
        packet_dir.mkdir(parents=True, exist_ok=True)

        acceptance_commands = goal.acceptance_commands or ["python3 scripts/check_docs_tree.py"]
        allowed_paths = goal.allowed_paths or [goal.phase_doc_path]
        task_path = packet_dir / "task_card.yaml"
        prompt_path = packet_dir / "task_prompt.md"
        wb_path = packet_dir / "workspace_before.json"
        wa_path = packet_dir / "workspace_after.json"
        acceptance_log_path = packet_dir / "acceptance_run_log.jsonl"
        exe_path = packet_dir / "executor_report.yaml"
        val_path = packet_dir / "validator_report.yaml"
        codex_events_log_path = packet_dir / "codex_events.log"
        codex_last_message_path = packet_dir / "codex_last_message.txt"
        codex_stderr_path = packet_dir / "codex_stderr.log"

        def _rel(path: Path) -> str:
            try:
                return path.relative_to(self.repo_root).as_posix()
            except ValueError:
                return path.as_posix()

        required_skills = goal.required_skills or self._track_required_skills(doc, goal.track)
        reasoning_profile = self._goal_reasoning_profile(doc, goal)
        skill_enforcement_mode = self._skill_enforcement_from_doc(doc)
        skill_registry = self._skill_registry_from_doc(doc)
        skill_paths = {sid: skill_registry.get(sid, f"skills/{sid}") for sid in required_skills}
        skills_available: dict[str, bool] = {}
        for sid, rel_path in skill_paths.items():
            abs_path = self.repo_root / rel_path
            skills_available[sid] = abs_path.is_dir() and (abs_path / "SKILL.md").is_file()

        codex_argv = self._build_codex_exec_argv(
            output_last_message_path=codex_last_message_path,
            model=str(reasoning_profile.get("model") or "").strip() or None,
        )
        prompt_text = self._build_subagent_prompt(
            goal,
            allowed_paths=allowed_paths,
            acceptance_commands=acceptance_commands,
            required_skills=required_skills,
            reasoning_profile=reasoning_profile,
        )
        prompt_path.write_text(prompt_text, encoding="utf-8")

        task = {
            "schema_version": "subagent_task_card_v1",
            "phase_id": goal.goal_id,
            "goal_ids": [goal.goal_id],
            "published_at": _utc_now(),
            "published_by": "orchestrator_codex",
            "executor_required": "codex_cli_subagent",
            "evidence_policy": "hardened",
            "evidence_files": {
                "workspace_before": _rel(wb_path),
                "workspace_after": _rel(wa_path),
                "acceptance_log": _rel(acceptance_log_path),
                "codex_events_log": _rel(codex_events_log_path),
                "codex_last_message": _rel(codex_last_message_path),
            },
            "external_noise_paths": [],
            "allowed_paths": allowed_paths,
            "allow_noop": bool(goal.allow_noop),
            "acceptance_commands": acceptance_commands,
            "required_skills": required_skills,
            "skill_registry_snapshot": skill_paths,
            "skill_enforcement_mode": skill_enforcement_mode,
            "reasoning_tier": str(reasoning_profile.get("tier") or goal.reasoning_tier or ""),
            "reasoning_profile": {
                "model": str(reasoning_profile.get("model") or ""),
                "timeout_sec": int(reasoning_profile.get("timeout_sec") or self.codex_timeout_sec),
                "retry": int(reasoning_profile.get("retry") or 2),
            },
            "subagent": {
                "execution_mode": self.subagent_mode,
                "codex_args": codex_argv,
                "prompt_file": _rel(prompt_path),
            },
            "published_context": {
                "attempt": attempt,
                "track": goal.track,
                "phase_doc_path": goal.phase_doc_path,
            },
        }
        task_path.write_text(yaml.safe_dump(task, allow_unicode=True, sort_keys=False), encoding="utf-8")

        before_files: dict[str, str] = {}
        for p in [task_path, prompt_path]:
            rel = _rel(p)
            if p.is_file():
                before_files[rel] = _sha256_file(p)
        wb_path.write_text(
            json.dumps(self._snapshot_payload(before_files), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        dirty_before = self._git_dirty_file_hashes()
        subagent_result: CommandResult
        codex_invoked = self.subagent_mode == "codex_exec"
        if self.subagent_mode == "codex_exec":
            subagent_result = self.run_command_argv(
                codex_argv,
                timeout_sec=int(reasoning_profile.get("timeout_sec") or self.codex_timeout_sec),
                input_text=prompt_text,
            )
            codex_events_log_path.write_text(subagent_result.stdout or "", encoding="utf-8")
            codex_stderr_path.write_text(subagent_result.stderr or "", encoding="utf-8")
            if not codex_last_message_path.exists():
                codex_last_message_path.write_text("", encoding="utf-8")
        else:
            subagent_result = CommandResult(
                command="acceptance_only://skip_codex_exec",
                exit_code=0,
                stdout="",
                stderr="",
            )
            self.commands.append(subagent_result)
            codex_events_log_path.write_text(
                "acceptance_only mode: codex exec skipped by operator option.\n",
                encoding="utf-8",
            )
            codex_stderr_path.write_text("", encoding="utf-8")
            codex_last_message_path.write_text(
                "acceptance_only mode: no codex output.\n",
                encoding="utf-8",
            )
        dirty_after = self._git_dirty_file_hashes()
        touched_paths = self._dirty_delta_paths(dirty_before, dirty_after)
        changed_files = sorted([p for p in touched_paths if not self._is_packet_internal_path(p, goal.goal_id)])
        codex_last_message_text = codex_last_message_path.read_text(encoding="utf-8") if codex_last_message_path.exists() else ""
        skills_used, skill_usage_evidence = self._extract_skill_usage(
            required_skills=required_skills,
            codex_events=subagent_result.stdout or "",
            codex_last_message=codex_last_message_text,
            changed_files=changed_files,
        )
        skills_declared_ok = bool(required_skills)
        skills_available_ok = all(skills_available.get(sid, False) for sid in required_skills)
        skills_invoked_ok = set(required_skills).issubset(set(skills_used))
        reasoning_tier_applied_ok = (
            self._normalize_reasoning_tier(str(task.get("reasoning_tier") or ""))
            == self._normalize_reasoning_tier(str(reasoning_profile.get("tier") or ""))
        )
        allowed_paths_ok = all(any(_match_rule(p, rule) for rule in allowed_paths) for p in changed_files)
        changed_files_non_empty = bool(changed_files) or goal.allow_noop
        stop_conditions = self._evaluate_stop_conditions(
            doc=doc,
            changed_files=changed_files,
            goals=[goal],
            context={"phase_id": goal.goal_id, "attempt": attempt, "stage": "dispatch"},
        )
        self._append_decision_log(doc, [x for x in stop_conditions.get("decision_entries", []) if isinstance(x, dict)])
        codex_ok = subagent_result.exit_code == 0
        skill_checks_pass = (
            skills_declared_ok and skills_available_ok and skills_invoked_ok and reasoning_tier_applied_ok
        )
        strict_gate_before_packet = (
            codex_invoked
            and codex_ok
            and changed_files_non_empty
            and allowed_paths_ok
            and bool(stop_conditions.get("pass", False))
            and (skill_checks_pass or skill_enforcement_mode != "enforce")
        )

        run_rows: list[dict[str, Any]] = []
        commands_run: list[str] = [subagent_result.command]
        acceptance_ok = True
        for cmd in acceptance_commands:
            started = _utc_now()
            res = self.run_command(cmd, timeout_sec=1800)
            ended = _utc_now()
            commands_run.append(cmd)
            run_rows.append(
                {
                    "role": "validator",
                    "command": cmd,
                    "exit_code": res.exit_code,
                    "started_at": started,
                    "ended_at": ended,
                    "stdout_tail": res.stdout.strip()[-300:],
                    "stderr_tail": res.stderr.strip()[-300:],
                }
            )
            if res.exit_code != 0:
                acceptance_ok = False

        acceptance_log_path.write_text(
            "\n".join(json.dumps(x, ensure_ascii=False, sort_keys=True) for x in run_rows) + ("\n" if run_rows else ""),
            encoding="utf-8",
        )

        exe = {
            "schema_version": "subagent_executor_report_v1",
            "phase_id": goal.goal_id,
            "reported_at": _utc_now(),
            "executor": {"role": "codex_cli_subagent", "runtime": "codex_cli"},
            "status": "completed" if (strict_gate_before_packet and acceptance_ok) else "failed",
            "changed_files": changed_files,
            "commands_run": commands_run,
            "skills_required": required_skills,
            "skills_used": skills_used,
            "skill_usage_evidence": skill_usage_evidence,
            "reasoning_tier": str(reasoning_profile.get("tier") or ""),
            "reasoning_runtime": {
                "model": str(reasoning_profile.get("model") or ""),
                "timeout_sec": int(reasoning_profile.get("timeout_sec") or self.codex_timeout_sec),
                "retry": int(reasoning_profile.get("retry") or 2),
                "attempt": attempt,
            },
            "evidence_summary": {
                "workspace_before": task["evidence_files"]["workspace_before"],
                "workspace_after": task["evidence_files"]["workspace_after"],
                "acceptance_log": task["evidence_files"]["acceptance_log"],
                "codex_events_log": task["evidence_files"]["codex_events_log"],
                "codex_last_message": task["evidence_files"]["codex_last_message"],
                "codex_stderr_log": _rel(codex_stderr_path),
            },
            "notes": [
                f"controller dispatch attempt {attempt}",
                f"subagent_mode={self.subagent_mode}",
            ],
        }
        exe_path.write_text(yaml.safe_dump(exe, allow_unicode=True, sort_keys=False), encoding="utf-8")

        checks = [
            {"name": "task_card_published", "pass": True, "detail": "task card exists"},
            {"name": "executor_is_codex_cli", "pass": True, "detail": "executor role/runtime fixed"},
            {
                "name": "codex_invoked",
                "pass": codex_invoked,
                "detail": "subagent command must execute through codex exec",
            },
            {
                "name": "changed_files_non_empty",
                "pass": changed_files_non_empty,
                "detail": "subagent must produce at least one non-packet file change unless allow_noop=true",
            },
            {
                "name": "changed_files_within_allowed_paths",
                "pass": allowed_paths_ok,
                "detail": "all non-packet changed files must remain inside allowed_paths",
            },
            {
                "name": "stop_conditions_respected",
                "pass": bool(stop_conditions.get("pass", False)),
                "detail": "stop-condition redlines must be blocked or explicitly waived via policy/audited exceptions",
            },
            {"name": "allowed_paths_only", "pass": allowed_paths_ok, "detail": "no out-of-scope file changes detected"},
            {
                "name": "acceptance_commands_executed",
                "pass": acceptance_ok,
                "detail": "all acceptance commands must succeed",
            },
            {"name": "ssot_updated", "pass": True, "detail": "controller will write status to SSOT"},
            {
                "name": "skills_declared",
                "pass": skills_declared_ok,
                "detail": "task card declares required_skills",
            },
            {
                "name": "skills_available",
                "pass": skills_available_ok,
                "detail": "all required skills exist under configured skill registry path",
            },
            {
                "name": "skills_invoked",
                "pass": skills_invoked_ok,
                "detail": "executor report includes skills_used coverage with evidence",
            },
            {
                "name": "reasoning_tier_applied",
                "pass": reasoning_tier_applied_ok,
                "detail": "task card reasoning_tier matches executor report reasoning_tier",
            },
        ]
        skill_check_names = {
            "skills_declared",
            "skills_available",
            "skills_invoked",
            "reasoning_tier_applied",
        }
        failed_checks = [x for x in checks if not bool(x.get("pass"))]
        hard_fail_checks = [
            x
            for x in failed_checks
            if skill_enforcement_mode == "enforce" or str(x.get("name") or "") not in skill_check_names
        ]
        validator_pass = not hard_fail_checks
        val = {
            "schema_version": "subagent_validator_report_v1",
            "phase_id": goal.goal_id,
            "reported_at": _utc_now(),
            "validator": {"role": "orchestrator_codex"},
            "status": "pass" if validator_pass else "fail",
            "checks": checks,
            "notes": [
                f"controller dispatch attempt {attempt}",
                f"skill_enforcement_mode={skill_enforcement_mode}",
            ],
        }
        if skill_enforcement_mode == "warn":
            soft_fail_names = [str(x.get("name") or "") for x in failed_checks if str(x.get("name") or "") in skill_check_names]
            if soft_fail_names:
                val["notes"].append(f"soft skill warnings: {soft_fail_names}")
        val_path.write_text(yaml.safe_dump(val, allow_unicode=True, sort_keys=False), encoding="utf-8")

        def _is_hex64(v: str) -> bool:
            return bool(re.fullmatch(r"[0-9a-f]{64}", str(v).strip().lower()))

        after_files: dict[str, str] = {}
        for p in [
            task_path,
            prompt_path,
            wb_path,
            acceptance_log_path,
            codex_events_log_path,
            codex_last_message_path,
            codex_stderr_path,
            exe_path,
            val_path,
        ]:
            rel = _rel(p)
            if p.is_file():
                after_files[rel] = _sha256_file(p)

        # Include non-packet changed files in workspace snapshots so hardened packet
        # validation can reconcile reported changed_files with actual workspace diff.
        for rel in changed_files:
            b = str(dirty_before.get(rel) or "").strip().lower()
            a = str(dirty_after.get(rel) or "").strip().lower()
            if _is_hex64(b):
                before_files[rel] = b
            if _is_hex64(a):
                after_files[rel] = a
                continue
            abs_path = self.repo_root / rel
            if abs_path.is_file():
                try:
                    after_files[rel] = _sha256_file(abs_path)
                except Exception:
                    pass

        wb_path.write_text(
            json.dumps(self._snapshot_payload(before_files), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        wa_path.write_text(
            json.dumps(self._snapshot_payload(after_files), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        checker_cmd = f"python3 scripts/check_subagent_packet.py --phase-id {goal.goal_id}"
        checker = self.run_command(checker_cmd, timeout_sec=600)
        packet_ok = checker.exit_code == 0
        passed = strict_gate_before_packet and acceptance_ok and packet_ok
        return passed, {
            "goal_id": goal.goal_id,
            "attempt": attempt,
            "codex_invoked": codex_invoked,
            "codex_ok": codex_ok,
            "changed_files_non_empty": changed_files_non_empty,
            "allowed_paths_ok": allowed_paths_ok,
            "changed_files": changed_files,
            "acceptance_ok": acceptance_ok,
            "packet_ok": packet_ok,
            "checker_exit_code": checker.exit_code,
            "packet_path": _rel(packet_dir),
            "stop_conditions_ok": bool(stop_conditions.get("pass", False)),
            "skill_enforcement_mode": skill_enforcement_mode,
            "required_skills": required_skills,
            "skills_used": skills_used,
            "skills_declared_ok": skills_declared_ok,
            "skills_available_ok": skills_available_ok,
            "skills_invoked_ok": skills_invoked_ok,
            "reasoning_tier": str(reasoning_profile.get("tier") or ""),
            "reasoning_tier_applied_ok": reasoning_tier_applied_ok,
            "stop_condition_report": {
                "violations": stop_conditions.get("violations", []),
                "waivers": stop_conditions.get("waivers", []),
                "auto_policy_enabled": stop_conditions.get("auto_policy_enabled", False),
                "auto_waivable_conditions": stop_conditions.get("auto_waivable_conditions", []),
            },
        }

    def _execute_goal_with_retries(self, doc: dict[str, Any], goal_id: str) -> dict[str, Any]:
        row = self._goal_row_by_id(doc, goal_id)
        if row is None:
            return {"goal_id": goal_id, "status": "blocked", "reason": "goal_missing"}
        goal_seed = self._build_goal_from_row(row)
        max_attempts = self._max_attempts_per_goal(doc, goal_seed)
        notes = row.get("notes") if isinstance(row.get("notes"), list) else []

        for attempt in range(1, max_attempts + 1):
            goal = self._build_goal_from_row(row)
            passed, detail = self._dispatch_goal_once(doc, goal, attempt=attempt)
            if passed:
                row["status_now"] = "implemented"
                self._writeback_requirement_status_for_goal(doc, goal, accepted=True)
                notes.append(
                    f"Implemented by controller lifecycle on {_utc_now()} after attempt {attempt}; packet {goal.goal_id} validated."
                )
                row["notes"] = notes
                return {"goal_id": goal_id, "status": "implemented", "attempts": attempt, "detail": detail}
            notes.append(
                "Attempt "
                + str(attempt)
                + f" failed on {_utc_now()}: "
                + f"codex_invoked={detail.get('codex_invoked')} "
                + f"codex_ok={detail.get('codex_ok')} "
                + f"changed_files_non_empty={detail.get('changed_files_non_empty')} "
                + f"allowed_paths_ok={detail.get('allowed_paths_ok')} "
                + f"stop_conditions_ok={detail.get('stop_conditions_ok')} "
                + f"acceptance_ok={detail.get('acceptance_ok')} "
                + f"packet_ok={detail.get('packet_ok')}"
            )
            row["notes"] = notes

        row["status_now"] = "blocked"
        self._writeback_requirement_status_for_goal(doc, self._build_goal_from_row(row), accepted=False)
        notes.append(f"Marked blocked after {max_attempts} attempts on {_utc_now()}.")
        row["notes"] = notes
        return {"goal_id": goal_id, "status": "blocked", "attempts": max_attempts}

    def _latest_phase_for_cluster(self, cluster: dict[str, Any]) -> str:
        if self.latest_phase_id_override:
            return self.latest_phase_id_override
        phase = str(cluster.get("latest_phase_id") or "")
        if phase:
            return phase
        goal_ids = [str(x) for x in (cluster.get("goal_ids") or []) if isinstance(x, str)]
        return max(goal_ids, key=_goal_num) if goal_ids else ""

    def _cluster_requirements_status_ok(self, cluster: dict[str, Any], req_by_id: dict[str, Requirement]) -> bool:
        req_ids = [str(x) for x in (cluster.get("requirement_ids") or []) if isinstance(x, str)]
        if not req_ids:
            return False
        return all(req_by_id.get(rid) and req_by_id[rid].status_now == "implemented" for rid in req_ids)

    def _cluster_goals_status_ok(self, cluster: dict[str, Any], goals_by_id: dict[str, Goal]) -> bool:
        goal_ids = [str(x) for x in (cluster.get("goal_ids") or []) if isinstance(x, str)]
        if not goal_ids:
            return False
        return all(goals_by_id.get(gid) and goals_by_id[gid].status_now == "implemented" for gid in goal_ids)

    def _run_acceptance_commands(self, commands: list[str]) -> tuple[bool, list[dict[str, Any]]]:
        rows: list[dict[str, Any]] = []
        ok = True
        for cmd in commands:
            started = _utc_now()
            res = self.run_command(cmd, timeout_sec=1200)
            ended = _utc_now()
            rows.append(
                {
                    "command": cmd,
                    "exit_code": res.exit_code,
                    "started_at": started,
                    "ended_at": ended,
                    "stdout_tail": res.stdout.strip()[-300:],
                    "stderr_tail": res.stderr.strip()[-300:],
                }
            )
            if res.exit_code != 0:
                ok = False
        return ok, rows

    @staticmethod
    def _extract_changed_files(status_output: str) -> list[str]:
        out: list[str] = []
        for raw in status_output.splitlines():
            ln = raw.rstrip()
            if not ln:
                continue
            # porcelain: XY <path> or XY <old> -> <new>
            payload = ln[3:] if len(ln) > 3 else ""
            if " -> " in payload:
                payload = payload.split(" -> ", 1)[1]
            path = _norm_path(payload)
            if path:
                out.append(path)
        return sorted(set(out))

    @staticmethod
    def _expanded_commit_files(changed_files: list[str], whitelist_rules: list[str]) -> list[str]:
        return sorted({p for p in changed_files if any(_match_rule(p, r) for r in whitelist_rules)})

    @staticmethod
    def _autonomous_waiver_policy(doc: dict[str, Any]) -> tuple[bool, set[str]]:
        wv = doc.get("whole_view_autopilot_v1") if isinstance(doc.get("whole_view_autopilot_v1"), dict) else {}
        auto = wv.get("autonomous_decision_policy_v1") if isinstance(wv.get("autonomous_decision_policy_v1"), dict) else {}
        if str(auto.get("status_now") or "").strip() != "active":
            return False, set()
        mode = str(auto.get("stop_condition_override_decision") or "").strip()
        if mode not in {"controller_auto_with_audit", "controller_auto"}:
            return False, set()
        waivable = {
            str(x).strip()
            for x in (auto.get("auto_waivable_stop_conditions") or [])
            if isinstance(x, str) and str(x).strip()
        }
        return True, waivable

    @staticmethod
    def _goal_waived_conditions(goals: list[Goal]) -> set[str]:
        out: set[str] = set()
        for g in goals:
            scope = g.stop_scope if isinstance(g.stop_scope, dict) else {}
            for c in (scope.get("waives_stop_condition") or []):
                if isinstance(c, str) and c.strip():
                    out.add(c.strip())
        return out

    @staticmethod
    def _detect_stop_condition_hits(changed_files: list[str]) -> dict[str, list[str]]:
        hits: dict[str, set[str]] = defaultdict(set)
        for raw in changed_files:
            p = _norm_path(raw)
            if not p:
                continue
            if _match_rule(p, "contracts/**"):
                hits[STOP_CONDITION_CONTRACTS].add(p)
            if _match_rule(p, "policies/**"):
                hits[STOP_CONDITION_POLICIES].add(p)
            if "holdout" in p.lower():
                hits[STOP_CONDITION_HOLDOUT].add(p)
            if any(_match_rule(p, rule) for rule in API_ROUTE_TOUCH_PATTERNS):
                hits[STOP_CONDITION_API].add(p)
        return {k: sorted(v) for k, v in hits.items()}

    def _evaluate_stop_conditions(
        self,
        *,
        doc: dict[str, Any],
        changed_files: list[str],
        goals: list[Goal],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ctx = context or {}
        hits = self._detect_stop_condition_hits(changed_files)
        exception_rules = self._exception_rules_from_goals(goals)
        goal_waived = self._goal_waived_conditions(goals)
        auto_enabled, auto_waivable = self._autonomous_waiver_policy(doc)

        violations: list[dict[str, Any]] = []
        waivers: list[dict[str, Any]] = []
        decisions: list[dict[str, Any]] = []
        for condition, files in hits.items():
            protected_files = []
            exempted_by_path = []
            for path in files:
                if any(_match_rule(path, r) for r in exception_rules):
                    exempted_by_path.append(path)
                else:
                    protected_files.append(path)
            if exempted_by_path:
                waivers.append(
                    {
                        "condition": condition,
                        "files": sorted(exempted_by_path),
                        "waived_by": "goal_path_exception",
                    }
                )
            if not protected_files:
                continue
            if condition in goal_waived:
                waivers.append(
                    {
                        "condition": condition,
                        "files": sorted(protected_files),
                        "waived_by": "goal_condition_exception",
                    }
                )
                continue
            if auto_enabled and condition in auto_waivable:
                row = {
                    "condition": condition,
                    "files": sorted(protected_files),
                    "waived_by": "autonomous_policy",
                }
                waivers.append(row)
                decisions.append(
                    {
                        "recorded_at": _utc_now(),
                        "decision_type": "auto_stop_condition_waiver",
                        "condition": condition,
                        "files": sorted(protected_files),
                        "context": ctx,
                    }
                )
                continue
            violation = {"condition": condition, "files": sorted(protected_files)}
            violations.append(violation)
            decisions.append(
                {
                    "recorded_at": _utc_now(),
                    "decision_type": "stop_condition_blocked",
                    "condition": condition,
                    "files": sorted(protected_files),
                    "context": ctx,
                }
            )

        return {
            "pass": len(violations) == 0,
            "hits": hits,
            "violations": violations,
            "waivers": waivers,
            "auto_policy_enabled": auto_enabled,
            "auto_waivable_conditions": sorted(auto_waivable),
            "decision_entries": decisions,
        }

    @staticmethod
    def _append_decision_log(doc: dict[str, Any], entries: list[dict[str, Any]]) -> None:
        if not entries:
            return
        rows = doc.get("autopilot_decision_log_v1") if isinstance(doc.get("autopilot_decision_log_v1"), list) else []
        rows.extend(entries)
        doc["autopilot_decision_log_v1"] = rows

    @staticmethod
    def _is_redline_path(path: str) -> bool:
        return any(_match_rule(path, p) for p in STOP_CONDITION_REDLINES)

    @staticmethod
    def _exception_rules_from_goals(goals: list[Goal]) -> list[str]:
        rules: list[str] = []
        for g in goals:
            scope = g.stop_scope
            pre = scope.get("preauthorized_scope") if isinstance(scope.get("preauthorized_scope"), dict) else {}
            allowed = pre.get("allowed_code_paths") if isinstance(pre.get("allowed_code_paths"), list) else []
            rules.extend([str(x) for x in allowed if isinstance(x, str)])
        return sorted(set(rules))

    def _strict_gate(
        self,
        *,
        doc: dict[str, Any],
        cluster: dict[str, Any],
        goals_by_id: dict[str, Goal],
    ) -> tuple[bool, dict[str, Any]]:
        latest_phase_id = self._latest_phase_for_cluster(cluster)
        goal_ids = [str(x) for x in (cluster.get("goal_ids") or []) if isinstance(x, str)]
        cluster_goals = [goals_by_id[gid] for gid in goal_ids if gid in goals_by_id]

        gate_report: dict[str, Any] = {
            "docs_tree": {"pass": False, "command": "python3 scripts/check_docs_tree.py"},
            "packet": {"pass": False, "command": f"python3 scripts/check_subagent_packet.py --phase-id {latest_phase_id}"},
            "acceptance": {"pass": False, "commands": []},
            "tests": {"pass": False, "commands": []},
            "whitelist": {"pass": False, "files": []},
            "redline": {
                "pass": False,
                "violations": [],
                "waivers": [],
                "hits": {},
                "auto_policy_enabled": False,
                "auto_waivable_conditions": [],
            },
        }

        if not self.run_gates:
            gate_report["skip_reason"] = "run_gates disabled"
            for key in ("docs_tree", "packet", "acceptance", "tests", "whitelist", "redline"):
                node = gate_report.get(key)
                if isinstance(node, dict):
                    node["pass"] = True
            return True, gate_report

        docs = self.run_command("python3 scripts/check_docs_tree.py", timeout_sec=300)
        gate_report["docs_tree"]["pass"] = docs.exit_code == 0
        gate_report["docs_tree"]["exit_code"] = docs.exit_code

        if latest_phase_id:
            pkt = self.run_command(
                f"python3 scripts/check_subagent_packet.py --phase-id {latest_phase_id}",
                timeout_sec=300,
            )
            gate_report["packet"]["pass"] = pkt.exit_code == 0
            gate_report["packet"]["exit_code"] = pkt.exit_code
        else:
            gate_report["packet"]["error"] = "latest phase id missing"

        acceptance_cmds = [str(x) for x in (cluster.get("acceptance_commands") or []) if isinstance(x, str)]
        if not acceptance_cmds:
            acceptance_cmds = sorted({cmd for g in cluster_goals for cmd in g.acceptance_commands if cmd})
        acceptance_ok, acceptance_rows = self._run_acceptance_commands(acceptance_cmds)
        gate_report["acceptance"]["pass"] = acceptance_ok
        gate_report["acceptance"]["commands"] = acceptance_rows

        test_cmds = [str(x) for x in (cluster.get("required_tests") or []) if isinstance(x, str)]
        tests_ok, test_rows = self._run_acceptance_commands(test_cmds)
        gate_report["tests"]["pass"] = tests_ok if test_cmds else True
        gate_report["tests"]["commands"] = test_rows

        status = self.run_command("git status --porcelain", timeout_sec=60)
        changed_files = self._extract_changed_files(status.stdout)
        whitelist = sorted(
            set(
                [*([f"artifacts/subagent_control/{self._latest_phase_for_cluster(cluster)}/**"] if self._latest_phase_for_cluster(cluster) else []), *[g.phase_doc_path for g in cluster_goals if g.phase_doc_path], *[r for g in cluster_goals for r in g.allowed_paths], "docs/12_workflows/skeleton_ssot_v1.yaml"]
            )
        )
        commit_files = self._expanded_commit_files(changed_files, whitelist)
        gate_report["whitelist"]["pass"] = bool(commit_files)
        gate_report["whitelist"]["files"] = commit_files
        gate_report["whitelist"]["rules"] = whitelist

        stop_conditions = self._evaluate_stop_conditions(
            doc=doc,
            changed_files=commit_files,
            goals=cluster_goals,
            context={
                "cluster_id": str(cluster.get("cluster_id") or ""),
                "latest_phase_id": latest_phase_id,
                "stage": "milestone_strict_gate",
            },
        )
        self._append_decision_log(doc, [x for x in stop_conditions.get("decision_entries", []) if isinstance(x, dict)])
        gate_report["redline"]["pass"] = bool(stop_conditions.get("pass", False))
        gate_report["redline"]["violations"] = stop_conditions.get("violations", [])
        gate_report["redline"]["waivers"] = stop_conditions.get("waivers", [])
        gate_report["redline"]["hits"] = stop_conditions.get("hits", {})
        gate_report["redline"]["auto_policy_enabled"] = bool(stop_conditions.get("auto_policy_enabled", False))
        gate_report["redline"]["auto_waivable_conditions"] = stop_conditions.get("auto_waivable_conditions", [])

        ok = all(
            [
                gate_report["docs_tree"]["pass"],
                gate_report["packet"]["pass"],
                gate_report["acceptance"]["pass"],
                gate_report["tests"]["pass"],
                gate_report["whitelist"]["pass"],
                gate_report["redline"]["pass"],
            ]
        )
        return ok, gate_report

    def _write_milestone_artifacts(
        self,
        *,
        milestone_id: str,
        cluster: dict[str, Any],
        gate_report: dict[str, Any],
        commit_manifest: dict[str, Any],
    ) -> tuple[str, str]:
        out_dir = self.milestone_root / milestone_id
        out_dir.mkdir(parents=True, exist_ok=True)
        summary_path = out_dir / "milestone_summary.md"
        manifest_path = out_dir / "commit_manifest.json"

        summary_lines = [
            f"# Milestone {milestone_id}",
            "",
            f"- cluster_id: `{cluster.get('cluster_id', '')}`",
            f"- status_now: `{cluster.get('status_now', '')}`",
            f"- generated_at: `{_utc_now()}`",
            "",
            "## Goals",
        ]
        for gid in cluster.get("goal_ids") or []:
            summary_lines.append(f"- `{gid}`")
        summary_lines.append("")
        summary_lines.append("## Requirements")
        for rid in cluster.get("requirement_ids") or []:
            summary_lines.append(f"- `{rid}`")
        summary_lines.append("")
        summary_lines.append("## Gate")
        for key in ("docs_tree", "packet", "acceptance", "tests", "whitelist", "redline"):
            item = gate_report.get(key, {})
            summary_lines.append(f"- {key}: `{'pass' if item.get('pass') else 'fail'}`")
        summary_path.write_text("\n".join(summary_lines).rstrip() + "\n", encoding="utf-8")
        manifest_path.write_text(json.dumps(commit_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return summary_path.relative_to(self.repo_root).as_posix(), manifest_path.relative_to(self.repo_root).as_posix()

    def _commit_and_push(
        self,
        *,
        milestone_id: str,
        cluster: dict[str, Any],
        files_to_commit: list[str],
    ) -> dict[str, Any]:
        if self.dry_run:
            return {
                "attempted": False,
                "commit_sha": "",
                "push_mode": "dry_run",
                "push_target": "",
                "branch": "",
            }

        staged_before = self.run_command("git diff --cached --name-only", timeout_sec=60)
        existing_staged = [x.strip() for x in staged_before.stdout.splitlines() if x.strip()]
        if existing_staged:
            return {
                "attempted": True,
                "commit_sha": "",
                "push_mode": "blocked",
                "push_target": "",
                "branch": "",
                "error": f"pre-staged files exist; refuse auto-commit: {existing_staged}",
            }

        if not files_to_commit:
            return {
                "attempted": True,
                "commit_sha": "",
                "push_mode": "blocked",
                "push_target": "",
                "branch": "",
                "error": "no whitelist files to commit",
            }

        quoted = " ".join([f"'{x}'" for x in files_to_commit])
        add_res = self.run_command(f"git add -- {quoted}", timeout_sec=120)
        if add_res.exit_code != 0:
            return {
                "attempted": True,
                "commit_sha": "",
                "push_mode": "failed",
                "push_target": "",
                "branch": "",
                "error": "git add failed",
            }

        cluster_id = str(cluster.get("cluster_id") or "")
        summary = str(cluster.get("title") or cluster_id).strip().replace("\n", " ")
        commit_msg = f"milestone({cluster_id}): {summary}"
        goals = ",".join([str(x) for x in (cluster.get("goal_ids") or []) if isinstance(x, str)])
        reqs = ",".join([str(x) for x in (cluster.get("requirement_ids") or []) if isinstance(x, str)])
        packet_phase = self._latest_phase_for_cluster(cluster)
        body = (
            "Goals: "
            + goals
            + "\nRequirements: "
            + reqs
            + "\nAcceptance: strict_gate_pass\nPacket: "
            + packet_phase
            + " pass"
        )
        commit_res = self.run_command(
            f"git commit -m \"{commit_msg}\" -m \"{body}\"",
            timeout_sec=120,
        )
        if commit_res.exit_code != 0:
            return {
                "attempted": True,
                "commit_sha": "",
                "push_mode": "failed",
                "push_target": "",
                "branch": "",
                "error": "git commit failed",
            }

        sha_res = self.run_command("git rev-parse HEAD", timeout_sec=30)
        sha = sha_res.stdout.strip() if sha_res.exit_code == 0 else ""
        out = {
            "attempted": True,
            "commit_sha": sha,
            "push_mode": "none",
            "push_target": "",
            "branch": "",
        }
        if not self.enable_push:
            return out

        push_master = self.run_command("git push origin master", timeout_sec=180)
        if push_master.exit_code == 0:
            out["push_mode"] = "direct_master"
            out["push_target"] = "origin/master"
            out["branch"] = "master"
            return out

        fallback_branch = f"autopilot/milestone-{milestone_id}"
        push_fb = self.run_command(
            f"git push origin HEAD:refs/heads/{fallback_branch}",
            timeout_sec=180,
        )
        if push_fb.exit_code == 0:
            out["push_mode"] = "fallback_branch"
            out["push_target"] = f"origin/{fallback_branch}"
            out["branch"] = fallback_branch
            return out

        out["push_mode"] = "failed"
        out["push_target"] = "origin/master + fallback"
        out["branch"] = fallback_branch
        out["error"] = "push master and fallback both failed"
        return out

    def evaluate_milestones(self, doc: dict[str, Any]) -> list[dict[str, Any]]:
        clusters = doc.get("capability_clusters_v1")
        if not isinstance(clusters, list):
            return []
        policy = doc.get("milestone_policy_v1") if isinstance(doc.get("milestone_policy_v1"), dict) else {}
        retry_blocked_clusters = bool(policy.get("retry_blocked_clusters", False))
        goals = self.parse_goals(doc)
        reqs = self.parse_requirements(doc)
        goals_by_id = {g.goal_id: g for g in goals}
        req_by_id = {r.req_id: r for r in reqs}
        history = doc.get("milestone_history_v1") if isinstance(doc.get("milestone_history_v1"), list) else []
        processed_statuses = {"implemented"} if retry_blocked_clusters else {"implemented", "blocked"}
        completed_cluster_ids = {
            str(x.get("cluster_id") or "")
            for x in history
            if isinstance(x, dict) and str(x.get("status_now") or "") in processed_statuses
        }

        outputs: list[dict[str, Any]] = []
        for cluster in clusters:
            if not isinstance(cluster, dict):
                continue
            cluster_id = str(cluster.get("cluster_id") or "")
            if not cluster_id or cluster_id in completed_cluster_ids:
                continue
            goals_ok = self._cluster_goals_status_ok(cluster, goals_by_id)
            reqs_ok = self._cluster_requirements_status_ok(cluster, req_by_id)
            if not (goals_ok and reqs_ok):
                continue

            gate_ok, gate_report = self._strict_gate(doc=doc, cluster=cluster, goals_by_id=goals_by_id)
            milestone_id = f"{cluster_id.lower()}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
            files_to_commit = [str(x) for x in gate_report.get("whitelist", {}).get("files", []) if isinstance(x, str)]

            commit_result = (
                self._commit_and_push(milestone_id=milestone_id, cluster=cluster, files_to_commit=files_to_commit)
                if gate_ok
                else {
                    "attempted": False,
                    "commit_sha": "",
                    "push_mode": "blocked_by_gate",
                    "push_target": "",
                    "branch": "",
                }
            )

            commit_manifest = {
                "schema_version": "milestone_commit_manifest_v1",
                "milestone_id": milestone_id,
                "cluster_id": cluster_id,
                "goals": [str(x) for x in (cluster.get("goal_ids") or []) if isinstance(x, str)],
                "requirements": [str(x) for x in (cluster.get("requirement_ids") or []) if isinstance(x, str)],
                "files": files_to_commit,
                "gate": gate_report,
                "commit": commit_result,
                "generated_at": _utc_now(),
            }
            summary_path, manifest_path = self._write_milestone_artifacts(
                milestone_id=milestone_id,
                cluster=cluster,
                gate_report=gate_report,
                commit_manifest=commit_manifest,
            )

            history_row = {
                "milestone_id": milestone_id,
                "cluster_id": cluster_id,
                "status_now": "implemented" if gate_ok and commit_result.get("push_mode") not in {"failed", "blocked"} else "blocked",
                "recorded_at": _utc_now(),
                "latest_phase_id": self._latest_phase_for_cluster(cluster),
                "push_mode": commit_result.get("push_mode"),
                "branch": commit_result.get("branch", ""),
                "commit_sha": commit_result.get("commit_sha", ""),
                "artifact_paths": {
                    "milestone_summary": summary_path,
                    "commit_manifest": manifest_path,
                },
                "notes": [
                    "auto-recorded by whole_view_autopilot milestone evaluator",
                ],
            }
            history.append(history_row)
            outputs.append(
                {
                    "cluster_id": cluster_id,
                    "milestone_id": milestone_id,
                    "gate_ok": gate_ok,
                    "commit": commit_result,
                    "history_status": history_row["status_now"],
                }
            )

            # Optional packet linkage for validator report.
            latest_phase = self._latest_phase_for_cluster(cluster)
            val_path = self.packet_root / latest_phase / "validator_report.yaml"
            if val_path.is_file():
                try:
                    val_doc = yaml.safe_load(val_path.read_text(encoding="utf-8"))
                    if isinstance(val_doc, dict):
                        val_doc["milestone_eval"] = {
                            "milestone_id": milestone_id,
                            "cluster_id": cluster_id,
                            "gate_ok": gate_ok,
                            "push_mode": commit_result.get("push_mode"),
                            "recorded_at": _utc_now(),
                        }
                        val_path.write_text(yaml.safe_dump(val_doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
                except Exception:
                    # Do not fail milestone flow on optional validator annotation.
                    pass

        doc["milestone_history_v1"] = history
        return outputs

    def _summary_payload(
        self,
        *,
        mode: str,
        preview: dict[str, Any],
        generated_goal_ids: list[str],
        selected: list[str],
        milestone_outputs: list[dict[str, Any]],
        controller_cycles: list[dict[str, Any]] | None = None,
        stop_reason: str = "",
        done_flags: dict[str, bool] | None = None,
        architect_preplan: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "status": "ok",
            "mode": mode,
            "ssot_path": self.ssot_path.relative_to(self.repo_root).as_posix(),
            "requirements_total": preview.get("requirements_total", 0),
            "clusters_total": preview.get("cluster_total", 0),
            "generated_goal_ids": generated_goal_ids,
            "selected_goal_ids": selected,
            "milestones": milestone_outputs,
            "stop_reason": stop_reason,
            "done_flags": done_flags or {},
            "controller_cycles": controller_cycles or [],
            "architect_preplan": architect_preplan or {},
            "command_log": [
                {
                    "command": c.command,
                    "exit_code": c.exit_code,
                    "stdout_tail": c.stdout.strip()[-200:],
                    "stderr_tail": c.stderr.strip()[-200:],
                }
                for c in self.commands
            ],
        }

    def run(self, *, mode: str, max_cycles: int = 1) -> tuple[int, dict[str, Any]]:
        if mode != "controller":
            ssot = self.load_ssot()
            ssot, preview = self.migrate_ssot(ssot)
            goals = self.parse_goals(ssot)
            architect_preplan = self._run_architect_preplan(ssot, goals)
            preplan_policy = self._architect_preplan_policy(ssot)
            preplan_blocked = bool(architect_preplan.get("blocked", False)) and bool(
                preplan_policy.get("enforce_before_goal_generation", True)
            )
            generated_goal_ids: list[str] = []
            if mode in {"plan", "run"} and not preplan_blocked:
                generated_goal_ids = self.maybe_generate_goals_when_queue_empty(ssot, goals)
                if generated_goal_ids:
                    goals = self.parse_goals(ssot)
            selected = self.select_parallel_goals(ssot, goals)

            milestone_outputs: list[dict[str, Any]] = []
            if mode == "run" and not preplan_blocked:
                milestone_outputs = self.evaluate_milestones(ssot)

            self.save_ssot(ssot)
            done_flags = self._done_state_flags(ssot)
            summary = self._summary_payload(
                mode=mode,
                preview=preview,
                generated_goal_ids=generated_goal_ids,
                selected=selected,
                milestone_outputs=milestone_outputs,
                stop_reason=("blocked_architect_preplan" if preplan_blocked else "single_cycle_complete"),
                done_flags=done_flags,
                architect_preplan=architect_preplan,
            )
            if preplan_blocked:
                return 2, summary
            failed = any(x.get("history_status") == "blocked" for x in milestone_outputs)
            return (2 if failed else 0), summary

        total_cycles = max(1, max_cycles)
        controller_cycles: list[dict[str, Any]] = []
        for cycle in range(1, total_cycles + 1):
            ssot = self.load_ssot()
            ssot, preview = self.migrate_ssot(ssot)
            goals = self.parse_goals(ssot)
            architect_preplan = self._run_architect_preplan(ssot, goals)
            preplan_policy = self._architect_preplan_policy(ssot)
            preplan_blocked = bool(architect_preplan.get("blocked", False)) and bool(
                preplan_policy.get("enforce_before_goal_generation", True)
            )
            generated_goal_ids: list[str] = []
            if not preplan_blocked:
                generated_goal_ids = self.maybe_generate_goals_when_queue_empty(ssot, goals)
            if generated_goal_ids:
                goals = self.parse_goals(ssot)
            selected = self.select_parallel_goals(ssot, goals)
            cycle_row: dict[str, Any] = {
                "cycle": cycle,
                "architect_preplan": {
                    "mode": str(architect_preplan.get("mode") or ""),
                    "source": str(architect_preplan.get("source") or ""),
                    "signature": str(architect_preplan.get("signature") or ""),
                    "blocked": bool(architect_preplan.get("blocked", False)),
                    "fallback_reason": str(architect_preplan.get("fallback_reason") or ""),
                    "requirement_priority_count": len(architect_preplan.get("requirement_priority") or []),
                    "goal_priority_count": len(architect_preplan.get("goal_priority") or []),
                    "artifact_path": str(architect_preplan.get("artifact_path") or ""),
                },
                "generated_goal_ids": generated_goal_ids,
                "selected_goal_ids": selected,
                "dispatch": [],
                "milestones": [],
            }

            if preplan_blocked:
                done_flags = self._done_state_flags(ssot)
                self.save_ssot(ssot)
                controller_cycles.append(cycle_row)
                summary = self._summary_payload(
                    mode=mode,
                    preview=preview,
                    generated_goal_ids=generated_goal_ids,
                    selected=[],
                    milestone_outputs=[],
                    controller_cycles=controller_cycles,
                    stop_reason="blocked_architect_preplan",
                    done_flags=done_flags,
                    architect_preplan=architect_preplan,
                )
                return 2, summary

            if not selected:
                done_flags = self._done_state_flags(ssot)
                self.save_ssot(ssot)
                stop_reason = "done_criteria_satisfied" if all(done_flags.values()) else "blocked_no_selectable_goal"
                controller_cycles.append(cycle_row)
                summary = self._summary_payload(
                    mode=mode,
                    preview=preview,
                    generated_goal_ids=[],
                    selected=[],
                    milestone_outputs=[],
                    controller_cycles=controller_cycles,
                    stop_reason=stop_reason,
                    done_flags=done_flags,
                    architect_preplan=architect_preplan,
                )
                return (0 if all(done_flags.values()) else 2), summary

            blocked = False
            for goal_id in selected:
                result = self._execute_goal_with_retries(ssot, goal_id)
                cycle_row["dispatch"].append(result)
                if result.get("status") == "blocked":
                    blocked = True
                    break

            # Recompute derived sections after status writeback.
            ssot, _ = self.migrate_ssot(ssot)
            milestones = [] if blocked else self.evaluate_milestones(ssot)
            cycle_row["milestones"] = milestones
            controller_cycles.append(cycle_row)
            done_flags = self._done_state_flags(ssot)
            self.save_ssot(ssot)

            if blocked:
                summary = self._summary_payload(
                    mode=mode,
                    preview=preview,
                    generated_goal_ids=generated_goal_ids,
                    selected=selected,
                    milestone_outputs=milestones,
                    controller_cycles=controller_cycles,
                    stop_reason="blocked_goal_retry_exhausted",
                    done_flags=done_flags,
                    architect_preplan=architect_preplan,
                )
                return 2, summary

            if all(done_flags.values()):
                summary = self._summary_payload(
                    mode=mode,
                    preview=preview,
                    generated_goal_ids=generated_goal_ids,
                    selected=selected,
                    milestone_outputs=milestones,
                    controller_cycles=controller_cycles,
                    stop_reason="done_criteria_satisfied",
                    done_flags=done_flags,
                    architect_preplan=architect_preplan,
                )
                return 0, summary

        final_ssot = self.load_ssot()
        final_done = self._done_state_flags(final_ssot)
        final_preplan = self._architect_preplan_policy(final_ssot).get("latest_plan")
        summary = self._summary_payload(
            mode=mode,
            preview={"requirements_total": len(self.parse_requirements(final_ssot)), "cluster_total": len(final_ssot.get("capability_clusters_v1") or [])},
            generated_goal_ids=[],
            selected=[],
            milestone_outputs=[],
            controller_cycles=controller_cycles,
            stop_reason="max_cycles_exhausted",
            done_flags=final_done,
            architect_preplan=final_preplan if isinstance(final_preplan, dict) else {},
        )
        return 2, summary


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=(
            "Unattended scheduler enhancer: requirement-level DAG + critical-path dispatch + "
            "capability-cluster milestones + whitelist commit/push fallback."
        )
    )
    ap.add_argument(
        "--mode",
        choices=("migrate", "plan", "run", "controller"),
        default="run",
        help=(
            "migrate: only SSOT migration; "
            "plan: migration+selection; "
            "run: single cycle with milestone evaluation; "
            "controller: internal loop dispatch until done/block."
        ),
    )
    ap.add_argument("--ssot-path", default=SSOT_DEFAULT.as_posix(), help="SSOT YAML path.")
    ap.add_argument("--packet-root", default=PACKET_ROOT_DEFAULT.as_posix(), help="Subagent packet root.")
    ap.add_argument("--milestone-root", default=MILESTONE_ROOT_DEFAULT.as_posix(), help="Milestone artifact root.")
    ap.add_argument(
        "--splitter-config",
        default=SPLITTER_CONFIG_DEFAULT.as_posix(),
        help="Requirement splitter profile YAML path.",
    )
    ap.add_argument("--max-parallel", type=int, default=2, help="Max goals selected in one scheduling batch.")
    ap.add_argument("--latest-phase-id", default="", help="Override latest phase id for packet validation.")
    ap.add_argument("--dry-run", action="store_true", help="Never commit/push; still run gate checks.")
    ap.add_argument(
        "--skip-gates",
        action="store_true",
        help="Skip strict gate command execution (used for schema migration only).",
    )
    ap.add_argument(
        "--disable-push",
        action="store_true",
        help="Allow commit but disable push.",
    )
    ap.add_argument(
        "--max-cycles",
        type=int,
        default=50,
        help="Max controller cycles in --mode controller.",
    )
    ap.add_argument(
        "--subagent-mode",
        choices=("codex_exec", "acceptance_only"),
        default="codex_exec",
        help="Subagent execution mode for dispatch lifecycle.",
    )
    ap.add_argument(
        "--codex-model",
        default="",
        help="Optional model name forwarded to codex exec.",
    )
    ap.add_argument(
        "--codex-timeout-sec",
        type=int,
        default=1800,
        help="Timeout seconds for codex exec subagent call.",
    )
    ap.add_argument(
        "--codex-json-log",
        action="store_true",
        help="Enable codex exec --json and persist stdout events log in packet evidence.",
    )
    ap.add_argument(
        "--skill-enforcement-mode",
        choices=("warn", "enforce"),
        default="warn",
        help="Skill gate mode for validator checks.",
    )
    ap.add_argument(
        "--reasoning-tier-override",
        choices=("medium", "high", "super_high"),
        default="",
        help="Optional forced reasoning tier for all goals.",
    )
    ap.add_argument(
        "--skill-registry-path",
        default="",
        help="Optional YAML path to load skill registry override; default uses SSOT skill_registry_v1.",
    )
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    engine = WholeViewAutopilot(
        ssot_path=Path(args.ssot_path),
        packet_root=Path(args.packet_root),
        milestone_root=Path(args.milestone_root),
        max_parallel=args.max_parallel,
        dry_run=bool(args.dry_run),
        run_gates=not bool(args.skip_gates),
        enable_push=not bool(args.disable_push),
        latest_phase_id=str(args.latest_phase_id).strip() or None,
        subagent_mode=str(args.subagent_mode).strip(),
        codex_model=str(args.codex_model).strip() or None,
        codex_timeout_sec=int(args.codex_timeout_sec),
        codex_json_log=bool(args.codex_json_log),
        skill_enforcement_mode=str(args.skill_enforcement_mode).strip(),
        reasoning_tier_override=str(args.reasoning_tier_override).strip() or None,
        skill_registry_path=Path(args.skill_registry_path).expanduser() if str(args.skill_registry_path).strip() else None,
        splitter_config_path=Path(args.splitter_config),
    )
    rc, summary = engine.run(mode=args.mode, max_cycles=int(args.max_cycles))
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
