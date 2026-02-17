from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from quant_eam.gates.types import GateContext, GateEvidence, GateResult


@dataclass(frozen=True)
class _Leak:
    file: str
    kind: str  # json|jsonl|md
    location: str  # json path or line number
    snippet: str


_NUM_RE = re.compile(r"(?:^|[^0-9])([0-9]+(?:\\.[0-9]+)?%?)(?:$|[^0-9])")


def _contains_number(v: Any) -> bool:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return True
    if isinstance(v, str):
        return bool(_NUM_RE.search(v))
    if isinstance(v, list):
        return any(_contains_number(x) for x in v)
    if isinstance(v, dict):
        return any(_contains_number(x) for x in v.values())
    return False


def _walk_holdout_keys(obj: Any, *, path: str = "") -> Iterable[tuple[str, str]]:
    """Yield (json_path, value_snippet) for any holdout-related key/value."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            k_s = str(k)
            p2 = f"{path}/{k_s}" if path else f"/{k_s}"
            if "holdout" in k_s.lower():
                yield p2, json.dumps(v, ensure_ascii=True)[:200]
            yield from _walk_holdout_keys(v, path=p2)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            p2 = f"{path}/{i}" if path else f"/{i}"
            yield from _walk_holdout_keys(v, path=p2)


def _scan_json(path: Path, *, rel: str) -> tuple[list[_Leak], list[str]]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return ([], [f"{rel}: JSON parse error: {type(e).__name__}: {e}"])

    leaks: list[_Leak] = []
    for jpath, snippet in _walk_holdout_keys(doc):
        # MVP rule: any holdout-related key must not carry numeric values (including percent).
        # Allowed: pass/fail booleans and tiny text summary WITHOUT numbers.
        try:
            # Resolve value by walking again is expensive; check snippet + path context only.
            if _contains_number(snippet):
                leaks.append(_Leak(file=rel, kind="json", location=jpath, snippet=snippet))
        except Exception:
            continue
    return leaks, []


def _scan_jsonl(path: Path, *, rel: str) -> tuple[list[_Leak], list[str]]:
    leaks: list[_Leak] = []
    errors: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception as e:  # noqa: BLE001
        return ([], [f"{rel}: read error: {type(e).__name__}: {e}"])

    for i, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            doc = json.loads(line)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{rel}:{i}: JSONL parse error: {type(e).__name__}: {e}")
            continue
        for jpath, snippet in _walk_holdout_keys(doc):
            if _contains_number(snippet):
                leaks.append(_Leak(file=rel, kind="jsonl", location=f"{i}{jpath}", snippet=snippet))
    return leaks, errors


def _scan_md(path: Path, *, rel: str) -> tuple[list[_Leak], list[str]]:
    leaks: list[_Leak] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception as e:  # noqa: BLE001
        return ([], [f"{rel}: read error: {type(e).__name__}: {e}"])

    for i, line in enumerate(lines, start=1):
        low = line.lower()
        if "holdout" not in low:
            continue
        # MVP heuristic: if a line mentions holdout and contains any numeric token, treat as leak.
        if _NUM_RE.search(line):
            leaks.append(_Leak(file=rel, kind="md", location=f"line:{i}", snippet=line.strip()[:200]))
    return leaks, []


def _scan_paths(paths: list[Path], *, base: Path) -> tuple[list[_Leak], list[str]]:
    leaks: list[_Leak] = []
    errors: list[str] = []
    for p in paths:
        try:
            rel = p.relative_to(base).as_posix()
        except Exception:
            rel = p.as_posix()

        if p.suffix.lower() == ".json":
            l, e = _scan_json(p, rel=rel)
        elif p.suffix.lower() == ".jsonl":
            l, e = _scan_jsonl(p, rel=rel)
        elif p.suffix.lower() == ".md":
            l, e = _scan_md(p, rel=rel)
        else:
            continue
        leaks.extend(l)
        errors.extend(e)
    return leaks, errors


def _collect_scan_targets(ctx: GateContext) -> tuple[list[Path], list[str]]:
    # Scan only deterministic, iteration-facing artifacts (avoid scanning raw market data).
    errs: list[str] = []

    artifact_root_raw = (ctx.config_snapshot.get("env", {}) or {}).get("EAM_ARTIFACT_ROOT")
    artifact_root = Path(str(artifact_root_raw)) if isinstance(artifact_root_raw, str) and str(artifact_root_raw).strip() else None
    if artifact_root is None:
        errs.append("missing config_snapshot.env.EAM_ARTIFACT_ROOT (cannot locate artifacts root)")
        return ([], errs)

    job_root = Path(str((ctx.config_snapshot.get("env", {}) or {}).get("EAM_JOB_ROOT") or "")) if isinstance(ctx.config_snapshot.get("env", {}), dict) else Path("")
    if not str(job_root).strip():
        job_root = artifact_root / "jobs"

    targets: list[Path] = []

    # Jobs: sweep outputs + proposals (if present).
    if job_root.is_dir():
        targets.extend(sorted(job_root.glob("*/outputs/sweep/leaderboard.json")))
        targets.extend(sorted(job_root.glob("*/outputs/sweep/trials.jsonl")))
        targets.extend(sorted(job_root.glob("*/outputs/proposals/*.json")))

    # Current dossier iteration-facing artifacts.
    for rel in ("attribution_report.json", "reports/report.md", "segments_summary.json"):
        p = ctx.dossier_dir / rel
        if p.is_file():
            targets.append(p)

    # Also scan any dossier attribution reports (common leak path).
    dossiers_dir = artifact_root / "dossiers"
    if dossiers_dir.is_dir():
        targets.extend(sorted(dossiers_dir.glob("*/attribution_report.json")))

    return targets, []


def run_holdout_leak_guard_v1(ctx: GateContext, params: dict[str, Any] | None) -> GateResult:
    _ = params or {}
    targets, errs = _collect_scan_targets(ctx)
    if errs:
        return GateResult(
            gate_id="holdout_leak_guard_v1",
            gate_version="v1",
            passed=False,
            status="fail",
            metrics={"error": "; ".join(errs)},
            evidence=GateEvidence(artifacts=["config_snapshot.json"]),
        )

    artifact_root_raw = (ctx.config_snapshot.get("env", {}) or {}).get("EAM_ARTIFACT_ROOT")
    base = Path(str(artifact_root_raw)) if isinstance(artifact_root_raw, str) else ctx.dossier_dir

    leaks, parse_errors = _scan_paths(targets, base=base)
    if parse_errors:
        return GateResult(
            gate_id="holdout_leak_guard_v1",
            gate_version="v1",
            passed=False,
            status="fail",
            metrics={"error": "parse errors while scanning holdout leak targets", "parse_errors": parse_errors},
            evidence=GateEvidence(artifacts=[p.as_posix() for p in targets][:50]),
        )

    if leaks:
        return GateResult(
            gate_id="holdout_leak_guard_v1",
            gate_version="v1",
            passed=False,
            status="fail",
            metrics={
                "leak_count": int(len(leaks)),
                "leaks": [
                    {"file": l.file, "kind": l.kind, "location": l.location, "snippet": l.snippet}
                    for l in leaks[:50]
                ],
                "scanned_files": int(len(targets)),
            },
            evidence=GateEvidence(artifacts=[p.as_posix() for p in targets][:50]),
        )

    return GateResult(
        gate_id="holdout_leak_guard_v1",
        gate_version="v1",
        passed=True,
        status="pass",
        metrics={"leak_count": 0, "scanned_files": int(len(targets))},
        evidence=GateEvidence(artifacts=[p.as_posix() for p in targets][:50]),
    )

