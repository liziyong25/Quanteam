from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from quant_eam.compiler.compile import compile_blueprint_to_runspec
from quant_eam.gaterunner.run import EXIT_OK as GATE_OK
from quant_eam.gaterunner.run import run_once as gaterunner_run_once
from quant_eam.jobstore.store import (
    append_event,
    job_paths,
    load_job_events,
    load_job_spec,
    resolve_repo_relative,
    write_outputs_index,
)
from quant_eam.registry.cards import create_card_from_run
from quant_eam.registry.errors import RegistryInvalid
from quant_eam.registry.storage import default_registry_root
from quant_eam.registry.triallog import record_trial
from quant_eam.runner.run import EXIT_OK as RUN_OK
from quant_eam.runner.run import run_once as runner_run_once


EVENTS_ORDER = [
    "BLUEPRINT_SUBMITTED",
    "IDEA_SUBMITTED",
    "BLUEPRINT_PROPOSED",
    "STRATEGY_SPEC_PROPOSED",
    "RUNSPEC_COMPILED",
    "WAITING_APPROVAL",
    "APPROVED",
    "TRACE_PREVIEW_COMPLETED",
    "RUN_COMPLETED",
    "GATES_COMPLETED",
    "REGISTRY_UPDATED",
    "REPORT_COMPLETED",
    "IMPROVEMENTS_PROPOSED",
    "SPAWNED",
    "STOPPED_BUDGET",
    "DONE",
    "ERROR",
]


def _utc_now_iso() -> str:
    sde = os.getenv("SOURCE_DATE_EPOCH")
    if sde and sde.isdigit():
        return datetime.fromtimestamp(int(sde), tz=timezone.utc).isoformat()
    return datetime.now(tz=timezone.utc).isoformat()


def _env_llm_provider_id() -> str:
    return str(os.getenv("EAM_LLM_PROVIDER", "mock")).strip() or "mock"


def _env_llm_mode() -> str:
    return str(os.getenv("EAM_LLM_MODE", "live")).strip() or "live"


def _env_llm_model() -> str | None:
    m = str(os.getenv("EAM_LLM_REAL_MODEL", "")).strip()
    return m or None


def _needs_llm_live_confirm() -> bool:
    # Phase-28: live/record with a real provider requires a second explicit approval checkpoint.
    return _env_llm_provider_id() == "real" and _env_llm_mode() in ("live", "record")


def _has_waiting_step(events: list[dict[str, Any]], step: str) -> bool:
    if not events:
        return False
    ev = events[-1]
    if str(ev.get("event_type", "")) != "WAITING_APPROVAL":
        return False
    out = ev.get("outputs") if isinstance(ev.get("outputs"), dict) else {}
    return str(out.get("step") or "") == str(step)


def _last_event_type(events: list[dict[str, Any]]) -> str | None:
    if not events:
        return None
    return str(events[-1].get("event_type", "") or "")


def _has_event(events: list[dict[str, Any]], event_type: str) -> bool:
    return any(str(ev.get("event_type", "")) == event_type for ev in events)


def _is_approved(events: list[dict[str, Any]], *, step: str | None) -> bool:
    if step is None:
        return any(str(ev.get("event_type", "")) == "APPROVED" for ev in events)
    for ev in events:
        if str(ev.get("event_type", "")) != "APPROVED":
            continue
        out = ev.get("outputs") if isinstance(ev.get("outputs"), dict) else {}
        if str(out.get("step") or "") == step:
            return True
    return False


def _parse_json_maybe(s: str) -> dict[str, Any]:
    try:
        doc = json.loads(s)
        return doc if isinstance(doc, dict) else {}
    except Exception:
        return {}


def _extract_sweep_spec(spec: dict[str, Any]) -> dict[str, Any] | None:
    # IdeaSpec may carry sweep_spec at top-level or under extensions.
    if isinstance(spec.get("sweep_spec"), dict):
        return spec.get("sweep_spec")
    ext = spec.get("extensions")
    if isinstance(ext, dict) and isinstance(ext.get("sweep_spec"), dict):
        return ext.get("sweep_spec")
    # JobSpec v1 may carry sweep_spec under blueprint.extensions or job_spec.extensions.
    if isinstance(ext, dict) and isinstance(ext.get("sweep_spec"), dict):
        return ext.get("sweep_spec")
    bp = spec.get("blueprint") if isinstance(spec.get("blueprint"), dict) else {}
    if isinstance(bp, dict) and isinstance(bp.get("extensions"), dict) and isinstance(bp["extensions"].get("sweep_spec"), dict):
        return bp["extensions"].get("sweep_spec")
    return None


def _sweep_evidence_exists(job_id: str) -> bool:
    p = job_paths(job_id).outputs_dir / "sweep" / "leaderboard.json"
    return p.is_file()


def _artifact_root() -> Path:
    return Path(os.getenv("EAM_ARTIFACT_ROOT", "/artifacts"))


def _data_root() -> Path:
    return Path(os.getenv("EAM_DATA_ROOT", "/data"))


def advance_job_once(*, job_id: str) -> dict[str, Any]:
    """Advance a single job until blocked (WAITING_APPROVAL) or terminal (DONE/ERROR)."""
    spec = load_job_spec(job_id)
    paths = job_paths(job_id)

    schema_version = str(spec.get("schema_version", "")).strip() if isinstance(spec, dict) else ""

    while True:
        events = load_job_events(job_id)
        if _has_event(events, "DONE"):
            return {"job_id": job_id, "status": "noop", "state": "DONE"}
        if _has_event(events, "ERROR"):
            return {"job_id": job_id, "status": "noop", "state": "ERROR"}

        # Phase-26: enforce job-level LLM budget stop as terminal (do not allow bypass).
        try:
            from quant_eam.jobstore.llm_usage import is_budget_stopped, llm_usage_paths

            stopped, reason = is_budget_stopped(job_id=job_id)
            if stopped:
                if not _has_event(events, "STOPPED_BUDGET"):
                    up = llm_usage_paths(job_id=job_id)
                    append_event(
                        job_id=job_id,
                        event_type="STOPPED_BUDGET",
                        message=str(reason or "budget_stopped"),
                        outputs={"reason": reason, "llm_usage_report_path": up.report.as_posix()},
                    )
                    append_event(job_id=job_id, event_type="DONE", outputs={"status": "stopped_budget"})
                return {"job_id": job_id, "status": "stopped", "state": "STOPPED_BUDGET", "reason": reason}
        except Exception:
            pass

        if schema_version == "idea_spec_v1":
            # Idea workflow v1: idea -> intent -> (approve blueprint) -> compile -> (approve runspec) -> run -> gates -> registry -> report.
            snapshot_id = str(spec.get("snapshot_id", "")).strip()
            policy_bundle_path = str(spec.get("policy_bundle_path", "")).strip() or "policies/policy_bundle_v1.yaml"
            budget_policy_path = str(spec.get("budget_policy_path", "")).strip() or "policies/budget_policy_v1.yaml"
            pb_path = resolve_repo_relative(policy_bundle_path)
            bp_budget_path = resolve_repo_relative(budget_policy_path)

            # Phase-28: second explicit review point before any LIVE/RECORD call to a real provider.
            if _needs_llm_live_confirm() and not _is_approved(events, step="llm_live_confirm"):
                if not _has_waiting_step(events, "llm_live_confirm"):
                    append_event(
                        job_id=job_id,
                        event_type="WAITING_APPROVAL",
                        outputs={
                            "step": "llm_live_confirm",
                            "llm_provider_id": _env_llm_provider_id(),
                            "llm_mode": _env_llm_mode(),
                            "llm_model": _env_llm_model(),
                        },
                    )
                return {"job_id": job_id, "status": "blocked", "state": "WAITING_APPROVAL", "step": "llm_live_confirm"}

            # 0) Propose blueprint via IntentAgent.
            if not _has_event(events, "BLUEPRINT_PROPOSED"):
                from quant_eam.agents.harness import run_agent

                in_path = paths.job_spec
                out_dir = paths.outputs_dir / "agents" / "intent"
                try:
                    res = run_agent(agent_id="intent_agent_v1", input_path=in_path, out_dir=out_dir, provider="mock")
                except Exception as e:  # noqa: BLE001
                    err_p = out_dir / "error_summary.json"
                    append_event(
                        job_id=job_id,
                        event_type="ERROR",
                        message="STOPPED_LLM_ERROR",
                        outputs={
                            "reason": "STOPPED_LLM_ERROR",
                            "step": "intent_agent_v1",
                            "error": str(e),
                            "error_summary_path": err_p.as_posix() if err_p.is_file() else None,
                        },
                    )
                    append_event(job_id=job_id, event_type="DONE", outputs={"status": "stopped_llm_error"})
                    return {"job_id": job_id, "status": "stopped", "state": "ERROR", "reason": "STOPPED_LLM_ERROR"}
                # If harness budget-stopped, terminate job deterministically.
                try:
                    ar = json.loads(res.agent_run_path.read_text(encoding="utf-8"))
                    llm = (ar.get("extensions") or {}).get("llm") if isinstance(ar, dict) else None
                    if isinstance(llm, dict) and bool(llm.get("budget_stopped")):
                        reason = str(llm.get("stop_reason") or "budget_stopped")
                        append_event(job_id=job_id, event_type="STOPPED_BUDGET", message=reason, outputs={"reason": reason, "agent_id": "intent_agent_v1"})
                        append_event(job_id=job_id, event_type="DONE", outputs={"status": "stopped_budget"})
                        return {"job_id": job_id, "status": "stopped", "state": "STOPPED_BUDGET", "reason": reason}
                except Exception:
                    pass
                blueprint_draft_path = out_dir / "blueprint_draft.json"
                # Phase-28: if output guard FAIL, force review before continuing.
                try:
                    guard = json.loads((out_dir / "output_guard_report.json").read_text(encoding="utf-8"))
                except Exception:
                    guard = {}
                if isinstance(guard, dict) and guard.get("passed") is False and not _is_approved(events, step="agent_output_invalid"):
                    if not _has_waiting_step(events, "agent_output_invalid"):
                        append_event(
                            job_id=job_id,
                            event_type="WAITING_APPROVAL",
                            outputs={
                                "step": "agent_output_invalid",
                                "agent_id": "intent_agent_v1",
                                "output_guard_report_path": (out_dir / "output_guard_report.json").as_posix(),
                                "finding_count": int(guard.get("finding_count", 0) or 0),
                            },
                        )
                    return {"job_id": job_id, "status": "blocked", "state": "WAITING_APPROVAL", "step": "agent_output_invalid"}
                write_outputs_index(
                    job_id=job_id,
                    updates={
                        "blueprint_draft_path": blueprint_draft_path.as_posix(),
                        "intent_agent_run_path": res.agent_run_path.as_posix(),
                        "snapshot_id": snapshot_id,
                        "policy_bundle_path": policy_bundle_path,
                    },
                )
                append_event(
                    job_id=job_id,
                    event_type="BLUEPRINT_PROPOSED",
                    outputs={"blueprint_draft_path": blueprint_draft_path.as_posix()},
                )
                append_event(job_id=job_id, event_type="WAITING_APPROVAL", outputs={"step": "blueprint"})
                continue

            # Checkpoint 1: blueprint approval.
            if not _is_approved(events, step="blueprint"):
                return {"job_id": job_id, "status": "blocked", "state": "WAITING_APPROVAL", "step": "blueprint"}

            # 1) Propose strategy spec (DSL/VarDict/TracePlan) from approved blueprint draft.
            if not _has_event(events, "STRATEGY_SPEC_PROPOSED"):
                from quant_eam.agents.harness import run_agent

                idx = json.loads((paths.outputs_dir / "outputs.json").read_text(encoding="utf-8"))
                bp_draft_path = Path(str(idx.get("blueprint_draft_path", "")))
                if not bp_draft_path.is_file():
                    append_event(job_id=job_id, event_type="ERROR", message="missing blueprint_draft_path", outputs={"step": "strategy_spec"})
                    continue

                bp_draft = json.loads(bp_draft_path.read_text(encoding="utf-8"))
                agent_in = {"blueprint_draft": bp_draft, "idea_spec": spec}

                out_dir = paths.outputs_dir / "agents" / "strategy_spec"
                agent_in_path = out_dir / "agent_input.json"
                agent_in_path.parent.mkdir(parents=True, exist_ok=True)
                agent_in_path.write_text(json.dumps(agent_in, indent=2, sort_keys=True) + "\n", encoding="utf-8")

                try:
                    res = run_agent(agent_id="strategy_spec_agent_v1", input_path=agent_in_path, out_dir=out_dir, provider="mock")
                except Exception as e:  # noqa: BLE001
                    err_p = out_dir / "error_summary.json"
                    append_event(
                        job_id=job_id,
                        event_type="ERROR",
                        message="STOPPED_LLM_ERROR",
                        outputs={
                            "reason": "STOPPED_LLM_ERROR",
                            "step": "strategy_spec_agent_v1",
                            "error": str(e),
                            "error_summary_path": err_p.as_posix() if err_p.is_file() else None,
                        },
                    )
                    append_event(job_id=job_id, event_type="DONE", outputs={"status": "stopped_llm_error"})
                    return {"job_id": job_id, "status": "stopped", "state": "ERROR", "reason": "STOPPED_LLM_ERROR"}
                try:
                    ar = json.loads(res.agent_run_path.read_text(encoding="utf-8"))
                    llm = (ar.get("extensions") or {}).get("llm") if isinstance(ar, dict) else None
                    if isinstance(llm, dict) and bool(llm.get("budget_stopped")):
                        reason = str(llm.get("stop_reason") or "budget_stopped")
                        append_event(job_id=job_id, event_type="STOPPED_BUDGET", message=reason, outputs={"reason": reason, "agent_id": "strategy_spec_agent_v1"})
                        append_event(job_id=job_id, event_type="DONE", outputs={"status": "stopped_budget"})
                        return {"job_id": job_id, "status": "stopped", "state": "STOPPED_BUDGET", "reason": reason}
                except Exception:
                    pass

                p_blueprint_final = out_dir / "blueprint_final.json"
                p_dsl = out_dir / "signal_dsl.json"
                p_vars = out_dir / "variable_dictionary.json"
                p_plan = out_dir / "calc_trace_plan.json"

                try:
                    guard = json.loads((out_dir / "output_guard_report.json").read_text(encoding="utf-8"))
                except Exception:
                    guard = {}
                if isinstance(guard, dict) and guard.get("passed") is False and not _is_approved(events, step="agent_output_invalid"):
                    if not _has_waiting_step(events, "agent_output_invalid"):
                        append_event(
                            job_id=job_id,
                            event_type="WAITING_APPROVAL",
                            outputs={
                                "step": "agent_output_invalid",
                                "agent_id": "strategy_spec_agent_v1",
                                "output_guard_report_path": (out_dir / "output_guard_report.json").as_posix(),
                                "finding_count": int(guard.get("finding_count", 0) or 0),
                            },
                        )
                    return {"job_id": job_id, "status": "blocked", "state": "WAITING_APPROVAL", "step": "agent_output_invalid"}

                write_outputs_index(
                    job_id=job_id,
                    updates={
                        "strategy_spec_agent_run_path": res.agent_run_path.as_posix(),
                        "blueprint_final_path": p_blueprint_final.as_posix(),
                        "signal_dsl_path": p_dsl.as_posix(),
                        "variable_dictionary_path": p_vars.as_posix(),
                        "calc_trace_plan_path": p_plan.as_posix(),
                    },
                )
                append_event(
                    job_id=job_id,
                    event_type="STRATEGY_SPEC_PROPOSED",
                    outputs={"blueprint_final_path": p_blueprint_final.as_posix()},
                )
                append_event(job_id=job_id, event_type="WAITING_APPROVAL", outputs={"step": "strategy_spec"})
                continue

            # Checkpoint 2: strategy_spec approval.
            if not _is_approved(events, step="strategy_spec"):
                return {"job_id": job_id, "status": "blocked", "state": "WAITING_APPROVAL", "step": "strategy_spec"}

            # 2.5) Spec-QA step (read-only) and dedicated checkpoint before compile.
            idx_path = paths.outputs_dir / "outputs.json"
            idx_now = json.loads(idx_path.read_text(encoding="utf-8")) if idx_path.is_file() else {}
            if not isinstance(idx_now, dict):
                idx_now = {}
            spec_qa_report_path = Path(str(idx_now.get("spec_qa_report_path", "")))
            if not spec_qa_report_path.is_file():
                from quant_eam.agents.harness import run_agent

                agent_in = {
                    "idea_spec": spec,
                    "blueprint_final": json.loads(Path(str(idx_now.get("blueprint_final_path", ""))).read_text(encoding="utf-8")),
                    "signal_dsl": json.loads(Path(str(idx_now.get("signal_dsl_path", ""))).read_text(encoding="utf-8")),
                    "variable_dictionary": json.loads(Path(str(idx_now.get("variable_dictionary_path", ""))).read_text(encoding="utf-8")),
                    "calc_trace_plan": json.loads(Path(str(idx_now.get("calc_trace_plan_path", ""))).read_text(encoding="utf-8")),
                }

                out_dir = paths.outputs_dir / "agents" / "spec_qa"
                agent_in_path = out_dir / "agent_input.json"
                agent_in_path.parent.mkdir(parents=True, exist_ok=True)
                agent_in_path.write_text(json.dumps(agent_in, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                try:
                    res = run_agent(agent_id="spec_qa_agent_v1", input_path=agent_in_path, out_dir=out_dir, provider="mock")
                except Exception as e:  # noqa: BLE001
                    err_p = out_dir / "error_summary.json"
                    append_event(
                        job_id=job_id,
                        event_type="ERROR",
                        message="STOPPED_LLM_ERROR",
                        outputs={
                            "reason": "STOPPED_LLM_ERROR",
                            "step": "spec_qa_agent_v1",
                            "error": str(e),
                            "error_summary_path": err_p.as_posix() if err_p.is_file() else None,
                        },
                    )
                    append_event(job_id=job_id, event_type="DONE", outputs={"status": "stopped_llm_error"})
                    return {"job_id": job_id, "status": "stopped", "state": "ERROR", "reason": "STOPPED_LLM_ERROR"}

                spec_qa_report = out_dir / "spec_qa_report.json"
                spec_qa_report_md = out_dir / "spec_qa_report.md"
                finding_count = 0
                try:
                    rep = json.loads(spec_qa_report.read_text(encoding="utf-8"))
                    if isinstance(rep, dict):
                        summary = rep.get("summary") if isinstance(rep.get("summary"), dict) else {}
                        finding_count = int(summary.get("finding_count", 0) or 0)
                except Exception:
                    finding_count = 0
                write_outputs_index(
                    job_id=job_id,
                    updates={
                        "spec_qa_agent_run_path": res.agent_run_path.as_posix(),
                        "spec_qa_report_path": spec_qa_report.as_posix(),
                        "spec_qa_report_md_path": spec_qa_report_md.as_posix(),
                    },
                )
                append_event(
                    job_id=job_id,
                    event_type="WAITING_APPROVAL",
                    outputs={"step": "spec_qa", "spec_qa_report_path": spec_qa_report.as_posix(), "finding_count": finding_count},
                )
                return {"job_id": job_id, "status": "blocked", "state": "WAITING_APPROVAL", "step": "spec_qa"}

            if not _is_approved(events, step="spec_qa"):
                return {"job_id": job_id, "status": "blocked", "state": "WAITING_APPROVAL", "step": "spec_qa"}

            # 2) Compile runspec from blueprint_final.
            if not _has_event(events, "RUNSPEC_COMPILED"):
                idx = json.loads((paths.outputs_dir / "outputs.json").read_text(encoding="utf-8"))
                bp_final = Path(str(idx.get("blueprint_final_path", "")))
                out_runspec = paths.outputs_dir / "runspec.json"
                code, msg = compile_blueprint_to_runspec(
                    blueprint_path=bp_final,
                    snapshot_id=snapshot_id,
                    policy_bundle_path=pb_path,
                    out_path=out_runspec,
                    check_availability=False,
                )
                if code != 0:
                    append_event(job_id=job_id, event_type="ERROR", message=str(msg), outputs={"step": "compile"})
                    continue
                write_outputs_index(job_id=job_id, updates={"runspec_path": out_runspec.as_posix()})
                append_event(job_id=job_id, event_type="RUNSPEC_COMPILED", outputs={"runspec_path": out_runspec.as_posix()})
                append_event(job_id=job_id, event_type="WAITING_APPROVAL", outputs={"step": "runspec"})
                continue

            # Checkpoint 3: runspec approval.
            if not _is_approved(events, step="runspec"):
                return {"job_id": job_id, "status": "blocked", "state": "WAITING_APPROVAL", "step": "runspec"}

            # 3) CalcTrace Preview (as_of filtered via DataCatalog), then optional approval.
            if not _has_event(events, "TRACE_PREVIEW_COMPLETED"):
                from quant_eam.agents.harness import run_agent
                from quant_eam.diagnostics.calc_trace_preview import run_calc_trace_preview

                idx = json.loads((paths.outputs_dir / "outputs.json").read_text(encoding="utf-8"))
                runspec = json.loads((paths.outputs_dir / "runspec.json").read_text(encoding="utf-8"))
                seg = (runspec.get("segments", {}) or {}).get("test", {}) if isinstance(runspec, dict) else {}
                start = str(seg.get("start", ""))
                end = str(seg.get("end", ""))
                as_of = str(seg.get("as_of", ""))
                syms = runspec.get("extensions", {}).get("symbols", []) if isinstance(runspec, dict) else []
                symbols = [str(s) for s in syms] if isinstance(syms, list) else []

                backtest_run_path = Path(str(idx.get("backtest_agent_run_path", "")))
                if not backtest_run_path.is_file():
                    fetch_request = None
                    if isinstance(spec.get("fetch_request"), dict):
                        fetch_request = spec.get("fetch_request")
                    else:
                        spec_ext = spec.get("extensions") if isinstance(spec, dict) else None
                        if isinstance(spec_ext, dict) and isinstance(spec_ext.get("fetch_request"), dict):
                            fetch_request = spec_ext.get("fetch_request")
                    if not isinstance(fetch_request, dict):
                        rs_ext = runspec.get("extensions") if isinstance(runspec, dict) else None
                        if isinstance(rs_ext, dict) and isinstance(rs_ext.get("fetch_request"), dict):
                            fetch_request = rs_ext.get("fetch_request")
                    backtest_in = {
                        "job_id": job_id,
                        "runspec_path": (paths.outputs_dir / "runspec.json").as_posix(),
                        "policy_bundle_path": policy_bundle_path,
                        "trace_preview_path": str(idx.get("calc_trace_preview_path", "")),
                    }
                    if isinstance(fetch_request, dict):
                        backtest_in["fetch_request"] = fetch_request
                    backtest_out_dir = paths.outputs_dir / "agents" / "backtest"
                    backtest_in_path = backtest_out_dir / "agent_input.json"
                    backtest_in_path.parent.mkdir(parents=True, exist_ok=True)
                    backtest_in_path.write_text(json.dumps(backtest_in, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                    try:
                        backtest_res = run_agent(
                            agent_id="backtest_agent_v1",
                            input_path=backtest_in_path,
                            out_dir=backtest_out_dir,
                            provider="mock",
                        )
                    except Exception as e:  # noqa: BLE001
                        err_p = backtest_out_dir / "error_summary.json"
                        append_event(
                            job_id=job_id,
                            event_type="ERROR",
                            message="STOPPED_LLM_ERROR",
                            outputs={
                                "reason": "STOPPED_LLM_ERROR",
                                "step": "backtest_agent_v1",
                                "error": str(e),
                                "error_summary_path": err_p.as_posix() if err_p.is_file() else None,
                            },
                        )
                        append_event(job_id=job_id, event_type="DONE", outputs={"status": "stopped_llm_error"})
                        return {"job_id": job_id, "status": "stopped", "state": "ERROR", "reason": "STOPPED_LLM_ERROR"}
                    backtest_plan = backtest_out_dir / "backtest_plan.json"
                    write_outputs_index(
                        job_id=job_id,
                        updates={
                            "backtest_agent_run_path": backtest_res.agent_run_path.as_posix(),
                            "backtest_plan_path": backtest_plan.as_posix(),
                        },
                    )
                    idx = json.loads((paths.outputs_dir / "outputs.json").read_text(encoding="utf-8"))

                demo_run_path = Path(str(idx.get("demo_agent_run_path", "")))
                if not demo_run_path.is_file():
                    fetch_request = None
                    if isinstance(spec.get("fetch_request"), dict):
                        fetch_request = spec.get("fetch_request")
                    else:
                        spec_ext = spec.get("extensions") if isinstance(spec, dict) else None
                        if isinstance(spec_ext, dict) and isinstance(spec_ext.get("fetch_request"), dict):
                            fetch_request = spec_ext.get("fetch_request")
                    if not isinstance(fetch_request, dict):
                        rs_ext = runspec.get("extensions") if isinstance(runspec, dict) else None
                        if isinstance(rs_ext, dict) and isinstance(rs_ext.get("fetch_request"), dict):
                            fetch_request = rs_ext.get("fetch_request")
                    demo_in = {
                        "snapshot_id": str(runspec.get("data_snapshot_id", snapshot_id)),
                        "start": start,
                        "end": end,
                        "as_of": as_of,
                        "symbols": symbols,
                        "runspec_path": (paths.outputs_dir / "runspec.json").as_posix(),
                        "signal_dsl_path": str(idx.get("signal_dsl_path", "")),
                        "variable_dictionary_path": str(idx.get("variable_dictionary_path", "")),
                        "calc_trace_plan_path": str(idx.get("calc_trace_plan_path", "")),
                    }
                    if isinstance(fetch_request, dict):
                        demo_in["fetch_request"] = fetch_request
                    demo_out_dir = paths.outputs_dir / "agents" / "demo"
                    demo_in_path = demo_out_dir / "agent_input.json"
                    demo_in_path.parent.mkdir(parents=True, exist_ok=True)
                    demo_in_path.write_text(json.dumps(demo_in, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                    try:
                        demo_res = run_agent(agent_id="demo_agent_v1", input_path=demo_in_path, out_dir=demo_out_dir, provider="mock")
                    except Exception as e:  # noqa: BLE001
                        err_p = demo_out_dir / "error_summary.json"
                        append_event(
                            job_id=job_id,
                            event_type="ERROR",
                            message="STOPPED_LLM_ERROR",
                            outputs={
                                "reason": "STOPPED_LLM_ERROR",
                                "step": "demo_agent_v1",
                                "error": str(e),
                                "error_summary_path": err_p.as_posix() if err_p.is_file() else None,
                            },
                        )
                        append_event(job_id=job_id, event_type="DONE", outputs={"status": "stopped_llm_error"})
                        return {"job_id": job_id, "status": "stopped", "state": "ERROR", "reason": "STOPPED_LLM_ERROR"}
                    demo_plan = demo_out_dir / "demo_plan.json"
                    write_outputs_index(
                        job_id=job_id,
                        updates={
                            "demo_agent_run_path": demo_res.agent_run_path.as_posix(),
                            "demo_plan_path": demo_plan.as_posix(),
                        },
                    )
                    idx = json.loads((paths.outputs_dir / "outputs.json").read_text(encoding="utf-8"))

                out_dir = paths.outputs_dir / "trace_preview"
                out_csv, meta_path, meta = run_calc_trace_preview(
                    out_dir=out_dir,
                    snapshot_id=str(runspec.get("data_snapshot_id", snapshot_id)),
                    as_of=as_of,
                    start=start,
                    end=end,
                    symbols=symbols,
                    signal_dsl_path=Path(str(idx.get("signal_dsl_path", ""))),
                    variable_dictionary_path=Path(str(idx.get("variable_dictionary_path", ""))),
                    calc_trace_plan_path=Path(str(idx.get("calc_trace_plan_path", ""))),
                    data_root=_data_root(),
                )
                write_outputs_index(
                    job_id=job_id,
                    updates={
                        "demo_agent_run_path": str(idx.get("demo_agent_run_path", "")),
                        "calc_trace_preview_path": out_csv.as_posix(),
                        "trace_meta_path": meta_path.as_posix(),
                        "trace_rows_written": int(meta.rows_written),
                    },
                )
                append_event(
                    job_id=job_id,
                    event_type="TRACE_PREVIEW_COMPLETED",
                    outputs={"calc_trace_preview_path": out_csv.as_posix(), "rows_written": int(meta.rows_written)},
                )
                append_event(job_id=job_id, event_type="WAITING_APPROVAL", outputs={"step": "trace_preview"})
                continue

            # Checkpoint 4: trace preview approval.
            if not _is_approved(events, step="trace_preview"):
                return {"job_id": job_id, "status": "blocked", "state": "WAITING_APPROVAL", "step": "trace_preview"}

            # 4) Run
            if not _has_event(events, "RUN_COMPLETED"):
                out_runspec = paths.outputs_dir / "runspec.json"
                code, msg = runner_run_once(
                    runspec_path=out_runspec,
                    policy_bundle_path=pb_path,
                    snapshot_id_override=None,
                    data_root=_data_root(),
                    artifact_root=_artifact_root(),
                    behavior_if_exists="noop",
                )
                if code != RUN_OK:
                    append_event(job_id=job_id, event_type="ERROR", message=str(msg), outputs={"step": "run"})
                    continue
                out = _parse_json_maybe(msg)
                run_id = str(out.get("run_id", "")).strip()
                dossier_path = str(out.get("dossier_path", "")).strip()
                run_link_path = paths.outputs_dir / "run_link.json"
                run_link_doc = {
                    "schema_version": "job_run_link_v1",
                    "job_id": job_id,
                    "run_id": run_id,
                    "dossier_path": dossier_path,
                    "gate_results_path": None,
                    "overall_pass": None,
                    "status": "run_completed",
                    "updated_at": _utc_now_iso(),
                }
                run_link_path.parent.mkdir(parents=True, exist_ok=True)
                run_link_path.write_text(json.dumps(run_link_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                write_outputs_index(
                    job_id=job_id,
                    updates={"run_id": run_id, "dossier_path": dossier_path, "run_link_path": run_link_path.as_posix()},
                )
                append_event(
                    job_id=job_id,
                    event_type="RUN_COMPLETED",
                    outputs={"run_id": run_id, "dossier_path": dossier_path, "run_link_path": run_link_path.as_posix()},
                )
                continue

            # 5) Gates
            if not _has_event(events, "GATES_COMPLETED"):
                idx = json.loads((paths.outputs_dir / "outputs.json").read_text(encoding="utf-8"))
                dossier_path = Path(str(idx.get("dossier_path", "")))
                code, msg = gaterunner_run_once(dossier_dir=dossier_path, policy_bundle_path=pb_path)
                if code not in (GATE_OK,):
                    append_event(job_id=job_id, event_type="ERROR", message=str(msg), outputs={"step": "gates"})
                    continue
                out = _parse_json_maybe(msg)
                gate_results_path = str(out.get("gate_results_path", "")).strip()
                overall_pass = bool(out.get("overall_pass"))
                run_link_path = paths.outputs_dir / "run_link.json"
                if run_link_path.is_file():
                    try:
                        run_link_doc = json.loads(run_link_path.read_text(encoding="utf-8"))
                        if not isinstance(run_link_doc, dict):
                            run_link_doc = {}
                    except Exception:
                        run_link_doc = {}
                else:
                    run_link_doc = {}
                run_link_doc.update(
                    {
                        "schema_version": "job_run_link_v1",
                        "job_id": job_id,
                        "run_id": str(idx.get("run_id", "")).strip(),
                        "dossier_path": str(idx.get("dossier_path", "")).strip(),
                        "gate_results_path": gate_results_path,
                        "overall_pass": overall_pass,
                        "status": "gates_completed",
                        "updated_at": _utc_now_iso(),
                    }
                )
                run_link_path.parent.mkdir(parents=True, exist_ok=True)
                run_link_path.write_text(json.dumps(run_link_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                write_outputs_index(
                    job_id=job_id,
                    updates={
                        "gate_results_path": gate_results_path,
                        "overall_pass": overall_pass,
                        "gate_suite_id": out.get("gate_suite_id"),
                        "run_link_path": run_link_path.as_posix(),
                    },
                )
                append_event(job_id=job_id, event_type="GATES_COMPLETED", outputs={"gate_results_path": gate_results_path, "overall_pass": overall_pass})
                continue

            # 6) Registry
            if not _has_event(events, "REGISTRY_UPDATED"):
                idx = json.loads((paths.outputs_dir / "outputs.json").read_text(encoding="utf-8"))
                dossier_path = Path(str(idx.get("dossier_path", "")))
                rr = default_registry_root(artifact_root=_artifact_root())
                try:
                    trial = record_trial(dossier_dir=dossier_path, registry_root=rr, if_exists="noop")
                except Exception as e:  # noqa: BLE001
                    append_event(job_id=job_id, event_type="ERROR", message=str(e), outputs={"step": "registry_record_trial"})
                    continue
                card_id = None
                if bool(trial.get("overall_pass")):
                    try:
                        card = create_card_from_run(run_id=str(trial["run_id"]), registry_root=rr, title=str(spec.get("title") or "job_card"), if_exists="noop")
                        card_id = str(card.get("card_id")) if isinstance(card, dict) else None
                    except RegistryInvalid:
                        card_id = None
                write_outputs_index(job_id=job_id, updates={"trial_recorded": True, "card_id": card_id})
                append_event(job_id=job_id, event_type="REGISTRY_UPDATED", outputs={"card_id": card_id})
                continue

            # 6.5) Phase-45: productized role agents (diagnostics/curator/composer), evidence-only.
            idx = json.loads((paths.outputs_dir / "outputs.json").read_text(encoding="utf-8"))
            diag_run_existing = Path(str(idx.get("diagnostics_agent_run_path", "")))
            if not diag_run_existing.is_file():
                from quant_eam.agents.harness import run_agent

                run_id = str(idx.get("run_id", "")).strip()
                dossier_path = Path(str(idx.get("dossier_path", "")))
                gate_results_path = Path(str(idx.get("gate_results_path", "")))
                gate_results = json.loads(gate_results_path.read_text(encoding="utf-8")) if gate_results_path.is_file() else {}
                failed_gates: list[str] = []
                if isinstance(gate_results, dict) and isinstance(gate_results.get("results"), list):
                    for row in gate_results["results"]:
                        if isinstance(row, dict) and not bool(row.get("pass")):
                            gid = str(row.get("gate_id") or "").strip()
                            if gid:
                                failed_gates.append(gid)

                agent_in = {
                    "job_id": job_id,
                    "run_id": run_id,
                    "dossier_path": dossier_path.as_posix(),
                    "gate_results_path": gate_results_path.as_posix(),
                    "failed_gates": sorted(set(failed_gates)),
                }
                out_dir = paths.outputs_dir / "agents" / "diagnostics_agent"
                agent_in_path = out_dir / "agent_input.json"
                agent_in_path.parent.mkdir(parents=True, exist_ok=True)
                agent_in_path.write_text(json.dumps(agent_in, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                try:
                    res = run_agent(agent_id="diagnostics_agent_v1", input_path=agent_in_path, out_dir=out_dir, provider="mock")
                except Exception as e:  # noqa: BLE001
                    err_p = out_dir / "error_summary.json"
                    append_event(
                        job_id=job_id,
                        event_type="ERROR",
                        message="STOPPED_LLM_ERROR",
                        outputs={
                            "reason": "STOPPED_LLM_ERROR",
                            "step": "diagnostics_agent_v1",
                            "error": str(e),
                            "error_summary_path": err_p.as_posix() if err_p.is_file() else None,
                        },
                    )
                    append_event(job_id=job_id, event_type="DONE", outputs={"status": "stopped_llm_error"})
                    return {"job_id": job_id, "status": "stopped", "state": "ERROR", "reason": "STOPPED_LLM_ERROR"}

                plan_path = out_dir / "diagnostics_plan.json"
                write_outputs_index(
                    job_id=job_id,
                    updates={
                        "diagnostics_agent_run_path": res.agent_run_path.as_posix(),
                        "diagnostics_plan_path": plan_path.as_posix(),
                    },
                )
                append_event(
                    job_id=job_id,
                    event_type="REGISTRY_UPDATED",
                    message="DIAGNOSTICS_AGENT_PROPOSED",
                    outputs={
                        "action": "diagnostics_agent_proposed",
                        "diagnostics_plan_path": plan_path.as_posix(),
                        "diagnostics_agent_run_path": res.agent_run_path.as_posix(),
                    },
                )
                continue

            idx = json.loads((paths.outputs_dir / "outputs.json").read_text(encoding="utf-8"))
            curator_run_existing = Path(str(idx.get("registry_curator_agent_run_path", "")))
            if not curator_run_existing.is_file():
                from quant_eam.agents.harness import run_agent

                agent_in = {
                    "job_id": job_id,
                    "run_id": str(idx.get("run_id", "")).strip(),
                    "card_id": str(idx.get("card_id", "")).strip(),
                    "overall_pass": bool(idx.get("overall_pass")),
                    "trial_recorded": bool(idx.get("trial_recorded")),
                }
                out_dir = paths.outputs_dir / "agents" / "registry_curator"
                agent_in_path = out_dir / "agent_input.json"
                agent_in_path.parent.mkdir(parents=True, exist_ok=True)
                agent_in_path.write_text(json.dumps(agent_in, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                try:
                    res = run_agent(agent_id="registry_curator_v1", input_path=agent_in_path, out_dir=out_dir, provider="mock")
                except Exception as e:  # noqa: BLE001
                    err_p = out_dir / "error_summary.json"
                    append_event(
                        job_id=job_id,
                        event_type="ERROR",
                        message="STOPPED_LLM_ERROR",
                        outputs={
                            "reason": "STOPPED_LLM_ERROR",
                            "step": "registry_curator_v1",
                            "error": str(e),
                            "error_summary_path": err_p.as_posix() if err_p.is_file() else None,
                        },
                    )
                    append_event(job_id=job_id, event_type="DONE", outputs={"status": "stopped_llm_error"})
                    return {"job_id": job_id, "status": "stopped", "state": "ERROR", "reason": "STOPPED_LLM_ERROR"}

                summary_path = out_dir / "registry_curator_summary.json"
                write_outputs_index(
                    job_id=job_id,
                    updates={
                        "registry_curator_agent_run_path": res.agent_run_path.as_posix(),
                        "registry_curator_summary_path": summary_path.as_posix(),
                    },
                )
                append_event(
                    job_id=job_id,
                    event_type="REGISTRY_UPDATED",
                    message="REGISTRY_CURATOR_PROPOSED",
                    outputs={
                        "action": "registry_curator_proposed",
                        "registry_curator_summary_path": summary_path.as_posix(),
                        "registry_curator_agent_run_path": res.agent_run_path.as_posix(),
                    },
                )
                continue

            idx = json.loads((paths.outputs_dir / "outputs.json").read_text(encoding="utf-8"))
            composer_run_existing = Path(str(idx.get("composer_agent_run_path", "")))
            if not composer_run_existing.is_file():
                from quant_eam.agents.harness import run_agent

                agent_in = {
                    "job_id": job_id,
                    "run_id": str(idx.get("run_id", "")).strip(),
                    "card_id": str(idx.get("card_id", "")).strip(),
                    "overall_pass": bool(idx.get("overall_pass")),
                }
                out_dir = paths.outputs_dir / "agents" / "composer_agent"
                agent_in_path = out_dir / "agent_input.json"
                agent_in_path.parent.mkdir(parents=True, exist_ok=True)
                agent_in_path.write_text(json.dumps(agent_in, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                try:
                    res = run_agent(agent_id="composer_agent_v1", input_path=agent_in_path, out_dir=out_dir, provider="mock")
                except Exception as e:  # noqa: BLE001
                    err_p = out_dir / "error_summary.json"
                    append_event(
                        job_id=job_id,
                        event_type="ERROR",
                        message="STOPPED_LLM_ERROR",
                        outputs={
                            "reason": "STOPPED_LLM_ERROR",
                            "step": "composer_agent_v1",
                            "error": str(e),
                            "error_summary_path": err_p.as_posix() if err_p.is_file() else None,
                        },
                    )
                    append_event(job_id=job_id, event_type="DONE", outputs={"status": "stopped_llm_error"})
                    return {"job_id": job_id, "status": "stopped", "state": "ERROR", "reason": "STOPPED_LLM_ERROR"}

                plan_path = out_dir / "composer_agent_plan.json"
                write_outputs_index(
                    job_id=job_id,
                    updates={
                        "composer_agent_run_path": res.agent_run_path.as_posix(),
                        "composer_agent_plan_path": plan_path.as_posix(),
                    },
                )
                append_event(
                    job_id=job_id,
                    event_type="REGISTRY_UPDATED",
                    message="COMPOSER_AGENT_PROPOSED",
                    outputs={
                        "action": "composer_agent_proposed",
                        "composer_agent_plan_path": plan_path.as_posix(),
                        "composer_agent_run_path": res.agent_run_path.as_posix(),
                    },
                )
                continue

            # 7) ReportAgent (deterministic, references artifacts).
            if not _has_event(events, "REPORT_COMPLETED"):
                from quant_eam.agents.harness import run_agent

                idx = json.loads((paths.outputs_dir / "outputs.json").read_text(encoding="utf-8"))
                dossier_path = Path(str(idx.get("dossier_path", "")))
                in_path = dossier_path / "dossier_manifest.json"
                out_dir = dossier_path / "reports" / "agent"
                # Ensure harness can attribute job-level LLM usage even though out_dir is under dossier/ (not jobs/).
                os.environ["EAM_CURRENT_JOB_ID"] = str(job_id)
                try:
                    try:
                        res = run_agent(agent_id="report_agent_v1", input_path=in_path, out_dir=out_dir, provider="mock")
                    except Exception as e:  # noqa: BLE001
                        err_p = out_dir / "error_summary.json"
                        append_event(
                            job_id=job_id,
                            event_type="ERROR",
                            message="STOPPED_LLM_ERROR",
                            outputs={
                                "reason": "STOPPED_LLM_ERROR",
                                "step": "report_agent_v1",
                                "error": str(e),
                                "error_summary_path": err_p.as_posix() if err_p.is_file() else None,
                            },
                        )
                        append_event(job_id=job_id, event_type="DONE", outputs={"status": "stopped_llm_error"})
                        return {"job_id": job_id, "status": "stopped", "state": "ERROR", "reason": "STOPPED_LLM_ERROR"}
                finally:
                    os.environ.pop("EAM_CURRENT_JOB_ID", None)
                try:
                    ar = json.loads(res.agent_run_path.read_text(encoding="utf-8"))
                    llm = (ar.get("extensions") or {}).get("llm") if isinstance(ar, dict) else None
                    if isinstance(llm, dict) and bool(llm.get("budget_stopped")):
                        reason = str(llm.get("stop_reason") or "budget_stopped")
                        append_event(job_id=job_id, event_type="STOPPED_BUDGET", message=reason, outputs={"reason": reason, "agent_id": "report_agent_v1"})
                        append_event(job_id=job_id, event_type="DONE", outputs={"status": "stopped_budget"})
                        return {"job_id": job_id, "status": "stopped", "state": "STOPPED_BUDGET", "reason": reason}
                except Exception:
                    pass
                report_md = out_dir / "report_agent.md"
                report_summary = out_dir / "report_summary.json"
                try:
                    guard = json.loads((out_dir / "output_guard_report.json").read_text(encoding="utf-8"))
                except Exception:
                    guard = {}
                if isinstance(guard, dict) and guard.get("passed") is False and not _is_approved(events, step="agent_output_invalid"):
                    if not _has_waiting_step(events, "agent_output_invalid"):
                        append_event(
                            job_id=job_id,
                            event_type="WAITING_APPROVAL",
                            outputs={
                                "step": "agent_output_invalid",
                                "agent_id": "report_agent_v1",
                                "output_guard_report_path": (out_dir / "output_guard_report.json").as_posix(),
                                "finding_count": int(guard.get("finding_count", 0) or 0),
                            },
                        )
                    return {"job_id": job_id, "status": "blocked", "state": "WAITING_APPROVAL", "step": "agent_output_invalid"}
                write_outputs_index(
                    job_id=job_id,
                    updates={
                        "report_agent_run_path": res.agent_run_path.as_posix(),
                        "report_md_path": report_md.as_posix(),
                        "report_summary_path": report_summary.as_posix(),
                    },
                )
                append_event(job_id=job_id, event_type="REPORT_COMPLETED", outputs={"report_md_path": report_md.as_posix()})
                continue

            # 7.5) Phase-23 Param Sweep (optional, deterministic, budgeted).
            sweep_spec = _extract_sweep_spec(spec) if isinstance(spec, dict) else None
            if isinstance(sweep_spec, dict) and (not _sweep_evidence_exists(job_id)):
                if not _is_approved(events, step="sweep"):
                    append_event(job_id=job_id, event_type="WAITING_APPROVAL", outputs={"step": "sweep"})
                    return {"job_id": job_id, "status": "blocked", "state": "WAITING_APPROVAL", "step": "sweep"}
                from quant_eam.orchestrator.param_sweep import run_param_sweep_for_job

                code_s, msg_s = run_param_sweep_for_job(job_id=job_id)
                if code_s != 0:
                    append_event(job_id=job_id, event_type="ERROR", message=str(msg_s), outputs={"step": "sweep"})
                    continue
                # Continue to improvements stage after sweep evidence is written.

            # 8) Improvement proposals (after DONE-evidence exists: gates + report). Stop at approvals for human selection/spawn.
            if not _has_event(events, "IMPROVEMENTS_PROPOSED"):
                from quant_eam.policies.validate import EXIT_OK as POL_OK
                from quant_eam.policies.validate import validate_file as validate_policy_file
                from quant_eam.policies.load import load_yaml, sha256_file
                from quant_eam.agents.harness import run_agent

                # Validate budget policy (governance input).
                pol_code, pol_msg = validate_policy_file(bp_budget_path)
                if pol_code != POL_OK:
                    append_event(job_id=job_id, event_type="ERROR", message=str(pol_msg), outputs={"step": "improvements_budget_policy"})
                    continue
                budget_doc = load_yaml(bp_budget_path)
                if not isinstance(budget_doc, dict):
                    append_event(job_id=job_id, event_type="ERROR", message="budget policy must be a mapping", outputs={"step": "improvements_budget_policy"})
                    continue

                # Enforce max_total_iterations (lineage is optional; default generation=0).
                lineage = spec.get("extensions", {}).get("lineage", {}) if isinstance(spec.get("extensions"), dict) else {}
                if isinstance(lineage, dict) and isinstance(lineage.get("generation"), int):
                    generation = int(lineage.get("generation", 0))
                else:
                    generation = int(lineage.get("iteration", 0)) if isinstance(lineage, dict) and isinstance(lineage.get("iteration", 0), int) else 0
                max_iter = int((budget_doc.get("params", {}) or {}).get("max_total_iterations", 0)) if isinstance(budget_doc.get("params"), dict) else 0
                # If we cannot legally spawn any child from this job, do not generate proposals.
                attempted_child_generation = generation + 1
                if max_iter and attempted_child_generation >= max_iter:
                    append_event(
                        job_id=job_id,
                        event_type="STOPPED_BUDGET",
                        message="STOP: max_total_iterations reached (no more spawn allowed)",
                        outputs={
                            "reason": "max_total_iterations",
                            "limit": max_iter,
                            "current_generation": generation,
                            "attempted_child_generation": attempted_child_generation,
                        },
                    )
                    append_event(job_id=job_id, event_type="DONE")
                    return {"job_id": job_id, "status": "advanced", "state": "DONE"}

                idx = json.loads((paths.outputs_dir / "outputs.json").read_text(encoding="utf-8"))
                dossier_path = Path(str(idx.get("dossier_path", "")))
                gate_results_path = Path(str(idx.get("gate_results_path", "")))
                report_summary_path = Path(str(idx.get("report_summary_path", "")))
                bp_final_path = Path(str(idx.get("blueprint_final_path", "")))
                blueprint_for_proposals: dict[str, Any] = {}
                if bp_final_path.is_file():
                    blueprint_for_proposals = json.loads(bp_final_path.read_text(encoding="utf-8"))
                else:
                    blueprint_for_proposals = json.loads(Path(str(idx.get("blueprint_draft_path", ""))).read_text(encoding="utf-8"))

                agent_in = {
                    "base_job_id": job_id,
                    "base_run_id": str(idx.get("run_id", "")),
                    "blueprint": blueprint_for_proposals,
                    "gate_results": json.loads(gate_results_path.read_text(encoding="utf-8")) if gate_results_path.is_file() else {},
                    "report_summary": json.loads(report_summary_path.read_text(encoding="utf-8")) if report_summary_path.is_file() else {},
                    "budget_policy": budget_doc,
                    "extensions": {
                        "budget_policy_path": budget_policy_path,
                        "budget_policy_sha256": sha256_file(bp_budget_path),
                        "dossier_path": dossier_path.as_posix(),
                    },
                }

                out_dir = paths.outputs_dir / "agents" / "improvement"
                agent_in_path = out_dir / "agent_input.json"
                agent_in_path.parent.mkdir(parents=True, exist_ok=True)
                agent_in_path.write_text(json.dumps(agent_in, indent=2, sort_keys=True) + "\n", encoding="utf-8")

                try:
                    res = run_agent(agent_id="improvement_agent_v1", input_path=agent_in_path, out_dir=out_dir, provider="mock")
                except Exception as e:  # noqa: BLE001
                    err_p = out_dir / "error_summary.json"
                    append_event(
                        job_id=job_id,
                        event_type="ERROR",
                        message="STOPPED_LLM_ERROR",
                        outputs={
                            "reason": "STOPPED_LLM_ERROR",
                            "step": "improvement_agent_v1",
                            "error": str(e),
                            "error_summary_path": err_p.as_posix() if err_p.is_file() else None,
                        },
                    )
                    append_event(job_id=job_id, event_type="DONE", outputs={"status": "stopped_llm_error"})
                    return {"job_id": job_id, "status": "stopped", "state": "ERROR", "reason": "STOPPED_LLM_ERROR"}
                try:
                    ar = json.loads(res.agent_run_path.read_text(encoding="utf-8"))
                    llm = (ar.get("extensions") or {}).get("llm") if isinstance(ar, dict) else None
                    if isinstance(llm, dict) and bool(llm.get("budget_stopped")):
                        reason = str(llm.get("stop_reason") or "budget_stopped")
                        append_event(job_id=job_id, event_type="STOPPED_BUDGET", message=reason, outputs={"reason": reason, "agent_id": "improvement_agent_v1"})
                        append_event(job_id=job_id, event_type="DONE", outputs={"status": "stopped_budget"})
                        return {"job_id": job_id, "status": "stopped", "state": "STOPPED_BUDGET", "reason": reason}
                except Exception:
                    pass
                proposals_path = out_dir / "improvement_proposals.json"

                try:
                    guard = json.loads((out_dir / "output_guard_report.json").read_text(encoding="utf-8"))
                except Exception:
                    guard = {}
                if isinstance(guard, dict) and guard.get("passed") is False and not _is_approved(events, step="agent_output_invalid"):
                    if not _has_waiting_step(events, "agent_output_invalid"):
                        append_event(
                            job_id=job_id,
                            event_type="WAITING_APPROVAL",
                            outputs={
                                "step": "agent_output_invalid",
                                "agent_id": "improvement_agent_v1",
                                "output_guard_report_path": (out_dir / "output_guard_report.json").as_posix(),
                                "finding_count": int(guard.get("finding_count", 0) or 0),
                            },
                        )
                    return {"job_id": job_id, "status": "blocked", "state": "WAITING_APPROVAL", "step": "agent_output_invalid"}

                write_outputs_index(
                    job_id=job_id,
                    updates={
                        "improvement_agent_run_path": res.agent_run_path.as_posix(),
                        "improvement_proposals_path": proposals_path.as_posix(),
                        "budget_policy_path": budget_policy_path,
                        "budget_policy_id": str(budget_doc.get("policy_id", "")),
                    },
                )
                append_event(job_id=job_id, event_type="IMPROVEMENTS_PROPOSED", outputs={"improvement_proposals_path": proposals_path.as_posix()})
                append_event(job_id=job_id, event_type="WAITING_APPROVAL", outputs={"step": "improvements"})
                continue

            # Checkpoint 5: improvements acknowledgement (user may spawn 0..N jobs before approving to finish).
            if not _is_approved(events, step="improvements"):
                return {"job_id": job_id, "status": "blocked", "state": "WAITING_APPROVAL", "step": "improvements"}

            append_event(job_id=job_id, event_type="DONE")
            return {"job_id": job_id, "status": "advanced", "state": "DONE"}

        # Default workflow (job_spec_v1 blueprint submit): compile -> WAITING_APPROVAL(runspec) -> run -> gates -> registry -> DONE.
        snapshot_id = str(spec.get("snapshot_id", "")).strip()
        policy_bundle_path = str(spec.get("policy_bundle_path", "")).strip()
        pb_path = resolve_repo_relative(policy_bundle_path)

        # Blueprint review checkpoint (single approval can cover subsequent steps).
        if not _is_approved(events, step=None) and not _is_approved(events, step="blueprint") and not _has_event(events, "RUNSPEC_COMPILED"):
            if not _has_event(events, "WAITING_APPROVAL"):
                append_event(job_id=job_id, event_type="WAITING_APPROVAL", outputs={"step": "blueprint"})
            return {"job_id": job_id, "status": "blocked", "state": "WAITING_APPROVAL", "step": "blueprint"}

        # 1) Compile
        if not _has_event(events, "RUNSPEC_COMPILED"):
            out_runspec = paths.outputs_dir / "runspec.json"
            code, msg = compile_blueprint_to_runspec(
                blueprint_path=paths.blueprint,
                snapshot_id=snapshot_id,
                policy_bundle_path=pb_path,
                out_path=out_runspec,
                check_availability=False,
            )
            if code != 0:
                append_event(job_id=job_id, event_type="ERROR", message=str(msg), outputs={"step": "compile"})
                continue
            write_outputs_index(job_id=job_id, updates={"runspec_path": out_runspec.as_posix()})
            append_event(job_id=job_id, event_type="RUNSPEC_COMPILED", outputs={"runspec_path": out_runspec.as_posix()})
            append_event(job_id=job_id, event_type="WAITING_APPROVAL", outputs={"step": "runspec"})
            continue

        # Checkpoint: stop here until approved.
        if not (_is_approved(events, step=None) or _is_approved(events, step="blueprint")):
            return {"job_id": job_id, "status": "blocked", "state": "WAITING_APPROVAL", "step": "runspec"}

        # 2) Run
        if not _has_event(events, "RUN_COMPLETED"):
            out_runspec = paths.outputs_dir / "runspec.json"
            code, msg = runner_run_once(
                runspec_path=out_runspec,
                policy_bundle_path=pb_path,
                snapshot_id_override=None,
                data_root=_data_root(),
                artifact_root=_artifact_root(),
                behavior_if_exists="noop",
            )
            if code != RUN_OK:
                append_event(job_id=job_id, event_type="ERROR", message=str(msg), outputs={"step": "run"})
                continue
            out = _parse_json_maybe(msg)
            run_id = str(out.get("run_id", "")).strip()
            dossier_path = str(out.get("dossier_path", "")).strip()
            write_outputs_index(job_id=job_id, updates={"run_id": run_id, "dossier_path": dossier_path})
            append_event(job_id=job_id, event_type="RUN_COMPLETED", outputs={"run_id": run_id, "dossier_path": dossier_path})
            continue

        # 3) Gates
        if not _has_event(events, "GATES_COMPLETED"):
            idx = json.loads((paths.outputs_dir / "outputs.json").read_text(encoding="utf-8"))
            dossier_path = Path(str(idx.get("dossier_path", "")))
            code, msg = gaterunner_run_once(dossier_dir=dossier_path, policy_bundle_path=pb_path)
            if code not in (GATE_OK,):
                append_event(job_id=job_id, event_type="ERROR", message=str(msg), outputs={"step": "gates"})
                continue
            out = _parse_json_maybe(msg)
            gate_results_path = str(out.get("gate_results_path", "")).strip()
            overall_pass = bool(out.get("overall_pass"))
            write_outputs_index(job_id=job_id, updates={"gate_results_path": gate_results_path, "overall_pass": overall_pass, "gate_suite_id": out.get("gate_suite_id")})
            append_event(job_id=job_id, event_type="GATES_COMPLETED", outputs={"gate_results_path": gate_results_path, "overall_pass": overall_pass})
            continue

        # 4) Registry
        if not _has_event(events, "REGISTRY_UPDATED"):
            idx = json.loads((paths.outputs_dir / "outputs.json").read_text(encoding="utf-8"))
            dossier_path = Path(str(idx.get("dossier_path", "")))
            rr = default_registry_root(artifact_root=_artifact_root())
            try:
                trial = record_trial(dossier_dir=dossier_path, registry_root=rr, if_exists="noop")
            except Exception as e:  # noqa: BLE001
                append_event(job_id=job_id, event_type="ERROR", message=str(e), outputs={"step": "registry_record_trial"})
                continue

            card_id = None
            if bool(trial.get("overall_pass")):
                try:
                    card = create_card_from_run(run_id=str(trial["run_id"]), registry_root=rr, title=str(spec.get("extensions", {}).get("title") or "job_card"), if_exists="noop")
                    card_id = str(card.get("card_id")) if isinstance(card, dict) else None
                except RegistryInvalid:
                    card_id = None

            write_outputs_index(job_id=job_id, updates={"trial_recorded": True, "card_id": card_id})
            append_event(job_id=job_id, event_type="REGISTRY_UPDATED", outputs={"card_id": card_id})
            continue

        # Phase-23 Param Sweep (optional, deterministic, budgeted). Runs only after core evidence exists.
        sweep_spec = _extract_sweep_spec(spec) if isinstance(spec, dict) else None
        if isinstance(sweep_spec, dict) and (not _sweep_evidence_exists(job_id)):
            if not _is_approved(events, step="sweep"):
                append_event(job_id=job_id, event_type="WAITING_APPROVAL", outputs={"step": "sweep"})
                return {"job_id": job_id, "status": "blocked", "state": "WAITING_APPROVAL", "step": "sweep"}
            from quant_eam.orchestrator.param_sweep import run_param_sweep_for_job

            code_s, msg_s = run_param_sweep_for_job(job_id=job_id)
            if code_s != 0:
                append_event(job_id=job_id, event_type="ERROR", message=str(msg_s), outputs={"step": "sweep"})
                continue

        append_event(job_id=job_id, event_type="DONE")
        return {"job_id": job_id, "status": "advanced", "state": "DONE"}


def advance_all_once() -> list[dict[str, Any]]:
    """Advance all jobs at most one stateful action each pass (deterministic order)."""
    from quant_eam.jobstore.store import list_job_ids

    results: list[dict[str, Any]] = []
    for jid in list_job_ids():
        results.append(advance_job_once(job_id=jid))
    return results
