from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from quant_eam.gaterunner.run import EXIT_OK as GATE_OK, run_once as gaterunner_run_once
from quant_eam.registry.cards import create_card_from_run, show_card
from quant_eam.registry.errors import RegistryInvalid
from quant_eam.registry.storage import default_registry_root
from quant_eam.registry.triallog import record_trial
from quant_eam.runner.run import EXIT_OK as RUN_OK, run_once as runner_run_once
from quant_eam.policies.resolve import load_policy_bundle


EXIT_OK = 0
EXIT_USAGE_OR_ERROR = 1
EXIT_INVALID = 2


def _canonical_json_sha256(obj: Any) -> str:
    b = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    import hashlib

    return hashlib.sha256(b).hexdigest()


def _load_curve_dt_range(artifact_root: Path, run_id: str) -> tuple[str, str]:
    p = artifact_root / "dossiers" / run_id / "curve.csv"
    if not p.is_file():
        raise ValueError(f"missing component curve.csv: {p.as_posix()}")
    df = pd.read_csv(p)
    if "dt" not in df.columns:
        raise ValueError("curve.csv missing dt column")
    s = pd.to_datetime(df["dt"], errors="coerce")
    if s.isna().any():
        raise ValueError("curve.csv has invalid dt")
    s = s.sort_values(kind="mergesort")
    return s.iloc[0].date().isoformat(), s.iloc[-1].date().isoformat()


def _parse_csv_list(s: str) -> list[str]:
    return [x.strip() for x in str(s).split(",") if x.strip()]


def _parse_weights(s: str) -> list[float]:
    out: list[float] = []
    for x in _parse_csv_list(s):
        try:
            out.append(float(x))
        except Exception as e:  # noqa: BLE001
            raise ValueError(f"invalid weight: {x!r}") from e
    return out


def _normalize_components(components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Deterministic ordering for stable run_id.
    out = []
    for c in components:
        out.append(
            {
                "card_id": str(c.get("card_id", "")).strip() or None,
                "run_id": str(c["run_id"]).strip(),
                "weight": float(c["weight"]),
            }
        )
    out.sort(key=lambda d: (str(d.get("card_id") or ""), d["run_id"]))
    return out


def _build_runspec(
    *,
    policy_bundle_id: str,
    components: list[dict[str, Any]],
    dt_start: str,
    dt_end: str,
    align: str,
    base_equity: float,
) -> dict[str, Any]:
    composer_spec = {
        "schema_version": "composer_spec_v1",
        "align": align,
        "base_equity": float(base_equity),
        "components": components,
    }
    blueprint_hash = _canonical_json_sha256(composer_spec)

    seg = {"start": dt_start, "end": dt_end, "as_of": f"{dt_end}T00:00:00+08:00"}

    return {
        "schema_version": "run_spec_v1",
        "blueprint_ref": {
            "blueprint_id": "composer_curve_level_mvp_v1",
            "blueprint_hash": blueprint_hash,
        },
        "policy_bundle_id": policy_bundle_id,
        # Virtual dataset: composition consumes dossier evidence, not the DataLake directly.
        "data_snapshot_id": "composer_virtual_v1",
        "segments": {"train": seg, "test": seg, "holdout": seg},
        "adapter": {"adapter_id": "curve_composer_v1"},
        "output_spec": {
            "write_dossier": True,
            "artifacts": {
                "dossier_manifest": "dossier_manifest.json",
                "config_snapshot": "config_snapshot.json",
                "data_manifest": "data_manifest.json",
                "metrics": "metrics.json",
                "curve": "curve.csv",
                "trades": "trades.csv",
                "report_md": "reports/report.md",
                "components": "components.json",
            },
        },
        "extensions": {
            "composer_spec": composer_spec,
        },
    }


def run_once(
    *,
    card_ids: list[str],
    weights: list[float],
    policy_bundle_path: Path,
    register_card: bool,
    title: str | None,
) -> tuple[int, dict[str, Any]]:
    artifact_root = Path(os.getenv("EAM_ARTIFACT_ROOT", "/artifacts"))
    data_root = Path(os.getenv("EAM_DATA_ROOT", "/data"))
    registry_root = default_registry_root(artifact_root=artifact_root)

    bundle_doc = load_policy_bundle(policy_bundle_path)
    policy_bundle_id = str(bundle_doc["policy_bundle_id"])

    allow_negative_weights = bool(
        isinstance(bundle_doc.get("extensions"), dict)
        and isinstance(bundle_doc["extensions"].get("composer"), dict)
        and bool(bundle_doc["extensions"]["composer"].get("allow_negative_weights"))
    )

    if not card_ids:
        return EXIT_USAGE_OR_ERROR, {"error": "missing --card-ids"}
    if len(weights) != len(card_ids):
        return EXIT_INVALID, {"error": "weights count must equal card_ids count"}
    if (not allow_negative_weights) and any((w < 0) for w in weights):
        return EXIT_INVALID, {"error": "negative weights are disabled by policy (set policy_bundle.extensions.composer.allow_negative_weights=true in a v2 bundle)"}
    # Strict sum=1 with tight tolerance (deterministic guard).
    if abs(sum(weights) - 1.0) > 1e-9:
        return EXIT_INVALID, {"error": "weights must sum to 1.0"}

    # Resolve cards -> primary runs.
    comps: list[dict[str, Any]] = []
    for cid, w in zip(card_ids, weights, strict=True):
        card = show_card(registry_root=registry_root, card_id=cid)
        run_id = str(card.get("primary_run_id", "")).strip()
        if not run_id:
            return EXIT_INVALID, {"error": f"card missing primary_run_id: {cid}"}
        comps.append({"card_id": cid, "run_id": run_id, "weight": float(w)})

    comps = _normalize_components(comps)
    # Determine dt range from component curves (deterministic).
    starts: list[str] = []
    ends: list[str] = []
    for c in comps:
        s, e = _load_curve_dt_range(artifact_root, str(c["run_id"]))
        starts.append(s)
        ends.append(e)
    dt_start = min(starts)
    dt_end = max(ends)

    runspec = _build_runspec(
        policy_bundle_id=policy_bundle_id,
        components=comps,
        dt_start=dt_start,
        dt_end=dt_end,
        align="intersection",
        base_equity=1.0,
    )

    runspec_path = artifact_root / ".tmp_curve_composer_runspec.json"
    runspec_path.write_text(json.dumps(runspec, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    code, msg = runner_run_once(
        runspec_path=runspec_path,
        policy_bundle_path=policy_bundle_path,
        snapshot_id_override=None,
        data_root=data_root,
        artifact_root=artifact_root,
        behavior_if_exists="noop",
    )
    if code != RUN_OK:
        return code, {"error": msg}

    out = json.loads(msg)
    run_id = str(out["run_id"])
    dossier_path = str(out["dossier_path"])

    # Run gates for the composed dossier using the passed policy bundle.
    gate_code, _gate_msg = gaterunner_run_once(dossier_dir=Path(dossier_path), policy_bundle_path=policy_bundle_path)
    gate_results_path = str(Path(dossier_path) / "gate_results.json")

    # Registry writeback (optional).
    card_id: str | None = None
    if register_card:
        if not title or not str(title).strip():
            return EXIT_USAGE_OR_ERROR, {"error": "--register-card requires --title"}

        # record-trial is append-only and idempotent.
        ev = record_trial(dossier_dir=Path(dossier_path), registry_root=registry_root, if_exists="noop")
        if not bool(ev.get("overall_pass")):
            return EXIT_INVALID, {
                "error": "cannot register card: overall_pass is false (Gate PASS required)",
                "run_id": run_id,
                "dossier_path": dossier_path,
                "gate_results_path": gate_results_path,
            }
        card = create_card_from_run(run_id=run_id, registry_root=registry_root, title=str(title), if_exists="fail")
        card_id = str(card.get("card_id"))

    return EXIT_OK, {
        "run_id": run_id,
        "dossier_path": dossier_path,
        "gate_results_path": gate_results_path,
        "gate_exit_code": int(gate_code),
        "card_id": card_id,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m quant_eam.composer.run")
    parser.add_argument("--card-ids", required=True, help="Comma-separated card_ids to compose.")
    parser.add_argument("--weights", required=True, help="Comma-separated weights aligned with --card-ids.")
    parser.add_argument("--policy-bundle", required=True, help="Path to composer policy bundle YAML.")
    parser.add_argument("--register-card", action="store_true", help="Record trial + create new experience card (PASS only).")
    parser.add_argument("--title", default=None, help="Card title (required when --register-card).")
    args = parser.parse_args(argv)

    try:
        card_ids = _parse_csv_list(args.card_ids)
        weights = _parse_weights(args.weights)
        policy_bundle_path = Path(args.policy_bundle)
        if not policy_bundle_path.is_file():
            print(json.dumps({"error": f"policy bundle not found: {policy_bundle_path.as_posix()}"}), file=sys.stderr)
            return EXIT_USAGE_OR_ERROR

        code, out = run_once(
            card_ids=card_ids,
            weights=weights,
            policy_bundle_path=policy_bundle_path,
            register_card=bool(args.register_card),
            title=args.title,
        )
        print(json.dumps(out, indent=2, sort_keys=True))
        return code
    except RegistryInvalid as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return EXIT_INVALID
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return EXIT_USAGE_OR_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
