from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

import pandas as pd


class SignalCompileInvalid(ValueError):
    pass


FORBIDDEN_INLINE_POLICY_KEYS = {
    # cost policy
    "commission_bps",
    "slippage_bps",
    "tax_bps",
    "min_fee",
    "currency",
    # asof latency policy
    "default_latency_seconds",
    "bar_close_to_signal_seconds",
    "trade_lag_bars_default",
    "asof_rule",
    # risk policy
    "max_leverage",
    "max_positions",
    "max_drawdown",
}

FORBIDDEN_SCRIPT_TOKENS = ("code", "python", "script", "bash", "shell")


def _canon_json(x: Any) -> str:
    return json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def dsl_fingerprint(signal_dsl: dict[str, Any]) -> str:
    return hashlib.sha256(_canon_json(signal_dsl).encode("utf-8")).hexdigest()


def _scan_for_forbidden_tokens(obj: Any, path: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            ks = str(k)
            kl = ks.lower()
            p2 = f"{path}/{ks}" if path else f"/{ks}"
            if kl in FORBIDDEN_INLINE_POLICY_KEYS:
                findings.append(f"{p2}: forbidden inline policy key: {ks}")
            toks = [t for t in re.split(r"[^a-z0-9]+", kl) if t]
            if any(tok in toks for tok in FORBIDDEN_SCRIPT_TOKENS):
                findings.append(f"{p2}: forbidden script token in key: {ks}")
            findings.extend(_scan_for_forbidden_tokens(v, p2))
        return findings
    if isinstance(obj, list):
        for i, v in enumerate(obj):
            findings.extend(_scan_for_forbidden_tokens(v, f"{path}/{i}" if path else f"/{i}"))
        return findings
    if isinstance(obj, str):
        vl = obj.lower()
        if "holdout_curve" in vl or "holdout_trades" in vl:
            findings.append(f"{path or '/'}: forbidden holdout detail reference in string value")
    return findings


def _as_series(x: Any, index: pd.Index) -> pd.Series:
    if isinstance(x, pd.Series):
        return x
    # scalar -> broadcast
    return pd.Series([x] * len(index), index=index)


def _sma(s: pd.Series, n: int) -> pd.Series:
    n = int(n)
    if n <= 0:
        raise SignalCompileInvalid("sma window must be >= 1")
    return s.rolling(window=n, min_periods=n).mean()


def _rsi(close: pd.Series, n: int) -> pd.Series:
    n = int(n)
    if n <= 0:
        raise SignalCompileInvalid("rsi period must be >= 1")
    delta = close.diff()
    gain = delta.where(delta > 0.0, 0.0)
    loss = (-delta).where(delta < 0.0, 0.0)
    # Wilder's smoothing via EMA with alpha=1/n (adjust=False), deterministic and lookahead-safe.
    avg_gain = gain.ewm(alpha=1.0 / float(n), adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / float(n), adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, pd.NA)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    # Ensure we return a numeric float series (missing values -> NaN) for stability.
    return pd.to_numeric(rsi, errors="coerce").astype(float)


def _cross_above(a: pd.Series, b: pd.Series) -> pd.Series:
    prev = (a.shift(1) <= b.shift(1)).fillna(False)
    now = (a > b).fillna(False)
    return (prev & now).astype(bool)


def _cross_below(a: pd.Series, b: pd.Series) -> pd.Series:
    prev = (a.shift(1) >= b.shift(1)).fillna(False)
    now = (a < b).fillna(False)
    return (prev & now).astype(bool)


@dataclass(frozen=True)
class SignalCompilerResult:
    frame: pd.DataFrame
    lag_bars_used: int
    dsl_fingerprint: str
    signals_fingerprint: str
    intermediate_cols: list[str]


def compile_signal_dsl_v1(
    *,
    prices: pd.DataFrame,
    signal_dsl: dict[str, Any],
    lag_bars: int,
) -> SignalCompilerResult:
    """Compile `signal_dsl_v1` into concrete, lagged signals and intermediates.

    Output columns include:
    - dt, symbol
    - entry_raw, exit_raw
    - entry_lagged, exit_lagged (shifted by lag_bars, must be >= 1)
    - intermediates for named expressions (e.g. sma_fast, sma_slow, rsi)
    """
    if not isinstance(signal_dsl, dict):
        raise SignalCompileInvalid("signal_dsl must be an object")
    if int(lag_bars) < 1:
        raise SignalCompileInvalid("lag_bars must be >= 1 (no-lookahead default)")

    findings = _scan_for_forbidden_tokens(signal_dsl)
    if findings:
        raise SignalCompileInvalid("signal_dsl violates governance red lines: " + "; ".join(findings[:5]))

    needed = {"dt", "symbol", "close"}
    miss = needed - set(prices.columns)
    if miss:
        raise SignalCompileInvalid(f"prices missing required columns: {sorted(miss)}")

    df = prices.copy()
    df["symbol"] = df["symbol"].astype(str)
    # Keep dt as string for stability in CSV outputs; parse for sorting only.
    dt_parsed = pd.to_datetime(df["dt"], errors="coerce")
    if dt_parsed.isna().any():
        raise SignalCompileInvalid("prices.dt contains unparseable values")
    df["_dt"] = dt_parsed
    df = df.sort_values(["symbol", "_dt"], kind="mergesort").reset_index(drop=True)

    sigs = signal_dsl.get("signals") if isinstance(signal_dsl.get("signals"), dict) else {}
    entry_key = str(sigs.get("entry") or "")
    exit_key = str(sigs.get("exit") or "")
    exprs = signal_dsl.get("expressions") if isinstance(signal_dsl.get("expressions"), dict) else {}
    params = signal_dsl.get("params") if isinstance(signal_dsl.get("params"), dict) else {}
    if not entry_key or entry_key not in exprs:
        raise SignalCompileInvalid("signal_dsl.signals.entry must reference an expressions key")
    if not exit_key or exit_key not in exprs:
        raise SignalCompileInvalid("signal_dsl.signals.exit must reference an expressions key")

    fp = dsl_fingerprint(signal_dsl)

    # Evaluate per-symbol to avoid cross-symbol leakage in rolling indicators.
    out_parts: list[pd.DataFrame] = []
    intermediate_cols: set[str] = set()
    for sym, g in df.groupby("symbol", sort=True):
        idx = g.index
        cache: dict[str, pd.Series] = {}

        def eval_expr_by_name(name: str) -> pd.Series:
            if name in cache:
                return cache[name]
            ast = exprs.get(name)
            if not isinstance(ast, dict):
                raise SignalCompileInvalid(f"expression not found or invalid: {name!r}")
            s = eval_ast(ast)
            cache[name] = s
            return s

        def eval_ast(ast: dict[str, Any]) -> pd.Series:
            t = ast.get("type")
            if t == "const":
                return _as_series(ast.get("value"), idx)
            if t == "param":
                pid = str(ast.get("param_id") or "")
                return _as_series(params.get(pid), idx)
            if t == "var":
                vid = str(ast.get("var_id") or "")
                if vid in g.columns:
                    return g[vid]
                if vid in exprs:
                    return eval_expr_by_name(vid)
                raise SignalCompileInvalid(f"unknown var_id: {vid!r}")
            if t == "op":
                op = str(ast.get("op") or "")
                args = ast.get("args") if isinstance(ast.get("args"), list) else []
                a = [eval_ast(x) for x in args if isinstance(x, dict)]

                # Boolean ops
                if op == "and":
                    out = pd.Series([True] * len(idx), index=idx)
                    for s in a:
                        out = out & s.astype(bool)
                    return out.astype(bool)
                if op == "or":
                    out = pd.Series([False] * len(idx), index=idx)
                    for s in a:
                        out = out | s.astype(bool)
                    return out.astype(bool)
                if op == "not":
                    return (~a[0].astype(bool)).astype(bool) if a else pd.Series([False] * len(idx), index=idx)

                # Comparisons
                if op == "eq":
                    return (a[0] == a[1]).astype(bool)
                if op == "gt":
                    return (a[0].astype(float) > a[1].astype(float)).astype(bool)
                if op == "lt":
                    return (a[0].astype(float) < a[1].astype(float)).astype(bool)
                if op == "ge":
                    return (a[0].astype(float) >= a[1].astype(float)).astype(bool)
                if op == "le":
                    return (a[0].astype(float) <= a[1].astype(float)).astype(bool)

                # Arithmetic
                if op == "add":
                    out = pd.Series([0.0] * len(idx), index=idx)
                    for s in a:
                        out = out + s.astype(float)
                    return out.astype(float)
                if op == "sub":
                    return (a[0].astype(float) - a[1].astype(float)).astype(float)
                if op == "mul":
                    out = pd.Series([1.0] * len(idx), index=idx)
                    for s in a:
                        out = out * s.astype(float)
                    return out.astype(float)
                if op == "div":
                    denom = a[1].astype(float).replace(0.0, pd.NA)
                    return (a[0].astype(float) / denom).astype(float)

                # Indicators and signal ops
                if op == "sma":
                    n = int(float(a[1].iloc[0])) if len(a) >= 2 else 0
                    return _sma(a[0].astype(float), n)
                if op == "rsi":
                    n = int(float(a[1].iloc[0])) if len(a) >= 2 else 0
                    return _rsi(a[0].astype(float), n)
                if op == "cross_above":
                    return _cross_above(a[0].astype(float), a[1].astype(float))
                if op == "cross_below":
                    return _cross_below(a[0].astype(float), a[1].astype(float))

                raise SignalCompileInvalid(f"unsupported op: {op!r}")
            raise SignalCompileInvalid(f"unsupported ast type: {t!r}")

        entry_raw = eval_expr_by_name(entry_key).astype(bool).fillna(False)
        exit_raw = eval_expr_by_name(exit_key).astype(bool).fillna(False)
        entry_lagged = entry_raw.shift(int(lag_bars)).fillna(False).astype(bool)
        exit_lagged = exit_raw.shift(int(lag_bars)).fillna(False).astype(bool)

        # Long-only position derived from lagged signals (execution-safe).
        # Deterministic rule when both happen same bar: exit first, then entry.
        pos = []
        in_pos = False
        for en, ex in zip(entry_lagged.tolist(), exit_lagged.tolist()):
            if bool(ex):
                in_pos = False
            if bool(en):
                in_pos = True
            pos.append(1 if in_pos else 0)

        # Expose named intermediates: any expression other than entry/exit that yields a numeric series.
        cols: dict[str, pd.Series] = {}
        for name in sorted(exprs.keys()):
            if name in (entry_key, exit_key):
                continue
            try:
                s = eval_expr_by_name(name)
            except Exception:
                continue
            # Keep only 1D series aligned to index; cast bools to int? keep as float where possible.
            if s.dtype == bool:
                cols[name] = s.astype(bool)
            else:
                try:
                    cols[name] = s.astype(float)
                except Exception:
                    # Skip non-numeric intermediates in v1.
                    continue
            intermediate_cols.add(name)

        part = pd.DataFrame({"dt": g["dt"], "symbol": g["symbol"]}, index=idx)
        for k, s in cols.items():
            part[k] = s
        part["entry_raw"] = entry_raw
        part["exit_raw"] = exit_raw
        part["entry_lagged"] = entry_lagged
        part["exit_lagged"] = exit_lagged
        part["position"] = pd.Series(pos, index=idx).astype(int)
        out_parts.append(part.reset_index(drop=True))

    out = pd.concat(out_parts, axis=0, ignore_index=True)
    out = out.sort_values(["symbol", "dt"], kind="mergesort").reset_index(drop=True)

    # signals_fingerprint: canonical hash of (symbol,dt,entry_lagged,exit_lagged)
    sig_rows = out[["symbol", "dt", "entry_lagged", "exit_lagged"]].copy()
    sig_rows["entry_lagged"] = sig_rows["entry_lagged"].astype(int)
    sig_rows["exit_lagged"] = sig_rows["exit_lagged"].astype(int)
    sig_fp = hashlib.sha256(_canon_json(sig_rows.to_dict(orient="records")).encode("utf-8")).hexdigest()

    return SignalCompilerResult(
        frame=out,
        lag_bars_used=int(lag_bars),
        dsl_fingerprint=fp,
        signals_fingerprint=sig_fp,
        intermediate_cols=sorted(intermediate_cols),
    )
