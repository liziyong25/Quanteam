from __future__ import annotations

from typing import Any

from .runtime import (
    DEFAULT_EXCEPTION_DECISIONS_PATH,
    DEFAULT_WINDOW_PROFILE_PATH,
    FetchExecutionPolicy,
    FetchExecutionResult,
    apply_fetch_review_rollback as _runtime_apply_fetch_review_rollback,
    build_fetch_review_checkpoint_state as _runtime_build_fetch_review_checkpoint_state,
    execute_fetch_by_intent as _runtime_execute_fetch_by_intent,
    execute_fetch_by_name as _runtime_execute_fetch_by_name,
    execute_ui_llm_query as _runtime_execute_ui_llm_query,
    execute_ui_llm_query_path as _runtime_execute_ui_llm_query_path,
    validate_fetch_request_v1,
)


def execute_fetch_by_name(
    *,
    function: str,
    kwargs: dict[str, Any] | None = None,
    policy: FetchExecutionPolicy | dict[str, Any] | None = None,
    source_hint: str | None = None,
    public_function: str | None = None,
    window_profile_path: str = str(DEFAULT_WINDOW_PROFILE_PATH),
    exception_decisions_path: str = str(DEFAULT_EXCEPTION_DECISIONS_PATH),
) -> FetchExecutionResult:
    return _runtime_execute_fetch_by_name(
        function=function,
        kwargs=kwargs,
        policy=policy,
        source_hint=source_hint,
        public_function=public_function,
        window_profile_path=window_profile_path,
        exception_decisions_path=exception_decisions_path,
    )


def execute_fetch_by_intent(
    intent: dict[str, Any] | Any,
    *,
    policy: FetchExecutionPolicy | dict[str, Any] | None = None,
    window_profile_path: str = str(DEFAULT_WINDOW_PROFILE_PATH),
    exception_decisions_path: str = str(DEFAULT_EXCEPTION_DECISIONS_PATH),
) -> FetchExecutionResult:
    return _runtime_execute_fetch_by_intent(
        intent,
        policy=policy,
        window_profile_path=window_profile_path,
        exception_decisions_path=exception_decisions_path,
    )


def execute_fetch_request(
    fetch_request: dict[str, Any],
    *,
    policy: FetchExecutionPolicy | dict[str, Any] | None = None,
    window_profile_path: str = str(DEFAULT_WINDOW_PROFILE_PATH),
    exception_decisions_path: str = str(DEFAULT_EXCEPTION_DECISIONS_PATH),
) -> FetchExecutionResult:
    fetch_request = validate_fetch_request_v1(fetch_request)
    return execute_fetch_by_intent(
        fetch_request,
        policy=policy,
        window_profile_path=window_profile_path,
        exception_decisions_path=exception_decisions_path,
    )


def execute_ui_llm_query(
    query_envelope: dict[str, Any],
    *,
    out_dir: str | None = None,
    step_records: list[dict[str, Any]] | None = None,
    policy: FetchExecutionPolicy | dict[str, Any] | None = None,
    window_profile_path: str = str(DEFAULT_WINDOW_PROFILE_PATH),
    exception_decisions_path: str = str(DEFAULT_EXCEPTION_DECISIONS_PATH),
) -> dict[str, Any]:
    return _runtime_execute_ui_llm_query(
        query_envelope,
        out_dir=out_dir,
        step_records=step_records,
        policy=policy,
        window_profile_path=window_profile_path,
        exception_decisions_path=exception_decisions_path,
    )


def execute_ui_llm_query_path(
    query_envelope: dict[str, Any],
    *,
    out_dir: str | None = None,
    step_records: list[dict[str, Any]] | None = None,
    policy: FetchExecutionPolicy | dict[str, Any] | None = None,
    window_profile_path: str = str(DEFAULT_WINDOW_PROFILE_PATH),
    exception_decisions_path: str = str(DEFAULT_EXCEPTION_DECISIONS_PATH),
) -> dict[str, Any]:
    return _runtime_execute_ui_llm_query_path(
        query_envelope,
        out_dir=out_dir,
        step_records=step_records,
        policy=policy,
        window_profile_path=window_profile_path,
        exception_decisions_path=exception_decisions_path,
    )


def build_fetch_review_checkpoint_state(
    *,
    fetch_evidence_dir: str,
) -> dict[str, Any]:
    return _runtime_build_fetch_review_checkpoint_state(fetch_evidence_dir=fetch_evidence_dir)


def apply_fetch_review_rollback(
    *,
    fetch_evidence_dir: str,
    action: str = "reject",
    target_attempt_index: int,
    target_scope: str = "canonical_files_with_errors",
    confirm: bool = False,
    expected_latest_attempt_index: int | None = None,
    expected_latest_preview_hash: str | None = None,
    expected_target_request_hash: str | None = None,
) -> dict[str, Any]:
    return _runtime_apply_fetch_review_rollback(
        fetch_evidence_dir=fetch_evidence_dir,
        action=action,
        target_attempt_index=target_attempt_index,
        target_scope=target_scope,
        confirm=confirm,
        expected_latest_attempt_index=expected_latest_attempt_index,
        expected_latest_preview_hash=expected_latest_preview_hash,
        expected_target_request_hash=expected_target_request_hash,
    )
