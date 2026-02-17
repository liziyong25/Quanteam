from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd

from quant_eam.backtest.curve_composer_adapter_v1 import (
    ADAPTER_ID_CURVE_COMPOSER_V1,
    compose_curves,
)
from quant_eam.backtest.vectorbt_adapter_mvp import (
    ADAPTER_ID_VECTORBT_SIGNAL_V1,
    BacktestInvalid,
    run_adapter,
)
from quant_eam.contracts import validate as contracts_validate
from quant_eam.data_lake.demo_ingest import main as demo_ingest_main
from quant_eam.datacatalog.catalog import DataCatalog
from quant_eam.dossier.writer import DossierAlreadyExists, DossierWriter
from quant_eam.policies.load import default_policies_dir, load_yaml, sha256_file
from quant_eam.policies.resolve import load_policy_bundle, resolve_asof_latency_policy

EXIT_OK = 0
EXIT_USAGE_OR_ERROR = 1
EXIT_INVALID = 2


def _canonical_json_sha256(obj: Any) -> str:
    b = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    import hashlib

    return hashlib.sha256(b).hexdigest()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _policy_index(policies_dir: Path) -> dict[str, Path]:
    idx: dict[str, Path] = {}
    for p in sorted([pp for pp in policies_dir.glob("*.y*ml") if pp.is_file()]):
        doc = load_yaml(p)
        if isinstance(doc, dict) and isinstance(doc.get("policy_id"), str):
            idx[str(doc["policy_id"])] = p
    return idx


def _load_policy_docs_from_bundle(bundle_path: Path) -> tuple[str, dict[str, Any], dict[str, Any], dict[str, Any], dict[str, str]]:
    policies_dir = bundle_path.parent
    bundle_doc = load_policy_bundle(bundle_path)
    bundle_id = str(bundle_doc["policy_bundle_id"])

    idx = _policy_index(policies_dir)

    def load_by_id(key: str) -> dict[str, Any]:
        pid = bundle_doc.get(key)
        if not isinstance(pid, str) or not pid.strip():
            raise ValueError(f"bundle missing {key}")
        p = idx.get(pid)
        if not p:
            raise ValueError(f"bundle references missing policy_id: {pid!r}")
        doc = load_yaml(p)
        if not isinstance(doc, dict):
            raise ValueError(f"policy file not an object: {p}")
        return doc

    execution = load_by_id("execution_policy_id")
    cost = load_by_id("cost_policy_id")
    asof_pid, asof_doc = resolve_asof_latency_policy(bundle_doc=bundle_doc, policies_dir=policies_dir)

    # sha256 lock for config snapshot.
    sha_map: dict[str, str] = {}
    sha_map["policy_bundle"] = sha256_file(bundle_path)
    for pid, p in idx.items():
        # Record only policies referenced by the bundle (deterministic + minimal).
        if pid in {
            str(bundle_doc.get("execution_policy_id")),
            str(bundle_doc.get("cost_policy_id")),
            str(bundle_doc.get("asof_latency_policy_id")),
            str(bundle_doc.get("risk_policy_id")),
            str(bundle_doc.get("gate_suite_id")),
        }:
            sha_map[pid] = sha256_file(p)

    return bundle_id, execution, cost, asof_doc, sha_map


def _trade_lag_bars_default(asof_latency_policy: dict[str, Any]) -> int:
    params = asof_latency_policy.get("params", {})
    if isinstance(params, dict) and "trade_lag_bars_default" in params:
        try:
            v = int(params["trade_lag_bars_default"])
            return max(1, v)
        except Exception:  # noqa: BLE001
            return 1
    return 1


def _runspec_demo(snapshot_id: str, *, policy_bundle_id: str) -> dict[str, Any]:
    return {
        "schema_version": "run_spec_v1",
        "blueprint_ref": {"blueprint_id": "demo_blueprint_v1", "blueprint_hash": "demo_blueprint_hash_v1"},
        "policy_bundle_id": policy_bundle_id,
        "data_snapshot_id": snapshot_id,
        "segments": {
            "train": {"start": "2024-01-01", "end": "2024-01-10", "as_of": "2024-01-11T00:00:00+08:00"},
            "test": {"start": "2024-01-01", "end": "2024-01-10", "as_of": "2024-01-11T00:00:00+08:00"},
            "holdout": {"start": "2024-01-01", "end": "2024-01-10", "as_of": "2024-01-11T00:00:00+08:00"},
        },
        "adapter": {"adapter_id": ADAPTER_ID_VECTORBT_SIGNAL_V1},
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
            },
        },
        "extensions": {"symbols": ["AAA", "BBB"], "strategy_id": "buy_and_hold_mvp"},
    }


def _runspec_segments_list(runspec: dict[str, Any]) -> list[dict[str, Any]]:
    segs = runspec.get("segments") if isinstance(runspec.get("segments"), dict) else {}
    lst = segs.get("list") if isinstance(segs.get("list"), list) else None
    out: list[dict[str, Any]] = []
    if isinstance(lst, list):
        for s in lst:
            if not isinstance(s, dict):
                continue
            sid = str(s.get("segment_id") or "").strip()
            kind = str(s.get("kind") or "").strip()
            start = str(s.get("start") or "").strip()
            end = str(s.get("end") or "").strip()
            as_of = str(s.get("as_of") or "").strip()
            holdout = bool(s.get("holdout")) if "holdout" in s else (kind == "holdout")
            if sid and kind and start and end and as_of:
                out.append(
                    {
                        "segment_id": sid,
                        "kind": kind,
                        "start": start,
                        "end": end,
                        "as_of": as_of,
                        "holdout": holdout,
                    }
                )
    if out:
        return out

    # Fallback: legacy single segments.
    segs2 = runspec.get("segments") if isinstance(runspec.get("segments"), dict) else {}
    for kind in ("train", "test", "holdout"):
        sd = segs2.get(kind) if isinstance(segs2.get(kind), dict) else {}
        start = str(sd.get("start") or "").strip()
        end = str(sd.get("end") or "").strip()
        as_of = str(sd.get("as_of") or "").strip()
        if start and end and as_of:
            out.append({"segment_id": f"{kind}_000", "kind": kind, "start": start, "end": end, "as_of": as_of, "holdout": kind == "holdout"})
    return out


def run_once(
    *,
    runspec_path: Path,
    policy_bundle_path: Path,
    snapshot_id_override: str | None,
    data_root: Path,
    artifact_root: Path,
    behavior_if_exists: str,
) -> tuple[int, str]:
    # 1) Validate runspec contract.
    code, msg = contracts_validate.validate_json(runspec_path)
    if code != contracts_validate.EXIT_OK:
        return EXIT_INVALID, msg

    runspec = _load_json(runspec_path)
    if not isinstance(runspec, dict):
        return EXIT_INVALID, "INVALID: runspec must be a JSON object"

    # 2) Load policies (read-only) and capture sha256.
    bundle_id, execution_policy, cost_policy, asof_latency_policy, policy_shas = _load_policy_docs_from_bundle(
        policy_bundle_path
    )

    # Ensure runspec references the same bundle id (no overrides).
    if str(runspec.get("policy_bundle_id")) != bundle_id:
        return EXIT_INVALID, f"INVALID: runspec.policy_bundle_id mismatch (runspec={runspec.get('policy_bundle_id')!r}, bundle={bundle_id!r})"

    snapshot_id = snapshot_id_override or str(runspec.get("data_snapshot_id", ""))
    if not snapshot_id:
        return EXIT_INVALID, "INVALID: missing data_snapshot_id"

    adapter_id = str(runspec.get("adapter", {}).get("adapter_id", ""))
    bt = None
    lag_bars: int | None = None

    if adapter_id == ADAPTER_ID_VECTORBT_SIGNAL_V1:
        seg_test = runspec.get("segments", {}).get("test", {})
        start = str(seg_test.get("start"))
        end = str(seg_test.get("end"))
        as_of = str(seg_test.get("as_of"))

        symbols = runspec.get("extensions", {}).get("symbols", ["AAA", "BBB"])
        if not isinstance(symbols, list) or not symbols:
            return EXIT_INVALID, "INVALID: runspec.extensions.symbols must be a non-empty list"
        symbols = [str(s) for s in symbols]

        lag_bars = _trade_lag_bars_default(asof_latency_policy)

        def run_segment(seg: dict[str, Any]) -> tuple[dict[str, Any], str, str, str, str, dict[str, Any]]:
            s_start = str(seg.get("start") or "")
            s_end = str(seg.get("end") or "")
            s_asof = str(seg.get("as_of") or "")
            cat = DataCatalog(root=data_root)
            rows, _stats = cat.query_ohlcv(snapshot_id=snapshot_id, symbols=symbols, start=s_start, end=s_end, as_of=s_asof)
            if not rows:
                raise BacktestInvalid("query returned 0 rows (as_of filter may exclude all data)")
            prices = pd.DataFrame.from_records(rows)
            for c in ["open", "high", "low", "close", "volume"]:
                prices[c] = prices[c].astype(float)
            prices["dt"] = prices["dt"].astype(str)
            prices["symbol"] = prices["symbol"].astype(str)

            out_bt = run_adapter(
                adapter_id=adapter_id,
                prices=prices,
                lag_bars=lag_bars,
                execution_policy=execution_policy,
                cost_policy=cost_policy,
            )

            seg_metrics = {
                "segment_id": str(seg.get("segment_id") or ""),
                "kind": str(seg.get("kind") or ""),
                "holdout": bool(seg.get("holdout")),
                "start": s_start,
                "end": s_end,
                "as_of": s_asof,
                "total_return": out_bt.stats.get("total_return"),
                "max_drawdown": out_bt.stats.get("max_drawdown"),
                "sharpe": out_bt.stats.get("sharpe"),
                "trade_count": out_bt.stats.get("trade_count"),
                "adapter_id": out_bt.stats.get("adapter_id"),
                "strategy_id": out_bt.stats.get("strategy_id"),
                "lag_bars": out_bt.stats.get("lag_bars"),
            }
            curve_csv = "dt,equity\n" + "\n".join(
                f"{row['dt']},{row['equity']}" for row in out_bt.equity_curve.to_dict(orient="records")
            ) + "\n"
            if out_bt.trades.empty:
                trades_csv = "symbol,entry_dt,exit_dt,pnl,qty,fees\n"
            else:
                trades_csv = "symbol,entry_dt,exit_dt,pnl,qty,fees\n" + "\n".join(
                    f"{r['symbol']},{r['entry_dt']},{r['exit_dt']},{r['pnl']},{r['qty']},{r['fees']}"
                    for r in out_bt.trades.to_dict(orient="records")
                ) + "\n"
            # Phase-27: risk evidence artifacts are produced by the backtest engine itself.
            positions_df = out_bt.positions
            turnover_df = out_bt.turnover
            exposure_obj = out_bt.exposure
            if positions_df is None or turnover_df is None or exposure_obj is None:
                raise BacktestInvalid("backtest adapter did not produce risk evidence artifacts (positions/turnover/exposure)")

            positions_df = positions_df.sort_values(["dt", "symbol"], kind="mergesort").reset_index(drop=True)
            turnover_df = turnover_df.sort_values(["dt"], kind="mergesort").reset_index(drop=True)

            pos_cols = ["dt", "symbol", "qty", "close", "position_value", "equity"]
            missing_pos = [c for c in pos_cols if c not in positions_df.columns]
            if missing_pos:
                raise BacktestInvalid(f"positions evidence missing columns: {missing_pos}")

            positions_csv = "dt,symbol,qty,close,position_value,equity\n" + "\n".join(
                f"{r['dt']},{r['symbol']},{r['qty']},{r['close']},{r['position_value']},{r['equity']}"
                for r in positions_df[pos_cols].to_dict(orient="records")
            ) + "\n"
            turnover_csv = "dt,turnover\n" + "\n".join(
                f"{r.get('dt')},{'' if r.get('turnover') is None else r.get('turnover')}"
                for r in turnover_df.to_dict(orient="records")
            ) + "\n"
            return seg_metrics, curve_csv, trades_csv, positions_csv, turnover_csv, (exposure_obj if isinstance(exposure_obj, dict) else {})

        # 3) Baseline execution for legacy top-level artifacts (overall test range in runspec.segments.test).
        try:
            base_metrics, base_curve_csv, base_trades_csv, base_positions_csv, base_turnover_csv, base_exposure = run_segment(
                {"segment_id": "test_overall", "kind": "test", "holdout": False, "start": start, "end": end, "as_of": as_of}
            )
            bt = None  # not used beyond derived strings
        except BacktestInvalid as e:
            return EXIT_INVALID, f"INVALID: {e}"

        # 4) Phase-21 segments execution (train/test only). Holdout evidence is restricted and handled by GateRunner via HoldoutVault.
        seg_list = _runspec_segments_list(runspec)
        seg_json: dict[str, Any] = {
            "schema_version": "segments_summary_v1",
            "run_id": "",  # filled after run_id computed
            "segments": [],
            "extensions": {
                "protocol": ((runspec.get("extensions") or {}).get("evaluation_protocol_v1") or {}).get("protocol") if isinstance(runspec.get("extensions"), dict) else None,
            },
        }
        extra_json: dict[str, Any] = {}
        extra_text: dict[str, str] = {}

        # Phase-27: risk evidence artifacts (run-level, derived from the baseline segment execution).
        out_artifacts = runspec.get("output_spec", {}).get("artifacts", {})
        if not isinstance(out_artifacts, dict):
            out_artifacts = {}
        positions_rel = str(out_artifacts.get("positions") or "positions.csv")
        turnover_rel = str(out_artifacts.get("turnover") or "turnover.csv")
        exposure_rel = str(out_artifacts.get("exposure") or "exposure.json")
        extra_text[positions_rel] = base_positions_csv
        extra_text[turnover_rel] = base_turnover_csv
        extra_json[exposure_rel] = base_exposure

        for s in seg_list:
            sid = str(s.get("segment_id") or "").strip()
            kind = str(s.get("kind") or "").strip()
            holdout = bool(s.get("holdout"))
            if not sid or not kind:
                continue
            if holdout:
                seg_json["segments"].append(
                    {"segment_id": sid, "kind": kind, "holdout": True, "start": s.get("start"), "end": s.get("end"), "as_of": s.get("as_of"), "artifacts": {}}
                )
                continue

            try:
                # Phase-27: run_segment also returns risk evidence strings/objects; segment-level
                # writer currently persists only metrics/curve/trades (risk evidence is persisted
                # at the run-level from the baseline execution above).
                m, c_csv, t_csv, _pos_csv, _turn_csv, _expo = run_segment(s)
            except BacktestInvalid as e:
                return EXIT_INVALID, f"INVALID: segment {sid}: {e}"

            seg_dir = f"segments/{sid}"
            extra_json[f"{seg_dir}/metrics.json"] = m
            extra_text[f"{seg_dir}/curve.csv"] = c_csv
            extra_text[f"{seg_dir}/trades.csv"] = t_csv

            seg_json["segments"].append(
                {
                    "segment_id": sid,
                    "kind": kind,
                    "holdout": False,
                    "start": s.get("start"),
                    "end": s.get("end"),
                    "as_of": s.get("as_of"),
                    "metrics": {
                        "total_return": m.get("total_return"),
                        "max_drawdown": m.get("max_drawdown"),
                        "sharpe": m.get("sharpe"),
                        "trade_count": m.get("trade_count"),
                    },
                    "artifacts": {
                        "metrics": f"{seg_dir}/metrics.json",
                        "curve": f"{seg_dir}/curve.csv",
                        "trades": f"{seg_dir}/trades.csv",
                    },
                }
            )

    elif adapter_id == ADAPTER_ID_CURVE_COMPOSER_V1:
        # 3) Curve-level composition (no DataCatalog access; consumes existing dossiers as evidence inputs).
        ext = runspec.get("extensions", {}) if isinstance(runspec.get("extensions"), dict) else {}
        composer = ext.get("composer_spec") if isinstance(ext.get("composer_spec"), dict) else None
        if not isinstance(composer, dict):
            return EXIT_INVALID, "INVALID: missing runspec.extensions.composer_spec for curve_composer_v1"
        comps = composer.get("components")
        if not isinstance(comps, list) or not comps:
            return EXIT_INVALID, "INVALID: composer_spec.components must be a non-empty list"

        comp_run_ids: list[str] = []
        comp_weights: list[float] = []
        dossier_dirs: list[Path] = []
        for i, c in enumerate(comps):
            if not isinstance(c, dict):
                return EXIT_INVALID, f"INVALID: composer_spec.components[{i}] must be an object"
            rid = c.get("run_id")
            w = c.get("weight")
            if not isinstance(rid, str) or not rid.strip():
                return EXIT_INVALID, f"INVALID: composer_spec.components[{i}].run_id must be a non-empty string"
            if not isinstance(w, (int, float)):
                return EXIT_INVALID, f"INVALID: composer_spec.components[{i}].weight must be a number"
            rid_s = str(rid).strip()
            comp_run_ids.append(rid_s)
            comp_weights.append(float(w))
            dossier_dirs.append(artifact_root / "dossiers" / rid_s)

        align = str(composer.get("align", "intersection"))
        base_equity = composer.get("base_equity", 1.0)
        try:
            base_equity_f = float(base_equity)
        except Exception:
            return EXIT_INVALID, "INVALID: composer_spec.base_equity must be a number"

        try:
            bt, cc = compose_curves(
                dossier_dirs=dossier_dirs,
                weights=comp_weights,
                align=align,
                base_equity=base_equity_f,
            )
        except BacktestInvalid as e:
            return EXIT_INVALID, f"INVALID: {e}"

        # Attach alignment stats for auditability (do not affect run_id; stored in components.json).
        try:
            for i, c in enumerate(comps):
                if not isinstance(c, dict):
                    continue
                c["_alignment_original_points"] = int(cc.original_points[i]) if i < len(cc.original_points) else None
                c["_alignment_intersection_points"] = int(cc.aligned_rows)
        except Exception:
            pass

        # Record minimal segment evidence derived from aligned dt range (deterministic).
        try:
            runspec.setdefault("segments", {})
            segs = runspec["segments"]
            if isinstance(segs, dict):
                for k in ("train", "test", "holdout"):
                    if k in segs and isinstance(segs[k], dict):
                        continue
                    segs[k] = {"start": cc.dt_start, "end": cc.dt_end, "as_of": f"{cc.dt_end}T00:00:00+08:00"}
        except Exception:
            pass

    else:
        return EXIT_INVALID, f"INVALID: unsupported adapter_id: {adapter_id!r}"

    # 5) Write dossier (append-only).
    run_id = _canonical_json_sha256(runspec)[:12]
    writer = DossierWriter(artifact_root)

    # Read DataLake manifest for data_manifest.json evidence.
    lake_manifest_path = data_root / "lake" / snapshot_id / "manifest.json"
    data_manifest: dict[str, Any] = {"snapshot_id": snapshot_id}
    if lake_manifest_path.is_file():
        data_manifest = _load_json(lake_manifest_path)

    config_snapshot = {
        "runspec": runspec,
        "policy_bundle_id": bundle_id,
        "policy_sha256": policy_shas,
        "env": {
            "EAM_DATA_ROOT": data_root.as_posix(),
            "EAM_ARTIFACT_ROOT": artifact_root.as_posix(),
        },
        "deps": {
            "python": sys.version.split()[0],
            "pandas": pd.__version__,
        },
    }

    # Dossier artifacts mapping (relative paths).
    artifacts = dict(runspec.get("output_spec", {}).get("artifacts", {}))
    # Phase-27: risk evidence artifacts. Ensure stable default paths even if older RunSpec omitted them.
    if adapter_id == ADAPTER_ID_VECTORBT_SIGNAL_V1:
        artifacts.setdefault("positions", "positions.csv")
        artifacts.setdefault("turnover", "turnover.csv")
        artifacts.setdefault("exposure", "exposure.json")
    # Ensure segments_summary.json is discoverable by UI (append-only evidence). Backward compatible: only add new key.
    if "segments_summary" not in artifacts:
        artifacts["segments_summary"] = "segments_summary.json"

    # Metrics baseline: legacy top-level (overall test segment for vectorbt adapter, or adapter-specific otherwise).
    if adapter_id == ADAPTER_ID_VECTORBT_SIGNAL_V1:
        metrics = dict(base_metrics)
        metrics["segments_summary_ref"] = artifacts["segments_summary"]
        curve_csv = base_curve_csv
        trades_csv = base_trades_csv
        # Finalize segments_summary now that run_id is known.
        seg_json["run_id"] = run_id
        extra_json[artifacts["segments_summary"]] = seg_json
    else:
        metrics = {
            "total_return": bt.stats.get("total_return"),
            "max_drawdown": bt.stats.get("max_drawdown"),
            "sharpe": bt.stats.get("sharpe"),
            "trade_count": bt.stats.get("trade_count"),
            "adapter_id": bt.stats.get("adapter_id"),
            "strategy_id": bt.stats.get("strategy_id"),
            "lag_bars": bt.stats.get("lag_bars") if adapter_id == ADAPTER_ID_VECTORBT_SIGNAL_V1 else None,
        }
        curve_csv = "dt,equity\n" + "\n".join(
            f"{row['dt']},{row['equity']}" for row in bt.equity_curve.to_dict(orient="records")
        ) + "\n"
        if bt.trades.empty:
            trades_csv = "symbol,entry_dt,exit_dt,pnl,qty,fees\n"
        else:
            trades_csv = "symbol,entry_dt,exit_dt,pnl,qty,fees\n" + "\n".join(
                f"{r['symbol']},{r['entry_dt']},{r['exit_dt']},{r['pnl']},{r['qty']},{r['fees']}"
                for r in bt.trades.to_dict(orient="records")
            ) + "\n"

    notes: list[str] = [
        "- Append-only dossier (no rewrites).",
    ]
    if adapter_id == ADAPTER_ID_VECTORBT_SIGNAL_V1:
        notes.append("- Data is accessed via DataCatalog with enforced `available_at <= as_of`.")
        notes.append(f"- Signals are lagged by {lag_bars} bar(s) to prevent lookahead.")
    elif adapter_id == ADAPTER_ID_CURVE_COMPOSER_V1:
        notes.append("- Curve-level composition adapter: consumes existing dossier evidence (see components.json).")
        notes.append("- Does not query DataCatalog in v1 (inputs are component dossier artifacts).")

    report_md = "\n".join(
        [
            "# Runner Report (MVP)",
            "",
            f"- run_id: `{run_id}`",
            f"- snapshot_id: `{snapshot_id}`",
            f"- policy_bundle_id: `{bundle_id}`",
            f"- adapter_id: `{adapter_id}`",
            "",
            "Artifacts:",
            f"- {artifacts.get('config_snapshot', 'config_snapshot.json')}",
            f"- {artifacts.get('data_manifest', 'data_manifest.json')}",
            f"- {artifacts.get('metrics', 'metrics.json')}",
            f"- {artifacts.get('curve', 'curve.csv')}",
            f"- {artifacts.get('trades', 'trades.csv')}",
            (f"- {artifacts.get('components', 'components.json')}" if adapter_id == ADAPTER_ID_CURVE_COMPOSER_V1 else "").strip(),
            "",
            "Notes:",
            *[n for n in notes if n],
            "",
        ]
    )

    try:
        paths = writer.write(
            run_id=run_id,
            blueprint_hash=str(runspec.get("blueprint_ref", {}).get("blueprint_hash", "")),
            policy_bundle_id=bundle_id,
            data_snapshot_id=snapshot_id,
            artifacts=artifacts,
            config_snapshot=config_snapshot,
            data_manifest=data_manifest,
            metrics=metrics,
            curve_csv=curve_csv,
            trades_csv=trades_csv,
            report_md=report_md,
            extra_json=(extra_json if adapter_id == ADAPTER_ID_VECTORBT_SIGNAL_V1 else None),
            extra_text=(extra_text if adapter_id == ADAPTER_ID_VECTORBT_SIGNAL_V1 else None),
            behavior_if_exists=behavior_if_exists,
        )
    except DossierAlreadyExists:
        paths = writer.write(
            run_id=run_id,
            blueprint_hash=str(runspec.get("blueprint_ref", {}).get("blueprint_hash", "")),
            policy_bundle_id=bundle_id,
            data_snapshot_id=snapshot_id,
            artifacts=artifacts,
            config_snapshot=config_snapshot,
            data_manifest=data_manifest,
            metrics=metrics,
            curve_csv=curve_csv,
            trades_csv=trades_csv,
            report_md=report_md,
            behavior_if_exists="noop",
        )

    # Optional extra evidence artifact: components.json for curve_composer_v1.
    # DossierWriter is immutable in v1; we append this file without rewriting existing ones.
    if adapter_id == ADAPTER_ID_CURVE_COMPOSER_V1:
        artifacts_map = dict(runspec.get("output_spec", {}).get("artifacts", {}))
        rel = str(artifacts_map.get("components", "components.json"))
        out_path = paths.dossier_dir / rel
        if not out_path.exists():
            ext = runspec.get("extensions", {}) if isinstance(runspec.get("extensions"), dict) else {}
            spec = ext.get("composer_spec") if isinstance(ext.get("composer_spec"), dict) else {}
            comps = spec.get("components") if isinstance(spec.get("components"), list) else []
            # Canonicalize components list for deterministic evidence.
            comps_norm: list[dict[str, Any]] = []
            for c in comps:
                if not isinstance(c, dict):
                    continue
                comps_norm.append(dict(c))
            comps_norm.sort(key=lambda d: (str(d.get("card_id") or ""), str(d.get("run_id") or "")))

            def _drop_ratio(orig: Any, inter: Any) -> float | None:
                try:
                    o = int(orig)
                    ii = int(inter)
                    if o <= 0:
                        return None
                    return float(max(0.0, min(1.0, 1.0 - (float(ii) / float(o)))))
                except Exception:
                    return None

            per: list[dict[str, Any]] = []
            for c in comps_norm:
                orig = c.get("_alignment_original_points")
                inter = c.get("_alignment_intersection_points")
                per.append(
                    {
                        "card_id": c.get("card_id"),
                        "run_id": c.get("run_id"),
                        "weight": c.get("weight"),
                        "original_points": orig,
                        "intersection_points": inter,
                        "drop_ratio": _drop_ratio(orig, inter),
                    }
                )

            # Deterministic evidence manifest for composition inputs.
            components_json = {
                "schema_version": "curve_composer_components_v1",
                "align": spec.get("align", "intersection"),
                "base_equity": spec.get("base_equity", 1.0),
                "alignment_stats": {
                    "overall": {"intersection_points": int(per[0]["intersection_points"]) if per else 0},
                    "per_component": per,
                },
                "components": [
                    {
                        "card_id": c.get("card_id"),
                        "run_id": c.get("run_id"),
                        "weight": c.get("weight"),
                        "dossier_dir": (writer.dossier_dir(str(c.get("run_id"))).as_posix() if c.get("run_id") else None),
                        "gate_results_path": (
                            (writer.dossier_dir(str(c.get("run_id"))) / "gate_results.json").as_posix()
                            if c.get("run_id")
                            else None
                        ),
                    }
                    for c in comps_norm
                ],
            }
            out_path.write_text(json.dumps(components_json, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # Validate dossier manifest against contract (must pass).
    dossier_manifest_path = paths.manifest
    code2, msg2 = contracts_validate.validate_json(dossier_manifest_path)
    if code2 != contracts_validate.EXIT_OK:
        return EXIT_INVALID, f"INVALID: dossier manifest failed contract validation: {msg2}"

    # Print key outputs for CLI callers.
    out_msg = json.dumps(
        {
            "run_id": run_id,
            "dossier_path": paths.dossier_dir.as_posix(),
            "metrics": metrics,
        },
        indent=2,
        sort_keys=True,
    )
    return EXIT_OK, out_msg


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m quant_eam.runner.run")
    parser.add_argument("--runspec", default=None, help="Path to a v1 RunSpec JSON.")
    parser.add_argument("--policy-bundle", required=True, help="Path to policy_bundle_v1.yaml (read-only).")
    parser.add_argument("--snapshot-id", default=None, help="Override runspec.data_snapshot_id.")
    parser.add_argument("--out-root", default=None, help="Artifacts root (default: env EAM_ARTIFACT_ROOT or /artifacts).")
    parser.add_argument("--demo", action="store_true", help="Offline demo: generate snapshot + runspec and run.")
    parser.add_argument(
        "--if-exists",
        choices=["noop", "reject"],
        default="noop",
        help="Append-only behavior if dossier already exists for run_id.",
    )
    args = parser.parse_args(argv)

    try:
        data_root = Path(os.getenv("EAM_DATA_ROOT", "/data"))
        artifact_root = Path(args.out_root) if args.out_root else Path(os.getenv("EAM_ARTIFACT_ROOT", "/artifacts"))
        policy_bundle_path = Path(args.policy_bundle)

        if args.demo:
            snapshot_id = args.snapshot_id or "demo_snap_001"
            # Ensure snapshot exists by running demo ingest (offline).
            demo_ingest_main(["--snapshot-id", snapshot_id])
            bundle_doc = load_policy_bundle(policy_bundle_path)
            runspec = _runspec_demo(snapshot_id, policy_bundle_id=str(bundle_doc["policy_bundle_id"]))
            runspec_path = Path("/tmp") / "run_spec_demo.json"
            runspec_path.write_text(json.dumps(runspec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            code, msg = run_once(
                runspec_path=runspec_path,
                policy_bundle_path=policy_bundle_path,
                snapshot_id_override=None,
                data_root=data_root,
                artifact_root=artifact_root,
                behavior_if_exists=args.if_exists,
            )
        else:
            if not args.runspec:
                print("ERROR: missing --runspec (or use --demo)", file=sys.stderr)
                return EXIT_USAGE_OR_ERROR
            runspec_path = Path(args.runspec)
            code, msg = run_once(
                runspec_path=runspec_path,
                policy_bundle_path=policy_bundle_path,
                snapshot_id_override=args.snapshot_id,
                data_root=data_root,
                artifact_root=artifact_root,
                behavior_if_exists=args.if_exists,
            )

        if code == EXIT_OK:
            print(msg)
        else:
            print(msg, file=sys.stderr)
        return code
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: {e}", file=sys.stderr)
        return EXIT_USAGE_OR_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
