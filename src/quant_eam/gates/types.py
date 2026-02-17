from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class GateEvidence:
    artifacts: list[str] | None = None
    notes: str | None = None


@dataclass(frozen=True)
class GateResult:
    gate_id: str
    gate_version: str
    passed: bool
    status: str | None  # "pass" | "fail" | "skipped" | None
    metrics: dict[str, Any]
    thresholds: dict[str, Any] | None = None
    evidence: GateEvidence | None = None

    def to_json_obj(self) -> dict[str, Any]:
        obj: dict[str, Any] = {
            "gate_id": self.gate_id,
            "gate_version": self.gate_version,
            "pass": bool(self.passed),
            "metrics": dict(self.metrics),
        }
        if self.status is not None:
            obj["status"] = self.status
        if self.thresholds is not None:
            obj["thresholds"] = dict(self.thresholds)
        if self.evidence is not None:
            ev: dict[str, Any] = {}
            if self.evidence.artifacts is not None:
                ev["artifacts"] = list(self.evidence.artifacts)
            if self.evidence.notes is not None:
                ev["notes"] = str(self.evidence.notes)
            obj["evidence"] = ev
        return obj


@dataclass(frozen=True)
class GateContext:
    dossier_dir: Path
    policies_dir: Path
    policy_bundle: dict[str, Any]
    execution_policy: dict[str, Any]
    cost_policy: dict[str, Any]
    asof_latency_policy: dict[str, Any]
    risk_policy: dict[str, Any] | None
    gate_suite: dict[str, Any]
    runspec: dict[str, Any]
    dossier_manifest: dict[str, Any]
    config_snapshot: dict[str, Any]
    metrics: dict[str, Any]


GateFn = Callable[[GateContext, dict[str, Any] | None], GateResult]

