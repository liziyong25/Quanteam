from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from quant_eam.qa_fetch.runtime import (
    FetchExecutionPolicy,
    FetchExecutionResult,
    STATUS_ERROR_RUNTIME,
    execute_fetch_by_intent,
    execute_fetch_by_name,
    write_fetch_evidence,
)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _resolve_fetch_out_dir(*, out_dir: Path, payload: dict[str, Any]) -> Path:
    for parent in [out_dir, *out_dir.parents]:
        if parent.name == "outputs":
            return parent / "fetch"

    job_id = str(payload.get("job_id", "")).strip()
    if job_id:
        job_root = Path(os.getenv("EAM_JOB_ROOT", "/jobs"))
        return job_root / job_id / "outputs" / "fetch"
    return out_dir / "fetch"


def _error_result(
    *,
    reason: str,
    mode: str,
    source: str | None = None,
    resolved_function: str | None = None,
    public_function: str | None = None,
    kwargs: dict[str, Any] | None = None,
) -> FetchExecutionResult:
    return FetchExecutionResult(
        status=STATUS_ERROR_RUNTIME,
        reason=reason,
        source=source,
        resolved_function=resolved_function,
        public_function=public_function or resolved_function,
        elapsed_sec=0.0,
        row_count=0,
        columns=[],
        dtypes={},
        preview=None,
        final_kwargs=dict(kwargs or {}),
        mode=mode,
        data=None,
    )


def _run_fetch_request(*, payload: dict[str, Any], out_dir: Path) -> tuple[dict[str, Any], list[Path]]:
    fetch_request = payload.get("fetch_request")
    if not isinstance(fetch_request, dict):
        return {"enabled": False, "reason": "no_fetch_request"}, []

    mode = str(fetch_request.get("mode", "smoke") or "smoke")
    policy_obj = fetch_request.get("policy")
    policy_payload = dict(policy_obj) if isinstance(policy_obj, dict) else {}
    policy_payload.setdefault("mode", mode)
    policy = FetchExecutionPolicy(**policy_payload)
    window_profile = fetch_request.get("window_profile_path") or None
    exception_path = fetch_request.get("exception_decisions_path") or None

    try:
        if isinstance(fetch_request.get("function"), str) and str(fetch_request.get("function")).strip():
            fn_name = str(fetch_request.get("function")).strip()
            kwargs = fetch_request.get("kwargs")
            kwargs = dict(kwargs) if isinstance(kwargs, dict) else {}
            result = execute_fetch_by_name(
                function=fn_name,
                kwargs=kwargs,
                policy=policy,
                source_hint=str(fetch_request.get("source_hint", "") or "") or None,
                public_function=str(fetch_request.get("public_function", "") or "") or None,
                window_profile_path=window_profile or "docs/05_data_plane/qa_fetch_smoke_window_profile_v1.json",
                exception_decisions_path=exception_path or "docs/05_data_plane/qa_fetch_exception_decisions_v1.md",
            )
        else:
            intent_obj = fetch_request.get("intent")
            if isinstance(intent_obj, dict):
                intent_payload = dict(intent_obj)
            else:
                intent_payload = {
                    "asset": fetch_request.get("asset"),
                    "freq": fetch_request.get("freq"),
                    "venue": fetch_request.get("venue"),
                    "adjust": fetch_request.get("adjust", "raw"),
                    "symbols": fetch_request.get("symbols"),
                    "start": fetch_request.get("start"),
                    "end": fetch_request.get("end"),
                    "function_override": fetch_request.get("function_override"),
                    "extra_kwargs": fetch_request.get("extra_kwargs", {}),
                }
            result = execute_fetch_by_intent(
                intent_payload,
                policy=policy,
                window_profile_path=window_profile or "docs/05_data_plane/qa_fetch_smoke_window_profile_v1.json",
                exception_decisions_path=exception_path or "docs/05_data_plane/qa_fetch_exception_decisions_v1.md",
            )
    except Exception as exc:  # noqa: BLE001
        reason = f"{type(exc).__name__}: {exc}"
        result = _error_result(
            reason=reason,
            mode=mode,
            source=None,
            resolved_function=str(fetch_request.get("function", "") or "") or None,
            public_function=str(fetch_request.get("public_function", "") or "") or None,
            kwargs=fetch_request.get("kwargs") if isinstance(fetch_request.get("kwargs"), dict) else {},
        )

    fetch_out_dir = _resolve_fetch_out_dir(out_dir=out_dir, payload=payload)
    path_map = write_fetch_evidence(
        request_payload=fetch_request,
        result=result,
        out_dir=fetch_out_dir,
    )
    fetch_files = [Path(v) for v in path_map.values() if isinstance(v, str)]
    meta = {
        "enabled": True,
        "status": result.status,
        "reason": result.reason,
        "mode": result.mode,
        "source": result.source,
        "resolved_function": result.resolved_function,
        "public_function": result.public_function,
        "row_count": result.row_count,
        "evidence_paths": path_map,
    }
    return meta, fetch_files


def run_demo_agent(*, input_path: Path, out_dir: Path, provider: str = "mock") -> list[Path]:
    if str(provider).strip() != "mock":
        raise ValueError("provider 'external' is not supported in demo_agent MVP")
    payload = _load_json(Path(input_path))
    if not isinstance(payload, dict):
        raise ValueError("demo_agent input must be a JSON object")
    fetch_meta, fetch_files = _run_fetch_request(payload=payload, out_dir=Path(out_dir))

    run_plan = {
        "schema_version": "demo_agent_plan_v1",
        "agent_id": "demo_agent_v1",
        "job_id": payload.get("job_id"),
        "snapshot_id": payload.get("snapshot_id"),
        "symbols": payload.get("symbols"),
        "start": payload.get("start"),
        "end": payload.get("end"),
        "as_of": payload.get("as_of"),
        "fetch": fetch_meta,
        "notes": [
            "Demo step is deterministic and read-only.",
            "Trace preview execution is performed by orchestrator deterministic kernel.",
        ],
    }
    out_path = Path(out_dir) / "demo_plan.json"
    _write_json(out_path, run_plan)
    return [out_path, *fetch_files]
