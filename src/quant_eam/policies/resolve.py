from __future__ import annotations

from pathlib import Path
from typing import Any

from quant_eam.policies.load import default_policies_dir, load_yaml


def load_policy_bundle(bundle_path: Path) -> dict[str, Any]:
    doc = load_yaml(bundle_path)
    if not isinstance(doc, dict):
        raise ValueError("policy bundle YAML must be a mapping/object")
    if doc.get("policy_version") != "v1":
        raise ValueError('policy_bundle policy_version must be "v1"')
    if not isinstance(doc.get("policy_bundle_id"), str) or not doc["policy_bundle_id"].strip():
        raise ValueError("policy_bundle_id must be a non-empty string")
    return doc


def resolve_asof_latency_policy(
    *, bundle_doc: dict[str, Any], policies_dir: Path | None = None
) -> tuple[str, dict[str, Any]]:
    policies_dir = policies_dir or default_policies_dir()
    pid = bundle_doc.get("asof_latency_policy_id")
    if not isinstance(pid, str) or not pid.strip():
        raise ValueError("bundle missing asof_latency_policy_id")

    # v1 assumes a single asset file per policy type (Phase-02/02B assets). Later versions can add registries.
    p = policies_dir / "asof_latency_policy_v1.yaml"
    doc = load_yaml(p)
    if not isinstance(doc, dict):
        raise ValueError("asof_latency_policy YAML must be a mapping/object")
    if doc.get("policy_id") != pid:
        raise ValueError(f"asof_latency_policy_id mismatch (bundle={pid!r}, file={doc.get('policy_id')!r})")
    if doc.get("policy_version") != "v1":
        raise ValueError('asof_latency_policy policy_version must be "v1"')

    params = doc.get("params")
    if not isinstance(params, dict):
        raise ValueError("asof_latency_policy params must be an object")
    if params.get("asof_rule") != "available_at<=as_of":
        raise ValueError('asof_latency_policy params.asof_rule must be "available_at<=as_of"')

    return pid, doc

