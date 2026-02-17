from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from quant_eam.contracts import validate as contracts_validate
from quant_eam.agents.experience_pack import ensure_experience_pack_for_job, retrieval_enabled


def _canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _stable_id(prefix: str, obj: Any, n: int = 8) -> str:
    h = hashlib.sha256(_canonical_bytes(obj)).hexdigest()
    return f"{prefix}{h[:n]}"


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _nonempty_str(x: Any) -> bool:
    return isinstance(x, str) and x.strip() != ""


def _extract_failed_gate_ids(gate_results: dict[str, Any]) -> list[str]:
    out: list[str] = []
    results = gate_results.get("results")
    if not isinstance(results, list):
        return out
    for r in results:
        if not isinstance(r, dict):
            continue
        if r.get("pass") is True:
            continue
        gid = r.get("gate_id")
        if _nonempty_str(gid):
            out.append(str(gid))
    return sorted(set(out))


def _budget_max_proposals(budget_policy: dict[str, Any]) -> int:
    params = budget_policy.get("params") if isinstance(budget_policy.get("params"), dict) else {}
    v = params.get("max_proposals_per_job", 0)
    return int(v) if isinstance(v, int) and v >= 0 else 0


def run_improvement_agent(*, input_path: Path, out_dir: Path, provider: str = "mock") -> list[Path]:
    """Deterministic ImprovementAgent (mock provider only).

    Input JSON format (agent_input.json written by Orchestrator):
    - base_job_id
    - base_run_id
    - blueprint (Blueprint v1 JSON)
    - gate_results (GateResults v1 JSON)
    - report_summary (structured summary JSON)
    - budget_policy (BudgetPolicy YAML loaded as dict)

    Output files:
    - improvement_proposals.json (improvement_proposals_v1)
    """
    if provider != "mock":
        raise ValueError("provider must be 'mock' for this MVP")

    in_doc = json.loads(Path(input_path).read_text(encoding="utf-8"))
    if not isinstance(in_doc, dict):
        raise ValueError("agent input must be a JSON object")

    base_job_id = str(in_doc.get("base_job_id", "")).strip()
    base_run_id = str(in_doc.get("base_run_id", "")).strip()
    blueprint = in_doc.get("blueprint")
    gate_results = in_doc.get("gate_results")
    report_summary = in_doc.get("report_summary")
    budget_policy = in_doc.get("budget_policy")

    if not _nonempty_str(base_job_id) or len(base_job_id) != 12:
        raise ValueError("missing/invalid base_job_id")
    if not _nonempty_str(base_run_id):
        raise ValueError("missing base_run_id")
    if not isinstance(blueprint, dict):
        raise ValueError("missing blueprint object")
    if not isinstance(gate_results, dict):
        raise ValueError("missing gate_results object")
    if not isinstance(report_summary, dict):
        raise ValueError("missing report_summary object")
    if not isinstance(budget_policy, dict):
        raise ValueError("missing budget_policy object")

    # Phase-29: deterministic experience retrieval (append-only job evidence), before proposing improvements.
    if retrieval_enabled():
        try:
            title = str(blueprint.get("title") or "")
            desc = str(blueprint.get("description") or "")
            q = " ".join([x for x in (title, desc) if x.strip()]).strip() or title or "improvement"
            # symbols from blueprint.universe.symbols
            u = blueprint.get("universe") if isinstance(blueprint.get("universe"), dict) else {}
            syms = u.get("symbols") if isinstance(u.get("symbols"), list) else []
            symbols = [str(s) for s in syms if str(s).strip()]
            freq = None
            bar = blueprint.get("bar_spec") if isinstance(blueprint.get("bar_spec"), dict) else {}
            if isinstance(bar.get("frequency"), str):
                freq = str(bar.get("frequency"))
            ensure_experience_pack_for_job(job_id=base_job_id, query=q, symbols=symbols, frequency=freq, top_k=5)
        except Exception:
            pass

    # Budget policy id is a governance input (read-only reference).
    budget_policy_id = str(budget_policy.get("policy_id", "")).strip()
    if not _nonempty_str(budget_policy_id):
        raise ValueError("budget_policy.policy_id missing")

    max_props = _budget_max_proposals(budget_policy)
    failed_gate_ids = _extract_failed_gate_ids(gate_results)
    overall_pass = bool(gate_results.get("overall_pass"))

    proposals: list[dict[str, Any]] = []

    def add_proposal(*, title: str, tweak: dict[str, Any], rationale_refs: list[str]) -> None:
        if len(proposals) >= max_props:
            return
        bp2 = copy.deepcopy(blueprint)
        pid = _stable_id("p_", {"title": title, "tweak": tweak, "rationale": rationale_refs, "base": base_job_id})
        base_bp_id = str(bp2.get("blueprint_id", "")).strip() or "blueprint"
        bp2["blueprint_id"] = f"{base_bp_id}__{pid}"
        bp2["title"] = f"{str(bp2.get('title') or 'Blueprint')} [{pid}]"
        ext = bp2.get("extensions") if isinstance(bp2.get("extensions"), dict) else {}
        ext2 = dict(ext)
        ext2["proposal"] = {
            "proposal_id": pid,
            "base_job_id": base_job_id,
            "base_run_id": base_run_id,
            "tweak": tweak,
            "rationale_refs": rationale_refs,
        }
        bp2["extensions"] = ext2

        # Validate blueprint draft against v1 contract (I/O SSOT).
        code, msg = contracts_validate.validate_payload(bp2)
        if code != contracts_validate.EXIT_OK:
            raise ValueError(f"generated blueprint_draft_json invalid: {msg}")

        proposals.append(
            {
                "proposal_id": pid,
                "title": title,
                "rationale_refs": rationale_refs,
                "blueprint_draft_json": bp2,
            }
        )

    # Minimal, deterministic proposal strategy:
    # - If there are failed gates: propose "safety-first" tweaks (metadata only for now).
    # - If all gates pass: propose a "robustness check" tweak (still declarative, no policy overrides).
    if failed_gate_ids:
        add_proposal(
            title="Safety: increase lag / no-lookahead conservatism (proposal)",
            tweak={"kind": "safety", "suggested_trade_lag_bars": 2, "failed_gate_ids": failed_gate_ids},
            rationale_refs=[f"gate_results.json:/results/* gate_id in {failed_gate_ids} pass=false", "report_summary.json:/overall_pass"],
        )
        add_proposal(
            title="Robustness: reduce churn hint (proposal)",
            tweak={"kind": "robustness", "suggested_max_turnover_hint": 0.2, "failed_gate_ids": failed_gate_ids},
            rationale_refs=[f"gate_results.json:/results/* gate_id in {failed_gate_ids} pass=false"],
        )
    else:
        add_proposal(
            title="Robustness: widen universe hint (proposal)",
            tweak={"kind": "robustness", "suggested_universe_hint": "expand_symbols"},
            rationale_refs=["gate_results.json:/overall_pass", "report_summary.json:/overall_pass"],
        )

    # Construct contract output.
    out_doc: dict[str, Any] = {
        "schema_version": "improvement_proposals_v1",
        "base_job_id": base_job_id,
        "base_run_id": base_run_id,
        "budget_policy_id": budget_policy_id,
        "proposals": proposals[:max_props],
        "extensions": {
            "overall_pass": overall_pass,
            "failed_gate_ids": failed_gate_ids,
            "max_proposals_per_job": max_props,
        },
    }

    # Validate output contract.
    code, msg = contracts_validate.validate_payload(out_doc)
    if code != contracts_validate.EXIT_OK:
        raise ValueError(f"invalid improvement_proposals_v1: {msg}")

    out_path = Path(out_dir) / "improvement_proposals.json"
    _write_json(out_path, out_doc)
    return [out_path]
