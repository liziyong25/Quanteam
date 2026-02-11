from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from quant_eam.contracts import validate as contracts_validate
from quant_eam.jobstore.store import job_paths, resolve_repo_relative
from quant_eam.policies.load import load_yaml


def _canonical_line(obj: dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(_canonical_line(obj) + "\n")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_atomic(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / (path.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


@dataclass(frozen=True)
class LLMUsagePaths:
    usage_dir: Path
    events: Path
    report: Path


def llm_usage_paths(*, job_id: str, job_root: Path | None = None) -> LLMUsagePaths:
    paths = job_paths(job_id, job_root=job_root)
    d = paths.outputs_dir / "llm"
    return LLMUsagePaths(
        usage_dir=d,
        events=d / "llm_usage_events.jsonl",
        report=d / "llm_usage_report.json",
    )


def infer_job_id_from_agent_out_dir(out_dir: Path) -> str | None:
    """Best-effort inference for job_id from an agent out_dir.

    Expected structure:
      <job_root>/<job_id>/outputs/agents/<name>
    """
    cur = Path(out_dir).resolve()
    for p in [cur, *cur.parents]:
        # Job dir contains job_spec.json and events.jsonl.
        if (p / "job_spec.json").is_file() and (p / "events.jsonl").is_file():
            jid = p.name
            return jid if jid and len(jid) == 12 else None
    return None


@dataclass(frozen=True)
class BudgetThresholds:
    policy_id: str
    max_calls_per_job: int
    max_prompt_chars_per_job: int
    max_response_chars_per_job: int
    max_wall_seconds_per_job: int
    max_calls_per_agent_run: int | None = None


def load_llm_budget_policy(policy_path: Path) -> BudgetThresholds:
    p = resolve_repo_relative(str(policy_path))
    doc = load_yaml(p)
    if not isinstance(doc, dict):
        raise ValueError("llm budget policy must be a YAML mapping")
    pid = str(doc.get("policy_id", "")).strip()
    params = doc.get("params") if isinstance(doc.get("params"), dict) else {}
    if not pid:
        raise ValueError("llm budget policy missing policy_id")

    def iget(k: str, default: int) -> int:
        v = params.get(k, default)
        try:
            return int(v)
        except Exception:  # noqa: BLE001
            return default

    mcapr = params.get("max_calls_per_agent_run")
    try:
        mcapr_i = int(mcapr) if mcapr is not None else None
    except Exception:  # noqa: BLE001
        mcapr_i = None

    return BudgetThresholds(
        policy_id=pid,
        max_calls_per_job=max(0, iget("max_calls_per_job", 0)),
        max_prompt_chars_per_job=max(0, iget("max_prompt_chars_per_job", 0)),
        max_response_chars_per_job=max(0, iget("max_response_chars_per_job", 0)),
        max_wall_seconds_per_job=max(0, iget("max_wall_seconds_per_job", 0)),
        max_calls_per_agent_run=(max(0, mcapr_i) if isinstance(mcapr_i, int) else None),
    )


@dataclass(frozen=True)
class UsageTotals:
    calls: int
    prompt_chars: int
    response_chars: int
    wall_seconds: float


def _zero_totals() -> UsageTotals:
    return UsageTotals(calls=0, prompt_chars=0, response_chars=0, wall_seconds=0.0)


def _add_totals(a: UsageTotals, b: UsageTotals) -> UsageTotals:
    return UsageTotals(
        calls=int(a.calls + b.calls),
        prompt_chars=int(a.prompt_chars + b.prompt_chars),
        response_chars=int(a.response_chars + b.response_chars),
        wall_seconds=float(a.wall_seconds + b.wall_seconds),
    )


def _parse_event_delta(ev: dict[str, Any]) -> UsageTotals:
    d = ev.get("delta") if isinstance(ev.get("delta"), dict) else {}
    try:
        calls = int(d.get("calls", 0) or 0)
    except Exception:  # noqa: BLE001
        calls = 0
    try:
        pc = int(d.get("prompt_chars", 0) or 0)
    except Exception:  # noqa: BLE001
        pc = 0
    try:
        rc = int(d.get("response_chars", 0) or 0)
    except Exception:  # noqa: BLE001
        rc = 0
    try:
        ws = float(d.get("wall_seconds", 0.0) or 0.0)
    except Exception:  # noqa: BLE001
        ws = 0.0
    return UsageTotals(calls=max(0, calls), prompt_chars=max(0, pc), response_chars=max(0, rc), wall_seconds=max(0.0, ws))


def load_usage_events(*, job_id: str, job_root: Path | None = None) -> list[dict[str, Any]]:
    p = llm_usage_paths(job_id=job_id, job_root=job_root).events
    if not p.is_file():
        return []
    out: list[dict[str, Any]] = []
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            doc = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if isinstance(doc, dict):
            out.append(doc)
    return out


def aggregate_totals(*, job_id: str, job_root: Path | None = None) -> tuple[UsageTotals, dict[str, UsageTotals], str | None]:
    events = load_usage_events(job_id=job_id, job_root=job_root)
    totals = _zero_totals()
    by_agent: dict[str, UsageTotals] = {}
    stop_reason: str | None = None
    for ev in events:
        agent_id = str(ev.get("agent_id", "")).strip() or "unknown"
        delta = _parse_event_delta(ev)
        totals = _add_totals(totals, delta)
        by_agent[agent_id] = _add_totals(by_agent.get(agent_id, _zero_totals()), delta)
        if isinstance(ev.get("stop_reason"), str) and ev.get("stop_reason"):
            stop_reason = str(ev["stop_reason"])
    return totals, by_agent, stop_reason


def write_usage_event(
    *,
    job_id: str,
    agent_id: str,
    event_type: str,
    delta: UsageTotals,
    thresholds: BudgetThresholds,
    would_exceed: dict[str, bool] | None = None,
    stop_reason: str | None = None,
    evidence_refs: dict[str, Any] | None = None,
    job_root: Path | None = None,
) -> Path:
    up = llm_usage_paths(job_id=job_id, job_root=job_root)
    ev: dict[str, Any] = {
        "schema_version": "llm_usage_event_v1",
        "job_id": str(job_id),
        "agent_id": str(agent_id),
        "event_type": str(event_type),
        "recorded_at_epoch": int(os.getenv("SOURCE_DATE_EPOCH") or "0") if (os.getenv("SOURCE_DATE_EPOCH") or "").isdigit() else None,
        "recorded_at_wall": time.time(),
        "delta": {
            "calls": int(delta.calls),
            "prompt_chars": int(delta.prompt_chars),
            "response_chars": int(delta.response_chars),
            "wall_seconds": float(delta.wall_seconds),
        },
        "policy_id": thresholds.policy_id,
        "thresholds": {
            "max_calls_per_job": thresholds.max_calls_per_job,
            "max_prompt_chars_per_job": thresholds.max_prompt_chars_per_job,
            "max_response_chars_per_job": thresholds.max_response_chars_per_job,
            "max_wall_seconds_per_job": thresholds.max_wall_seconds_per_job,
            "max_calls_per_agent_run": thresholds.max_calls_per_agent_run,
        },
    }
    if would_exceed:
        ev["would_exceed"] = {str(k): bool(v) for k, v in would_exceed.items()}
    if stop_reason:
        ev["stop_reason"] = str(stop_reason)
    if evidence_refs:
        ev["evidence_refs"] = evidence_refs
    _append_jsonl(up.events, ev)
    return up.events


def build_usage_report(*, job_id: str, thresholds: BudgetThresholds, job_root: Path | None = None) -> dict[str, Any]:
    totals, by_agent_totals, stop_reason = aggregate_totals(job_id=job_id, job_root=job_root)
    events = load_usage_events(job_id=job_id, job_root=job_root)
    llm_calls_paths: set[str] = set()
    redaction_paths: set[str] = set()
    cassette_paths: set[str] = set()
    agent_out_dirs: set[str] = set()
    for ev in events:
        refs = ev.get("evidence_refs") if isinstance(ev.get("evidence_refs"), dict) else {}
        if isinstance(refs.get("llm_calls_path"), str):
            llm_calls_paths.add(str(refs["llm_calls_path"]))
        if isinstance(refs.get("redaction_summary_path"), str):
            redaction_paths.add(str(refs["redaction_summary_path"]))
        if isinstance(refs.get("cassette_path"), str):
            cassette_paths.add(str(refs["cassette_path"]))
        if isinstance(refs.get("agent_out_dir"), str):
            agent_out_dirs.add(str(refs["agent_out_dir"]))

    stopped = bool(stop_reason)
    report: dict[str, Any] = {
        "schema_version": "llm_usage_report_v1",
        "job_id": str(job_id),
        "policy_id": thresholds.policy_id,
        "thresholds": {
            "max_calls_per_job": thresholds.max_calls_per_job,
            "max_prompt_chars_per_job": thresholds.max_prompt_chars_per_job,
            "max_response_chars_per_job": thresholds.max_response_chars_per_job,
            "max_wall_seconds_per_job": thresholds.max_wall_seconds_per_job,
            "max_calls_per_agent_run": thresholds.max_calls_per_agent_run,
        },
        "totals": {
            "calls": totals.calls,
            "prompt_chars": totals.prompt_chars,
            "response_chars": totals.response_chars,
            "wall_seconds": totals.wall_seconds,
        },
        "by_agent": {
            aid: {
                "calls": t.calls,
                "prompt_chars": t.prompt_chars,
                "response_chars": t.response_chars,
                "wall_seconds": t.wall_seconds,
            }
            for aid, t in sorted(by_agent_totals.items(), key=lambda kv: kv[0])
        },
        "stopped": bool(stopped),
        "evidence_refs": {
            "usage_events_path": llm_usage_paths(job_id=job_id, job_root=job_root).events.as_posix(),
            "usage_report_path": llm_usage_paths(job_id=job_id, job_root=job_root).report.as_posix(),
            "llm_calls_paths": sorted(llm_calls_paths),
            "redaction_summary_paths": sorted(redaction_paths),
            "cassette_paths": sorted(cassette_paths),
            "agent_out_dirs": sorted(agent_out_dirs),
        },
        "extensions": {},
    }
    if stop_reason:
        report["stop_reason"] = str(stop_reason)
    return report


def write_usage_report(*, job_id: str, thresholds: BudgetThresholds, job_root: Path | None = None) -> Path:
    up = llm_usage_paths(job_id=job_id, job_root=job_root)
    report = build_usage_report(job_id=job_id, thresholds=thresholds, job_root=job_root)
    code, msg = contracts_validate.validate_payload(report)
    if code != contracts_validate.EXIT_OK:
        raise ValueError(f"invalid llm_usage_report_v1: {msg}")
    _write_json_atomic(up.report, report)
    return up.report


def is_budget_stopped(*, job_id: str, job_root: Path | None = None) -> tuple[bool, str | None]:
    up = llm_usage_paths(job_id=job_id, job_root=job_root)
    if not up.report.is_file():
        return False, None
    doc = _read_json(up.report)
    if not isinstance(doc, dict):
        return False, None
    stopped = bool(doc.get("stopped"))
    reason = doc.get("stop_reason") if isinstance(doc.get("stop_reason"), str) else None
    return stopped, reason
