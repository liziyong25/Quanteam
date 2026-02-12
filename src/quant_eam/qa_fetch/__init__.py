from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .policy import apply_user_policy
from .registry import FetchMapping, build_fetch_mappings
from .registry import _snake_case as _snake_case_internal
from .resolver import fetch_market_data, qa_fetch_registry_payload, resolve_fetch
from .runtime import (
    STATUS_BLOCKED_SOURCE_MISSING,
    STATUS_ERROR_RUNTIME,
    STATUS_PASS_EMPTY,
    STATUS_PASS_HAS_DATA,
    FetchExecutionPolicy,
    FetchExecutionResult,
    FetchIntent,
    execute_fetch_by_intent,
    execute_fetch_by_name,
    write_fetch_evidence,
)
from .wbdata_bridge import resolve_wbdata_callable
from .wequant_bridge import resolve_wequant_callable

try:
    from .probe import (
        DEFAULT_EXPECTED_COUNT,
        DEFAULT_MATRIX_V3_PATH,
        DEFAULT_OUTPUT_DIR,
        ProbeResult,
        parse_matrix_v3,
        probe_matrix_v3,
        results_to_frame,
        write_probe_artifacts,
    )
except ModuleNotFoundError as exc:  # pragma: no cover - env dependent
    _PROBE_IMPORT_ERROR = exc
    DEFAULT_MATRIX_V3_PATH = "docs/05_data_plane/_draft_qa_fetch_rename_matrix_v3.md"
    DEFAULT_EXPECTED_COUNT = 77
    DEFAULT_OUTPUT_DIR = "docs/05_data_plane/qa_fetch_probe_v3"
    ProbeResult = Any  # type: ignore[misc,assignment]

    def _raise_probe_import_error(*args: Any, **kwargs: Any) -> Any:
        raise ModuleNotFoundError(
            "quant_eam.qa_fetch.probe requires optional dependency 'pandas'"
        ) from _PROBE_IMPORT_ERROR

    parse_matrix_v3 = _raise_probe_import_error
    probe_matrix_v3 = _raise_probe_import_error
    results_to_frame = _raise_probe_import_error
    write_probe_artifacts = _raise_probe_import_error


_SOURCE_PRIORITY = {"wbdata": 0, "wequant": 1}
_MAPPINGS = [row for row in apply_user_policy(tuple(build_fetch_mappings())) if row.status != "drop"]
_EXPORT_META: dict[str, dict[str, Any]] = {}


def _dispatch(source: str, target_name: str, *args: Any, **kwargs: Any) -> Any:
    if source == "wequant":
        fn = resolve_wequant_callable(target_name)
    elif source == "wbdata":
        fn = resolve_wbdata_callable(target_name)
    else:
        raise ValueError(f"unsupported source: {source!r}")
    return fn(*args, **kwargs)


def _make_proxy(public_name: str, *, source: str, target_name: str):
    def _proxy(*args: Any, **kwargs: Any) -> Any:
        return _dispatch(source, target_name, *args, **kwargs)

    _proxy.__name__ = public_name
    _proxy.__qualname__ = public_name
    _proxy.__doc__ = f"qa_fetch proxy for `{source}.{target_name}`"
    return _proxy


def _bind(public_name: str, *, source: str, target_name: str, mapping: FetchMapping, force: bool = False) -> None:
    if (not force) and public_name in globals():
        return
    globals()[public_name] = _make_proxy(public_name, source=source, target_name=target_name)
    _EXPORT_META[public_name] = {
        "source": source,
        "target_name": target_name,
        "mapping": asdict(mapping),
    }


def _build_exports() -> None:
    # 1) Canonical names from v3 policy baseline. wequant takes precedence on collisions.
    chosen_by_proposed: dict[str, FetchMapping] = {}
    for item in sorted(_MAPPINGS, key=lambda x: (_SOURCE_PRIORITY[x.source], x.proposed_name, x.old_name)):
        chosen_by_proposed[item.proposed_name] = item
    for proposed_name, item in sorted(chosen_by_proposed.items()):
        _bind(proposed_name, source=item.source, target_name=item.old_name, mapping=item, force=True)

    # 2) Compatibility aliases for old names.
    for item in _MAPPINGS:
        old_name = item.old_name
        # Keep direct old name aliases. On collisions, wequant wins.
        if not (item.source == "wbdata" and item.collision):
            if old_name not in globals():
                _bind(old_name, source=item.source, target_name=old_name, mapping=item)
            elif item.source == "wequant" and _EXPORT_META.get(old_name, {}).get("source") != "wequant":
                _bind(old_name, source=item.source, target_name=old_name, mapping=item, force=True)

        # WBData prefixed aliases are always exported to avoid collision ambiguity.
        if item.source == "wbdata":
            wb_alias = f"wb_{_snake_case_internal(old_name)}"
            _bind(wb_alias, source=item.source, target_name=old_name, mapping=item)

        # Legacy QUANTAXIS-style aliases for wequant.
        if item.source == "wequant" and old_name.startswith("fetch_"):
            qa_alias = f"QA_{old_name}"
            if qa_alias not in globals():
                _bind(qa_alias, source=item.source, target_name=old_name, mapping=item)


def qa_fetch_registry() -> list[dict[str, object]]:
    return [asdict(r) for r in _MAPPINGS]


def qa_fetch_registry_v3(*, include_drop: bool = False) -> list[dict[str, object]]:
    if include_drop:
        rows = apply_user_policy(tuple(build_fetch_mappings()))
        return [asdict(r) for r in rows]
    return [asdict(r) for r in _MAPPINGS]


def qa_fetch_collision_keys() -> tuple[str, ...]:
    keys = {_snake_case_internal(r.old_name) for r in _MAPPINGS if r.collision}
    return tuple(sorted(keys))


def qa_fetch_export_map() -> dict[str, dict[str, Any]]:
    return dict(_EXPORT_META)


_build_exports()


__all__ = sorted(
    [
        name
        for name in globals()
        if name.startswith(("qa_fetch_", "fetch_", "QA_fetch_", "wb_fetch_"))
    ]
    + [
        "qa_fetch_registry",
        "qa_fetch_registry_v3",
        "qa_fetch_collision_keys",
        "qa_fetch_export_map",
        "qa_fetch_registry_payload",
        "resolve_fetch",
        "fetch_market_data",
        "FetchIntent",
        "FetchExecutionPolicy",
        "FetchExecutionResult",
        "execute_fetch_by_intent",
        "execute_fetch_by_name",
        "write_fetch_evidence",
        "STATUS_PASS_HAS_DATA",
        "STATUS_PASS_EMPTY",
        "STATUS_BLOCKED_SOURCE_MISSING",
        "STATUS_ERROR_RUNTIME",
        "ProbeResult",
        "DEFAULT_MATRIX_V3_PATH",
        "DEFAULT_EXPECTED_COUNT",
        "DEFAULT_OUTPUT_DIR",
        "parse_matrix_v3",
        "probe_matrix_v3",
        "results_to_frame",
        "write_probe_artifacts",
    ]
)
