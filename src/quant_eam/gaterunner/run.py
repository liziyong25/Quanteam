from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from quant_eam.contracts import validate as contracts_validate
from quant_eam.gates.registry import run_gate
from quant_eam.gates.types import GateContext
from quant_eam.policies.load import load_yaml
from quant_eam.policies.resolve import load_policy_bundle, resolve_asof_latency_policy

EXIT_OK = 0
EXIT_USAGE_OR_ERROR = 1
EXIT_INVALID = 2

ADAPTER_ID_CURVE_COMPOSER_V1 = "curve_composer_v1"
ADAPTER_ID_VECTORBT_SIGNAL_V1 = "vectorbt_signal_v1"

MANDATORY_GATES: list[dict[str, Any]] = [
    {"gate_id": "gate_no_lookahead_v1", "gate_version": "v1", "params": {}},
    {"gate_id": "gate_delay_plus_1bar_v1", "gate_version": "v1", "params": {}},
    {"gate_id": "gate_cost_x2_v1", "gate_version": "v1", "params": {}},
    {"gate_id": "risk_policy_compliance_v1", "gate_version": "v1", "params": {}},
    {"gate_id": "gate_holdout_passfail_v1", "gate_version": "v1", "params": {}},
]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_atomic(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / (path.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _load_policy_file(policies_dir: Path, filename: str, expected_policy_id: str) -> dict[str, Any]:
    p = policies_dir / filename
    doc = load_yaml(p)
    if not isinstance(doc, dict):
        raise ValueError(f"{filename} must be a YAML mapping/object")
    if doc.get("policy_version") != "v1":
        raise ValueError(f"{filename} policy_version must be 'v1'")
    if doc.get("policy_id") != expected_policy_id:
        raise ValueError(
            f"{filename} policy_id mismatch (bundle={expected_policy_id!r}, file={doc.get('policy_id')!r})"
        )
    return doc


def _find_policy_file_by_id(policies_dir: Path, expected_policy_id: str) -> Path | None:
    for p in sorted([pp for pp in policies_dir.glob("*.y*ml") if pp.is_file()]):
        try:
            doc = load_yaml(p)
        except Exception:  # noqa: BLE001
            continue
        if isinstance(doc, dict) and doc.get("policy_id") == expected_policy_id:
            return p
    return None


def _load_gate_suite(policies_dir: Path, gate_suite_id: str) -> dict[str, Any]:
    # Allow multiple gate suites: resolve by policy_id rather than a single fixed filename.
    p = _find_policy_file_by_id(policies_dir, gate_suite_id)
    if p is None:
        raise ValueError(f"gate_suite policy_id not found in policies/: {gate_suite_id!r}")
    doc = load_yaml(p)
    if not isinstance(doc, dict):
        raise ValueError("gate_suite must be a YAML mapping/object")
    if doc.get("policy_version") != "v1":
        raise ValueError("gate_suite policy_version must be 'v1'")
    if doc.get("policy_id") != gate_suite_id:
        raise ValueError(
            f"gate_suite policy_id mismatch (bundle={gate_suite_id!r}, file={doc.get('policy_id')!r})"
        )
    params = doc.get("params")
    if not isinstance(params, dict):
        raise ValueError("gate_suite.params must be an object")
    holdout = params.get("holdout_policy")
    if not isinstance(holdout, dict):
        raise ValueError("gate_suite.params.holdout_policy must be an object")
    out = holdout.get("output")
    if out != "pass_fail_minimal_summary":
        raise ValueError("gate_suite.params.holdout_policy.output must equal 'pass_fail_minimal_summary'")
    gates = params.get("gates")
    if not isinstance(gates, list) or not gates:
        raise ValueError("gate_suite.params.gates must be a non-empty list")
    return doc


def _gate_list_from_suite(gate_suite: dict[str, Any]) -> list[dict[str, Any]]:
    params = gate_suite.get("params", {})
    gates = params.get("gates", []) if isinstance(params, dict) else []
    out: list[dict[str, Any]] = []
    if isinstance(gates, list):
        for g in gates:
            if not isinstance(g, dict):
                continue
            gate_id = g.get("gate_id")
            gate_version = g.get("gate_version")
            if not isinstance(gate_id, str) or not isinstance(gate_version, str):
                continue
            gp = g.get("params") if isinstance(g.get("params"), dict) else {}
            out.append({"gate_id": gate_id, "gate_version": gate_version, "params": gp})
    return out


def _merge_gates(suite_gates: list[dict[str, Any]], mandatory_gates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Deterministic order: policy-declared gates first (in order), then mandatory gates if missing.
    seen: set[tuple[str, str]] = set()
    merged: list[dict[str, Any]] = []
    for g in suite_gates:
        k = (str(g.get("gate_id", "")), str(g.get("gate_version", "")))
        if k in seen:
            continue
        seen.add(k)
        merged.append(g)
    for g in mandatory_gates:
        k = (str(g.get("gate_id", "")), str(g.get("gate_version", "")))
        if k in seen:
            continue
        seen.add(k)
        merged.append(g)
    return merged


def run_once(*, dossier_dir: Path, policy_bundle_path: Path) -> tuple[int, str]:
    gate_results_path = dossier_dir / "gate_results.json"
    if gate_results_path.is_file():
        return EXIT_OK, json.dumps(
            {"status": "noop", "gate_results_path": gate_results_path.as_posix()}, indent=2, sort_keys=True
        )

    # Load dossier artifacts.
    dossier_manifest = _load_json(dossier_dir / "dossier_manifest.json")
    config_snapshot = _load_json(dossier_dir / "config_snapshot.json")
    metrics = _load_json(dossier_dir / "metrics.json")

    if not isinstance(dossier_manifest, dict):
        return EXIT_INVALID, "INVALID: dossier_manifest.json must be a JSON object"
    if not isinstance(config_snapshot, dict):
        return EXIT_INVALID, "INVALID: config_snapshot.json must be a JSON object"
    if not isinstance(metrics, dict):
        return EXIT_INVALID, "INVALID: metrics.json must be a JSON object"

    run_id = str(dossier_manifest.get("run_id", "")).strip()
    if not run_id:
        return EXIT_INVALID, "INVALID: missing run_id in dossier_manifest.json"

    runspec = config_snapshot.get("runspec")
    if not isinstance(runspec, dict):
        return EXIT_INVALID, "INVALID: config_snapshot.runspec missing or not an object"
    adapter_id = str((runspec.get("adapter", {}) or {}).get("adapter_id", "")).strip()

    # Load policies (read-only).
    bundle_doc = load_policy_bundle(policy_bundle_path)
    policies_dir = policy_bundle_path.parent

    gate_suite_id = bundle_doc.get("gate_suite_id")
    if not isinstance(gate_suite_id, str) or not gate_suite_id.strip():
        return EXIT_INVALID, "INVALID: policy_bundle missing gate_suite_id"

    # Gate suite must enforce holdout output restriction.
    try:
        gate_suite = _load_gate_suite(policies_dir, str(gate_suite_id))
    except Exception as e:  # noqa: BLE001
        return EXIT_INVALID, f"INVALID: {e}"

    # Required policies for stress gates.
    try:
        execution_policy = _load_policy_file(policies_dir, "execution_policy_v1.yaml", str(bundle_doc["execution_policy_id"]))
        cost_policy = _load_policy_file(policies_dir, "cost_policy_v1.yaml", str(bundle_doc["cost_policy_id"]))
        _asof_pid, asof_latency_policy = resolve_asof_latency_policy(bundle_doc=bundle_doc, policies_dir=policies_dir)
        risk_policy = _load_policy_file(policies_dir, "risk_policy_v1.yaml", str(bundle_doc["risk_policy_id"]))
    except Exception as e:  # noqa: BLE001
        return EXIT_INVALID, f"INVALID: {e}"

    ctx = GateContext(
        dossier_dir=dossier_dir,
        policies_dir=policies_dir,
        policy_bundle=bundle_doc,
        execution_policy=execution_policy,
        cost_policy=cost_policy,
        asof_latency_policy=asof_latency_policy,
        risk_policy=risk_policy,
        gate_suite=gate_suite,
        runspec=runspec,
        dossier_manifest=dossier_manifest,
        config_snapshot=config_snapshot,
        metrics=metrics,
    )

    suite_gates = _gate_list_from_suite(gate_suite)
    # Mandatory gates apply only to the vectorbt runner adapter in v1; composition adapters bring their own suites.
    mandatory = MANDATORY_GATES if adapter_id == ADAPTER_ID_VECTORBT_SIGNAL_V1 else []
    gates = _merge_gates(suite_gates, mandatory)

    results: list[dict[str, Any]] = []
    invalid = False
    holdout_summary: dict[str, Any] | None = None
    segment_results: list[dict[str, Any]] = []

    always_invalid_on_fail = {"basic_sanity", "determinism_guard", "gate_no_lookahead_v1", "data_snapshot_integrity_v1"}

    # Phase-21: multi-segment evaluation protocol. When runspec.segments.list exists, we:
    # - run run-level gates once
    # - run segment-specific gates per test segment
    # - run holdout gate once against the holdout segment (minimal output only)
    segs = runspec.get("segments") if isinstance(runspec.get("segments"), dict) else {}
    seg_list = segs.get("list") if isinstance(segs.get("list"), list) else None

    segment_specific_gate_ids = {"gate_no_lookahead_v1", "gate_delay_plus_1bar_v1", "gate_cost_x2_v1"}
    holdout_gate_id = "gate_holdout_passfail_v1"

    def _rewrite_evidence_artifacts(gr_obj: dict[str, Any], *, segment_id: str) -> dict[str, Any]:
        ev = gr_obj.get("evidence")
        if not isinstance(ev, dict):
            return gr_obj
        arts = ev.get("artifacts")
        if not isinstance(arts, list):
            return gr_obj
        out = []
        for a in arts:
            s = str(a)
            if s in ("metrics.json", "curve.csv", "trades.csv"):
                out.append(f"segments/{segment_id}/{s}")
            else:
                out.append(s)
        ev2 = dict(ev)
        ev2["artifacts"] = out
        gr2 = dict(gr_obj)
        gr2["evidence"] = ev2
        return gr2

    def _runspec_with_segment(*, kind: str, seg_obj: dict[str, Any]) -> dict[str, Any]:
        rs2 = dict(runspec)
        segs2 = dict(segs) if isinstance(segs, dict) else {}
        segs2[kind] = {"start": seg_obj.get("start"), "end": seg_obj.get("end"), "as_of": seg_obj.get("as_of")}
        rs2["segments"] = segs2
        return rs2

    if isinstance(seg_list, list) and seg_list:
        # Run-level gates (exclude segment-specific + holdout gate).
        for g in gates:
            gate_id = str(g.get("gate_id"))
            gate_version = str(g.get("gate_version"))
            params = g.get("params") if isinstance(g.get("params"), dict) else {}
            if gate_id in segment_specific_gate_ids or gate_id == holdout_gate_id:
                continue

            gr = run_gate(ctx=ctx, gate_id=gate_id, gate_version=gate_version, params=params)
            results.append(gr.to_json_obj())

            if (not gr.passed) and (
                (gate_id in always_invalid_on_fail)
                or ("error" in gr.metrics)
                or (isinstance(gr.metrics.get("missing_artifacts"), list) and bool(gr.metrics.get("missing_artifacts")))
            ):
                invalid = True

        # Per-test segment gates.
        for seg in seg_list:
            if not isinstance(seg, dict):
                continue
            if str(seg.get("kind") or "") != "test":
                continue
            segment_id = str(seg.get("segment_id") or "").strip()
            if not segment_id:
                continue

            seg_metrics_path = dossier_dir / "segments" / segment_id / "metrics.json"
            if not seg_metrics_path.is_file():
                invalid = True
                segment_results.append(
                    {"segment_id": segment_id, "kind": "test", "overall_pass": False, "invalid": True, "gates": [], "error": "missing segments/<segment_id>/metrics.json"}
                )
                continue
            try:
                seg_metrics = _load_json(seg_metrics_path)
            except Exception:
                seg_metrics = {}

            rs2 = _runspec_with_segment(kind="test", seg_obj=seg)
            ctx2 = GateContext(
                dossier_dir=dossier_dir,
                policies_dir=policies_dir,
                policy_bundle=bundle_doc,
                execution_policy=execution_policy,
                cost_policy=cost_policy,
                asof_latency_policy=asof_latency_policy,
                risk_policy=risk_policy,
                gate_suite=gate_suite,
                runspec=rs2,
                dossier_manifest=dossier_manifest,
                config_snapshot=config_snapshot,
                metrics=(seg_metrics if isinstance(seg_metrics, dict) else {}),
            )

            seg_gate_rows: list[dict[str, Any]] = []
            for g in gates:
                gate_id = str(g.get("gate_id"))
                gate_version = str(g.get("gate_version"))
                if gate_id not in segment_specific_gate_ids:
                    continue
                params = g.get("params") if isinstance(g.get("params"), dict) else {}
                gr = run_gate(ctx=ctx2, gate_id=gate_id, gate_version=gate_version, params=params)
                obj = _rewrite_evidence_artifacts(gr.to_json_obj(), segment_id=segment_id)
                seg_gate_rows.append(obj)
                if (not gr.passed) and (
                    (gate_id in always_invalid_on_fail)
                    or ("error" in gr.metrics)
                    or (isinstance(gr.metrics.get("missing_artifacts"), list) and bool(gr.metrics.get("missing_artifacts")))
                ):
                    invalid = True

            segment_results.append(
                {
                    "segment_id": segment_id,
                    "kind": "test",
                    "holdout": False,
                    "overall_pass": all(bool(r.get("pass")) for r in seg_gate_rows) if seg_gate_rows else True,
                    "gates": seg_gate_rows,
                    "artifacts": {"metrics": f"segments/{segment_id}/metrics.json", "curve": f"segments/{segment_id}/curve.csv", "trades": f"segments/{segment_id}/trades.csv"},
                }
            )

        # Holdout gate once (minimal-only output).
        holdout_seg = None
        for seg in seg_list:
            if isinstance(seg, dict) and str(seg.get("kind") or "") == "holdout":
                holdout_seg = seg
                break
        if isinstance(holdout_seg, dict):
            rs_h = _runspec_with_segment(kind="holdout", seg_obj=holdout_seg)
            ctx_h = GateContext(
                dossier_dir=dossier_dir,
                policies_dir=policies_dir,
                policy_bundle=bundle_doc,
                execution_policy=execution_policy,
                cost_policy=cost_policy,
                asof_latency_policy=asof_latency_policy,
                risk_policy=risk_policy,
                gate_suite=gate_suite,
                runspec=rs_h,
                dossier_manifest=dossier_manifest,
                config_snapshot=config_snapshot,
                metrics=metrics,
            )
            for g in gates:
                gate_id = str(g.get("gate_id"))
                gate_version = str(g.get("gate_version"))
                if gate_id != holdout_gate_id:
                    continue
                params = g.get("params") if isinstance(g.get("params"), dict) else {}
                gr = run_gate(ctx=ctx_h, gate_id=gate_id, gate_version=gate_version, params=params)
                obj = gr.to_json_obj()
                if bool(obj.get("metrics", {}).get("holdout_present")):
                    holdout_summary = {
                        "pass": bool(obj.get("pass")),
                        "summary": str(obj.get("metrics", {}).get("summary", ""))[:240],
                        "metrics_minimal": obj.get("metrics", {}).get("metrics_minimal") if isinstance(obj.get("metrics", {}).get("metrics_minimal"), dict) else {},
                    }
                segment_results.append(
                    {"segment_id": str(holdout_seg.get("segment_id") or "holdout_000"), "kind": "holdout", "holdout": True, "overall_pass": bool(obj.get("pass")), "gates": [obj], "artifacts": {}}
                )

        overall_pass = all(bool(r.get("pass")) for r in results) and all(bool(sr.get("overall_pass")) for sr in segment_results)
    else:
        # Legacy single-segment gating.
        for g in gates:
            gate_id = str(g.get("gate_id"))
            gate_version = str(g.get("gate_version"))
            params = g.get("params") if isinstance(g.get("params"), dict) else {}

            gr = run_gate(ctx=ctx, gate_id=gate_id, gate_version=gate_version, params=params)
            results.append(gr.to_json_obj())

            if (not gr.passed) and (
                (gate_id in always_invalid_on_fail)
                or ("error" in gr.metrics)
                or (isinstance(gr.metrics.get("missing_artifacts"), list) and bool(gr.metrics.get("missing_artifacts")))
            ):
                invalid = True

            if gate_id == holdout_gate_id and bool(gr.metrics.get("holdout_present")):
                holdout_summary = {
                    "pass": bool(gr.passed),
                    "summary": str(gr.metrics.get("summary", ""))[:240],
                    "metrics_minimal": gr.metrics.get("metrics_minimal") if isinstance(gr.metrics.get("metrics_minimal"), dict) else {},
                }

        overall_pass = all(bool(r.get("pass")) for r in results)
    gate_results: dict[str, Any] = {
        "schema_version": "gate_results_v2",
        "run_id": run_id,
        "gate_suite_id": str(gate_suite_id),
        "overall_pass": bool(overall_pass),
        "results": results,
    }
    if holdout_summary is not None:
        gate_results["holdout_summary"] = holdout_summary
    if segment_results:
        gate_results["segment_results"] = segment_results

    # Validate contract before finalizing file write.
    tmp_path = dossier_dir / ".tmp_gate_results.json"
    tmp_path.write_text(json.dumps(gate_results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    code, msg = contracts_validate.validate_json(tmp_path)
    if code != contracts_validate.EXIT_OK:
        tmp_path.unlink(missing_ok=True)
        return EXIT_INVALID, f"INVALID: gate_results schema validation failed: {msg}"

    tmp_path.replace(gate_results_path)

    out_msg = json.dumps(
        {
            "run_id": run_id,
            "gate_suite_id": str(gate_suite_id),
            "overall_pass": bool(overall_pass),
            "gate_results_path": gate_results_path.as_posix(),
            "gates": [{"gate_id": r["gate_id"], "pass": r["pass"], "status": r.get("status")} for r in results],
        },
        indent=2,
        sort_keys=True,
    )
    return (EXIT_INVALID if invalid else EXIT_OK), out_msg


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m quant_eam.gaterunner.run")
    parser.add_argument("--dossier", required=True, help="Path to a dossier directory (append-only evidence bundle).")
    parser.add_argument("--policy-bundle", required=True, help="Path to policy_bundle_v1.yaml (read-only).")
    args = parser.parse_args(argv)

    try:
        dossier_dir = Path(args.dossier)
        if not dossier_dir.is_dir():
            print(f"ERROR: dossier dir not found: {dossier_dir}", file=sys.stderr)
            return EXIT_USAGE_OR_ERROR
        policy_bundle_path = Path(args.policy_bundle)
        if not policy_bundle_path.is_file():
            print(f"ERROR: policy bundle not found: {policy_bundle_path}", file=sys.stderr)
            return EXIT_USAGE_OR_ERROR

        code, msg = run_once(dossier_dir=dossier_dir, policy_bundle_path=policy_bundle_path)
        if code == EXIT_OK:
            print(msg)
        else:
            print(msg, file=sys.stderr)
        return code
    except json.JSONDecodeError as e:
        print(f"ERROR: invalid JSON: {e}", file=sys.stderr)
        return EXIT_USAGE_OR_ERROR
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: {e}", file=sys.stderr)
        return EXIT_USAGE_OR_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
