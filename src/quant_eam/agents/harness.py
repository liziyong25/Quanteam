from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from quant_eam.agents.guards import validate_agent_output
from quant_eam.agents.promptpack import default_prompt_version, load_promptpack
from quant_eam.contracts import validate as contracts_validate
from quant_eam.jobstore.llm_usage import (
    BudgetThresholds,
    UsageTotals,
    aggregate_totals,
    infer_job_id_from_agent_out_dir,
    load_llm_budget_policy,
    llm_usage_paths,
    write_usage_event,
    write_usage_report,
)
from quant_eam.jobstore.store import default_job_root, load_job_spec
from quant_eam.llm.cassette import CassetteStore, prompt_hash_v1, sha256_hex
from quant_eam.llm.provider import get_provider
from quant_eam.llm.redaction import sanitize_for_llm, write_redaction_summary


EXIT_OK = 0
EXIT_USAGE_OR_ERROR = 1
EXIT_INVALID = 2


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _llm_mode() -> str:
    return str(os.getenv("EAM_LLM_MODE", "live")).strip() or "live"


def _llm_provider_id() -> str:
    return str(os.getenv("EAM_LLM_PROVIDER", "mock")).strip() or "mock"


def _cassette_dir(out_dir: Path) -> Path:
    d = os.getenv("EAM_LLM_CASSETTE_DIR")
    if d and d.strip():
        return Path(d)
    return out_dir


def _promptpack_root() -> Path | None:
    p = os.getenv("EAM_AGENT_PROMPTPACK_ROOT")
    if p and p.strip():
        return Path(p)
    return None


def _promptpack_version() -> str:
    return str(os.getenv("EAM_AGENT_PROMPT_VERSION", default_prompt_version())).strip() or default_prompt_version()


def _current_job_id(out_dir: Path) -> str | None:
    # Orchestrator may set this for agents whose out_dir is not under jobs/ (e.g. report agent under dossier).
    env = str(os.getenv("EAM_CURRENT_JOB_ID", "")).strip()
    if env:
        return env
    return infer_job_id_from_agent_out_dir(out_dir)


def _job_llm_budget_policy_path(job_id: str) -> str:
    """Resolve job-level budget policy path from job_spec, else default."""
    jr = default_job_root()
    try:
        spec = load_job_spec(job_id, job_root=jr)
    except Exception:
        spec = {}
    if isinstance(spec, dict):
        p = spec.get("llm_budget_policy_path")
        if isinstance(p, str) and p.strip():
            return p.strip()
    return "policies/llm_budget_policy_v1.yaml"


def _budget_reason_from_would_exceed(w: dict[str, bool]) -> str:
    # Stable priority order.
    for k in (
        "max_calls_per_job",
        "max_prompt_chars_per_job",
        "max_response_chars_per_job",
        "max_wall_seconds_per_job",
        "max_calls_per_agent_run",
    ):
        if w.get(k):
            return f"exceeded_{k}"
    return "budget_exceeded"


@dataclass(frozen=True)
class AgentResult:
    agent_run_path: Path
    output_paths: list[Path]


def _provider_complete_json_with_fallback(
    *,
    prov_id: str,
    prov: Any,
    llm_mode: str,
    cassette: CassetteStore,
    prompt_hash: str,
    out_dir: Path,
    system: str,
    user: str,
    schema: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    """Return (response_bundle, effective_mode).

    Phase-28: if the provider raises, evidence `error_summary.json` and fall back to cassette replay if possible.
    """
    try:
        resp = prov.complete_json(system=system, user=user, schema=schema, temperature=0.0, seed=None)
        if not isinstance(resp, dict):
            raise ValueError("provider must return a JSON object")
        return resp, llm_mode
    except Exception as e:  # noqa: BLE001
        err_path = out_dir / "error_summary.json"
        _write_json(
            err_path,
            {
                "schema_version": "llm_error_summary_v1",
                "provider_id": prov_id,
                "requested_mode": llm_mode,
                "fallback_attempted": True,
                "prompt_hash": prompt_hash,
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
        )
        fb = cassette.replay_response(prompt_hash)
        if fb is None:
            raise
        return fb, "replay"


def run_agent(
    *,
    agent_id: str,
    input_path: Path,
    out_dir: Path,
    provider: str = "mock",
) -> AgentResult:
    """Run a harnessed agent deterministically.

    Must write:
    - agent_run.json (agent_run_v1)
    - agent outputs (paths listed in agent_run.output_refs)
    """
    agent_id = str(agent_id).strip()
    if agent_id not in (
        "intent_agent_v1",
        "strategy_spec_agent_v1",
        "spec_qa_agent_v1",
        "demo_agent_v1",
        "backtest_agent_v1",
        "report_agent_v1",
        "improvement_agent_v1",
        "diagnostics_agent_v1",
        "registry_curator_v1",
        "composer_agent_v1",
    ):
        raise ValueError(f"unknown agent_id: {agent_id}")
    provider = str(provider).strip()
    if provider not in ("mock", "external"):
        raise ValueError("provider must be 'mock' or 'external'")
    if provider != "mock":
        # Phase-11+ tests must be offline; keep external provider explicit.
        raise ValueError("provider 'external' is not supported in this harness MVP")

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    input_path = Path(input_path)
    if not input_path.is_file():
        raise FileNotFoundError(str(input_path))
    in_sha = sha256_file(input_path)

    # Append-only behavior: if already executed, return existing agent_run + outputs.
    existing_run = out_dir / "agent_run.json"
    if existing_run.is_file():
        try:
            doc = _load_json(existing_run)
            outs = doc.get("output_refs") if isinstance(doc, dict) else None
            if isinstance(outs, list) and all(isinstance(p, str) for p in outs):
                return AgentResult(agent_run_path=existing_run, output_paths=[Path(p) for p in outs])
        except Exception:
            pass

    llm_mode = _llm_mode()
    if llm_mode not in ("live", "record", "replay"):
        raise ValueError("EAM_LLM_MODE must be live|record|replay")
    llm_provider = _llm_provider_id()

    cassette_dir = _cassette_dir(out_dir)
    cassette_dir.mkdir(parents=True, exist_ok=True)
    cassette_path = cassette_dir / "cassette.jsonl"
    cassette = CassetteStore(path=cassette_path)

    evidence_calls_path = out_dir / "llm_calls.jsonl"
    evidence_calls = CassetteStore(path=evidence_calls_path)

    # PromptPack (versioned).
    pp = load_promptpack(agent_id=agent_id, version=_promptpack_version(), root=_promptpack_root())
    pp_sha = sha256_file(pp.path)

    # Read and sanitize agent input for redline compliance (no holdout/secret leaks).
    try:
        agent_input_obj = _load_json(input_path)
    except Exception:
        agent_input_obj = {"input_ref": input_path.as_posix()}
    sanitized_input, red_summary = sanitize_for_llm(agent_input_obj)
    redaction_path = out_dir / "redaction_summary.json"
    write_redaction_summary(redaction_path, red_summary)

    output_paths: list[Path] = []
    response_bundle: dict[str, Any] | None = None
    prompt_hash = ""

    # Cassette request: must be stable across record/replay and must NOT include secrets/holdout.
    request_obj: dict[str, Any] = {
        "agent_id": agent_id,
        "agent_version": "v1",
        "provider_id": llm_provider,
        "sanitized_input_sha256": red_summary.sanitized_sha256,
        "prompt_version": pp.prompt_version,
        "output_schema_version": pp.output_schema_version,
        # Use prompt content hash instead of absolute file path to make cassettes portable.
        "promptpack_sha256": pp_sha,
        "system": pp.system,
        "user": json.dumps(sanitized_input, sort_keys=True, separators=(",", ":"), ensure_ascii=True),
        "schema_sha256": "",  # filled per agent below
        "temperature": 0.0,
        "seed": None,
    }

    # Job-level budget (Phase-26). Enforced only when we can resolve job_id.
    job_id = _current_job_id(out_dir)
    thresholds: BudgetThresholds | None = None
    if job_id:
        try:
            thresholds = load_llm_budget_policy(Path(_job_llm_budget_policy_path(job_id)))
        except Exception:
            thresholds = None

    start_t = time.perf_counter()

    # Pre-call budget check (calls + prompt chars). Response chars and wall seconds are checked post-call.
    if job_id and thresholds:
        totals, _by_agent, _stop_reason = aggregate_totals(job_id=job_id, job_root=default_job_root())
        prompt_chars_pred = len(str(request_obj.get("system") or "")) + len(str(request_obj.get("user") or ""))
        would_exceed = {
            "max_calls_per_job": (totals.calls + 1) > thresholds.max_calls_per_job,
            "max_prompt_chars_per_job": (totals.prompt_chars + prompt_chars_pred) > thresholds.max_prompt_chars_per_job,
        }
        if thresholds.max_calls_per_agent_run is not None:
            would_exceed["max_calls_per_agent_run"] = 1 > int(thresholds.max_calls_per_agent_run)
        if any(would_exceed.values()):
            stop_reason = _budget_reason_from_would_exceed(would_exceed)
            write_usage_event(
                job_id=job_id,
                agent_id=agent_id,
                event_type="BUDGET_BLOCKED_PRECALL",
                delta=UsageTotals(calls=0, prompt_chars=0, response_chars=0, wall_seconds=0.0),
                thresholds=thresholds,
                would_exceed=would_exceed,
                stop_reason=stop_reason,
                evidence_refs={
                    "agent_out_dir": out_dir.as_posix(),
                    "cassette_path": cassette_path.as_posix(),
                    "redaction_summary_path": redaction_path.as_posix(),
                },
                job_root=default_job_root(),
            )
            report_path = write_usage_report(job_id=job_id, thresholds=thresholds, job_root=default_job_root())

            stop_obj = {
                "schema_version": "llm_budget_stop_v1",
                "job_id": job_id,
                "agent_id": agent_id,
                "policy_id": thresholds.policy_id,
                "stop_reason": stop_reason,
                "usage_report_ref": report_path.as_posix(),
            }
            stop_path = out_dir / "budget_stop.json"
            _write_json(stop_path, stop_obj)
            output_paths = [stop_path]
            response_bundle = {"budget_stop": stop_obj}

            request_obj["schema_sha256"] = sha256_hex({"type": "object"})
            prompt_hash = prompt_hash_v1(request=request_obj)
            evidence_calls.append_call(
                {
                    "schema_version": "llm_call_v1",
                    "prompt_hash": prompt_hash,
                    "provider_id": llm_provider,
                    "mode": llm_mode,
                    "request": request_obj,
                    "response_json": response_bundle,
                    "extensions": {"budget_blocked": True, "stop_reason": stop_reason},
                }
            )

            guard = validate_agent_output(
                agent_id=agent_id,
                output_json=response_bundle,
                prompt_version=pp.prompt_version,
                output_schema_version=pp.output_schema_version,
            )
            code_g, msg_g = contracts_validate.validate_payload(guard)
            if code_g != contracts_validate.EXIT_OK:
                raise ValueError(f"invalid output_guard_report_v1: {msg_g}")
            guard_path = out_dir / "output_guard_report.json"
            _write_json(guard_path, guard)

            session = {
                "schema_version": "llm_session_v1",
                "provider_id": llm_provider,
                "mode": llm_mode,
                "call_count": 0,
                "prompt_hashes": [],
                "cassette_path": cassette_path.as_posix(),
                "evidence_calls_path": evidence_calls_path.as_posix(),
                "promptpack_path": pp.path.as_posix(),
                "prompt_version": pp.prompt_version,
                "output_schema_version": pp.output_schema_version,
                "extensions": {
                    "redaction_summary_sha256": red_summary.sanitized_sha256,
                    "promptpack_sha256": pp_sha,
                    "guard_passed": bool(guard.get("passed")),
                    "guard_finding_count": int(guard.get("finding_count", 0) or 0),
                    "output_guard_report_ref": guard_path.as_posix(),
                    "budget_stopped": True,
                    "stop_reason": stop_reason,
                    "llm_usage_report_ref": report_path.as_posix(),
                },
            }
            code_s, msg_s = contracts_validate.validate_payload(session)
            if code_s != contracts_validate.EXIT_OK:
                raise ValueError(f"invalid llm_session_v1: {msg_s}")
            session_path = out_dir / "llm_session.json"
            _write_json(session_path, session)

            agent_run = {
                "schema_version": "agent_run_v1",
                "agent_id": agent_id,
                "agent_version": "v1",
                "provider": provider,
                "input_ref": input_path.as_posix(),
                "input_sha256": in_sha,
                "output_refs": [p.as_posix() for p in output_paths],
                "extensions": {
                    "llm": {
                        "provider_id": llm_provider,
                        "mode": llm_mode,
                        "cassette_path": cassette_path.as_posix(),
                        "prompt_hashes": [],
                        "llm_session_ref": session_path.as_posix(),
                        "llm_calls_ref": evidence_calls_path.as_posix(),
                        "redaction_summary_ref": redaction_path.as_posix(),
                        "output_guard_report_ref": guard_path.as_posix(),
                        "budget_stopped": True,
                        "stop_reason": stop_reason,
                        "llm_usage_report_ref": report_path.as_posix(),
                    }
                },
            }
            code, msg = contracts_validate.validate_payload(agent_run)
            if code != contracts_validate.EXIT_OK:
                raise ValueError(f"invalid agent_run_v1: {msg}")
            agent_run_path = out_dir / "agent_run.json"
            _write_json(agent_run_path, agent_run)
            return AgentResult(agent_run_path=agent_run_path, output_paths=output_paths)

    # --- Per-agent schemas + execution ---
    if agent_id == "intent_agent_v1":
        bundle_schema = {"type": "object", "required": ["blueprint_draft"], "properties": {"blueprint_draft": {"type": "object"}}}
        request_obj["schema_sha256"] = sha256_hex(bundle_schema)
        prompt_hash = prompt_hash_v1(request=request_obj)
        if llm_mode == "replay":
            response_bundle = cassette.replay_response(prompt_hash)
            if response_bundle is None:
                raise ValueError("cassette miss for prompt_hash (replay mode)")
            bp = response_bundle.get("blueprint_draft")
            if not isinstance(bp, dict):
                raise ValueError("cassette response missing blueprint_draft object")
            code, msg = contracts_validate.validate_payload(bp)
            if code != contracts_validate.EXIT_OK:
                raise ValueError(f"cassette blueprint_draft invalid: {msg}")
            p = out_dir / "blueprint_draft.json"
            _write_json(p, bp)
            output_paths = [p]
        else:
            if llm_provider != "mock":
                prov = get_provider(llm_provider)
                response_bundle, llm_mode = _provider_complete_json_with_fallback(
                    prov_id=llm_provider,
                    prov=prov,
                    llm_mode=llm_mode,
                    cassette=cassette,
                    prompt_hash=prompt_hash,
                    out_dir=out_dir,
                    system=pp.system,
                    user=str(request_obj["user"]),
                    schema=bundle_schema,
                )
                bp = response_bundle.get("blueprint_draft")
                if not isinstance(bp, dict):
                    raise ValueError("real provider must return {blueprint_draft: {...}} bundle")
                code, msg = contracts_validate.validate_payload(bp)
                if code != contracts_validate.EXIT_OK:
                    raise ValueError(f"real provider blueprint_draft invalid: {msg}")
                p = out_dir / "blueprint_draft.json"
                _write_json(p, bp)
                output_paths = [p]
            else:
                from quant_eam.agents.intent_agent import run_intent_agent

                output_paths = run_intent_agent(input_path=input_path, out_dir=out_dir, provider=provider)
                bp = _load_json(out_dir / "blueprint_draft.json")
                response_bundle = {"blueprint_draft": bp} if isinstance(bp, dict) else {}
            if llm_mode == "record":
                cassette.append_call(
                    {
                        "schema_version": "llm_call_v1",
                        "prompt_hash": prompt_hash,
                        "provider_id": llm_provider,
                        "mode": "record",
                        "request": request_obj,
                        "response_json": response_bundle,
                        "extensions": {"redaction_summary_sha256": red_summary.sanitized_sha256},
                    }
                )
        agent_version = "v1"
    elif agent_id == "strategy_spec_agent_v1":
        bundle_schema = {
            "type": "object",
            "required": ["blueprint_final", "signal_dsl", "variable_dictionary", "calc_trace_plan"],
            "properties": {
                "blueprint_final": {"type": "object"},
                "signal_dsl": {"type": "object"},
                "variable_dictionary": {"type": "object"},
                "calc_trace_plan": {"type": "object"},
            },
        }
        request_obj["schema_sha256"] = sha256_hex(bundle_schema)
        prompt_hash = prompt_hash_v1(request=request_obj)
        if llm_mode == "replay":
            response_bundle = cassette.replay_response(prompt_hash)
            if response_bundle is None:
                raise ValueError("cassette miss for prompt_hash (replay mode)")
            bf = response_bundle.get("blueprint_final")
            dsl = response_bundle.get("signal_dsl")
            vd = response_bundle.get("variable_dictionary")
            tp = response_bundle.get("calc_trace_plan")
            for name, obj in (("blueprint_final", bf), ("signal_dsl", dsl), ("variable_dictionary", vd), ("calc_trace_plan", tp)):
                if not isinstance(obj, dict):
                    raise ValueError(f"cassette response missing {name} object")
                code, msg = contracts_validate.validate_payload(obj)
                if code != contracts_validate.EXIT_OK:
                    raise ValueError(f"cassette {name} invalid: {msg}")
            p_blueprint = out_dir / "blueprint_final.json"
            p_dsl = out_dir / "signal_dsl.json"
            p_vars = out_dir / "variable_dictionary.json"
            p_plan = out_dir / "calc_trace_plan.json"
            _write_json(p_blueprint, bf)
            _write_json(p_dsl, dsl)
            _write_json(p_vars, vd)
            _write_json(p_plan, tp)
            output_paths = [p_blueprint, p_dsl, p_vars, p_plan]
        else:
            if llm_provider != "mock":
                prov = get_provider(llm_provider)
                response_bundle, llm_mode = _provider_complete_json_with_fallback(
                    prov_id=llm_provider,
                    prov=prov,
                    llm_mode=llm_mode,
                    cassette=cassette,
                    prompt_hash=prompt_hash,
                    out_dir=out_dir,
                    system=pp.system,
                    user=str(request_obj["user"]),
                    schema=bundle_schema,
                )
                bf = response_bundle.get("blueprint_final")
                dsl = response_bundle.get("signal_dsl")
                vd = response_bundle.get("variable_dictionary")
                tp = response_bundle.get("calc_trace_plan")
                for name, obj in (("blueprint_final", bf), ("signal_dsl", dsl), ("variable_dictionary", vd), ("calc_trace_plan", tp)):
                    if not isinstance(obj, dict):
                        raise ValueError(f"real provider missing {name} object")
                    code, msg = contracts_validate.validate_payload(obj)
                    if code != contracts_validate.EXIT_OK:
                        raise ValueError(f"real provider {name} invalid: {msg}")
                p_blueprint = out_dir / "blueprint_final.json"
                p_dsl = out_dir / "signal_dsl.json"
                p_vars = out_dir / "variable_dictionary.json"
                p_plan = out_dir / "calc_trace_plan.json"
                _write_json(p_blueprint, bf)
                _write_json(p_dsl, dsl)
                _write_json(p_vars, vd)
                _write_json(p_plan, tp)
                output_paths = [p_blueprint, p_dsl, p_vars, p_plan]
            else:
                from quant_eam.agents.strategy_spec_agent import run_strategy_spec_agent

                output_paths = run_strategy_spec_agent(input_path=input_path, out_dir=out_dir, provider=provider)
                response_bundle = {
                    "blueprint_final": _load_json(out_dir / "blueprint_final.json"),
                    "signal_dsl": _load_json(out_dir / "signal_dsl.json"),
                    "variable_dictionary": _load_json(out_dir / "variable_dictionary.json"),
                    "calc_trace_plan": _load_json(out_dir / "calc_trace_plan.json"),
                }
            if llm_mode == "record":
                cassette.append_call(
                    {
                        "schema_version": "llm_call_v1",
                        "prompt_hash": prompt_hash,
                        "provider_id": llm_provider,
                        "mode": "record",
                        "request": request_obj,
                        "response_json": response_bundle,
                        "extensions": {"redaction_summary_sha256": red_summary.sanitized_sha256},
                    }
                )
        agent_version = "v1"
    else:
        if agent_id == "spec_qa_agent_v1":
            bundle_schema = {
                "type": "object",
                "required": ["spec_qa_report", "spec_qa_report_md"],
                "properties": {
                    "spec_qa_report": {"type": "object"},
                    "spec_qa_report_md": {"type": "string"},
                },
            }
            request_obj["schema_sha256"] = sha256_hex(bundle_schema)
            prompt_hash = prompt_hash_v1(request=request_obj)
            if llm_mode == "replay":
                response_bundle = cassette.replay_response(prompt_hash)
                if response_bundle is None:
                    raise ValueError("cassette miss for prompt_hash (replay mode)")
                rep = response_bundle.get("spec_qa_report")
                rep_md = response_bundle.get("spec_qa_report_md")
                if not isinstance(rep, dict) or not isinstance(rep_md, str):
                    raise ValueError("cassette response missing spec_qa_report/spec_qa_report_md")
                report_path = out_dir / "spec_qa_report.json"
                report_md_path = out_dir / "spec_qa_report.md"
                _write_json(report_path, rep)
                _write_text(report_md_path, rep_md)
                output_paths = [report_path, report_md_path]
            else:
                if llm_provider != "mock":
                    prov = get_provider(llm_provider)
                    response_bundle, llm_mode = _provider_complete_json_with_fallback(
                        prov_id=llm_provider,
                        prov=prov,
                        llm_mode=llm_mode,
                        cassette=cassette,
                        prompt_hash=prompt_hash,
                        out_dir=out_dir,
                        system=pp.system,
                        user=str(request_obj["user"]),
                        schema=bundle_schema,
                    )
                    rep = response_bundle.get("spec_qa_report")
                    rep_md = response_bundle.get("spec_qa_report_md")
                    if not isinstance(rep, dict) or not isinstance(rep_md, str):
                        raise ValueError("real provider must return {spec_qa_report: object, spec_qa_report_md: string}")
                    report_path = out_dir / "spec_qa_report.json"
                    report_md_path = out_dir / "spec_qa_report.md"
                    _write_json(report_path, rep)
                    _write_text(report_md_path, rep_md)
                    output_paths = [report_path, report_md_path]
                else:
                    from quant_eam.agents.spec_qa_agent import run_spec_qa_agent

                    output_paths = run_spec_qa_agent(input_path=input_path, out_dir=out_dir, provider=provider)
                    report_path = out_dir / "spec_qa_report.json"
                    report_md_path = out_dir / "spec_qa_report.md"
                    response_bundle = {
                        "spec_qa_report": _load_json(report_path) if report_path.is_file() else {},
                        "spec_qa_report_md": report_md_path.read_text(encoding="utf-8") if report_md_path.is_file() else "",
                    }
                if llm_mode == "record":
                    cassette.append_call(
                        {
                            "schema_version": "llm_call_v1",
                            "prompt_hash": prompt_hash,
                            "provider_id": llm_provider,
                            "mode": "record",
                            "request": request_obj,
                            "response_json": response_bundle,
                            "extensions": {"redaction_summary_sha256": red_summary.sanitized_sha256},
                        }
                    )
            agent_version = "v1"
        elif agent_id == "demo_agent_v1":
            bundle_schema = {
                "type": "object",
                "required": ["demo_plan"],
                "properties": {"demo_plan": {"type": "object"}},
            }
            request_obj["schema_sha256"] = sha256_hex(bundle_schema)
            prompt_hash = prompt_hash_v1(request=request_obj)
            if llm_mode == "replay":
                response_bundle = cassette.replay_response(prompt_hash)
                if response_bundle is None:
                    raise ValueError("cassette miss for prompt_hash (replay mode)")
                demo_plan = response_bundle.get("demo_plan")
                if not isinstance(demo_plan, dict):
                    raise ValueError("cassette response missing demo_plan object")
                out_path = out_dir / "demo_plan.json"
                _write_json(out_path, demo_plan)
                output_paths = [out_path]
            else:
                if llm_provider != "mock":
                    prov = get_provider(llm_provider)
                    response_bundle, llm_mode = _provider_complete_json_with_fallback(
                        prov_id=llm_provider,
                        prov=prov,
                        llm_mode=llm_mode,
                        cassette=cassette,
                        prompt_hash=prompt_hash,
                        out_dir=out_dir,
                        system=pp.system,
                        user=str(request_obj["user"]),
                        schema=bundle_schema,
                    )
                    demo_plan = response_bundle.get("demo_plan")
                    if not isinstance(demo_plan, dict):
                        raise ValueError("real provider must return {demo_plan: object}")
                    out_path = out_dir / "demo_plan.json"
                    _write_json(out_path, demo_plan)
                    output_paths = [out_path]
                else:
                    from quant_eam.agents.demo_agent import run_demo_agent

                    output_paths = run_demo_agent(input_path=input_path, out_dir=out_dir, provider=provider)
                    out_path = out_dir / "demo_plan.json"
                    response_bundle = {"demo_plan": _load_json(out_path) if out_path.is_file() else {}}
                if llm_mode == "record":
                    cassette.append_call(
                        {
                            "schema_version": "llm_call_v1",
                            "prompt_hash": prompt_hash,
                            "provider_id": llm_provider,
                            "mode": "record",
                            "request": request_obj,
                            "response_json": response_bundle,
                            "extensions": {"redaction_summary_sha256": red_summary.sanitized_sha256},
                        }
                    )
            agent_version = "v1"
        elif agent_id == "backtest_agent_v1":
            bundle_schema = {
                "type": "object",
                "required": ["backtest_plan"],
                "properties": {"backtest_plan": {"type": "object"}},
            }
            request_obj["schema_sha256"] = sha256_hex(bundle_schema)
            prompt_hash = prompt_hash_v1(request=request_obj)
            if llm_mode == "replay":
                response_bundle = cassette.replay_response(prompt_hash)
                if response_bundle is None:
                    raise ValueError("cassette miss for prompt_hash (replay mode)")
                backtest_plan = response_bundle.get("backtest_plan")
                if not isinstance(backtest_plan, dict):
                    raise ValueError("cassette response missing backtest_plan object")
                out_path = out_dir / "backtest_plan.json"
                _write_json(out_path, backtest_plan)
                output_paths = [out_path]
            else:
                if llm_provider != "mock":
                    prov = get_provider(llm_provider)
                    response_bundle, llm_mode = _provider_complete_json_with_fallback(
                        prov_id=llm_provider,
                        prov=prov,
                        llm_mode=llm_mode,
                        cassette=cassette,
                        prompt_hash=prompt_hash,
                        out_dir=out_dir,
                        system=pp.system,
                        user=str(request_obj["user"]),
                        schema=bundle_schema,
                    )
                    backtest_plan = response_bundle.get("backtest_plan")
                    if not isinstance(backtest_plan, dict):
                        raise ValueError("real provider must return {backtest_plan: object}")
                    out_path = out_dir / "backtest_plan.json"
                    _write_json(out_path, backtest_plan)
                    output_paths = [out_path]
                else:
                    from quant_eam.agents.backtest_agent import run_backtest_agent

                    output_paths = run_backtest_agent(input_path=input_path, out_dir=out_dir, provider=provider)
                    out_path = out_dir / "backtest_plan.json"
                    response_bundle = {"backtest_plan": _load_json(out_path) if out_path.is_file() else {}}
                if llm_mode == "record":
                    cassette.append_call(
                        {
                            "schema_version": "llm_call_v1",
                            "prompt_hash": prompt_hash,
                            "provider_id": llm_provider,
                            "mode": "record",
                            "request": request_obj,
                            "response_json": response_bundle,
                            "extensions": {"redaction_summary_sha256": red_summary.sanitized_sha256},
                        }
                    )
            agent_version = "v1"
        else:
            if agent_id == "report_agent_v1":
                bundle_schema = {
                    "type": "object",
                    "required": ["report_md", "report_summary"],
                    "properties": {"report_md": {"type": "string"}, "report_summary": {"type": "object"}},
                }
                request_obj["schema_sha256"] = sha256_hex(bundle_schema)
                prompt_hash = prompt_hash_v1(request=request_obj)
                if llm_mode == "replay":
                    response_bundle = cassette.replay_response(prompt_hash)
                    if response_bundle is None:
                        raise ValueError("cassette miss for prompt_hash (replay mode)")
                    md = response_bundle.get("report_md")
                    summ = response_bundle.get("report_summary")
                    if not isinstance(md, str) or not isinstance(summ, dict):
                        raise ValueError("cassette response missing report_md/report_summary")
                    report_md = out_dir / "report_agent.md"
                    summary_path = out_dir / "report_summary.json"
                    _write_text(report_md, md)
                    _write_json(summary_path, summ)
                    output_paths = [report_md, summary_path]
                else:
                    if llm_provider != "mock":
                        prov = get_provider(llm_provider)
                        response_bundle, llm_mode = _provider_complete_json_with_fallback(
                            prov_id=llm_provider,
                            prov=prov,
                            llm_mode=llm_mode,
                            cassette=cassette,
                            prompt_hash=prompt_hash,
                            out_dir=out_dir,
                            system=pp.system,
                            user=str(request_obj["user"]),
                            schema=bundle_schema,
                        )
                        md = response_bundle.get("report_md")
                        summ = response_bundle.get("report_summary")
                        if not isinstance(md, str) or not isinstance(summ, dict):
                            raise ValueError("real provider must return {report_md: str, report_summary: object}")
                        report_md = out_dir / "report_agent.md"
                        summary_path = out_dir / "report_summary.json"
                        _write_text(report_md, md)
                        _write_json(summary_path, summ)
                        output_paths = [report_md, summary_path]
                    else:
                        from quant_eam.agents.report_agent import run_report_agent

                        output_paths = run_report_agent(input_path=input_path, out_dir=out_dir, provider=provider)
                        report_md = out_dir / "report_agent.md"
                        summ_p = out_dir / "report_summary.json"
                        response_bundle = {
                            "report_md": report_md.read_text(encoding="utf-8") if report_md.is_file() else "",
                            "report_summary": _load_json(summ_p) if summ_p.is_file() else {},
                        }
                    if llm_mode == "record":
                        cassette.append_call(
                            {
                                "schema_version": "llm_call_v1",
                                "prompt_hash": prompt_hash,
                                "provider_id": llm_provider,
                                "mode": "record",
                                "request": request_obj,
                                "response_json": response_bundle,
                                "extensions": {"redaction_summary_sha256": red_summary.sanitized_sha256},
                            }
                        )
                agent_version = "v1"
            elif agent_id == "diagnostics_agent_v1":
                bundle_schema = {
                    "type": "object",
                    "required": ["diagnostics_plan"],
                    "properties": {"diagnostics_plan": {"type": "object"}},
                }
                request_obj["schema_sha256"] = sha256_hex(bundle_schema)
                prompt_hash = prompt_hash_v1(request=request_obj)
                if llm_mode == "replay":
                    response_bundle = cassette.replay_response(prompt_hash)
                    if response_bundle is None:
                        raise ValueError("cassette miss for prompt_hash (replay mode)")
                    plan = response_bundle.get("diagnostics_plan")
                    if not isinstance(plan, dict):
                        raise ValueError("cassette response missing diagnostics_plan object")
                    out_path = out_dir / "diagnostics_plan.json"
                    _write_json(out_path, plan)
                    output_paths = [out_path]
                else:
                    if llm_provider != "mock":
                        prov = get_provider(llm_provider)
                        response_bundle, llm_mode = _provider_complete_json_with_fallback(
                            prov_id=llm_provider,
                            prov=prov,
                            llm_mode=llm_mode,
                            cassette=cassette,
                            prompt_hash=prompt_hash,
                            out_dir=out_dir,
                            system=pp.system,
                            user=str(request_obj["user"]),
                            schema=bundle_schema,
                        )
                        plan = response_bundle.get("diagnostics_plan")
                        if not isinstance(plan, dict):
                            raise ValueError("real provider must return {diagnostics_plan: object}")
                        out_path = out_dir / "diagnostics_plan.json"
                        _write_json(out_path, plan)
                        output_paths = [out_path]
                    else:
                        from quant_eam.agents.diagnostics_agent import run_diagnostics_agent

                        output_paths = run_diagnostics_agent(input_path=input_path, out_dir=out_dir, provider=provider)
                        out_path = out_dir / "diagnostics_plan.json"
                        response_bundle = {"diagnostics_plan": _load_json(out_path) if out_path.is_file() else {}}
                    if llm_mode == "record":
                        cassette.append_call(
                            {
                                "schema_version": "llm_call_v1",
                                "prompt_hash": prompt_hash,
                                "provider_id": llm_provider,
                                "mode": "record",
                                "request": request_obj,
                                "response_json": response_bundle,
                                "extensions": {"redaction_summary_sha256": red_summary.sanitized_sha256},
                            }
                        )
                agent_version = "v1"
            elif agent_id == "registry_curator_v1":
                bundle_schema = {
                    "type": "object",
                    "required": ["registry_curator_summary"],
                    "properties": {"registry_curator_summary": {"type": "object"}},
                }
                request_obj["schema_sha256"] = sha256_hex(bundle_schema)
                prompt_hash = prompt_hash_v1(request=request_obj)
                if llm_mode == "replay":
                    response_bundle = cassette.replay_response(prompt_hash)
                    if response_bundle is None:
                        raise ValueError("cassette miss for prompt_hash (replay mode)")
                    summary = response_bundle.get("registry_curator_summary")
                    if not isinstance(summary, dict):
                        raise ValueError("cassette response missing registry_curator_summary object")
                    out_path = out_dir / "registry_curator_summary.json"
                    _write_json(out_path, summary)
                    output_paths = [out_path]
                else:
                    if llm_provider != "mock":
                        prov = get_provider(llm_provider)
                        response_bundle, llm_mode = _provider_complete_json_with_fallback(
                            prov_id=llm_provider,
                            prov=prov,
                            llm_mode=llm_mode,
                            cassette=cassette,
                            prompt_hash=prompt_hash,
                            out_dir=out_dir,
                            system=pp.system,
                            user=str(request_obj["user"]),
                            schema=bundle_schema,
                        )
                        summary = response_bundle.get("registry_curator_summary")
                        if not isinstance(summary, dict):
                            raise ValueError("real provider must return {registry_curator_summary: object}")
                        out_path = out_dir / "registry_curator_summary.json"
                        _write_json(out_path, summary)
                        output_paths = [out_path]
                    else:
                        from quant_eam.agents.registry_curator_agent import run_registry_curator_agent

                        output_paths = run_registry_curator_agent(input_path=input_path, out_dir=out_dir, provider=provider)
                        out_path = out_dir / "registry_curator_summary.json"
                        response_bundle = {"registry_curator_summary": _load_json(out_path) if out_path.is_file() else {}}
                    if llm_mode == "record":
                        cassette.append_call(
                            {
                                "schema_version": "llm_call_v1",
                                "prompt_hash": prompt_hash,
                                "provider_id": llm_provider,
                                "mode": "record",
                                "request": request_obj,
                                "response_json": response_bundle,
                                "extensions": {"redaction_summary_sha256": red_summary.sanitized_sha256},
                            }
                        )
                agent_version = "v1"
            elif agent_id == "composer_agent_v1":
                bundle_schema = {
                    "type": "object",
                    "required": ["composer_agent_plan"],
                    "properties": {"composer_agent_plan": {"type": "object"}},
                }
                request_obj["schema_sha256"] = sha256_hex(bundle_schema)
                prompt_hash = prompt_hash_v1(request=request_obj)
                if llm_mode == "replay":
                    response_bundle = cassette.replay_response(prompt_hash)
                    if response_bundle is None:
                        raise ValueError("cassette miss for prompt_hash (replay mode)")
                    plan = response_bundle.get("composer_agent_plan")
                    if not isinstance(plan, dict):
                        raise ValueError("cassette response missing composer_agent_plan object")
                    out_path = out_dir / "composer_agent_plan.json"
                    _write_json(out_path, plan)
                    output_paths = [out_path]
                else:
                    if llm_provider != "mock":
                        prov = get_provider(llm_provider)
                        response_bundle, llm_mode = _provider_complete_json_with_fallback(
                            prov_id=llm_provider,
                            prov=prov,
                            llm_mode=llm_mode,
                            cassette=cassette,
                            prompt_hash=prompt_hash,
                            out_dir=out_dir,
                            system=pp.system,
                            user=str(request_obj["user"]),
                            schema=bundle_schema,
                        )
                        plan = response_bundle.get("composer_agent_plan")
                        if not isinstance(plan, dict):
                            raise ValueError("real provider must return {composer_agent_plan: object}")
                        out_path = out_dir / "composer_agent_plan.json"
                        _write_json(out_path, plan)
                        output_paths = [out_path]
                    else:
                        from quant_eam.agents.composer_agent import run_composer_agent

                        output_paths = run_composer_agent(input_path=input_path, out_dir=out_dir, provider=provider)
                        out_path = out_dir / "composer_agent_plan.json"
                        response_bundle = {"composer_agent_plan": _load_json(out_path) if out_path.is_file() else {}}
                    if llm_mode == "record":
                        cassette.append_call(
                            {
                                "schema_version": "llm_call_v1",
                                "prompt_hash": prompt_hash,
                                "provider_id": llm_provider,
                                "mode": "record",
                                "request": request_obj,
                                "response_json": response_bundle,
                                "extensions": {"redaction_summary_sha256": red_summary.sanitized_sha256},
                            }
                        )
                agent_version = "v1"
            else:
                bundle_schema = {
                    "type": "object",
                    "required": ["improvement_proposals"],
                    "properties": {"improvement_proposals": {"type": "object"}},
                }
                request_obj["schema_sha256"] = sha256_hex(bundle_schema)
                prompt_hash = prompt_hash_v1(request=request_obj)
                if llm_mode == "replay":
                    response_bundle = cassette.replay_response(prompt_hash)
                    if response_bundle is None:
                        raise ValueError("cassette miss for prompt_hash (replay mode)")
                    props = response_bundle.get("improvement_proposals")
                    if not isinstance(props, dict):
                        raise ValueError("cassette response missing improvement_proposals object")
                    code, msg = contracts_validate.validate_payload(props)
                    if code != contracts_validate.EXIT_OK:
                        raise ValueError(f"cassette improvement_proposals invalid: {msg}")
                    out_path = out_dir / "improvement_proposals.json"
                    _write_json(out_path, props)
                    output_paths = [out_path]
                else:
                    if llm_provider != "mock":
                        prov = get_provider(llm_provider)
                        response_bundle, llm_mode = _provider_complete_json_with_fallback(
                            prov_id=llm_provider,
                            prov=prov,
                            llm_mode=llm_mode,
                            cassette=cassette,
                            prompt_hash=prompt_hash,
                            out_dir=out_dir,
                            system=pp.system,
                            user=str(request_obj["user"]),
                            schema=bundle_schema,
                        )
                        props = response_bundle.get("improvement_proposals")
                        if not isinstance(props, dict):
                            raise ValueError("real provider missing improvement_proposals object")
                        code, msg = contracts_validate.validate_payload(props)
                        if code != contracts_validate.EXIT_OK:
                            raise ValueError(f"real provider improvement_proposals invalid: {msg}")
                        out_path = out_dir / "improvement_proposals.json"
                        _write_json(out_path, props)
                        output_paths = [out_path]
                    else:
                        from quant_eam.agents.improvement_agent import run_improvement_agent

                        output_paths = run_improvement_agent(input_path=input_path, out_dir=out_dir, provider=provider)
                        props = _load_json(out_dir / "improvement_proposals.json")
                        response_bundle = {"improvement_proposals": props} if isinstance(props, dict) else {}
                    if llm_mode == "record":
                        cassette.append_call(
                            {
                                "schema_version": "llm_call_v1",
                                "prompt_hash": prompt_hash,
                                "provider_id": llm_provider,
                                "mode": "record",
                                "request": request_obj,
                                "response_json": response_bundle,
                                "extensions": {"redaction_summary_sha256": red_summary.sanitized_sha256},
                            }
                        )
                agent_version = "v1"

    assert response_bundle is not None
    end_t = time.perf_counter()
    wall_s = max(0.0, float(end_t - start_t))

    call_obj = {
        "schema_version": "llm_call_v1",
        "prompt_hash": prompt_hash,
        "provider_id": llm_provider,
        "mode": llm_mode,
        "request": request_obj,
        "response_json": response_bundle,
        "extensions": {"redaction_summary_sha256": red_summary.sanitized_sha256},
    }
    code_c, msg_c = contracts_validate.validate_payload(call_obj)
    if code_c != contracts_validate.EXIT_OK:
        raise ValueError(f"invalid llm_call_v1: {msg_c}")
    evidence_calls.append_call(call_obj)

    guard = validate_agent_output(
        agent_id=agent_id,
        output_json=response_bundle,
        prompt_version=pp.prompt_version,
        output_schema_version=pp.output_schema_version,
    )
    code_g, msg_g = contracts_validate.validate_payload(guard)
    if code_g != contracts_validate.EXIT_OK:
        raise ValueError(f"invalid output_guard_report_v1: {msg_g}")
    guard_path = out_dir / "output_guard_report.json"
    _write_json(guard_path, guard)

    session = {
        "schema_version": "llm_session_v1",
        "provider_id": llm_provider,
        "mode": llm_mode,
        "call_count": 1,
        "prompt_hashes": [prompt_hash],
        "cassette_path": cassette_path.as_posix(),
        "evidence_calls_path": evidence_calls_path.as_posix(),
        "promptpack_path": pp.path.as_posix(),
        "prompt_version": pp.prompt_version,
        "output_schema_version": pp.output_schema_version,
        "extensions": {
            "redaction_summary_sha256": red_summary.sanitized_sha256,
            "promptpack_sha256": pp_sha,
            "guard_passed": bool(guard.get("passed")),
            "guard_finding_count": int(guard.get("finding_count", 0) or 0),
            "output_guard_report_ref": guard_path.as_posix(),
        },
    }
    code_s, msg_s = contracts_validate.validate_payload(session)
    if code_s != contracts_validate.EXIT_OK:
        raise ValueError(f"invalid llm_session_v1: {msg_s}")
    session_path = out_dir / "llm_session.json"
    _write_json(session_path, session)

    # Job-level usage update (Phase-26) after a successful (non-blocked) agent run.
    if job_id and thresholds:
        prompt_chars = len(str(request_obj.get("system") or "")) + len(str(request_obj.get("user") or ""))
        response_chars = len(json.dumps(response_bundle, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
        delta = UsageTotals(calls=1, prompt_chars=prompt_chars, response_chars=response_chars, wall_seconds=wall_s)
        totals2, _by, _sr = aggregate_totals(job_id=job_id, job_root=default_job_root())
        would_exceed_post = {
            "max_calls_per_job": (totals2.calls + delta.calls) > thresholds.max_calls_per_job,
            "max_prompt_chars_per_job": (totals2.prompt_chars + delta.prompt_chars) > thresholds.max_prompt_chars_per_job,
            "max_response_chars_per_job": (totals2.response_chars + delta.response_chars) > thresholds.max_response_chars_per_job,
            "max_wall_seconds_per_job": (totals2.wall_seconds + delta.wall_seconds) > float(thresholds.max_wall_seconds_per_job),
        }
        stop_reason = _budget_reason_from_would_exceed(would_exceed_post) if any(would_exceed_post.values()) else None
        write_usage_event(
            job_id=job_id,
            agent_id=agent_id,
            event_type="CALL_COMPLETED",
            delta=delta,
            thresholds=thresholds,
            would_exceed=would_exceed_post if any(would_exceed_post.values()) else None,
            stop_reason=stop_reason,
            evidence_refs={
                "agent_out_dir": out_dir.as_posix(),
                "llm_calls_path": evidence_calls_path.as_posix(),
                "llm_session_path": session_path.as_posix(),
                "redaction_summary_path": redaction_path.as_posix(),
                "cassette_path": cassette_path.as_posix(),
            },
            job_root=default_job_root(),
        )
        _ = write_usage_report(job_id=job_id, thresholds=thresholds, job_root=default_job_root())

    agent_run = {
        "schema_version": "agent_run_v1",
        "agent_id": agent_id,
        "agent_version": agent_version,
        "provider": provider,
        "input_ref": input_path.as_posix(),
        "input_sha256": in_sha,
        "output_refs": [p.as_posix() for p in output_paths],
        "extensions": {
            "llm": {
                "provider_id": llm_provider,
                "mode": llm_mode,
                "cassette_path": cassette_path.as_posix(),
                "prompt_hashes": [prompt_hash],
                "llm_session_ref": session_path.as_posix(),
                "llm_calls_ref": evidence_calls_path.as_posix(),
                "redaction_summary_ref": redaction_path.as_posix(),
                "output_guard_report_ref": guard_path.as_posix(),
                "llm_usage_report_ref": (
                    llm_usage_paths(job_id=job_id, job_root=default_job_root()).report.as_posix() if job_id else None
                ),
            }
        },
    }
    code, msg = contracts_validate.validate_payload(agent_run)
    if code != contracts_validate.EXIT_OK:
        raise ValueError(f"invalid agent_run_v1: {msg}")
    agent_run_path = out_dir / "agent_run.json"
    _write_json(agent_run_path, agent_run)
    return AgentResult(agent_run_path=agent_run_path, output_paths=output_paths)
