from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from quant_eam.contracts import validate as contracts_validate
from quant_eam.registry.errors import RegistryInvalid
from quant_eam.registry.storage import RegistryPaths, _jsonl_append, iter_jsonl, new_recorded_at, registry_paths


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _require_file(p: Path) -> None:
    if not p.is_file():
        raise RegistryInvalid(f"missing required file: {p.as_posix()}")


def _find_existing_trial(paths: RegistryPaths, run_id: str) -> dict[str, Any] | None:
    for ev in iter_jsonl(paths.trial_log):
        if str(ev.get("run_id", "")) == run_id:
            return ev
    return None


def record_trial(
    *,
    dossier_dir: Path,
    registry_root: Path,
    if_exists: str = "noop",  # "noop" or "append"
) -> dict[str, Any]:
    """Append-only record of a run into trial_log.jsonl.

    Requirements:
    - Must reference dossier + gate_results (no text-only arbitration).
    - Must validate gate_results (gate_results_v1) and the produced trial event (trial_event_v1).
    - Default idempotency: if run_id already exists in log -> noop and return existing event.
    """
    paths = registry_paths(registry_root)
    paths.registry_root.mkdir(parents=True, exist_ok=True)
    dossier_dir = Path(dossier_dir)
    _require_file(dossier_dir / "dossier_manifest.json")
    _require_file(dossier_dir / "config_snapshot.json")
    _require_file(dossier_dir / "gate_results.json")

    dossier_manifest = _load_json(dossier_dir / "dossier_manifest.json")
    config_snapshot = _load_json(dossier_dir / "config_snapshot.json")
    gate_results_path = dossier_dir / "gate_results.json"

    if not isinstance(dossier_manifest, dict):
        raise RegistryInvalid("dossier_manifest.json must be a JSON object")
    if not isinstance(config_snapshot, dict):
        raise RegistryInvalid("config_snapshot.json must be a JSON object")

    # Validate gate_results contract.
    code, msg = contracts_validate.validate_json(gate_results_path)
    if code != contracts_validate.EXIT_OK:
        raise RegistryInvalid(f"gate_results invalid: {msg}")

    gate_results = _load_json(gate_results_path)
    if not isinstance(gate_results, dict):
        raise RegistryInvalid("gate_results.json must be a JSON object")

    run_id = str(dossier_manifest.get("run_id", "")).strip()
    if not run_id:
        raise RegistryInvalid("missing run_id in dossier_manifest.json")

    existing = _find_existing_trial(paths, run_id)
    if existing is not None and if_exists == "noop":
        return existing

    runspec = config_snapshot.get("runspec")
    if not isinstance(runspec, dict):
        raise RegistryInvalid("config_snapshot.runspec missing or not an object")

    policy_bundle_id = str(dossier_manifest.get("policy_bundle_id", "")).strip()
    snapshot_id = str(dossier_manifest.get("data_snapshot_id", "")).strip()
    adapter_id = str((runspec.get("adapter", {}) or {}).get("adapter_id", "")).strip()
    if not policy_bundle_id or not snapshot_id or not adapter_id:
        raise RegistryInvalid("missing policy_bundle_id/data_snapshot_id/adapter_id evidence")

    blueprint_id = str((runspec.get("blueprint_ref", {}) or {}).get("blueprint_id", "")).strip()
    overall_pass = bool(gate_results.get("overall_pass"))

    ev: dict[str, Any] = {
        "schema_version": "trial_event_v1",
        "run_id": run_id,
        "recorded_at": new_recorded_at(),
        "dossier_path": dossier_dir.as_posix(),
        "gate_results_path": gate_results_path.as_posix(),
        "overall_pass": overall_pass,
        "policy_bundle_id": policy_bundle_id,
        "snapshot_id": snapshot_id,
        "adapter_id": adapter_id,
    }
    if blueprint_id:
        ev["blueprint_id"] = blueprint_id

    # Validate trial event contract before writing.
    tmp = paths.registry_root / ".tmp_trial_event.json"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps(ev, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    code2, msg2 = contracts_validate.validate_json(tmp)
    tmp.unlink(missing_ok=True)
    if code2 != contracts_validate.EXIT_OK:
        raise RegistryInvalid(f"trial_event invalid: {msg2}")

    _jsonl_append(paths.trial_log, ev)
    return ev


def get_trial(*, registry_root: Path, run_id: str) -> dict[str, Any] | None:
    paths = registry_paths(registry_root)
    return _find_existing_trial(paths, run_id)
