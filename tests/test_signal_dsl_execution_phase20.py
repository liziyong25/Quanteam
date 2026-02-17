from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

import pytest

from quant_eam.backtest.signal_compiler import SignalCompileInvalid, compile_signal_dsl_v1
from quant_eam.backtest.vectorbt_adapter_mvp import run_adapter
from quant_eam.agents.harness import run_agent
from quant_eam.data_lake.demo_ingest import main as demo_ingest_main
from quant_eam.datacatalog.catalog import DataCatalog
from quant_eam.diagnostics.calc_trace_preview import run_calc_trace_preview
from quant_eam.policies.load import find_repo_root
from quant_eam.policies.resolve import load_policy_bundle
from quant_eam.runner.run import _load_policy_docs_from_bundle, _trade_lag_bars_default


def _ma_crossover_dsl(*, fast: int = 2, slow: int = 3) -> dict:
    return {
        "dsl_version": "signal_dsl_v1",
        "signals": {"entry": "entry", "exit": "exit"},
        "expressions": {
            "sma_fast": {"type": "op", "op": "sma", "args": [{"type": "var", "var_id": "close"}, {"type": "param", "param_id": "fast"}]},
            "sma_slow": {"type": "op", "op": "sma", "args": [{"type": "var", "var_id": "close"}, {"type": "param", "param_id": "slow"}]},
            "entry": {"type": "op", "op": "cross_above", "args": [{"type": "var", "var_id": "sma_fast"}, {"type": "var", "var_id": "sma_slow"}]},
            "exit": {"type": "op", "op": "cross_below", "args": [{"type": "var", "var_id": "sma_fast"}, {"type": "var", "var_id": "sma_slow"}]},
        },
        "params": {"fast": fast, "slow": slow},
        "execution": {"order_timing": "next_open", "cost_model": {"ref_policy": True}},
        "extensions": {"engine_contract": "vectorbt_signal_v1", "strategy_id": "ma_crossover_test", "policy_bundle_path": "policies/policy_bundle_v1.yaml"},
    }


def _rsi_mr_dsl(*, n: int = 5, entry_th: float = 30.0, exit_th: float = 70.0) -> dict:
    return {
        "dsl_version": "signal_dsl_v1",
        "signals": {"entry": "entry", "exit": "exit"},
        "expressions": {
            "rsi": {"type": "op", "op": "rsi", "args": [{"type": "var", "var_id": "close"}, {"type": "param", "param_id": "n"}]},
            "entry": {"type": "op", "op": "lt", "args": [{"type": "var", "var_id": "rsi"}, {"type": "param", "param_id": "entry_th"}]},
            "exit": {"type": "op", "op": "gt", "args": [{"type": "var", "var_id": "rsi"}, {"type": "param", "param_id": "exit_th"}]},
        },
        "params": {"n": n, "entry_th": entry_th, "exit_th": exit_th},
        "execution": {"order_timing": "next_open", "cost_model": {"ref_policy": True}},
        "extensions": {"engine_contract": "vectorbt_signal_v1", "strategy_id": "rsi_mr_test", "policy_bundle_path": "policies/policy_bundle_v1.yaml"},
    }


def test_phase20_signal_compiler_ma_crossover_and_lag() -> None:
    # close sequence crafted to cross above after both SMAs are defined.
    df = pd.DataFrame(
        {
            "dt": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-06"],
            "symbol": ["AAA"] * 6,
            "open": [1, 1, 1, 2, 3, 4],
            "close": [1, 1, 1, 2, 3, 4],
            "available_at": ["2024-01-01T16:00:00+08:00"] * 6,
        }
    )
    dsl = _ma_crossover_dsl(fast=2, slow=3)
    comp = compile_signal_dsl_v1(prices=df, signal_dsl=dsl, lag_bars=1)
    out = comp.frame
    assert "sma_fast" in out.columns
    assert "sma_slow" in out.columns
    assert "position" in out.columns
    # Entry raw should trigger on 2024-01-04 for this sequence; lag shifts to 2024-01-05.
    row_0404 = out[(out["symbol"] == "AAA") & (out["dt"] == "2024-01-04")].iloc[0]
    row_0405 = out[(out["symbol"] == "AAA") & (out["dt"] == "2024-01-05")].iloc[0]
    assert bool(row_0404["entry_raw"]) is True
    assert bool(row_0404["entry_lagged"]) is False
    assert bool(row_0405["entry_lagged"]) is True


def test_phase20_signal_compiler_rsi_outputs_and_threshold_logic() -> None:
    df = pd.DataFrame(
        {
            "dt": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-06"],
            "symbol": ["AAA"] * 6,
            "open": [10, 9, 8, 9, 10, 11],
            "close": [10, 9, 8, 9, 10, 11],
            "available_at": ["2024-01-01T16:00:00+08:00"] * 6,
        }
    )
    dsl = _rsi_mr_dsl(n=3, entry_th=40, exit_th=60)
    comp = compile_signal_dsl_v1(prices=df, signal_dsl=dsl, lag_bars=1)
    out = comp.frame
    assert "rsi" in out.columns
    assert "position" in out.columns
    # RSI must be in [0,100] when defined; entry/exit are thresholded rsi.
    rsi_vals = out["rsi"].dropna().astype(float)
    assert (rsi_vals >= 0.0).all()
    assert (rsi_vals <= 100.0).all()
    assert set(out["entry_raw"].dropna().unique().tolist()) <= {True, False}
    assert set(out["exit_raw"].dropna().unique().tolist()) <= {True, False}


def test_phase20_lag_must_be_ge_1() -> None:
    df = pd.DataFrame(
        {
            "dt": ["2024-01-01", "2024-01-02"],
            "symbol": ["AAA", "AAA"],
            "open": [1, 1],
            "close": [1, 2],
            "available_at": ["2024-01-01T16:00:00+08:00"] * 2,
        }
    )
    with pytest.raises(SignalCompileInvalid, match="lag_bars must be >= 1"):
        _ = compile_signal_dsl_v1(prices=df, signal_dsl=_ma_crossover_dsl(), lag_bars=0)


def test_phase20_trace_preview_and_backtest_share_signals_fingerprint(tmp_path: Path, monkeypatch) -> None:
    data_root = tmp_path / "data"
    data_root.mkdir()
    snapshot_id = "snap_phase20_001"
    assert demo_ingest_main(["--root", str(data_root), "--snapshot-id", snapshot_id]) == 0

    # Build DSL + minimal trace plan inputs.
    dsl = _ma_crossover_dsl(fast=2, slow=3)
    p_dsl = tmp_path / "signal_dsl.json"
    p_vars = tmp_path / "variable_dictionary.json"
    p_plan = tmp_path / "calc_trace_plan.json"
    p_dsl.write_text(json.dumps(dsl, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    p_vars.write_text(
        json.dumps(
            {
                "schema_version": "variable_dictionary_v1",
                "variables": [
                    {"var_id": "close", "kind": "field", "dtype": "float", "source": {"dataset_id": "ohlcv_1d", "field": "close"}, "alignment": {"lag_bars": 0}, "missing_policy": {"mode": "drop"}},
                    {"var_id": "available_at", "kind": "field", "dtype": "datetime", "source": {"dataset_id": "ohlcv_1d", "field": "available_at"}, "alignment": {"lag_bars": 0}, "missing_policy": {"mode": "drop"}},
                ],
                "extensions": {"policy_bundle_path": "policies/policy_bundle_v1.yaml"},
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    p_plan.write_text(
        json.dumps(
            {"schema_version": "calc_trace_plan_v1", "samples": [{"symbols": ["AAA"], "start": "2024-01-01", "end": "2024-01-10", "max_rows": 30}], "steps": [{"step_id": "t", "title": "t", "type": "table", "render": {"mode": "table"}, "variables": ["close"]}]},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    out_dir = tmp_path / "trace"
    out_csv, meta_path, meta = run_calc_trace_preview(
        out_dir=out_dir,
        snapshot_id=snapshot_id,
        as_of="2024-01-11T00:00:00+08:00",
        start="2024-01-01",
        end="2024-01-10",
        symbols=["AAA"],
        signal_dsl_path=p_dsl,
        variable_dictionary_path=p_vars,
        calc_trace_plan_path=p_plan,
        data_root=data_root,
    )
    assert out_csv.is_file()
    assert meta_path.is_file()
    assert meta.lag_bars_used >= 1
    assert meta.signals_fingerprint

    # Backtest using the same data snapshot and policies (read-only).
    cat = DataCatalog(root=data_root)
    rows, _stats = cat.query_ohlcv(snapshot_id=snapshot_id, symbols=["AAA"], start="2024-01-01", end="2024-01-10", as_of="2024-01-11T00:00:00+08:00")
    prices = pd.DataFrame.from_records(rows)
    for c in ["open", "high", "low", "close", "volume"]:
        prices[c] = prices[c].astype(float)

    repo_root = find_repo_root()
    bundle_path = repo_root / "policies" / "policy_bundle_v1.yaml"
    _bundle_id, execution_policy, cost_policy, asof_latency_policy, _sha = _load_policy_docs_from_bundle(bundle_path)
    lag = _trade_lag_bars_default(asof_latency_policy)

    bt = run_adapter(
        adapter_id="vectorbt_signal_v1",
        prices=prices,
        lag_bars=lag,
        execution_policy=execution_policy,
        cost_policy=cost_policy,
        signal_dsl=dsl,
    )
    assert bt.stats.get("signals_fingerprint") == meta.signals_fingerprint

    # CSV must include core columns + entry/exit raw/lagged.
    with out_csv.open("r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        cols = r.fieldnames or []
    for c in ("close", "entry_raw", "exit_raw", "entry_lagged", "exit_lagged"):
        assert c in cols


def test_phase20_strategy_spec_fixtures_guard_pass(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    monkeypatch.setenv("EAM_LLM_PROVIDER", "mock")
    monkeypatch.setenv("EAM_LLM_MODE", "live")
    monkeypatch.setenv("EAM_AGENT_PROMPT_VERSION", "v1")

    for case in ("ma_crossover_case", "rsi_mean_reversion_case"):
        in_path = Path("tests/fixtures/agents/strategy_spec_agent_v1") / case / "input.json"
        assert in_path.is_file()
        out_dir = tmp_path / case
        _ = run_agent(agent_id="strategy_spec_agent_v1", input_path=in_path, out_dir=out_dir, provider="mock")
        guard = json.loads((out_dir / "output_guard_report.json").read_text(encoding="utf-8"))
        assert guard.get("passed") is True
