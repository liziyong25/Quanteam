from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from quant_eam.backtest.signal_compiler import SignalCompileInvalid, compile_signal_dsl_v1, dsl_fingerprint
from quant_eam.data_lake.timeutil import parse_iso_datetime
from quant_eam.datacatalog.catalog import DataCatalog
from quant_eam.policies.resolve import load_policy_bundle, resolve_asof_latency_policy


@dataclass(frozen=True)
class TraceMeta:
    snapshot_id: str
    dataset_id: str
    as_of: str
    rows_before_asof: int
    rows_after_asof: int
    rows_written: int
    lag_bars_used: int
    dsl_fingerprint: str
    signals_fingerprint: str


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _trade_lag_bars_default_from_policy_bundle(policy_bundle_path: Path) -> int:
    bundle_path = Path(policy_bundle_path)
    if not bundle_path.is_absolute():
        # Resolve relative to repo root via policies loader helper.
        from quant_eam.policies.load import find_repo_root

        bundle_path = find_repo_root() / bundle_path
    bundle_doc = load_policy_bundle(bundle_path)
    # Resolve asof_latency policy (read-only); trade_lag_bars_default default=1.
    asof_pid, asof_doc = resolve_asof_latency_policy(bundle_doc=bundle_doc, policies_dir=bundle_path.parent)
    _ = asof_pid
    params = asof_doc.get("params") if isinstance(asof_doc, dict) else {}
    if isinstance(params, dict) and "trade_lag_bars_default" in params:
        try:
            v = int(params["trade_lag_bars_default"])
            return max(1, v)
        except Exception:
            return 1
    return 1


def run_calc_trace_preview(
    *,
    out_dir: Path,
    snapshot_id: str,
    as_of: str,
    start: str,
    end: str,
    symbols: list[str],
    signal_dsl_path: Path,
    variable_dictionary_path: Path,
    calc_trace_plan_path: Path,
    data_root: Path,
    dataset_id: str = "ohlcv_1d",
) -> tuple[Path, Path, TraceMeta]:
    """Execute a minimal calc trace preview using DataCatalog (as_of filtered).

    Output CSV columns (minimum):
    dt,symbol,close,available_at,eligible,entry_raw,entry_lagged
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    signal_dsl = _load_json(signal_dsl_path)
    var_dict = _load_json(variable_dictionary_path)
    trace_plan = _load_json(calc_trace_plan_path)

    # Use calc_trace_plan first sample if present.
    sample = None
    if isinstance(trace_plan, dict) and isinstance(trace_plan.get("samples"), list) and trace_plan["samples"]:
        s0 = trace_plan["samples"][0]
        if isinstance(s0, dict):
            sample = s0
    if sample:
        symbols = [str(s) for s in (sample.get("symbols") or symbols) if str(s).strip()] or symbols
        start = str(sample.get("start") or start)
        end = str(sample.get("end") or end)
        max_rows = int(sample.get("max_rows") or 20)
    else:
        max_rows = 20

    cat = DataCatalog(root=data_root)
    rows, stats = cat.query_ohlcv(snapshot_id=snapshot_id, symbols=symbols, start=start, end=end, as_of=as_of, dataset_id=dataset_id)

    # Keep only the first max_rows (stable order already symbol,dt).
    rows = rows[:max_rows]

    # Determine lag bars from policy bundle (SSOT). We read policy_bundle_path as metadata from outputs;
    # orchestrator does not pass it in explicitly in v1.
    policy_bundle_path = "policies/policy_bundle_v1.yaml"
    try:
        ext = signal_dsl.get("extensions") if isinstance(signal_dsl, dict) else {}
        if isinstance(ext, dict) and isinstance(ext.get("policy_bundle_path"), str) and ext.get("policy_bundle_path"):
            policy_bundle_path = str(ext["policy_bundle_path"])
        ext2 = var_dict.get("extensions") if isinstance(var_dict, dict) else {}
        if isinstance(ext2, dict) and isinstance(ext2.get("policy_bundle_path"), str) and ext2.get("policy_bundle_path"):
            policy_bundle_path = str(ext2["policy_bundle_path"])
    except Exception:
        policy_bundle_path = "policies/policy_bundle_v1.yaml"

    lag_bars = _trade_lag_bars_default_from_policy_bundle(Path(policy_bundle_path))

    asof_dt = parse_iso_datetime(as_of)

    # Compile signals + intermediates (single truth).
    prices_df = pd.DataFrame.from_records(rows)
    for c in ("open", "high", "low", "close", "volume"):
        if c in prices_df.columns:
            try:
                prices_df[c] = prices_df[c].astype(float)
            except Exception:
                pass

    try:
        comp = compile_signal_dsl_v1(prices=prices_df, signal_dsl=signal_dsl if isinstance(signal_dsl, dict) else {}, lag_bars=lag_bars)
    except SignalCompileInvalid as e:
        raise ValueError(f"trace preview failed to compile signal_dsl_v1: {e}")

    comp_df = comp.frame.copy()
    # Join raw price columns that are not in compiler output (available_at).
    # compiler keeps dt,symbol; we merge with original rows by (symbol,dt) stable.
    px_keep = prices_df[["dt", "symbol", "close", "available_at"]].copy()
    merged = pd.merge(px_keep, comp_df, on=["dt", "symbol"], how="left", sort=False)

    # Build output rows for CSV; eligible computed vs as_of (even though DataCatalog enforces availability).
    out_rows: list[dict[str, Any]] = []
    for rec in merged.sort_values(["symbol", "dt"], kind="mergesort").to_dict(orient="records"):
        eligible = bool(parse_iso_datetime(str(rec.get("available_at"))) <= asof_dt)
        row: dict[str, Any] = {
            "dt": str(rec.get("dt")),
            "symbol": str(rec.get("symbol")),
            "close": str(rec.get("close")),
            "available_at": str(rec.get("available_at")),
            "eligible": "true" if eligible else "false",
        }
        # Intermediates first (stable ordering).
        for c in comp.intermediate_cols:
            if c in rec:
                row[c] = "" if rec[c] is None else str(rec[c])
        for k in ("entry_raw", "exit_raw", "entry_lagged", "exit_lagged"):
            v = bool(rec.get(k)) if rec.get(k) is not None else False
            row[k] = "true" if v else "false"
        out_rows.append(row)

    out_csv = out_dir / "calc_trace_preview.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        fieldnames = ["dt", "symbol", "close", "available_at", "eligible", *comp.intermediate_cols, "entry_raw", "exit_raw", "entry_lagged", "exit_lagged"]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in out_rows:
            w.writerow(r)

    meta = TraceMeta(
        snapshot_id=snapshot_id,
        dataset_id=dataset_id,
        as_of=as_of,
        rows_before_asof=int(stats.rows_before_asof),
        rows_after_asof=int(stats.rows_after_asof),
        rows_written=len(out_rows),
        lag_bars_used=int(lag_bars),
        dsl_fingerprint=str(comp.dsl_fingerprint),
        signals_fingerprint=str(comp.signals_fingerprint),
    )
    meta_path = out_dir / "trace_meta.json"
    meta_path.write_text(json.dumps(meta.__dict__, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out_csv, meta_path, meta


def _normalize_row(r: dict[str, Any]) -> dict[str, Any]:
    # Convert common numeric fields to float where possible, keep original strings for dt/symbol.
    out = dict(r)
    for k in ("open", "high", "low", "close", "volume"):
        if k in out:
            try:
                out[k] = float(out[k])
            except Exception:
                pass
    return out
