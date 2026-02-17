from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from quant_eam.contracts import validate as contracts_validate
from quant_eam.policies.resolve import load_policy_bundle


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha12(obj: Any) -> str:
    b = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(b).hexdigest()[:12]


def run_strategy_spec_agent(*, input_path: Path, out_dir: Path, provider: str = "mock") -> list[Path]:
    """StrategySpecAgent v1 (mock): Blueprint draft + IdeaSpec -> strategy artifacts.

    input_path: JSON file with shape:
      { "blueprint_draft": <blueprint_v1>, "idea_spec": <idea_spec_v1> }
    """
    if provider != "mock":
        raise ValueError("StrategySpecAgent MVP supports provider=mock only")

    payload = _load_json(Path(input_path))
    if not isinstance(payload, dict):
        raise ValueError("strategy_spec_agent input must be a JSON object")
    bp = payload.get("blueprint_draft")
    idea = payload.get("idea_spec")
    if not isinstance(bp, dict) or not isinstance(idea, dict):
        raise ValueError("strategy_spec_agent input must include blueprint_draft and idea_spec objects")

    # Validate both inputs.
    c1, m1 = contracts_validate.validate_payload(bp)
    if c1 != contracts_validate.EXIT_OK:
        raise ValueError(f"invalid blueprint_draft: {m1}")
    c2, m2 = contracts_validate.validate_payload(idea)
    if c2 != contracts_validate.EXIT_OK:
        raise ValueError(f"invalid idea_spec: {m2}")

    # Resolve policy_bundle_id from policy_bundle_path (read-only) and enforce blueprint matches.
    pb_path = Path(str(idea.get("policy_bundle_path") or "policies/policy_bundle_v1.yaml"))
    if not pb_path.is_absolute():
        from quant_eam.policies.load import find_repo_root

        pb_path = find_repo_root() / pb_path
    bundle_doc = load_policy_bundle(pb_path)
    bundle_id = str(bundle_doc["policy_bundle_id"])
    if str(bp.get("policy_bundle_id", "")).strip() != bundle_id:
        raise ValueError("policy_bundle_id mismatch between blueprint draft and policy bundle asset")

    symbols = idea.get("symbols") if isinstance(idea.get("symbols"), list) else []
    symbols = [str(s) for s in symbols if str(s).strip()] or ["AAA"]
    freq = str(idea.get("frequency") or "1d")
    start = str(idea.get("start") or "2024-01-01")
    end = str(idea.get("end") or "2024-01-10")

    # Strategy template selection (deterministic). This is an agent proposal; execution is still governed by policies.
    tmpl = "buy_and_hold_mvp"
    ext_in = idea.get("extensions") if isinstance(idea.get("extensions"), dict) else {}
    if isinstance(ext_in, dict):
        v = str(ext_in.get("strategy_template") or "").strip()
        if v in ("ma_crossover", "rsi_mean_reversion"):
            tmpl = v

    # Signal DSL v1 (subset). Use named expressions so trace can surface intermediates consistently.
    if tmpl == "ma_crossover":
        signal_dsl = {
            "dsl_version": "signal_dsl_v1",
            "signals": {"entry": "entry", "exit": "exit"},
            "expressions": {
                "sma_fast": {"type": "op", "op": "sma", "args": [{"type": "var", "var_id": "close"}, {"type": "param", "param_id": "fast"}]},
                "sma_slow": {"type": "op", "op": "sma", "args": [{"type": "var", "var_id": "close"}, {"type": "param", "param_id": "slow"}]},
                "entry": {"type": "op", "op": "cross_above", "args": [{"type": "var", "var_id": "sma_fast"}, {"type": "var", "var_id": "sma_slow"}]},
                "exit": {"type": "op", "op": "cross_below", "args": [{"type": "var", "var_id": "sma_fast"}, {"type": "var", "var_id": "sma_slow"}]},
            },
            "params": {"fast": 5, "slow": 20},
            "execution": {"order_timing": "next_open", "cost_model": {"ref_policy": True}},
            "extensions": {
                "engine_contract": "vectorbt_signal_v1",
                "strategy_id": "ma_crossover_v1",
                "policy_bundle_path": str(idea.get("policy_bundle_path") or "policies/policy_bundle_v1.yaml"),
            },
        }
    elif tmpl == "rsi_mean_reversion":
        signal_dsl = {
            "dsl_version": "signal_dsl_v1",
            "signals": {"entry": "entry", "exit": "exit"},
            "expressions": {
                "rsi": {"type": "op", "op": "rsi", "args": [{"type": "var", "var_id": "close"}, {"type": "param", "param_id": "n"}]},
                "entry": {"type": "op", "op": "lt", "args": [{"type": "var", "var_id": "rsi"}, {"type": "param", "param_id": "entry_th"}]},
                "exit": {"type": "op", "op": "gt", "args": [{"type": "var", "var_id": "rsi"}, {"type": "param", "param_id": "exit_th"}]},
            },
            "params": {"n": 14, "entry_th": 30, "exit_th": 70},
            "execution": {"order_timing": "next_open", "cost_model": {"ref_policy": True}},
            "extensions": {
                "engine_contract": "vectorbt_signal_v1",
                "strategy_id": "rsi_mean_reversion_v1",
                "policy_bundle_path": str(idea.get("policy_bundle_path") or "policies/policy_bundle_v1.yaml"),
            },
        }
    else:
        # MVP fallback: buy-and-hold always-in (entries const true, exits const false).
        signal_dsl = {
            "dsl_version": "signal_dsl_v1",
            "signals": {"entry": "enter", "exit": "exit"},
            "expressions": {"enter": {"type": "const", "value": True}, "exit": {"type": "const", "value": False}},
            "execution": {"order_timing": "next_open", "cost_model": {"ref_policy": True}},
            "extensions": {
                "engine_contract": "vectorbt_signal_v1",
                "strategy_id": "buy_and_hold_mvp",
                "policy_bundle_path": str(idea.get("policy_bundle_path") or "policies/policy_bundle_v1.yaml"),
            },
        }
    c3, m3 = contracts_validate.validate_payload(signal_dsl)
    if c3 != contracts_validate.EXIT_OK:
        raise ValueError(f"invalid signal_dsl_v1 output: {m3}")

    # Variable dictionary: raw fields + derived entry signals (raw vs lagged).
    # In v1, signal lag is a no-lookahead guardrail; keep lag>=1.
    var_dict: dict[str, Any] = {
        "schema_version": "variable_dictionary_v1",
        "variables": [
            {
                "var_id": "close",
                "kind": "field",
                "dtype": "float",
                "source": {
                    "dataset_id": "ohlcv_1d",
                    "field": "close",
                    "adjustment": "none",
                    "frequency": freq,
                    "asof_rule": {"mode": "asof"},
                },
                "alignment": {"lag_bars": 0},
                "missing_policy": {"mode": "drop"},
            },
            {
                "var_id": "available_at",
                "kind": "field",
                "dtype": "datetime",
                "source": {
                    "dataset_id": "ohlcv_1d",
                    "field": "available_at",
                    "adjustment": "none",
                    "frequency": freq,
                    "asof_rule": {"mode": "asof"},
                },
                "alignment": {"lag_bars": 0},
                "missing_policy": {"mode": "drop"},
            },
            {
                # Raw boolean feature (lag=0), used to preview and to derive a lagged "signal".
                "var_id": "entry_raw",
                "kind": "feature",
                "dtype": "bool",
                "compute": {"ast": signal_dsl["expressions"][str(signal_dsl["signals"]["entry"])]},
                "alignment": {"lag_bars": 0},
                "missing_policy": {"mode": "false"},
                "notes": "Raw entry intent (unlagged). For execution, use entry_lagged (signal with lag>=1).",
            },
            {
                "var_id": "entry_lagged",
                "kind": "signal",
                "dtype": "bool",
                "compute": {"ast": {"type": "var", "var_id": "entry_raw"}},
                "alignment": {"lag_bars": 1},
                "missing_policy": {"mode": "false"},
                "notes": "Execution-safe entry signal (lag enforced).",
            },
            {
                "var_id": "exit_raw",
                "kind": "feature",
                "dtype": "bool",
                "compute": {"ast": signal_dsl["expressions"][str(signal_dsl["signals"]["exit"])]},
                "alignment": {"lag_bars": 0},
                "missing_policy": {"mode": "false"},
                "notes": "Raw exit intent (unlagged). For execution, use exit_lagged (signal with lag>=1).",
            },
            {
                "var_id": "exit_lagged",
                "kind": "signal",
                "dtype": "bool",
                "compute": {"ast": {"type": "var", "var_id": "exit_raw"}},
                "alignment": {"lag_bars": 1},
                "missing_policy": {"mode": "false"},
                "notes": "Execution-safe exit signal (lag enforced).",
            },
        ],
        "extensions": {"agent_provider": provider, "policy_bundle_path": str(idea.get("policy_bundle_path") or "policies/policy_bundle_v1.yaml")},
    }
    c4, m4 = contracts_validate.validate_payload(var_dict)
    if c4 != contracts_validate.EXIT_OK:
        raise ValueError(f"invalid variable_dictionary_v1 output: {m4}")

    # Calc trace plan: sample small window and render key variables as a table.
    trace_vars = ["close", "available_at"]
    if tmpl == "ma_crossover":
        trace_vars += ["sma_fast", "sma_slow"]
    if tmpl == "rsi_mean_reversion":
        trace_vars += ["rsi"]
    trace_vars += ["entry_raw", "exit_raw", "entry_lagged", "exit_lagged"]

    trace_plan: dict[str, Any] = {
        "schema_version": "calc_trace_plan_v1",
        "samples": [{"symbols": symbols, "start": start, "end": end, "max_rows": 20}],
        "steps": [
            {
                "step_id": "preview_table",
                "title": "CalcTrace Preview (MVP)",
                "type": "table",
                "render": {"mode": "table"},
                "variables": trace_vars,
            }
        ],
        "assertions": [{"assertion_id": "lag_enforced_entry", "type": "lag_enforced", "variables": ["entry_lagged"], "min_lag_bars": 1}],
        "extensions": {"agent_provider": provider},
    }
    c5, m5 = contracts_validate.validate_payload(trace_plan)
    if c5 != contracts_validate.EXIT_OK:
        raise ValueError(f"invalid calc_trace_plan_v1 output: {m5}")

    # Blueprint final: replace strategy_spec with the generated DSL, and annotate references in extensions (metadata only).
    blueprint_final = dict(bp)
    blueprint_final["strategy_spec"] = signal_dsl
    blueprint_final.setdefault("extensions", {})
    if isinstance(blueprint_final["extensions"], dict):
        blueprint_final["extensions"]["strategy_spec_agent"] = {
            "agent_id": "strategy_spec_agent_v1",
            "input_fingerprint": _sha12(payload),
            "variable_dictionary_ref": "variable_dictionary.json",
            "calc_trace_plan_ref": "calc_trace_plan.json",
        }

    c6, m6 = contracts_validate.validate_payload(blueprint_final)
    if c6 != contracts_validate.EXIT_OK:
        raise ValueError(f"invalid blueprint_final output: {m6}")

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    p_blueprint = out_dir / "blueprint_final.json"
    p_dsl = out_dir / "signal_dsl.json"
    p_vars = out_dir / "variable_dictionary.json"
    p_plan = out_dir / "calc_trace_plan.json"
    _write_json(p_blueprint, blueprint_final)
    _write_json(p_dsl, signal_dsl)
    _write_json(p_vars, var_dict)
    _write_json(p_plan, trace_plan)

    # Validate on-disk artifacts too (ensures dispatch works).
    for p in (p_blueprint, p_dsl, p_vars, p_plan):
        code, msg = contracts_validate.validate_json(p)
        if code != contracts_validate.EXIT_OK:
            raise ValueError(f"output failed validation: {p.name}: {msg}")

    return [p_blueprint, p_dsl, p_vars, p_plan]
