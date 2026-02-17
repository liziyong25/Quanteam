from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from quant_eam.gates.types import GateContext, GateEvidence, GateResult
from quant_eam.gates.util import extract_segment, extract_symbols, query_prices_df


@dataclass(frozen=True)
class _CurvePoint:
    dt: str  # YYYY-MM-DD
    equity: float


def _date_part(s: str) -> str:
    # Inputs are typically ISO timestamps from runner/backtest ("YYYY-MM-DDTHH:MM:SS")
    # or already a date ("YYYY-MM-DD"). Keep it deterministic and strict-ish.
    s = str(s).strip()
    if not s:
        return ""
    if "T" in s:
        s = s.split("T", 1)[0]
    return s


def _load_curve_points(curve_csv: Path) -> list[_CurvePoint]:
    pts: list[_CurvePoint] = []
    with curve_csv.open("r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            dt = _date_part(row.get("dt", ""))
            if not dt:
                continue
            try:
                eq = float(row.get("equity") or 0.0)
            except Exception:
                eq = 0.0
            pts.append(_CurvePoint(dt=dt, equity=eq))
    return pts


def _load_trades(trades_csv: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with trades_csv.open("r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            sym = str(row.get("symbol", "")).strip()
            if not sym:
                continue
            entry_dt = _date_part(row.get("entry_dt", ""))
            exit_dt = _date_part(row.get("exit_dt", ""))
            try:
                qty = float(row.get("qty") or 0.0)
            except Exception:
                qty = 0.0
            out.append(
                {
                    "symbol": sym,
                    "entry_dt": entry_dt,
                    "exit_dt": exit_dt,
                    "qty": float(qty),
                }
            )
    return out


def _load_turnover_series(turnover_csv: Path) -> tuple[list[str], list[float | None]]:
    dt_list: list[str] = []
    to_list: list[float | None] = []
    with turnover_csv.open("r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            dt = _date_part(row.get("dt", ""))
            if not dt:
                continue
            v_raw = row.get("turnover")
            if v_raw is None or str(v_raw).strip() == "":
                v = None
            else:
                try:
                    v = float(v_raw)
                except Exception:
                    v = None
            dt_list.append(dt)
            to_list.append(v)
    return dt_list, to_list


def _load_positions_count_series(positions_csv: Path) -> tuple[list[str], list[int]]:
    # positions.csv is long format: dt,symbol,qty,...
    counts: dict[str, int] = {}
    with positions_csv.open("r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            dt = _date_part(row.get("dt", ""))
            if not dt:
                continue
            try:
                qty = float(row.get("qty") or 0.0)
            except Exception:
                qty = 0.0
            if abs(qty) <= 0.0:
                continue
            counts[dt] = int(counts.get(dt, 0) + 1)
    dt_list = sorted(counts.keys())
    return dt_list, [int(counts[d]) for d in dt_list]


def _load_exposure(exposure_json: Path) -> dict[str, Any]:
    doc = json.loads(exposure_json.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError("exposure.json must be a JSON object")
    return doc


def _write_json_atomic(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / (path.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _policy_params(risk_policy: dict[str, Any]) -> dict[str, Any]:
    params = risk_policy.get("params")
    if not isinstance(params, dict):
        return {}
    return params


def _as_float(v: Any, default: float) -> float:
    try:
        return float(v)
    except Exception:
        return float(default)


def _as_int(v: Any, default: int) -> int:
    try:
        return int(v)
    except Exception:
        return int(default)


def _build_price_lookup(prices_df, col: str) -> dict[tuple[str, str], float]:
    out: dict[tuple[str, str], float] = {}
    for rec in prices_df.to_dict(orient="records"):
        sym = str(rec.get("symbol") or "").strip()
        dt = str(rec.get("dt") or "").strip()
        if not sym or not dt:
            continue
        try:
            v = float(rec.get(col) or 0.0)
        except Exception:
            v = 0.0
        out[(sym, dt)] = v
    return out


def _compute_risk_report(
    *,
    ctx: GateContext,
    curve_points: list[_CurvePoint],
    trades: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Returns: (risk_report_json_obj, derived_metrics_for_gate_results)

    Determinism:
    - dt ordering follows curve.csv ordering (append-only artifact produced by runner/backtest)
    - symbol ordering is sorted
    - close prices are re-queried via DataCatalog with as_of enforced (same root as other gates)
    """
    runspec = ctx.runspec
    seg = extract_segment(runspec, "test")
    if seg is None:
        raise ValueError("missing runspec.segments.test.{start,end,as_of}")

    snapshot_id = str(runspec.get("data_snapshot_id", "")).strip()
    if not snapshot_id:
        raise ValueError("missing runspec.data_snapshot_id")

    symbols = extract_symbols(runspec)
    if not symbols:
        # Fallback: infer from trades, else empty.
        symbols = sorted({str(t.get("symbol") or "") for t in trades if str(t.get("symbol") or "").strip()})

    data_root_raw = (ctx.config_snapshot.get("env", {}) or {}).get("EAM_DATA_ROOT")
    data_root = Path(str(data_root_raw)) if isinstance(data_root_raw, str) and str(data_root_raw).strip() else None

    prices_df, _stats = query_prices_df(data_root=data_root, snapshot_id=snapshot_id, symbols=symbols, seg=seg)
    close_lut = _build_price_lookup(prices_df, "close")

    # Turnover should be computed on traded notional at execution fill price (not close),
    # otherwise a buy-at-open order can exceed 1.0 turnover due to open->close drift.
    ep = ctx.execution_policy
    ep_params = ep.get("params") if isinstance(ep, dict) else {}
    order_timing = str(ep_params.get("order_timing") or "").strip() if isinstance(ep_params, dict) else ""
    fill_price = ep_params.get("fill_price") if isinstance(ep_params, dict) else None
    fill_price_s = str(fill_price).strip() if isinstance(fill_price, str) else ""
    if not fill_price_s:
        fill_price_s = "open" if order_timing == "next_open" else "close"
    if fill_price_s not in ("open", "close"):
        fill_price_s = "close"
    fill_lut = _build_price_lookup(prices_df, fill_price_s)

    # Build per-dt events from trades: entry sets qty, exit sets qty=0.
    events: dict[str, list[tuple[int, str, float]]] = {}
    for tr in trades:
        sym = str(tr.get("symbol") or "").strip()
        if not sym:
            continue
        entry_dt = str(tr.get("entry_dt") or "").strip()
        exit_dt = str(tr.get("exit_dt") or "").strip()
        qty = float(tr.get("qty") or 0.0)
        if entry_dt:
            events.setdefault(entry_dt, []).append((0, sym, qty))
        if exit_dt:
            events.setdefault(exit_dt, []).append((1, sym, 0.0))

    symbols_sorted = sorted(set(symbols))
    qty_by_sym: dict[str, float] = {s: 0.0 for s in symbols_sorted}

    # Series (aligned to curve dt list)
    dt_list: list[str] = [p.dt for p in curve_points]
    equity_list: list[float] = [float(p.equity) for p in curve_points]

    leverage_series: list[float | None] = []
    positions_series: list[int] = []
    turnover_series: list[float | None] = []
    short_exposure_days = 0

    prev_equity: float | None = None

    for i, dt in enumerate(dt_list):
        # Apply events for dt in deterministic order: entry first, then exit; within kind sort by symbol.
        evs = sorted(events.get(dt, []), key=lambda x: (x[0], x[1]))
        prev_qty_snapshot = dict(qty_by_sym)
        for kind, sym, v in evs:
            if sym not in qty_by_sym:
                qty_by_sym[sym] = 0.0
            if kind == 0:
                qty_by_sym[sym] = float(v)
            else:
                qty_by_sym[sym] = 0.0

        # Turnover: sum(|delta_qty| * fill_price) / prev_equity (fallback: current equity for first bar).
        trade_value = 0.0
        for sym, q_new in qty_by_sym.items():
            q_old = float(prev_qty_snapshot.get(sym, 0.0))
            dq = float(q_new) - q_old
            if dq == 0.0:
                continue
            px = fill_lut.get((sym, dt))
            if px is None:
                continue
            trade_value += abs(dq) * float(px)
        denom = prev_equity if (prev_equity is not None and prev_equity > 0.0) else float(equity_list[i] or 0.0)
        turnover = (trade_value / denom) if denom and denom > 0.0 else None
        turnover_series.append(turnover)

        # Positions/leverage (end-of-bar, marked on close).
        positions = 0
        gross = 0.0
        net = 0.0
        has_short = False
        for sym, q in qty_by_sym.items():
            if abs(float(q)) > 0.0:
                positions += 1
            if float(q) < 0.0:
                has_short = True
            px = close_lut.get((sym, dt))
            if px is None:
                continue
            pos_val = float(q) * float(px)
            net += pos_val
            gross += abs(pos_val)
        positions_series.append(int(positions))
        if has_short:
            short_exposure_days += 1

        eq = float(equity_list[i] or 0.0)
        # Define leverage in v1 as gross exposure divided by (gross + non-negative cash).
        # This avoids spurious >1.0 leverage from transaction costs pushing MTM cash slightly negative
        # in a no-margin engine (buy-and-hold with fees would otherwise exceed max_leverage=1.0).
        cash_mtm = eq - net
        denom2 = gross + max(cash_mtm, 0.0)
        leverage = (gross / denom2) if denom2 > 0.0 else None
        leverage_series.append(leverage)

        prev_equity = eq

    # Summaries
    max_leverage_obs = max([x for x in leverage_series if isinstance(x, (int, float))], default=0.0)
    max_positions_obs = max(positions_series, default=0)
    max_turnover_obs = max([x for x in turnover_series if isinstance(x, (int, float))], default=0.0)

    rp = ctx.risk_policy or {}
    params = _policy_params(rp)
    max_leverage = _as_float(params.get("max_leverage"), 1.0)
    max_positions = _as_int(params.get("max_positions"), 20)
    max_turnover = _as_float(params.get("max_turnover"), 1.0)
    max_drawdown = params.get("max_drawdown")
    max_drawdown_f = _as_float(max_drawdown, 0.0) if max_drawdown is not None else None

    # Count violations by dt.
    eps = 1e-12
    lev_viol = sum(1 for x in leverage_series if isinstance(x, (int, float)) and x > max_leverage + eps)
    pos_viol = sum(1 for x in positions_series if int(x) > max_positions)
    to_viol = sum(1 for x in turnover_series if isinstance(x, (int, float)) and x > max_turnover + eps)

    dd_obs = float(ctx.metrics.get("max_drawdown") or 0.0) if isinstance(ctx.metrics, dict) else 0.0
    dd_viol = 0
    if max_drawdown_f is not None:
        # max_drawdown is negative (e.g. -0.23). Policy is typically positive threshold like 0.2.
        # Violation when abs(drawdown) > threshold.
        dd_viol = 1 if abs(dd_obs) > float(max_drawdown_f) + eps else 0

    risk_report: dict[str, Any] = {
        "schema_version": "risk_report_v1",
        "run_id": str(ctx.dossier_manifest.get("run_id") or ""),
        "risk_policy_id": str(rp.get("policy_id") or ""),
        "policy_params": {
            "max_leverage": max_leverage,
            "max_positions": max_positions,
            "max_turnover": max_turnover,
            "max_drawdown": max_drawdown_f,
        },
        "computed_from": {
            "curve": "curve.csv",
            "trades": "trades.csv",
            "snapshot_id": snapshot_id,
            "segment": {"start": seg.start, "end": seg.end, "as_of": seg.as_of},
        },
        "series": {
            "dt": dt_list,
            "leverage": leverage_series,
            "positions_count": positions_series,
            "turnover": turnover_series,
        },
        "max_observed": {
            "max_leverage_observed": float(max_leverage_obs),
            "max_positions_observed": int(max_positions_obs),
            "max_turnover_observed": float(max_turnover_obs),
            "max_drawdown_observed": float(dd_obs),
            "short_exposure_days": int(short_exposure_days),
        },
        "violation_count_by_rule": {
            "max_leverage": int(lev_viol),
            "max_positions": int(pos_viol),
            "max_turnover": int(to_viol),
            "max_drawdown": int(dd_viol),
            "no_short": int(short_exposure_days),
        },
        "extensions": {},
    }

    derived_metrics = {
        "risk_policy_id": risk_report["risk_policy_id"],
        "max_leverage_limit": max_leverage,
        "max_positions_limit": max_positions,
        "max_turnover_limit": max_turnover,
        "max_leverage_observed": float(max_leverage_obs),
        "max_positions_observed": int(max_positions_obs),
        "max_turnover_observed": float(max_turnover_obs),
        "short_exposure_days": int(short_exposure_days),
        "violations": dict(risk_report["violation_count_by_rule"]),
    }
    if max_drawdown_f is not None:
        derived_metrics["max_drawdown_limit"] = float(max_drawdown_f)
        derived_metrics["max_drawdown_observed"] = float(dd_obs)

    return risk_report, derived_metrics


def run_risk_policy_compliance_v1(ctx: GateContext, params: dict[str, Any] | None) -> GateResult:
    _ = params or {}
    if ctx.risk_policy is None:
        return GateResult(
            gate_id="risk_policy_compliance_v1",
            gate_version="v1",
            passed=False,
            status="fail",
            metrics={"reason": "missing risk_policy (bundle missing risk_policy_id or policy file not loaded)"},
            evidence=GateEvidence(artifacts=["config_snapshot.json"]),
        )

    # Phase-27: risk gates must use backtest-produced intermediate evidence to avoid drift:
    # positions.csv / turnover.csv / exposure.json must exist and be referenced by risk_report.json.
    pos_p = ctx.dossier_dir / "positions.csv"
    to_p = ctx.dossier_dir / "turnover.csv"
    ex_p = ctx.dossier_dir / "exposure.json"
    missing: list[str] = []
    for p, name in ((pos_p, "positions.csv"), (to_p, "turnover.csv"), (ex_p, "exposure.json")):
        if not p.is_file():
            missing.append(name)
    if missing:
        return GateResult(
            gate_id="risk_policy_compliance_v1",
            gate_version="v1",
            passed=False,
            status="fail",
            metrics={"error": "missing risk evidence artifacts", "missing_artifacts": missing},
            evidence=GateEvidence(artifacts=["dossier_manifest.json", "config_snapshot.json"]),
        )

    try:
        exposure = _load_exposure(ex_p)
        dt_turnover, turnover_series = _load_turnover_series(to_p)
        dt_pos, positions_series = _load_positions_count_series(pos_p)
    except Exception as e:  # noqa: BLE001
        return GateResult(
            gate_id="risk_policy_compliance_v1",
            gate_version="v1",
            passed=False,
            status="fail",
            metrics={"error": f"risk evidence parse error: {type(e).__name__}: {e}"},
            evidence=GateEvidence(artifacts=["positions.csv", "turnover.csv", "exposure.json"]),
        )

    # Canonical dt list: use turnover series (one row per dt), fallback to positions.
    dt_list = dt_turnover or dt_pos

    rp = ctx.risk_policy or {}
    params2 = _policy_params(rp)
    max_leverage = _as_float(params2.get("max_leverage"), 1.0)
    max_positions = _as_int(params2.get("max_positions"), 20)
    max_turnover = _as_float(params2.get("max_turnover"), 1.0)
    max_drawdown = params2.get("max_drawdown")
    max_drawdown_f = _as_float(max_drawdown, 0.0) if max_drawdown is not None else None

    max_obs = exposure.get("max_observed") if isinstance(exposure.get("max_observed"), dict) else {}
    max_leverage_obs = _as_float(max_obs.get("max_leverage_observed"), 0.0)
    max_positions_obs = _as_int(max_obs.get("max_positions_observed"), 0)
    max_turnover_obs = _as_float(max_obs.get("max_turnover_observed"), 0.0)

    # Violation counts: v1 uses series where available; leverage uses max-only evidence.
    eps = 1e-12
    lev_viol = 1 if max_leverage_obs > max_leverage + eps else 0
    pos_viol = sum(1 for x in positions_series if int(x) > max_positions) if positions_series else (1 if max_positions_obs > max_positions else 0)
    to_viol = sum(1 for x in turnover_series if isinstance(x, (int, float)) and float(x) > max_turnover + eps) if turnover_series else (1 if max_turnover_obs > max_turnover else 0)

    dd_obs = float(ctx.metrics.get("max_drawdown") or 0.0) if isinstance(ctx.metrics, dict) else 0.0
    dd_viol = 0
    if max_drawdown_f is not None:
        dd_viol = 1 if abs(dd_obs) > float(max_drawdown_f) + eps else 0

    seg = extract_segment(ctx.runspec, "test")
    snapshot_id = str(ctx.runspec.get("data_snapshot_id") or "").strip()
    rr: dict[str, Any] = {
        "schema_version": "risk_report_v1",
        "run_id": str(ctx.dossier_manifest.get("run_id") or ""),
        "risk_policy_id": str(rp.get("policy_id") or ""),
        "policy_params": {
            "max_leverage": float(max_leverage),
            "max_positions": int(max_positions),
            "max_turnover": float(max_turnover),
            "max_drawdown": float(max_drawdown_f) if max_drawdown_f is not None else None,
        },
        "computed_from": {
            "positions": "positions.csv",
            "turnover": "turnover.csv",
            "exposure": "exposure.json",
            "snapshot_id": snapshot_id,
            "segment": {"start": seg.start, "end": seg.end, "as_of": seg.as_of} if seg is not None else None,
        },
        "series": {
            "dt": dt_list,
            "positions_count": positions_series,
            "turnover": turnover_series,
        },
        "max_observed": {
            "max_leverage_observed": float(max_leverage_obs),
            "max_positions_observed": int(max_positions_obs),
            "max_turnover_observed": float(max_turnover_obs),
            "max_drawdown_observed": float(dd_obs),
        },
        "violation_count_by_rule": {
            "max_leverage": int(lev_viol),
            "max_positions": int(pos_viol),
            "max_turnover": int(to_viol),
            "max_drawdown": int(dd_viol),
        },
        "extensions": {
            "evidence_refs": {
                "positions_csv": "positions.csv",
                "turnover_csv": "turnover.csv",
                "exposure_json": "exposure.json",
            }
        },
    }

    derived = {
        "risk_policy_id": rr["risk_policy_id"],
        "max_leverage_limit": float(max_leverage),
        "max_positions_limit": int(max_positions),
        "max_turnover_limit": float(max_turnover),
        "max_leverage_observed": float(max_leverage_obs),
        "max_positions_observed": int(max_positions_obs),
        "max_turnover_observed": float(max_turnover_obs),
        "violations": dict(rr["violation_count_by_rule"]),
    }
    if max_drawdown_f is not None:
        derived["max_drawdown_limit"] = float(max_drawdown_f)
        derived["max_drawdown_observed"] = float(dd_obs)

    # Write evidence (append-only: new file).
    out_path = ctx.dossier_dir / "risk_report.json"
    if not out_path.is_file():
        try:
            _write_json_atomic(out_path, rr)
        except Exception:
            # Do not fail gate if writing evidence fails, but report it.
            derived = dict(derived)
            derived["warning"] = "failed to write risk_report.json"
    violations = rr.get("violation_count_by_rule") if isinstance(rr.get("violation_count_by_rule"), dict) else {}
    fail = False
    for k in ("max_leverage", "max_positions", "max_turnover", "max_drawdown"):
        try:
            if int(violations.get(k) or 0) > 0:
                fail = True
        except Exception:
            continue

    # Also enforce allow_short from execution_policy even if risk_policy has no explicit rule.
    allow_short = True
    ep_params2 = ctx.execution_policy.get("params") if isinstance(ctx.execution_policy, dict) else {}
    if isinstance(ep_params2, dict) and "allow_short" in ep_params2:
        allow_short = bool(ep_params2.get("allow_short"))
    if not allow_short:
        # v1 engine does not produce short exposure series; treat any negative-qty in positions.csv as violation.
        try:
            has_short = False
            with pos_p.open("r", newline="", encoding="utf-8") as f:
                r = csv.DictReader(f)
                for row in r:
                    try:
                        qty = float(row.get("qty") or 0.0)
                    except Exception:
                        qty = 0.0
                    if qty < 0.0:
                        has_short = True
                        break
            if has_short:
                fail = True
        except Exception:
            # If we cannot parse, mark invalid via error so runner exits non-zero.
            return GateResult(
                gate_id="risk_policy_compliance_v1",
                gate_version="v1",
                passed=False,
                status="fail",
                metrics={"error": "failed to parse positions.csv for short check"},
                evidence=GateEvidence(artifacts=["positions.csv", "config_snapshot.json"]),
            )

    passed = not fail
    thresholds = {
        "max_leverage": float(max_leverage),
        "max_positions": int(max_positions),
        "max_turnover": float(max_turnover),
    }
    if max_drawdown_f is not None:
        thresholds["max_drawdown"] = float(max_drawdown_f)
    thresholds["allow_short"] = bool(allow_short)

    return GateResult(
        gate_id="risk_policy_compliance_v1",
        gate_version="v1",
        passed=passed,
        status="pass" if passed else "fail",
        metrics=derived,
        thresholds=thresholds,
        evidence=GateEvidence(
            artifacts=["risk_report.json", "positions.csv", "turnover.csv", "exposure.json", "config_snapshot.json"],
            notes="Phase-27: computes policy compliance from backtest-produced risk evidence artifacts; writes risk_report.json evidence",
        ),
    )
