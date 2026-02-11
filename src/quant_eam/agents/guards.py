from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


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

# Tokens that indicate executable/script payloads in agent outputs.
# We match on token boundaries (split on non-alnum and underscores), not substrings,
# to avoid false positives like "description" containing "script".
FORBIDDEN_SCRIPT_KEYS = {"code", "python", "script", "bash", "shell"}

FORBIDDEN_HOLDOUT_DETAIL_KEYS = {"holdout_curve", "holdout_trades", "holdout_curve.csv", "holdout_trades.csv"}

FORBIDDEN_POLICY_OVERRIDE_KEYS = {
    "policy_overrides",
    "policy_override",
    "overrides",
    "execution_policy",
    "cost_policy",
    "asof_latency_policy",
    "risk_policy",
    "gate_suite",
    "budget_policy",
    "policy_bundle",
}


def _is_str(x: Any) -> bool:
    return isinstance(x, str) and x.strip() != ""


def _canon_json(x: Any) -> str:
    return json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _key_tokens(lower_key: str) -> list[str]:
    # Split on non-alphanumeric boundaries. Also split snake_case.
    parts = re.split(r"[^a-z0-9]+", lower_key)
    return [p for p in parts if p]


@dataclass(frozen=True)
class GuardFinding:
    rule_id: str
    path: str
    message: str

    def to_json_obj(self) -> dict[str, Any]:
        return {"rule_id": self.rule_id, "path": self.path, "message": self.message}


def validate_agent_output(
    *,
    agent_id: str,
    output_json: Any,
    prompt_version: str | None = None,
    output_schema_version: str | None = None,
) -> dict[str, Any]:
    """Hard governance guardrails for agent outputs.

    This is not schema validation; it is a set of deterministic 'red lines' that prevent:
    - inline policy params (policies must remain read-only references)
    - executable script/code content in outputs
    - holdout detail leakage
    """
    agent_id = str(agent_id).strip()
    findings: list[GuardFinding] = []
    allow_inline_metric_keys = agent_id == "report_agent_v1"

    def walk(x: Any, path: str, depth: int) -> None:
        if depth > 30:
            return
        if isinstance(x, dict):
            for k, v in x.items():
                ks = str(k)
                p2 = f"{path}/{ks}" if path else f"/{ks}"
                kl = ks.lower()

                if (not allow_inline_metric_keys) and kl in FORBIDDEN_INLINE_POLICY_KEYS:
                    # Avoid false positives for contract fields that reuse names:
                    # - Blueprint data_requirements[].asof_rule is an object contract field.
                    # - Policy asof_latency_policy.params.asof_rule is a scalar policy param (must not be inlined).
                    if kl == "asof_rule" and not _is_str(v):
                        walk(v, p2, depth + 1)
                        continue
                    findings.append(
                        GuardFinding(
                            rule_id="no_inline_policy_params",
                            path=p2,
                            message=f"forbidden inline policy param key: {ks}",
                        )
                    )

                if any(tok in _key_tokens(kl) for tok in FORBIDDEN_SCRIPT_KEYS):
                    findings.append(
                        GuardFinding(
                            rule_id="no_executable_scripts",
                            path=p2,
                            message=f"forbidden script/code key: {ks}",
                        )
                    )

                if kl in FORBIDDEN_POLICY_OVERRIDE_KEYS:
                    findings.append(
                        GuardFinding(
                            rule_id="no_policy_overrides",
                            path=p2,
                            message=f"forbidden policy override key: {ks}",
                        )
                    )

                if kl in FORBIDDEN_HOLDOUT_DETAIL_KEYS:
                    findings.append(
                        GuardFinding(
                            rule_id="no_holdout_details",
                            path=p2,
                            message=f"forbidden holdout detail key: {ks}",
                        )
                    )

                # Also scan string values for a few obvious holdout artifact names.
                if _is_str(v):
                    vl = str(v).lower()
                    if "holdout_curve" in vl or "holdout_trades" in vl:
                        findings.append(
                            GuardFinding(
                                rule_id="no_holdout_details",
                                path=p2,
                                message="holdout detail reference found in string value",
                            )
                        )

                walk(v, p2, depth + 1)
            return
        if isinstance(x, list):
            for i, v in enumerate(x):
                walk(v, f"{path}/{i}" if path else f"/{i}", depth + 1)
            return
        # Scalars: nothing else

    walk(output_json, "", 0)

    passed = len(findings) == 0
    guard_status = "pass" if passed else "fail"
    report = {
        "schema_version": "output_guard_report_v1",
        "agent_id": agent_id,
        # Phase-28: these fields are required for operational rollout reviews (live/record/replay).
        "prompt_version": (str(prompt_version).strip() if isinstance(prompt_version, str) and prompt_version.strip() else None),
        "output_schema_version": (
            str(output_schema_version).strip() if isinstance(output_schema_version, str) and output_schema_version.strip() else None
        ),
        "guard_status": guard_status,
        "passed": bool(passed),
        "finding_count": int(len(findings)),
        "findings": [f.to_json_obj() for f in findings],
        "extensions": {
            "output_sha256_hint": __import__("hashlib").sha256(_canon_json(output_json).encode("utf-8")).hexdigest(),
        },
    }
    return report
