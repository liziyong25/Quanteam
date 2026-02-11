from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from quant_eam.backtest.vectorbt_adapter_mvp import BacktestInvalid, run_adapter
from quant_eam.datacatalog.catalog import DataCatalog
from quant_eam.policies.load import default_policies_dir, load_yaml
from quant_eam.policies.resolve import load_policy_bundle


class AttributionError(ValueError):
    pass


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _source_date_now_iso() -> str:
    # Deterministic timestamps for tests/CI; fall back to wall clock if unset.
    sde = os.getenv("SOURCE_DATE_EPOCH")
    if sde:
        try:
            ts = int(sde)
            return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))
        except Exception:  # noqa: BLE001
            pass
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(time.time())))


def _read_curve(curve_csv: Path) -> pd.DataFrame:
    if not curve_csv.is_file():
        raise AttributionError(f"missing curve.csv: {curve_csv.as_posix()}")
    df = pd.read_csv(curve_csv)
    if "dt" not in df.columns or "equity" not in df.columns:
        raise AttributionError("curve.csv must have columns: dt,equity")
    df["dt"] = pd.to_datetime(df["dt"], errors="coerce")
    if df["dt"].isna().any():
        raise AttributionError("curve.csv has invalid dt values")
    df["equity"] = pd.to_numeric(df["equity"], errors="coerce")
    if df["equity"].isna().any():
        raise AttributionError("curve.csv has invalid equity values")
    df = df.sort_values(["dt"], kind="mergesort").reset_index(drop=True)
    if df.empty:
        raise AttributionError("curve.csv has 0 rows after parsing")
    return df


def _read_trades(trades_csv: Path) -> pd.DataFrame | None:
    if not trades_csv.is_file():
        return None
    df = pd.read_csv(trades_csv)
    if df.empty:
        return df
    for c in ("entry_dt", "exit_dt"):
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    if "pnl" in df.columns:
        df["pnl"] = pd.to_numeric(df["pnl"], errors="coerce")
    if "fees" in df.columns:
        df["fees"] = pd.to_numeric(df["fees"], errors="coerce")
    if "qty" in df.columns:
        df["qty"] = pd.to_numeric(df["qty"], errors="coerce")
    if "symbol" in df.columns:
        df["symbol"] = df["symbol"].astype(str)
    # Stable ordering for deterministic top/worst.
    df = df.sort_values(["exit_dt", "symbol"], kind="mergesort").reset_index(drop=True)
    return df


def _drawdown_diagnostics(curve: pd.DataFrame, top_n: int = 3) -> dict[str, Any]:
    equity = curve["equity"].astype(float)
    peak = equity.cummax()
    dd = equity / peak - 1.0
    max_dd = float(dd.min()) if not dd.empty else 0.0

    # Duration: longest consecutive period dd < 0.
    under = (dd < 0.0).astype(int)
    longest = 0
    cur = 0
    for v in under.tolist():
        if v:
            cur += 1
            longest = max(longest, cur)
        else:
            cur = 0

    # Top drawdown periods: find local minima and record windows from previous peak to recovery (or end).
    # Keep it deterministic + minimal (no heavy heuristics).
    top_periods: list[dict[str, Any]] = []
    if len(curve) >= 2:
        # Identify candidate minima points.
        for i in range(1, len(dd) - 1):
            if dd.iat[i] <= dd.iat[i - 1] and dd.iat[i] <= dd.iat[i + 1]:
                top_periods.append({"dt": curve["dt"].iat[i].isoformat(), "drawdown": float(dd.iat[i])})
        top_periods.sort(key=lambda x: x["drawdown"])  # most negative first
        top_periods = top_periods[: max(0, int(top_n))]

    return {
        "max_drawdown": max_dd,
        "dd_duration_bars": int(longest),
        "top_dd_points": top_periods,
    }


def _trade_diagnostics(trades: pd.DataFrame | None, top_n: int = 3) -> dict[str, Any]:
    if trades is None or trades.empty or "pnl" not in trades.columns:
        return {
            "trade_count": 0,
            "win_rate": None,
            "avg_win": None,
            "avg_loss": None,
            "profit_factor": None,
            "top_trades": [],
            "worst_trades": [],
        }

    pnl = trades["pnl"].dropna().astype(float)
    if pnl.empty:
        return {
            "trade_count": int(len(trades)),
            "win_rate": None,
            "avg_win": None,
            "avg_loss": None,
            "profit_factor": None,
            "top_trades": [],
            "worst_trades": [],
        }

    wins = pnl[pnl > 0.0]
    losses = pnl[pnl < 0.0]
    win_rate = float(len(wins) / len(pnl)) if len(pnl) else None
    avg_win = float(wins.mean()) if len(wins) else None
    avg_loss = float(losses.mean()) if len(losses) else None
    gross_win = float(wins.sum()) if len(wins) else 0.0
    gross_loss = float((-losses).sum()) if len(losses) else 0.0
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else None

    # Stable selection (sort by pnl, tie-break by exit_dt/symbol).
    cols = [c for c in ("symbol", "entry_dt", "exit_dt", "pnl", "qty", "fees") if c in trades.columns]
    t = trades[cols].copy()
    t["pnl"] = pd.to_numeric(t["pnl"], errors="coerce")
    t = t.dropna(subset=["pnl"])
    t = t.sort_values(["pnl", "exit_dt", "symbol"], kind="mergesort")
    worst = t.head(top_n).to_dict(orient="records")
    best = t.tail(top_n).sort_values(["pnl", "exit_dt", "symbol"], kind="mergesort", ascending=[False, True, True]).to_dict(
        orient="records"
    )

    def _row_to_obj(r: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k, v in r.items():
            if isinstance(v, (pd.Timestamp,)):
                out[k] = v.isoformat()
            elif pd.isna(v):
                out[k] = None
            else:
                out[k] = v
        return out

    return {
        "trade_count": int(len(pnl)),
        "win_rate": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": profit_factor,
        "top_trades": [_row_to_obj(x) for x in best],
        "worst_trades": [_row_to_obj(x) for x in worst],
    }


def _contribution_by_symbol(trades: pd.DataFrame | None) -> list[dict[str, Any]]:
    if trades is None or trades.empty or "pnl" not in trades.columns or "symbol" not in trades.columns:
        return []
    g = trades.dropna(subset=["pnl"]).groupby("symbol", sort=True)["pnl"].sum()
    out = [{"symbol": str(sym), "pnl": float(val)} for sym, val in g.items()]
    out.sort(key=lambda x: (x["symbol"],))
    return out


def _contribution_by_timebucket(trades: pd.DataFrame | None, curve: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    # If trades exist, attribute by trade exit bucket; otherwise use equity curve returns as a proxy.
    out: dict[str, list[dict[str, Any]]] = {"by_month": [], "by_week": []}
    if trades is not None and (not trades.empty) and "pnl" in trades.columns and "exit_dt" in trades.columns:
        t = trades.dropna(subset=["pnl", "exit_dt"]).copy()
        if t.empty:
            return out
        t["month"] = t["exit_dt"].dt.strftime("%Y-%m")
        t["week"] = t["exit_dt"].dt.strftime("%G-W%V")
        by_m = t.groupby("month", sort=True)["pnl"].sum()
        by_w = t.groupby("week", sort=True)["pnl"].sum()
        out["by_month"] = [{"bucket": str(k), "pnl": float(v)} for k, v in by_m.items()]
        out["by_week"] = [{"bucket": str(k), "pnl": float(v)} for k, v in by_w.items()]
        return out

    # Fallback: bucket equity curve pct_change.
    c = curve.copy()
    c["ret"] = c["equity"].pct_change().fillna(0.0)
    c["month"] = c["dt"].dt.strftime("%Y-%m")
    c["week"] = c["dt"].dt.strftime("%G-W%V")
    by_m = c.groupby("month", sort=True)["ret"].sum()
    by_w = c.groupby("week", sort=True)["ret"].sum()
    out["by_month"] = [{"bucket": str(k), "return": float(v)} for k, v in by_m.items()]
    out["by_week"] = [{"bucket": str(k), "return": float(v)} for k, v in by_w.items()]
    return out


@dataclass(frozen=True)
class RecomputeResult:
    gross_return: float | None
    net_return_cost_x2: float | None
    notes: str | None


def _find_bundle_path(policies_dir: Path, policy_bundle_id: str) -> Path:
    for p in sorted([pp for pp in policies_dir.glob("policy_bundle*.y*ml") if pp.is_file()]):
        doc = load_yaml(p)
        if isinstance(doc, dict) and str(doc.get("policy_bundle_id", "")).strip() == policy_bundle_id:
            return p
    raise AttributionError(f"policy_bundle_id not found in policies/: {policy_bundle_id!r}")


def _load_policy_file_by_id(policies_dir: Path, policy_id: str) -> dict[str, Any]:
    for p in sorted([pp for pp in policies_dir.glob("*.y*ml") if pp.is_file()]):
        doc = load_yaml(p)
        if isinstance(doc, dict) and str(doc.get("policy_id", "")).strip() == policy_id:
            return doc
    raise AttributionError(f"policy_id not found in policies/: {policy_id!r}")


def _recompute_cost_sensitivity(
    *,
    dossier_dir: Path,
    policies_dir: Path,
    cfg: dict[str, Any],
    lag_bars: int,
) -> RecomputeResult:
    runspec = cfg.get("runspec") if isinstance(cfg.get("runspec"), dict) else {}
    policy_bundle_id = str(cfg.get("policy_bundle_id") or runspec.get("policy_bundle_id") or "").strip()
    if not policy_bundle_id:
        return RecomputeResult(gross_return=None, net_return_cost_x2=None, notes="missing policy_bundle_id")

    # Resolve bundle + referenced execution/cost policies.
    bundle_path = _find_bundle_path(policies_dir, policy_bundle_id)
    bundle_doc = load_policy_bundle(bundle_path)

    exec_pid = str(bundle_doc.get("execution_policy_id") or "").strip()
    cost_pid = str(bundle_doc.get("cost_policy_id") or "").strip()
    if not exec_pid or not cost_pid:
        return RecomputeResult(gross_return=None, net_return_cost_x2=None, notes="bundle missing execution/cost refs")

    execution_policy = _load_policy_file_by_id(policies_dir, exec_pid)
    cost_policy = _load_policy_file_by_id(policies_dir, cost_pid)

    # Pull segment window: prefer explicit segments.list selected elsewhere; in dossier config snapshot, keep to test.
    segs = runspec.get("segments") if isinstance(runspec.get("segments"), dict) else {}
    test_seg = segs.get("test") if isinstance(segs.get("test"), dict) else None
    if not test_seg:
        return RecomputeResult(gross_return=None, net_return_cost_x2=None, notes="missing runspec.segments.test")

    snapshot_id = str(runspec.get("data_snapshot_id") or "").strip()
    if not snapshot_id:
        return RecomputeResult(gross_return=None, net_return_cost_x2=None, notes="missing runspec.data_snapshot_id")

    ext = runspec.get("extensions") if isinstance(runspec.get("extensions"), dict) else {}
    symbols = ext.get("symbols") if isinstance(ext.get("symbols"), list) else None
    if not symbols:
        return RecomputeResult(gross_return=None, net_return_cost_x2=None, notes="missing runspec.extensions.symbols")
    symbols = [str(s) for s in symbols if str(s).strip()]
    if not symbols:
        return RecomputeResult(gross_return=None, net_return_cost_x2=None, notes="empty runspec.extensions.symbols")

    adapter = runspec.get("adapter") if isinstance(runspec.get("adapter"), dict) else {}
    adapter_id = str(adapter.get("adapter_id") or "").strip()
    if not adapter_id:
        return RecomputeResult(gross_return=None, net_return_cost_x2=None, notes="missing runspec.adapter.adapter_id")

    start = str(test_seg.get("start") or "")
    end = str(test_seg.get("end") or "")
    as_of = str(test_seg.get("as_of") or "")
    if not (start and end and as_of):
        return RecomputeResult(gross_return=None, net_return_cost_x2=None, notes="missing test segment window fields")

    cat = DataCatalog(root=Path(os.getenv("EAM_DATA_ROOT", "/data")))
    rows, _stats = cat.query_ohlcv(snapshot_id=snapshot_id, symbols=symbols, start=start, end=end, as_of=as_of)
    if not rows:
        return RecomputeResult(gross_return=None, net_return_cost_x2=None, notes="no ohlcv rows returned (as_of filtered?)")

    prices = pd.DataFrame(rows)
    for k in ("open", "close"):
        prices[k] = pd.to_numeric(prices.get(k), errors="coerce")
    prices["dt"] = prices["dt"].astype(str)
    prices["symbol"] = prices["symbol"].astype(str)
    prices = prices.dropna(subset=["open", "close"]).reset_index(drop=True)
    if prices.empty:
        return RecomputeResult(gross_return=None, net_return_cost_x2=None, notes="prices empty after parsing")

    # Optional signal_dsl artifact in dossier.
    signal_dsl = None
    p_dsl = dossier_dir / "signal_dsl.json"
    if p_dsl.is_file():
        try:
            signal_dsl = _load_json(p_dsl)
        except Exception:  # noqa: BLE001
            signal_dsl = None

    # Prepare cost policy variants (do not mutate original doc).
    def with_cost_bps(mult: float) -> dict[str, Any]:
        out = dict(cost_policy)
        params = dict(cost_policy.get("params") or {})
        try:
            params["commission_bps"] = float(params.get("commission_bps", 0.0)) * mult
        except Exception:  # noqa: BLE001
            params["commission_bps"] = 0.0
        try:
            params["slippage_bps"] = float(params.get("slippage_bps", 0.0)) * mult
        except Exception:  # noqa: BLE001
            params["slippage_bps"] = 0.0
        out["params"] = params
        return out

    try:
        gross = run_adapter(
            adapter_id=adapter_id,
            prices=prices,
            lag_bars=lag_bars,
            execution_policy=execution_policy,
            cost_policy=with_cost_bps(0.0),
            signal_dsl=signal_dsl if isinstance(signal_dsl, dict) else None,
        ).stats.get("total_return")
        x2 = run_adapter(
            adapter_id=adapter_id,
            prices=prices,
            lag_bars=lag_bars,
            execution_policy=execution_policy,
            cost_policy=with_cost_bps(2.0),
            signal_dsl=signal_dsl if isinstance(signal_dsl, dict) else None,
        ).stats.get("total_return")
    except BacktestInvalid as e:
        return RecomputeResult(gross_return=None, net_return_cost_x2=None, notes=f"recompute failed: {e}")

    gross_f = float(gross) if isinstance(gross, (int, float)) else None
    x2_f = float(x2) if isinstance(x2, (int, float)) else None
    return RecomputeResult(gross_return=gross_f, net_return_cost_x2=x2_f, notes=None)


def write_attribution_artifacts(*, dossier_dir: Path, policies_dir: Path | None = None) -> list[Path]:
    """Write Phase-24 attribution evidence into a dossier directory (append-only).

    Artifacts:
    - attribution_report.json (dossier root)
    - reports/attribution/report.md
    """
    dossier_dir = Path(dossier_dir)
    if not dossier_dir.is_dir():
        raise AttributionError(f"not a dossier dir: {dossier_dir.as_posix()}")

    out_paths: list[Path] = []

    curve = _read_curve(dossier_dir / "curve.csv")
    trades = _read_trades(dossier_dir / "trades.csv")
    metrics = _load_json(dossier_dir / "metrics.json") if (dossier_dir / "metrics.json").is_file() else {}
    cfg = _load_json(dossier_dir / "config_snapshot.json") if (dossier_dir / "config_snapshot.json").is_file() else {}
    gate = _load_json(dossier_dir / "gate_results.json") if (dossier_dir / "gate_results.json").is_file() else {}

    equity0 = float(curve["equity"].iloc[0])
    equity1 = float(curve["equity"].iloc[-1])
    net_return = float(equity1 / equity0 - 1.0) if equity0 != 0.0 else 0.0

    lag_bars = 1
    if isinstance(metrics, dict) and "lag_bars" in metrics:
        try:
            lag_bars = max(1, int(metrics["lag_bars"]))
        except Exception:  # noqa: BLE001
            lag_bars = 1

    policies_dir = policies_dir or default_policies_dir()
    rec = _recompute_cost_sensitivity(dossier_dir=dossier_dir, policies_dir=Path(policies_dir), cfg=cfg if isinstance(cfg, dict) else {}, lag_bars=lag_bars)

    gross_return = rec.gross_return
    cost_drag = (gross_return - net_return) if isinstance(gross_return, (int, float)) else None
    net_return_cost_x2 = rec.net_return_cost_x2
    delta_cost_x2 = (net_return_cost_x2 - net_return) if isinstance(net_return_cost_x2, (int, float)) else None

    # Returns decomposition: if recompute missing, fall back to totals in metrics.
    total_return_metric = metrics.get("total_return") if isinstance(metrics, dict) else None

    report: dict[str, Any] = {
        "schema_version": "attribution_report_v1",
        "run_id": str((dossier_dir / "dossier_manifest.json").is_file() and _load_json(dossier_dir / "dossier_manifest.json").get("run_id") or dossier_dir.name),
        "created_at": _source_date_now_iso(),
        "returns": {
            "net_return": net_return,
            "gross_return": gross_return,
            "cost_drag": cost_drag,
            "net_return_from_metrics": float(total_return_metric) if isinstance(total_return_metric, (int, float)) else None,
        },
        "contribution_by_symbol": _contribution_by_symbol(trades),
        "contribution_by_timebucket": _contribution_by_timebucket(trades, curve),
        "drawdown": _drawdown_diagnostics(curve),
        "trades": _trade_diagnostics(trades),
        "sensitivity": {
            "cost_x2_recompute": {
                "net_return_cost_x2": net_return_cost_x2,
                "delta_vs_net_return": delta_cost_x2,
                "notes": rec.notes,
            }
        },
        "gate_summary": {
            "overall_pass": bool(gate.get("overall_pass")) if isinstance(gate, dict) else None,
        },
        "evidence_refs": {
            "curve": "curve.csv",
            "trades": "trades.csv",
            "metrics": "metrics.json",
            "config_snapshot": "config_snapshot.json",
            "gate_results": "gate_results.json" if (dossier_dir / "gate_results.json").is_file() else None,
        },
    }

    # Deterministic fingerprint for traceability (not a governance input).
    report["report_fingerprint"] = __import__("hashlib").sha256(_canonical_json(report).encode("utf-8")).hexdigest()

    # Append-only writes: never overwrite existing artifacts.
    report_path = dossier_dir / "attribution_report.json"
    if not report_path.exists():
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        out_paths.append(report_path)

    # Deterministic markdown referencing JSON fields.
    rep_dir = dossier_dir / "reports" / "attribution"
    rep_dir.mkdir(parents=True, exist_ok=True)
    md_path = rep_dir / "report.md"
    if not md_path.exists():
        md_lines: list[str] = []
        md_lines.append("# Attribution Report (v1, deterministic)\n")
        md_lines.append("## Evidence (SSOT)\n")
        md_lines.append(f"- dossier_dir: `{dossier_dir.as_posix()}`\n")
        md_lines.append("- artifacts:\n")
        md_lines.append("  - `attribution_report.json`\n")
        md_lines.append("  - `curve.csv`\n")
        md_lines.append("  - `trades.csv`\n")
        md_lines.append("  - `metrics.json`\n")
        md_lines.append("  - `config_snapshot.json`\n")
        if (dossier_dir / "gate_results.json").is_file():
            md_lines.append("  - `gate_results.json`\n")
        md_lines.append("\n")
        md_lines.append("## Returns Decomposition (from attribution_report.json)\n")
        md_lines.append(f"- net_return: `{report['returns']['net_return']}`\n")
        md_lines.append(f"- gross_return: `{report['returns']['gross_return']}`\n")
        md_lines.append(f"- cost_drag: `{report['returns']['cost_drag']}`\n")
        md_lines.append("\n")
        md_lines.append("## Drawdown Diagnostics (from curve.csv -> attribution_report.json)\n")
        md_lines.append(f"- max_drawdown: `{report['drawdown']['max_drawdown']}`\n")
        md_lines.append(f"- dd_duration_bars: `{report['drawdown']['dd_duration_bars']}`\n")
        md_lines.append("\n")
        md_lines.append("## Trade Diagnostics (from trades.csv -> attribution_report.json)\n")
        md_lines.append(f"- trade_count: `{report['trades']['trade_count']}`\n")
        md_lines.append(f"- win_rate: `{report['trades']['win_rate']}`\n")
        md_lines.append(f"- profit_factor: `{report['trades']['profit_factor']}`\n")
        md_lines.append("\n")
        md_lines.append("## Sensitivity (from policy -> recompute)\n")
        md_lines.append(f"- cost_x2_recompute.net_return_cost_x2: `{report['sensitivity']['cost_x2_recompute']['net_return_cost_x2']}`\n")
        md_lines.append(f"- cost_x2_recompute.delta_vs_net_return: `{report['sensitivity']['cost_x2_recompute']['delta_vs_net_return']}`\n")
        md_lines.append(f"- cost_x2_recompute.notes: `{report['sensitivity']['cost_x2_recompute']['notes']}`\n")
        md_lines.append("\n")
        md_lines.append("## Notes\n")
        md_lines.append("- This report contains no free-form claims; all values reference dossier artifacts or deterministic recomputation.\n")

        md_path.write_text("".join(md_lines), encoding="utf-8")
        out_paths.append(md_path)

    # Add evidence refs for UI convenience if the md was created.
    return out_paths

