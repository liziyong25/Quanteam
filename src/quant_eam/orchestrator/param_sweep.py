from __future__ import annotations

import itertools
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from quant_eam.backtest.vectorbt_adapter_mvp import BacktestInvalid, run_adapter
from quant_eam.contracts import validate as contracts_validate
from quant_eam.dossier.writer import DossierWriter
from quant_eam.gaterunner.run import run_once as gaterunner_run_once
from quant_eam.jobstore.store import (
    append_event,
    job_paths,
    load_job_events,
    load_job_spec,
    resolve_repo_relative,
    write_outputs_index,
)
from quant_eam.policies.load import load_yaml, sha256_file
from quant_eam.runner.run import _canonical_json_sha256, _load_policy_docs_from_bundle, _trade_lag_bars_default
from quant_eam.datacatalog.catalog import DataCatalog


EXIT_OK = 0
EXIT_INVALID = 2


def _artifact_root() -> Path:
    return Path(os.getenv("EAM_ARTIFACT_ROOT", "/artifacts"))


def _data_root() -> Path:
    return Path(os.getenv("EAM_DATA_ROOT", "/data"))


def _safe_metric_name(name: str) -> str:
    name = str(name or "").strip()
    if name in ("sharpe", "total_return", "max_drawdown"):
        return name
    return "sharpe"


def _canonical_hash(obj: Any) -> str:
    b = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    import hashlib

    return hashlib.sha256(b).hexdigest()


def _type_order(v: Any) -> tuple[int, Any]:
    if v is None:
        return (0, 0)
    if isinstance(v, bool):
        return (1, int(v))
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return (2, float(v))
    if isinstance(v, str):
        return (3, v)
    raise ValueError(f"unsupported param value type: {type(v).__name__}")


def enumerate_param_grid(param_grid: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(param_grid, dict) or not param_grid:
        raise ValueError("sweep_spec.param_grid must be a non-empty object")

    keys = sorted([str(k) for k in param_grid.keys()])
    values_by_key: list[list[Any]] = []
    for k in keys:
        raw = param_grid.get(k)
        if not isinstance(raw, list) or not raw:
            raise ValueError(f"sweep_spec.param_grid[{k!r}] must be a non-empty list")
        cleaned: list[Any] = []
        for v in raw:
            if v is None or isinstance(v, (bool, int, float, str)):
                cleaned.append(v)
            else:
                raise ValueError(f"sweep_spec.param_grid[{k!r}] contains unsupported value type: {type(v).__name__}")
        cleaned_sorted = sorted(cleaned, key=_type_order)
        values_by_key.append(cleaned_sorted)

    out: list[dict[str, Any]] = []
    for combo in itertools.product(*values_by_key):
        out.append({k: v for k, v in zip(keys, combo, strict=True)})
    return out


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_json_maybe(s: str) -> dict[str, Any]:
    try:
        doc = json.loads(s)
        return doc if isinstance(doc, dict) else {}
    except Exception:
        return {}


def _jsonl_lines(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            doc = json.loads(ln)
        except Exception:
            continue
        if isinstance(doc, dict):
            out.append(doc)
    return out


def _jsonl_append(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _write_json_atomic(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / (path.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _load_budget_policy(*, job_spec: dict[str, Any], sweep_spec: dict[str, Any]) -> tuple[dict[str, Any], str, str]:
    p = sweep_spec.get("budget_policy_path") or job_spec.get("budget_policy_path") or "policies/budget_policy_v1.yaml"
    p = str(p).strip() or "policies/budget_policy_v1.yaml"
    bp_path = resolve_repo_relative(p)
    doc = load_yaml(bp_path)
    if not isinstance(doc, dict) or doc.get("policy_version") != "v1":
        raise ValueError("invalid budget policy (must be a v1 YAML mapping)")
    return doc, str(p), sha256_file(bp_path)


def _extract_sweep_spec(job_spec: dict[str, Any]) -> dict[str, Any] | None:
    # Prefer job_spec.extensions.sweep_spec; fallback to blueprint.extensions.sweep_spec.
    if isinstance(job_spec.get("extensions"), dict):
        ss = job_spec["extensions"].get("sweep_spec")
        if isinstance(ss, dict):
            return ss
    bp = job_spec.get("blueprint") if isinstance(job_spec.get("blueprint"), dict) else {}
    if isinstance(bp, dict) and isinstance(bp.get("extensions"), dict):
        ss = bp["extensions"].get("sweep_spec")
        if isinstance(ss, dict):
            return ss
    return None


def _extract_signal_dsl_for_job(job_spec: dict[str, Any]) -> dict[str, Any] | None:
    sv = str(job_spec.get("schema_version") or "")
    if sv == "job_spec_v1":
        bp = job_spec.get("blueprint") if isinstance(job_spec.get("blueprint"), dict) else None
        if isinstance(bp, dict) and isinstance(bp.get("strategy_spec"), dict):
            return dict(bp["strategy_spec"])
        return None
    return None


@dataclass(frozen=True)
class SweepTrialResult:
    run_id: str
    dossier_path: str
    gate_results_path: str
    overall_pass: bool
    holdout_pass_minimal: bool | None
    test_metric: float | None


def _run_segment(
    *,
    snapshot_id: str,
    symbols: list[str],
    seg: dict[str, Any],
    adapter_id: str,
    lag_bars: int,
    execution_policy: dict[str, Any],
    cost_policy: dict[str, Any],
    signal_dsl: dict[str, Any],
    data_root: Path,
) -> tuple[dict[str, Any], str, str, dict[str, Any], str, str, dict[str, Any]]:
    start = str(seg.get("start") or "").strip()
    end = str(seg.get("end") or "").strip()
    as_of = str(seg.get("as_of") or "").strip()
    if not start or not end or not as_of:
        raise ValueError("segment missing start/end/as_of")

    cat = DataCatalog(root=data_root)
    rows, _stats = cat.query_ohlcv(snapshot_id=snapshot_id, symbols=symbols, start=start, end=end, as_of=as_of)
    if not rows:
        raise BacktestInvalid("query returned 0 rows (as_of filter may exclude all data)")
    prices = pd.DataFrame.from_records(rows)
    for c in ["open", "high", "low", "close", "volume"]:
        if c in prices.columns:
            prices[c] = prices[c].astype(float)
    prices["dt"] = prices["dt"].astype(str)
    prices["symbol"] = prices["symbol"].astype(str)

    out_bt = run_adapter(
        adapter_id=adapter_id,
        prices=prices,
        lag_bars=lag_bars,
        execution_policy=execution_policy,
        cost_policy=cost_policy,
        signal_dsl=signal_dsl,
    )

    seg_metrics = {
        "segment_id": str(seg.get("segment_id") or ""),
        "kind": str(seg.get("kind") or ""),
        "holdout": bool(seg.get("holdout")),
        "start": start,
        "end": end,
        "as_of": as_of,
        "total_return": out_bt.stats.get("total_return"),
        "max_drawdown": out_bt.stats.get("max_drawdown"),
        "sharpe": out_bt.stats.get("sharpe"),
        "trade_count": out_bt.stats.get("trade_count"),
        "adapter_id": out_bt.stats.get("adapter_id"),
        "strategy_id": out_bt.stats.get("strategy_id"),
        "lag_bars": out_bt.stats.get("lag_bars"),
        "dsl_fingerprint": out_bt.stats.get("dsl_fingerprint"),
        "signals_fingerprint": out_bt.stats.get("signals_fingerprint"),
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

    # Phase-27 risk evidence artifacts: produced by the backtest adapter and written into trial dossiers.
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

    return seg_metrics, curve_csv, trades_csv, out_bt.stats, positions_csv, turnover_csv, (exposure_obj if isinstance(exposure_obj, dict) else {})


def _extract_holdout_pass_minimal(gate_results_path: Path) -> bool | None:
    if not gate_results_path.is_file():
        return None
    try:
        doc = _read_json(gate_results_path)
    except Exception:
        return None
    if not isinstance(doc, dict):
        return None
    hs = doc.get("holdout_summary")
    if not isinstance(hs, dict):
        return None
    if "pass" not in hs:
        return None
    return bool(hs.get("pass"))


def run_param_sweep_for_job(*, job_id: str) -> tuple[int, str]:
    """Run a deterministic grid sweep for a job. Evidence is written under jobs/<job_id>/outputs/sweep/."""
    spec = load_job_spec(job_id)
    paths = job_paths(job_id)
    sweep_spec = _extract_sweep_spec(spec)
    if not isinstance(sweep_spec, dict):
        return EXIT_INVALID, "INVALID: missing sweep_spec (job_spec.extensions.sweep_spec or blueprint.extensions.sweep_spec)"

    param_grid = sweep_spec.get("param_grid")
    if not isinstance(param_grid, dict):
        return EXIT_INVALID, "INVALID: sweep_spec.param_grid must be an object"

    metric_name = _safe_metric_name(str(sweep_spec.get("metric") or "sharpe"))
    higher_is_better = bool(sweep_spec.get("higher_is_better", True))
    if metric_name == "max_drawdown":
        # max_drawdown is negative; "higher" means less negative, which is correct.
        higher_is_better = True if "higher_is_better" not in sweep_spec else bool(sweep_spec.get("higher_is_better"))

    try:
        combos = enumerate_param_grid(param_grid)
    except Exception as e:  # noqa: BLE001
        return EXIT_INVALID, f"INVALID: {e}"

    out_dir = paths.outputs_dir / "sweep"
    trials_path = out_dir / "trials.jsonl"
    leaderboard_path = out_dir / "leaderboard.json"

    if leaderboard_path.is_file():
        return EXIT_OK, f"noop: leaderboard exists: {leaderboard_path.as_posix()}"

    # Budget policy is a governance input (read-only); sweep may reduce limits but must not increase.
    try:
        budget_doc, budget_policy_path, budget_sha = _load_budget_policy(job_spec=spec, sweep_spec=sweep_spec)
    except Exception as e:  # noqa: BLE001
        return EXIT_INVALID, f"INVALID: {e}"
    bparams = budget_doc.get("params") if isinstance(budget_doc.get("params"), dict) else {}

    max_trials_budget = int(bparams.get("max_proposals_per_job") or 0) if isinstance(bparams, dict) else 0
    max_trials_user = sweep_spec.get("max_trials")
    max_trials_user_i = int(max_trials_user) if isinstance(max_trials_user, int) else 0

    max_trials = len(combos)
    if max_trials_budget > 0:
        max_trials = min(max_trials, max_trials_budget)
    if max_trials_user_i > 0:
        max_trials = min(max_trials, max_trials_user_i)

    stop_no_improve_n = int(bparams.get("stop_if_no_improvement_n") or 0) if isinstance(bparams, dict) else 0
    if isinstance(sweep_spec.get("stop_if_no_improvement_n"), int) and int(sweep_spec.get("stop_if_no_improvement_n")) >= 0:
        # Allow only a stricter (smaller) knob than governance default.
        v = int(sweep_spec["stop_if_no_improvement_n"])
        stop_no_improve_n = min(stop_no_improve_n or v, v) if stop_no_improve_n else v

    existing_trials = _jsonl_lines(trials_path)
    done_keys = set()
    for t in existing_trials:
        params = t.get("params")
        if isinstance(params, dict):
            done_keys.add(_canonical_hash(params))

    # Resolve policy bundle + lag bars.
    pb_path_str = str(spec.get("policy_bundle_path") or "policies/policy_bundle_v1.yaml").strip() or "policies/policy_bundle_v1.yaml"
    pb_path = resolve_repo_relative(pb_path_str)
    _bundle_id, execution_policy, cost_policy, asof_latency_policy, policy_sha = _load_policy_docs_from_bundle(pb_path)
    lag_bars = _trade_lag_bars_default(asof_latency_policy)

    # Base runspec (compiler output) is used for segment definitions + evidence. Must exist.
    outputs_idx = {}
    idx_p = paths.outputs_dir / "outputs.json"
    if idx_p.is_file():
        try:
            outputs_idx = _read_json(idx_p)
        except Exception:
            outputs_idx = {}
    if not isinstance(outputs_idx, dict):
        outputs_idx = {}
    runspec_path = outputs_idx.get("runspec_path")
    if not isinstance(runspec_path, str) or not Path(runspec_path).is_file():
        runspec_path2 = paths.outputs_dir / "runspec.json"
        if not runspec_path2.is_file():
            return EXIT_INVALID, "INVALID: missing runspec.json (compile must run before sweep)"
        runspec_path = runspec_path2.as_posix()

    runspec_base = _read_json(Path(runspec_path))
    if not isinstance(runspec_base, dict) or str(runspec_base.get("schema_version")) != "run_spec_v1":
        return EXIT_INVALID, "INVALID: runspec must be run_spec_v1"

    snapshot_id = str(runspec_base.get("data_snapshot_id") or spec.get("snapshot_id") or "").strip()
    if not snapshot_id:
        return EXIT_INVALID, "INVALID: missing snapshot_id"
    syms = (runspec_base.get("extensions", {}) or {}).get("symbols") if isinstance(runspec_base.get("extensions"), dict) else []
    symbols = [str(s) for s in syms] if isinstance(syms, list) else []
    if not symbols:
        return EXIT_INVALID, "INVALID: missing symbols in runspec.extensions.symbols"

    adapter_id = str((runspec_base.get("adapter", {}) or {}).get("adapter_id") or "").strip() or "vectorbt_signal_v1"

    base_signal_dsl = _extract_signal_dsl_for_job(spec)
    if not isinstance(base_signal_dsl, dict):
        # idea_spec_v1: load StrategySpecAgent output if present.
        if str(spec.get("schema_version") or "") == "idea_spec_v1":
            p = outputs_idx.get("signal_dsl_path")
            if isinstance(p, str) and Path(p).is_file():
                try:
                    base_signal_dsl = _read_json(Path(p))
                except Exception:
                    base_signal_dsl = None
        if not isinstance(base_signal_dsl, dict):
            return EXIT_INVALID, "INVALID: missing signal DSL (expected blueprint.strategy_spec or outputs.signal_dsl_path)"
    # Validate DSL contract once (defensive).
    code_dsl, msg_dsl = contracts_validate.validate_payload(base_signal_dsl)
    if code_dsl != contracts_validate.EXIT_OK:
        return EXIT_INVALID, f"INVALID: base signal_dsl invalid: {msg_dsl}"

    writer = DossierWriter(_artifact_root())

    best_metric: float | None = None
    best_trial: dict[str, Any] | None = None
    no_improve_streak = 0

    tried = 0
    wrote = 0

    for i, params in enumerate(combos):
        if tried >= max_trials:
            append_event(
                job_id=job_id,
                event_type="STOPPED_BUDGET",
                message="STOP: sweep trial budget exhausted",
                outputs={
                    "reason": "max_trials",
                    "limit": int(max_trials),
                    "current_trials": int(tried),
                    "grid_total": int(len(combos)),
                },
            )
            break

        key = _canonical_hash(params)
        if key in done_keys:
            tried += 1
            continue

        # Build trial DSL by overriding params (metadata only; policies remain referenced by id).
        dsl = dict(base_signal_dsl)
        p0 = dsl.get("params") if isinstance(dsl.get("params"), dict) else {}
        p1 = dict(p0)
        p1.update(params)
        dsl["params"] = p1

        # Make trial runspec unique and evidence-carrying.
        rs = dict(runspec_base)
        ext = rs.get("extensions") if isinstance(rs.get("extensions"), dict) else {}
        ext2 = dict(ext)
        ext2["sweep_params"] = dict(params)
        ext2["signal_dsl_hash"] = _canonical_hash(dsl)
        ext2["sweep_metric"] = metric_name
        rs["extensions"] = ext2

        run_id = _canonical_json_sha256(rs)[:12]

        # Run "test_overall" using legacy anchor segment (runspec.segments.test).
        seg_test = (rs.get("segments", {}) or {}).get("test", {}) if isinstance(rs.get("segments"), dict) else {}
        seg_obj = {"segment_id": "test_overall", "kind": "test", "holdout": False, **(seg_test if isinstance(seg_test, dict) else {})}

        try:
            base_metrics, base_curve_csv, base_trades_csv, base_stats, base_positions_csv, base_turnover_csv, base_exposure = _run_segment(
                snapshot_id=snapshot_id,
                symbols=symbols,
                seg=seg_obj,
                adapter_id=adapter_id,
                lag_bars=lag_bars,
                execution_policy=execution_policy,
                cost_policy=cost_policy,
                signal_dsl=dsl,
                data_root=_data_root(),
            )
        except BacktestInvalid as e:
            trial_doc = {
                "schema_version": "sweep_trial_v1",
                "job_id": job_id,
                "trial_index": int(i),
                "params": dict(params),
                "metric": metric_name,
                "test_metric": None,
                "overall_pass": False,
                "holdout_pass_minimal": None,
                "run_id": None,
                "dossier_path": None,
                "error": f"BacktestInvalid: {e}",
            }
            _jsonl_append(trials_path, trial_doc)
            done_keys.add(key)
            tried += 1
            wrote += 1
            continue

        # Phase-21 segment evidence (train/test only; holdout restricted and handled by GateRunner).
        segs = rs.get("segments") if isinstance(rs.get("segments"), dict) else {}
        seg_list = segs.get("list") if isinstance(segs.get("list"), list) else []
        seg_summary: dict[str, Any] = {
            "schema_version": "segments_summary_v1",
            "run_id": run_id,
            "segments": [],
            "extensions": {"protocol": ((ext2.get("evaluation_protocol_v1") or {}) if isinstance(ext2.get("evaluation_protocol_v1"), dict) else {}).get("protocol")},
        }
        extra_json: dict[str, Any] = {}
        extra_text: dict[str, str] = {}

        for seg in seg_list:
            if not isinstance(seg, dict):
                continue
            sid = str(seg.get("segment_id") or "").strip()
            kind = str(seg.get("kind") or "").strip()
            holdout = bool(seg.get("holdout"))
            if not sid or not kind:
                continue
            if holdout:
                seg_summary["segments"].append(
                    {"segment_id": sid, "kind": kind, "holdout": True, "start": seg.get("start"), "end": seg.get("end"), "as_of": seg.get("as_of"), "artifacts": {}}
                )
                continue

            m, c_csv, t_csv, _stats2, _pos_csv2, _to_csv2, _ex2 = _run_segment(
                snapshot_id=snapshot_id,
                symbols=symbols,
                seg=seg,
                adapter_id=adapter_id,
                lag_bars=lag_bars,
                execution_policy=execution_policy,
                cost_policy=cost_policy,
                signal_dsl=dsl,
                data_root=_data_root(),
            )
            seg_dir = f"segments/{sid}"
            extra_json[f"{seg_dir}/metrics.json"] = m
            extra_text[f"{seg_dir}/curve.csv"] = c_csv
            extra_text[f"{seg_dir}/trades.csv"] = t_csv

            seg_summary["segments"].append(
                {
                    "segment_id": sid,
                    "kind": kind,
                    "holdout": False,
                    "start": seg.get("start"),
                    "end": seg.get("end"),
                    "as_of": seg.get("as_of"),
                    "metrics": {
                        "total_return": m.get("total_return"),
                        "max_drawdown": m.get("max_drawdown"),
                        "sharpe": m.get("sharpe"),
                        "trade_count": m.get("trade_count"),
                    },
                    "artifacts": {"metrics": f"{seg_dir}/metrics.json", "curve": f"{seg_dir}/curve.csv", "trades": f"{seg_dir}/trades.csv"},
                }
            )

        # Data manifest evidence.
        lake_manifest_path = _data_root() / "lake" / snapshot_id / "manifest.json"
        data_manifest: dict[str, Any] = {"snapshot_id": snapshot_id}
        if lake_manifest_path.is_file():
            data_manifest = _read_json(lake_manifest_path)

        config_snapshot = {
            "runspec": rs,
            "policy_bundle_id": str(runspec_base.get("policy_bundle_id") or ""),
            "policy_sha256": policy_sha,
            "env": {"EAM_DATA_ROOT": _data_root().as_posix(), "EAM_ARTIFACT_ROOT": _artifact_root().as_posix()},
            "deps": {"python": sys.version.split()[0], "pandas": pd.__version__},
            "extensions": {
                "sweep_job_id": job_id,
                "sweep_trial_index": int(i),
                "budget_policy_path": budget_policy_path,
                "budget_policy_id": str(budget_doc.get("policy_id") or ""),
                "budget_policy_sha256": budget_sha,
            },
        }

        artifacts = dict((runspec_base.get("output_spec", {}) or {}).get("artifacts", {}))
        # Ensure segments summary and signal DSL are discoverable.
        artifacts.setdefault("segments_summary", "segments_summary.json")
        artifacts.setdefault("signal_dsl", "signal_dsl.json")
        # Phase-27: risk evidence artifacts (required by risk_policy_compliance_v1 gate).
        artifacts.setdefault("positions", "positions.csv")
        artifacts.setdefault("turnover", "turnover.csv")
        artifacts.setdefault("exposure", "exposure.json")

        extra_json[artifacts["segments_summary"]] = seg_summary
        extra_json[artifacts["signal_dsl"]] = dsl
        extra_text[str(artifacts["positions"])] = base_positions_csv
        extra_text[str(artifacts["turnover"])] = base_turnover_csv
        extra_json[str(artifacts["exposure"])] = base_exposure

        # Top-level metrics follow runner convention.
        metrics_top = dict(base_metrics)
        metrics_top["segments_summary_ref"] = artifacts["segments_summary"]
        metrics_top["adapter_id"] = adapter_id
        metrics_top["strategy_id"] = str(base_stats.get("strategy_id") or metrics_top.get("strategy_id") or "signal_dsl_v1")
        metrics_top["lag_bars"] = int(lag_bars)

        report_md = "\n".join(
            [
                "# Sweep Trial Report (MVP)",
                "",
                f"- run_id: `{run_id}`",
                f"- base_job_id: `{job_id}`",
                f"- snapshot_id: `{snapshot_id}`",
                f"- metric: `{metric_name}`",
                f"- params: `{json.dumps(params, sort_keys=True, ensure_ascii=True)}`",
                "",
                "Artifacts:",
                "- config_snapshot.json",
                "- data_manifest.json",
                "- metrics.json",
                "- curve.csv",
                "- trades.csv",
                "- gate_results.json (after gaterunner)",
                "- risk_report.json (after gaterunner risk gate)",
                "",
            ]
        )

        # Blueprint hash: preserve base blueprint hash if present; include sweep params in runspec hash anyway.
        blueprint_hash = str((runspec_base.get("blueprint_ref", {}) or {}).get("blueprint_hash") or "")

        paths_written = writer.write(
            run_id=run_id,
            blueprint_hash=blueprint_hash,
            policy_bundle_id=str(runspec_base.get("policy_bundle_id") or ""),
            data_snapshot_id=snapshot_id,
            artifacts=artifacts,
            config_snapshot=config_snapshot,
            data_manifest=data_manifest,
            metrics=metrics_top,
            curve_csv=base_curve_csv,
            trades_csv=base_trades_csv,
            report_md=report_md,
            extra_json=extra_json,
            extra_text=extra_text,
            behavior_if_exists="noop",
        )

        # Run gates for this trial dossier (writes gate_results.json).
        code_g, msg_g = gaterunner_run_once(dossier_dir=paths_written.dossier_dir, policy_bundle_path=pb_path)
        out_g = _parse_json_maybe(msg_g)
        gate_results_path = paths_written.dossier_dir / "gate_results.json"
        overall_pass = bool(out_g.get("overall_pass")) if out_g else False
        holdout_pass_minimal = _extract_holdout_pass_minimal(gate_results_path)

        # Extract test metric from top-level metrics.json (computed on test_overall).
        tm_raw = metrics_top.get(metric_name)
        try:
            test_metric = float(tm_raw) if tm_raw is not None else None
        except Exception:
            test_metric = None

        trial_doc = {
            "schema_version": "sweep_trial_v1",
            "job_id": job_id,
            "trial_index": int(i),
            "params": dict(params),
            "metric": metric_name,
            "higher_is_better": bool(higher_is_better),
            "test_metric": test_metric,
            "overall_pass": bool(overall_pass),
            "holdout_pass_minimal": holdout_pass_minimal,
            "run_id": run_id,
            "dossier_path": paths_written.dossier_dir.as_posix(),
            "gate_results_path": gate_results_path.as_posix() if gate_results_path.is_file() else None,
            "gaterunner_exit_code": int(code_g),
        }
        _jsonl_append(trials_path, trial_doc)
        done_keys.add(key)
        tried += 1
        wrote += 1

        # Update best candidate by test metric only (holdout is filter-only).
        eligible = bool(overall_pass) and (holdout_pass_minimal is not False)
        if eligible and test_metric is not None:
            if best_metric is None:
                best_metric = float(test_metric)
                best_trial = dict(trial_doc)
                no_improve_streak = 0
            else:
                improved = (test_metric > best_metric) if higher_is_better else (test_metric < best_metric)
                if improved:
                    best_metric = float(test_metric)
                    best_trial = dict(trial_doc)
                    no_improve_streak = 0
                else:
                    no_improve_streak += 1
        else:
            no_improve_streak += 1

        if stop_no_improve_n and no_improve_streak >= stop_no_improve_n:
            append_event(
                job_id=job_id,
                event_type="STOPPED_BUDGET",
                message="STOP: sweep stopped due to no improvement",
                outputs={
                    "reason": "stop_if_no_improvement_n",
                    "limit": int(stop_no_improve_n),
                    "no_improve_streak": int(no_improve_streak),
                    "trials_completed": int(tried),
                },
            )
            break

    # Build leaderboard from all recorded trials.
    all_trials = _jsonl_lines(trials_path)

    def _eligible_trial(t: dict[str, Any]) -> bool:
        if not bool(t.get("overall_pass")):
            return False
        hp = t.get("holdout_pass_minimal")
        return (hp is None) or bool(hp)

    def _metric_val(t: dict[str, Any]) -> float | None:
        try:
            return float(t.get("test_metric")) if t.get("test_metric") is not None else None
        except Exception:
            return None

    elig = [t for t in all_trials if isinstance(t, dict) and _eligible_trial(t) and _metric_val(t) is not None]
    elig_sorted = sorted(
        elig,
        key=lambda t: _metric_val(t) if _metric_val(t) is not None else float("-inf"),
        reverse=bool(higher_is_better),
    )
    best = elig_sorted[0] if elig_sorted else None

    leaderboard = {
        "schema_version": "leaderboard_v1",
        "job_id": job_id,
        "metric": metric_name,
        "higher_is_better": bool(higher_is_better),
        "grid_total": int(len(combos)),
        "max_trials": int(max_trials),
        "trials_recorded": int(len(all_trials)),
        "budget_policy_ref": {
            "budget_policy_path": budget_policy_path,
            "budget_policy_id": str(budget_doc.get("policy_id") or ""),
            "budget_policy_sha256": budget_sha,
        },
        "best": {
            "trial_index": int(best.get("trial_index")) if isinstance(best, dict) and best.get("trial_index") is not None else None,
            "params": best.get("params") if isinstance(best, dict) else None,
            "test_metric": best.get("test_metric") if isinstance(best, dict) else None,
            "run_id": best.get("run_id") if isinstance(best, dict) else None,
            "dossier_path": best.get("dossier_path") if isinstance(best, dict) else None,
            "gate_results_path": best.get("gate_results_path") if isinstance(best, dict) else None,
        },
        "top": [
            {
                "trial_index": int(t.get("trial_index")) if t.get("trial_index") is not None else None,
                "params": t.get("params"),
                "test_metric": t.get("test_metric"),
                "run_id": t.get("run_id"),
                "dossier_path": t.get("dossier_path"),
                "overall_pass": bool(t.get("overall_pass")),
                "holdout_pass_minimal": t.get("holdout_pass_minimal"),
            }
            for t in elig_sorted[:10]
        ],
        "extensions": {},
    }

    _write_json_atomic(leaderboard_path, leaderboard)
    write_outputs_index(
        job_id=job_id,
        updates={
            "sweep_trials_path": trials_path.as_posix(),
            "sweep_leaderboard_path": leaderboard_path.as_posix(),
            "sweep_metric": metric_name,
        },
    )

    return EXIT_OK, f"OK: sweep wrote {len(all_trials)} trial(s) and leaderboard: {leaderboard_path.as_posix()}"
