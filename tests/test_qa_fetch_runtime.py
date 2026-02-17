from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from quant_eam.qa_fetch import runtime


def _registry_row(
    function: str,
    *,
    source: str = "mysql_fetch",
    target_name: str | None = None,
) -> dict[str, dict[str, str]]:
    return {
        function: {
            "function": function,
            "source": source,
            "target_name": target_name or function,
            "status": "active",
        }
    }


def _write_function_registry_payload(
    path: Path,
    *,
    functions: list[dict[str, Any]],
    function_count: int | None = None,
) -> None:
    payload = {
        "schema_version": "qa_fetch_function_registry_v1",
        "generated_at_utc": "2026-02-13T00:00:00Z",
        "function_count": int(function_count if function_count is not None else len(functions)),
        "functions": functions,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_routing_registry_payload(
    path: Path,
    *,
    resolver_entries: list[dict[str, Any]],
) -> None:
    payload = {
        "schema_version": "qa_fetch_registry_v1",
        "generated_at_utc": "2026-02-14T00:00:00Z",
        "resolver_entries": resolver_entries,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_probe_summary_payload(
    path: Path,
    *,
    total: int,
    pass_has_data: int,
    pass_empty: int | None = None,
    pass_has_data_or_empty: int | None = None,
    status_counts_extra: dict[str, int] | None = None,
) -> None:
    resolved_pass_empty = int(pass_empty if pass_empty is not None else (int(total) - int(pass_has_data)))
    status_counts: dict[str, int] = {
        "pass_has_data": int(pass_has_data),
        "pass_empty": resolved_pass_empty,
    }
    if isinstance(status_counts_extra, dict):
        for key, value in status_counts_extra.items():
            status_counts[str(key)] = int(value)
    resolved_callable_total = int(
        pass_has_data_or_empty if pass_has_data_or_empty is not None else (int(pass_has_data) + resolved_pass_empty)
    )
    payload = {
        "total": int(total),
        "status_counts": status_counts,
        "pass_has_data": int(pass_has_data),
        "pass_has_data_or_empty": resolved_callable_total,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_smoke_window_profile_payload(
    path: Path,
    *,
    functions: list[dict[str, Any]],
    notebook_ref: str | None = None,
) -> None:
    payload: dict[str, Any] = {
        "schema_version": "qa_fetch_smoke_window_profile_v1",
        "generated_at_utc": "2026-02-14T00:00:00Z",
        "functions": functions,
    }
    if notebook_ref is not None:
        payload["notebook_ref"] = notebook_ref
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_golden_summary_payload(path: Path, *, query_hashes: dict[str, str]) -> None:
    payload = {
        "schema_version": "qa_fetch_golden_summary_v1",
        "generated_at": "2026-02-14T00:00:00Z",
        "total_queries": len(query_hashes),
        "query_hashes": dict(query_hashes),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _baseline_registry_rows(*, mongo_count: int, mysql_count: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx in range(mongo_count):
        fn = f"fetch_mongo_case_{idx:03d}"
        rows.append(
            {
                "function": fn,
                "source": "fetch",
                "source_internal": "mongo_fetch",
                "provider_internal": "mongo_fetch",
                "engine": "mongo",
                "target_name": fn,
                "status": "active",
            }
        )
    for idx in range(mysql_count):
        fn = f"fetch_mysql_case_{idx:03d}"
        rows.append(
            {
                "function": fn,
                "source": "fetch",
                "source_internal": "mysql_fetch",
                "provider_internal": "mysql_fetch",
                "engine": "mysql",
                "target_name": fn,
                "status": "active",
            }
        )
    return rows


def _step_filename(template: str, *, step_index: int) -> str:
    return str(template).format(step_index=step_index)


def test_load_function_registry_rejects_baseline_engine_split_mismatch(tmp_path) -> None:
    rows = _baseline_registry_rows(mongo_count=47, mysql_count=24)
    registry_path = tmp_path / "qa_fetch_function_registry_v1.json"
    _write_function_registry_payload(registry_path, functions=rows, function_count=71)

    with pytest.raises(ValueError, match=r"baseline engine split mismatch"):
        runtime.load_function_registry(registry_path)


def test_load_function_registry_accepts_baseline_engine_split_contract(tmp_path) -> None:
    rows = _baseline_registry_rows(mongo_count=48, mysql_count=23)
    registry_path = tmp_path / "qa_fetch_function_registry_v1.json"
    _write_function_registry_payload(registry_path, functions=rows, function_count=71)

    out = runtime.load_function_registry(registry_path)

    assert len(out) == 71
    assert out["fetch_mongo_case_000"]["engine"] == "mongo"
    assert out["fetch_mysql_case_000"]["engine"] == "mysql"


def test_load_function_registry_rejects_row_level_engine_source_mismatch(tmp_path) -> None:
    rows = [
        {
            "function": "fetch_demo",
            "source": "fetch",
            "source_internal": "mysql_fetch",
            "provider_internal": "mysql_fetch",
            "engine": "mongo",
            "target_name": "fetch_demo",
            "status": "active",
        }
    ]
    registry_path = tmp_path / "qa_fetch_function_registry_v1.json"
    _write_function_registry_payload(registry_path, functions=rows, function_count=1)

    with pytest.raises(ValueError, match=r"engine='mongo'.*source_internal='mysql_fetch'"):
        runtime.load_function_registry(registry_path)


def test_load_function_registry_rejects_qf_016_source_semantic_mismatch(tmp_path) -> None:
    rows = [
        {
            "function": "fetch_demo",
            "source": "mysql_fetch",
            "source_internal": "mysql_fetch",
            "provider_internal": "mysql_fetch",
            "engine": "mysql",
            "target_name": "fetch_demo",
            "status": "active",
        }
    ]
    registry_path = tmp_path / "qa_fetch_function_registry_v1.json"
    _write_function_registry_payload(registry_path, functions=rows, function_count=1)

    with pytest.raises(ValueError, match=r"expected semantic source='fetch'"):
        runtime.load_function_registry(registry_path)


def test_load_routing_registry_extracts_public_names(tmp_path) -> None:
    routing_path = tmp_path / "qa_fetch_registry_v1.json"
    _write_routing_registry_payload(
        routing_path,
        resolver_entries=[
            {
                "asset": "stock",
                "freq": "day",
                "venue": None,
                "raw": {"public_name": "fetch_stock_day"},
                "adjustment": {"adv": {"public_name": "fetch_stock_day_adv"}},
            },
            {
                "asset": "bond",
                "freq": "day",
                "venue": None,
                "raw": {"public_name": "fetch_bond_day"},
                "adjustment": {"adv": None},
            },
            {"asset": "broken", "raw": {}},
        ],
    )

    out = runtime.load_routing_registry(routing_path)

    assert out == {"fetch_stock_day", "fetch_stock_day_adv", "fetch_bond_day"}


def test_load_probe_summary_rejects_baseline_pass_has_data_mismatch(tmp_path) -> None:
    summary_path = tmp_path / "probe_summary_v3_notebook_params.json"
    _write_probe_summary_payload(
        summary_path,
        total=runtime.BASELINE_FUNCTION_COUNT,
        pass_has_data=runtime.BASELINE_PASS_HAS_DATA_COUNT - 1,
    )

    with pytest.raises(ValueError, match=r"baseline pass_has_data mismatch"):
        runtime.load_probe_summary(summary_path)


def test_load_probe_summary_accepts_baseline_pass_has_data_contract(tmp_path) -> None:
    summary_path = tmp_path / "probe_summary_v3_notebook_params.json"
    _write_probe_summary_payload(
        summary_path,
        total=runtime.BASELINE_FUNCTION_COUNT,
        pass_has_data=runtime.BASELINE_PASS_HAS_DATA_COUNT,
    )

    payload = runtime.load_probe_summary(summary_path)

    assert payload["total"] == runtime.BASELINE_FUNCTION_COUNT
    assert payload["pass_has_data"] == runtime.BASELINE_PASS_HAS_DATA_COUNT
    assert payload["status_counts"]["pass_empty"] == runtime.BASELINE_PASS_EMPTY_COUNT
    assert payload["pass_has_data_or_empty"] == runtime.BASELINE_FUNCTION_COUNT


def test_load_probe_summary_rejects_baseline_pass_empty_mismatch(tmp_path) -> None:
    summary_path = tmp_path / "probe_summary_v3_notebook_params.json"
    _write_probe_summary_payload(
        summary_path,
        total=runtime.BASELINE_FUNCTION_COUNT,
        pass_has_data=runtime.BASELINE_PASS_HAS_DATA_COUNT,
        pass_empty=runtime.BASELINE_PASS_EMPTY_COUNT - 1,
    )

    with pytest.raises(ValueError, match=r"baseline pass_empty mismatch"):
        runtime.load_probe_summary(summary_path)


def test_load_probe_summary_rejects_baseline_callable_coverage_mismatch(tmp_path) -> None:
    summary_path = tmp_path / "probe_summary_v3_notebook_params.json"
    _write_probe_summary_payload(
        summary_path,
        total=runtime.BASELINE_FUNCTION_COUNT,
        pass_has_data=runtime.BASELINE_PASS_HAS_DATA_COUNT,
        pass_empty=runtime.BASELINE_PASS_EMPTY_COUNT,
        pass_has_data_or_empty=runtime.BASELINE_FUNCTION_COUNT - 1,
    )

    with pytest.raises(ValueError, match=r"baseline callable coverage mismatch"):
        runtime.load_probe_summary(summary_path)


def test_load_probe_summary_rejects_baseline_runtime_blockage_mismatch(tmp_path) -> None:
    summary_path = tmp_path / "probe_summary_v3_notebook_params.json"
    _write_probe_summary_payload(
        summary_path,
        total=runtime.BASELINE_FUNCTION_COUNT,
        pass_has_data=runtime.BASELINE_PASS_HAS_DATA_COUNT,
        pass_empty=runtime.BASELINE_PASS_EMPTY_COUNT,
        status_counts_extra={
            runtime.STATUS_BLOCKED_SOURCE_MISSING: 1,
            runtime.STATUS_ERROR_RUNTIME: 0,
        },
    )

    with pytest.raises(ValueError, match=r"baseline runtime blockage mismatch"):
        runtime.load_probe_summary(summary_path)


def test_load_probe_summary_accepts_qf_120_notebook_params_has_data_contract(tmp_path) -> None:
    summary_path = tmp_path / "probe_summary_v3_notebook_params.json"
    _write_probe_summary_payload(
        summary_path,
        total=2,
        pass_has_data=1,
        pass_empty=1,
    )

    payload = runtime.load_probe_summary(summary_path)

    assert payload["pass_has_data"] == 1


def test_load_probe_summary_rejects_qf_120_notebook_params_has_no_data(tmp_path) -> None:
    summary_path = tmp_path / "probe_summary_v3_notebook_params.json"
    _write_probe_summary_payload(
        summary_path,
        total=2,
        pass_has_data=0,
        pass_empty=2,
    )

    with pytest.raises(ValueError, match=r"notebook params data availability mismatch"):
        runtime.load_probe_summary(summary_path)


def test_load_smoke_window_profile_accepts_qf_118_notebook_ref_contract(tmp_path) -> None:
    profile_path = tmp_path / "qa_fetch_smoke_window_profile_v1.json"
    _write_smoke_window_profile_payload(
        profile_path,
        notebook_ref=runtime.NOTEBOOK_KERNEL_MANUAL_PARAMS_NOTEBOOK_PATH,
        functions=[
            {
                "function": "fetch_demo",
                "smoke_kwargs": {"symbol": "000001"},
                "smoke_timeout_sec": 30,
            }
        ],
    )

    payload = runtime.load_smoke_window_profile(profile_path)

    assert "fetch_demo" in payload


def test_load_smoke_window_profile_rejects_qf_118_notebook_ref_mismatch(tmp_path) -> None:
    profile_path = tmp_path / "qa_fetch_smoke_window_profile_v1.json"
    _write_smoke_window_profile_payload(
        profile_path,
        notebook_ref="notebooks/another_notebook.ipynb",
        functions=[],
    )

    with pytest.raises(ValueError, match=r"notebook_ref mismatch"):
        runtime.load_smoke_window_profile(profile_path)


def test_runtime_module_contract_path_matches_qf_025_clause() -> None:
    assert runtime.FETCHDATA_IMPL_RUNTIME_MODULE_REQUIREMENT_ID == "QF-025"
    assert (
        runtime.FETCHDATA_IMPL_RUNTIME_MODULE_SOURCE_DOCUMENT
        == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    )
    assert runtime.FETCHDATA_IMPL_RUNTIME_MODULE_CLAUSE == "runtime：`src/quant_eam/qa_fetch/runtime.py`"
    assert runtime.RUNTIME_MODULE_CONTRACT_PATH == "src/quant_eam/qa_fetch/runtime.py"
    runtime_path = Path(runtime.__file__).resolve().as_posix()
    assert runtime_path.endswith(runtime.RUNTIME_MODULE_CONTRACT_PATH)


def test_runtime_fetchdata_impl_spec_anchor_matches_qf_001_clause() -> None:
    assert runtime.FETCHDATA_IMPL_SPEC_REQUIREMENT_ID == "QF-001"
    assert runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    assert runtime.FETCHDATA_IMPL_SPEC_CLAUSE == "QA-Fetch FetchData Implementation Spec (v1)"


def test_runtime_fetchdata_impl_purpose_anchor_matches_qf_002_clause() -> None:
    assert runtime.FETCHDATA_IMPL_PURPOSE_REQUIREMENT_ID == "QF-002"
    assert runtime.FETCHDATA_IMPL_PURPOSE_SOURCE_DOCUMENT == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    assert runtime.FETCHDATA_IMPL_PURPOSE_CLAUSE == "QA-Fetch FetchData Implementation Spec (v1) / 0. 目的与定位"


def test_runtime_fetchdata_impl_purpose_objective_anchor_matches_qf_003_clause() -> None:
    assert runtime.FETCHDATA_IMPL_PURPOSE_OBJECTIVE_REQUIREMENT_ID == "QF-003"
    assert (
        runtime.FETCHDATA_IMPL_PURPOSE_OBJECTIVE_SOURCE_DOCUMENT
        == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    )
    assert (
        runtime.FETCHDATA_IMPL_PURPOSE_OBJECTIVE_CLAUSE
        == "QA-Fetch FetchData Implementation Spec (v1) / 0. 目的与定位 / 0.1 目的"
    )


def test_runtime_fetchdata_impl_purpose_positioning_anchor_matches_qf_004_clause() -> None:
    assert runtime.FETCHDATA_IMPL_PURPOSE_POSITIONING_REQUIREMENT_ID == "QF-004"
    assert (
        runtime.FETCHDATA_IMPL_PURPOSE_POSITIONING_SOURCE_DOCUMENT
        == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    )
    assert (
        runtime.FETCHDATA_IMPL_PURPOSE_POSITIONING_CLAUSE
        == "QA-Fetch FetchData Implementation Spec (v1) / 0. 目的与定位 / 0.2 定位（系统边界）"
    )


def test_runtime_fetchdata_impl_fetch_request_intent_priority_anchor_matches_qf_005_clause() -> None:
    assert runtime.FETCHDATA_IMPL_FETCH_REQUEST_INTENT_PRIORITY_REQUIREMENT_ID == "QF-005"
    assert (
        runtime.FETCHDATA_IMPL_FETCH_REQUEST_INTENT_PRIORITY_SOURCE_DOCUMENT
        == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    )
    assert runtime.FETCHDATA_IMPL_FETCH_REQUEST_INTENT_PRIORITY_CLAUSE == "接受来自主链路的 `fetch_request`（intent 优先）；"


def test_runtime_fetchdata_impl_runtime_unified_execution_anchor_matches_qf_006_clause() -> None:
    assert runtime.FETCHDATA_IMPL_RUNTIME_UNIFIED_EXECUTION_REQUIREMENT_ID == "QF-006"
    assert (
        runtime.FETCHDATA_IMPL_RUNTIME_UNIFIED_EXECUTION_SOURCE_DOCUMENT
        == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    )
    assert runtime.FETCHDATA_IMPL_RUNTIME_UNIFIED_EXECUTION_CLAUSE == "通过统一 runtime 解析/执行 fetch；"
    assert getattr(runtime, runtime.RUNTIME_INTENT_ENTRYPOINT_NAME) is runtime.execute_fetch_by_intent
    assert getattr(runtime, runtime.RUNTIME_NAME_ENTRYPOINT_NAME) is runtime.execute_fetch_by_name


def test_runtime_fetchdata_impl_forced_evidence_anchor_matches_qf_007_clause() -> None:
    assert runtime.FETCHDATA_IMPL_FORCED_EVIDENCE_REQUIREMENT_ID == "QF-007"
    assert runtime.FETCHDATA_IMPL_FORCED_EVIDENCE_SOURCE_DOCUMENT == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    assert runtime.FETCHDATA_IMPL_FORCED_EVIDENCE_CLAUSE == "为每次取数强制落盘证据；"


def test_runtime_fetchdata_impl_datacatalog_time_travel_gates_anchor_matches_qf_008_clause() -> None:
    assert runtime.FETCHDATA_IMPL_DATACATALOG_TIME_TRAVEL_GATES_REQUIREMENT_ID == "QF-008"
    assert (
        runtime.FETCHDATA_IMPL_DATACATALOG_TIME_TRAVEL_GATES_SOURCE_DOCUMENT
        == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    )
    assert (
        runtime.FETCHDATA_IMPL_DATACATALOG_TIME_TRAVEL_GATES_CLAUSE
        == "为 DataCatalog/time‑travel 与 gates 提供可审计输入基础；"
    )


def test_runtime_fetchdata_impl_multi_step_traceability_anchor_matches_qf_009_clause() -> None:
    assert runtime.FETCHDATA_IMPL_MULTI_STEP_TRACEABILITY_REQUIREMENT_ID == "QF-009"
    assert (
        runtime.FETCHDATA_IMPL_MULTI_STEP_TRACEABILITY_SOURCE_DOCUMENT
        == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    )
    assert runtime.FETCHDATA_IMPL_MULTI_STEP_TRACEABILITY_CLAUSE == "支持多步取数（如 list→sample→day）并可追溯。"


def test_runtime_fetchdata_impl_backtest_plane_kernel_boundary_anchor_matches_qf_010_clause() -> None:
    assert runtime.FETCHDATA_IMPL_BACKTEST_PLANE_KERNEL_BOUNDARY_REQUIREMENT_ID == "QF-010"
    assert (
        runtime.FETCHDATA_IMPL_BACKTEST_PLANE_KERNEL_BOUNDARY_SOURCE_DOCUMENT
        == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    )
    assert (
        runtime.FETCHDATA_IMPL_BACKTEST_PLANE_KERNEL_BOUNDARY_CLAUSE
        == "策略逻辑生成、回测引擎实现（属于 Backtest Plane / Kernel）；"
    )


def test_runtime_fetchdata_impl_gaterunner_arbitration_boundary_anchor_matches_qf_011_clause() -> None:
    assert runtime.FETCHDATA_IMPL_GATERUNNER_ARBITRATION_BOUNDARY_REQUIREMENT_ID == "QF-011"
    assert (
        runtime.FETCHDATA_IMPL_GATERUNNER_ARBITRATION_BOUNDARY_SOURCE_DOCUMENT
        == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    )
    assert (
        runtime.FETCHDATA_IMPL_GATERUNNER_ARBITRATION_BOUNDARY_CLAUSE
        == "策略是否有效的裁决（只允许 GateRunner 裁决）；"
    )


def test_runtime_fetchdata_impl_ui_reviewable_evidence_anchor_matches_qf_012_clause() -> None:
    assert runtime.FETCHDATA_IMPL_UI_REVIEWABLE_EVIDENCE_REQUIREMENT_ID == "QF-012"
    assert (
        runtime.FETCHDATA_IMPL_UI_REVIEWABLE_EVIDENCE_SOURCE_DOCUMENT
        == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    )
    assert (
        runtime.FETCHDATA_IMPL_UI_REVIEWABLE_EVIDENCE_CLAUSE
        == "UI 的交互实现（但必须规定 UI 可审阅的证据接口与产物）。"
    )
    assert runtime.UI_REVIEWABLE_FETCH_EVIDENCE_INTERFACE_FIELDS == (
        "query_result",
        "fetch_evidence_summary",
        "evidence_pointer",
        "fetch_evidence_paths",
    )
    assert runtime.UI_REVIEWABLE_FETCH_EVIDENCE_ARTIFACT_KEYS == (
        "fetch_request_path",
        "fetch_result_meta_path",
        "fetch_preview_path",
        "fetch_steps_index_path",
    )


def test_runtime_fetchdata_impl_baseline_regression_anchor_matches_qf_013_clause() -> None:
    assert runtime.FETCHDATA_IMPL_BASELINE_REGRESSION_REQUIREMENT_ID == "QF-013"
    assert (
        runtime.FETCHDATA_IMPL_BASELINE_REGRESSION_SOURCE_DOCUMENT
        == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    )
    assert (
        runtime.FETCHDATA_IMPL_BASELINE_REGRESSION_CLAUSE
        == "QA‑Fetch FetchData Implementation Spec (v1) / 1. 现有事实基线（必须保持可回归）"
    )
    assert runtime.BASELINE_ENGINE_SPLIT == {"mongo": 48, "mysql": 23}
    assert runtime.BASELINE_FUNCTION_COUNT == 71
    assert runtime.BASELINE_PASS_HAS_DATA_COUNT == 52
    assert runtime.BASELINE_PASS_EMPTY_COUNT == 19


def test_runtime_fetchdata_impl_function_baseline_anchor_matches_qf_014_clause() -> None:
    assert runtime.FETCHDATA_IMPL_FUNCTION_BASELINE_REQUIREMENT_ID == "QF-014"
    assert (
        runtime.FETCHDATA_IMPL_FUNCTION_BASELINE_SOURCE_DOCUMENT
        == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    )
    assert (
        runtime.FETCHDATA_IMPL_FUNCTION_BASELINE_CLAUSE
        == "QA‑Fetch FetchData Implementation Spec (v1) / 1. 现有事实基线（必须保持可回归） / 1.1 函数基线"
    )
    assert runtime.BASELINE_FUNCTION_COUNT == 71
    assert sum(runtime.BASELINE_ENGINE_SPLIT.values()) == runtime.BASELINE_FUNCTION_COUNT


def test_runtime_fetchdata_impl_function_registry_anchor_matches_qf_015_clause() -> None:
    assert runtime.FETCHDATA_IMPL_FUNCTION_REGISTRY_REQUIREMENT_ID == "QF-015"
    assert (
        runtime.FETCHDATA_IMPL_FUNCTION_REGISTRY_SOURCE_DOCUMENT
        == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    )
    assert (
        runtime.FETCHDATA_IMPL_FUNCTION_REGISTRY_CLAUSE
        == "函数注册表：`docs/05_data_plane/qa_fetch_function_registry_v1.json`"
    )
    assert (
        runtime.FETCHDATA_IMPL_FUNCTION_REGISTRY_CONTRACT_PATH
        == "docs/05_data_plane/qa_fetch_function_registry_v1.json"
    )
    assert runtime.DEFAULT_FUNCTION_REGISTRY_PATH.as_posix() == runtime.FETCHDATA_IMPL_FUNCTION_REGISTRY_CONTRACT_PATH


def test_runtime_fetchdata_impl_source_semantic_anchor_matches_qf_016_clause() -> None:
    assert runtime.FETCHDATA_IMPL_SOURCE_SEMANTIC_REQUIREMENT_ID == "QF-016"
    assert runtime.FETCHDATA_IMPL_SOURCE_SEMANTIC_SOURCE_DOCUMENT == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    assert runtime.FETCHDATA_IMPL_SOURCE_SEMANTIC_CLAUSE == "对外语义：`source=fetch`"
    assert runtime.FETCHDATA_IMPL_SOURCE_SEMANTIC_VALUE == "fetch"


def test_runtime_fetchdata_impl_engine_split_anchor_matches_qf_017_clause() -> None:
    assert runtime.FETCHDATA_IMPL_ENGINE_SPLIT_REQUIREMENT_ID == "QF-017"
    assert runtime.FETCHDATA_IMPL_ENGINE_SPLIT_SOURCE_DOCUMENT == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    assert runtime.FETCHDATA_IMPL_ENGINE_SPLIT_CLAUSE == "引擎拆分：`engine=mongo|mysql`（分布：mongo 48、mysql 23）"
    assert runtime.BASELINE_ENGINE_SPLIT == {"mongo": 48, "mysql": 23}
    assert runtime.ENGINE_INTERNAL_SOURCE == {"mongo": "mongo_fetch", "mysql": "mysql_fetch"}


def test_runtime_fetchdata_impl_machine_routing_availability_anchor_matches_qf_018_clause() -> None:
    assert runtime.FETCHDATA_IMPL_MACHINE_ROUTING_AVAILABILITY_REQUIREMENT_ID == "QF-018"
    assert (
        runtime.FETCHDATA_IMPL_MACHINE_ROUTING_AVAILABILITY_SOURCE_DOCUMENT
        == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    )
    assert (
        runtime.FETCHDATA_IMPL_MACHINE_ROUTING_AVAILABILITY_CLAUSE
        == "QA‑Fetch FetchData Implementation Spec (v1) / 1. 现有事实基线（必须保持可回归） / 1.2 机器路由与可用性证据"
    )
    assert runtime.FETCHDATA_IMPL_MACHINE_ROUTING_REGISTRY_CONTRACT_PATH == "docs/05_data_plane/qa_fetch_registry_v1.json"
    assert (
        runtime.FETCHDATA_IMPL_MACHINE_ROUTING_PROBE_SUMMARY_CONTRACT_PATH
        == "docs/05_data_plane/qa_fetch_probe_v3/probe_summary_v3_notebook_params.json"
    )
    assert runtime.FETCHDATA_IMPL_MACHINE_ROUTING_AVAILABILITY_EVIDENCE_PATHS == (
        "docs/05_data_plane/qa_fetch_registry_v1.json",
        "docs/05_data_plane/qa_fetch_probe_v3/probe_summary_v3_notebook_params.json",
    )
    assert runtime.DEFAULT_ROUTING_REGISTRY_PATH.as_posix() == runtime.FETCHDATA_IMPL_MACHINE_ROUTING_REGISTRY_CONTRACT_PATH
    assert (
        runtime.DEFAULT_PROBE_SUMMARY_PATH.as_posix()
        == runtime.FETCHDATA_IMPL_MACHINE_ROUTING_PROBE_SUMMARY_CONTRACT_PATH
    )


def test_runtime_fetchdata_impl_routing_registry_anchor_matches_qf_019_clause() -> None:
    assert runtime.FETCHDATA_IMPL_ROUTING_REGISTRY_REQUIREMENT_ID == "QF-019"
    assert runtime.FETCHDATA_IMPL_ROUTING_REGISTRY_SOURCE_DOCUMENT == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    assert runtime.FETCHDATA_IMPL_ROUTING_REGISTRY_CLAUSE == "路由注册表：`docs/05_data_plane/qa_fetch_registry_v1.json`"
    assert runtime.FETCHDATA_IMPL_ROUTING_REGISTRY_CONTRACT_PATH == "docs/05_data_plane/qa_fetch_registry_v1.json"
    assert runtime.DEFAULT_ROUTING_REGISTRY_PATH.as_posix() == runtime.FETCHDATA_IMPL_ROUTING_REGISTRY_CONTRACT_PATH


def test_runtime_fetchdata_impl_probe_evidence_anchor_matches_qf_020_clause() -> None:
    assert runtime.FETCHDATA_IMPL_PROBE_EVIDENCE_REQUIREMENT_ID == "QF-020"
    assert runtime.FETCHDATA_IMPL_PROBE_EVIDENCE_SOURCE_DOCUMENT == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    assert (
        runtime.FETCHDATA_IMPL_PROBE_EVIDENCE_CLAUSE
        == "probe 证据：`docs/05_data_plane/qa_fetch_probe_v3/probe_summary_v3_notebook_params.json`"
    )
    assert (
        runtime.FETCHDATA_IMPL_PROBE_EVIDENCE_CONTRACT_PATH
        == "docs/05_data_plane/qa_fetch_probe_v3/probe_summary_v3_notebook_params.json"
    )
    assert runtime.DEFAULT_PROBE_SUMMARY_PATH.as_posix() == runtime.FETCHDATA_IMPL_PROBE_EVIDENCE_CONTRACT_PATH


def test_runtime_fetchdata_impl_pass_has_data_anchor_matches_qf_021_clause() -> None:
    assert runtime.FETCHDATA_IMPL_PASS_HAS_DATA_REQUIREMENT_ID == "QF-021"
    assert runtime.FETCHDATA_IMPL_PASS_HAS_DATA_SOURCE_DOCUMENT == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    assert runtime.FETCHDATA_IMPL_PASS_HAS_DATA_CLAUSE == "pass_has_data=52"
    assert runtime.FETCHDATA_IMPL_PASS_HAS_DATA_BASELINE_COUNT == 52
    assert runtime.BASELINE_PASS_HAS_DATA_COUNT == runtime.FETCHDATA_IMPL_PASS_HAS_DATA_BASELINE_COUNT


def test_runtime_fetchdata_impl_pass_empty_anchor_matches_qf_022_clause() -> None:
    assert runtime.FETCHDATA_IMPL_PASS_EMPTY_REQUIREMENT_ID == "QF-022"
    assert runtime.FETCHDATA_IMPL_PASS_EMPTY_SOURCE_DOCUMENT == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    assert runtime.FETCHDATA_IMPL_PASS_EMPTY_CLAUSE == "pass_empty=19"
    assert runtime.FETCHDATA_IMPL_PASS_EMPTY_BASELINE_COUNT == 19
    assert runtime.BASELINE_PASS_EMPTY_COUNT == runtime.FETCHDATA_IMPL_PASS_EMPTY_BASELINE_COUNT


def test_runtime_fetchdata_impl_callable_no_runtime_blockage_anchor_matches_qf_023_clause() -> None:
    assert runtime.FETCHDATA_IMPL_CALLABLE_NO_RUNTIME_BLOCKAGE_REQUIREMENT_ID == "QF-023"
    assert (
        runtime.FETCHDATA_IMPL_CALLABLE_NO_RUNTIME_BLOCKAGE_SOURCE_DOCUMENT
        == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    )
    assert (
        runtime.FETCHDATA_IMPL_CALLABLE_NO_RUNTIME_BLOCKAGE_CLAUSE
        == "结论：基线函数均可调用（按当前 smoke 口径），无 runtime 阻塞。"
    )
    assert runtime.FETCHDATA_IMPL_CALLABLE_BASELINE_COUNT == runtime.BASELINE_FUNCTION_COUNT
    assert runtime.FETCHDATA_IMPL_RUNTIME_BLOCKED_SOURCE_MISSING_BASELINE_COUNT == 0
    assert runtime.FETCHDATA_IMPL_RUNTIME_ERROR_BASELINE_COUNT == 0


def test_runtime_fetchdata_impl_runtime_entrypoints_baseline_anchor_matches_qf_024_clause() -> None:
    assert runtime.FETCHDATA_IMPL_RUNTIME_ENTRYPOINTS_BASELINE_REQUIREMENT_ID == "QF-024"
    assert (
        runtime.FETCHDATA_IMPL_RUNTIME_ENTRYPOINTS_BASELINE_SOURCE_DOCUMENT
        == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    )
    assert (
        runtime.FETCHDATA_IMPL_RUNTIME_ENTRYPOINTS_BASELINE_CLAUSE
        == "QA‑Fetch FetchData Implementation Spec (v1) / 1. 现有事实基线（必须保持可回归） / 1.3 运行入口（已存在）"
    )
    assert runtime.RUNTIME_ENTRYPOINT_NAMES == ("execute_fetch_by_intent", "execute_fetch_by_name")
    for name in runtime.RUNTIME_ENTRYPOINT_NAMES:
        assert callable(getattr(runtime, name))


def test_runtime_intent_entrypoint_matches_qf_026_clause() -> None:
    assert runtime.FETCHDATA_IMPL_RUNTIME_INTENT_ENTRYPOINT_REQUIREMENT_ID == "QF-026"
    assert (
        runtime.FETCHDATA_IMPL_RUNTIME_INTENT_ENTRYPOINT_SOURCE_DOCUMENT
        == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    )
    assert runtime.FETCHDATA_IMPL_RUNTIME_INTENT_ENTRYPOINT_CLAUSE == "`execute_fetch_by_intent(...)`"
    assert runtime.RUNTIME_INTENT_ENTRYPOINT_NAME == "execute_fetch_by_intent"
    assert getattr(runtime, runtime.RUNTIME_INTENT_ENTRYPOINT_NAME) is runtime.execute_fetch_by_intent


def test_runtime_name_entrypoint_matches_qf_027_clause() -> None:
    assert runtime.FETCHDATA_IMPL_RUNTIME_NAME_ENTRYPOINT_REQUIREMENT_ID == "QF-027"
    assert (
        runtime.FETCHDATA_IMPL_RUNTIME_NAME_ENTRYPOINT_SOURCE_DOCUMENT
        == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    )
    assert runtime.FETCHDATA_IMPL_RUNTIME_NAME_ENTRYPOINT_CLAUSE == "`execute_fetch_by_name(...)`"
    assert runtime.RUNTIME_NAME_ENTRYPOINT_NAME == "execute_fetch_by_name"
    assert getattr(runtime, runtime.RUNTIME_NAME_ENTRYPOINT_NAME) is runtime.execute_fetch_by_name


def test_runtime_top_level_goals_anchor_matches_qf_028_clause() -> None:
    assert runtime.FETCHDATA_IMPL_TOP_LEVEL_GOALS_REQUIREMENT_ID == "QF-028"
    assert (
        runtime.FETCHDATA_IMPL_TOP_LEVEL_GOALS_SOURCE_DOCUMENT
        == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    )
    assert (
        runtime.FETCHDATA_IMPL_TOP_LEVEL_GOALS_CLAUSE
        == "QA‑Fetch FetchData Implementation Spec (v1) / 2. 顶层设计目标（Goals）"
    )


def test_runtime_single_data_access_channel_anchor_matches_qf_029_clause() -> None:
    assert runtime.FETCHDATA_IMPL_SINGLE_DATA_ACCESS_CHANNEL_REQUIREMENT_ID == "QF-029"
    assert (
        runtime.FETCHDATA_IMPL_SINGLE_DATA_ACCESS_CHANNEL_SOURCE_DOCUMENT
        == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    )
    assert (
        runtime.FETCHDATA_IMPL_SINGLE_DATA_ACCESS_CHANNEL_CLAUSE
        == "QA‑Fetch FetchData Implementation Spec (v1) / 2. 顶层设计目标（Goals） / G1 单一取数通道（Single Data Access Channel）"
    )


def test_runtime_auditability_anchor_matches_qf_030_clause() -> None:
    assert runtime.FETCHDATA_IMPL_AUDITABILITY_REQUIREMENT_ID == "QF-030"
    assert runtime.FETCHDATA_IMPL_AUDITABILITY_SOURCE_DOCUMENT == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    assert runtime.FETCHDATA_IMPL_AUDITABILITY_SOURCE_DOCUMENT == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    assert (
        runtime.FETCHDATA_IMPL_AUDITABILITY_CLAUSE
        == "QA‑Fetch FetchData Implementation Spec (v1) / 2. 顶层设计目标（Goals） / G2 证据链可审计（Auditability）"
    )


def test_runtime_no_lookahead_anchor_matches_qf_031_clause() -> None:
    assert runtime.FETCHDATA_IMPL_NO_LOOKAHEAD_REQUIREMENT_ID == "QF-031"
    assert runtime.FETCHDATA_IMPL_NO_LOOKAHEAD_SOURCE_DOCUMENT == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    assert runtime.FETCHDATA_IMPL_NO_LOOKAHEAD_SOURCE_DOCUMENT == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    assert runtime.FETCHDATA_IMPL_NO_LOOKAHEAD_CLAUSE == "no‑lookahead（防前视）；"
    assert runtime.NO_LOOKAHEAD_GATE_NAME == "no_lookahead"


def test_runtime_structural_sanity_anchor_matches_qf_032_clause() -> None:
    assert runtime.FETCHDATA_IMPL_STRUCTURAL_SANITY_REQUIREMENT_ID == "QF-032"
    assert runtime.FETCHDATA_IMPL_STRUCTURAL_SANITY_SOURCE_DOCUMENT == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    assert runtime.FETCHDATA_IMPL_STRUCTURAL_SANITY_SOURCE_DOCUMENT == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    assert runtime.FETCHDATA_IMPL_STRUCTURAL_SANITY_CLAUSE == "数据结构性 sanity checks；"


def test_runtime_golden_queries_anchor_matches_qf_033_clause() -> None:
    assert runtime.FETCHDATA_IMPL_GOLDEN_QUERIES_REQUIREMENT_ID == "QF-033"
    assert runtime.FETCHDATA_IMPL_GOLDEN_QUERIES_SOURCE_DOCUMENT == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    assert runtime.FETCHDATA_IMPL_GOLDEN_QUERIES_SOURCE_DOCUMENT == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    assert runtime.FETCHDATA_IMPL_GOLDEN_QUERIES_CLAUSE == "Golden Queries 回归与漂移报告（最小集）。"
    assert runtime.FETCHDATA_IMPL_GOLDEN_QUERIES_MIN_SET_RULE == "golden_query_minimal_set_non_empty"
    assert runtime.GOLDEN_QUERY_MIN_SET_MIN_QUERIES == 1


def test_runtime_adaptive_data_planning_anchor_matches_qf_034_clause() -> None:
    assert runtime.FETCHDATA_IMPL_ADAPTIVE_DATA_PLANNING_REQUIREMENT_ID == "QF-034"
    assert (
        runtime.FETCHDATA_IMPL_ADAPTIVE_DATA_PLANNING_SOURCE_DOCUMENT
        == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    )
    assert runtime.FETCHDATA_IMPL_ADAPTIVE_DATA_PLANNING_SOURCE_DOCUMENT == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    assert (
        runtime.FETCHDATA_IMPL_ADAPTIVE_DATA_PLANNING_CLAUSE
        == "QA‑Fetch FetchData Implementation Spec (v1) / 2. 顶层设计目标（Goals） / G4 自适应取数（Adaptive Data Planning）"
    )


def test_runtime_list_sample_day_anchor_matches_qf_035_clause() -> None:
    assert runtime.FETCHDATA_IMPL_LIST_SAMPLE_DAY_REQUIREMENT_ID == "QF-035"
    assert runtime.FETCHDATA_IMPL_LIST_SAMPLE_DAY_SOURCE_DOCUMENT == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    assert runtime.FETCHDATA_IMPL_LIST_SAMPLE_DAY_SOURCE_DOCUMENT == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    assert runtime.FETCHDATA_IMPL_LIST_SAMPLE_DAY_CLAUSE == "*_list → 选择样本 → *_day（例如 MA250 年线用例）"
    assert runtime.AUTO_SYMBOLS_MA250_STEP_SEQUENCE == ("list", "sample", "day")


def test_runtime_review_rollback_anchor_matches_qf_036_clause() -> None:
    assert runtime.FETCHDATA_IMPL_REVIEW_ROLLBACK_REQUIREMENT_ID == "QF-036"
    assert runtime.FETCHDATA_IMPL_REVIEW_ROLLBACK_SOURCE_DOCUMENT == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    assert runtime.FETCHDATA_IMPL_REVIEW_ROLLBACK_SOURCE_DOCUMENT == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    assert (
        runtime.FETCHDATA_IMPL_REVIEW_ROLLBACK_CLAUSE
        == "QA‑Fetch FetchData Implementation Spec (v1) / 2. 顶层设计目标（Goals） / G5 UI 可审阅与可回退（Review & Rollback）"
    )


def test_runtime_interfaces_umbrella_anchor_matches_qf_037_clause() -> None:
    assert runtime.FETCHDATA_IMPL_INTERFACES_UMBRELLA_REQUIREMENT_ID == "QF-037"
    assert (
        runtime.FETCHDATA_IMPL_INTERFACES_UMBRELLA_SOURCE_DOCUMENT
        == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    )
    assert runtime.FETCHDATA_IMPL_INTERFACES_UMBRELLA_SOURCE_DOCUMENT == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    assert (
        runtime.FETCHDATA_IMPL_INTERFACES_UMBRELLA_CLAUSE
        == "QA‑Fetch FetchData Implementation Spec (v1) / 3. 对外接口与 Contracts（Interfaces）"
    )


def test_runtime_fetch_request_v1_anchor_matches_qf_038_clause() -> None:
    assert runtime.FETCHDATA_IMPL_FETCH_REQUEST_V1_REQUIREMENT_ID == "QF-038"
    assert (
        runtime.FETCHDATA_IMPL_FETCH_REQUEST_V1_SOURCE_DOCUMENT
        == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    )
    assert runtime.FETCHDATA_IMPL_FETCH_REQUEST_V1_SOURCE_DOCUMENT == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    assert (
        runtime.FETCHDATA_IMPL_FETCH_REQUEST_V1_CLAUSE
        == "QA‑Fetch FetchData Implementation Spec (v1) / 3. 对外接口与 Contracts（Interfaces） / 3.1 FetchRequest v1（intent-first）"
    )
    assert runtime.FETCH_REQUEST_V1_INTENT_MODE == "intent_first"
    assert runtime.FETCH_REQUEST_V1_FUNCTION_MODE == "strong_control_function"
    assert runtime.FETCH_REQUEST_V1_SAMPLE_KEYS == ("n", "method")


def test_runtime_fetch_request_mode_anchor_matches_qf_039_clause() -> None:
    assert runtime.FETCHDATA_IMPL_FETCH_REQUEST_MODE_REQUIREMENT_ID == "QF-039"
    assert runtime.FETCHDATA_IMPL_FETCH_REQUEST_MODE_SOURCE_DOCUMENT == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    assert runtime.FETCHDATA_IMPL_FETCH_REQUEST_MODE_CLAUSE == "mode: demo | backtest"
    assert runtime.FETCH_REQUEST_MODE_TO_POLICY_MODE == {"demo": "demo", "backtest": "backtest"}


def test_runtime_fetch_request_intent_core_anchor_matches_qf_040_clause() -> None:
    assert runtime.FETCHDATA_IMPL_FETCH_REQUEST_INTENT_CORE_REQUIREMENT_ID == "QF-040"
    assert runtime.FETCHDATA_IMPL_FETCH_REQUEST_INTENT_CORE_SOURCE_DOCUMENT == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    assert runtime.FETCHDATA_IMPL_FETCH_REQUEST_INTENT_CORE_CLAUSE == "asset, freq, (universe/venue), adjust"
    assert runtime.FETCH_REQUEST_V1_INTENT_CORE_FIELDS == ("asset", "freq", "universe_or_venue", "adjust")


def test_runtime_fetch_request_optional_symbols_anchor_matches_qf_041_clause() -> None:
    assert runtime.FETCHDATA_IMPL_FETCH_REQUEST_SYMBOLS_OPTIONAL_REQUIREMENT_ID == "QF-041"
    assert (
        runtime.FETCHDATA_IMPL_FETCH_REQUEST_SYMBOLS_OPTIONAL_SOURCE_DOCUMENT
        == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    )
    assert runtime.FETCHDATA_IMPL_FETCH_REQUEST_SYMBOLS_OPTIONAL_CLAUSE == "symbols（可为空/缺省）"
    assert runtime.FETCH_REQUEST_V1_SYMBOLS_OPTIONAL_BEHAVIOR == "symbols_optional_allow_empty_or_omitted"
    assert (
        runtime.FETCH_REQUEST_V1_SYMBOLS_NORMALIZATION_BEHAVIOR
        == "empty_or_missing_symbols_normalize_to_omitted_selector"
    )


def test_runtime_fetch_request_optional_fields_anchor_matches_qf_042_clause() -> None:
    assert runtime.FETCHDATA_IMPL_FETCH_REQUEST_FIELDS_OPTIONAL_REQUIREMENT_ID == "QF-042"
    assert runtime.FETCHDATA_IMPL_FETCH_REQUEST_FIELDS_OPTIONAL_SOURCE_DOCUMENT == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    assert runtime.FETCHDATA_IMPL_FETCH_REQUEST_FIELDS_OPTIONAL_CLAUSE == "fields（可选，技术指标默认 OHLCV）"
    assert runtime.FETCH_REQUEST_V1_FIELDS_DEFAULT_ALIAS == "OHLCV"
    assert (
        runtime.FETCH_REQUEST_V1_FIELDS_DEFAULT_BEHAVIOR
        == "when_fields_omitted_runtime_defaults_to_ohlcv_for_technical_indicators"
    )


def test_runtime_correctness_umbrella_anchor_matches_qf_076_clause() -> None:
    assert runtime.FETCHDATA_IMPL_CORRECTNESS_UMBRELLA_REQUIREMENT_ID == "QF-076"
    assert runtime.FETCHDATA_IMPL_CORRECTNESS_UMBRELLA_SOURCE_DOCUMENT == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    assert runtime.FETCHDATA_IMPL_CORRECTNESS_UMBRELLA_CLAUSE == (
        "QA‑Fetch FetchData Implementation Spec (v1) / 6. 正确性保障（Correctness）"
    )


def test_runtime_correctness_umbrella_clause_mapping_links_subclauses() -> None:
    assert runtime.FETCHDATA_IMPL_CORRECTNESS_UMBRELLA_SUBCLAUSE_REQUIREMENT_IDS == (
        "QF-077",
        "QF-078",
        "QF-079",
        "QF-087",
        "QF-088",
    )
    assert runtime.FETCHDATA_IMPL_CORRECTNESS_UMBRELLA_CLAUSE_MAPPING == {
        "6.1 time-travel 可得性": (runtime.TIME_TRAVEL_AVAILABILITY_RULE,),
        "6.2 Gate 双重约束": (
            runtime.NO_LOOKAHEAD_GATE_NAME,
            runtime.DATA_SNAPSHOT_INTEGRITY_GATE_NAME,
            runtime.FETCH_EVIDENCE_SNAPSHOT_MANIFEST_GATE_FAIL_RULE,
        ),
    }


def test_runtime_time_travel_rule_anchor_matches_clause() -> None:
    assert runtime.TIME_TRAVEL_AVAILABILITY_RULE == "available_at<=as_of"
    assert runtime.TIME_TRAVEL_HISTORICAL_SELECTION_RULE == "select_historical_rows_where_available_at_lte_as_of"
    assert runtime.TIME_TRAVEL_UNAVAILABLE_REASON == "time_travel_unavailable"


def test_runtime_time_travel_availability_anchor_matches_qf_077_clause() -> None:
    assert runtime.FETCHDATA_IMPL_TIME_TRAVEL_AVAILABILITY_REQUIREMENT_ID == "QF-077"
    assert runtime.FETCHDATA_IMPL_TIME_TRAVEL_AVAILABILITY_SOURCE_DOCUMENT == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    assert runtime.FETCHDATA_IMPL_TIME_TRAVEL_AVAILABILITY_CLAUSE == (
        "QA‑Fetch FetchData Implementation Spec (v1) / 6. 正确性保障（Correctness） / 6.1 time-travel 可得性"
    )


def test_runtime_datacatalog_available_at_as_of_anchor_matches_qf_078_clause() -> None:
    assert runtime.FETCHDATA_IMPL_DATACATALOG_AVAILABLE_AT_AS_OF_REQUIREMENT_ID == "QF-078"
    assert (
        runtime.FETCHDATA_IMPL_DATACATALOG_AVAILABLE_AT_AS_OF_SOURCE_DOCUMENT
        == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    )
    assert runtime.FETCHDATA_IMPL_DATACATALOG_AVAILABLE_AT_AS_OF_CLAUSE == "DataCatalog 层必须强制 available_at <= as_of；"


def test_runtime_fetch_evidence_as_of_availability_anchor_matches_qf_079_clause() -> None:
    assert runtime.FETCHDATA_IMPL_FETCH_EVIDENCE_AS_OF_AVAILABILITY_REQUIREMENT_ID == "QF-079"
    assert (
        runtime.FETCHDATA_IMPL_FETCH_EVIDENCE_AS_OF_AVAILABILITY_SOURCE_DOCUMENT
        == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    )
    assert (
        runtime.FETCHDATA_IMPL_FETCH_EVIDENCE_AS_OF_AVAILABILITY_CLAUSE
        == "fetch 证据必须记录 as_of 与可得性相关摘要（用于复盘与 gate 解释）。"
    )
    assert runtime.FETCH_EVIDENCE_AS_OF_NORMALIZED_UTC_FORMAT == "YYYY-MM-DDTHH:MM:SSZ"
    assert runtime.FETCH_RESULT_META_AS_OF_FIELD == "as_of"
    assert runtime.FETCH_RESULT_META_AVAILABILITY_SUMMARY_FIELD == "availability_summary"


def test_runtime_intent_window_fields_anchor_matches_qf_044_clause() -> None:
    assert runtime.INTENT_REQUIRED_WINDOW_FIELDS == ("start", "end")


def test_runtime_intent_default_fields_anchor_matches_qf_045_clause() -> None:
    assert runtime.INTENT_DEFAULT_FIELDS_OHLCV == ("open", "high", "low", "close", "volume")


def test_runtime_planner_technical_indicator_default_data_shape_anchor_matches_qf_073_clause() -> None:
    assert runtime.FETCHDATA_IMPL_PLANNER_TECHNICAL_INDICATOR_DEFAULT_DATA_SHAPE_REQUIREMENT_ID == "QF-073"
    assert (
        runtime.FETCHDATA_IMPL_PLANNER_TECHNICAL_INDICATOR_DEFAULT_DATA_SHAPE_SOURCE_DOCUMENT
        == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    )
    assert runtime.FETCHDATA_IMPL_PLANNER_TECHNICAL_INDICATOR_DEFAULT_DATA_SHAPE_CLAUSE == (
        "QA‑Fetch FetchData Implementation Spec (v1) / 5. 自适应规划规则（Planner Requirements） / "
        "5.2 技术指标默认数据形态"
    )
    assert runtime.TECHNICAL_INDICATOR_DEFAULT_FREQ == "day"
    assert runtime.TECHNICAL_INDICATOR_DEFAULT_DATA_SHAPE_RULE == (
        "default_freq_day_fields_ohlcv_adjust_raw_for_technical_indicator_tasks"
    )


def test_runtime_technical_indicator_min_fields_anchor_matches_qf_074_clause() -> None:
    assert runtime.FETCHDATA_IMPL_PLANNER_TECHNICAL_INDICATOR_DEFAULT_FIELDS_REQUIREMENT_ID == "QF-074"
    assert (
        runtime.FETCHDATA_IMPL_PLANNER_TECHNICAL_INDICATOR_DEFAULT_FIELDS_SOURCE_DOCUMENT
        == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    )
    assert runtime.FETCHDATA_IMPL_PLANNER_TECHNICAL_INDICATOR_DEFAULT_FIELDS_CLAUSE == "默认 fields 至少包含 OHLCV"
    assert runtime.TECHNICAL_INDICATOR_MIN_FIELDS_OHLCV == ("open", "high", "low", "close", "volume")


def test_runtime_technical_indicator_default_adjust_anchor_matches_qf_081_clause() -> None:
    assert runtime.TECHNICAL_INDICATOR_DEFAULT_ADJUST == "raw"


def test_runtime_gaterunner_required_gates_anchor_matches_qf_081_clause() -> None:
    assert runtime.FETCHDATA_IMPL_GATERUNNER_DUAL_GATES_REQUIREMENT_ID == "QF-081"
    assert runtime.FETCHDATA_IMPL_GATERUNNER_DUAL_GATES_SOURCE_DOCUMENT == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    assert runtime.FETCHDATA_IMPL_GATERUNNER_DUAL_GATES_CLAUSE == (
        "GateRunner 必须包含 no_lookahead 与 data_snapshot_integrity（或等价 gates）；"
    )
    assert runtime.NO_LOOKAHEAD_GATE_NAME == "no_lookahead"
    assert runtime.DATA_SNAPSHOT_INTEGRITY_GATE_NAME == "data_snapshot_integrity"
    assert runtime.GATERUNNER_REQUIRED_GATES == ("no_lookahead", "data_snapshot_integrity")


def test_runtime_gate_dual_constraint_bundle_contract_non_regression() -> None:
    summary = runtime._build_gate_input_summary(
        request_hash="a" * 64,
        availability_summary={
            "rule": runtime.TIME_TRAVEL_AVAILABILITY_RULE,
            "has_as_of": True,
            "available_at_field_present": True,
            "available_at_violation_count": 1,
        },
        sanity_checks={
            "preview_row_count": 2,
            "timestamp_field": "date",
            "timestamp_order_rule": runtime.SANITY_TIMESTAMP_ORDER_RULE,
            "timestamp_duplicate_policy": runtime.SANITY_TIMESTAMP_DUPLICATE_POLICY,
            "timestamp_monotonic_non_decreasing": True,
            "timestamp_duplicate_count": 0,
            "timestamp_rule_satisfied": True,
            "missing_ratio_by_column": {"close": 0.25, "open": 0.0},
            "dtype_reasonable": False,
            "dtype_mismatch_columns": ["close"],
        },
    )

    assert tuple(summary.keys()) == runtime.GATERUNNER_REQUIRED_GATES
    assert tuple(summary.keys()) == ("no_lookahead", "data_snapshot_integrity")
    assert runtime.NO_LOOKAHEAD_GATE_NAME in summary
    assert runtime.DATA_SNAPSHOT_INTEGRITY_GATE_NAME in summary

    no_lookahead = summary[runtime.NO_LOOKAHEAD_GATE_NAME]
    assert no_lookahead["rule"] == runtime.TIME_TRAVEL_AVAILABILITY_RULE
    assert no_lookahead["has_as_of"] is True
    assert no_lookahead["available_at_field_present"] is True
    assert no_lookahead["available_at_violation_count"] == 1

    integrity = summary[runtime.DATA_SNAPSHOT_INTEGRITY_GATE_NAME]
    assert integrity["request_hash"] == "a" * 64
    assert integrity["preview_row_count"] == 2
    assert integrity["timestamp_field"] == "date"
    assert integrity["timestamp_order_rule"] == runtime.SANITY_TIMESTAMP_ORDER_RULE
    assert integrity["timestamp_duplicate_policy"] == runtime.SANITY_TIMESTAMP_DUPLICATE_POLICY
    assert integrity["timestamp_monotonic_non_decreasing"] is True
    assert integrity["timestamp_duplicate_count"] == 0
    assert integrity["timestamp_rule_satisfied"] is True
    assert integrity["nonzero_missing_ratio_columns"] == ["close"]
    assert integrity["dtype_reasonable"] is False
    assert integrity["dtype_mismatch_columns"] == ["close"]


def test_runtime_fetch_evidence_snapshot_manifest_gate_fail_rule_anchor_matches_qf_088_clause() -> None:
    assert runtime.FETCH_EVIDENCE_SNAPSHOT_MANIFEST_GATE_FAIL_RULE == (
        "gate_fail_when_fetch_evidence_or_snapshot_manifest_missing"
    )


def test_runtime_direct_gate_fail_anchor_matches_qf_107_clause() -> None:
    assert runtime.FETCHDATA_IMPL_DIRECT_GATE_FAIL_REQUIREMENT_ID == "QF-107"
    assert (
        runtime.FETCHDATA_IMPL_DIRECT_GATE_FAIL_SOURCE_DOCUMENT
        == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    )
    assert runtime.FETCHDATA_IMPL_DIRECT_GATE_FAIL_CLAUSE == "违规直接 gate fail。"
    assert (
        runtime.FETCH_RESULT_GATES_VIOLATION_RULE
        == "gate_fail_when_fetch_result_gate_summary_has_violations"
    )


def test_runtime_sanity_timestamp_order_rule_anchor_matches_qf_084_clause() -> None:
    assert runtime.SANITY_TIMESTAMP_ORDER_RULE == "timestamp_monotonic_increasing_and_no_duplicates_or_record_allow_rule"
    assert runtime.SANITY_TIMESTAMP_DUPLICATE_POLICY == "no_duplicates_allowed"


def test_runtime_qf_084_timestamp_rule_accepts_monotonic_increasing_preview() -> None:
    sanity = runtime._build_preview_sanity_checks(
        [
            {"date": "2024-01-01"},
            {"date": "2024-01-02"},
            {"date": "2024-01-03"},
        ]
    )

    assert sanity["timestamp_field"] == "date"
    assert sanity["timestamp_monotonic_non_decreasing"] is True
    assert sanity["timestamp_duplicate_count"] == 0
    assert sanity["timestamp_rule_satisfied"] is True
    assert sanity["timestamp_duplicate_policy"] == runtime.SANITY_TIMESTAMP_DUPLICATE_POLICY
    assert sanity["timestamp_duplicates_allowed"] is False


def test_runtime_qf_084_timestamp_rule_rejects_non_monotonic_preview() -> None:
    sanity = runtime._build_preview_sanity_checks(
        [
            {"date": "2024-01-03"},
            {"date": "2024-01-01"},
            {"date": "2024-01-02"},
        ]
    )

    assert sanity["timestamp_field"] == "date"
    assert sanity["timestamp_monotonic_non_decreasing"] is False
    assert sanity["timestamp_duplicate_count"] == 0
    assert sanity["timestamp_rule_satisfied"] is False


def test_runtime_qf_084_timestamp_rule_rejects_duplicates_and_records_policy() -> None:
    sanity = runtime._build_preview_sanity_checks(
        [
            {"date": "2024-01-01"},
            {"date": "2024-01-01"},
            {"date": "2024-01-02"},
        ]
    )

    assert sanity["timestamp_field"] == "date"
    assert sanity["timestamp_monotonic_non_decreasing"] is True
    assert sanity["timestamp_duplicate_count"] == 1
    assert sanity["timestamp_duplicate_policy"] == runtime.SANITY_TIMESTAMP_DUPLICATE_POLICY
    assert sanity["timestamp_duplicates_allowed"] is False
    assert sanity["timestamp_rule_satisfied"] is False


def test_runtime_sanity_dtype_and_missing_ratio_rule_anchor_matches_qf_083_clause() -> None:
    assert runtime.SANITY_DTYPE_REASONABLENESS_RULE == "dtype_reasonableness_against_preview_non_missing_values"
    assert runtime.SANITY_MISSING_RATIO_RULE == "column_level_missing_ratio_statistics"


def test_runtime_sanity_empty_data_policy_rule_anchor_matches_qf_091_clause() -> None:
    assert runtime.SANITY_EMPTY_DATA_POLICY_RULE == "empty_data_semantics_consistent_with_policy_on_no_data"


def test_runtime_golden_query_drift_report_path_rule_anchor_matches_qf_088_clause() -> None:
    assert runtime.FETCHDATA_IMPL_CORRECTNESS_DRIFT_REPORT_REQUIREMENT_ID == "QF-088"
    assert (
        runtime.FETCHDATA_IMPL_CORRECTNESS_DRIFT_REPORT_SOURCE_DOCUMENT
        == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    )
    assert (
        runtime.FETCHDATA_IMPL_CORRECTNESS_DRIFT_REPORT_CLAUSE
        == "漂移必须产出报告（报告文件位置由主控定义，但必须可被 CI 或 nightly 读取）"
    )
    assert runtime.GOLDEN_QUERY_DRIFT_REPORT_PATH_RULE == "controller_defined_report_path_ci_nightly_readable"
    assert runtime.GOLDEN_QUERY_DRIFT_REPORT_SCHEMA_VERSION == "qa_fetch_golden_drift_report_v1"
    assert runtime.GOLDEN_QUERY_SUMMARY_SCHEMA_VERSION == "qa_fetch_golden_summary_v1"


def test_runtime_golden_query_correctness_anchor_matches_qf_086_clause() -> None:
    assert runtime.FETCHDATA_IMPL_CORRECTNESS_GOLDEN_QUERIES_REQUIREMENT_ID == "QF-086"
    assert runtime.FETCHDATA_IMPL_CORRECTNESS_GOLDEN_QUERIES_SOURCE_DOCUMENT == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    assert runtime.FETCHDATA_IMPL_CORRECTNESS_GOLDEN_QUERIES_CLAUSE == (
        "QA‑Fetch FetchData Implementation Spec (v1) / 6. 正确性保障（Correctness） / 6.4 Golden Queries（回归与漂移）"
    )
    assert runtime.GOLDEN_QUERY_FIXED_SET_RULE == "fixed_query_set_with_expected_outputs"
    assert runtime.GOLDEN_QUERY_EXPECTED_OUTPUT_FIELDS == ("status", "request_hash", "row_count", "columns")


def test_runtime_golden_query_fixed_request_output_anchor_matches_qf_087_clause() -> None:
    assert runtime.FETCHDATA_IMPL_CORRECTNESS_FIXED_REQUEST_OUTPUT_REQUIREMENT_ID == "QF-087"
    assert (
        runtime.FETCHDATA_IMPL_CORRECTNESS_FIXED_REQUEST_OUTPUT_SOURCE_DOCUMENT
        == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    )
    assert runtime.FETCHDATA_IMPL_CORRECTNESS_FIXED_REQUEST_OUTPUT_CLAUSE == "固定请求 → 产出 meta/hash/row_count/columns"
    assert runtime.GOLDEN_QUERY_FIXED_REQUEST_ARTIFACT_FIELDS == ("meta", "request_hash", "row_count", "columns")


def test_runtime_orchestrator_regression_anchor_matches_qf_113_clause() -> None:
    assert runtime.FETCHDATA_IMPL_ORCHESTRATOR_CONTRACTS_REGRESSION_REQUIREMENT_ID == "QF-113"
    assert runtime.FETCHDATA_IMPL_ORCHESTRATOR_CONTRACTS_REGRESSION_SOURCE_DOCUMENT == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    assert (
        runtime.FETCHDATA_IMPL_ORCHESTRATOR_CONTRACTS_REGRESSION_SOURCE_DOCUMENT
        == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    )
    assert (
        runtime.FETCHDATA_IMPL_ORCHESTRATOR_CONTRACTS_REGRESSION_CLAUSE
        == "用于 contracts/orchestrator/tests 的自动化回归，不等价于 notebook kernel 结果。"
    )
    assert runtime.FETCHDATA_IMPL_ORCHESTRATOR_CONTRACTS_REGRESSION_EXECUTION_ENV == "host_terminal"
    assert runtime.FETCHDATA_IMPL_ORCHESTRATOR_CONTRACTS_REGRESSION_EXECUTION_ENV_RULE == "contracts/orchestrator_tests_host_terminal"


def test_runtime_host_terminal_baseline_sample_anchor_matches_qf_114_clause() -> None:
    assert runtime.FETCHDATA_IMPL_HOST_TERMINAL_BASELINE_SAMPLE_REQUIREMENT_ID == "QF-114"
    assert runtime.FETCHDATA_IMPL_HOST_TERMINAL_BASELINE_SAMPLE_SOURCE_DOCUMENT == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    assert runtime.FETCHDATA_IMPL_HOST_TERMINAL_BASELINE_SAMPLE_CLAUSE == (
        "QA‑Fetch FetchData Implementation Spec (v1) / 8. Definition of Done（主路闭环验收） / "
        "8.2 本轮已记录的宿主终端环境（基线样例）"
    )
    assert runtime.FETCHDATA_IMPL_HOST_TERMINAL_BASELINE_SAMPLE_RULE == (
        "record_host_terminal_environment_baseline_sample_for_contract_regression"
    )
    assert runtime.FETCHDATA_IMPL_HOST_TERMINAL_BASELINE_SAMPLE_REQUIRED_FIELDS == (
        "recorded_at_utc",
        "baseline_commit",
        "cwd",
        "shell_binary",
        "shell_process",
        "os_kernel",
        "python_bin",
        "python_version",
        "python_sys_executable",
        "python_sys_prefix",
        "python_sys_base_prefix",
        "virtual_env",
        "dot_venv_python",
        "pip_bin",
        "pip_version",
        "pytest_bin",
        "pytest_version",
        "ripgrep_bin",
        "ripgrep_version",
        "git_bin",
        "git_version",
        "pandas_version",
        "numpy_version",
        "shell_mount_namespace",
    )


def test_runtime_intent_auto_symbols_anchor_matches_qf_043_clause() -> None:
    assert runtime.FETCHDATA_IMPL_FETCH_REQUEST_AUTO_SYMBOLS_REQUIREMENT_ID == "QF-043"
    assert runtime.FETCHDATA_IMPL_FETCH_REQUEST_AUTO_SYMBOLS_SOURCE_DOCUMENT == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    assert runtime.FETCHDATA_IMPL_FETCH_REQUEST_AUTO_SYMBOLS_CLAUSE == "auto_symbols（bool，可选）"
    assert runtime.INTENT_OPTIONAL_AUTO_SYMBOLS_BOOL == ("auto_symbols", "bool", "optional")
    assert runtime.AUTO_SYMBOLS_DEFAULT_ENABLED is False


def test_runtime_sample_anchor_matches_qf_044_clause() -> None:
    assert runtime.FETCHDATA_IMPL_FETCH_REQUEST_SAMPLE_REQUIREMENT_ID == "QF-044"
    assert runtime.FETCHDATA_IMPL_FETCH_REQUEST_SAMPLE_SOURCE_DOCUMENT == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    assert runtime.FETCHDATA_IMPL_FETCH_REQUEST_SAMPLE_CLAUSE == "sample（可选：n/method）"
    assert runtime.FETCH_REQUEST_V1_SAMPLE_KEYS == ("n", "method")


def test_runtime_policy_on_no_data_anchor_matches_qf_045_clause() -> None:
    assert runtime.FETCHDATA_IMPL_FETCH_REQUEST_ON_NO_DATA_REQUIREMENT_ID == "QF-045"
    assert runtime.FETCHDATA_IMPL_FETCH_REQUEST_ON_NO_DATA_SOURCE_DOCUMENT == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    assert runtime.FETCHDATA_IMPL_FETCH_REQUEST_ON_NO_DATA_CLAUSE == "on_no_data: error | pass_empty | retry"
    assert runtime.POLICY_ON_NO_DATA_OPTIONS == ("error", "pass_empty", "retry")


def test_runtime_policy_optional_execution_controls_anchor_matches_qf_046_clause() -> None:
    assert runtime.FETCHDATA_IMPL_FETCH_REQUEST_LIMITS_REQUIREMENT_ID == "QF-046"
    assert runtime.FETCHDATA_IMPL_FETCH_REQUEST_LIMITS_SOURCE_DOCUMENT == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    assert runtime.FETCHDATA_IMPL_FETCH_REQUEST_LIMITS_CLAUSE == "（可选）max_symbols/max_rows/retry_strategy"
    assert runtime.POLICY_OPTIONAL_EXECUTION_CONTROLS == ("max_symbols", "max_rows", "retry_strategy")


def test_runtime_fetch_request_fail_fast_anchor_matches_qf_047_clause() -> None:
    assert runtime.FETCHDATA_IMPL_FETCH_REQUEST_FAIL_FAST_REQUIREMENT_ID == "QF-047"
    assert runtime.FETCHDATA_IMPL_FETCH_REQUEST_FAIL_FAST_SOURCE_DOCUMENT == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    assert runtime.FETCHDATA_IMPL_FETCH_REQUEST_FAIL_FAST_CLAUSE == "FetchRequest 必须在编排前通过 schema+逻辑校验（非法直接 fail-fast）。"
    assert runtime.FETCH_REQUEST_V1_FAIL_FAST_ERROR_PREFIX == "fetch_request validation failed before orchestration"


def test_runtime_fetch_request_intent_function_exclusive_anchor_matches_qf_048_clause() -> None:
    assert runtime.FETCHDATA_IMPL_FETCH_REQUEST_INTENT_FUNCTION_EXCLUSIVE_REQUIREMENT_ID == "QF-048"
    assert (
        runtime.FETCHDATA_IMPL_FETCH_REQUEST_INTENT_FUNCTION_EXCLUSIVE_SOURCE_DOCUMENT
        == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    )
    assert (
        runtime.FETCHDATA_IMPL_FETCH_REQUEST_INTENT_FUNCTION_EXCLUSIVE_CLAUSE
        == "intent 与 function 只能二选一：默认 intent；只有“强控函数”场景才允许 function 模式。"
    )
    assert runtime.FETCH_REQUEST_V1_STRONG_CONTROL_FUNCTION_FIELD == "strong_control_function"


def test_runtime_fetch_result_meta_selected_function_field_anchor_matches_qf_050_clause() -> None:
    assert runtime.FETCH_RESULT_META_SELECTED_FUNCTION_FIELD == "selected_function"


def test_runtime_fetch_result_meta_engine_field_anchor_matches_qf_051_clause() -> None:
    assert runtime.FETCH_RESULT_META_ENGINE_FIELD == "engine"


def test_runtime_fetch_result_meta_engine_options_anchor_matches_qf_051_clause() -> None:
    assert runtime.FETCH_RESULT_META_ENGINE_OPTIONS == ("mongo", "mysql")


def test_runtime_fetch_result_meta_row_col_count_fields_anchor_matches_qf_052_clause() -> None:
    assert runtime.FETCH_RESULT_META_ROW_COL_COUNT_FIELDS == ("row_count", "col_count")


def test_runtime_fetch_result_meta_min_max_ts_fields_anchor_matches_qf_054_clause() -> None:
    assert runtime.FETCH_RESULT_META_MIN_MAX_TS_FIELDS == ("min_ts", "max_ts")


def test_runtime_fetch_result_meta_request_hash_field_anchor_matches_qf_053_clause() -> None:
    assert runtime.FETCH_RESULT_META_REQUEST_HASH_FIELD == "request_hash"
    assert runtime.FETCH_RESULT_META_REQUEST_HASH_VERSION_SALT == "qa_fetch_request_hash_v1"


def test_runtime_fetch_result_meta_optional_probe_status_options_anchor_matches_qf_055_clause() -> None:
    assert runtime.FETCH_RESULT_META_OPTIONAL_PROBE_STATUS_OPTIONS == ("pass_has_data", "pass_empty")


def test_runtime_fetch_evidence_bundle_dossier_clause_anchor_matches_qf_056_clause() -> None:
    assert runtime.FETCHDATA_IMPL_EVIDENCE_BUNDLE_REQUIREMENT_ID == "QF-056"
    assert runtime.FETCHDATA_IMPL_EVIDENCE_BUNDLE_SOURCE_DOCUMENT == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    assert runtime.FETCHDATA_IMPL_EVIDENCE_BUNDLE_CLAUSE == (
        "QA‑Fetch FetchData Implementation Spec (v1) / 4. Evidence Bundle 规范（必须进入 Dossier）"
    )
    assert runtime.FETCH_EVIDENCE_DOSSIER_ROOT_TEMPLATE == "artifacts/dossiers/<run_id>/fetch"
    assert runtime.FETCH_EVIDENCE_DOSSIER_ONE_HOP_RULE == "ui_reads_dossier_fetch_evidence_without_jobs_output_jumps"
    assert runtime.FETCH_EVIDENCE_DOSSIER_RUN_ID_KEYS == ("run_id", "dossier_run_id")


def test_runtime_fetch_evidence_single_step_quartet_clause_anchor_matches_qf_057_clause() -> None:
    assert runtime.FETCHDATA_IMPL_EVIDENCE_BUNDLE_SINGLE_STEP_REQUIREMENT_ID == "QF-057"
    assert (
        runtime.FETCHDATA_IMPL_EVIDENCE_BUNDLE_SINGLE_STEP_SOURCE_DOCUMENT
        == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    )
    assert runtime.FETCHDATA_IMPL_EVIDENCE_BUNDLE_SINGLE_STEP_CLAUSE == (
        "QA‑Fetch FetchData Implementation Spec (v1) / 4. Evidence Bundle 规范（必须进入 Dossier） / 4.1 单步证据（四件套）"
    )
    assert runtime.FETCH_EVIDENCE_SINGLE_STEP_REQUIRED_FILES == (
        "fetch_request.json",
        "fetch_result_meta.json",
        "fetch_preview.csv",
    )
    assert runtime.FETCH_EVIDENCE_SINGLE_STEP_FAILURE_FILE == "fetch_error.json"
    assert runtime.FETCH_EVIDENCE_SINGLE_STEP_FAILURE_RULE == "failure_requires_fetch_error_json"
    assert runtime.FETCH_EVIDENCE_SINGLE_STEP_SUCCESS_RULE == "success_must_not_emit_fetch_error_json"


def test_resolve_optional_probe_status_accepts_only_qf_055_values() -> None:
    assert runtime._resolve_optional_probe_status(runtime.STATUS_PASS_HAS_DATA) == runtime.STATUS_PASS_HAS_DATA
    assert runtime._resolve_optional_probe_status(runtime.STATUS_PASS_EMPTY) == runtime.STATUS_PASS_EMPTY
    assert runtime._resolve_optional_probe_status(runtime.STATUS_ERROR_RUNTIME) is None
    assert runtime._resolve_optional_probe_status(runtime.STATUS_BLOCKED_SOURCE_MISSING) is None
    assert runtime._resolve_optional_probe_status(None) is None


def test_runtime_fetch_result_meta_warnings_field_anchor_matches_spec_clause() -> None:
    assert runtime.FETCH_RESULT_META_WARNINGS_FIELD == "warnings"


def test_runtime_fetch_evidence_request_filename_anchor_matches_qf_058_clause() -> None:
    assert runtime.FETCHDATA_IMPL_EVIDENCE_FETCH_REQUEST_REQUIREMENT_ID == "QF-058"
    assert runtime.FETCHDATA_IMPL_EVIDENCE_FETCH_REQUEST_SOURCE_DOCUMENT == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    assert runtime.FETCHDATA_IMPL_EVIDENCE_FETCH_REQUEST_CLAUSE == "fetch_request.json"
    assert runtime.FETCH_EVIDENCE_REQUEST_FILENAME == "fetch_request.json"


def test_runtime_fetch_evidence_result_meta_filename_anchor_matches_qf_059_clause() -> None:
    assert runtime.FETCHDATA_IMPL_EVIDENCE_FETCH_RESULT_META_REQUIREMENT_ID == "QF-059"
    assert (
        runtime.FETCHDATA_IMPL_EVIDENCE_FETCH_RESULT_META_SOURCE_DOCUMENT == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    )
    assert runtime.FETCHDATA_IMPL_EVIDENCE_FETCH_RESULT_META_CLAUSE == "fetch_result_meta.json"
    assert runtime.FETCH_EVIDENCE_RESULT_META_FILENAME == "fetch_result_meta.json"


def test_runtime_fetch_evidence_preview_filename_anchor_matches_qf_060_clause() -> None:
    assert runtime.FETCHDATA_IMPL_EVIDENCE_FETCH_PREVIEW_REQUIREMENT_ID == "QF-060"
    assert runtime.FETCHDATA_IMPL_EVIDENCE_FETCH_PREVIEW_SOURCE_DOCUMENT == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    assert runtime.FETCHDATA_IMPL_EVIDENCE_FETCH_PREVIEW_CLAUSE == "fetch_preview.csv"
    assert runtime.FETCH_EVIDENCE_PREVIEW_FILENAME == "fetch_preview.csv"


def test_runtime_fetch_evidence_error_filename_anchor_matches_qf_061_clause() -> None:
    assert runtime.FETCHDATA_IMPL_EVIDENCE_FETCH_ERROR_REQUIREMENT_ID == "QF-061"
    assert runtime.FETCHDATA_IMPL_EVIDENCE_FETCH_ERROR_SOURCE_DOCUMENT == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    assert runtime.FETCHDATA_IMPL_EVIDENCE_FETCH_ERROR_CLAUSE == "fetch_error.json（仅失败时，但失败必须有）"
    assert runtime.FETCH_EVIDENCE_ERROR_FILENAME == "fetch_error.json"


def test_runtime_fetch_evidence_multistep_clause_anchor_matches_qf_062_clause() -> None:
    assert runtime.FETCHDATA_IMPL_EVIDENCE_BUNDLE_MULTI_STEP_REQUIREMENT_ID == "QF-062"
    assert (
        runtime.FETCHDATA_IMPL_EVIDENCE_BUNDLE_MULTI_STEP_SOURCE_DOCUMENT
        == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    )
    assert runtime.FETCHDATA_IMPL_EVIDENCE_BUNDLE_MULTI_STEP_CLAUSE == (
        "QA‑Fetch FetchData Implementation Spec (v1) / 4. Evidence Bundle 规范（必须进入 Dossier） / 4.2 多步证据（step index）"
    )
    assert (
        runtime.FETCH_EVIDENCE_MULTI_STEP_STEP_INDEX_RULE
        == "dossier_multistep_steps_must_include_explicit_step_index"
    )


def test_runtime_fetch_evidence_dossier_archive_clause_anchor_matches_qf_065_clause() -> None:
    assert runtime.FETCHDATA_IMPL_EVIDENCE_DOSSIER_ARCHIVE_REQUIREMENT_ID == "QF-065"
    assert runtime.FETCHDATA_IMPL_EVIDENCE_DOSSIER_ARCHIVE_SOURCE_DOCUMENT == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    assert runtime.FETCHDATA_IMPL_EVIDENCE_DOSSIER_ARCHIVE_CLAUSE == (
        "QA‑Fetch FetchData Implementation Spec (v1) / 4. Evidence Bundle 规范（必须进入 Dossier） / 4.3 Dossier 归档要求"
    )
    assert runtime.FETCH_EVIDENCE_DOSSIER_ARCHIVE_ROOT_TEMPLATE == "artifacts/dossiers/<run_id>/fetch"
    assert (
        runtime.FETCH_EVIDENCE_DOSSIER_ARCHIVE_ONE_HOP_RULE
        == "ui_reads_dossier_fetch_evidence_without_jobs_output_jumps"
    )


def test_runtime_fetch_evidence_ui_dossier_viewer_clause_anchor_matches_qf_066_clause() -> None:
    assert runtime.FETCHDATA_IMPL_UI_DOSSIER_FETCH_EVIDENCE_REQUIREMENT_ID == "QF-066"
    assert runtime.FETCHDATA_IMPL_UI_DOSSIER_FETCH_EVIDENCE_SOURCE_DOCUMENT == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    assert runtime.FETCHDATA_IMPL_UI_DOSSIER_FETCH_EVIDENCE_CLAUSE == (
        "UI 只读 Dossier 即可展示 fetch evidence（不需要跳转 jobs outputs 路径）。"
    )
    assert runtime.UI_DOSSIER_FETCH_EVIDENCE_FIELD == "dossier_fetch_evidence"
    assert runtime.UI_DOSSIER_FETCH_EVIDENCE_READ_MODE == "read_only_dossier"
    assert (
        runtime.UI_DOSSIER_FETCH_EVIDENCE_PATH_RULE
        == "dossier_payload_paths_must_resolve_under_artifacts_dossiers_run_id_fetch"
    )
    assert runtime.UI_DOSSIER_FETCH_EVIDENCE_REQUIRED_PATH_KEYS == runtime.UI_REVIEWABLE_FETCH_EVIDENCE_ARTIFACT_KEYS


def test_runtime_planner_requirements_umbrella_anchor_matches_qf_067_clause() -> None:
    assert runtime.FETCHDATA_IMPL_PLANNER_REQUIREMENTS_UMBRELLA_REQUIREMENT_ID == "QF-067"
    assert (
        runtime.FETCHDATA_IMPL_PLANNER_REQUIREMENTS_UMBRELLA_SOURCE_DOCUMENT
        == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    )
    assert (
        runtime.FETCHDATA_IMPL_PLANNER_REQUIREMENTS_UMBRELLA_SOURCE_DOCUMENT
        == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    )
    assert runtime.FETCHDATA_IMPL_PLANNER_REQUIREMENTS_UMBRELLA_CLAUSE == (
        "QA‑Fetch FetchData Implementation Spec (v1) / 5. 自适应规划规则（Planner Requirements）"
    )


def test_runtime_planner_symbols_omitted_required_behavior_anchor_matches_qf_068_clause() -> None:
    assert runtime.FETCHDATA_IMPL_PLANNER_SYMBOLS_OMITTED_REQUIREMENT_ID == "QF-068"
    assert runtime.FETCHDATA_IMPL_PLANNER_SYMBOLS_OMITTED_SOURCE_DOCUMENT == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    assert runtime.FETCHDATA_IMPL_PLANNER_SYMBOLS_OMITTED_CLAUSE == (
        "QA‑Fetch FetchData Implementation Spec (v1) / 5. 自适应规划规则（Planner Requirements） / "
        "5.1 symbols 缺省时的必备行为"
    )
    assert runtime.AUTO_SYMBOLS_REQUIRED_TRIGGER_RULE == "when_symbols_missing_and_auto_symbols_true_run_planner"
    assert runtime.AUTO_SYMBOLS_DEFAULT_DERIVATION_RULE == "derive_symbols_from_list_candidates_then_sample"
    assert runtime.AUTO_SYMBOLS_FALLBACK_RULE == "fallback_to_error_runtime_when_no_sampled_symbols"


def test_runtime_planner_list_sample_day_step_evidence_anchor_matches_qf_069_to_qf_072() -> None:
    assert runtime.FETCHDATA_IMPL_PLANNER_LIST_CANDIDATES_REQUIREMENT_ID == "QF-069"
    assert runtime.FETCHDATA_IMPL_PLANNER_LIST_CANDIDATES_SOURCE_DOCUMENT == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    assert runtime.FETCHDATA_IMPL_PLANNER_LIST_CANDIDATES_CLAUSE == "先执行对应 *_list 获取候选集合；"
    assert runtime.FETCHDATA_IMPL_PLANNER_SAMPLE_STRATEGY_REQUIREMENT_ID == "QF-070"
    assert runtime.FETCHDATA_IMPL_PLANNER_SAMPLE_STRATEGY_SOURCE_DOCUMENT == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    assert runtime.FETCHDATA_IMPL_PLANNER_SAMPLE_STRATEGY_CLAUSE == "执行 sample（随机/流动性/行业分层等，具体策略由主控决定）；"
    assert runtime.FETCHDATA_IMPL_PLANNER_DAY_FETCH_REQUIREMENT_ID == "QF-071"
    assert runtime.FETCHDATA_IMPL_PLANNER_DAY_FETCH_SOURCE_DOCUMENT == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    assert runtime.FETCHDATA_IMPL_PLANNER_DAY_FETCH_CLAUSE == "再执行 *_day 拉取行情数据；"
    assert runtime.FETCHDATA_IMPL_PLANNER_STEP_EVIDENCE_REQUIREMENT_ID == "QF-072"
    assert runtime.FETCHDATA_IMPL_PLANNER_STEP_EVIDENCE_SOURCE_DOCUMENT == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    assert runtime.FETCHDATA_IMPL_PLANNER_STEP_EVIDENCE_CLAUSE == "每一步必须落 step evidence（可审计）。"
    assert runtime.AUTO_SYMBOLS_SAMPLE_STRATEGY_CONFIG_RULE == "controller_configurable_sample_strategy_with_params"
    assert runtime.AUTO_SYMBOLS_STEP_EVIDENCE_REQUIRED_FIELDS == (
        "generated_at",
        "input_summary",
        "output_summary",
        "trace_id",
    )
    assert runtime.AUTO_SYMBOLS_MA250_STEP_SEQUENCE == ("list", "sample", "day")


def test_runtime_fetch_evidence_steps_index_filename_anchor_matches_qf_063_clause() -> None:
    assert runtime.FETCHDATA_IMPL_EVIDENCE_FETCH_STEPS_INDEX_REQUIREMENT_ID == "QF-063"
    assert (
        runtime.FETCHDATA_IMPL_EVIDENCE_FETCH_STEPS_INDEX_SOURCE_DOCUMENT
        == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    )
    assert runtime.FETCHDATA_IMPL_EVIDENCE_FETCH_STEPS_INDEX_CLAUSE == "fetch_steps_index.json"
    assert runtime.FETCH_EVIDENCE_STEPS_INDEX_FILENAME == "fetch_steps_index.json"


def test_runtime_ui_review_rollback_umbrella_anchor_matches_qf_089_clause() -> None:
    assert runtime.FETCHDATA_IMPL_UI_REVIEW_ROLLBACK_UMBRELLA_REQUIREMENT_ID == "QF-089"
    assert runtime.FETCHDATA_IMPL_UI_REVIEW_ROLLBACK_UMBRELLA_SOURCE_DOCUMENT == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    assert runtime.FETCHDATA_IMPL_UI_REVIEW_ROLLBACK_UMBRELLA_CLAUSE == (
        "QA‑Fetch FetchData Implementation Spec (v1) / 7. UI 集成要求（Review & Rollback）"
    )
    assert runtime.FETCHDATA_IMPL_UI_REVIEW_ROLLBACK_UMBRELLA_SUBCLAUSE_REQUIREMENT_IDS == (
        "QF-090",
        "QF-091",
        "QF-092",
        "QF-093",
        "QF-094",
        "QF-095",
        "QF-096",
    )
    assert runtime.FETCHDATA_IMPL_UI_REVIEW_ROLLBACK_UMBRELLA_CLAUSE_MAPPING == {
        "7.1 Fetch Evidence Viewer": (
            runtime.UI_FETCH_EVIDENCE_VIEWER_STEPS_INDEX_FILENAME,
            runtime.UI_FETCH_EVIDENCE_VIEWER_STEP_META_PREVIEW_RULE,
            runtime.UI_FETCH_EVIDENCE_VIEWER_ERROR_FILENAME,
            runtime.UI_FETCH_EVIDENCE_VIEWER_ERROR_EXPOSURE_RULE,
        ),
        "7.2 审阅点与回退": (
            runtime.FETCH_REVIEW_CHECKPOINT_APPROVE_TRANSITION,
            runtime.FETCH_REVIEW_CHECKPOINT_REJECT_TRANSITION,
            runtime.FETCH_EVIDENCE_APPEND_ONLY_RULE,
        ),
    }


def test_runtime_ui_fetch_evidence_viewer_steps_index_filename_anchor_matches_qf_090_clause() -> None:
    assert runtime.UI_FETCH_EVIDENCE_VIEWER_STEPS_INDEX_FILENAME == "fetch_steps_index.json"
    assert runtime.UI_FETCH_EVIDENCE_VIEWER_STEPS_INDEX_FILENAME == runtime.FETCH_EVIDENCE_STEPS_INDEX_FILENAME
    assert runtime.UI_FETCH_EVIDENCE_VIEWER_STEP_META_PREVIEW_FIELDS == ("result_meta_path", "preview_path")
    assert runtime.UI_FETCH_EVIDENCE_VIEWER_STEP_META_PREVIEW_RULE == "step_meta_preview_exposed_via_fetch_steps_index_steps"
    assert runtime.UI_FETCH_EVIDENCE_VIEWER_STATE_SCHEMA_VERSION == "qa_fetch_evidence_viewer_state_v1"
    assert (
        runtime.UI_FETCH_EVIDENCE_VIEWER_REVIEW_ROLLBACK_RULE
        == "fetch_evidence_viewer_exposes_review_checkpoint_rollback_entrypoint"
    )


def test_runtime_ui_fetch_evidence_viewer_error_filename_anchor_matches_qf_092_clause() -> None:
    assert runtime.UI_FETCH_EVIDENCE_VIEWER_ERROR_FILENAME == "error.json"
    assert runtime.UI_FETCH_EVIDENCE_VIEWER_ERROR_FILENAME != runtime.FETCH_EVIDENCE_ERROR_FILENAME
    assert runtime.UI_FETCH_EVIDENCE_VIEWER_FETCH_ERROR_PATH_OUTPUT_KEY == "fetch_error_path"
    assert runtime.UI_FETCH_EVIDENCE_VIEWER_ERROR_PATH_OUTPUT_KEY == "error_path"
    assert (
        runtime.UI_FETCH_EVIDENCE_VIEWER_ERROR_EXPOSURE_RULE
        == "error_json_exposed_via_fetch_evidence_paths_error_path_when_failure"
    )


def test_runtime_fetch_review_checkpoint_approve_transition_anchor_matches_qf_094_clause() -> None:
    assert runtime.FETCH_REVIEW_CHECKPOINT_APPROVE_ACTION == "approve"
    assert runtime.FETCH_REVIEW_CHECKPOINT_APPROVE_TRANSITION == "enter_next_stage"


def test_runtime_fetch_review_checkpoint_reject_transition_anchor_matches_qf_095_clause() -> None:
    assert runtime.FETCH_REVIEW_CHECKPOINT_REJECT_ACTION == "reject"
    assert runtime.FETCH_REVIEW_CHECKPOINT_REJECT_TRANSITION == "rollback_and_allow_fetch_request_edit_or_rerun"


def test_runtime_fetch_evidence_append_only_attempt_rule_anchor_matches_qf_096_clause() -> None:
    assert runtime.FETCH_EVIDENCE_APPEND_ONLY_RULE == "append_only_keep_attempt_history"
    assert runtime.FETCH_EVIDENCE_ATTEMPT_DIRNAME_TEMPLATE == "attempt_{attempt_index:06d}"
    assert runtime.FETCH_EVIDENCE_ATTEMPTS_INDEX_FILENAME == "fetch_attempts_index.json"


def test_runtime_closed_loop_dod_anchor_matches_qf_097_clause() -> None:
    assert runtime.FETCHDATA_IMPL_CLOSED_LOOP_DOD_REQUIREMENT_ID == "QF-097"
    assert runtime.FETCHDATA_IMPL_CLOSED_LOOP_DOD_SOURCE_DOCUMENT == runtime.FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
    assert (
        runtime.FETCHDATA_IMPL_CLOSED_LOOP_DOD_CLAUSE
        == "QA‑Fetch FetchData Implementation Spec (v1) / 8. Definition of Done（主路闭环验收）"
    )


def test_runtime_fetch_contract_validation_rule_anchor_matches_qf_105_clause() -> None:
    assert runtime.FETCH_CONTRACT_VALIDATION_RULE == "pre_orchestrator_contract_validation_required"


def test_runtime_notebook_kernel_path_anchor_matches_qf_118_clause() -> None:
    assert runtime.NOTEBOOK_KERNEL_MANUAL_PARAMS_NOTEBOOK_PATH == "notebooks/qa_fetch_manual_params_v3.ipynb"
    assert runtime.NOTEBOOK_KERNEL_EXECUTION_ENV == "jupyter_notebook_kernel"


def test_runtime_notebook_kernel_sys_executable_anchor_matches_qf_119_clause() -> None:
    assert runtime.NOTEBOOK_KERNEL_PYTHON_EXECUTABLE_RULE == "use_notebook_kernel_sys_executable"
    assert runtime.NOTEBOOK_KERNEL_FORBIDDEN_HOST_EXECUTABLE == "/usr/bin/python3"


def test_runtime_notebook_params_data_verification_anchor_matches_qf_120_clause() -> None:
    assert runtime.NOTEBOOK_PARAMS_DATA_VERIFICATION_RULE == "notebook_params_probe_requires_pass_has_data"


def test_resolve_notebook_kernel_python_executable_uses_sys_executable(monkeypatch) -> None:
    monkeypatch.setattr(runtime.sys, "executable", "/opt/notebook-kernel/bin/python")

    resolved = runtime.resolve_notebook_kernel_python_executable()

    assert resolved == "/opt/notebook-kernel/bin/python"


def test_resolve_notebook_kernel_python_executable_rejects_host_usr_bin_python3() -> None:
    with pytest.raises(ValueError, match=r"must not use host /usr/bin/python3"):
        runtime.resolve_notebook_kernel_python_executable(sys_executable="/usr/bin/python3")


def test_build_notebook_kernel_python_command_prefixes_sys_executable(monkeypatch) -> None:
    monkeypatch.setattr(runtime.sys, "executable", "/opt/notebook-kernel/bin/python")

    cmd = runtime.build_notebook_kernel_python_command(
        ["scripts/run_qa_fetch_probe_from_notebook.py", "--output-dir", "docs/05_data_plane/qa_fetch_probe_v3"]
    )

    assert cmd[0] == "/opt/notebook-kernel/bin/python"
    assert cmd[1:] == ["scripts/run_qa_fetch_probe_from_notebook.py", "--output-dir", "docs/05_data_plane/qa_fetch_probe_v3"]


def test_runtime_fetch_evidence_step_filename_templates_anchor_match_qf_064_clause() -> None:
    assert runtime.FETCHDATA_IMPL_EVIDENCE_STEP_ARTIFACTS_REQUIREMENT_ID == "QF-064"
    assert (
        runtime.FETCHDATA_IMPL_EVIDENCE_STEP_ARTIFACTS_SOURCE_DOCUMENT
        == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    )
    assert runtime.FETCHDATA_IMPL_EVIDENCE_STEP_ARTIFACTS_CLAUSE == (
        "step_XXX_fetch_request.json / step_XXX_fetch_result_meta.json / "
        "step_XXX_fetch_preview.csv / step_XXX_fetch_error.json"
    )
    assert runtime.FETCH_EVIDENCE_STEP_REQUEST_FILENAME_TEMPLATE == "step_{step_index:03d}_fetch_request.json"
    assert runtime.FETCH_EVIDENCE_STEP_RESULT_META_FILENAME_TEMPLATE == "step_{step_index:03d}_fetch_result_meta.json"
    assert runtime.FETCH_EVIDENCE_STEP_PREVIEW_FILENAME_TEMPLATE == "step_{step_index:03d}_fetch_preview.csv"
    assert runtime.FETCH_EVIDENCE_STEP_ERROR_FILENAME_TEMPLATE == "step_{step_index:03d}_fetch_error.json"


def test_runtime_auto_symbols_list_first_rule_anchor_matches_qf_074_clause() -> None:
    assert runtime.AUTO_SYMBOLS_LIST_FIRST_RULE == "resolve_corresponding_list_before_sample_day"


def test_runtime_auto_symbols_day_execution_rule_anchor_matches_qf_071_clause() -> None:
    assert runtime.AUTO_SYMBOLS_DAY_EXECUTION_RULE == "execute_corresponding_day_after_sample"


def test_runtime_auto_symbols_step_evidence_rule_anchor_matches_qf_072_clause() -> None:
    assert runtime.AUTO_SYMBOLS_STEP_EVIDENCE_RULE == "emit_step_evidence_for_each_planner_step"


def test_runtime_request_hash_is_canonical_for_equivalent_payloads() -> None:
    payload_a = {
        "function": "fetch_stock_day",
        "kwargs": {"symbol": "000001", "start": "2024-01-01", "end": "2024-01-31"},
        "policy": {"mode": "smoke"},
    }
    payload_b = {
        "policy": {"mode": "smoke"},
        "kwargs": {"end": "2024-01-31", "start": "2024-01-01", "symbol": "000001"},
        "function": "fetch_stock_day",
    }

    assert runtime._canonical_request_hash(payload_a) == runtime._canonical_request_hash(payload_b)


def test_runtime_request_hash_includes_version_salt() -> None:
    payload = {
        "function": "fetch_stock_day",
        "kwargs": {"symbol": "000001", "start": "2024-01-01", "end": "2024-01-31"},
        "policy": {"mode": "smoke"},
    }
    canonical = runtime._json_safe(payload)
    unsalted = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

    assert runtime._canonical_request_hash(payload) != runtime.hashlib.sha256(unsalted).hexdigest()


def test_normalize_payload_list_of_dicts_reports_tabular_shape() -> None:
    payload = [
        {"code": "000001", "close": 10.0},
        {"code": "000002", "close": 11.0, "volume": 1000},
    ]

    _data, _typ, row_count, columns, dtypes, preview = runtime._normalize_payload(payload)

    assert row_count == 2
    assert columns == ["code", "close", "volume"]
    assert dtypes["code"] == "str"
    assert dtypes["close"] == "float"
    assert preview == payload


def test_normalize_payload_all_missing_list_of_dicts_is_semantically_empty() -> None:
    payload = [
        {"code": None, "close": None},
        {"code": "   ", "close": float("nan")},
    ]

    _data, _typ, row_count, columns, dtypes, preview = runtime._normalize_payload(payload)

    assert row_count == 0
    assert columns == ["code", "close"]
    assert dtypes["close"] == "float"
    assert preview == []


def test_normalize_payload_all_na_dataframe_is_semantically_empty() -> None:
    pd = pytest.importorskip("pandas")
    payload = pd.DataFrame(
        [
            {"code": None, "close": None},
            {"code": " ", "close": float("nan")},
        ]
    )

    _data, typ, row_count, columns, _dtypes, preview = runtime._normalize_payload(payload)

    assert typ == "DataFrame"
    assert row_count == 0
    assert columns == ["code", "close"]
    assert preview == []


def test_normalize_payload_dataframe_with_non_missing_value_reports_rows() -> None:
    pd = pytest.importorskip("pandas")
    payload = pd.DataFrame(
        [
            {"code": None, "close": None},
            {"code": "000001", "close": 10.0},
        ]
    )

    _data, typ, row_count, columns, _dtypes, preview = runtime._normalize_payload(payload)

    assert typ == "DataFrame"
    assert row_count == 2
    assert columns == ["code", "close"]
    assert len(preview) == 2


def test_runtime_param_priority_notebook_over_profile(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def _fn(symbol: str, start: str, end: str, format: str = "pd") -> list[dict[str, int]]:
        captured["symbol"] = symbol
        captured["start"] = start
        captured["end"] = end
        captured["format"] = format
        return [{"ok": 1}]

    monkeypatch.setattr(
        runtime,
        "load_smoke_window_profile",
        lambda _path: {
            "fetch_demo": {
                "smoke_kwargs": {"symbol": "from_profile", "start": "2026-01-01", "end": "2026-01-31"},
                "smoke_timeout_sec": 30,
            }
        },
    )
    monkeypatch.setattr(runtime, "load_exception_decisions", lambda _path: {})
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: _registry_row("fetch_demo"))
    monkeypatch.setattr(runtime, "_resolve_callable", lambda _fn_name, source_hint=None: (_fn, "mysql_fetch"))

    res = runtime.execute_fetch_by_name(
        function="fetch_demo",
        kwargs={"symbol": "from_llm"},
        policy={"mode": "smoke"},
    )

    assert res.status == runtime.STATUS_PASS_HAS_DATA
    assert res.source == "fetch"
    assert res.engine == "mysql"
    assert res.source_internal == "mysql_fetch"
    assert captured["symbol"] == "from_llm"
    assert captured["start"] == "2026-01-01"
    assert captured["end"] == "2026-01-31"
    assert captured["format"] == "pd"


def test_runtime_timeout_rule_by_mode(monkeypatch) -> None:
    called: list[int | None] = []

    def _fn() -> list[int]:
        return []

    def _fake_call_with_timeout(fn, *, timeout_sec):
        called.append(timeout_sec)
        return fn()

    monkeypatch.setattr(runtime, "load_smoke_window_profile", lambda _path: {})
    monkeypatch.setattr(runtime, "load_exception_decisions", lambda _path: {})
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: _registry_row("fetch_demo"))
    monkeypatch.setattr(runtime, "_resolve_callable", lambda _fn_name, source_hint=None: (_fn, "mysql_fetch"))
    monkeypatch.setattr(runtime, "_call_with_timeout", _fake_call_with_timeout)

    _ = runtime.execute_fetch_by_name(function="fetch_demo", kwargs={}, policy={"mode": "smoke"})
    _ = runtime.execute_fetch_by_name(function="fetch_demo", kwargs={}, policy={"mode": "research"})

    assert called[0] == 30
    assert called[1] is None


def test_runtime_status_on_empty_data(monkeypatch) -> None:
    def _fn() -> list[int]:
        return []

    monkeypatch.setattr(runtime, "load_smoke_window_profile", lambda _path: {})
    monkeypatch.setattr(runtime, "load_exception_decisions", lambda _path: {})
    monkeypatch.setattr(
        runtime,
        "load_function_registry",
        lambda _path: _registry_row("fetch_demo", source="mongo_fetch"),
    )
    monkeypatch.setattr(runtime, "_resolve_callable", lambda _fn_name, source_hint=None: (_fn, "mongo_fetch"))

    pass_empty = runtime.execute_fetch_by_name(function="fetch_demo", kwargs={}, policy={"mode": "smoke"})
    as_error = runtime.execute_fetch_by_name(
        function="fetch_demo",
        kwargs={},
        policy={"mode": "smoke", "on_no_data": "error"},
    )

    assert pass_empty.status == runtime.STATUS_PASS_EMPTY
    assert pass_empty.source == "fetch"
    assert pass_empty.engine == "mongo"
    assert as_error.status == runtime.STATUS_ERROR_RUNTIME
    assert as_error.reason == "no_data"


def test_runtime_status_on_all_na_rows_respects_on_no_data_policy(monkeypatch) -> None:
    def _fn() -> list[dict[str, Any]]:
        return [{"code": None, "close": None}, {"code": " ", "close": float("nan")}]

    monkeypatch.setattr(runtime, "load_smoke_window_profile", lambda _path: {})
    monkeypatch.setattr(runtime, "load_exception_decisions", lambda _path: {})
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: _registry_row("fetch_demo"))
    monkeypatch.setattr(runtime, "_resolve_callable", lambda _fn_name, source_hint=None: (_fn, "mysql_fetch"))

    pass_empty = runtime.execute_fetch_by_name(function="fetch_demo", kwargs={}, policy={"mode": "smoke"})
    as_error = runtime.execute_fetch_by_name(
        function="fetch_demo",
        kwargs={},
        policy={"mode": "smoke", "on_no_data": "error"},
    )

    assert pass_empty.status == runtime.STATUS_PASS_EMPTY
    assert pass_empty.reason == "no_data"
    assert pass_empty.row_count == 0
    assert as_error.status == runtime.STATUS_ERROR_RUNTIME
    assert as_error.reason == "no_data"
    assert as_error.row_count == 0


def test_runtime_status_on_partially_missing_rows_remains_pass_has_data(monkeypatch) -> None:
    def _fn() -> list[dict[str, Any]]:
        return [{"code": None, "close": None}, {"code": "000001", "close": None}]

    monkeypatch.setattr(runtime, "load_smoke_window_profile", lambda _path: {})
    monkeypatch.setattr(runtime, "load_exception_decisions", lambda _path: {})
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: _registry_row("fetch_demo"))
    monkeypatch.setattr(runtime, "_resolve_callable", lambda _fn_name, source_hint=None: (_fn, "mysql_fetch"))

    out = runtime.execute_fetch_by_name(function="fetch_demo", kwargs={}, policy={"mode": "smoke"})

    assert out.status == runtime.STATUS_PASS_HAS_DATA
    assert out.reason == "ok"
    assert out.row_count == 2


def test_runtime_status_on_empty_data_retry_succeeds_on_second_attempt(monkeypatch) -> None:
    attempts = {"count": 0}

    def _fn() -> list[dict[str, int]]:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return []
        return [{"ok": 1}]

    monkeypatch.setattr(runtime, "load_smoke_window_profile", lambda _path: {})
    monkeypatch.setattr(runtime, "load_exception_decisions", lambda _path: {})
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: _registry_row("fetch_demo"))
    monkeypatch.setattr(runtime, "_resolve_callable", lambda _fn_name, source_hint=None: (_fn, "mysql_fetch"))

    out = runtime.execute_fetch_by_name(
        function="fetch_demo",
        kwargs={},
        policy={"mode": "smoke", "on_no_data": "retry"},
    )

    assert attempts["count"] == 2
    assert out.status == runtime.STATUS_PASS_HAS_DATA
    assert out.reason == "ok"
    assert out.row_count == 1


def test_runtime_status_on_all_na_rows_retry_succeeds_on_second_attempt(monkeypatch) -> None:
    attempts = {"count": 0}

    def _fn() -> list[dict[str, Any]]:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return [{"code": None, "close": None}]
        return [{"ok": 1}]

    monkeypatch.setattr(runtime, "load_smoke_window_profile", lambda _path: {})
    monkeypatch.setattr(runtime, "load_exception_decisions", lambda _path: {})
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: _registry_row("fetch_demo"))
    monkeypatch.setattr(runtime, "_resolve_callable", lambda _fn_name, source_hint=None: (_fn, "mysql_fetch"))

    out = runtime.execute_fetch_by_name(
        function="fetch_demo",
        kwargs={},
        policy={"mode": "smoke", "on_no_data": "retry"},
    )

    assert attempts["count"] == 2
    assert out.status == runtime.STATUS_PASS_HAS_DATA
    assert out.reason == "ok"
    assert out.row_count == 1


def test_runtime_status_on_empty_data_retry_exhausted_returns_pass_empty(monkeypatch) -> None:
    attempts = {"count": 0}

    def _fn() -> list[dict[str, int]]:
        attempts["count"] += 1
        return []

    monkeypatch.setattr(runtime, "load_smoke_window_profile", lambda _path: {})
    monkeypatch.setattr(runtime, "load_exception_decisions", lambda _path: {})
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: _registry_row("fetch_demo"))
    monkeypatch.setattr(runtime, "_resolve_callable", lambda _fn_name, source_hint=None: (_fn, "mysql_fetch"))

    out = runtime.execute_fetch_by_name(
        function="fetch_demo",
        kwargs={},
        policy={"mode": "smoke", "on_no_data": "retry"},
    )

    assert attempts["count"] == 2
    assert out.status == runtime.STATUS_PASS_EMPTY
    assert out.reason == "no_data"


def test_runtime_status_on_empty_data_retry_uses_retry_strategy_max_attempts(monkeypatch) -> None:
    attempts = {"count": 0}

    def _fn() -> list[dict[str, int]]:
        attempts["count"] += 1
        if attempts["count"] < 3:
            return []
        return [{"ok": 1}]

    monkeypatch.setattr(runtime, "load_smoke_window_profile", lambda _path: {})
    monkeypatch.setattr(runtime, "load_exception_decisions", lambda _path: {})
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: _registry_row("fetch_demo"))
    monkeypatch.setattr(runtime, "_resolve_callable", lambda _fn_name, source_hint=None: (_fn, "mysql_fetch"))

    out = runtime.execute_fetch_by_name(
        function="fetch_demo",
        kwargs={},
        policy={"mode": "smoke", "on_no_data": "retry", "retry_strategy": {"max_attempts": 3}},
    )

    assert attempts["count"] == 3
    assert out.status == runtime.STATUS_PASS_HAS_DATA
    assert out.row_count == 1


def test_execute_fetch_by_name_adaptive_source_fallback_succeeds(monkeypatch, tmp_path) -> None:
    call_order: list[str | None] = []

    def _resolve(_fn_name: str, *, source_hint: str | None):
        normalized = runtime.normalize_source(source_hint)
        call_order.append(normalized)

        if normalized == "mongo_fetch":
            def _mongo_fn(code: str, start: str, end: str, format: str = "pd") -> list[dict[str, Any]]:
                assert code == "000001"
                assert start == "2024-01-01"
                assert end == "2024-01-31"
                return [{"code": None, "date": None, "close": None}]

            return _mongo_fn, "mongo_fetch"

        if normalized == "mysql_fetch":
            def _mysql_fn(code: str, start: str, end: str, format: str = "pd") -> list[dict[str, Any]]:
                assert code == "000001"
                assert start == "2024-01-01"
                assert end == "2024-01-31"
                return [{"code": code, "date": "2024-01-02", "close": 10.0}]

            return _mysql_fn, "mysql_fetch"

        raise AssertionError(f"unexpected source_hint={source_hint!r}")

    monkeypatch.setattr(
        runtime,
        "load_smoke_window_profile",
        lambda _path: {
            "fetch_demo": {
                "adaptive_source_order": ["mongo_fetch", "mysql_fetch"],
                "enable_source_fallback": True,
            }
        },
    )
    monkeypatch.setattr(runtime, "load_exception_decisions", lambda _path: {})
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: _registry_row("fetch_demo", source="mongo_fetch"))
    monkeypatch.setattr(runtime, "_resolve_callable", _resolve)
    monkeypatch.chdir(tmp_path)

    out = runtime.execute_fetch_by_name(
        function="fetch_demo",
        kwargs={"code": "000001", "start": "2024-01-01", "end": "2024-01-31"},
        policy={"mode": "research"},
        write_evidence=False,
    )

    assert out.status == runtime.STATUS_PASS_HAS_DATA
    assert out.source_internal == "mysql_fetch"
    assert out.row_count == 1
    assert call_order == ["mongo_fetch", "mysql_fetch"]


def test_execute_fetch_by_name_adaptive_source_no_data_error_does_not_fallback(monkeypatch, tmp_path) -> None:
    call_order: list[str | None] = []

    def _resolve(_fn_name: str, *, source_hint: str | None):
        normalized = runtime.normalize_source(source_hint)
        call_order.append(normalized)

        if normalized == "mongo_fetch":
            def _mongo_fn(code: str, start: str, end: str, format: str = "pd") -> list[dict[str, Any]]:
                assert code == "000001"
                assert start == "2024-01-01"
                assert end == "2024-01-31"
                return [{"code": None, "date": None, "close": None}]

            return _mongo_fn, "mongo_fetch"

        if normalized == "mysql_fetch":
            def _mysql_fn(code: str, start: str, end: str, format: str = "pd") -> list[dict[str, Any]]:
                return [{"code": code, "date": "2024-01-02", "close": 10.0}]

            return _mysql_fn, "mysql_fetch"

        raise AssertionError(f"unexpected source_hint={source_hint!r}")

    monkeypatch.setattr(
        runtime,
        "load_smoke_window_profile",
        lambda _path: {
            "fetch_demo": {
                "adaptive_source_order": ["mongo_fetch", "mysql_fetch"],
                "enable_source_fallback": True,
            }
        },
    )
    monkeypatch.setattr(runtime, "load_exception_decisions", lambda _path: {})
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: _registry_row("fetch_demo", source="mongo_fetch"))
    monkeypatch.setattr(runtime, "_resolve_callable", _resolve)
    monkeypatch.chdir(tmp_path)

    out = runtime.execute_fetch_by_name(
        function="fetch_demo",
        kwargs={"code": "000001", "start": "2024-01-01", "end": "2024-01-31"},
        policy={"mode": "research", "on_no_data": "error"},
        write_evidence=False,
    )

    assert out.status == runtime.STATUS_ERROR_RUNTIME
    assert out.reason == "no_data"
    assert out.source_internal == "mongo_fetch"
    assert call_order == ["mongo_fetch"]


def test_execute_fetch_by_name_adaptive_window_fallback_succeeds(monkeypatch, tmp_path) -> None:
    starts_seen: list[str] = []

    def _fn(code: str, start: str, end: str, format: str = "pd") -> list[dict[str, Any]]:
        starts_seen.append(start)
        assert code == "000001"
        assert end == "2024-01-31"
        if start == "2024-01-01":
            return []
        if start == "2024-01-27":
            return [{"code": code, "date": "2024-01-30", "close": 10.0}]
        raise AssertionError(f"unexpected start={start!r}")

    monkeypatch.setattr(
        runtime,
        "load_smoke_window_profile",
        lambda _path: {"fetch_demo": {"adaptive_window_lookback_days": [5]}},
    )
    monkeypatch.setattr(runtime, "load_exception_decisions", lambda _path: {})
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: _registry_row("fetch_demo", source="mysql_fetch"))
    monkeypatch.setattr(runtime, "_resolve_callable", lambda _fn_name, source_hint=None: (_fn, "mysql_fetch"))
    monkeypatch.chdir(tmp_path)

    out = runtime.execute_fetch_by_name(
        function="fetch_demo",
        kwargs={"code": "000001", "start": "2024-01-01", "end": "2024-01-31"},
        policy={"mode": "research"},
        write_evidence=False,
    )

    assert out.status == runtime.STATUS_PASS_HAS_DATA
    assert out.row_count == 1
    assert out.final_kwargs["start"] == "2024-01-27"
    assert starts_seen == ["2024-01-01", "2024-01-27"]


def test_execute_fetch_by_name_adaptive_plan_exhausted_returns_pass_empty(monkeypatch, tmp_path) -> None:
    calls: list[tuple[str | None, str, str]] = []

    def _resolve(_fn_name: str, *, source_hint: str | None):
        normalized = runtime.normalize_source(source_hint)

        def _fn(code: str, start: str, end: str, format: str = "pd") -> list[dict[str, Any]]:
            calls.append((normalized, start, end))
            assert code == "000001"
            return []

        return _fn, normalized or "mongo_fetch"

    monkeypatch.setattr(
        runtime,
        "load_smoke_window_profile",
        lambda _path: {
            "fetch_demo": {
                "adaptive_source_order": ["mongo_fetch", "mysql_fetch"],
                "enable_source_fallback": True,
                "adaptive_window_lookback_days": [3],
            }
        },
    )
    monkeypatch.setattr(runtime, "load_exception_decisions", lambda _path: {})
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: _registry_row("fetch_demo", source="mongo_fetch"))
    monkeypatch.setattr(runtime, "_resolve_callable", _resolve)
    monkeypatch.chdir(tmp_path)

    out = runtime.execute_fetch_by_name(
        function="fetch_demo",
        kwargs={"code": "000001", "start": "2024-01-01", "end": "2024-01-10"},
        policy={"mode": "research"},
        write_evidence=False,
    )

    assert out.status == runtime.STATUS_PASS_EMPTY
    assert out.reason == "no_data"
    assert out.final_kwargs["start"] == "2024-01-08"
    assert calls == [
        ("mongo_fetch", "2024-01-01", "2024-01-10"),
        ("mongo_fetch", "2024-01-08", "2024-01-10"),
        ("mysql_fetch", "2024-01-01", "2024-01-10"),
        ("mysql_fetch", "2024-01-08", "2024-01-10"),
    ]


def test_runtime_status_on_no_data_exception_respects_policy_error(monkeypatch, tmp_path) -> None:
    def _fn() -> None:
        raise RuntimeError("no data from mongo source")

    monkeypatch.setattr(runtime, "load_smoke_window_profile", lambda _path: {})
    monkeypatch.setattr(runtime, "load_exception_decisions", lambda _path: {})
    monkeypatch.setattr(
        runtime,
        "load_function_registry",
        lambda _path: _registry_row("fetch_demo", source="mongo_fetch"),
    )
    monkeypatch.setattr(runtime, "_resolve_callable", lambda _fn_name, source_hint=None: (_fn, "mongo_fetch"))
    monkeypatch.chdir(tmp_path)

    out = runtime.execute_fetch_by_name(
        function="fetch_demo",
        kwargs={},
        policy={"mode": "smoke", "on_no_data": "error"},
        write_evidence=False,
    )

    assert out.status == runtime.STATUS_ERROR_RUNTIME
    assert out.row_count == 0
    assert str(out.reason).startswith("no_data:")


def test_runtime_status_on_no_data_exception_retry_succeeds_on_second_attempt(monkeypatch, tmp_path) -> None:
    attempts = {"count": 0}

    def _fn() -> list[dict[str, int]]:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("no data from mongo source")
        return [{"ok": 1}]

    monkeypatch.setattr(runtime, "load_smoke_window_profile", lambda _path: {})
    monkeypatch.setattr(runtime, "load_exception_decisions", lambda _path: {})
    monkeypatch.setattr(
        runtime,
        "load_function_registry",
        lambda _path: _registry_row("fetch_demo", source="mongo_fetch"),
    )
    monkeypatch.setattr(runtime, "_resolve_callable", lambda _fn_name, source_hint=None: (_fn, "mongo_fetch"))
    monkeypatch.chdir(tmp_path)

    out = runtime.execute_fetch_by_name(
        function="fetch_demo",
        kwargs={},
        policy={"mode": "smoke", "on_no_data": "retry"},
        write_evidence=False,
    )

    assert attempts["count"] == 2
    assert out.status == runtime.STATUS_PASS_HAS_DATA
    assert out.row_count == 1


def test_execute_fetch_by_name_enforces_policy_max_symbols(monkeypatch, tmp_path) -> None:
    captured: dict[str, Any] = {}

    def _fn(code: str | list[str], format: str = "pd") -> list[dict[str, Any]]:
        captured["code"] = code
        symbols = [code] if isinstance(code, str) else list(code)
        return [{"code": sym, "close": 10.0} for sym in symbols]

    monkeypatch.setattr(runtime, "load_smoke_window_profile", lambda _path: {})
    monkeypatch.setattr(runtime, "load_exception_decisions", lambda _path: {})
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: _registry_row("fetch_demo"))
    monkeypatch.setattr(runtime, "_resolve_callable", lambda _fn_name, source_hint=None: (_fn, "mysql_fetch"))
    monkeypatch.chdir(tmp_path)

    out = runtime.execute_fetch_by_name(
        function="fetch_demo",
        kwargs={"code": ["000001", "000002", "000003"]},
        policy={"mode": "research", "max_symbols": 2},
        write_evidence=False,
    )

    assert captured["code"] == ["000001", "000002"]
    assert out.final_kwargs["code"] == ["000001", "000002"]
    assert out.row_count == 2


def test_execute_fetch_by_name_enforces_policy_max_rows(monkeypatch, tmp_path) -> None:
    def _fn(format: str = "pd") -> list[dict[str, Any]]:
        return [
            {"code": "000001", "date": "2024-01-01", "close": 10.0},
            {"code": "000001", "date": "2024-01-02", "close": 11.0},
            {"code": "000001", "date": "2024-01-03", "close": 12.0},
        ]

    monkeypatch.setattr(runtime, "load_smoke_window_profile", lambda _path: {})
    monkeypatch.setattr(runtime, "load_exception_decisions", lambda _path: {})
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: _registry_row("fetch_demo"))
    monkeypatch.setattr(runtime, "_resolve_callable", lambda _fn_name, source_hint=None: (_fn, "mysql_fetch"))
    monkeypatch.chdir(tmp_path)

    out = runtime.execute_fetch_by_name(
        function="fetch_demo",
        kwargs={},
        policy={"mode": "research", "max_rows": 2},
        write_evidence=False,
    )

    assert out.status == runtime.STATUS_PASS_HAS_DATA
    assert out.row_count == 2
    assert isinstance(out.data, list) and len(out.data) == 2
    assert out.preview == [
        {"code": "000001", "date": "2024-01-01", "close": 10.0},
        {"code": "000001", "date": "2024-01-02", "close": 11.0},
    ]


def test_execute_fetch_by_name_enforces_no_lookahead_filter(monkeypatch, tmp_path) -> None:
    def _fn(symbol: str, as_of: str, format: str = "pd") -> list[dict[str, Any]]:
        assert symbol == "000001"
        assert as_of == "2024-01-02T23:59:59+08:00"
        assert format == "pd"
        return [
            {"code": "000001", "date": "2024-01-01", "available_at": "2024-01-01T16:00:00+08:00", "close": 10.0},
            {"code": "000001", "date": "2024-01-02", "available_at": "2024-01-02T16:00:00+08:00", "close": 11.0},
            {"code": "000001", "date": "2024-01-03", "available_at": "2024-01-03T16:00:00+08:00", "close": 12.0},
        ]

    monkeypatch.setattr(runtime, "load_smoke_window_profile", lambda _path: {})
    monkeypatch.setattr(runtime, "load_exception_decisions", lambda _path: {})
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: _registry_row("fetch_demo"))
    monkeypatch.setattr(runtime, "_resolve_callable", lambda _fn_name, source_hint=None: (_fn, "mysql_fetch"))
    monkeypatch.chdir(tmp_path)

    out = runtime.execute_fetch_by_name(
        function="fetch_demo",
        kwargs={"symbol": "000001", "as_of": "2024-01-02T23:59:59+08:00"},
        policy={"mode": "research"},
        write_evidence=False,
    )

    assert out.status == runtime.STATUS_PASS_HAS_DATA
    assert out.row_count == 2
    assert out.preview == [
        {"code": "000001", "date": "2024-01-01", "available_at": "2024-01-01T16:00:00+08:00", "close": 10.0},
        {"code": "000001", "date": "2024-01-02", "available_at": "2024-01-02T16:00:00+08:00", "close": 11.0},
    ]
    assert isinstance(out.data, list) and len(out.data) == 2


def test_execute_fetch_by_name_no_lookahead_drops_missing_or_invalid_available_at_rows(monkeypatch, tmp_path) -> None:
    def _fn(symbol: str, as_of: str, format: str = "pd") -> list[dict[str, Any]]:
        assert symbol == "000001"
        assert as_of == "2024-01-02T23:59:59+08:00"
        assert format == "pd"
        return [
            {"code": "000001", "date": "2024-01-01", "available_at": "2024-01-01T16:00:00+08:00", "close": 10.0},
            {"code": "000001", "date": "2024-01-01", "available_at": "", "close": 10.1},
            {"code": "000001", "date": "2024-01-01", "close": 10.2},
            {"code": "000001", "date": "2024-01-01", "available_at": "bad", "close": 10.3},
            {"code": "000001", "date": "2024-01-03", "available_at": "2024-01-03T16:00:00+08:00", "close": 12.0},
        ]

    monkeypatch.setattr(runtime, "load_smoke_window_profile", lambda _path: {})
    monkeypatch.setattr(runtime, "load_exception_decisions", lambda _path: {})
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: _registry_row("fetch_demo"))
    monkeypatch.setattr(runtime, "_resolve_callable", lambda _fn_name, source_hint=None: (_fn, "mysql_fetch"))
    monkeypatch.chdir(tmp_path)

    out = runtime.execute_fetch_by_name(
        function="fetch_demo",
        kwargs={"symbol": "000001", "as_of": "2024-01-02T23:59:59+08:00"},
        policy={"mode": "research"},
        write_evidence=False,
    )

    assert out.status == runtime.STATUS_PASS_HAS_DATA
    assert out.row_count == 1
    assert out.preview == [
        {"code": "000001", "date": "2024-01-01", "available_at": "2024-01-01T16:00:00+08:00", "close": 10.0},
    ]
    assert isinstance(out.data, list) and len(out.data) == 1


def test_execute_fetch_by_name_no_lookahead_skips_gate_when_available_at_absent(monkeypatch, tmp_path) -> None:
    def _fn(symbol: str, as_of: str, format: str = "pd") -> list[dict[str, Any]]:
        assert symbol == "000001"
        assert as_of == "2024-01-02T23:59:59+08:00"
        assert format == "pd"
        return [
            {"code": "000001", "date": "2024-01-01", "close": 10.0},
            {"code": "000001", "date": "2024-01-02", "close": 11.0},
        ]

    monkeypatch.setattr(runtime, "load_smoke_window_profile", lambda _path: {})
    monkeypatch.setattr(runtime, "load_exception_decisions", lambda _path: {})
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: _registry_row("fetch_demo"))
    monkeypatch.setattr(runtime, "_resolve_callable", lambda _fn_name, source_hint=None: (_fn, "mysql_fetch"))
    monkeypatch.chdir(tmp_path)

    out = runtime.execute_fetch_by_name(
        function="fetch_demo",
        kwargs={"symbol": "000001", "as_of": "2024-01-02T23:59:59+08:00"},
        policy={"mode": "research"},
        write_evidence=False,
    )

    assert out.status == runtime.STATUS_PASS_HAS_DATA
    assert out.row_count == 2
    assert out.preview == [
        {"code": "000001", "date": "2024-01-01", "close": 10.0},
        {"code": "000001", "date": "2024-01-02", "close": 11.0},
    ]
    assert isinstance(out.data, list) and len(out.data) == 2


def test_execute_fetch_by_name_time_travel_boundary_keeps_available_at_equal_to_as_of(monkeypatch, tmp_path) -> None:
    def _fn(symbol: str, as_of: str, format: str = "pd") -> list[dict[str, Any]]:
        assert symbol == "000001"
        assert as_of == "2024-01-02T16:00:00+08:00"
        assert format == "pd"
        return [
            {"code": "000001", "date": "2024-01-02", "available_at": "2024-01-02T16:00:00+08:00", "close": 11.0},
            {"code": "000001", "date": "2024-01-03", "available_at": "2024-01-02T16:00:01+08:00", "close": 12.0},
        ]

    monkeypatch.setattr(runtime, "load_smoke_window_profile", lambda _path: {})
    monkeypatch.setattr(runtime, "load_exception_decisions", lambda _path: {})
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: _registry_row("fetch_demo"))
    monkeypatch.setattr(runtime, "_resolve_callable", lambda _fn_name, source_hint=None: (_fn, "mysql_fetch"))
    monkeypatch.chdir(tmp_path)

    out = runtime.execute_fetch_by_name(
        function="fetch_demo",
        kwargs={"symbol": "000001", "as_of": "2024-01-02T16:00:00+08:00"},
        policy={"mode": "research"},
        write_evidence=False,
    )

    assert out.status == runtime.STATUS_PASS_HAS_DATA
    assert out.row_count == 1
    assert out.preview == [
        {"code": "000001", "date": "2024-01-02", "available_at": "2024-01-02T16:00:00+08:00", "close": 11.0},
    ]


def test_datacatalog_guard_keeps_equal_available_at_and_flags_future_only_payload() -> None:
    payload = [
        {"code": "000001", "available_at": "2024-01-02T08:00:00Z", "close": 11.0},
        {"code": "000001", "available_at": "2024-01-02T08:00:01Z", "close": 12.0},
    ]

    filtered, unavailable = runtime._apply_datacatalog_available_at_as_of_guard(
        payload=payload,
        as_of="2024-01-02T16:00:00+08:00",
    )
    assert unavailable is False
    assert filtered == [{"code": "000001", "available_at": "2024-01-02T08:00:00Z", "close": 11.0}]

    filtered_only_future, unavailable_only_future = runtime._apply_datacatalog_available_at_as_of_guard(
        payload=[{"code": "000001", "available_at": "2024-01-02T08:00:01Z", "close": 12.0}],
        as_of="2024-01-02T16:00:00+08:00",
    )
    assert filtered_only_future == []
    assert unavailable_only_future is True


def test_execute_fetch_by_name_time_travel_unavailable_falls_back_to_next_source(monkeypatch, tmp_path) -> None:
    called_sources: list[str | None] = []

    def _mysql_fn(symbol: str, as_of: str, format: str = "pd") -> list[dict[str, Any]]:
        assert symbol == "000001"
        assert as_of == "2024-01-02T23:59:59+08:00"
        assert format == "pd"
        return [
            {"code": "000001", "date": "2024-01-03", "available_at": "2024-01-03T16:00:00+08:00", "close": 12.0},
        ]

    def _mongo_fn(symbol: str, as_of: str, format: str = "pd") -> list[dict[str, Any]]:
        assert symbol == "000001"
        assert as_of == "2024-01-02T23:59:59+08:00"
        assert format == "pd"
        return [
            {"code": "000001", "date": "2024-01-02", "available_at": "2024-01-02T16:00:00+08:00", "close": 11.0},
        ]

    def _resolve_callable(_fn_name: str, source_hint: str | None = None) -> tuple[Any, str]:
        called_sources.append(source_hint)
        if source_hint == "mysql_fetch":
            return _mysql_fn, "mysql_fetch"
        if source_hint == "mongo_fetch":
            return _mongo_fn, "mongo_fetch"
        raise AssertionError(f"unexpected source_hint: {source_hint}")

    monkeypatch.setattr(
        runtime,
        "load_smoke_window_profile",
        lambda _path: {"fetch_demo": {runtime.ADAPTIVE_PROFILE_SOURCE_FALLBACK_KEY: True}},
    )
    monkeypatch.setattr(runtime, "load_exception_decisions", lambda _path: {})
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: _registry_row("fetch_demo"))
    monkeypatch.setattr(runtime, "_resolve_callable", _resolve_callable)
    monkeypatch.chdir(tmp_path)

    out = runtime.execute_fetch_by_name(
        function="fetch_demo",
        kwargs={"symbol": "000001", "as_of": "2024-01-02T23:59:59+08:00"},
        policy={"mode": "research", "on_no_data": "error"},
        write_evidence=False,
    )

    assert called_sources == ["mysql_fetch", "mongo_fetch"]
    assert out.status == runtime.STATUS_PASS_HAS_DATA
    assert out.source_internal == "mongo_fetch"
    assert out.row_count == 1
    assert out.preview == [
        {"code": "000001", "date": "2024-01-02", "available_at": "2024-01-02T16:00:00+08:00", "close": 11.0},
    ]


def test_execute_fetch_by_name_time_travel_unavailable_returns_error(monkeypatch, tmp_path) -> None:
    def _fn(symbol: str, as_of: str, format: str = "pd") -> list[dict[str, Any]]:
        assert symbol == "000001"
        assert as_of == "2024-01-02T23:59:59+08:00"
        assert format == "pd"
        return [
            {"code": "000001", "date": "2024-01-03", "available_at": "2024-01-03T16:00:00+08:00", "close": 12.0},
            {"code": "000001", "date": "2024-01-04", "available_at": "2024-01-04T16:00:00+08:00", "close": 13.0},
        ]

    monkeypatch.setattr(runtime, "load_smoke_window_profile", lambda _path: {})
    monkeypatch.setattr(runtime, "load_exception_decisions", lambda _path: {})
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: _registry_row("fetch_demo"))
    monkeypatch.setattr(runtime, "_resolve_callable", lambda _fn_name, source_hint=None: (_fn, "mysql_fetch"))
    monkeypatch.chdir(tmp_path)

    out = runtime.execute_fetch_by_name(
        function="fetch_demo",
        kwargs={"symbol": "000001", "as_of": "2024-01-02T23:59:59+08:00"},
        policy={"mode": "research"},
        write_evidence=False,
    )

    assert out.status == runtime.STATUS_ERROR_RUNTIME
    assert out.reason == runtime.TIME_TRAVEL_UNAVAILABLE_REASON
    assert out.row_count == 0
    assert out.preview == []
    assert out.data == []


def test_execute_fetch_by_intent_enforces_no_lookahead_with_top_level_as_of(monkeypatch, tmp_path) -> None:
    class _Resolution:
        source = "mysql_fetch"
        public_name = "fetch_stock_day"

    def _fn(code: str | list[str], start: str, end: str, format: str = "pd") -> list[dict[str, Any]]:
        symbols = [code] if isinstance(code, str) else list(code)
        assert symbols == ["000001"]
        assert start == "2024-01-01"
        assert end == "2024-01-31"
        assert format == "pd"
        return [
            {"code": "000001", "date": "2024-01-01", "available_at": "2024-01-01T16:00:00+08:00", "close": 10.0},
            {"code": "000001", "date": "2024-01-03", "available_at": "2024-01-03T16:00:00+08:00", "close": 12.0},
        ]

    monkeypatch.setattr(runtime, "resolve_fetch", lambda **_: _Resolution())
    monkeypatch.setattr(runtime, "load_smoke_window_profile", lambda _path: {})
    monkeypatch.setattr(runtime, "load_exception_decisions", lambda _path: {})
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: _registry_row("fetch_stock_day"))
    monkeypatch.setattr(runtime, "_resolve_callable", lambda _fn_name, source_hint=None: (_fn, "mysql_fetch"))
    monkeypatch.chdir(tmp_path)

    out = runtime.execute_fetch_by_intent(
        {
            "intent": {"asset": "stock", "freq": "day"},
            "symbols": ["000001"],
            "start": "2024-01-01",
            "end": "2024-01-31",
            "as_of": "2024-01-02T23:59:59+08:00",
            "policy": {"mode": "research"},
        },
        write_evidence=False,
    )

    assert out.status == runtime.STATUS_PASS_HAS_DATA
    assert out.row_count == 1
    assert out.preview == [
        {"code": "000001", "date": "2024-01-01", "available_at": "2024-01-01T16:00:00+08:00", "close": 10.0},
    ]


def test_runtime_exception_mapping_and_decision_gate(monkeypatch, tmp_path) -> None:
    def _missing_table_fn() -> None:
        raise RuntimeError("ProgrammingError: table test2.clean_bond_quote doesn't exist")

    monkeypatch.setattr(runtime, "load_smoke_window_profile", lambda _path: {})
    monkeypatch.setattr(runtime, "load_exception_decisions", lambda _path: {})
    monkeypatch.setattr(
        runtime,
        "load_function_registry",
        lambda _path: _registry_row("fetch_bond_quote", target_name="fetch_clean_quote"),
    )
    monkeypatch.setattr(
        runtime,
        "_resolve_callable",
        lambda _fn_name, source_hint=None: (_missing_table_fn, "mysql_fetch"),
    )
    monkeypatch.chdir(tmp_path)

    blocked = runtime.execute_fetch_by_name(function="fetch_bond_quote", kwargs={}, policy={"mode": "smoke"})
    assert blocked.status == runtime.STATUS_BLOCKED_SOURCE_MISSING
    assert blocked.source == "fetch"
    assert blocked.engine == "mysql"

    monkeypatch.setattr(
        runtime,
        "load_exception_decisions",
        lambda _path: {
            "fetch_bond_quote": {
                "issue_type": "source_table_missing",
                "smoke_policy": "blocked",
                "research_policy": "blocked",
                "decision": "pending",
                "notes": "manual",
            }
        },
    )
    pending = runtime.execute_fetch_by_name(function="fetch_bond_quote", kwargs={}, policy={"mode": "smoke"})
    assert pending.status == runtime.STATUS_BLOCKED_SOURCE_MISSING
    assert "disabled_by_exception_policy" in pending.reason


def test_runtime_blocks_function_outside_frozen_baseline(monkeypatch) -> None:
    monkeypatch.setattr(runtime, "load_smoke_window_profile", lambda _path: {})
    monkeypatch.setattr(runtime, "load_exception_decisions", lambda _path: {})
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: {})

    out = runtime.execute_fetch_by_name(function="fetch_not_in_baseline", kwargs={}, policy={"mode": "smoke"})
    assert out.status == runtime.STATUS_BLOCKED_SOURCE_MISSING
    assert out.reason == "not_in_baseline"
    assert out.source == "fetch"


def test_execute_fetch_by_name_forces_runtime_evidence_write(tmp_path, monkeypatch) -> None:
    def _fn(symbol: str, as_of: str, format: str = "pd") -> list[dict[str, Any]]:
        assert format == "pd"
        assert as_of == "2024-01-02T23:59:59+08:00"
        return [
            {
                "symbol": symbol,
                "date": "2024-01-02",
                "available_at": "2024-01-02T16:00:00+08:00",
                "close": 10.0,
            }
        ]

    monkeypatch.setattr(runtime, "load_smoke_window_profile", lambda _path: {})
    monkeypatch.setattr(runtime, "load_exception_decisions", lambda _path: {})
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: _registry_row("fetch_demo"))
    monkeypatch.setattr(runtime, "_resolve_callable", lambda _fn_name, source_hint=None: (_fn, "mysql_fetch"))
    monkeypatch.chdir(tmp_path)

    out = runtime.execute_fetch_by_name(
        function="fetch_demo",
        kwargs={"symbol": "000001", "as_of": "2024-01-02T23:59:59+08:00"},
        policy={"mode": "smoke"},
    )
    assert out.status == runtime.STATUS_PASS_HAS_DATA

    bundles = sorted((tmp_path / "artifacts" / "qa_fetch" / "runtime_fetch_evidence").glob("*/fetch_request.json"))
    assert len(bundles) == 1
    request_payload = json.loads(bundles[0].read_text(encoding="utf-8"))
    assert request_payload["function"] == "fetch_demo"
    assert request_payload["kwargs"]["symbol"] == "000001"
    assert request_payload["kwargs"]["as_of"] == "2024-01-02T23:59:59+08:00"
    assert (bundles[0].parent / "fetch_result_meta.json").is_file()
    assert (bundles[0].parent / runtime.FETCH_EVIDENCE_PREVIEW_FILENAME).is_file()
    assert (bundles[0].parent / runtime.FETCH_EVIDENCE_STEPS_INDEX_FILENAME).is_file()
    meta = json.loads((bundles[0].parent / "fetch_result_meta.json").read_text(encoding="utf-8"))
    assert meta["as_of"] == "2024-01-02T15:59:59Z"
    assert isinstance(meta["availability_summary"], dict)
    assert meta["availability_summary"]["has_as_of"] is True
    assert meta["availability_summary"]["as_of"] == "2024-01-02T15:59:59Z"


def test_execute_fetch_by_name_ignores_write_evidence_opt_out_for_qf_007(tmp_path, monkeypatch) -> None:
    def _fn(symbol: str, format: str = "pd") -> list[dict[str, Any]]:
        assert format == "pd"
        return [{"symbol": symbol, "date": "2024-01-02", "close": 10.0}]

    monkeypatch.setattr(runtime, "load_smoke_window_profile", lambda _path: {})
    monkeypatch.setattr(runtime, "load_exception_decisions", lambda _path: {})
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: _registry_row("fetch_demo"))
    monkeypatch.setattr(runtime, "_resolve_callable", lambda _fn_name, source_hint=None: (_fn, "mysql_fetch"))
    monkeypatch.chdir(tmp_path)

    out = runtime.execute_fetch_by_name(
        function="fetch_demo",
        kwargs={"symbol": "000001"},
        policy={"mode": "smoke"},
        write_evidence=False,
    )
    assert out.status == runtime.STATUS_PASS_HAS_DATA

    bundles = sorted((tmp_path / "artifacts" / "qa_fetch" / "runtime_fetch_evidence").glob("*/fetch_request.json"))
    assert len(bundles) == 1
    assert (bundles[0].parent / runtime.FETCH_EVIDENCE_RESULT_META_FILENAME).is_file()


def test_execute_fetch_by_name_policy_run_id_routes_evidence_to_dossier_fetch_root(tmp_path, monkeypatch) -> None:
    def _fn(symbol: str, format: str = "pd") -> list[dict[str, Any]]:
        assert format == "pd"
        return [{"symbol": symbol, "date": "2024-01-02", "close": 10.0}]

    monkeypatch.setattr(runtime, "load_smoke_window_profile", lambda _path: {})
    monkeypatch.setattr(runtime, "load_exception_decisions", lambda _path: {})
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: _registry_row("fetch_demo"))
    monkeypatch.setattr(runtime, "_resolve_callable", lambda _fn_name, source_hint=None: (_fn, "mysql_fetch"))
    monkeypatch.chdir(tmp_path)
    snapshot_manifest_path = tmp_path / "data_lake" / "snapshot_run_fetch_001" / "manifest.json"
    snapshot_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_manifest_path.write_text('{"schema_version":"data_snapshot_manifest_v1"}\n', encoding="utf-8")

    out = runtime.execute_fetch_by_name(
        function="fetch_demo",
        kwargs={"symbol": "000001"},
        policy={
            "mode": "smoke",
            "run_id": "run_fetch_001",
            "snapshot_manifest_path": snapshot_manifest_path.as_posix(),
        },
    )
    assert out.status == runtime.STATUS_PASS_HAS_DATA

    dossier_fetch_rel = Path("artifacts") / "dossiers" / "run_fetch_001" / "fetch"
    dossier_fetch = tmp_path / "artifacts" / "dossiers" / "run_fetch_001" / "fetch"
    assert (dossier_fetch / runtime.FETCH_EVIDENCE_REQUEST_FILENAME).is_file()
    assert (dossier_fetch / runtime.FETCH_EVIDENCE_RESULT_META_FILENAME).is_file()
    assert (dossier_fetch / runtime.FETCH_EVIDENCE_PREVIEW_FILENAME).is_file()
    assert (dossier_fetch / runtime.FETCH_EVIDENCE_STEPS_INDEX_FILENAME).is_file()
    assert not (dossier_fetch / runtime.FETCH_EVIDENCE_ERROR_FILENAME).exists()
    assert not (dossier_fetch / runtime.UI_FETCH_EVIDENCE_VIEWER_ERROR_FILENAME).exists()
    assert not list(dossier_fetch.glob("step_*_fetch_*"))
    idx = json.loads((dossier_fetch / runtime.FETCH_EVIDENCE_STEPS_INDEX_FILENAME).read_text(encoding="utf-8"))
    assert len(idx["steps"]) == 1
    assert idx["steps"][0]["step_kind"] == "single_fetch"
    assert idx["steps"][0]["status"] == runtime.STATUS_PASS_HAS_DATA
    assert idx["steps"][0]["request_path"] == (dossier_fetch_rel / runtime.FETCH_EVIDENCE_REQUEST_FILENAME).as_posix()
    assert idx["steps"][0]["result_meta_path"] == (
        dossier_fetch_rel / runtime.FETCH_EVIDENCE_RESULT_META_FILENAME
    ).as_posix()
    assert idx["steps"][0]["preview_path"] == (dossier_fetch_rel / runtime.FETCH_EVIDENCE_PREVIEW_FILENAME).as_posix()


def test_execute_fetch_by_name_policy_run_id_failure_writes_fetch_error_in_dossier_fetch_root(tmp_path, monkeypatch) -> None:
    def _fn(symbol: str, format: str = "pd") -> list[dict[str, Any]]:
        assert format == "pd"
        raise RuntimeError("RuntimeError: boom")

    monkeypatch.setattr(runtime, "load_smoke_window_profile", lambda _path: {})
    monkeypatch.setattr(runtime, "load_exception_decisions", lambda _path: {})
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: _registry_row("fetch_demo"))
    monkeypatch.setattr(runtime, "_resolve_callable", lambda _fn_name, source_hint=None: (_fn, "mysql_fetch"))
    monkeypatch.chdir(tmp_path)
    snapshot_manifest_path = tmp_path / "data_lake" / "snapshot_run_fetch_fail_001" / "manifest.json"
    snapshot_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_manifest_path.write_text('{"schema_version":"data_snapshot_manifest_v1"}\n', encoding="utf-8")

    out = runtime.execute_fetch_by_name(
        function="fetch_demo",
        kwargs={"symbol": "000001"},
        policy={
            "mode": "smoke",
            "run_id": "run_fetch_fail_001",
            "snapshot_manifest_path": snapshot_manifest_path.as_posix(),
        },
    )
    assert out.status == runtime.STATUS_ERROR_RUNTIME

    dossier_fetch_rel = Path("artifacts") / "dossiers" / "run_fetch_fail_001" / "fetch"
    dossier_fetch = tmp_path / "artifacts" / "dossiers" / "run_fetch_fail_001" / "fetch"
    assert (dossier_fetch / runtime.FETCH_EVIDENCE_REQUEST_FILENAME).is_file()
    assert (dossier_fetch / runtime.FETCH_EVIDENCE_RESULT_META_FILENAME).is_file()
    assert (dossier_fetch / runtime.FETCH_EVIDENCE_PREVIEW_FILENAME).is_file()
    assert (dossier_fetch / runtime.FETCH_EVIDENCE_STEPS_INDEX_FILENAME).is_file()
    assert (dossier_fetch / runtime.FETCH_EVIDENCE_ERROR_FILENAME).is_file()
    assert (dossier_fetch / runtime.UI_FETCH_EVIDENCE_VIEWER_ERROR_FILENAME).is_file()
    assert not list(dossier_fetch.glob("step_*_fetch_*"))
    idx = json.loads((dossier_fetch / runtime.FETCH_EVIDENCE_STEPS_INDEX_FILENAME).read_text(encoding="utf-8"))
    assert len(idx["steps"]) == 1
    assert idx["steps"][0]["step_kind"] == "single_fetch"
    assert idx["steps"][0]["status"] == runtime.STATUS_ERROR_RUNTIME
    assert idx["steps"][0]["request_path"] == (dossier_fetch_rel / runtime.FETCH_EVIDENCE_REQUEST_FILENAME).as_posix()
    assert idx["steps"][0]["result_meta_path"] == (
        dossier_fetch_rel / runtime.FETCH_EVIDENCE_RESULT_META_FILENAME
    ).as_posix()
    assert idx["steps"][0]["preview_path"] == (dossier_fetch_rel / runtime.FETCH_EVIDENCE_PREVIEW_FILENAME).as_posix()
    assert idx["steps"][0]["error_path"] == (dossier_fetch_rel / runtime.FETCH_EVIDENCE_ERROR_FILENAME).as_posix()
    fetch_error_payload = json.loads((dossier_fetch / runtime.FETCH_EVIDENCE_ERROR_FILENAME).read_text(encoding="utf-8"))
    viewer_error_payload = json.loads((dossier_fetch / runtime.UI_FETCH_EVIDENCE_VIEWER_ERROR_FILENAME).read_text(encoding="utf-8"))
    assert viewer_error_payload == fetch_error_payload


def test_execute_fetch_by_name_policy_run_id_gate_fails_when_snapshot_manifest_missing(tmp_path, monkeypatch) -> None:
    def _fn(symbol: str, format: str = "pd") -> list[dict[str, Any]]:
        assert format == "pd"
        return [{"symbol": symbol, "date": "2024-01-02", "close": 10.0}]

    monkeypatch.setattr(runtime, "load_smoke_window_profile", lambda _path: {})
    monkeypatch.setattr(runtime, "load_exception_decisions", lambda _path: {})
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: _registry_row("fetch_demo"))
    monkeypatch.setattr(runtime, "_resolve_callable", lambda _fn_name, source_hint=None: (_fn, "mysql_fetch"))
    monkeypatch.chdir(tmp_path)

    with pytest.raises(
        ValueError,
        match=r"run must gate fail when fetch evidence / snapshot manifest is missing; run_id=run_fetch_missing_manifest_001; violations=missing_snapshot_manifest",
    ):
        runtime.execute_fetch_by_name(
            function="fetch_demo",
            kwargs={"symbol": "000001"},
            policy={"mode": "smoke", "run_id": "run_fetch_missing_manifest_001"},
        )


def test_execute_fetch_by_name_policy_run_id_gate_fails_when_no_lookahead_violation(tmp_path, monkeypatch) -> None:
    def _fn(symbol: str, as_of: str, format: str = "pd") -> list[dict[str, Any]]:
        assert format == "pd"
        return [
            {
                "symbol": symbol,
                "date": "2024-01-02",
                "available_at": "2024-01-01T16:00:00+08:00",
                "close": 10.0,
            },
            {
                "symbol": symbol,
                "date": "2024-01-03",
                "available_at": "2024-01-04T16:00:00+08:00",
                "close": 11.0,
            },
        ]

    monkeypatch.setattr(runtime, "load_smoke_window_profile", lambda _path: {})
    monkeypatch.setattr(runtime, "load_exception_decisions", lambda _path: {})
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: _registry_row("fetch_demo"))
    monkeypatch.setattr(runtime, "_resolve_callable", lambda _fn_name, source_hint=None: (_fn, "mysql_fetch"))
    snapshot_manifest_path = tmp_path / "data_lake" / "snapshot_run_fetch_violation_001" / "manifest.json"
    snapshot_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_manifest_path.write_text('{"schema_version":"data_snapshot_manifest_v1"}\n', encoding="utf-8")
    original_contracts_validate = runtime._contracts_validate

    runtime._contracts_validate = None
    try:
        out = runtime.execute_fetch_by_name(
            function="fetch_demo",
            kwargs={"symbol": "000001", "as_of": "2024-01-02T23:59:59+08:00"},
            policy={
                "mode": "smoke",
                "run_id": "run_fetch_no_lookahead_001",
                "snapshot_manifest_path": snapshot_manifest_path.as_posix(),
            },
        )
    finally:
        runtime._contracts_validate = original_contracts_validate

    assert out.status == runtime.STATUS_ERROR_RUNTIME
    assert out.reason.startswith("ValueError: run must gate fail when fetch execution gates are violated")
    assert "no_lookahead.available_at_violation_count=1" in out.reason
    assert "run_id=run_fetch_no_lookahead_001" in out.reason


def test_execute_fetch_by_intent_forces_runtime_evidence_write(tmp_path, monkeypatch) -> None:
    class _Resolution:
        source = "mongo_fetch"
        public_name = "fetch_stock_day"

    def _fn(code: str | list[str], start: str, end: str, format: str = "pd") -> list[dict[str, Any]]:
        assert format == "pd"
        assert start == "2024-01-01"
        assert end == "2024-01-31"
        symbols = [code] if isinstance(code, str) else list(code)
        return [{"symbol": symbols[0], "date": "2024-01-02", "close": 10.0}]

    monkeypatch.setattr(runtime, "resolve_fetch", lambda **_: _Resolution())
    monkeypatch.setattr(runtime, "load_smoke_window_profile", lambda _path: {})
    monkeypatch.setattr(runtime, "load_exception_decisions", lambda _path: {})
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: _registry_row("fetch_stock_day"))
    monkeypatch.setattr(runtime, "_resolve_callable", lambda _fn_name, source_hint=None: (_fn, "mongo_fetch"))
    monkeypatch.chdir(tmp_path)

    out = runtime.execute_fetch_by_intent(
        {
            "intent": {"asset": "stock", "freq": "day"},
            "symbols": ["000001"],
            "start": "2024-01-01",
            "end": "2024-01-31",
            "policy": {"mode": "research"},
        }
    )
    assert out.status == runtime.STATUS_PASS_HAS_DATA

    bundles = sorted((tmp_path / "artifacts" / "qa_fetch" / "runtime_fetch_evidence").glob("*/fetch_request.json"))
    assert len(bundles) == 1
    request_payload = json.loads(bundles[0].read_text(encoding="utf-8"))
    assert request_payload["intent"]["asset"] == "stock"
    assert request_payload["intent"]["freq"] == "day"
    assert request_payload["symbols"] == ["000001"]
    assert request_payload["function"] == "fetch_stock_day"
    assert (bundles[0].parent / "fetch_result_meta.json").is_file()
    assert (bundles[0].parent / runtime.FETCH_EVIDENCE_PREVIEW_FILENAME).is_file()
    assert (bundles[0].parent / runtime.FETCH_EVIDENCE_STEPS_INDEX_FILENAME).is_file()


def test_execute_fetch_by_intent_ignores_write_evidence_opt_out_for_qf_007(tmp_path, monkeypatch) -> None:
    class _Resolution:
        source = "mongo_fetch"
        public_name = "fetch_stock_day"

    def _fn(code: str | list[str], start: str, end: str, format: str = "pd") -> list[dict[str, Any]]:
        assert format == "pd"
        assert start == "2024-01-01"
        assert end == "2024-01-31"
        symbols = [code] if isinstance(code, str) else list(code)
        return [{"symbol": symbols[0], "date": "2024-01-02", "close": 10.0}]

    monkeypatch.setattr(runtime, "resolve_fetch", lambda **_: _Resolution())
    monkeypatch.setattr(runtime, "load_smoke_window_profile", lambda _path: {})
    monkeypatch.setattr(runtime, "load_exception_decisions", lambda _path: {})
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: _registry_row("fetch_stock_day"))
    monkeypatch.setattr(runtime, "_resolve_callable", lambda _fn_name, source_hint=None: (_fn, "mongo_fetch"))
    monkeypatch.chdir(tmp_path)

    out = runtime.execute_fetch_by_intent(
        {
            "intent": {"asset": "stock", "freq": "day"},
            "symbols": ["000001"],
            "start": "2024-01-01",
            "end": "2024-01-31",
            "policy": {"mode": "research"},
        },
        write_evidence=False,
    )
    assert out.status == runtime.STATUS_PASS_HAS_DATA

    bundles = sorted((tmp_path / "artifacts" / "qa_fetch" / "runtime_fetch_evidence").glob("*/fetch_request.json"))
    assert len(bundles) == 1
    assert (bundles[0].parent / runtime.FETCH_EVIDENCE_RESULT_META_FILENAME).is_file()


def test_execute_fetch_by_intent_rejects_resolution_missing_from_routing_registry(tmp_path, monkeypatch) -> None:
    class _Resolution:
        source = "mongo_fetch"
        public_name = "fetch_stock_day_adv"

    routing_path = tmp_path / "qa_fetch_registry_v1.json"
    _write_routing_registry_payload(
        routing_path,
        resolver_entries=[
            {
                "asset": "stock",
                "freq": "day",
                "venue": None,
                "raw": {"public_name": "fetch_stock_day"},
                "adjustment": {"adv": None},
            }
        ],
    )

    monkeypatch.setattr(runtime, "resolve_fetch", lambda **_: _Resolution())
    monkeypatch.setattr(runtime, "execute_fetch_by_name", lambda **_kwargs: _dummy_result())

    with pytest.raises(ValueError, match=r"not declared in routing registry"):
        runtime.execute_fetch_by_intent(
            {
                "intent": {"asset": "stock", "freq": "day"},
                "symbols": ["000001"],
                "start": "2024-01-01",
                "end": "2024-01-31",
            },
            routing_registry_path=routing_path,
        )


def test_execute_fetch_by_intent_auto_symbols_planner_emits_list_sample_day_steps(tmp_path, monkeypatch) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    class _Resolution:
        source = "mongo_fetch"
        public_name = "fetch_stock_day"

    def _fake_execute_fetch_by_name(*, function: str, kwargs=None, policy=None, **_extra):
        call_kwargs = dict(kwargs or {})
        calls.append((function, call_kwargs))
        if function == "fetch_stock_list":
            return runtime.FetchExecutionResult(
                status=runtime.STATUS_PASS_HAS_DATA,
                reason="ok",
                source="fetch",
                source_internal="mongo_fetch",
                engine="mongo",
                provider_id="fetch",
                provider_internal="mongo_fetch",
                resolved_function="fetch_stock_list",
                public_function="fetch_stock_list",
                elapsed_sec=0.01,
                row_count=3,
                columns=["symbol"],
                dtypes={"symbol": "object"},
                preview=[{"code": "000003"}, {"symbol": "000001"}, {"ticker": "000002"}],
                final_kwargs=call_kwargs,
                mode=policy.mode if isinstance(policy, runtime.FetchExecutionPolicy) else "smoke",
                data=[{"code": "000003"}, {"symbol": "000001"}, {"ticker": "000002"}],
            )
        if function == "fetch_stock_day":
            assert call_kwargs.get("symbols") == ["000003", "000001"]
            return runtime.FetchExecutionResult(
                status=runtime.STATUS_PASS_HAS_DATA,
                reason="ok",
                source="fetch",
                source_internal="mongo_fetch",
                engine="mongo",
                provider_id="fetch",
                provider_internal="mongo_fetch",
                resolved_function="fetch_stock_day",
                public_function="fetch_stock_day",
                elapsed_sec=0.01,
                row_count=1,
                columns=["code", "date", "close"],
                dtypes={"code": "object", "date": "object", "close": "float64"},
                preview=[{"code": "000003", "date": "2024-01-02", "close": 10.0}],
                final_kwargs=call_kwargs,
                mode=policy.mode if isinstance(policy, runtime.FetchExecutionPolicy) else "smoke",
                data=[{"code": "000003", "date": "2024-01-02", "close": 10.0}],
            )
        raise AssertionError(f"unexpected function {function!r}")

    monkeypatch.setattr(runtime, "resolve_fetch", lambda **_: _Resolution())
    monkeypatch.setattr(runtime, "execute_fetch_by_name", _fake_execute_fetch_by_name)
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: _registry_row("fetch_stock_list"))

    out = runtime.execute_fetch_by_intent(
        {
            "intent": {
                "asset": "stock",
                "freq": "day",
                "auto_symbols": True,
                "sample": {"n": 2, "method": "stable_first_n"},
            },
            "start": "2024-01-01",
            "end": "2024-01-31",
            "policy": {"mode": "research"},
        },
        evidence_out_dir=tmp_path,
    )

    assert out.status == runtime.STATUS_PASS_HAS_DATA
    assert calls[0][0] == "fetch_stock_list"
    assert calls[1][0] == "fetch_stock_day"

    idx = json.loads((tmp_path / runtime.FETCH_EVIDENCE_STEPS_INDEX_FILENAME).read_text(encoding="utf-8"))
    assert [step["step_kind"] for step in idx["steps"]] == ["list", "sample", "day"]
    for step_index, step in enumerate(idx["steps"], start=1):
        assert step["step_index"] == step_index
        assert isinstance(step["generated_at"], str) and step["generated_at"]
        assert isinstance(step["trace_id"], str) and step["trace_id"]
        assert isinstance(step["input_summary"], dict)
        assert isinstance(step["output_summary"], dict)
        assert step["input_summary"]["request_hash"]
        assert step["output_summary"]["row_count"] >= 0
        assert step["output_summary"]["col_count"] >= 0
        assert Path(step["request_path"]).is_file()
        assert Path(step["result_meta_path"]).is_file()
        assert Path(step["preview_path"]).is_file()
        assert "error_path" not in step
        assert step["request_path"] == (
            tmp_path / _step_filename(runtime.FETCH_EVIDENCE_STEP_REQUEST_FILENAME_TEMPLATE, step_index=step_index)
        ).as_posix()
        assert step["result_meta_path"] == (
            tmp_path / _step_filename(runtime.FETCH_EVIDENCE_STEP_RESULT_META_FILENAME_TEMPLATE, step_index=step_index)
        ).as_posix()
        assert step["preview_path"] == (
            tmp_path / _step_filename(runtime.FETCH_EVIDENCE_STEP_PREVIEW_FILENAME_TEMPLATE, step_index=step_index)
        ).as_posix()

    canonical_req = json.loads((tmp_path / "fetch_request.json").read_text(encoding="utf-8"))
    step3_req = json.loads(
        (tmp_path / _step_filename(runtime.FETCH_EVIDENCE_STEP_REQUEST_FILENAME_TEMPLATE, step_index=3)).read_text(
            encoding="utf-8"
        )
    )
    assert canonical_req == step3_req
    assert canonical_req["intent"]["symbols"] == ["000003", "000001"]
    assert canonical_req["intent"]["auto_symbols"] is False


def test_execute_fetch_by_intent_auto_symbols_planner_derives_candidates_from_data_when_preview_missing_symbols(
    tmp_path, monkeypatch
) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    class _Resolution:
        source = "mongo_fetch"
        public_name = "fetch_stock_day"

    def _fake_execute_fetch_by_name(*, function: str, kwargs=None, policy=None, **_extra):
        call_kwargs = dict(kwargs or {})
        calls.append((function, call_kwargs))
        if function == "fetch_stock_list":
            return runtime.FetchExecutionResult(
                status=runtime.STATUS_PASS_HAS_DATA,
                reason="ok",
                source="fetch",
                source_internal="mongo_fetch",
                engine="mongo",
                provider_id="fetch",
                provider_internal="mongo_fetch",
                resolved_function="fetch_stock_list",
                public_function="fetch_stock_list",
                elapsed_sec=0.01,
                row_count=1,
                columns=["id"],
                dtypes={"id": "int64"},
                preview=[{"id": 1}],
                final_kwargs=call_kwargs,
                mode=policy.mode if isinstance(policy, runtime.FetchExecutionPolicy) else "smoke",
                data=[{"symbol": "000009"}],
            )
        if function == "fetch_stock_day":
            assert call_kwargs.get("symbols") == "000009"
            return runtime.FetchExecutionResult(
                status=runtime.STATUS_PASS_HAS_DATA,
                reason="ok",
                source="fetch",
                source_internal="mongo_fetch",
                engine="mongo",
                provider_id="fetch",
                provider_internal="mongo_fetch",
                resolved_function="fetch_stock_day",
                public_function="fetch_stock_day",
                elapsed_sec=0.01,
                row_count=1,
                columns=["code", "date", "close"],
                dtypes={"code": "object", "date": "object", "close": "float64"},
                preview=[{"code": "000009", "date": "2024-01-02", "close": 10.0}],
                final_kwargs=call_kwargs,
                mode=policy.mode if isinstance(policy, runtime.FetchExecutionPolicy) else "smoke",
                data=[{"code": "000009", "date": "2024-01-02", "close": 10.0}],
            )
        raise AssertionError(f"unexpected function {function!r}")

    monkeypatch.setattr(runtime, "resolve_fetch", lambda **_: _Resolution())
    monkeypatch.setattr(runtime, "execute_fetch_by_name", _fake_execute_fetch_by_name)
    monkeypatch.setattr(runtime, "_validate_routing_registry_resolution", lambda **_kwargs: None)
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: _registry_row("fetch_stock_list", source="mongo_fetch"))

    out = runtime.execute_fetch_by_intent(
        {
            "intent": {"asset": "stock", "freq": "day", "auto_symbols": True},
            "start": "2024-01-01",
            "end": "2024-01-31",
            "policy": {"mode": "research"},
        },
        evidence_out_dir=tmp_path,
    )

    assert out.status == runtime.STATUS_PASS_HAS_DATA
    assert [name for name, _kwargs in calls] == ["fetch_stock_list", "fetch_stock_day"]


def test_execute_fetch_by_intent_run_id_emits_multistep_evidence_into_dossier_fetch_root(tmp_path, monkeypatch) -> None:
    class _Resolution:
        source = "mongo_fetch"
        public_name = "fetch_stock_day"

    def _fake_execute_fetch_by_name(*, function: str, kwargs=None, policy=None, **_extra):
        call_kwargs = dict(kwargs or {})
        if function == "fetch_stock_list":
            return runtime.FetchExecutionResult(
                status=runtime.STATUS_PASS_HAS_DATA,
                reason="ok",
                source="fetch",
                source_internal="mongo_fetch",
                engine="mongo",
                provider_id="fetch",
                provider_internal="mongo_fetch",
                resolved_function="fetch_stock_list",
                public_function="fetch_stock_list",
                elapsed_sec=0.01,
                row_count=3,
                columns=["symbol"],
                dtypes={"symbol": "object"},
                preview=[{"code": "000003"}, {"symbol": "000001"}, {"ticker": "000002"}],
                final_kwargs=call_kwargs,
                mode=policy.mode if isinstance(policy, runtime.FetchExecutionPolicy) else "smoke",
                data=[{"code": "000003"}, {"symbol": "000001"}, {"ticker": "000002"}],
            )
        if function == "fetch_stock_day":
            return runtime.FetchExecutionResult(
                status=runtime.STATUS_PASS_HAS_DATA,
                reason="ok",
                source="fetch",
                source_internal="mongo_fetch",
                engine="mongo",
                provider_id="fetch",
                provider_internal="mongo_fetch",
                resolved_function="fetch_stock_day",
                public_function="fetch_stock_day",
                elapsed_sec=0.01,
                row_count=1,
                columns=["code", "date", "close"],
                dtypes={"code": "object", "date": "object", "close": "float64"},
                preview=[{"code": "000003", "date": "2024-01-02", "close": 10.0}],
                final_kwargs=call_kwargs,
                mode=policy.mode if isinstance(policy, runtime.FetchExecutionPolicy) else "smoke",
                data=[{"code": "000003", "date": "2024-01-02", "close": 10.0}],
            )
        raise AssertionError(f"unexpected function {function!r}")

    monkeypatch.setattr(runtime, "resolve_fetch", lambda **_: _Resolution())
    monkeypatch.setattr(runtime, "execute_fetch_by_name", _fake_execute_fetch_by_name)
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: _registry_row("fetch_stock_list"))
    monkeypatch.chdir(tmp_path)
    snapshot_manifest_path = tmp_path / "data_lake" / "snapshot_run_intent_001" / "manifest.json"
    snapshot_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_manifest_path.write_text('{"schema_version":"data_snapshot_manifest_v1"}\n', encoding="utf-8")

    out = runtime.execute_fetch_by_intent(
        {
            "run_id": "run_intent_001",
            "intent": {
                "asset": "stock",
                "freq": "day",
                "auto_symbols": True,
                "sample": {"n": 2, "method": "stable_first_n"},
            },
            "start": "2024-01-01",
            "end": "2024-01-31",
            "policy": {
                "mode": "research",
                "snapshot_manifest_path": snapshot_manifest_path.as_posix(),
            },
        }
    )

    assert out.status == runtime.STATUS_PASS_HAS_DATA
    dossier_fetch_rel = Path("artifacts") / "dossiers" / "run_intent_001" / "fetch"
    dossier_fetch = tmp_path / "artifacts" / "dossiers" / "run_intent_001" / "fetch"
    idx = json.loads((dossier_fetch / runtime.FETCH_EVIDENCE_STEPS_INDEX_FILENAME).read_text(encoding="utf-8"))
    assert [step["step_kind"] for step in idx["steps"]] == ["list", "sample", "day"]
    for step_index, step in enumerate(idx["steps"], start=1):
        assert step["step_index"] == step_index
        assert step["request_path"] == (
            dossier_fetch_rel
            / _step_filename(runtime.FETCH_EVIDENCE_STEP_REQUEST_FILENAME_TEMPLATE, step_index=step_index)
        ).as_posix()
        assert step["result_meta_path"] == (
            dossier_fetch_rel
            / _step_filename(runtime.FETCH_EVIDENCE_STEP_RESULT_META_FILENAME_TEMPLATE, step_index=step_index)
        ).as_posix()
        assert step["preview_path"] == (
            dossier_fetch_rel
            / _step_filename(runtime.FETCH_EVIDENCE_STEP_PREVIEW_FILENAME_TEMPLATE, step_index=step_index)
        ).as_posix()
        assert Path(step["request_path"]).is_file()
        assert Path(step["result_meta_path"]).is_file()
        assert Path(step["preview_path"]).is_file()

    canonical_req = json.loads((dossier_fetch / runtime.FETCH_EVIDENCE_REQUEST_FILENAME).read_text(encoding="utf-8"))
    step3_req = json.loads(
        (
            dossier_fetch / _step_filename(runtime.FETCH_EVIDENCE_STEP_REQUEST_FILENAME_TEMPLATE, step_index=3)
        ).read_text(encoding="utf-8")
    )
    assert canonical_req == step3_req
    assert canonical_req["intent"]["auto_symbols"] is False


def test_execute_fetch_by_intent_auto_symbols_planner_prefers_source_matched_list_function(tmp_path, monkeypatch) -> None:
    calls: list[str] = []

    class _Resolution:
        source = "mongo_fetch"
        public_name = "fetch_future_day"

    registry_rows = {
        "fetch_future_list": {
            "function": "fetch_future_list",
            "source_internal": "mysql_fetch",
            "status": "active",
        },
        "fetch_ctp_future_list": {
            "function": "fetch_ctp_future_list",
            "source_internal": "mongo_fetch",
            "status": "active",
        },
    }

    def _fake_execute_fetch_by_name(*, function: str, kwargs=None, policy=None, **_extra):
        call_kwargs = dict(kwargs or {})
        calls.append(function)
        if function == "fetch_future_list":
            raise AssertionError("planner should prioritize source-matched list function first")
        if function == "fetch_ctp_future_list":
            return runtime.FetchExecutionResult(
                status=runtime.STATUS_PASS_HAS_DATA,
                reason="ok",
                source="fetch",
                source_internal="mongo_fetch",
                engine="mongo",
                provider_id="fetch",
                provider_internal="mongo_fetch",
                resolved_function="fetch_ctp_future_list",
                public_function="fetch_ctp_future_list",
                elapsed_sec=0.01,
                row_count=1,
                columns=["symbol"],
                dtypes={"symbol": "object"},
                preview=[{"symbol": "IF9999"}],
                final_kwargs=call_kwargs,
                mode=policy.mode if isinstance(policy, runtime.FetchExecutionPolicy) else "smoke",
                data=[{"symbol": "IF9999"}],
            )
        if function == "fetch_future_day":
            assert call_kwargs.get("symbols") == "IF9999"
            return runtime.FetchExecutionResult(
                status=runtime.STATUS_PASS_HAS_DATA,
                reason="ok",
                source="fetch",
                source_internal="mongo_fetch",
                engine="mongo",
                provider_id="fetch",
                provider_internal="mongo_fetch",
                resolved_function="fetch_future_day",
                public_function="fetch_future_day",
                elapsed_sec=0.01,
                row_count=1,
                columns=["symbol", "date", "close"],
                dtypes={"symbol": "object", "date": "object", "close": "float64"},
                preview=[{"symbol": "IF9999", "date": "2024-01-02", "close": 10.0}],
                final_kwargs=call_kwargs,
                mode=policy.mode if isinstance(policy, runtime.FetchExecutionPolicy) else "smoke",
                data=[{"symbol": "IF9999", "date": "2024-01-02", "close": 10.0}],
            )
        raise AssertionError(f"unexpected function {function!r}")

    monkeypatch.setattr(runtime, "resolve_fetch", lambda **_: _Resolution())
    monkeypatch.setattr(runtime, "execute_fetch_by_name", _fake_execute_fetch_by_name)
    monkeypatch.setattr(runtime, "_validate_routing_registry_resolution", lambda **_kwargs: None)
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: dict(registry_rows))

    out = runtime.execute_fetch_by_intent(
        {
            "intent": {"asset": "future", "freq": "day", "auto_symbols": True},
            "start": "2024-01-01",
            "end": "2024-01-31",
            "policy": {"mode": "research"},
        },
        evidence_out_dir=tmp_path,
    )

    assert out.status == runtime.STATUS_PASS_HAS_DATA
    assert calls[0] == "fetch_ctp_future_list"
    assert calls[1] == "fetch_future_day"


def test_execute_fetch_by_intent_auto_symbols_planner_normalizes_random_alias_with_deterministic_seed(
    tmp_path, monkeypatch
) -> None:
    class _Resolution:
        source = "mongo_fetch"
        public_name = "fetch_stock_day"

    def _fake_execute_fetch_by_name(*, function: str, kwargs=None, policy=None, **_extra):
        call_kwargs = dict(kwargs or {})
        if function == "fetch_stock_list":
            return runtime.FetchExecutionResult(
                status=runtime.STATUS_PASS_HAS_DATA,
                reason="ok",
                source="fetch",
                source_internal="mongo_fetch",
                engine="mongo",
                provider_id="fetch",
                provider_internal="mongo_fetch",
                resolved_function="fetch_stock_list",
                public_function="fetch_stock_list",
                elapsed_sec=0.01,
                row_count=3,
                columns=["symbol"],
                dtypes={"symbol": "object"},
                preview=[{"code": "000003"}, {"symbol": "000001"}, {"ticker": "000002"}],
                final_kwargs=call_kwargs,
                mode=policy.mode if isinstance(policy, runtime.FetchExecutionPolicy) else "smoke",
                data=[{"code": "000003"}, {"symbol": "000001"}, {"ticker": "000002"}],
            )
        if function == "fetch_stock_day":
            return runtime.FetchExecutionResult(
                status=runtime.STATUS_PASS_HAS_DATA,
                reason="ok",
                source="fetch",
                source_internal="mongo_fetch",
                engine="mongo",
                provider_id="fetch",
                provider_internal="mongo_fetch",
                resolved_function="fetch_stock_day",
                public_function="fetch_stock_day",
                elapsed_sec=0.01,
                row_count=1,
                columns=["code", "date", "close"],
                dtypes={"code": "object", "date": "object", "close": "float64"},
                preview=[{"code": "000003", "date": "2024-01-02", "close": 10.0}],
                final_kwargs=call_kwargs,
                mode=policy.mode if isinstance(policy, runtime.FetchExecutionPolicy) else "smoke",
                data=[{"code": "000003", "date": "2024-01-02", "close": 10.0}],
            )
        raise AssertionError(f"unexpected function {function!r}")

    monkeypatch.setattr(runtime, "resolve_fetch", lambda **_: _Resolution())
    monkeypatch.setattr(runtime, "execute_fetch_by_name", _fake_execute_fetch_by_name)
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: _registry_row("fetch_stock_list"))

    out = runtime.execute_fetch_by_intent(
        {
            "intent": {
                "asset": "stock",
                "freq": "day",
                "auto_symbols": True,
                "sample": {"n": 2, "method": "random_shuffle"},
            },
            "start": "2024-01-01",
            "end": "2024-01-31",
            "policy": {"mode": "research"},
        },
        evidence_out_dir=tmp_path,
    )

    assert out.status == runtime.STATUS_PASS_HAS_DATA
    idx = json.loads((tmp_path / runtime.FETCH_EVIDENCE_STEPS_INDEX_FILENAME).read_text(encoding="utf-8"))
    assert [step["step_kind"] for step in idx["steps"]] == list(runtime.AUTO_SYMBOLS_MA250_STEP_SEQUENCE)
    step2_req = json.loads(Path(idx["steps"][1]["request_path"]).read_text(encoding="utf-8"))
    assert step2_req["sample"] == {"n": 2, "method": "random"}
    assert step2_req["sample_strategy"]["method"] == "random"
    assert step2_req["sample_strategy"]["seed"] == runtime.AUTO_SYMBOLS_DEFAULT_SAMPLE_SEED
    step2_meta = json.loads(Path(idx["steps"][1]["result_meta_path"]).read_text(encoding="utf-8"))
    assert step2_meta["final_kwargs"]["sample_method"] == "random"
    assert step2_meta["final_kwargs"]["sample_strategy"]["seed"] == runtime.AUTO_SYMBOLS_DEFAULT_SAMPLE_SEED


def test_execute_fetch_by_intent_auto_symbols_planner_applies_max_symbols_boundary(tmp_path, monkeypatch) -> None:
    class _Resolution:
        source = "mongo_fetch"
        public_name = "fetch_stock_day"

    day_kwargs_seen: dict[str, Any] = {}

    def _fake_execute_fetch_by_name(*, function: str, kwargs=None, policy=None, **_extra):
        call_kwargs = dict(kwargs or {})
        if function == "fetch_stock_list":
            return runtime.FetchExecutionResult(
                status=runtime.STATUS_PASS_HAS_DATA,
                reason="ok",
                source="fetch",
                source_internal="mongo_fetch",
                engine="mongo",
                provider_id="fetch",
                provider_internal="mongo_fetch",
                resolved_function="fetch_stock_list",
                public_function="fetch_stock_list",
                elapsed_sec=0.01,
                row_count=3,
                columns=["symbol"],
                dtypes={"symbol": "object"},
                preview=[{"code": "000003", "amount": 100.0}, {"symbol": "000001", "amount": 200.0}, {"ticker": "000002", "amount": 300.0}],
                final_kwargs=call_kwargs,
                mode=policy.mode if isinstance(policy, runtime.FetchExecutionPolicy) else "smoke",
                data=[{"code": "000003", "amount": 100.0}, {"symbol": "000001", "amount": 200.0}, {"ticker": "000002", "amount": 300.0}],
            )
        if function == "fetch_stock_day":
            day_kwargs_seen.update(call_kwargs)
            return runtime.FetchExecutionResult(
                status=runtime.STATUS_PASS_HAS_DATA,
                reason="ok",
                source="fetch",
                source_internal="mongo_fetch",
                engine="mongo",
                provider_id="fetch",
                provider_internal="mongo_fetch",
                resolved_function="fetch_stock_day",
                public_function="fetch_stock_day",
                elapsed_sec=0.01,
                row_count=1,
                columns=["code", "date", "close"],
                dtypes={"code": "object", "date": "object", "close": "float64"},
                preview=[{"code": "000003", "date": "2024-01-02", "close": 10.0}],
                final_kwargs=call_kwargs,
                mode=policy.mode if isinstance(policy, runtime.FetchExecutionPolicy) else "smoke",
                data=[{"code": "000003", "date": "2024-01-02", "close": 10.0}],
            )
        raise AssertionError(f"unexpected function {function!r}")

    monkeypatch.setattr(runtime, "resolve_fetch", lambda **_: _Resolution())
    monkeypatch.setattr(runtime, "execute_fetch_by_name", _fake_execute_fetch_by_name)
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: _registry_row("fetch_stock_list"))

    out = runtime.execute_fetch_by_intent(
        {
            "intent": {
                "asset": "stock",
                "freq": "day",
                "auto_symbols": True,
                "sample": {"n": 5, "method": "liquidity"},
            },
            "start": "2024-01-01",
            "end": "2024-01-31",
            "policy": {"mode": "research", "max_symbols": 1},
        },
        evidence_out_dir=tmp_path,
    )

    assert out.status == runtime.STATUS_PASS_HAS_DATA
    assert day_kwargs_seen["symbols"] == "000002"
    idx = json.loads((tmp_path / runtime.FETCH_EVIDENCE_STEPS_INDEX_FILENAME).read_text(encoding="utf-8"))
    step2_req = json.loads(Path(idx["steps"][1]["request_path"]).read_text(encoding="utf-8"))
    assert step2_req["sample"] == {"n": 1, "method": "liquidity"}
    assert step2_req["sample_strategy"]["liquidity_field"] == "amount"


def test_execute_fetch_by_intent_auto_symbols_planner_supports_industry_stratified_strategy(tmp_path, monkeypatch) -> None:
    class _Resolution:
        source = "mongo_fetch"
        public_name = "fetch_stock_day"

    day_kwargs_seen: dict[str, Any] = {}

    def _fake_execute_fetch_by_name(*, function: str, kwargs=None, policy=None, **_extra):
        call_kwargs = dict(kwargs or {})
        if function == "fetch_stock_list":
            return runtime.FetchExecutionResult(
                status=runtime.STATUS_PASS_HAS_DATA,
                reason="ok",
                source="fetch",
                source_internal="mongo_fetch",
                engine="mongo",
                provider_id="fetch",
                provider_internal="mongo_fetch",
                resolved_function="fetch_stock_list",
                public_function="fetch_stock_list",
                elapsed_sec=0.01,
                row_count=4,
                columns=["symbol", "industry"],
                dtypes={"symbol": "object", "industry": "object"},
                preview=[
                    {"symbol": "000001", "industry": "bank"},
                    {"symbol": "000002", "industry": "bank"},
                    {"symbol": "000003", "industry": "steel"},
                    {"symbol": "000004", "industry": "steel"},
                ],
                final_kwargs=call_kwargs,
                mode=policy.mode if isinstance(policy, runtime.FetchExecutionPolicy) else "smoke",
                data=[
                    {"symbol": "000001", "industry": "bank"},
                    {"symbol": "000002", "industry": "bank"},
                    {"symbol": "000003", "industry": "steel"},
                    {"symbol": "000004", "industry": "steel"},
                ],
            )
        if function == "fetch_stock_day":
            day_kwargs_seen.update(call_kwargs)
            return runtime.FetchExecutionResult(
                status=runtime.STATUS_PASS_HAS_DATA,
                reason="ok",
                source="fetch",
                source_internal="mongo_fetch",
                engine="mongo",
                provider_id="fetch",
                provider_internal="mongo_fetch",
                resolved_function="fetch_stock_day",
                public_function="fetch_stock_day",
                elapsed_sec=0.01,
                row_count=1,
                columns=["symbol", "date", "close"],
                dtypes={"symbol": "object", "date": "object", "close": "float64"},
                preview=[{"symbol": "000001", "date": "2024-01-02", "close": 10.0}],
                final_kwargs=call_kwargs,
                mode=policy.mode if isinstance(policy, runtime.FetchExecutionPolicy) else "smoke",
                data=[{"symbol": "000001", "date": "2024-01-02", "close": 10.0}],
            )
        raise AssertionError(f"unexpected function {function!r}")

    monkeypatch.setattr(runtime, "resolve_fetch", lambda **_: _Resolution())
    monkeypatch.setattr(runtime, "execute_fetch_by_name", _fake_execute_fetch_by_name)
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: _registry_row("fetch_stock_list"))

    out = runtime.execute_fetch_by_intent(
        {
            "intent": {
                "asset": "stock",
                "freq": "day",
                "auto_symbols": True,
                "sample": {"n": 3, "method": "industry_stratified"},
            },
            "start": "2024-01-01",
            "end": "2024-01-31",
            "policy": {"mode": "research"},
        },
        evidence_out_dir=tmp_path,
    )

    assert out.status == runtime.STATUS_PASS_HAS_DATA
    assert day_kwargs_seen["symbols"] == ["000001", "000003", "000002"]
    idx = json.loads((tmp_path / runtime.FETCH_EVIDENCE_STEPS_INDEX_FILENAME).read_text(encoding="utf-8"))
    step2_req = json.loads(Path(idx["steps"][1]["request_path"]).read_text(encoding="utf-8"))
    assert step2_req["sample"] == {"n": 3, "method": "industry_stratified"}
    assert step2_req["sample_strategy"]["industry_field"] == "industry"


def test_execute_fetch_by_intent_auto_symbols_planner_no_candidates_returns_runtime_error(tmp_path, monkeypatch) -> None:
    calls: list[str] = []

    class _Resolution:
        source = "mysql_fetch"
        public_name = "fetch_stock_day"

    def _fake_execute_fetch_by_name(*, function: str, kwargs=None, policy=None, **_extra):
        calls.append(function)
        assert function == "fetch_stock_list"
        call_kwargs = dict(kwargs or {})
        return runtime.FetchExecutionResult(
            status=runtime.STATUS_PASS_EMPTY,
            reason="no_data",
            source="fetch",
            source_internal="mysql_fetch",
            engine="mysql",
            provider_id="fetch",
            provider_internal="mysql_fetch",
            resolved_function="fetch_stock_list",
            public_function="fetch_stock_list",
            elapsed_sec=0.01,
            row_count=0,
            columns=[],
            dtypes={},
            preview=[],
            final_kwargs=call_kwargs,
            mode=policy.mode if isinstance(policy, runtime.FetchExecutionPolicy) else "smoke",
            data=[],
        )

    monkeypatch.setattr(runtime, "resolve_fetch", lambda **_: _Resolution())
    monkeypatch.setattr(runtime, "execute_fetch_by_name", _fake_execute_fetch_by_name)
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: _registry_row("fetch_stock_list", source="mysql_fetch"))

    out = runtime.execute_fetch_by_intent(
        {
            "intent": {"asset": "stock", "freq": "day", "auto_symbols": True},
            "start": "2024-01-01",
            "end": "2024-01-31",
            "policy": {"mode": "smoke"},
        },
        evidence_out_dir=tmp_path,
    )

    assert out.status == runtime.STATUS_ERROR_RUNTIME
    assert "sample step produced no symbols" in out.reason
    assert calls == ["fetch_stock_list"]

    idx = json.loads((tmp_path / runtime.FETCH_EVIDENCE_STEPS_INDEX_FILENAME).read_text(encoding="utf-8"))
    assert [step["step_kind"] for step in idx["steps"]] == ["list", "sample", "day"]
    assert [step["status"] for step in idx["steps"]] == [
        runtime.STATUS_PASS_EMPTY,
        runtime.STATUS_PASS_EMPTY,
        runtime.STATUS_ERROR_RUNTIME,
    ]
    for step_index, step in enumerate(idx["steps"], start=1):
        assert step["step_index"] == step_index
        assert Path(step["request_path"]).is_file()
        assert Path(step["result_meta_path"]).is_file()
        assert Path(step["preview_path"]).is_file()
        assert step["request_path"] == (
            tmp_path / _step_filename(runtime.FETCH_EVIDENCE_STEP_REQUEST_FILENAME_TEMPLATE, step_index=step_index)
        ).as_posix()
        assert step["result_meta_path"] == (
            tmp_path / _step_filename(runtime.FETCH_EVIDENCE_STEP_RESULT_META_FILENAME_TEMPLATE, step_index=step_index)
        ).as_posix()
        assert step["preview_path"] == (
            tmp_path / _step_filename(runtime.FETCH_EVIDENCE_STEP_PREVIEW_FILENAME_TEMPLATE, step_index=step_index)
        ).as_posix()
    assert (tmp_path / _step_filename(runtime.FETCH_EVIDENCE_STEP_ERROR_FILENAME_TEMPLATE, step_index=3)).is_file()


def test_execute_fetch_by_intent_auto_symbols_planner_list_failure_blocks_sample_and_day(tmp_path, monkeypatch) -> None:
    calls: list[str] = []

    class _Resolution:
        source = "mysql_fetch"
        public_name = "fetch_stock_day"

    def _fake_execute_fetch_by_name(*, function: str, kwargs=None, policy=None, **_extra):
        calls.append(function)
        assert function == "fetch_stock_list"
        call_kwargs = dict(kwargs or {})
        return runtime.FetchExecutionResult(
            status=runtime.STATUS_ERROR_RUNTIME,
            reason="RuntimeError: upstream list failure",
            source="fetch",
            source_internal="mysql_fetch",
            engine="mysql",
            provider_id="fetch",
            provider_internal="mysql_fetch",
            resolved_function="fetch_stock_list",
            public_function="fetch_stock_list",
            elapsed_sec=0.01,
            row_count=0,
            columns=[],
            dtypes={},
            preview=[],
            final_kwargs=call_kwargs,
            mode=policy.mode if isinstance(policy, runtime.FetchExecutionPolicy) else "smoke",
            data=None,
        )

    monkeypatch.setattr(runtime, "resolve_fetch", lambda **_: _Resolution())
    monkeypatch.setattr(runtime, "execute_fetch_by_name", _fake_execute_fetch_by_name)
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: _registry_row("fetch_stock_list", source="mysql_fetch"))

    out = runtime.execute_fetch_by_intent(
        {
            "intent": {"asset": "stock", "freq": "day", "auto_symbols": True},
            "start": "2024-01-01",
            "end": "2024-01-31",
            "policy": {"mode": "smoke"},
        },
        evidence_out_dir=tmp_path,
    )

    assert out.status == runtime.STATUS_ERROR_RUNTIME
    assert "sample step produced no symbols" in out.reason
    assert calls == ["fetch_stock_list"]

    idx = json.loads((tmp_path / runtime.FETCH_EVIDENCE_STEPS_INDEX_FILENAME).read_text(encoding="utf-8"))
    assert [step["step_kind"] for step in idx["steps"]] == ["list", "sample", "day"]
    assert [step["status"] for step in idx["steps"]] == [
        runtime.STATUS_ERROR_RUNTIME,
        runtime.STATUS_BLOCKED_SOURCE_MISSING,
        runtime.STATUS_ERROR_RUNTIME,
    ]
    step2_req = json.loads(Path(idx["steps"][1]["request_path"]).read_text(encoding="utf-8"))
    assert step2_req["candidates_preview_count"] == 0
    step2_meta = json.loads(Path(idx["steps"][1]["result_meta_path"]).read_text(encoding="utf-8"))
    assert step2_meta["final_kwargs"]["sample_method"] == runtime.AUTO_SYMBOLS_DEFAULT_SAMPLE_METHOD
    assert Path(idx["steps"][1]["error_path"]).is_file()
    assert Path(idx["steps"][2]["error_path"]).is_file()


def test_execute_fetch_by_intent_auto_symbols_planner_does_not_use_unrelated_list(tmp_path, monkeypatch) -> None:
    calls: list[str] = []

    class _Resolution:
        source = "mysql_fetch"
        public_name = "fetch_stock_day"

    def _fake_execute_fetch_by_name(*, function: str, **_kwargs):
        calls.append(function)
        raise AssertionError("planner must not execute unrelated list functions")

    monkeypatch.setattr(runtime, "resolve_fetch", lambda **_: _Resolution())
    monkeypatch.setattr(runtime, "execute_fetch_by_name", _fake_execute_fetch_by_name)
    monkeypatch.setattr(runtime, "load_function_registry", lambda _path: _registry_row("fetch_etf_list", source="mysql_fetch"))

    out = runtime.execute_fetch_by_intent(
        {
            "intent": {"asset": "stock", "freq": "day", "auto_symbols": True},
            "start": "2024-01-01",
            "end": "2024-01-31",
            "policy": {"mode": "smoke"},
        },
        evidence_out_dir=tmp_path,
    )

    assert out.status == runtime.STATUS_ERROR_RUNTIME
    assert "sample step produced no symbols" in out.reason
    assert calls == []

    idx = json.loads((tmp_path / runtime.FETCH_EVIDENCE_STEPS_INDEX_FILENAME).read_text(encoding="utf-8"))
    assert [step["step_kind"] for step in idx["steps"]] == ["list", "sample", "day"]
    assert [step["status"] for step in idx["steps"]] == [
        runtime.STATUS_ERROR_RUNTIME,
        runtime.STATUS_BLOCKED_SOURCE_MISSING,
        runtime.STATUS_ERROR_RUNTIME,
    ]
    step1_req = json.loads(
        (tmp_path / _step_filename(runtime.FETCH_EVIDENCE_STEP_REQUEST_FILENAME_TEMPLATE, step_index=1)).read_text(
            encoding="utf-8"
        )
    )
    assert step1_req["reason"] == "auto_symbols_list_function_missing"


def test_execute_fetch_by_intent_auto_symbols_skips_planner_when_code_is_present(tmp_path, monkeypatch) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    class _Resolution:
        source = "mysql_fetch"
        public_name = "fetch_stock_day"

    def _fake_execute_fetch_by_name(*, function: str, kwargs=None, policy=None, **_extra):
        call_kwargs = dict(kwargs or {})
        calls.append((function, call_kwargs))
        return runtime.FetchExecutionResult(
            status=runtime.STATUS_PASS_HAS_DATA,
            reason="ok",
            source="fetch",
            source_internal="mysql_fetch",
            engine="mysql",
            provider_id="fetch",
            provider_internal="mysql_fetch",
            resolved_function=function,
            public_function=function,
            elapsed_sec=0.01,
            row_count=1,
            columns=["code", "date", "close"],
            dtypes={"code": "object", "date": "object", "close": "float64"},
            preview=[{"code": "000001", "date": "2024-01-02", "close": 10.0}],
            final_kwargs=call_kwargs,
            mode=policy.mode if isinstance(policy, runtime.FetchExecutionPolicy) else "smoke",
            data=[{"code": "000001", "date": "2024-01-02", "close": 10.0}],
        )

    monkeypatch.setattr(runtime, "resolve_fetch", lambda **_: _Resolution())
    monkeypatch.setattr(runtime, "execute_fetch_by_name", _fake_execute_fetch_by_name)
    monkeypatch.setattr(runtime, "_validate_routing_registry_resolution", lambda **_kwargs: None)

    out = runtime.execute_fetch_by_intent(
        {
            "intent": {
                "asset": "stock",
                "freq": "day",
                "auto_symbols": True,
                "start": "2024-01-01",
                "end": "2024-01-31",
                "extra_kwargs": {"code": "000001"},
            },
            "policy": {"mode": "research"},
        },
        evidence_out_dir=tmp_path,
    )

    assert out.status == runtime.STATUS_PASS_HAS_DATA
    assert calls == [
        (
            "fetch_stock_day",
            {
                "code": "000001",
                "start": "2024-01-01",
                "end": "2024-01-31",
                "fields": list(runtime.TECHNICAL_INDICATOR_MIN_FIELDS_OHLCV),
            },
        )
    ]
    idx = json.loads((tmp_path / runtime.FETCH_EVIDENCE_STEPS_INDEX_FILENAME).read_text(encoding="utf-8"))
    assert len(idx["steps"]) == 1
    assert idx["steps"][0]["step_index"] == 1
    assert idx["steps"][0]["step_kind"] == "single_fetch"


def test_execute_fetch_by_intent_auto_symbols_false_skips_planner(tmp_path, monkeypatch) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    class _Resolution:
        source = "mysql_fetch"
        public_name = "fetch_stock_day"

    def _fake_execute_fetch_by_name(*, function: str, kwargs=None, policy=None, **_extra):
        call_kwargs = dict(kwargs or {})
        calls.append((function, call_kwargs))
        return runtime.FetchExecutionResult(
            status=runtime.STATUS_PASS_HAS_DATA,
            reason="ok",
            source="fetch",
            source_internal="mysql_fetch",
            engine="mysql",
            provider_id="fetch",
            provider_internal="mysql_fetch",
            resolved_function=function,
            public_function=function,
            elapsed_sec=0.01,
            row_count=1,
            columns=["code", "date", "close"],
            dtypes={"code": "object", "date": "object", "close": "float64"},
            preview=[{"code": "000001", "date": "2024-01-02", "close": 10.0}],
            final_kwargs=call_kwargs,
            mode=policy.mode if isinstance(policy, runtime.FetchExecutionPolicy) else "smoke",
            data=[{"code": "000001", "date": "2024-01-02", "close": 10.0}],
        )

    def _planner_should_not_run(**_kwargs):
        raise AssertionError("auto-symbols planner should not run when auto_symbols is false")

    monkeypatch.setattr(runtime, "resolve_fetch", lambda **_: _Resolution())
    monkeypatch.setattr(runtime, "execute_fetch_by_name", _fake_execute_fetch_by_name)
    monkeypatch.setattr(runtime, "_run_auto_symbols_planner_for_intent", _planner_should_not_run)
    monkeypatch.setattr(runtime, "_validate_routing_registry_resolution", lambda **_kwargs: None)

    out = runtime.execute_fetch_by_intent(
        {
            "intent": {
                "asset": "stock",
                "freq": "day",
                "auto_symbols": False,
            },
            "start": "2024-01-01",
            "end": "2024-01-31",
            "policy": {"mode": "research"},
        },
        evidence_out_dir=tmp_path,
    )

    assert out.status == runtime.STATUS_PASS_HAS_DATA
    assert len(calls) == 1
    assert calls[0][0] == "fetch_stock_day"
    assert calls[0][1]["fields"] == list(runtime.TECHNICAL_INDICATOR_MIN_FIELDS_OHLCV)
    idx = json.loads((tmp_path / runtime.FETCH_EVIDENCE_STEPS_INDEX_FILENAME).read_text(encoding="utf-8"))
    assert len(idx["steps"]) == 1
    assert idx["steps"][0]["step_kind"] == "single_fetch"


def _dummy_result() -> runtime.FetchExecutionResult:
    return runtime.FetchExecutionResult(
        status=runtime.STATUS_PASS_HAS_DATA,
        reason="ok",
        source="fetch",
        source_internal="mysql_fetch",
        engine="mysql",
        provider_id="fetch",
        provider_internal="mysql_fetch",
        resolved_function="fetch_demo",
        public_function="fetch_demo",
        elapsed_sec=0.0,
        row_count=1,
        columns=["x"],
        dtypes={"x": "int64"},
        preview=[{"x": 1}],
        final_kwargs={"x": 1},
        mode="backtest",
        data=[{"x": 1}],
    )


def test_execute_fetch_by_intent_accepts_fetch_request_wrapper(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class _Resolution:
        source = "mysql_fetch"
        public_name = "fetch_stock_day"

    def _fake_execute_fetch_by_name(**kwargs):
        captured.update(kwargs)
        return _dummy_result()

    monkeypatch.setattr(runtime, "resolve_fetch", lambda **_: _Resolution())
    monkeypatch.setattr(runtime, "execute_fetch_by_name", _fake_execute_fetch_by_name)

    payload = {
        "intent": {
            "asset": "stock",
            "freq": "day",
            "extra_kwargs": {"bar": 2},
        },
        "symbols": ["000001"],
        "start": "2024-01-01",
        "end": "2024-01-31",
        "kwargs": {"foo": 1, "bar": 9},
        "policy": {
            "mode": "backtest",
            "on_no_data": "error",
            "max_symbols": 4,
            "max_rows": 120,
            "retry_strategy": {"max_attempts": 3},
        },
    }
    _ = runtime.execute_fetch_by_intent(payload)

    assert captured["function"] == "fetch_stock_day"
    assert captured["source_hint"] == "mysql_fetch"
    assert isinstance(captured["policy"], runtime.FetchExecutionPolicy)
    assert captured["policy"].mode == "backtest"
    assert captured["policy"].on_no_data == "error"
    assert captured["policy"].max_symbols == 4
    assert captured["policy"].max_rows == 120
    assert captured["policy"].retry_strategy == {"max_attempts": 3}
    assert captured["kwargs"]["symbols"] == ["000001"]
    assert captured["kwargs"]["start"] == "2024-01-01"
    assert captured["kwargs"]["end"] == "2024-01-31"
    assert captured["kwargs"]["foo"] == 1
    # intent.extra_kwargs should have higher priority than top-level kwargs on collisions.
    assert captured["kwargs"]["bar"] == 2


def test_execute_fetch_by_intent_prefers_nested_intent_over_top_level_fields(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class _Resolution:
        source = "mysql_fetch"
        public_name = "fetch_stock_day"

    def _fake_execute_fetch_by_name(**kwargs):
        captured.update(kwargs)
        return _dummy_result()

    monkeypatch.setattr(runtime, "resolve_fetch", lambda **_: _Resolution())
    monkeypatch.setattr(runtime, "execute_fetch_by_name", _fake_execute_fetch_by_name)

    payload = {
        "intent": {
            "asset": "stock",
            "freq": "day",
            "symbols": ["600000"],
            "start": "2024-02-01",
            "end": "2024-02-29",
        },
        "symbols": ["000001"],
        "start": "2024-01-01",
        "end": "2024-01-31",
    }
    _ = runtime.execute_fetch_by_intent(payload)

    assert captured["kwargs"]["symbols"] == ["600000"]
    assert captured["kwargs"]["start"] == "2024-02-01"
    assert captured["kwargs"]["end"] == "2024-02-29"


def test_execute_fetch_by_intent_defaults_fields_to_ohlcv(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class _Resolution:
        source = "mysql_fetch"
        public_name = "fetch_stock_day"

    def _fake_execute_fetch_by_name(**kwargs):
        captured.update(kwargs)
        return _dummy_result()

    monkeypatch.setattr(runtime, "resolve_fetch", lambda **_: _Resolution())
    monkeypatch.setattr(runtime, "execute_fetch_by_name", _fake_execute_fetch_by_name)

    _ = runtime.execute_fetch_by_intent(
        {
            "intent": {"asset": "stock", "freq": "day"},
            "symbols": ["000001"],
            "start": "2024-01-01",
            "end": "2024-01-31",
        }
    )

    assert captured["kwargs"]["fields"] == list(runtime.TECHNICAL_INDICATOR_MIN_FIELDS_OHLCV)


def test_execute_fetch_by_intent_defaults_fields_to_ohlcv_for_nested_fetch_request_wrapper(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class _Resolution:
        source = "mysql_fetch"
        public_name = "fetch_stock_day"

    def _fake_execute_fetch_by_name(**kwargs):
        captured.update(kwargs)
        return _dummy_result()

    monkeypatch.setattr(runtime, "resolve_fetch", lambda **_: _Resolution())
    monkeypatch.setattr(runtime, "execute_fetch_by_name", _fake_execute_fetch_by_name)

    _ = runtime.execute_fetch_by_intent(
        {
            "intent": {"asset": "stock", "freq": "day"},
            "kwargs": {
                "symbols": ["000001"],
                "start": "2024-01-01",
                "end": "2024-01-31",
            },
        }
    )

    assert captured["kwargs"]["fields"] == list(runtime.TECHNICAL_INDICATOR_MIN_FIELDS_OHLCV)


def test_execute_fetch_by_intent_accepts_fields_ohlcv_alias(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class _Resolution:
        source = "mysql_fetch"
        public_name = "fetch_stock_day"

    def _fake_execute_fetch_by_name(**kwargs):
        captured.update(kwargs)
        return _dummy_result()

    monkeypatch.setattr(runtime, "resolve_fetch", lambda **_: _Resolution())
    monkeypatch.setattr(runtime, "execute_fetch_by_name", _fake_execute_fetch_by_name)

    _ = runtime.execute_fetch_by_intent(
        {
            "intent": {"asset": "stock", "freq": "day"},
            "symbols": ["000001"],
            "start": "2024-01-01",
            "end": "2024-01-31",
            "fields": "OHLCV",
        }
    )

    assert captured["kwargs"]["fields"] == list(runtime.TECHNICAL_INDICATOR_MIN_FIELDS_OHLCV)


def test_execute_fetch_by_intent_normalizes_empty_symbols_to_omitted_before_provider_call(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class _Resolution:
        source = "mysql_fetch"
        public_name = "fetch_stock_day"

    def _fake_execute_fetch_by_name(**kwargs):
        captured.update(kwargs)
        return _dummy_result()

    monkeypatch.setattr(runtime, "resolve_fetch", lambda **_: _Resolution())
    monkeypatch.setattr(runtime, "execute_fetch_by_name", _fake_execute_fetch_by_name)

    _ = runtime.execute_fetch_by_intent(
        {
            "intent": {"asset": "stock", "freq": "day"},
            "symbols": [],
            "start": "2024-01-01",
            "end": "2024-01-31",
        }
    )

    assert "symbols" not in captured["kwargs"]
    assert captured["kwargs"]["fields"] == list(runtime.TECHNICAL_INDICATOR_MIN_FIELDS_OHLCV)


def test_execute_fetch_by_intent_normalizes_blank_symbol_tokens_in_intent_kwargs(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class _Resolution:
        source = "mysql_fetch"
        public_name = "fetch_stock_day"

    def _fake_execute_fetch_by_name(**kwargs):
        captured.update(kwargs)
        return _dummy_result()

    monkeypatch.setattr(runtime, "resolve_fetch", lambda **_: _Resolution())
    monkeypatch.setattr(runtime, "execute_fetch_by_name", _fake_execute_fetch_by_name)

    _ = runtime.execute_fetch_by_intent(
        {
            "intent": {
                "asset": "stock",
                "freq": "day",
                "extra_kwargs": {"symbols": ["000001", " ", "000002"]},
            },
            "start": "2024-01-01",
            "end": "2024-01-31",
        }
    )

    assert captured["kwargs"]["symbols"] == ["000001", "000002"]


def test_execute_fetch_by_intent_rejects_invalid_intent_fields_selector() -> None:
    with pytest.raises(ValueError, match=r"intent.fields must be a string or list\[str\] when provided"):
        runtime.execute_fetch_by_intent(
            {
                "intent": {"asset": "stock", "freq": "day", "fields": 1},
                "start": "2024-01-01",
                "end": "2024-01-31",
            }
        )


def test_execute_fetch_by_intent_rejects_invalid_auto_symbols_type() -> None:
    with pytest.raises(ValueError, match=r"intent.auto_symbols must be bool when provided"):
        runtime.execute_fetch_by_intent(
            {
                "intent": {"asset": "stock", "freq": "day", "auto_symbols": "true"},
                "start": "2024-01-01",
                "end": "2024-01-31",
            }
        )

    with pytest.raises(ValueError, match=r"intent.auto_symbols must be bool when provided"):
        runtime.execute_fetch_by_intent(
            runtime.FetchIntent(
                asset="stock",
                freq="day",
                start="2024-01-01",
                end="2024-01-31",
                auto_symbols=1,  # type: ignore[arg-type]
            )
        )


def test_execute_fetch_by_intent_accepts_universe_alias_in_nested_intent(monkeypatch, tmp_path) -> None:
    captured: dict[str, Any] = {}

    class _Resolution:
        source = "mysql_fetch"
        public_name = "fetch_stock_day"

    def _fake_resolve_fetch(**kwargs):
        captured["resolve_fetch"] = dict(kwargs)
        return _Resolution()

    def _fake_execute_fetch_by_name(**kwargs):
        captured["execute_fetch_by_name"] = dict(kwargs)
        return _dummy_result()

    monkeypatch.setattr(runtime, "resolve_fetch", _fake_resolve_fetch)
    monkeypatch.setattr(runtime, "execute_fetch_by_name", _fake_execute_fetch_by_name)
    monkeypatch.chdir(tmp_path)

    _ = runtime.execute_fetch_by_intent(
        {
            "intent": {"asset": "stock", "freq": "day", "universe": "cn_a"},
            "start": "2024-01-01",
            "end": "2024-01-31",
        },
        write_evidence=False,
    )

    assert captured["resolve_fetch"]["asset"] == "stock"
    assert captured["resolve_fetch"]["freq"] == "day"
    assert captured["resolve_fetch"]["venue"] == "cn_a"
    assert captured["resolve_fetch"]["adjust"] == "raw"


def test_execute_fetch_by_intent_mode_fetch_request_defaults_adjust_to_raw_when_omitted(monkeypatch, tmp_path) -> None:
    captured: dict[str, Any] = {}

    class _Resolution:
        source = "mysql_fetch"
        public_name = "fetch_stock_day"

    def _fake_resolve_fetch(**kwargs):
        captured["resolve_fetch"] = dict(kwargs)
        return _Resolution()

    monkeypatch.setattr(runtime, "resolve_fetch", _fake_resolve_fetch)
    monkeypatch.setattr(runtime, "execute_fetch_by_name", lambda **_kwargs: _dummy_result())
    monkeypatch.chdir(tmp_path)

    _ = runtime.execute_fetch_by_intent(
        {
            "mode": "demo",
            "intent": {
                "asset": "stock",
                "freq": "day",
                "universe": "cn_a",
                "start": "2024-01-01",
                "end": "2024-01-31",
            },
        },
        write_evidence=False,
    )

    assert captured["resolve_fetch"]["adjust"] == runtime.TECHNICAL_INDICATOR_DEFAULT_ADJUST


def test_execute_fetch_by_intent_normalizes_fetchintent_none_adjust_to_default_raw(monkeypatch, tmp_path) -> None:
    captured: dict[str, Any] = {}

    class _Resolution:
        source = "mysql_fetch"
        public_name = "fetch_stock_day"

    def _fake_resolve_fetch(**kwargs):
        captured["resolve_fetch"] = dict(kwargs)
        return _Resolution()

    monkeypatch.setattr(runtime, "resolve_fetch", _fake_resolve_fetch)
    monkeypatch.setattr(runtime, "execute_fetch_by_name", lambda **_kwargs: _dummy_result())
    monkeypatch.chdir(tmp_path)

    _ = runtime.execute_fetch_by_intent(
        runtime.FetchIntent(
            asset="stock",
            freq="day",
            adjust=None,  # type: ignore[arg-type]
            start="2024-01-01",
            end="2024-01-31",
        ),
        write_evidence=False,
    )

    assert captured["resolve_fetch"]["adjust"] == runtime.TECHNICAL_INDICATOR_DEFAULT_ADJUST


def test_execute_fetch_by_intent_preserves_explicit_adjust_override(monkeypatch, tmp_path) -> None:
    captured: dict[str, Any] = {}

    class _Resolution:
        source = "mysql_fetch"
        public_name = "fetch_stock_day_adv"

    def _fake_resolve_fetch(**kwargs):
        captured["resolve_fetch"] = dict(kwargs)
        return _Resolution()

    monkeypatch.setattr(runtime, "resolve_fetch", _fake_resolve_fetch)
    monkeypatch.setattr(runtime, "execute_fetch_by_name", lambda **_kwargs: _dummy_result())
    monkeypatch.chdir(tmp_path)

    _ = runtime.execute_fetch_by_intent(
        {
            "intent": {"asset": "stock", "freq": "day", "adjust": "qfq"},
            "start": "2024-01-01",
            "end": "2024-01-31",
        },
        write_evidence=False,
    )

    assert captured["resolve_fetch"]["adjust"] == "qfq"


def test_execute_fetch_by_intent_mode_fetch_request_preserves_explicit_adjust_override(monkeypatch, tmp_path) -> None:
    captured: dict[str, Any] = {}

    class _Resolution:
        source = "mysql_fetch"
        public_name = "fetch_stock_day_adv"

    def _fake_resolve_fetch(**kwargs):
        captured["resolve_fetch"] = dict(kwargs)
        return _Resolution()

    monkeypatch.setattr(runtime, "resolve_fetch", _fake_resolve_fetch)
    monkeypatch.setattr(runtime, "execute_fetch_by_name", lambda **_kwargs: _dummy_result())
    monkeypatch.chdir(tmp_path)

    _ = runtime.execute_fetch_by_intent(
        {
            "mode": "demo",
            "intent": {
                "asset": "stock",
                "freq": "day",
                "universe": "cn_a",
                "adjust": "hfq",
                "start": "2024-01-01",
                "end": "2024-01-31",
            },
        },
        write_evidence=False,
    )

    assert captured["resolve_fetch"]["adjust"] == "hfq"


def test_execute_fetch_by_intent_prefers_explicit_venue_over_universe(monkeypatch, tmp_path) -> None:
    captured: dict[str, Any] = {}

    class _Resolution:
        source = "mysql_fetch"
        public_name = "fetch_stock_day"

    def _fake_resolve_fetch(**kwargs):
        captured["resolve_fetch"] = dict(kwargs)
        return _Resolution()

    monkeypatch.setattr(runtime, "resolve_fetch", _fake_resolve_fetch)
    monkeypatch.setattr(runtime, "execute_fetch_by_name", lambda **_kwargs: _dummy_result())
    monkeypatch.chdir(tmp_path)

    _ = runtime.execute_fetch_by_intent(
        {
            "intent": {"asset": "stock", "freq": "day", "venue": "sse", "universe": "cn_a"},
            "start": "2024-01-01",
            "end": "2024-01-31",
        },
        write_evidence=False,
    )

    assert captured["resolve_fetch"]["venue"] == "sse"


def test_execute_fetch_by_intent_merges_top_level_universe_into_intent(monkeypatch, tmp_path) -> None:
    captured: dict[str, Any] = {}

    class _Resolution:
        source = "mysql_fetch"
        public_name = "fetch_stock_day"

    def _fake_resolve_fetch(**kwargs):
        captured["resolve_fetch"] = dict(kwargs)
        return _Resolution()

    monkeypatch.setattr(runtime, "resolve_fetch", _fake_resolve_fetch)
    monkeypatch.setattr(runtime, "execute_fetch_by_name", lambda **_kwargs: _dummy_result())
    monkeypatch.chdir(tmp_path)

    _ = runtime.execute_fetch_by_intent(
        {
            "intent": {"asset": "stock", "freq": "day"},
            "universe": "cn_a",
            "start": "2024-01-01",
            "end": "2024-01-31",
        },
        write_evidence=False,
    )

    assert captured["resolve_fetch"]["venue"] == "cn_a"


def test_execute_fetch_by_intent_merges_top_level_sample_into_nested_intent(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def _fake_planner_for_intent(**kwargs):
        captured["intent"] = kwargs["intent"]
        return _dummy_result(), []

    monkeypatch.setattr(runtime, "_run_auto_symbols_planner_for_intent", _fake_planner_for_intent)

    out = runtime.execute_fetch_by_intent(
        {
            "intent": {"asset": "stock", "freq": "day", "auto_symbols": True},
            "sample": {"n": 3, "method": "stable_first_n"},
            "start": "2024-01-01",
            "end": "2024-01-31",
        },
        write_evidence=False,
    )

    assert out.status == runtime.STATUS_PASS_HAS_DATA
    assert captured["intent"].sample == {"n": 3, "method": "stable_first_n"}


def test_execute_fetch_by_intent_auto_symbols_defaults_freq_day_for_technical_indicator_shape(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def _fake_planner_for_intent(**kwargs):
        captured["intent"] = kwargs["intent"]
        captured["base_kwargs"] = dict(kwargs["base_kwargs"])
        return _dummy_result(), []

    monkeypatch.setattr(runtime, "_run_auto_symbols_planner_for_intent", _fake_planner_for_intent)

    out = runtime.execute_fetch_by_intent(
        {
            "intent": {"asset": "stock", "auto_symbols": True},
            "start": "2024-01-01",
            "end": "2024-01-31",
        },
        write_evidence=False,
    )

    assert out.status == runtime.STATUS_PASS_HAS_DATA
    assert captured["intent"].freq == runtime.TECHNICAL_INDICATOR_DEFAULT_FREQ
    assert captured["intent"].adjust == runtime.TECHNICAL_INDICATOR_DEFAULT_ADJUST
    assert captured["base_kwargs"]["fields"] == list(runtime.TECHNICAL_INDICATOR_MIN_FIELDS_OHLCV)


def test_execute_fetch_by_intent_accepts_function_wrapper(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def _fake_execute_fetch_by_name(**kwargs):
        captured.update(kwargs)
        return _dummy_result()

    monkeypatch.setattr(runtime, "execute_fetch_by_name", _fake_execute_fetch_by_name)
    monkeypatch.setattr(
        runtime,
        "resolve_fetch",
        lambda **_: (_ for _ in ()).throw(AssertionError("resolve_fetch should not be called")),
    )

    payload = {
        "function": "fetch_stock_day",
        "strong_control_function": True,
        "kwargs": {"code": "000001", "start": "2024-01-01", "end": "2024-01-31"},
        "source_hint": "mongo_fetch",
        "public_function": "fetch_stock_day_public",
        "policy": {"mode": "research"},
    }
    _ = runtime.execute_fetch_by_intent(payload)

    assert captured["function"] == "fetch_stock_day"
    assert captured["kwargs"] == {
        "code": "000001",
        "start": "2024-01-01",
        "end": "2024-01-31",
        "fields": list(runtime.TECHNICAL_INDICATOR_MIN_FIELDS_OHLCV),
    }
    assert captured["source_hint"] == "mongo_fetch"
    assert captured["public_function"] == "fetch_stock_day_public"
    assert isinstance(captured["policy"], runtime.FetchExecutionPolicy)
    assert captured["policy"].mode == "research"


def test_execute_fetch_by_intent_function_wrapper_preserves_explicit_fields(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def _fake_execute_fetch_by_name(**kwargs):
        captured.update(kwargs)
        return _dummy_result()

    monkeypatch.setattr(runtime, "execute_fetch_by_name", _fake_execute_fetch_by_name)
    monkeypatch.setattr(
        runtime,
        "resolve_fetch",
        lambda **_: (_ for _ in ()).throw(AssertionError("resolve_fetch should not be called")),
    )

    payload = {
        "function": "fetch_stock_day",
        "strong_control_function": True,
        "kwargs": {"code": "000001", "start": "2024-01-01", "end": "2024-01-31", "fields": ["close"]},
        "source_hint": "mongo_fetch",
        "policy": {"mode": "research"},
    }
    _ = runtime.execute_fetch_by_intent(payload)

    assert captured["kwargs"]["fields"] == ["close"]


def test_execute_fetch_by_intent_rejects_intent_and_function_mode_together() -> None:
    with pytest.raises(ValueError, match=r"intent and function modes are mutually exclusive in v1"):
        runtime.execute_fetch_by_intent(
            {
                "intent": {"asset": "stock", "freq": "day"},
                "function": "fetch_stock_day",
                "strong_control_function": True,
                "start": "2024-01-01",
                "end": "2024-01-31",
            }
        )


def test_execute_fetch_by_intent_rejects_function_wrapper_mixed_with_intent_fields() -> None:
    with pytest.raises(
        ValueError,
        match=r"function mode is only allowed for strong-control wrappers",
    ):
        runtime.execute_fetch_by_intent(
            {
                "function": "fetch_stock_day",
                "strong_control_function": True,
                "asset": "stock",
                "kwargs": {"code": "000001", "start": "2024-01-01", "end": "2024-01-31"},
            }
        )


def test_execute_fetch_by_intent_rejects_function_wrapper_without_explicit_strong_control_flag() -> None:
    with pytest.raises(
        ValueError,
        match=r"fetch_request\.function requires explicit strong-control-function mode",
    ):
        runtime.execute_fetch_by_intent(
            {
                "function": "fetch_stock_day",
                "kwargs": {"code": "000001", "start": "2024-01-01", "end": "2024-01-31"},
            }
        )


def test_execute_fetch_by_intent_rejects_strong_control_flag_without_function() -> None:
    with pytest.raises(
        ValueError,
        match=r"strong_control_function=true requires fetch_request\.function",
    ):
        runtime.execute_fetch_by_intent(
            {
                "strong_control_function": True,
                "intent": {"asset": "stock", "freq": "day"},
                "start": "2024-01-01",
                "end": "2024-01-31",
            }
        )


def test_execute_fetch_by_intent_rejects_intent_function_override_in_intent_first_mode() -> None:
    with pytest.raises(
        ValueError,
        match=r"fetch_request.intent.function_override is not allowed in intent-first mode",
    ):
        runtime.execute_fetch_by_intent(
            {
                "intent": {
                    "asset": "stock",
                    "freq": "day",
                    "function_override": "fetch_stock_day",
                },
                "start": "2024-01-01",
                "end": "2024-01-31",
            }
        )


def test_execute_fetch_by_intent_accepts_fetch_request_mode_demo(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class _Resolution:
        source = "mysql_fetch"
        public_name = "fetch_stock_day"

    def _fake_execute_fetch_by_name(**kwargs):
        captured.update(kwargs)
        return _dummy_result()

    monkeypatch.setattr(runtime, "resolve_fetch", lambda **_: _Resolution())
    monkeypatch.setattr(runtime, "execute_fetch_by_name", _fake_execute_fetch_by_name)

    payload = {
        "intent": {"asset": "stock", "freq": "day", "universe": "cn_a", "adjust": "raw"},
        "symbols": ["000001"],
        "start": "2024-01-01",
        "end": "2024-01-31",
        "mode": "demo",
        "policy": {"on_no_data": "error"},
    }
    _ = runtime.execute_fetch_by_intent(payload)

    assert isinstance(captured["policy"], runtime.FetchExecutionPolicy)
    assert captured["policy"].mode == "demo"
    assert captured["policy"].on_no_data == "error"


def test_execute_fetch_by_intent_accepts_fetch_request_mode_backtest(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class _Resolution:
        source = "mysql_fetch"
        public_name = "fetch_stock_day"

    def _fake_execute_fetch_by_name(**kwargs):
        captured.update(kwargs)
        return _dummy_result()

    monkeypatch.setattr(runtime, "resolve_fetch", lambda **_: _Resolution())
    monkeypatch.setattr(runtime, "execute_fetch_by_name", _fake_execute_fetch_by_name)

    payload = {
        "intent": {"asset": "stock", "freq": "day", "universe": "cn_a", "adjust": "raw"},
        "symbols": ["000001"],
        "start": "2024-01-01",
        "end": "2024-01-31",
        "mode": "backtest",
        "policy": {"on_no_data": "error"},
    }
    _ = runtime.execute_fetch_by_intent(payload)

    assert isinstance(captured["policy"], runtime.FetchExecutionPolicy)
    assert captured["policy"].mode == "backtest"
    assert captured["policy"].on_no_data == "error"


def test_execute_fetch_by_intent_rejects_invalid_fetch_request_mode() -> None:
    with pytest.raises(ValueError, match=r"fetch_request.mode must be one of: demo, backtest"):
        runtime.execute_fetch_by_intent(
            {
                "intent": {"asset": "stock", "freq": "day"},
                "mode": "research",
            }
        )


def test_execute_fetch_by_intent_rejects_conflicting_fetch_request_mode_and_policy_mode() -> None:
    with pytest.raises(
        ValueError,
        match=r"fetch_request.mode conflicts with policy.mode",
    ):
        runtime.execute_fetch_by_intent(
            {
                "intent": {"asset": "stock", "freq": "day", "universe": "cn_a", "adjust": "raw"},
                "start": "2024-01-01",
                "end": "2024-01-31",
                "mode": "demo",
                "policy": {"mode": "backtest"},
            }
        )


def test_execute_fetch_by_intent_rejects_conflicting_wrapper_policy_and_entrypoint_policy() -> None:
    with pytest.raises(
        ValueError,
        match=r"fetch_request\.policy conflicts with execute_fetch_by_intent",
    ):
        runtime.execute_fetch_by_intent(
            {
                "intent": {"asset": "stock", "freq": "day"},
                "start": "2024-01-01",
                "end": "2024-01-31",
                "policy": {"mode": "demo"},
            },
            policy={"mode": "research"},
        )


def test_execute_fetch_by_intent_accepts_equivalent_wrapper_and_entrypoint_policy(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class _Resolution:
        source = "mysql_fetch"
        public_name = "fetch_stock_day"

    def _fake_execute_fetch_by_name(**kwargs):
        captured.update(kwargs)
        return _dummy_result()

    monkeypatch.setattr(runtime, "resolve_fetch", lambda **_: _Resolution())
    monkeypatch.setattr(runtime, "execute_fetch_by_name", _fake_execute_fetch_by_name)

    payload = {
        "intent": {"asset": "stock", "freq": "day"},
        "symbols": ["000001"],
        "start": "2024-01-01",
        "end": "2024-01-31",
        "policy": {"mode": "demo"},
    }
    _ = runtime.execute_fetch_by_intent(payload, policy=runtime.FetchExecutionPolicy(mode="demo"))

    assert isinstance(captured["policy"], runtime.FetchExecutionPolicy)
    assert captured["policy"].mode == "demo"


def test_execute_fetch_by_intent_rejects_unsupported_policy_mode() -> None:
    with pytest.raises(ValueError, match=r"policy.mode must be one of"):
        runtime.execute_fetch_by_intent(
            {
                "intent": {"asset": "stock", "freq": "day"},
                "policy": {"mode": "paper"},
            }
        )


def test_execute_fetch_by_name_rejects_unsupported_on_no_data_policy() -> None:
    with pytest.raises(ValueError, match=r"policy.on_no_data must be one of"):
        runtime.execute_fetch_by_name(
            function="fetch_demo",
            kwargs={},
            policy={"mode": "smoke", "on_no_data": "drop"},
        )


def test_execute_fetch_by_name_rejects_invalid_policy_max_symbols() -> None:
    with pytest.raises(ValueError, match=r"policy.max_symbols must be a positive integer when provided"):
        runtime.execute_fetch_by_name(
            function="fetch_demo",
            kwargs={},
            policy={"mode": "smoke", "max_symbols": 0},
        )


def test_execute_fetch_by_name_rejects_invalid_policy_retry_strategy() -> None:
    with pytest.raises(ValueError, match=r"policy.retry_strategy must be an object when provided"):
        runtime.execute_fetch_by_name(
            function="fetch_demo",
            kwargs={},
            policy={"mode": "smoke", "on_no_data": "retry", "retry_strategy": "single_retry"},
        )

def test_execute_fetch_by_intent_rejects_missing_required_start_end_window() -> None:
    with pytest.raises(ValueError, match=r"intent must provide non-empty start, end"):
        runtime.execute_fetch_by_intent(
            {
                "intent": {"asset": "stock", "freq": "day"},
            }
        )


def test_execute_fetch_by_intent_rejects_missing_asset_or_freq_without_function_override() -> None:
    with pytest.raises(ValueError, match=r"intent must provide asset/freq or function_override"):
        runtime.execute_fetch_by_intent(
            {
                "intent": {"asset": "stock"},
                "start": "2024-01-01",
                "end": "2024-01-31",
            }
        )

    with pytest.raises(ValueError, match=r"intent must provide asset/freq or function_override"):
        runtime.execute_fetch_by_intent(
            {
                "intent": {"freq": "day"},
                "start": "2024-01-01",
                "end": "2024-01-31",
            }
        )


def test_execute_fetch_by_intent_rejects_start_after_end_window() -> None:
    with pytest.raises(
        ValueError,
        match=r"fetch_request validation failed before orchestration: fetch_request\.intent\.start must be <= fetch_request\.intent\.end",
    ):
        runtime.execute_fetch_by_intent(
            {
                "intent": {"asset": "stock", "freq": "day"},
                "start": "2024-01-31",
                "end": "2024-01-01",
            }
        )


def test_execute_fetch_by_intent_rejects_invalid_fetch_request_kwargs() -> None:
    with pytest.raises(ValueError, match=r"fetch_request.kwargs must be an object when provided"):
        runtime.execute_fetch_by_intent(
            {
                "intent": {"asset": "stock", "freq": "day"},
                "kwargs": "bad",
            }
        )


def test_execute_fetch_by_intent_rejects_invalid_fetch_request_policy_shape() -> None:
    with pytest.raises(ValueError, match=r"fetch_request.policy must be an object when provided"):
        runtime.execute_fetch_by_intent(
            {
                "intent": {"asset": "stock", "freq": "day"},
                "policy": "mode=demo",
            }
        )


def test_execute_fetch_by_intent_rejects_invalid_fetch_request_sample_shape() -> None:
    with pytest.raises(ValueError, match=r"fetch_request.sample must be an object when provided"):
        runtime.execute_fetch_by_intent(
            {
                "intent": {"asset": "stock", "freq": "day"},
                "sample": "n=5",
            }
        )


def test_execute_fetch_by_intent_fail_fast_rejects_schema_error_before_orchestration(monkeypatch) -> None:
    monkeypatch.setattr(
        runtime,
        "resolve_fetch",
        lambda **_: (_ for _ in ()).throw(AssertionError("resolve_fetch should not be called")),
    )

    with pytest.raises(
        ValueError,
        match=r"^fetch_request validation failed before orchestration: fetch_request.intent must be an object when provided$",
    ):
        runtime.execute_fetch_by_intent({"intent": "bad"})


def test_execute_fetch_by_intent_fail_fast_rejects_logic_error_before_orchestration(monkeypatch) -> None:
    monkeypatch.setattr(
        runtime,
        "resolve_fetch",
        lambda **_: (_ for _ in ()).throw(AssertionError("resolve_fetch should not be called")),
    )

    with pytest.raises(
        ValueError,
        match=(
            r"^fetch_request validation failed before orchestration: "
            r"fetch_request.intent.start must be <= fetch_request.intent.end$"
        ),
    ):
        runtime.execute_fetch_by_intent(
            {
                "mode": "demo",
                "intent": {"asset": "stock", "freq": "day", "universe": "cn_a", "adjust": "raw"},
                "start": "2024-01-31",
                "end": "2024-01-01",
            }
        )


def test_execute_fetch_by_intent_rejects_invalid_fetch_request_intent_sample_n() -> None:
    with pytest.raises(ValueError, match=r"fetch_request.intent.sample.n must be a positive integer when provided"):
        runtime.execute_fetch_by_intent(
            {
                "intent": {"asset": "stock", "freq": "day", "sample": {"n": 0}},
            }
        )


def test_execute_fetch_by_intent_rejects_invalid_fetch_request_intent_sample_method() -> None:
    with pytest.raises(ValueError, match=r"fetch_request.intent.sample.method must be a non-empty string when provided"):
        runtime.execute_fetch_by_intent(
            {
                "intent": {"asset": "stock", "freq": "day", "sample": {"method": ""}},
            }
        )


def test_execute_fetch_by_intent_rejects_invalid_fetch_request_intent_sample_seed() -> None:
    with pytest.raises(ValueError, match=r"fetch_request.intent.sample.seed must be an integer when provided"):
        runtime.execute_fetch_by_intent(
            {
                "intent": {"asset": "stock", "freq": "day", "sample": {"method": "random", "seed": "x"}},
            }
        )


def test_execute_fetch_by_intent_rejects_unsupported_fetch_request_intent_sample_method() -> None:
    with pytest.raises(ValueError, match=r"fetch_request.intent.sample.method must be one of:"):
        runtime.execute_fetch_by_intent(
            {
                "intent": {"asset": "stock", "freq": "day", "sample": {"method": "weighted_random"}},
                "start": "2024-01-01",
                "end": "2024-01-31",
            }
        )


def test_execute_fetch_by_intent_rejects_conflicting_auto_symbols_locations() -> None:
    with pytest.raises(
        ValueError,
        match=r"fetch_request.intent.auto_symbols conflicts with fetch_request.auto_symbols",
    ):
        runtime.execute_fetch_by_intent(
            {
                "intent": {"asset": "stock", "freq": "day", "auto_symbols": False},
                "auto_symbols": True,
                "start": "2024-01-01",
                "end": "2024-01-31",
            }
        )


def test_execute_fetch_by_intent_rejects_backtest_plane_fields_in_fetch_request() -> None:
    with pytest.raises(
        ValueError,
        match=r"fetch_request contains Backtest Plane / Kernel fields.*strategy_spec",
    ):
        runtime.execute_fetch_by_intent(
            {
                "intent": {"asset": "stock", "freq": "day"},
                "strategy_spec": {"dsl_version": "signal_dsl_v1"},
            }
        )


def test_execute_fetch_by_intent_rejects_backtest_plane_fields_in_fetch_request_kwargs() -> None:
    with pytest.raises(
        ValueError,
        match=r"fetch_request.kwargs contains Backtest Plane / Kernel fields.*runspec",
    ):
        runtime.execute_fetch_by_intent(
            {
                "function": "fetch_stock_day",
                "strong_control_function": True,
                "kwargs": {
                    "code": "000001",
                    "start": "2024-01-01",
                    "end": "2024-01-31",
                    "runspec": {"adapter": {"adapter_id": "vectorbt_signal_v1"}},
                },
            }
        )


def test_execute_fetch_by_intent_rejects_backtest_plane_fields_in_fetch_request_intent_block() -> None:
    with pytest.raises(
        ValueError,
        match=r"fetch_request.intent contains Backtest Plane / Kernel fields.*signal_dsl",
    ):
        runtime.execute_fetch_by_intent(
            {
                "intent": {
                    "asset": "stock",
                    "freq": "day",
                    "signal_dsl": {"version": "signal_dsl_v1"},
                },
            }
        )


def test_execute_fetch_by_intent_rejects_backtest_plane_fields_in_intent_extra_kwargs() -> None:
    with pytest.raises(
        ValueError,
        match=r"intent.extra_kwargs contains Backtest Plane / Kernel fields.*calc_trace_plan",
    ):
        runtime.execute_fetch_by_intent(
            {
                "intent": {
                    "asset": "stock",
                    "freq": "day",
                    "start": "2024-01-01",
                    "end": "2024-01-31",
                    "extra_kwargs": {"calc_trace_plan": {"steps": []}},
                },
            }
        )


def test_execute_fetch_by_intent_rejects_gaterunner_arbitration_fields_in_fetch_request() -> None:
    with pytest.raises(
        ValueError,
        match=r"fetch_request contains GateRunner-only arbitration fields.*gate_verdict",
    ):
        runtime.execute_fetch_by_intent(
            {
                "intent": {"asset": "stock", "freq": "day"},
                "gate_verdict": "PASS",
            }
        )


def test_execute_fetch_by_intent_rejects_gaterunner_arbitration_fields_in_fetch_request_kwargs() -> None:
    with pytest.raises(
        ValueError,
        match=r"fetch_request.kwargs contains GateRunner-only arbitration fields.*strategy_verdict",
    ):
        runtime.execute_fetch_by_intent(
            {
                "function": "fetch_stock_day",
                "strong_control_function": True,
                "kwargs": {
                    "code": "000001",
                    "start": "2024-01-01",
                    "end": "2024-01-31",
                    "strategy_verdict": "FAIL",
                },
            }
        )


def test_execute_fetch_by_intent_rejects_gaterunner_arbitration_fields_in_fetch_request_intent_block() -> None:
    with pytest.raises(
        ValueError,
        match=r"fetch_request.intent contains GateRunner-only arbitration fields.*strategy_validity",
    ):
        runtime.execute_fetch_by_intent(
            {
                "intent": {
                    "asset": "stock",
                    "freq": "day",
                    "strategy_validity": "PASS",
                },
            }
        )


def test_execute_fetch_by_intent_rejects_gaterunner_arbitration_fields_in_intent_extra_kwargs() -> None:
    with pytest.raises(
        ValueError,
        match=r"intent.extra_kwargs contains GateRunner-only arbitration fields.*gate_results",
    ):
        runtime.execute_fetch_by_intent(
            {
                "intent": {
                    "asset": "stock",
                    "freq": "day",
                    "start": "2024-01-01",
                    "end": "2024-01-31",
                    "extra_kwargs": {"gate_results": {"status": "FAIL"}},
                },
            }
        )


def test_execute_ui_llm_query_executes_runtime_and_returns_result_plus_evidence_summary(tmp_path, monkeypatch) -> None:
    captured: dict[str, Any] = {}

    runtime_result = runtime.FetchExecutionResult(
        status=runtime.STATUS_PASS_HAS_DATA,
        reason="ok",
        source="fetch",
        source_internal="mongo_fetch",
        engine="mongo",
        provider_id="fetch",
        provider_internal="mongo_fetch",
        resolved_function="fetch_stock_day",
        public_function="fetch_stock_day",
        elapsed_sec=0.02,
        row_count=1,
        columns=["code", "date", "close"],
        dtypes={"code": "object", "date": "object", "close": "float64"},
        preview=[{"code": "000001", "date": "2024-01-02", "close": 10.0}],
        final_kwargs={"code": "000001"},
        mode="smoke",
        data=[{"code": "000001", "date": "2024-01-02", "close": 10.0}],
    )

    def _fake_execute_fetch_by_intent(intent_payload, **kwargs):
        captured["intent_payload"] = intent_payload
        captured.update(kwargs)
        return runtime_result

    monkeypatch.setattr(runtime, "execute_fetch_by_intent", _fake_execute_fetch_by_intent)

    out = runtime.execute_ui_llm_query(
        {
            "query_id": "q_stock_day_001",
            "fetch_request": {
                "intent": {"asset": "stock", "freq": "day"},
                "symbols": ["000001"],
                "as_of": "2024-01-02T23:59:59+08:00",
                "policy": {"mode": "smoke"},
            },
        },
        out_dir=tmp_path,
    )

    assert set(runtime.UI_REVIEWABLE_FETCH_EVIDENCE_INTERFACE_FIELDS).issubset(out)
    evidence_paths = out["fetch_evidence_paths"]
    assert set(runtime.UI_REVIEWABLE_FETCH_EVIDENCE_ARTIFACT_KEYS).issubset(evidence_paths)
    assert set(evidence_paths.keys()) >= {
        "fetch_request_path",
        "fetch_result_meta_path",
        "fetch_preview_path",
        "fetch_steps_index_path",
    }
    steps_index_path = Path(evidence_paths["fetch_steps_index_path"])
    assert steps_index_path.is_file()
    steps_index = json.loads(steps_index_path.read_text(encoding="utf-8"))
    assert steps_index["schema_version"] == "qa_fetch_steps_index_v1"
    assert isinstance(steps_index["steps"], list) and len(steps_index["steps"]) == 1
    assert steps_index["steps"][0]["result_meta_path"] == evidence_paths["fetch_result_meta_path"]

    assert captured["intent_payload"]["intent"]["asset"] == "stock"
    assert captured["intent_payload"]["symbols"] == ["000001"]
    assert out["query_id"] == "q_stock_day_001"
    assert out["query_result"]["status"] == runtime.STATUS_PASS_HAS_DATA
    assert out["query_result"]["row_count"] == 1
    assert out["query_result"]["preview"][0]["code"] == "000001"
    assert out["query_result"]["resolved_function"] == "fetch_stock_day"

    summary = out["fetch_evidence_summary"]
    assert summary["selected_function"] == "fetch_stock_day"
    assert summary["probe_status"] == runtime.STATUS_PASS_HAS_DATA
    assert summary["row_count"] == 1
    assert summary["columns"] == ["code", "date", "close"]
    assert summary["coverage"]["requested_symbols"] == ["000001"]
    assert summary["coverage"]["observed_symbols"] == ["000001"]
    assert summary["as_of"] == "2024-01-02T15:59:59Z"
    assert summary["availability_summary"]["has_as_of"] is True
    assert summary["availability_summary"]["as_of"] == "2024-01-02T15:59:59Z"
    assert summary["request_hash"] == runtime._canonical_request_hash(captured["intent_payload"])
    assert isinstance(summary["request_hash"], str) and len(summary["request_hash"]) == 64
    assert out["evidence_pointer"] == out["fetch_evidence_paths"]["fetch_result_meta_path"]
    assert out[runtime.UI_DOSSIER_FETCH_EVIDENCE_FIELD] is None

    meta_path = tmp_path / "fetch_result_meta.json"
    assert meta_path.is_file()
    persisted_meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert persisted_meta["request_hash"] == summary["request_hash"]
    assert persisted_meta["row_count"] == summary["row_count"]
    assert persisted_meta["columns"] == summary["columns"]
    assert persisted_meta["probe_status"] == summary["probe_status"]
    assert persisted_meta["as_of"] == "2024-01-02T15:59:59Z"
    assert persisted_meta["availability_summary"]["as_of"] == "2024-01-02T15:59:59Z"


def test_execute_ui_llm_query_failure_exposes_steps_index_step_meta_preview_and_error_json(tmp_path, monkeypatch) -> None:
    runtime_result = runtime.FetchExecutionResult(
        status=runtime.STATUS_ERROR_RUNTIME,
        reason="RuntimeError: upstream unavailable",
        source="fetch",
        source_internal="mongo_fetch",
        engine="mongo",
        provider_id="fetch",
        provider_internal="mongo_fetch",
        resolved_function="fetch_stock_day",
        public_function="fetch_stock_day",
        elapsed_sec=0.02,
        row_count=0,
        columns=[],
        dtypes={},
        preview=[],
        final_kwargs={"code": "000001"},
        mode="smoke",
        data=None,
    )
    monkeypatch.setattr(runtime, "execute_fetch_by_intent", lambda *_args, **_kwargs: runtime_result)

    out = runtime.execute_ui_llm_query(
        {
            "query_id": "q_stock_day_002",
            "fetch_request": {
                "intent": {"asset": "stock", "freq": "day"},
                "symbols": ["000001"],
                "policy": {"mode": "smoke"},
            },
        },
        out_dir=tmp_path,
    )

    paths = out["fetch_evidence_paths"]
    assert "fetch_steps_index_path" in paths
    assert "fetch_error_path" in paths
    assert "error_path" in paths
    assert Path(paths["fetch_error_path"]).name == runtime.FETCH_EVIDENCE_ERROR_FILENAME
    assert Path(paths["error_path"]).name == runtime.UI_FETCH_EVIDENCE_VIEWER_ERROR_FILENAME
    assert Path(paths["fetch_error_path"]).read_text(encoding="utf-8") == Path(paths["error_path"]).read_text(encoding="utf-8")

    steps_index = json.loads(Path(paths["fetch_steps_index_path"]).read_text(encoding="utf-8"))
    step = steps_index["steps"][0]
    assert set(runtime.UI_FETCH_EVIDENCE_VIEWER_STEP_META_PREVIEW_FIELDS).issubset(step)
    assert step["result_meta_path"] == paths["fetch_result_meta_path"]
    assert step["preview_path"] == paths["fetch_preview_path"]

    viewer = out["fetch_evidence_viewer"]
    assert viewer["schema_version"] == runtime.UI_FETCH_EVIDENCE_VIEWER_STATE_SCHEMA_VERSION
    assert viewer["steps_index_path"] == paths["fetch_steps_index_path"]
    assert viewer["step_meta_preview_rule"] == runtime.UI_FETCH_EVIDENCE_VIEWER_STEP_META_PREVIEW_RULE
    assert viewer["steps_count"] == 1
    assert viewer["steps"][0]["result_meta_path"] == paths["fetch_result_meta_path"]
    assert viewer["steps"][0]["preview_path"] == paths["fetch_preview_path"]
    assert viewer["fetch_error_path"] == paths["fetch_error_path"]
    assert viewer["error_path"] == paths["error_path"]


def test_build_fetch_evidence_viewer_state_rejects_step_missing_meta_preview_fields(tmp_path) -> None:
    steps_index_path = tmp_path / runtime.FETCH_EVIDENCE_STEPS_INDEX_FILENAME
    steps_index_path.write_text(
        json.dumps(
            {
                "schema_version": runtime.FETCH_EVIDENCE_STEPS_INDEX_SCHEMA_VERSION,
                "generated_at": "2026-02-16T00:00:00Z",
                "trace_id": "trace-demo",
                "steps": [
                    {
                        "step_index": 1,
                        "result_meta_path": (tmp_path / runtime.FETCH_EVIDENCE_RESULT_META_FILENAME).as_posix(),
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"missing required meta/preview fields"):
        runtime.build_fetch_evidence_viewer_state(
            fetch_evidence_paths={
                "fetch_steps_index_path": steps_index_path.as_posix(),
            }
        )


def test_build_fetch_evidence_viewer_state_multistep_exposes_step_meta_preview_for_each_step(tmp_path) -> None:
    list_result = _dummy_result()
    list_result.resolved_function = "fetch_stock_list"
    list_result.public_function = "fetch_stock_list"
    sample_result = _dummy_result()
    sample_result.resolved_function = "planner_sample_symbols"
    sample_result.public_function = "planner_sample_symbols"
    sample_result.source_internal = "planner"
    sample_result.provider_internal = "planner"
    sample_result.engine = None
    day_result = _dummy_result()
    day_result.resolved_function = "fetch_stock_day"
    day_result.public_function = "fetch_stock_day"

    paths = runtime.write_fetch_evidence(
        request_payload={"intent": {"asset": "stock", "freq": "day", "auto_symbols": True}},
        result=day_result,
        out_dir=tmp_path,
        step_records=[
            {
                "step_index": 1,
                "step_kind": "list",
                "request_payload": {"function": "fetch_stock_list", "kwargs": {}},
                "result": list_result,
            },
            {
                "step_index": 2,
                "step_kind": "sample",
                "request_payload": {"planner_step": "sample", "sample": {"n": 1, "method": "stable_first_n"}},
                "result": sample_result,
            },
            {
                "step_index": 3,
                "step_kind": "day",
                "request_payload": {"intent": {"asset": "stock", "freq": "day", "symbols": ["000001"]}},
                "result": day_result,
            },
        ],
    )

    viewer = runtime.build_fetch_evidence_viewer_state(fetch_evidence_paths=paths)

    assert viewer["steps_count"] == 3
    for step_index, step in enumerate(viewer["steps"], start=1):
        assert step["step_index"] == step_index
        assert set(runtime.UI_FETCH_EVIDENCE_VIEWER_STEP_META_PREVIEW_FIELDS).issubset(step)
        assert Path(step["result_meta_path"]).is_file()
        assert Path(step["preview_path"]).is_file()
        meta_doc = json.loads(Path(step["result_meta_path"]).read_text(encoding="utf-8"))
        assert isinstance(meta_doc, dict)
        preview_lines = Path(step["preview_path"]).read_text(encoding="utf-8").splitlines()
        assert preview_lines


def test_execute_ui_llm_query_emits_fetch_evidence_viewer_review_rollback_integration(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(runtime, "execute_fetch_by_intent", lambda *_args, **_kwargs: _dummy_result())

    out = runtime.execute_ui_llm_query(
        {
            "query_id": "q_stock_day_003",
            "fetch_request": {
                "intent": {"asset": "stock", "freq": "day"},
                "symbols": ["000001"],
                "policy": {"mode": "smoke"},
            },
        },
        out_dir=tmp_path,
    )

    viewer = out["fetch_evidence_viewer"]
    checkpoint = out["fetch_review_checkpoint"]
    rollback_entrypoint = checkpoint["rollback_entrypoint"]
    review_integration = viewer["review_integration"]

    assert viewer["schema_version"] == runtime.UI_FETCH_EVIDENCE_VIEWER_STATE_SCHEMA_VERSION
    assert viewer["steps_index_filename"] == runtime.UI_FETCH_EVIDENCE_VIEWER_STEPS_INDEX_FILENAME
    assert viewer["steps_index_path"] == out["fetch_evidence_paths"]["fetch_steps_index_path"]
    assert viewer["step_meta_preview_rule"] == runtime.UI_FETCH_EVIDENCE_VIEWER_STEP_META_PREVIEW_RULE
    assert viewer["steps_count"] == 1
    assert viewer["steps"][0]["result_meta_path"] == out["fetch_evidence_paths"]["fetch_result_meta_path"]
    assert viewer["steps"][0]["preview_path"] == out["fetch_evidence_paths"]["fetch_preview_path"]
    assert viewer["fetch_error_path"] is None
    assert viewer["error_path"] is None

    assert review_integration["rule"] == runtime.UI_FETCH_EVIDENCE_VIEWER_REVIEW_ROLLBACK_RULE
    assert review_integration["review_status"] == checkpoint["review_status"]
    assert review_integration["active_attempt_index"] == checkpoint["active_attempt_index"]
    assert review_integration["latest_attempt_index"] == checkpoint["latest_attempt_index"]
    assert review_integration["action"] == rollback_entrypoint["action"]
    assert review_integration["transition"] == rollback_entrypoint["transition"]
    assert review_integration["target_scope_options"] == rollback_entrypoint["target_scope_options"]
    assert review_integration["target_attempt_index_options"] == rollback_entrypoint["target_attempt_index_options"]


def test_execute_ui_llm_query_dossier_payload_exposes_multistep_timeline_with_explicit_step_indexes(tmp_path, monkeypatch) -> None:
    list_result = _dummy_result()
    list_result.resolved_function = "fetch_stock_list"
    list_result.public_function = "fetch_stock_list"
    sample_result = _dummy_result()
    sample_result.resolved_function = "planner_sample_symbols"
    sample_result.public_function = "planner_sample_symbols"
    sample_result.source_internal = "planner"
    sample_result.provider_internal = "planner"
    sample_result.engine = None
    day_result = _dummy_result()
    day_result.resolved_function = "fetch_stock_day"
    day_result.public_function = "fetch_stock_day"

    monkeypatch.setattr(runtime, "execute_fetch_by_intent", lambda *_args, **_kwargs: day_result)
    monkeypatch.setattr(
        runtime,
        "enforce_fetch_evidence_snapshot_manifest_gate",
        lambda **_kwargs: {"gate_pass": True},
    )
    monkeypatch.chdir(tmp_path)

    out = runtime.execute_ui_llm_query(
        {
            "query_id": "q_stock_day_multi_timeline",
            "run_id": "run_ui_fetch_multi_timeline",
            "fetch_request": {
                "intent": {"asset": "stock", "freq": "day"},
                "symbols": ["000001"],
                "policy": {"mode": "smoke"},
            },
        },
        out_dir=tmp_path / "artifacts" / "jobs" / "job_001" / "outputs" / "fetch",
        step_records=[
            {
                "step_index": 3,
                "step_kind": "day",
                "request_payload": {"intent": {"asset": "stock", "freq": "day", "symbols": ["000001"]}},
                "result": day_result,
            },
            {
                "step_index": 1,
                "step_kind": "list",
                "request_payload": {"function": "fetch_stock_list", "kwargs": {}},
                "result": list_result,
            },
            {
                "step_index": 2,
                "step_kind": "sample",
                "request_payload": {"planner_step": "sample", "sample": {"n": 1, "method": "stable_first_n"}},
                "result": sample_result,
            },
        ],
    )

    dossier_payload = out[runtime.UI_DOSSIER_FETCH_EVIDENCE_FIELD]
    assert dossier_payload is not None
    attempts_timeline = dossier_payload[runtime.UI_DOSSIER_FETCH_EVIDENCE_ATTEMPTS_FIELD]
    steps_timeline = dossier_payload[runtime.UI_DOSSIER_FETCH_EVIDENCE_STEPS_FIELD]
    retry_rollback_map = dossier_payload[runtime.UI_DOSSIER_FETCH_EVIDENCE_RETRY_ROLLBACK_FIELD]

    assert len(attempts_timeline) == 1
    assert attempts_timeline[0]["attempt_index"] == 1
    assert attempts_timeline[0]["is_active"] is True
    assert len(steps_timeline) == 3
    assert [row["step_index"] for row in steps_timeline] == [1, 2, 3]
    assert [row["step_kind"] for row in steps_timeline] == ["list", "sample", "day"]
    assert all(row["attempt_index"] == 1 for row in steps_timeline)
    assert all(Path(row["result_meta_path"]).is_file() for row in steps_timeline)
    assert all(Path(row["preview_path"]).is_file() for row in steps_timeline)
    assert retry_rollback_map["rule"] == runtime.UI_FETCH_EVIDENCE_VIEWER_REVIEW_ROLLBACK_RULE


def test_execute_ui_llm_query_enforces_public_source_fetch_semantics(tmp_path, monkeypatch) -> None:
    runtime_result = _dummy_result()
    runtime_result.source = "mysql_fetch"
    runtime_result.source_internal = "mysql_fetch"
    runtime_result.engine = "mysql"
    runtime_result.resolved_function = "fetch_stock_day"
    runtime_result.public_function = "fetch_stock_day"
    runtime_result.columns = ["code", "date", "close"]
    runtime_result.dtypes = {"code": "object", "date": "object", "close": "float64"}
    runtime_result.preview = [{"code": "000001", "date": "2024-01-02", "close": 10.0}]
    runtime_result.final_kwargs = {"code": "000001"}
    runtime_result.data = [{"code": "000001", "date": "2024-01-02", "close": 10.0}]

    monkeypatch.setattr(runtime, "execute_fetch_by_intent", lambda *_args, **_kwargs: runtime_result)

    out = runtime.execute_ui_llm_query(
        {
            "fetch_request": {
                "intent": {"asset": "stock", "freq": "day"},
                "symbols": ["000001"],
            }
        },
        out_dir=tmp_path,
    )

    assert out["query_result"]["source"] == "fetch"
    assert out["fetch_evidence_summary"]["source"] == "fetch"

    persisted_meta = json.loads((tmp_path / "fetch_result_meta.json").read_text(encoding="utf-8"))
    assert persisted_meta["source"] == "fetch"


def test_execute_ui_llm_query_accepts_direct_fetch_payload(tmp_path, monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def _fake_execute_fetch_by_intent(intent_payload, **kwargs):
        captured["intent_payload"] = intent_payload
        captured.update(kwargs)
        return _dummy_result()

    monkeypatch.setattr(runtime, "execute_fetch_by_intent", _fake_execute_fetch_by_intent)
    monkeypatch.chdir(tmp_path)

    out = runtime.execute_ui_llm_query(
        {
            "function": "fetch_stock_day",
            "strong_control_function": True,
            "kwargs": {"code": "000001", "start": "2024-01-01", "end": "2024-01-31"},
            "policy": {"mode": "research"},
        }
    )

    assert captured["intent_payload"]["function"] == "fetch_stock_day"
    assert captured["intent_payload"]["kwargs"]["code"] == "000001"
    assert out["query_result"]["resolved_function"] == "fetch_demo"
    assert out["fetch_evidence_summary"]["selected_function"] == "fetch_demo"
    assert set(out["fetch_evidence_paths"].keys()) >= {
        "fetch_request_path",
        "fetch_result_meta_path",
        "fetch_preview_path",
        "fetch_steps_index_path",
    }
    assert out["evidence_pointer"] == out["fetch_evidence_paths"]["fetch_result_meta_path"]
    meta_path = Path(out["fetch_evidence_paths"]["fetch_result_meta_path"])
    steps_index_path = Path(out["fetch_evidence_paths"]["fetch_steps_index_path"])
    assert meta_path.is_file()
    assert steps_index_path.is_file()
    assert out["fetch_evidence_paths"]["fetch_result_meta_path"].startswith(
        "artifacts/qa_fetch/ui_llm_query_evidence/"
    )


def test_execute_ui_llm_query_run_id_defaults_to_dossier_fetch_paths(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(runtime, "execute_fetch_by_intent", lambda *_args, **_kwargs: _dummy_result())
    monkeypatch.chdir(tmp_path)
    snapshot_manifest_path = tmp_path / "data_lake" / "snapshot_run_ui_fetch_001" / "manifest.json"
    snapshot_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_manifest_path.write_text('{"schema_version":"data_snapshot_manifest_v1"}\n', encoding="utf-8")

    out = runtime.execute_ui_llm_query(
        {
            "run_id": "run_ui_fetch_001",
            "fetch_request": {
                "intent": {"asset": "stock", "freq": "day"},
                "symbols": ["000001"],
                "start": "2024-01-01",
                "end": "2024-01-31",
                "policy": {
                    "mode": "smoke",
                    "snapshot_manifest_path": snapshot_manifest_path.as_posix(),
                },
            },
        }
    )

    dossier_fetch_prefix = "artifacts/dossiers/run_ui_fetch_001/fetch/"
    paths = out["fetch_evidence_paths"]
    assert paths["fetch_request_path"].startswith(dossier_fetch_prefix)
    assert paths["fetch_result_meta_path"].startswith(dossier_fetch_prefix)
    assert paths["fetch_preview_path"].startswith(dossier_fetch_prefix)
    assert paths["fetch_steps_index_path"].startswith(dossier_fetch_prefix)
    assert out["evidence_pointer"] == paths["fetch_result_meta_path"]
    assert Path(paths["fetch_request_path"]).is_file()
    assert Path(paths["fetch_result_meta_path"]).is_file()
    assert Path(paths["fetch_preview_path"]).is_file()
    assert Path(paths["fetch_steps_index_path"]).is_file()
    dossier_payload = out[runtime.UI_DOSSIER_FETCH_EVIDENCE_FIELD]
    assert dossier_payload["run_id"] == "run_ui_fetch_001"
    assert dossier_payload["read_mode"] == runtime.UI_DOSSIER_FETCH_EVIDENCE_READ_MODE
    assert dossier_payload["fetch_root_path"] == "artifacts/dossiers/run_ui_fetch_001/fetch"
    assert dossier_payload["required_paths"] == {
        key: paths[key] for key in runtime.UI_DOSSIER_FETCH_EVIDENCE_REQUIRED_PATH_KEYS
    }
    assert dossier_payload["evidence_pointer"] == out["evidence_pointer"]
    assert runtime.UI_DOSSIER_FETCH_EVIDENCE_ATTEMPTS_FIELD in dossier_payload
    assert runtime.UI_DOSSIER_FETCH_EVIDENCE_STEPS_FIELD in dossier_payload
    assert runtime.UI_DOSSIER_FETCH_EVIDENCE_RETRY_ROLLBACK_FIELD in dossier_payload
    assert dossier_payload[runtime.UI_DOSSIER_FETCH_EVIDENCE_ATTEMPTS_FIELD][0]["attempt_index"] == 1
    assert dossier_payload[runtime.UI_DOSSIER_FETCH_EVIDENCE_ATTEMPTS_FIELD][0]["result_meta_path"].endswith(
        "/attempt_000001/fetch_result_meta.json"
    )
    assert Path(dossier_payload[runtime.UI_DOSSIER_FETCH_EVIDENCE_ATTEMPTS_FIELD][0]["result_meta_path"]).is_file()
    assert len(dossier_payload[runtime.UI_DOSSIER_FETCH_EVIDENCE_STEPS_FIELD]) == 1
    assert dossier_payload[runtime.UI_DOSSIER_FETCH_EVIDENCE_STEPS_FIELD][0]["attempt_index"] == 1
    assert dossier_payload[runtime.UI_DOSSIER_FETCH_EVIDENCE_STEPS_FIELD][0]["step_index"] == 1
    assert dossier_payload[runtime.UI_DOSSIER_FETCH_EVIDENCE_RETRY_ROLLBACK_FIELD]["latest_attempt_index"] == 1
    assert dossier_payload[runtime.UI_DOSSIER_FETCH_EVIDENCE_RETRY_ROLLBACK_FIELD]["active_attempt_index"] == 1


def test_execute_ui_llm_query_run_id_prefers_dossier_fetch_paths_over_explicit_out_dir(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(runtime, "execute_fetch_by_intent", lambda *_args, **_kwargs: _dummy_result())
    monkeypatch.chdir(tmp_path)
    snapshot_manifest_path = tmp_path / "data_lake" / "snapshot_run_ui_fetch_002" / "manifest.json"
    snapshot_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_manifest_path.write_text('{"schema_version":"data_snapshot_manifest_v1"}\n', encoding="utf-8")

    out = runtime.execute_ui_llm_query(
        {
            "run_id": "run_ui_fetch_002",
            "fetch_request": {
                "intent": {"asset": "stock", "freq": "day"},
                "symbols": ["000001"],
                "start": "2024-01-01",
                "end": "2024-01-31",
                "policy": {
                    "mode": "smoke",
                    "snapshot_manifest_path": snapshot_manifest_path.as_posix(),
                },
            },
        },
        out_dir=tmp_path / "artifacts" / "jobs" / "job_001" / "outputs" / "fetch",
    )

    dossier_fetch_prefix = "artifacts/dossiers/run_ui_fetch_002/fetch/"
    paths = out["fetch_evidence_paths"]
    assert paths["fetch_request_path"].startswith(dossier_fetch_prefix)
    assert paths["fetch_result_meta_path"].startswith(dossier_fetch_prefix)
    assert paths["fetch_preview_path"].startswith(dossier_fetch_prefix)
    assert paths["fetch_steps_index_path"].startswith(dossier_fetch_prefix)
    assert not (tmp_path / "artifacts" / "jobs" / "job_001" / "outputs" / "fetch").exists()
    dossier_payload = out[runtime.UI_DOSSIER_FETCH_EVIDENCE_FIELD]
    assert dossier_payload["run_id"] == "run_ui_fetch_002"
    assert dossier_payload["one_hop_rule"] == runtime.FETCH_EVIDENCE_DOSSIER_ONE_HOP_RULE
    assert dossier_payload["required_paths"] == {
        key: paths[key] for key in runtime.UI_DOSSIER_FETCH_EVIDENCE_REQUIRED_PATH_KEYS
    }
    assert dossier_payload["evidence_pointer"] == out["evidence_pointer"]
    assert runtime.UI_DOSSIER_FETCH_EVIDENCE_ATTEMPTS_FIELD in dossier_payload
    assert runtime.UI_DOSSIER_FETCH_EVIDENCE_STEPS_FIELD in dossier_payload
    assert runtime.UI_DOSSIER_FETCH_EVIDENCE_RETRY_ROLLBACK_FIELD in dossier_payload
    assert dossier_payload[runtime.UI_DOSSIER_FETCH_EVIDENCE_ATTEMPTS_FIELD][0]["attempt_index"] == 1
    assert dossier_payload[runtime.UI_DOSSIER_FETCH_EVIDENCE_ATTEMPTS_FIELD][0]["is_active"] is True
    assert len(dossier_payload[runtime.UI_DOSSIER_FETCH_EVIDENCE_STEPS_FIELD]) == 1


def test_execute_ui_llm_query_rejects_invalid_query_envelope() -> None:
    with pytest.raises(ValueError, match=r"query_envelope must be an object"):
        runtime.execute_ui_llm_query("bad")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match=r"query_envelope.fetch_request must be an object when provided"):
        runtime.execute_ui_llm_query({"fetch_request": "bad"})

    with pytest.raises(ValueError, match=r"must include fetch_request or fetch intent/function fields"):
        runtime.execute_ui_llm_query({"query_id": "q_only"})


def test_validate_fetch_request_v1_allows_omitted_adjust_and_still_requires_venue_or_universe_when_mode_is_provided() -> None:
    out = runtime.validate_fetch_request_v1(
        {
            "mode": "demo",
            "intent": {
                "asset": "stock",
                "freq": "day",
                "venue": "cn_a",
                "start": "2024-01-01",
                "end": "2024-01-31",
            },
        }
    )

    assert out["intent"].get("adjust") is None

    with pytest.raises(
        ValueError,
        match=r"fetch_request.intent must include one of: venue, universe",
    ):
        runtime.validate_fetch_request_v1(
            {
                "mode": "demo",
                "intent": {
                    "asset": "stock",
                    "freq": "day",
                    "adjust": "raw",
                    "start": "2024-01-01",
                    "end": "2024-01-31",
                },
            }
        )


def test_validate_fetch_request_v1_rejects_unsupported_intent_core_selectors() -> None:
    with pytest.raises(ValueError, match=r"fetch_request.intent.asset must be one of:"):
        runtime.validate_fetch_request_v1(
            {
                "mode": "demo",
                "intent": {
                    "asset": "crypto",
                    "freq": "day",
                    "venue": "cn_a",
                    "adjust": "raw",
                },
            }
        )

    with pytest.raises(ValueError, match=r"fetch_request.intent.adjust must be one of:"):
        runtime.validate_fetch_request_v1(
            {
                "mode": "demo",
                "intent": {
                    "asset": "stock",
                    "freq": "day",
                    "venue": "cn_a",
                    "adjust": "bad_adjust",
                },
            }
        )


def test_validate_fetch_request_v1_accepts_optional_empty_symbols_and_fields_omission() -> None:
    out = runtime.validate_fetch_request_v1(
        {
            "mode": "demo",
            "intent": {
                "asset": "stock",
                "freq": "day",
                "universe": "cn_a",
                "adjust": "raw",
                "symbols": [],
                "start": "2024-01-01",
                "end": "2024-01-31",
            },
        }
    )

    assert out["intent"]["symbols"] == []


def test_execute_ui_llm_query_rejects_invalid_fetch_request_v1_sample_shape() -> None:
    with pytest.raises(ValueError, match=r"fetch_request.sample must be an object when provided"):
        runtime.execute_ui_llm_query(
            {
                "fetch_request": {
                    "intent": {"asset": "stock", "freq": "day"},
                    "sample": "n=3",
                }
            }
        )


def test_execute_ui_llm_query_rejects_conflicting_fetch_request_and_entrypoint_policy() -> None:
    with pytest.raises(
        ValueError,
        match=r"fetch_request\.policy conflicts with execute_fetch_by_intent",
    ):
        runtime.execute_ui_llm_query(
            {
                "query_id": "q_policy_conflict",
                "fetch_request": {
                    "intent": {"asset": "stock", "freq": "day"},
                    "start": "2024-01-01",
                    "end": "2024-01-31",
                    "policy": {"mode": "demo"},
                },
            },
            policy={"mode": "research"},
        )


def test_execute_ui_llm_query_rejects_missing_ui_reviewable_evidence_artifact_paths(monkeypatch) -> None:
    monkeypatch.setattr(runtime, "execute_fetch_by_intent", lambda *_args, **_kwargs: _dummy_result())
    monkeypatch.setattr(
        runtime,
        "write_fetch_evidence",
        lambda **_kwargs: {
            "fetch_request_path": "artifacts/qa_fetch/ui_llm_query_evidence/q1/fetch_request.json",
            "fetch_result_meta_path": "artifacts/qa_fetch/ui_llm_query_evidence/q1/fetch_result_meta.json",
            "fetch_preview_path": "artifacts/qa_fetch/ui_llm_query_evidence/q1/fetch_preview.csv",
        },
    )

    with pytest.raises(
        ValueError,
        match=r"ui-reviewable fetch evidence artifact paths missing required keys: fetch_steps_index_path",
    ):
        runtime.execute_ui_llm_query(
            {
                "query_id": "q_stock_day_001",
                "fetch_request": {
                    "intent": {"asset": "stock", "freq": "day"},
                    "symbols": ["000001"],
                    "policy": {"mode": "smoke"},
                },
            }
        )


def test_execute_ui_llm_query_rejects_failure_paths_missing_ui_error_json_exposure(monkeypatch) -> None:
    monkeypatch.setattr(runtime, "execute_fetch_by_intent", lambda *_args, **_kwargs: _dummy_result())
    monkeypatch.setattr(
        runtime,
        "write_fetch_evidence",
        lambda **_kwargs: {
            "fetch_request_path": "artifacts/qa_fetch/ui_llm_query_evidence/q1/fetch_request.json",
            "fetch_result_meta_path": "artifacts/qa_fetch/ui_llm_query_evidence/q1/fetch_result_meta.json",
            "fetch_preview_path": "artifacts/qa_fetch/ui_llm_query_evidence/q1/fetch_preview.csv",
            "fetch_steps_index_path": "artifacts/qa_fetch/ui_llm_query_evidence/q1/fetch_steps_index.json",
            "fetch_error_path": "artifacts/qa_fetch/ui_llm_query_evidence/q1/fetch_error.json",
        },
    )

    with pytest.raises(
        ValueError,
        match=r"ui-reviewable fetch evidence artifact paths missing required keys: error_path",
    ):
        runtime.execute_ui_llm_query(
            {
                "query_id": "q_stock_day_001",
                "fetch_request": {
                    "intent": {"asset": "stock", "freq": "day"},
                    "symbols": ["000001"],
                    "policy": {"mode": "smoke"},
                },
            }
        )


def test_execute_ui_llm_query_rejects_failure_paths_missing_fetch_error_json_exposure(monkeypatch) -> None:
    monkeypatch.setattr(runtime, "execute_fetch_by_intent", lambda *_args, **_kwargs: _dummy_result())
    monkeypatch.setattr(
        runtime,
        "write_fetch_evidence",
        lambda **_kwargs: {
            "fetch_request_path": "artifacts/qa_fetch/ui_llm_query_evidence/q1/fetch_request.json",
            "fetch_result_meta_path": "artifacts/qa_fetch/ui_llm_query_evidence/q1/fetch_result_meta.json",
            "fetch_preview_path": "artifacts/qa_fetch/ui_llm_query_evidence/q1/fetch_preview.csv",
            "fetch_steps_index_path": "artifacts/qa_fetch/ui_llm_query_evidence/q1/fetch_steps_index.json",
            "error_path": "artifacts/qa_fetch/ui_llm_query_evidence/q1/error.json",
        },
    )

    with pytest.raises(
        ValueError,
        match=r"ui-reviewable fetch evidence artifact paths missing required keys: fetch_error_path",
    ):
        runtime.execute_ui_llm_query(
            {
                "query_id": "q_stock_day_001",
                "fetch_request": {
                    "intent": {"asset": "stock", "freq": "day"},
                    "symbols": ["000001"],
                    "policy": {"mode": "smoke"},
                },
            }
        )


def test_execute_ui_llm_query_rejects_non_dossier_evidence_paths_when_run_id_present(monkeypatch) -> None:
    monkeypatch.setattr(runtime, "execute_fetch_by_intent", lambda *_args, **_kwargs: _dummy_result())
    monkeypatch.setattr(
        runtime,
        "enforce_fetch_evidence_snapshot_manifest_gate",
        lambda **_kwargs: {"gate_pass": True},
    )
    monkeypatch.setattr(
        runtime,
        "write_fetch_evidence",
        lambda **_kwargs: {
            "fetch_request_path": "artifacts/qa_fetch/ui_llm_query_evidence/q1/fetch_request.json",
            "fetch_result_meta_path": "artifacts/qa_fetch/ui_llm_query_evidence/q1/fetch_result_meta.json",
            "fetch_preview_path": "artifacts/qa_fetch/ui_llm_query_evidence/q1/fetch_preview.csv",
            "fetch_steps_index_path": "artifacts/qa_fetch/ui_llm_query_evidence/q1/fetch_steps_index.json",
        },
    )

    with pytest.raises(
        ValueError,
        match=r"dossier fetch evidence path must stay under dossier fetch root",
    ):
        runtime.execute_ui_llm_query(
            {
                "run_id": "run_ui_fetch_003",
                "fetch_request": {
                    "intent": {"asset": "stock", "freq": "day"},
                    "symbols": ["000001"],
                    "start": "2024-01-01",
                    "end": "2024-01-31",
                },
            }
        )


def test_write_fetch_evidence_success_bundle_emits_qf_058_qf_059_qf_060_artifacts(tmp_path) -> None:
    result = runtime.FetchExecutionResult(
        status=runtime.STATUS_PASS_HAS_DATA,
        reason="ok",
        source="fetch",
        source_internal="mysql_fetch",
        engine="mysql",
        provider_id="fetch",
        provider_internal="mysql_fetch",
        resolved_function="fetch_stock_day",
        public_function="fetch_stock_day",
        elapsed_sec=0.01,
        row_count=2,
        columns=["code", "close"],
        dtypes={"code": "object", "close": "float64"},
        preview=[{"code": "000001", "date": "2024-01-02", "close": 10.0}],
        final_kwargs={"code": "000001"},
        mode="smoke",
        data=[
            {"code": "000001", "date": "2024-01-02", "close": 10.0},
            {"code": "000001", "date": "2024-01-03", "close": 10.5},
        ],
    )

    request_payload = {"intent": {"asset": "stock", "freq": "day"}}
    paths = runtime.write_fetch_evidence(
        request_payload=request_payload,
        result=result,
        out_dir=tmp_path,
    )
    assert Path(paths["fetch_request_path"]).name == runtime.FETCH_EVIDENCE_REQUEST_FILENAME
    assert Path(paths["fetch_request_path"]).is_file()
    assert Path(paths["fetch_result_meta_path"]).name == runtime.FETCH_EVIDENCE_RESULT_META_FILENAME
    assert Path(paths["fetch_result_meta_path"]).is_file()
    assert Path(paths["fetch_preview_path"]).name == runtime.FETCH_EVIDENCE_PREVIEW_FILENAME
    assert Path(paths["fetch_preview_path"]).is_file()
    preview_lines = Path(paths["fetch_preview_path"]).read_text(encoding="utf-8").splitlines()
    assert preview_lines and preview_lines[0].split(",") == ["code", "date", "close"]
    assert all("\t" not in line for line in preview_lines)
    assert "fetch_error_path" not in paths
    assert not (tmp_path / runtime.FETCH_EVIDENCE_ERROR_FILENAME).exists()
    assert "fetch_steps_index_path" in paths
    idx = json.loads((tmp_path / runtime.FETCH_EVIDENCE_STEPS_INDEX_FILENAME).read_text(encoding="utf-8"))
    assert idx["schema_version"] == "qa_fetch_steps_index_v1"
    assert isinstance(idx.get("steps"), list) and len(idx["steps"]) == 1
    step = idx["steps"][0]
    assert step["step_index"] == 1
    assert step["step_kind"] == "single_fetch"
    assert step["status"] == runtime.STATUS_PASS_HAS_DATA
    assert step["request_path"] == paths["fetch_request_path"]
    assert step["result_meta_path"] == paths["fetch_result_meta_path"]
    assert step["preview_path"] == paths["fetch_preview_path"]
    assert "error_path" not in step
    meta = json.loads((tmp_path / "fetch_result_meta.json").read_text(encoding="utf-8"))
    required_meta_fields = {
        "selected_function",
        "engine",
        "row_count",
        "col_count",
        "min_ts",
        "max_ts",
        "request_hash",
        "coverage",
        "warnings",
    }
    assert required_meta_fields.issubset(meta.keys())
    assert meta["selected_function"] == "fetch_stock_day"
    assert meta["engine"] in runtime.FETCH_RESULT_META_ENGINE_OPTIONS
    assert meta["row_count"] == 2
    assert meta["col_count"] == 3
    assert meta["probe_status"] == runtime.STATUS_PASS_HAS_DATA
    assert meta["request_hash"] == runtime._canonical_request_hash(request_payload)
    assert isinstance(meta["request_hash"], str) and len(meta["request_hash"]) == 64
    assert meta["warnings"] == []
    assert meta["min_ts"] == "2024-01-02"
    assert meta["max_ts"] == "2024-01-02"
    assert meta["coverage"]["requested_symbol_count"] == 0
    assert meta["coverage"]["observed_symbol_count"] == 1
    assert meta["coverage"]["observed_symbols"] == ["000001"]
    assert meta["coverage"]["missing_symbol_count"] == 0
    assert meta["coverage"]["missing_symbols"] == []
    assert meta["coverage"]["symbol_coverage_scope"] == runtime.FETCH_RESULT_META_COVERAGE_SYMBOL_SCOPE
    assert (
        meta["coverage"]["reporting_granularity"]
        == runtime.FETCH_RESULT_META_COVERAGE_REPORTING_GRANULARITY
    )
    assert (
        meta["coverage"]["symbol_missing_rate_formula"]
        == runtime.FETCH_RESULT_META_COVERAGE_MISSING_RATE_FORMULA
    )
    assert meta["coverage"]["symbol_missing_rate_denominator"] == 0
    assert meta["coverage"]["symbol_missing_rate_numerator"] == 0
    assert meta["coverage"]["symbol_coverage_rate"] == 1.0
    assert meta["coverage"]["symbol_missing_rate"] == 0.0
    assert meta["coverage"]["symbol_missing_ratio"] == 0.0
    sanity = meta["sanity_checks"]
    assert sanity["timestamp_field"] == "date"
    assert sanity["timestamp_order_rule"] == runtime.SANITY_TIMESTAMP_ORDER_RULE
    assert sanity["timestamp_duplicate_policy"] == runtime.SANITY_TIMESTAMP_DUPLICATE_POLICY
    assert sanity["timestamp_monotonic_non_decreasing"] is True
    assert sanity["timestamp_duplicate_count"] == 0
    assert sanity["timestamp_rule_satisfied"] is True
    assert sanity["missing_ratio_by_column"]["code"] == 0.0
    assert sanity["missing_ratio_by_column"]["close"] == 0.0
    assert sanity["preview_row_count"] == 1
    gate = meta["gate_input_summary"]
    assert gate["no_lookahead"]["rule"] == runtime.TIME_TRAVEL_AVAILABILITY_RULE
    assert gate["no_lookahead"]["has_as_of"] is False
    assert gate["no_lookahead"]["available_at_field_present"] is False
    assert gate["no_lookahead"]["available_at_violation_count"] == 0
    integrity = gate["data_snapshot_integrity"]
    assert integrity["request_hash"] == meta["request_hash"]
    assert integrity["preview_row_count"] == 1
    assert integrity["timestamp_field"] == "date"
    assert integrity["timestamp_order_rule"] == runtime.SANITY_TIMESTAMP_ORDER_RULE
    assert integrity["timestamp_duplicate_policy"] == runtime.SANITY_TIMESTAMP_DUPLICATE_POLICY
    assert integrity["timestamp_monotonic_non_decreasing"] is True
    assert integrity["timestamp_duplicate_count"] == 0
    assert integrity["timestamp_rule_satisfied"] is True
    assert integrity["nonzero_missing_ratio_columns"] == []


def test_write_fetch_evidence_preserves_append_only_attempt_history(tmp_path) -> None:
    request_payload = {"intent": {"asset": "stock", "freq": "day"}}
    first_result = runtime.FetchExecutionResult(
        status=runtime.STATUS_PASS_HAS_DATA,
        reason="ok",
        source="fetch",
        source_internal="mysql_fetch",
        engine="mysql",
        provider_id="fetch",
        provider_internal="mysql_fetch",
        resolved_function="fetch_stock_day",
        public_function="fetch_stock_day",
        elapsed_sec=0.01,
        row_count=1,
        columns=["code", "date", "close"],
        dtypes={"code": "object", "date": "object", "close": "float64"},
        preview=[{"code": "000001", "date": "2024-01-02", "close": 10.0}],
        final_kwargs={"code": "000001"},
        mode="smoke",
        data=[{"code": "000001", "date": "2024-01-02", "close": 10.0}],
    )
    second_result = runtime.FetchExecutionResult(
        status=runtime.STATUS_PASS_EMPTY,
        reason="no_data",
        source="fetch",
        source_internal="mysql_fetch",
        engine="mysql",
        provider_id="fetch",
        provider_internal="mysql_fetch",
        resolved_function="fetch_stock_day",
        public_function="fetch_stock_day",
        elapsed_sec=0.02,
        row_count=0,
        columns=[],
        dtypes={},
        preview=[],
        final_kwargs={"code": "000001"},
        mode="smoke",
        data=[],
    )

    first_paths = runtime.write_fetch_evidence(request_payload=request_payload, result=first_result, out_dir=tmp_path)
    second_paths = runtime.write_fetch_evidence(request_payload=request_payload, result=second_result, out_dir=tmp_path)

    first_attempt_dir = tmp_path / runtime.FETCH_EVIDENCE_ATTEMPT_DIRNAME_TEMPLATE.format(attempt_index=1)
    second_attempt_dir = tmp_path / runtime.FETCH_EVIDENCE_ATTEMPT_DIRNAME_TEMPLATE.format(attempt_index=2)
    assert Path(first_paths["attempt_path"]) == first_attempt_dir
    assert Path(second_paths["attempt_path"]) == second_attempt_dir
    assert first_attempt_dir.is_dir()
    assert second_attempt_dir.is_dir()

    first_meta = json.loads((first_attempt_dir / runtime.FETCH_EVIDENCE_RESULT_META_FILENAME).read_text(encoding="utf-8"))
    second_meta = json.loads((second_attempt_dir / runtime.FETCH_EVIDENCE_RESULT_META_FILENAME).read_text(encoding="utf-8"))
    latest_meta = json.loads((tmp_path / runtime.FETCH_EVIDENCE_RESULT_META_FILENAME).read_text(encoding="utf-8"))
    assert first_meta["row_count"] == 1
    assert second_meta["row_count"] == 0
    assert latest_meta["row_count"] == 0

    attempts_index_path = tmp_path / runtime.FETCH_EVIDENCE_ATTEMPTS_INDEX_FILENAME
    assert Path(second_paths["fetch_attempts_index_path"]) == attempts_index_path
    attempts_index = json.loads(attempts_index_path.read_text(encoding="utf-8"))
    assert attempts_index["schema_version"] == "qa_fetch_attempts_index_v1"
    assert attempts_index["rule"] == runtime.FETCH_EVIDENCE_APPEND_ONLY_RULE
    assert attempts_index["latest_attempt_index"] == 2
    assert attempts_index["attempt_count"] == 2
    assert [row["attempt_index"] for row in attempts_index["attempts"]] == [1, 2]


def test_fetch_review_failure_rollback_rerun_rereview_loop_preserves_evidence_readability(tmp_path) -> None:
    first_request_payload = {
        "function": "fetch_stock_day",
        "kwargs": {"code": "000001", "start": "2024-01-01", "end": "2024-01-31"},
        "policy": {"mode": "smoke"},
    }
    second_request_payload = {
        "function": "fetch_stock_day",
        "kwargs": {"code": "000002", "start": "2024-01-01", "end": "2024-01-31"},
        "policy": {"mode": "smoke"},
    }
    first_result = runtime.FetchExecutionResult(
        status=runtime.STATUS_PASS_HAS_DATA,
        reason="ok",
        source="fetch",
        source_internal="mysql_fetch",
        engine="mysql",
        provider_id="fetch",
        provider_internal="mysql_fetch",
        resolved_function="fetch_stock_day",
        public_function="fetch_stock_day",
        elapsed_sec=0.01,
        row_count=1,
        columns=["code", "date", "close"],
        dtypes={"code": "object", "date": "object", "close": "float64"},
        preview=[{"code": "000001", "date": "2024-01-02", "close": 10.0}],
        final_kwargs={"code": "000001"},
        mode="smoke",
        data=[{"code": "000001", "date": "2024-01-02", "close": 10.0}],
    )
    second_result = runtime.FetchExecutionResult(
        status=runtime.STATUS_PASS_HAS_DATA,
        reason="ok",
        source="fetch",
        source_internal="mysql_fetch",
        engine="mysql",
        provider_id="fetch",
        provider_internal="mysql_fetch",
        resolved_function="fetch_stock_day",
        public_function="fetch_stock_day",
        elapsed_sec=0.02,
        row_count=1,
        columns=["code", "date", "close"],
        dtypes={"code": "object", "date": "object", "close": "float64"},
        preview=[{"code": "000002", "date": "2024-01-03", "close": 12.0}],
        final_kwargs={"code": "000002"},
        mode="smoke",
        data=[{"code": "000002", "date": "2024-01-03", "close": 12.0}],
    )

    first_paths = runtime.write_fetch_evidence(
        request_payload=first_request_payload,
        result=first_result,
        out_dir=tmp_path,
    )
    first_attempt_dir = Path(first_paths["attempt_path"])
    first_attempt_request_text = (first_attempt_dir / runtime.FETCH_EVIDENCE_REQUEST_FILENAME).read_text(encoding="utf-8")
    first_attempt_meta_text = (first_attempt_dir / runtime.FETCH_EVIDENCE_RESULT_META_FILENAME).read_text(encoding="utf-8")
    first_attempt_preview_text = (first_attempt_dir / runtime.FETCH_EVIDENCE_PREVIEW_FILENAME).read_text(encoding="utf-8")
    first_attempt_steps_index_text = (
        first_attempt_dir / runtime.FETCH_EVIDENCE_STEPS_INDEX_FILENAME
    ).read_text(encoding="utf-8")

    assert runtime.FETCH_REVIEW_CHECKPOINT_REJECT_ACTION == "reject"
    assert runtime.FETCH_REVIEW_CHECKPOINT_REJECT_TRANSITION == "rollback_and_allow_fetch_request_edit_or_rerun"

    second_paths = runtime.write_fetch_evidence(
        request_payload=second_request_payload,
        result=second_result,
        out_dir=tmp_path,
    )
    second_attempt_dir = Path(second_paths["attempt_path"])
    assert second_attempt_dir != first_attempt_dir

    assert runtime.FETCH_REVIEW_CHECKPOINT_APPROVE_ACTION == "approve"
    assert runtime.FETCH_REVIEW_CHECKPOINT_APPROVE_TRANSITION == "enter_next_stage"

    assert (first_attempt_dir / runtime.FETCH_EVIDENCE_REQUEST_FILENAME).read_text(encoding="utf-8") == first_attempt_request_text
    assert (first_attempt_dir / runtime.FETCH_EVIDENCE_RESULT_META_FILENAME).read_text(encoding="utf-8") == first_attempt_meta_text
    assert (first_attempt_dir / runtime.FETCH_EVIDENCE_PREVIEW_FILENAME).read_text(encoding="utf-8") == first_attempt_preview_text
    assert (first_attempt_dir / runtime.FETCH_EVIDENCE_STEPS_INDEX_FILENAME).read_text(encoding="utf-8") == first_attempt_steps_index_text

    attempts_index = json.loads(Path(second_paths["fetch_attempts_index_path"]).read_text(encoding="utf-8"))
    assert attempts_index["rule"] == runtime.FETCH_EVIDENCE_APPEND_ONLY_RULE
    assert attempts_index["latest_attempt_index"] == 2
    assert attempts_index["attempt_count"] == 2
    assert [row["attempt_index"] for row in attempts_index["attempts"]] == [1, 2]

    first_attempt_request = json.loads(first_attempt_request_text)
    latest_request = json.loads(Path(second_paths["fetch_request_path"]).read_text(encoding="utf-8"))
    assert first_attempt_request["kwargs"]["code"] == "000001"
    assert latest_request["kwargs"]["code"] == "000002"

    latest_steps_index = json.loads(Path(second_paths["fetch_steps_index_path"]).read_text(encoding="utf-8"))
    assert latest_steps_index["schema_version"] == "qa_fetch_steps_index_v1"
    assert latest_steps_index["steps"][0]["preview_path"] == second_paths["fetch_preview_path"]
    assert Path(second_paths["fetch_result_meta_path"]).is_file()
    assert Path(second_paths["fetch_preview_path"]).is_file()
    assert "000002" in Path(second_paths["fetch_preview_path"]).read_text(encoding="utf-8")


def test_execute_ui_llm_query_fail_rollback_rerun_rereview_preserves_read_only_dossier_timeline(tmp_path, monkeypatch) -> None:
    run_id = "run_ui_g339_qf105"
    failing_request = {
        "query_id": "q_stock_day_fail_105",
        "run_id": run_id,
        "fetch_request": {
            "intent": {"asset": "stock", "freq": "day"},
            "symbols": ["000001"],
            "policy": {"mode": "smoke"},
        },
    }
    retrying_request = {
        "query_id": "q_stock_day_rerun_105",
        "run_id": run_id,
        "fetch_request": {
            "intent": {"asset": "stock", "freq": "day"},
            "symbols": ["000002"],
            "policy": {"mode": "smoke"},
        },
    }
    fail_result = runtime.FetchExecutionResult(
        status=runtime.STATUS_ERROR_RUNTIME,
        reason="RuntimeError: upstream unavailable",
        source="fetch",
        source_internal="mongo_fetch",
        engine="mongo",
        provider_id="fetch",
        provider_internal="mongo_fetch",
        resolved_function="fetch_stock_day",
        public_function="fetch_stock_day",
        elapsed_sec=0.02,
        row_count=0,
        columns=[],
        dtypes={},
        preview=[],
        final_kwargs={"code": "000001"},
        mode="smoke",
        data=None,
    )
    success_result = runtime.FetchExecutionResult(
        status=runtime.STATUS_PASS_HAS_DATA,
        reason="ok",
        source="fetch",
        source_internal="mongo_fetch",
        engine="mongo",
        provider_id="fetch",
        provider_internal="mongo_fetch",
        resolved_function="fetch_stock_day",
        public_function="fetch_stock_day",
        elapsed_sec=0.03,
        row_count=1,
        columns=["code", "date", "close"],
        dtypes={"code": "object", "date": "object", "close": "float64"},
        preview=[{"code": "000002", "date": "2024-01-03", "close": 12.0}],
        final_kwargs={"code": "000002"},
        mode="smoke",
        data=[{"code": "000002", "date": "2024-01-03", "close": 12.0}],
    )
    state = {"call_index": 0}

    def _fake_execute_fetch_by_intent(*_args: Any, **_kwargs: Any) -> runtime.FetchExecutionResult:
        if state["call_index"] == 0:
            state["call_index"] += 1
            return fail_result
        return success_result

    monkeypatch.setattr(runtime, "execute_fetch_by_intent", _fake_execute_fetch_by_intent)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        runtime,
        "enforce_fetch_evidence_snapshot_manifest_gate",
        lambda **_kwargs: {"gate_pass": True},
    )

    first = runtime.execute_ui_llm_query(failing_request, out_dir=tmp_path)
    assert first["query_result"]["status"] == runtime.STATUS_ERROR_RUNTIME

    first_payload = first[runtime.UI_DOSSIER_FETCH_EVIDENCE_FIELD]
    assert first_payload is not None
    assert len(first_payload[runtime.UI_DOSSIER_FETCH_EVIDENCE_ATTEMPTS_FIELD]) == 1
    first_attempt = first_payload[runtime.UI_DOSSIER_FETCH_EVIDENCE_ATTEMPTS_FIELD][0]
    assert first_attempt["attempt_index"] == 1
    assert first_attempt["is_active"] is True

    rollback_result = runtime.apply_fetch_review_rollback(
        fetch_evidence_dir=runtime._build_dossier_fetch_root_path(run_id),
        action=runtime.FETCH_REVIEW_CHECKPOINT_REJECT_ACTION,
        target_attempt_index=first_attempt["attempt_index"],
        target_scope=runtime.FETCH_REVIEW_ROLLBACK_SCOPE_CANONICAL_FILES_WITH_ERRORS,
        confirm=True,
        expected_latest_attempt_index=first_attempt["attempt_index"],
        expected_latest_preview_hash=first_attempt["preview_hash"],
        expected_target_request_hash=first_attempt["request_hash"],
    )
    assert rollback_result["success"] is True
    assert rollback_result["status"] == "rollback_applied"

    second = runtime.execute_ui_llm_query(retrying_request, out_dir=tmp_path)
    assert second["query_result"]["status"] == runtime.STATUS_PASS_HAS_DATA
    second_payload = second[runtime.UI_DOSSIER_FETCH_EVIDENCE_FIELD]
    assert second_payload is not None
    attempts = second_payload[runtime.UI_DOSSIER_FETCH_EVIDENCE_ATTEMPTS_FIELD]
    steps = second_payload[runtime.UI_DOSSIER_FETCH_EVIDENCE_STEPS_FIELD]
    assert [attempt["attempt_index"] for attempt in attempts] == [1, 2]
    assert attempts[1]["status"] == runtime.STATUS_PASS_HAS_DATA
    assert attempts[1]["is_active"] is True
    assert any(row["attempt_index"] == 2 for row in steps)
    assert second_payload[runtime.UI_DOSSIER_FETCH_EVIDENCE_RETRY_ROLLBACK_FIELD]["latest_attempt_index"] == 2
    assert second_payload[runtime.UI_DOSSIER_FETCH_EVIDENCE_RETRY_ROLLBACK_FIELD]["review_status"] == "ready"
    rereview_checkpoint = runtime.build_fetch_review_checkpoint_state(
        fetch_evidence_dir=runtime._build_dossier_fetch_root_path(run_id)
    )
    assert rereview_checkpoint["latest_attempt_index"] == 2
    assert rereview_checkpoint["reviewable_changes"] is not None


def test_build_fetch_review_checkpoint_state_exposes_reviewable_changes_and_rollback_entrypoint(tmp_path) -> None:
    first_request_payload = {
        "function": "fetch_stock_day",
        "kwargs": {"code": "000001", "start": "2024-01-01", "end": "2024-01-31"},
        "policy": {"mode": "smoke"},
    }
    second_request_payload = {
        "function": "fetch_stock_day",
        "kwargs": {"code": "000002", "start": "2024-01-01", "end": "2024-01-31"},
        "policy": {"mode": "smoke"},
    }
    first_result = runtime.FetchExecutionResult(
        status=runtime.STATUS_PASS_HAS_DATA,
        reason="ok",
        source="fetch",
        source_internal="mysql_fetch",
        engine="mysql",
        provider_id="fetch",
        provider_internal="mysql_fetch",
        resolved_function="fetch_stock_day",
        public_function="fetch_stock_day",
        elapsed_sec=0.01,
        row_count=1,
        columns=["code", "date", "close"],
        dtypes={"code": "object", "date": "object", "close": "float64"},
        preview=[{"code": "000001", "date": "2024-01-02", "close": 10.0}],
        final_kwargs={"code": "000001"},
        mode="smoke",
        data=[{"code": "000001", "date": "2024-01-02", "close": 10.0}],
    )
    second_result = runtime.FetchExecutionResult(
        status=runtime.STATUS_PASS_HAS_DATA,
        reason="ok",
        source="fetch",
        source_internal="mysql_fetch",
        engine="mysql",
        provider_id="fetch",
        provider_internal="mysql_fetch",
        resolved_function="fetch_stock_day",
        public_function="fetch_stock_day",
        elapsed_sec=0.02,
        row_count=2,
        columns=["code", "date", "close"],
        dtypes={"code": "object", "date": "object", "close": "float64"},
        preview=[
            {"code": "000002", "date": "2024-01-03", "close": 12.0},
            {"code": "000002", "date": "2024-01-04", "close": 13.0},
        ],
        final_kwargs={"code": "000002"},
        mode="smoke",
        data=[
            {"code": "000002", "date": "2024-01-03", "close": 12.0},
            {"code": "000002", "date": "2024-01-04", "close": 13.0},
        ],
    )

    runtime.write_fetch_evidence(
        request_payload=first_request_payload,
        result=first_result,
        out_dir=tmp_path,
    )
    runtime.write_fetch_evidence(
        request_payload=second_request_payload,
        result=second_result,
        out_dir=tmp_path,
    )

    checkpoint_state = runtime.build_fetch_review_checkpoint_state(fetch_evidence_dir=tmp_path)

    assert checkpoint_state["schema_version"] == runtime.FETCH_REVIEW_CHECKPOINT_STATE_SCHEMA_VERSION
    assert checkpoint_state["review_status"] == "ready"
    assert checkpoint_state["attempt_count"] == 2
    assert checkpoint_state["latest_attempt_index"] == 2
    assert [row["attempt_index"] for row in checkpoint_state["attempts"]] == [1, 2]
    changes = checkpoint_state["reviewable_changes"]
    assert changes["base_attempt_index"] == 1
    assert changes["candidate_attempt_index"] == 2
    assert changes["request_hash_changed"] is True
    assert changes["row_count_delta"] == 1
    entrypoint = checkpoint_state["rollback_entrypoint"]
    assert entrypoint["action"] == runtime.FETCH_REVIEW_CHECKPOINT_REJECT_ACTION
    assert entrypoint["transition"] == runtime.FETCH_REVIEW_CHECKPOINT_REJECT_TRANSITION
    assert entrypoint["confirmation_required"] is True
    assert entrypoint["target_scope_options"] == list(runtime.FETCH_REVIEW_ROLLBACK_SCOPE_OPTIONS)
    assert entrypoint["target_attempt_index_options"] == [1, 2]


def test_apply_fetch_review_rollback_requires_scope_confirmation_and_fresh_review_state(tmp_path) -> None:
    request_payload = {
        "function": "fetch_stock_day",
        "kwargs": {"code": "000001", "start": "2024-01-01", "end": "2024-01-31"},
        "policy": {"mode": "smoke"},
    }
    runtime.write_fetch_evidence(
        request_payload=request_payload,
        result=_dummy_result(),
        out_dir=tmp_path,
    )
    runtime.write_fetch_evidence(
        request_payload={**request_payload, "kwargs": {"code": "000002", "start": "2024-01-01", "end": "2024-01-31"}},
        result=_dummy_result(),
        out_dir=tmp_path,
    )

    invalid_scope = runtime.apply_fetch_review_rollback(
        fetch_evidence_dir=tmp_path,
        target_attempt_index=1,
        target_scope="unknown_scope",
        confirm=True,
    )
    assert invalid_scope["success"] is False
    assert invalid_scope["failure_reason"] == "invalid_target_scope"

    needs_confirm = runtime.apply_fetch_review_rollback(
        fetch_evidence_dir=tmp_path,
        target_attempt_index=1,
        target_scope=runtime.FETCH_REVIEW_ROLLBACK_SCOPE_CANONICAL_FILES,
        confirm=False,
    )
    assert needs_confirm["success"] is False
    assert needs_confirm["failure_reason"] == "confirmation_required"

    stale_state = runtime.apply_fetch_review_rollback(
        fetch_evidence_dir=tmp_path,
        target_attempt_index=1,
        target_scope=runtime.FETCH_REVIEW_ROLLBACK_SCOPE_CANONICAL_FILES,
        confirm=True,
        expected_latest_attempt_index=1,
    )
    assert stale_state["success"] is False
    assert stale_state["failure_reason"] == "stale_review_state"
    assert stale_state["latest_attempt_index"] == 2


def test_apply_fetch_review_rollback_rejects_stale_preview_hash_and_preserves_append_only_history(tmp_path) -> None:
    first_request_payload = {
        "function": "fetch_stock_day",
        "kwargs": {"code": "000001", "start": "2024-01-01", "end": "2024-01-31"},
        "policy": {"mode": "smoke"},
    }
    second_request_payload = {
        "function": "fetch_stock_day",
        "kwargs": {"code": "000002", "start": "2024-01-01", "end": "2024-01-31"},
        "policy": {"mode": "smoke"},
    }
    first_result = runtime.FetchExecutionResult(
        status=runtime.STATUS_PASS_HAS_DATA,
        reason="ok",
        source="fetch",
        source_internal="mysql_fetch",
        engine="mysql",
        provider_id="fetch",
        provider_internal="mysql_fetch",
        resolved_function="fetch_stock_day",
        public_function="fetch_stock_day",
        elapsed_sec=0.01,
        row_count=1,
        columns=["code", "date", "close"],
        dtypes={"code": "object", "date": "object", "close": "float64"},
        preview=[{"code": "000001", "date": "2024-01-02", "close": 10.0}],
        final_kwargs={"code": "000001"},
        mode="smoke",
        data=[{"code": "000001", "date": "2024-01-02", "close": 10.0}],
    )
    second_result = runtime.FetchExecutionResult(
        status=runtime.STATUS_PASS_HAS_DATA,
        reason="ok",
        source="fetch",
        source_internal="mysql_fetch",
        engine="mysql",
        provider_id="fetch",
        provider_internal="mysql_fetch",
        resolved_function="fetch_stock_day",
        public_function="fetch_stock_day",
        elapsed_sec=0.02,
        row_count=1,
        columns=["code", "date", "close"],
        dtypes={"code": "object", "date": "object", "close": "float64"},
        preview=[{"code": "000002", "date": "2024-01-03", "close": 12.0}],
        final_kwargs={"code": "000002"},
        mode="smoke",
        data=[{"code": "000002", "date": "2024-01-03", "close": 12.0}],
    )

    runtime.write_fetch_evidence(
        request_payload=first_request_payload,
        result=first_result,
        out_dir=tmp_path,
    )
    runtime.write_fetch_evidence(
        request_payload=second_request_payload,
        result=second_result,
        out_dir=tmp_path,
    )

    checkpoint_state = runtime.build_fetch_review_checkpoint_state(fetch_evidence_dir=tmp_path)
    stale_preview_hash = checkpoint_state["attempts"][0]["preview_hash"]
    assert stale_preview_hash != checkpoint_state["latest_preview_hash"]

    stale_preview = runtime.apply_fetch_review_rollback(
        fetch_evidence_dir=tmp_path,
        target_attempt_index=1,
        target_scope=runtime.FETCH_REVIEW_ROLLBACK_SCOPE_CANONICAL_FILES,
        confirm=True,
        expected_latest_attempt_index=2,
        expected_latest_preview_hash=stale_preview_hash,
    )
    assert stale_preview["success"] is False
    assert stale_preview["failure_reason"] == "stale_review_preview"
    assert stale_preview["latest_attempt_index"] == 2

    attempts_index = json.loads((tmp_path / runtime.FETCH_EVIDENCE_ATTEMPTS_INDEX_FILENAME).read_text(encoding="utf-8"))
    assert attempts_index["latest_attempt_index"] == 2
    assert attempts_index["attempt_count"] == 2
    assert [row["attempt_index"] for row in attempts_index["attempts"]] == [1, 2]

    latest_request = json.loads((tmp_path / runtime.FETCH_EVIDENCE_REQUEST_FILENAME).read_text(encoding="utf-8"))
    assert latest_request["kwargs"]["code"] == "000002"


def test_apply_fetch_review_approve_path_moves_to_next_stage_without_mutating_attempt_audit(tmp_path) -> None:
    first_request_payload = {
        "function": "fetch_stock_day",
        "kwargs": {"code": "000001", "start": "2024-01-01", "end": "2024-01-31"},
        "policy": {"mode": "smoke"},
    }
    second_request_payload = {
        "function": "fetch_stock_day",
        "kwargs": {"code": "000002", "start": "2024-01-01", "end": "2024-01-31"},
        "policy": {"mode": "smoke"},
    }

    runtime.write_fetch_evidence(
        request_payload=first_request_payload,
        result=_dummy_result(),
        out_dir=tmp_path,
    )
    runtime.write_fetch_evidence(
        request_payload=second_request_payload,
        result=_dummy_result(),
        out_dir=tmp_path,
    )

    checkpoint_state = runtime.build_fetch_review_checkpoint_state(fetch_evidence_dir=tmp_path)
    pre_root_request = (tmp_path / runtime.FETCH_EVIDENCE_REQUEST_FILENAME).read_text(encoding="utf-8")
    pre_root_meta = (tmp_path / runtime.FETCH_EVIDENCE_RESULT_META_FILENAME).read_text(encoding="utf-8")
    pre_root_preview = (tmp_path / runtime.FETCH_EVIDENCE_PREVIEW_FILENAME).read_text(encoding="utf-8")
    pre_root_steps_index = (tmp_path / runtime.FETCH_EVIDENCE_STEPS_INDEX_FILENAME).read_text(encoding="utf-8")
    pre_attempt_dirs = sorted(p.name for p in tmp_path.glob("attempt_*") if p.is_dir())

    approve_result = runtime.apply_fetch_review_rollback(
        fetch_evidence_dir=tmp_path,
        action=runtime.FETCH_REVIEW_CHECKPOINT_APPROVE_ACTION,
        target_attempt_index=2,
        target_scope=runtime.FETCH_REVIEW_ROLLBACK_SCOPE_CANONICAL_FILES_WITH_ERRORS,
        expected_latest_attempt_index=checkpoint_state["latest_attempt_index"],
        expected_latest_preview_hash=checkpoint_state["latest_preview_hash"],
        expected_target_request_hash=checkpoint_state["attempts"][-1].get("request_hash"),
    )

    assert approve_result["success"] is True
    assert approve_result["action"] == runtime.FETCH_REVIEW_CHECKPOINT_APPROVE_ACTION
    assert approve_result["transition"] == runtime.FETCH_REVIEW_CHECKPOINT_APPROVE_TRANSITION
    assert approve_result["status"] == "review_approved"
    assert approve_result["active_attempt_index"] == 2
    assert (tmp_path / runtime.FETCH_REVIEW_ROLLBACK_LOG_FILENAME).is_file()

    attempts_index = json.loads((tmp_path / runtime.FETCH_EVIDENCE_ATTEMPTS_INDEX_FILENAME).read_text(encoding="utf-8"))
    assert attempts_index["latest_attempt_index"] == 2
    assert attempts_index["attempt_count"] == 2
    assert [row["attempt_index"] for row in attempts_index["attempts"]] == [1, 2]

    assert (tmp_path / runtime.FETCH_EVIDENCE_REQUEST_FILENAME).read_text(encoding="utf-8") == pre_root_request
    assert (tmp_path / runtime.FETCH_EVIDENCE_RESULT_META_FILENAME).read_text(encoding="utf-8") == pre_root_meta
    assert (tmp_path / runtime.FETCH_EVIDENCE_PREVIEW_FILENAME).read_text(encoding="utf-8") == pre_root_preview
    assert (tmp_path / runtime.FETCH_EVIDENCE_STEPS_INDEX_FILENAME).read_text(encoding="utf-8") == pre_root_steps_index

    post_attempt_dirs = sorted(p.name for p in tmp_path.glob("attempt_*") if p.is_dir())
    assert post_attempt_dirs == pre_attempt_dirs


def test_apply_fetch_review_rollback_rejects_target_attempt_identity_mismatch(tmp_path) -> None:
    first_request_payload = {
        "function": "fetch_stock_day",
        "kwargs": {"code": "000001", "start": "2024-01-01", "end": "2024-01-31"},
        "policy": {"mode": "smoke"},
    }
    second_request_payload = {
        "function": "fetch_stock_day",
        "kwargs": {"code": "000002", "start": "2024-01-01", "end": "2024-01-31"},
        "policy": {"mode": "smoke"},
    }

    runtime.write_fetch_evidence(
        request_payload=first_request_payload,
        result=_dummy_result(),
        out_dir=tmp_path,
    )
    runtime.write_fetch_evidence(
        request_payload=second_request_payload,
        result=_dummy_result(),
        out_dir=tmp_path,
    )

    mismatched_identity = runtime.apply_fetch_review_rollback(
        fetch_evidence_dir=tmp_path,
        target_attempt_index=1,
        target_scope=runtime.FETCH_REVIEW_ROLLBACK_SCOPE_CANONICAL_FILES_WITH_ERRORS,
        confirm=True,
        expected_latest_attempt_index=2,
        expected_target_request_hash="0" * 64,
    )

    assert mismatched_identity["success"] is False
    assert mismatched_identity["failure_reason"] == "target_attempt_identity_mismatch"
    attempts_index = json.loads((tmp_path / runtime.FETCH_EVIDENCE_ATTEMPTS_INDEX_FILENAME).read_text(encoding="utf-8"))
    assert attempts_index["latest_attempt_index"] == 2
    assert attempts_index["attempt_count"] == 2


def test_apply_fetch_review_rollback_restores_target_attempt_with_scope_feedback(tmp_path) -> None:
    first_request_payload = {
        "function": "fetch_stock_day",
        "kwargs": {"code": "000001", "start": "2024-01-01", "end": "2024-01-31"},
        "policy": {"mode": "smoke"},
    }
    second_request_payload = {
        "function": "fetch_stock_day",
        "kwargs": {"code": "000002", "start": "2024-01-01", "end": "2024-01-31"},
        "policy": {"mode": "smoke"},
    }
    first_result = runtime.FetchExecutionResult(
        status=runtime.STATUS_PASS_HAS_DATA,
        reason="ok",
        source="fetch",
        source_internal="mysql_fetch",
        engine="mysql",
        provider_id="fetch",
        provider_internal="mysql_fetch",
        resolved_function="fetch_stock_day",
        public_function="fetch_stock_day",
        elapsed_sec=0.01,
        row_count=1,
        columns=["code", "date", "close"],
        dtypes={"code": "object", "date": "object", "close": "float64"},
        preview=[{"code": "000001", "date": "2024-01-02", "close": 10.0}],
        final_kwargs={"code": "000001"},
        mode="smoke",
        data=[{"code": "000001", "date": "2024-01-02", "close": 10.0}],
    )
    second_result = runtime.FetchExecutionResult(
        status=runtime.STATUS_ERROR_RUNTIME,
        reason="RuntimeError: upstream unavailable",
        source="fetch",
        source_internal="mysql_fetch",
        engine="mysql",
        provider_id="fetch",
        provider_internal="mysql_fetch",
        resolved_function="fetch_stock_day",
        public_function="fetch_stock_day",
        elapsed_sec=0.02,
        row_count=0,
        columns=[],
        dtypes={},
        preview=[],
        final_kwargs={"code": "000002"},
        mode="smoke",
        data=None,
    )

    runtime.write_fetch_evidence(
        request_payload=first_request_payload,
        result=first_result,
        out_dir=tmp_path,
    )
    runtime.write_fetch_evidence(
        request_payload=second_request_payload,
        result=second_result,
        out_dir=tmp_path,
    )
    assert (tmp_path / runtime.FETCH_EVIDENCE_ERROR_FILENAME).is_file()
    assert (tmp_path / runtime.UI_FETCH_EVIDENCE_VIEWER_ERROR_FILENAME).is_file()

    rollback_result = runtime.apply_fetch_review_rollback(
        fetch_evidence_dir=tmp_path,
        target_attempt_index=1,
        target_scope=runtime.FETCH_REVIEW_ROLLBACK_SCOPE_CANONICAL_FILES,
        confirm=True,
        expected_latest_attempt_index=2,
    )

    assert rollback_result["success"] is True
    assert rollback_result["status"] == "rollback_applied"
    assert rollback_result["active_attempt_index"] == 1
    assert rollback_result["target_scope"] == runtime.FETCH_REVIEW_ROLLBACK_SCOPE_CANONICAL_FILES
    assert Path(rollback_result["rollback_log_path"]).is_file()
    assert Path(rollback_result["rollback_state_path"]).is_file()
    rolled_back_request = json.loads((tmp_path / runtime.FETCH_EVIDENCE_REQUEST_FILENAME).read_text(encoding="utf-8"))
    assert rolled_back_request["kwargs"]["code"] == "000001"
    assert not (tmp_path / runtime.FETCH_EVIDENCE_ERROR_FILENAME).exists()
    assert not (tmp_path / runtime.UI_FETCH_EVIDENCE_VIEWER_ERROR_FILENAME).exists()

    attempts_index = json.loads((tmp_path / runtime.FETCH_EVIDENCE_ATTEMPTS_INDEX_FILENAME).read_text(encoding="utf-8"))
    assert attempts_index["latest_attempt_index"] == 2
    assert attempts_index["attempt_count"] == 2

    rollback_log_lines = (tmp_path / runtime.FETCH_REVIEW_ROLLBACK_LOG_FILENAME).read_text(encoding="utf-8").splitlines()
    assert rollback_log_lines
    rollback_log_payload = json.loads(rollback_log_lines[-1])
    assert rollback_log_payload["success"] is True
    assert rollback_log_payload["active_attempt_index"] == 1


def test_write_fetch_evidence_pass_empty_persists_optional_probe_status(tmp_path) -> None:
    result = runtime.FetchExecutionResult(
        status=runtime.STATUS_PASS_EMPTY,
        reason="no_data",
        source="fetch",
        source_internal="mysql_fetch",
        engine="mysql",
        provider_id="fetch",
        provider_internal="mysql_fetch",
        resolved_function="fetch_stock_day",
        public_function="fetch_stock_day",
        elapsed_sec=0.01,
        row_count=0,
        columns=[],
        dtypes={},
        preview=[],
        final_kwargs={"code": "000001"},
        mode="smoke",
        data=[],
    )

    runtime.write_fetch_evidence(
        request_payload={"intent": {"asset": "stock", "freq": "day"}},
        result=result,
        out_dir=tmp_path,
    )
    meta = json.loads((tmp_path / "fetch_result_meta.json").read_text(encoding="utf-8"))
    assert meta["probe_status"] == runtime.STATUS_PASS_EMPTY
    assert meta["warnings"] == ["no_data"]
    sanity = meta["sanity_checks"]
    assert sanity["empty_data_policy_rule"] == runtime.SANITY_EMPTY_DATA_POLICY_RULE
    assert sanity["on_no_data_policy"] == "pass_empty"
    assert sanity["empty_data_expected_status"] == runtime.STATUS_PASS_EMPTY
    assert sanity["empty_data_observed_status"] == runtime.STATUS_PASS_EMPTY
    assert sanity["empty_data_semantics_consistent"] is True


def test_write_fetch_evidence_empty_data_policy_error_marks_consistent_semantics(tmp_path) -> None:
    result = runtime.FetchExecutionResult(
        status=runtime.STATUS_ERROR_RUNTIME,
        reason="no_data",
        source="fetch",
        source_internal="mysql_fetch",
        engine="mysql",
        provider_id="fetch",
        provider_internal="mysql_fetch",
        resolved_function="fetch_stock_day",
        public_function="fetch_stock_day",
        elapsed_sec=0.01,
        row_count=0,
        columns=[],
        dtypes={},
        preview=[],
        final_kwargs={"code": "000001"},
        mode="smoke",
        data=None,
    )

    runtime.write_fetch_evidence(
        request_payload={"intent": {"asset": "stock", "freq": "day"}, "policy": {"on_no_data": "error"}},
        result=result,
        out_dir=tmp_path,
    )
    meta = json.loads((tmp_path / "fetch_result_meta.json").read_text(encoding="utf-8"))
    sanity = meta["sanity_checks"]
    assert sanity["empty_data_policy_rule"] == runtime.SANITY_EMPTY_DATA_POLICY_RULE
    assert sanity["on_no_data_policy"] == "error"
    assert sanity["empty_data_expected_status"] == runtime.STATUS_ERROR_RUNTIME
    assert sanity["empty_data_observed_status"] == runtime.STATUS_ERROR_RUNTIME
    assert sanity["empty_data_semantics_consistent"] is True


def test_write_fetch_evidence_empty_data_policy_inconsistency_is_recorded(tmp_path) -> None:
    result = runtime.FetchExecutionResult(
        status=runtime.STATUS_ERROR_RUNTIME,
        reason="no_data",
        source="fetch",
        source_internal="mysql_fetch",
        engine="mysql",
        provider_id="fetch",
        provider_internal="mysql_fetch",
        resolved_function="fetch_stock_day",
        public_function="fetch_stock_day",
        elapsed_sec=0.01,
        row_count=0,
        columns=[],
        dtypes={},
        preview=[],
        final_kwargs={"code": "000001"},
        mode="smoke",
        data=None,
    )

    runtime.write_fetch_evidence(
        request_payload={"intent": {"asset": "stock", "freq": "day"}, "policy": {"on_no_data": "pass_empty"}},
        result=result,
        out_dir=tmp_path,
    )
    meta = json.loads((tmp_path / "fetch_result_meta.json").read_text(encoding="utf-8"))
    sanity = meta["sanity_checks"]
    assert sanity["on_no_data_policy"] == "pass_empty"
    assert sanity["empty_data_expected_status"] == runtime.STATUS_PASS_EMPTY
    assert sanity["empty_data_observed_status"] == runtime.STATUS_ERROR_RUNTIME
    assert sanity["empty_data_semantics_consistent"] is False


def test_write_fetch_evidence_failure_emits_qf_061_fetch_error_json(tmp_path) -> None:
    request_payload = {
        "intent": {"asset": "stock", "freq": "day"},
        "symbols": ["000001", "000002"],
    }
    result = runtime.FetchExecutionResult(
        status=runtime.STATUS_ERROR_RUNTIME,
        reason="RuntimeError: boom",
        source="fetch",
        source_internal="mongo_fetch",
        engine="mongo",
        provider_id="fetch",
        provider_internal="mongo_fetch",
        resolved_function="fetch_stock_day",
        public_function="fetch_stock_day",
        elapsed_sec=0.02,
        row_count=0,
        columns=[],
        dtypes={},
        preview=[],
        final_kwargs={"code": "000001"},
        mode="smoke",
        data=None,
    )

    paths = runtime.write_fetch_evidence(
        request_payload=request_payload,
        result=result,
        out_dir=tmp_path,
    )
    idx = json.loads((tmp_path / runtime.FETCH_EVIDENCE_STEPS_INDEX_FILENAME).read_text(encoding="utf-8"))
    step = idx["steps"][0]
    assert Path(paths["fetch_request_path"]).name == runtime.FETCH_EVIDENCE_REQUEST_FILENAME
    assert Path(paths["fetch_request_path"]).is_file()
    assert Path(paths["fetch_result_meta_path"]).name == runtime.FETCH_EVIDENCE_RESULT_META_FILENAME
    assert Path(paths["fetch_result_meta_path"]).is_file()
    assert Path(paths["fetch_preview_path"]).name == runtime.FETCH_EVIDENCE_PREVIEW_FILENAME
    assert Path(paths["fetch_preview_path"]).is_file()
    written_request = json.loads(Path(paths["fetch_request_path"]).read_text(encoding="utf-8"))
    assert written_request == request_payload
    assert "fetch_error_path" in paths
    assert "error_path" in paths
    assert Path(paths["fetch_error_path"]).name == runtime.FETCH_EVIDENCE_ERROR_FILENAME
    assert Path(paths["fetch_error_path"]).is_file()
    assert Path(paths["error_path"]).name == runtime.UI_FETCH_EVIDENCE_VIEWER_ERROR_FILENAME
    assert Path(paths["error_path"]).is_file()
    fetch_error_doc = json.loads(Path(paths["fetch_error_path"]).read_text(encoding="utf-8"))
    ui_error_doc = json.loads(Path(paths["error_path"]).read_text(encoding="utf-8"))
    assert ui_error_doc == fetch_error_doc
    assert step["error_path"] == paths["fetch_error_path"]
    meta = json.loads((tmp_path / "fetch_result_meta.json").read_text(encoding="utf-8"))
    required_meta_fields = {
        "selected_function",
        "engine",
        "row_count",
        "col_count",
        "min_ts",
        "max_ts",
        "request_hash",
        "coverage",
        "warnings",
    }
    assert required_meta_fields.issubset(meta.keys())
    assert meta["engine"] in runtime.FETCH_RESULT_META_ENGINE_OPTIONS
    assert meta["probe_status"] == runtime.STATUS_ERROR_RUNTIME
    assert meta["warnings"] == ["RuntimeError: boom"]
    assert meta["request_hash"] == runtime._canonical_request_hash(request_payload)
    assert isinstance(meta["request_hash"], str) and len(meta["request_hash"]) == 64
    assert meta["row_count"] == 0
    assert meta["col_count"] == 0
    assert meta["min_ts"] is None
    assert meta["max_ts"] is None
    assert meta["coverage"]["requested_symbols"] == ["000001", "000002"]
    assert meta["coverage"]["observed_symbols"] == []
    assert meta["coverage"]["missing_symbols"] == ["000001", "000002"]
    assert meta["coverage"]["missing_symbol_count"] == 2
    assert meta["coverage"]["symbol_missing_rate_denominator"] == 2
    assert meta["coverage"]["symbol_missing_rate_numerator"] == 2
    assert meta["coverage"]["symbol_coverage_rate"] == 0.0
    assert meta["coverage"]["symbol_missing_rate"] == 1.0
    assert meta["coverage"]["symbol_missing_ratio"] == 1.0
    sanity = meta["sanity_checks"]
    assert sanity["timestamp_field"] == ""
    assert sanity["timestamp_order_rule"] == runtime.SANITY_TIMESTAMP_ORDER_RULE
    assert sanity["timestamp_duplicate_policy"] == runtime.SANITY_TIMESTAMP_DUPLICATE_POLICY
    assert sanity["timestamp_monotonic_non_decreasing"] is True
    assert sanity["timestamp_duplicate_count"] == 0
    assert sanity["timestamp_rule_satisfied"] is True
    assert sanity["missing_ratio_by_column"] == {}
    assert sanity["preview_row_count"] == 0
    gate = meta["gate_input_summary"]
    assert gate["no_lookahead"]["has_as_of"] is False
    assert gate["no_lookahead"]["available_at_field_present"] is False
    assert gate["no_lookahead"]["available_at_violation_count"] == 0
    integrity = gate["data_snapshot_integrity"]
    assert integrity["request_hash"] == meta["request_hash"]
    assert integrity["preview_row_count"] == 0
    assert integrity["timestamp_field"] == ""
    assert integrity["timestamp_order_rule"] == runtime.SANITY_TIMESTAMP_ORDER_RULE
    assert integrity["timestamp_duplicate_policy"] == runtime.SANITY_TIMESTAMP_DUPLICATE_POLICY
    assert integrity["timestamp_monotonic_non_decreasing"] is True
    assert integrity["timestamp_duplicate_count"] == 0
    assert integrity["timestamp_rule_satisfied"] is True
    assert integrity["nonzero_missing_ratio_columns"] == []


def test_build_coverage_summary_qf_054_reports_scope_formula_and_request_level_granularity() -> None:
    request_payload = {
        "symbols": ["000001", "000002", "000001"],
        "intent": {
            "asset": "stock",
            "freq": "day",
            "symbols": "000003",
            "extra_kwargs": {
                "code": ["000002", "000004"],
                "symbol": "000005",
            },
        },
        "kwargs": {"symbol": ["000003", "000006"]},
    }
    preview = [
        {"code": "000001", "date": "2024-01-02"},
        {"symbol": "000004", "date": "2024-01-02"},
        {"ticker": "000006", "date": "2024-01-02"},
        {"symbols": ["000006", "000007"], "date": "2024-01-02"},
    ]

    coverage = runtime._build_coverage_summary(request_payload, preview)

    assert coverage["symbol_coverage_scope"] == runtime.FETCH_RESULT_META_COVERAGE_SYMBOL_SCOPE
    assert coverage["reporting_granularity"] == runtime.FETCH_RESULT_META_COVERAGE_REPORTING_GRANULARITY
    assert coverage["symbol_missing_rate_formula"] == runtime.FETCH_RESULT_META_COVERAGE_MISSING_RATE_FORMULA
    assert coverage["requested_symbols"] == ["000001", "000002", "000003", "000004", "000005", "000006"]
    assert coverage["observed_symbols"] == ["000001", "000004", "000006", "000007"]
    assert coverage["covered_symbols"] == ["000001", "000004", "000006"]
    assert coverage["missing_symbols"] == ["000002", "000003", "000005"]
    assert coverage["symbol_missing_rate_denominator"] == 6
    assert coverage["symbol_missing_rate_numerator"] == 3
    assert coverage["symbol_coverage_ratio"] == 0.5
    assert coverage["symbol_missing_ratio"] == 0.5
    assert coverage["symbol_coverage_rate"] == 0.5
    assert coverage["symbol_missing_rate"] == 0.5


def test_build_coverage_summary_qf_054_empty_request_has_deterministic_missing_rate() -> None:
    request_payload = {"intent": {"asset": "stock", "freq": "day"}}
    preview = [{"code": "000001", "date": "2024-01-02"}]

    coverage = runtime._build_coverage_summary(request_payload, preview)

    assert coverage["requested_symbol_count"] == 0
    assert coverage["requested_symbols"] == []
    assert coverage["observed_symbols"] == ["000001"]
    assert coverage["empty_request_policy"] == runtime.FETCH_RESULT_META_COVERAGE_EMPTY_REQUEST_POLICY
    assert coverage["symbol_missing_rate_denominator"] == 0
    assert coverage["symbol_missing_rate_numerator"] == 0
    assert coverage["symbol_coverage_ratio"] == 1.0
    assert coverage["symbol_missing_ratio"] == 0.0
    assert coverage["symbol_coverage_rate"] == 1.0
    assert coverage["symbol_missing_rate"] == 0.0


def test_write_fetch_evidence_selected_function_falls_back_to_public_function(tmp_path) -> None:
    result = runtime.FetchExecutionResult(
        status=runtime.STATUS_BLOCKED_SOURCE_MISSING,
        reason="not_in_baseline",
        source="fetch",
        source_internal=None,
        engine=None,
        provider_id="fetch",
        provider_internal=None,
        resolved_function=None,
        public_function="fetch_not_in_baseline",
        elapsed_sec=0.0,
        row_count=0,
        columns=[],
        dtypes={},
        preview=[],
        final_kwargs={},
        mode="smoke",
        data=None,
    )

    runtime.write_fetch_evidence(
        request_payload={"function": "fetch_not_in_baseline", "kwargs": {}},
        result=result,
        out_dir=tmp_path,
    )
    meta = json.loads((tmp_path / "fetch_result_meta.json").read_text(encoding="utf-8"))
    assert meta["selected_function"] == "fetch_not_in_baseline"
    assert meta["probe_status"] == runtime.STATUS_BLOCKED_SOURCE_MISSING


def test_write_fetch_evidence_selected_function_prefers_resolved_function(tmp_path) -> None:
    result = runtime.FetchExecutionResult(
        status=runtime.STATUS_PASS_HAS_DATA,
        reason="ok",
        source="fetch",
        source_internal="mysql_fetch",
        engine="mysql",
        provider_id="fetch",
        provider_internal="mysql_fetch",
        resolved_function="fetch_stock_day_runtime_target",
        public_function="fetch_stock_day_public_alias",
        elapsed_sec=0.01,
        row_count=1,
        columns=["code"],
        dtypes={"code": "object"},
        preview=[{"code": "000001"}],
        final_kwargs={"code": "000001"},
        mode="smoke",
        data=[{"code": "000001"}],
    )

    runtime.write_fetch_evidence(
        request_payload={"function": "fetch_stock_day_requested_by_caller", "kwargs": {"code": "000001"}},
        result=result,
        out_dir=tmp_path,
    )
    meta = json.loads((tmp_path / "fetch_result_meta.json").read_text(encoding="utf-8"))
    assert meta["selected_function"] == "fetch_stock_day_runtime_target"


def test_write_fetch_evidence_engine_falls_back_to_source_internal(tmp_path) -> None:
    result = runtime.FetchExecutionResult(
        status=runtime.STATUS_BLOCKED_SOURCE_MISSING,
        reason="not_in_baseline",
        source="fetch",
        source_internal="mysql_fetch",
        engine=None,
        provider_id="fetch",
        provider_internal="mysql_fetch",
        resolved_function=None,
        public_function="fetch_not_in_baseline",
        elapsed_sec=0.0,
        row_count=0,
        columns=[],
        dtypes={},
        preview=[],
        final_kwargs={},
        mode="smoke",
        data=None,
    )

    runtime.write_fetch_evidence(
        request_payload={"function": "fetch_not_in_baseline", "kwargs": {}},
        result=result,
        out_dir=tmp_path,
    )
    meta = json.loads((tmp_path / "fetch_result_meta.json").read_text(encoding="utf-8"))
    assert meta["engine"] == "mysql"


def test_write_fetch_evidence_engine_does_not_use_caller_source_hint(tmp_path) -> None:
    result = runtime.FetchExecutionResult(
        status=runtime.STATUS_BLOCKED_SOURCE_MISSING,
        reason="not_in_baseline",
        source="fetch",
        source_internal=None,
        engine=None,
        provider_id="fetch",
        provider_internal=None,
        resolved_function=None,
        public_function="fetch_not_in_baseline",
        elapsed_sec=0.0,
        row_count=0,
        columns=[],
        dtypes={},
        preview=[],
        final_kwargs={},
        mode="smoke",
        data=None,
    )

    runtime.write_fetch_evidence(
        request_payload={
            "function": "fetch_not_in_baseline",
            "source_hint": "mysql_fetch",
            "intent": {"source_hint": "mongo_fetch"},
            "kwargs": {},
        },
        result=result,
        out_dir=tmp_path,
    )
    meta = json.loads((tmp_path / "fetch_result_meta.json").read_text(encoding="utf-8"))
    assert meta["engine"] is None


def test_write_fetch_evidence_row_col_count_use_normalized_list_table_shape(tmp_path) -> None:
    result = runtime.FetchExecutionResult(
        status=runtime.STATUS_PASS_HAS_DATA,
        reason="ok",
        source="fetch",
        source_internal="mysql_fetch",
        engine="mysql",
        provider_id="fetch",
        provider_internal="mysql_fetch",
        resolved_function="fetch_stock_day",
        public_function="fetch_stock_day",
        elapsed_sec=0.01,
        row_count=999,
        columns=[],
        dtypes={},
        preview=[{"code": "000001", "close": 10.0}],
        final_kwargs={"code": "000001"},
        mode="smoke",
        data=[
            {"code": "000001", "close": 10.0},
            {"code": "000002", "close": 11.0, "volume": 1000},
        ],
    )

    runtime.write_fetch_evidence(
        request_payload={"function": "fetch_stock_day", "kwargs": {"code": ["000001", "000002"]}},
        result=result,
        out_dir=tmp_path,
    )
    meta = json.loads((tmp_path / "fetch_result_meta.json").read_text(encoding="utf-8"))
    assert meta["row_count"] == 2
    assert meta["col_count"] == 3
    assert meta["columns"] == ["code", "close", "volume"]


def test_write_fetch_evidence_multistep_canonical_maps_to_final_step(tmp_path) -> None:
    list_result = runtime.FetchExecutionResult(
        status=runtime.STATUS_PASS_HAS_DATA,
        reason="ok",
        source="fetch",
        source_internal="mysql_fetch",
        engine="mysql",
        provider_id="fetch",
        provider_internal="mysql_fetch",
        resolved_function="fetch_stock_list",
        public_function="fetch_stock_list",
        elapsed_sec=0.01,
        row_count=3,
        columns=["symbol"],
        dtypes={"symbol": "object"},
        preview=[{"symbol": "000001"}, {"symbol": "000002"}, {"symbol": "000003"}],
        final_kwargs={},
        mode="smoke",
        data=[{"symbol": "000001"}, {"symbol": "000002"}, {"symbol": "000003"}],
    )
    sample_result = runtime.FetchExecutionResult(
        status=runtime.STATUS_PASS_HAS_DATA,
        reason="ok",
        source="fetch",
        source_internal="planner",
        engine=None,
        provider_id="fetch",
        provider_internal="planner",
        resolved_function="planner_sample_symbols",
        public_function="planner_sample_symbols",
        elapsed_sec=0.0,
        row_count=2,
        columns=["symbol", "rank"],
        dtypes={"symbol": "object", "rank": "int64"},
        preview=[{"symbol": "000001", "rank": 1}, {"symbol": "000002", "rank": 2}],
        final_kwargs={"sample_n": 2, "sample_method": "stable_first_n"},
        mode="smoke",
        data=[{"symbol": "000001", "rank": 1}, {"symbol": "000002", "rank": 2}],
    )
    day_result = runtime.FetchExecutionResult(
        status=runtime.STATUS_ERROR_RUNTIME,
        reason="RuntimeError: downstream failure",
        source="fetch",
        source_internal="mongo_fetch",
        engine="mongo",
        provider_id="fetch",
        provider_internal="mongo_fetch",
        resolved_function="fetch_stock_day",
        public_function="fetch_stock_day",
        elapsed_sec=0.02,
        row_count=0,
        columns=[],
        dtypes={},
        preview=[],
        final_kwargs={"symbols": ["000001", "000002"]},
        mode="smoke",
        data=None,
    )

    paths = runtime.write_fetch_evidence(
        request_payload={"intent": {"asset": "stock", "freq": "day", "auto_symbols": True}},
        result=day_result,
        out_dir=tmp_path,
        step_records=[
            {
                "step_kind": "list",
                "request_payload": {"function": "fetch_stock_list", "kwargs": {}},
                "result": list_result,
            },
            {
                "step_kind": "sample",
                "request_payload": {"planner_step": "sample", "sample": {"n": 2, "method": "stable_first_n"}},
                "result": sample_result,
            },
            {
                "step_kind": "day",
                "request_payload": {"intent": {"asset": "stock", "freq": "day", "symbols": ["000001", "000002"]}},
                "result": day_result,
            },
        ],
    )

    idx = json.loads((tmp_path / runtime.FETCH_EVIDENCE_STEPS_INDEX_FILENAME).read_text(encoding="utf-8"))
    assert [step["step_kind"] for step in idx["steps"]] == ["list", "sample", "day"]
    assert (tmp_path / _step_filename(runtime.FETCH_EVIDENCE_STEP_REQUEST_FILENAME_TEMPLATE, step_index=1)).is_file()
    assert (tmp_path / _step_filename(runtime.FETCH_EVIDENCE_STEP_REQUEST_FILENAME_TEMPLATE, step_index=2)).is_file()
    assert (tmp_path / _step_filename(runtime.FETCH_EVIDENCE_STEP_REQUEST_FILENAME_TEMPLATE, step_index=3)).is_file()
    assert (tmp_path / _step_filename(runtime.FETCH_EVIDENCE_STEP_ERROR_FILENAME_TEMPLATE, step_index=3)).is_file()

    canonical_req = json.loads((tmp_path / "fetch_request.json").read_text(encoding="utf-8"))
    step3_req = json.loads(
        (tmp_path / _step_filename(runtime.FETCH_EVIDENCE_STEP_REQUEST_FILENAME_TEMPLATE, step_index=3)).read_text(
            encoding="utf-8"
        )
    )
    assert canonical_req == step3_req
    assert "fetch_error_path" in paths
    assert "error_path" in paths
    assert Path(paths["error_path"]).name == runtime.UI_FETCH_EVIDENCE_VIEWER_ERROR_FILENAME
    assert json.loads(Path(paths["error_path"]).read_text(encoding="utf-8")) == json.loads(
        Path(paths["fetch_error_path"]).read_text(encoding="utf-8")
    )
    assert paths["fetch_result_meta_path"] == (tmp_path / "fetch_result_meta.json").as_posix()
    meta = json.loads((tmp_path / "fetch_result_meta.json").read_text(encoding="utf-8"))
    assert meta["selected_function"] == "fetch_stock_day"
    assert meta["probe_status"] == runtime.STATUS_ERROR_RUNTIME
    sanity = meta["sanity_checks"]
    assert sanity["preview_row_count"] == 0
    assert sanity["missing_ratio_by_column"] == {}


def test_write_fetch_evidence_multistep_orders_by_explicit_step_index(tmp_path) -> None:
    list_result = _dummy_result()
    list_result.resolved_function = "fetch_stock_list"
    list_result.public_function = "fetch_stock_list"
    sample_result = _dummy_result()
    sample_result.resolved_function = "planner_sample_symbols"
    sample_result.public_function = "planner_sample_symbols"
    sample_result.source_internal = "planner"
    sample_result.provider_internal = "planner"
    sample_result.engine = None
    day_result = _dummy_result()
    day_result.resolved_function = "fetch_stock_day"
    day_result.public_function = "fetch_stock_day"

    runtime.write_fetch_evidence(
        request_payload={"intent": {"asset": "stock", "freq": "day", "auto_symbols": True}},
        result=day_result,
        out_dir=tmp_path,
        step_records=[
            {
                "step_index": 3,
                "step_kind": "day",
                "request_payload": {"intent": {"asset": "stock", "freq": "day", "symbols": ["000001"]}},
                "result": day_result,
            },
            {
                "step_index": 1,
                "step_kind": "list",
                "request_payload": {"function": "fetch_stock_list", "kwargs": {}},
                "result": list_result,
            },
            {
                "step_index": 2,
                "step_kind": "sample",
                "request_payload": {"planner_step": "sample", "sample": {"n": 1, "method": "stable_first_n"}},
                "result": sample_result,
            },
        ],
    )

    idx = json.loads((tmp_path / runtime.FETCH_EVIDENCE_STEPS_INDEX_FILENAME).read_text(encoding="utf-8"))
    assert [step["step_index"] for step in idx["steps"]] == [1, 2, 3]
    assert [step["step_kind"] for step in idx["steps"]] == ["list", "sample", "day"]
    assert idx["steps"][0]["request_path"].endswith("step_001_fetch_request.json")
    assert idx["steps"][1]["request_path"].endswith("step_002_fetch_request.json")
    assert idx["steps"][2]["request_path"].endswith("step_003_fetch_request.json")

    canonical_req = json.loads((tmp_path / runtime.FETCH_EVIDENCE_REQUEST_FILENAME).read_text(encoding="utf-8"))
    step3_req = json.loads(
        (tmp_path / _step_filename(runtime.FETCH_EVIDENCE_STEP_REQUEST_FILENAME_TEMPLATE, step_index=3)).read_text(
            encoding="utf-8"
        )
    )
    assert canonical_req == step3_req


def test_write_fetch_evidence_multistep_success_emits_qf_064_step_artifacts(tmp_path) -> None:
    list_result = _dummy_result()
    list_result.resolved_function = "fetch_stock_list"
    list_result.public_function = "fetch_stock_list"
    sample_result = _dummy_result()
    sample_result.resolved_function = "planner_sample_symbols"
    sample_result.public_function = "planner_sample_symbols"
    sample_result.source_internal = "planner"
    sample_result.provider_internal = "planner"
    sample_result.engine = None
    day_result = _dummy_result()
    day_result.resolved_function = "fetch_stock_day"
    day_result.public_function = "fetch_stock_day"

    paths = runtime.write_fetch_evidence(
        request_payload={"intent": {"asset": "stock", "freq": "day", "auto_symbols": True}},
        result=day_result,
        out_dir=tmp_path,
        step_records=[
            {
                "step_index": 1,
                "step_kind": "list",
                "request_payload": {"function": "fetch_stock_list", "kwargs": {}},
                "result": list_result,
            },
            {
                "step_index": 2,
                "step_kind": "sample",
                "request_payload": {"planner_step": "sample", "sample": {"n": 1, "method": "stable_first_n"}},
                "result": sample_result,
            },
            {
                "step_index": 3,
                "step_kind": "day",
                "request_payload": {"intent": {"asset": "stock", "freq": "day", "symbols": ["000001"]}},
                "result": day_result,
            },
        ],
    )

    idx = json.loads((tmp_path / runtime.FETCH_EVIDENCE_STEPS_INDEX_FILENAME).read_text(encoding="utf-8"))
    assert [step["step_index"] for step in idx["steps"]] == [1, 2, 3]
    assert all("error_path" not in step for step in idx["steps"])
    assert "fetch_error_path" not in paths
    assert "error_path" not in paths

    for step_index, step in enumerate(idx["steps"], start=1):
        expected_request_path = (
            tmp_path / _step_filename(runtime.FETCH_EVIDENCE_STEP_REQUEST_FILENAME_TEMPLATE, step_index=step_index)
        ).as_posix()
        expected_meta_path = (
            tmp_path / _step_filename(runtime.FETCH_EVIDENCE_STEP_RESULT_META_FILENAME_TEMPLATE, step_index=step_index)
        ).as_posix()
        expected_preview_path = (
            tmp_path / _step_filename(runtime.FETCH_EVIDENCE_STEP_PREVIEW_FILENAME_TEMPLATE, step_index=step_index)
        ).as_posix()
        assert step["request_path"] == expected_request_path
        assert step["result_meta_path"] == expected_meta_path
        assert step["preview_path"] == expected_preview_path

        request_doc = json.loads(Path(step["request_path"]).read_text(encoding="utf-8"))
        assert isinstance(request_doc, dict)
        meta_doc = json.loads(Path(step["result_meta_path"]).read_text(encoding="utf-8"))
        assert isinstance(meta_doc, dict)

        preview_text = Path(step["preview_path"]).read_text(encoding="utf-8")
        assert preview_text.splitlines()[0] == "x"
        assert "1" in preview_text

        step_error_path = tmp_path / _step_filename(runtime.FETCH_EVIDENCE_STEP_ERROR_FILENAME_TEMPLATE, step_index=step_index)
        assert not step_error_path.exists()


def test_write_fetch_evidence_multistep_failure_emits_qf_064_step_error_artifact(tmp_path) -> None:
    list_result = _dummy_result()
    list_result.resolved_function = "fetch_stock_list"
    list_result.public_function = "fetch_stock_list"
    sample_result = _dummy_result()
    sample_result.resolved_function = "planner_sample_symbols"
    sample_result.public_function = "planner_sample_symbols"
    sample_result.source_internal = "planner"
    sample_result.provider_internal = "planner"
    sample_result.engine = None
    day_result = _dummy_result()
    day_result.status = runtime.STATUS_ERROR_RUNTIME
    day_result.reason = "RuntimeError: downstream failure"
    day_result.row_count = 0
    day_result.columns = []
    day_result.preview = []
    day_result.data = None
    day_result.final_kwargs = {"symbols": ["000001"]}
    day_result.resolved_function = "fetch_stock_day"
    day_result.public_function = "fetch_stock_day"

    paths = runtime.write_fetch_evidence(
        request_payload={"intent": {"asset": "stock", "freq": "day", "auto_symbols": True}},
        result=day_result,
        out_dir=tmp_path,
        step_records=[
            {
                "step_index": 1,
                "step_kind": "list",
                "request_payload": {"function": "fetch_stock_list", "kwargs": {}},
                "result": list_result,
            },
            {
                "step_index": 2,
                "step_kind": "sample",
                "request_payload": {"planner_step": "sample", "sample": {"n": 1, "method": "stable_first_n"}},
                "result": sample_result,
            },
            {
                "step_index": 3,
                "step_kind": "day",
                "request_payload": {"intent": {"asset": "stock", "freq": "day", "symbols": ["000001"]}},
                "result": day_result,
            },
        ],
    )

    idx = json.loads((tmp_path / runtime.FETCH_EVIDENCE_STEPS_INDEX_FILENAME).read_text(encoding="utf-8"))
    assert [step["status"] for step in idx["steps"]] == [
        runtime.STATUS_PASS_HAS_DATA,
        runtime.STATUS_PASS_HAS_DATA,
        runtime.STATUS_ERROR_RUNTIME,
    ]
    assert "error_path" not in idx["steps"][0]
    assert "error_path" not in idx["steps"][1]
    assert "error_path" in idx["steps"][2]

    step1_error = tmp_path / _step_filename(runtime.FETCH_EVIDENCE_STEP_ERROR_FILENAME_TEMPLATE, step_index=1)
    step2_error = tmp_path / _step_filename(runtime.FETCH_EVIDENCE_STEP_ERROR_FILENAME_TEMPLATE, step_index=2)
    step3_error = tmp_path / _step_filename(runtime.FETCH_EVIDENCE_STEP_ERROR_FILENAME_TEMPLATE, step_index=3)
    assert not step1_error.exists()
    assert not step2_error.exists()
    assert step3_error.is_file()

    error_doc = json.loads(step3_error.read_text(encoding="utf-8"))
    assert error_doc["status"] == runtime.STATUS_ERROR_RUNTIME
    assert error_doc["reason"] == "RuntimeError: downstream failure"
    assert error_doc["source"] == "fetch"

    assert paths["fetch_error_path"] == (tmp_path / runtime.FETCH_EVIDENCE_ERROR_FILENAME).as_posix()
    assert paths["error_path"] == (tmp_path / runtime.UI_FETCH_EVIDENCE_VIEWER_ERROR_FILENAME).as_posix()


def test_write_fetch_evidence_multistep_rejects_non_contiguous_explicit_step_index(tmp_path) -> None:
    list_result = _dummy_result()
    list_result.resolved_function = "fetch_stock_list"
    list_result.public_function = "fetch_stock_list"
    day_result = _dummy_result()
    day_result.resolved_function = "fetch_stock_day"
    day_result.public_function = "fetch_stock_day"

    with pytest.raises(RuntimeError, match=r"requires explicit contiguous step_index values"):
        runtime.write_fetch_evidence(
            request_payload={"intent": {"asset": "stock", "freq": "day", "auto_symbols": True}},
            result=day_result,
            out_dir=tmp_path,
            step_records=[
                {
                    "step_index": 1,
                    "step_kind": "list",
                    "request_payload": {"function": "fetch_stock_list", "kwargs": {}},
                    "result": list_result,
                },
                {
                    "step_index": 3,
                    "step_kind": "day",
                    "request_payload": {"intent": {"asset": "stock", "freq": "day", "symbols": ["000001"]}},
                    "result": day_result,
                },
            ],
        )


def test_write_fetch_evidence_sanity_checks_detect_non_monotonic_duplicates_and_missing(tmp_path) -> None:
    result = runtime.FetchExecutionResult(
        status=runtime.STATUS_PASS_HAS_DATA,
        reason="ok",
        source="fetch",
        source_internal="mysql_fetch",
        engine="mysql",
        provider_id="fetch",
        provider_internal="mysql_fetch",
        resolved_function="fetch_stock_day",
        public_function="fetch_stock_day",
        elapsed_sec=0.01,
        row_count=3,
        columns=["code", "date", "close", "volume"],
        dtypes={"code": "object", "date": "object", "close": "float64", "volume": "float64"},
        preview=[
            {"code": "000001", "date": "2024-01-03", "close": 10.0, "volume": None},
            {"code": "000001", "date": "2024-01-02", "close": 11.0},
            {"code": "", "date": "2024-01-02", "close": None, "volume": 200.0},
        ],
        final_kwargs={"code": "000001"},
        mode="smoke",
        data=None,
    )

    _ = runtime.write_fetch_evidence(
        request_payload={"intent": {"asset": "stock", "freq": "day"}},
        result=result,
        out_dir=tmp_path,
    )
    meta = json.loads((tmp_path / "fetch_result_meta.json").read_text(encoding="utf-8"))
    sanity = meta["sanity_checks"]
    assert sanity["timestamp_field"] == "date"
    assert sanity["timestamp_order_rule"] == runtime.SANITY_TIMESTAMP_ORDER_RULE
    assert sanity["timestamp_duplicate_policy"] == runtime.SANITY_TIMESTAMP_DUPLICATE_POLICY
    assert sanity["timestamp_monotonic_non_decreasing"] is False
    assert sanity["timestamp_duplicate_count"] == 1
    assert sanity["timestamp_rule_satisfied"] is False
    assert sanity["missing_ratio_rule"] == runtime.SANITY_MISSING_RATIO_RULE
    assert sanity["preview_row_count"] == 3
    assert sanity["missing_ratio_by_column"]["volume"] == pytest.approx(2 / 3, rel=0, abs=1e-6)
    assert sanity["missing_ratio_by_column"]["code"] == pytest.approx(1 / 3, rel=0, abs=1e-6)
    assert sanity["missing_ratio_by_column"]["close"] == pytest.approx(1 / 3, rel=0, abs=1e-6)
    assert sanity["dtype_reasonableness_rule"] == runtime.SANITY_DTYPE_REASONABLENESS_RULE
    assert sanity["dtype_reasonable"] is True
    assert sanity["dtype_mismatch_columns"] == []
    gate = meta["gate_input_summary"]
    integrity = gate["data_snapshot_integrity"]
    assert integrity["preview_row_count"] == 3
    assert integrity["timestamp_field"] == "date"
    assert integrity["timestamp_order_rule"] == runtime.SANITY_TIMESTAMP_ORDER_RULE
    assert integrity["timestamp_duplicate_policy"] == runtime.SANITY_TIMESTAMP_DUPLICATE_POLICY
    assert integrity["timestamp_monotonic_non_decreasing"] is False
    assert integrity["timestamp_duplicate_count"] == 1
    assert integrity["timestamp_rule_satisfied"] is False
    assert integrity["nonzero_missing_ratio_columns"] == ["close", "code", "volume"]
    assert integrity["dtype_reasonable"] is True
    assert integrity["dtype_mismatch_columns"] == []


def test_write_fetch_evidence_sanity_checks_detect_dtype_mismatch(tmp_path) -> None:
    result = runtime.FetchExecutionResult(
        status=runtime.STATUS_PASS_HAS_DATA,
        reason="ok",
        source="fetch",
        source_internal="mysql_fetch",
        engine="mysql",
        provider_id="fetch",
        provider_internal="mysql_fetch",
        resolved_function="fetch_stock_day",
        public_function="fetch_stock_day",
        elapsed_sec=0.01,
        row_count=2,
        columns=["date", "close", "flag", "payload"],
        dtypes={"date": "datetime64[ns]", "close": "float64", "flag": "bool", "payload": "int64"},
        preview=[
            {"date": "2024-01-01", "close": "oops", "flag": "maybe", "payload": {"raw": 1}},
            {"date": "2024-01-02", "close": "10.5", "flag": "1", "payload": {"raw": 2}},
        ],
        final_kwargs={"code": "000001"},
        mode="smoke",
        data=None,
    )

    _ = runtime.write_fetch_evidence(
        request_payload={"intent": {"asset": "stock", "freq": "day"}},
        result=result,
        out_dir=tmp_path,
    )
    meta = json.loads((tmp_path / "fetch_result_meta.json").read_text(encoding="utf-8"))
    sanity = meta["sanity_checks"]
    assert sanity["dtype_reasonableness_rule"] == runtime.SANITY_DTYPE_REASONABLENESS_RULE
    assert sanity["dtype_reasonable"] is False
    assert sanity["dtype_mismatch_columns"] == ["close", "flag", "payload"]
    gate = meta["gate_input_summary"]
    integrity = gate["data_snapshot_integrity"]
    assert integrity["dtype_reasonable"] is False
    assert integrity["dtype_mismatch_columns"] == ["close", "flag", "payload"]


def test_write_fetch_evidence_emits_asof_availability_summary(tmp_path) -> None:
    result = runtime.FetchExecutionResult(
        status=runtime.STATUS_PASS_HAS_DATA,
        reason="ok",
        source="fetch",
        source_internal="mysql_fetch",
        engine="mysql",
        provider_id="fetch",
        provider_internal="mysql_fetch",
        resolved_function="fetch_stock_day",
        public_function="fetch_stock_day",
        elapsed_sec=0.01,
        row_count=3,
        columns=["code", "date", "available_at", "close"],
        dtypes={"code": "object", "date": "object", "available_at": "object", "close": "float64"},
        preview=[
            {"code": "000001", "date": "2024-01-01", "available_at": "2024-01-01T16:00:00+08:00", "close": 10.0},
            {"code": "000001", "date": "2024-01-02", "available_at": "2024-01-02T16:00:00+08:00", "close": 11.0},
            {"code": "000001", "date": "2024-01-03", "available_at": "2024-01-03T16:00:00+08:00", "close": 12.0},
        ],
        final_kwargs={"code": "000001"},
        mode="smoke",
        data=None,
    )

    _ = runtime.write_fetch_evidence(
        request_payload={
            "intent": {"asset": "stock", "freq": "day"},
            "as_of": "2024-01-02T23:59:59+08:00",
        },
        result=result,
        out_dir=tmp_path,
    )
    meta = json.loads((tmp_path / "fetch_result_meta.json").read_text(encoding="utf-8"))
    assert meta["as_of"] == "2024-01-02T15:59:59Z"
    av = meta["availability_summary"]
    assert av["rule"] == runtime.TIME_TRAVEL_AVAILABILITY_RULE
    assert av["has_as_of"] is True
    assert av["as_of"] == "2024-01-02T15:59:59Z"
    assert av["available_at_field_present"] is True
    assert av["available_at_min"] == "2024-01-01T08:00:00Z"
    assert av["available_at_max"] == "2024-01-03T08:00:00Z"
    assert av["available_at_violation_count"] == 1
    gate = meta["gate_input_summary"]
    assert gate["no_lookahead"]["rule"] == runtime.TIME_TRAVEL_AVAILABILITY_RULE
    assert gate["no_lookahead"]["has_as_of"] is True
    assert gate["no_lookahead"]["available_at_field_present"] is True
    assert gate["no_lookahead"]["available_at_violation_count"] == 1
    integrity = gate["data_snapshot_integrity"]
    assert integrity["request_hash"] == meta["request_hash"]
    assert integrity["preview_row_count"] == 3
    assert integrity["timestamp_field"] == "date"
    assert integrity["timestamp_monotonic_non_decreasing"] is True
    assert integrity["timestamp_duplicate_count"] == 0
    assert integrity["nonzero_missing_ratio_columns"] == []


def test_write_fetch_evidence_availability_summary_defaults_without_asof_or_available_at(tmp_path) -> None:
    result = runtime.FetchExecutionResult(
        status=runtime.STATUS_PASS_HAS_DATA,
        reason="ok",
        source="fetch",
        source_internal="mysql_fetch",
        engine="mysql",
        provider_id="fetch",
        provider_internal="mysql_fetch",
        resolved_function="fetch_stock_day",
        public_function="fetch_stock_day",
        elapsed_sec=0.01,
        row_count=1,
        columns=["code", "date", "close"],
        dtypes={"code": "object", "date": "object", "close": "float64"},
        preview=[{"code": "000001", "date": "2024-01-01", "close": 10.0}],
        final_kwargs={"code": "000001"},
        mode="smoke",
        data=None,
    )

    _ = runtime.write_fetch_evidence(
        request_payload={"intent": {"asset": "stock", "freq": "day"}},
        result=result,
        out_dir=tmp_path,
    )
    meta = json.loads((tmp_path / "fetch_result_meta.json").read_text(encoding="utf-8"))
    assert meta["as_of"] is None
    av = meta["availability_summary"]
    assert av["has_as_of"] is False
    assert av["as_of"] is None
    assert av["available_at_field_present"] is False
    assert av["available_at_min"] is None
    assert av["available_at_max"] is None
    assert av["available_at_violation_count"] == 0
    gate = meta["gate_input_summary"]
    assert gate["no_lookahead"]["rule"] == runtime.TIME_TRAVEL_AVAILABILITY_RULE
    assert gate["no_lookahead"]["has_as_of"] is False
    assert gate["no_lookahead"]["available_at_field_present"] is False
    assert gate["no_lookahead"]["available_at_violation_count"] == 0
    integrity = gate["data_snapshot_integrity"]
    assert integrity["request_hash"] == meta["request_hash"]
    assert integrity["preview_row_count"] == 1
    assert integrity["timestamp_field"] == "date"
    assert integrity["timestamp_monotonic_non_decreasing"] is True
    assert integrity["timestamp_duplicate_count"] == 0
    assert integrity["nonzero_missing_ratio_columns"] == []


def test_runtime_qf_106_regression_bundle_sanity_time_travel_gate_summary(tmp_path) -> None:
    result = runtime.FetchExecutionResult(
        status=runtime.STATUS_PASS_HAS_DATA,
        reason="ok",
        source="fetch",
        source_internal="mysql_fetch",
        engine="mysql",
        provider_id="fetch",
        provider_internal="mysql_fetch",
        resolved_function="fetch_stock_day",
        public_function="fetch_stock_day",
        elapsed_sec=0.02,
        row_count=2,
        columns=["code", "date", "available_at", "close", "note"],
        dtypes={"code": "object", "date": "int64", "available_at": "object", "close": "int64", "note": "object"},
        preview=[
            {
                "code": "000001",
                "date": "2024-01-02",
                "available_at": "2024-01-03T00:00:00+08:00",
                "close": "bad",
                "note": "future",
            },
            {
                "code": "000001",
                "date": "2024-01-01",
                "available_at": "2024-01-01T00:00:00+08:00",
                "close": 10,
            },
        ],
        final_kwargs={"code": "000001"},
        mode="smoke",
        data=[
            {
                "code": "000001",
                "date": "2024-01-02",
                "available_at": "2024-01-03T00:00:00+08:00",
                "close": "bad",
                "note": "future",
            },
            {
                "code": "000001",
                "date": "2024-01-01",
                "available_at": "2024-01-01T00:00:00+08:00",
                "close": 10,
            },
        ],
    )

    _ = runtime.write_fetch_evidence(
        request_payload={
            "intent": {"asset": "stock", "freq": "day"},
            "as_of": "2024-01-02T23:59:59+08:00",
        },
        result=result,
        out_dir=tmp_path,
    )
    meta = json.loads((tmp_path / "fetch_result_meta.json").read_text(encoding="utf-8"))

    assert meta["as_of"] == "2024-01-02T15:59:59Z"
    av = meta["availability_summary"]
    assert av["available_at_field_present"] is True
    assert av["available_at_min"] == "2023-12-31T16:00:00Z"
    assert av["available_at_max"] == "2024-01-02T16:00:00Z"
    assert av["available_at_violation_count"] == 1

    sanity = meta["sanity_checks"]
    assert sanity["timestamp_field"] == "date"
    assert sanity["timestamp_monotonic_non_decreasing"] is False
    assert sanity["timestamp_duplicate_count"] == 0
    assert sanity["timestamp_rule_satisfied"] is False
    assert sanity["missing_ratio_by_column"]["note"] == 0.5
    assert sanity["dtype_reasonable"] is False
    assert sanity["dtype_mismatch_columns"] == ["close", "date"]

    gate = meta["gate_input_summary"]
    assert gate["no_lookahead"]["available_at_violation_count"] == 1
    integrity = gate["data_snapshot_integrity"]
    assert integrity["timestamp_rule_satisfied"] is False
    assert integrity["nonzero_missing_ratio_columns"] == ["note"]
    assert integrity["dtype_mismatch_columns"] == ["close", "date"]


def test_evaluate_fetch_evidence_snapshot_manifest_gate_passes_with_all_artifacts(tmp_path) -> None:
    evidence_dir = tmp_path / "fetch_evidence"
    paths = runtime.write_fetch_evidence(
        request_payload={"intent": {"asset": "stock", "freq": "day"}},
        result=_dummy_result(),
        out_dir=evidence_dir,
    )
    snapshot_manifest_path = tmp_path / "data_lake" / "snapshot_001" / "manifest.json"
    snapshot_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_manifest_path.write_text('{"schema_version":"data_snapshot_manifest_v1"}\n', encoding="utf-8")

    verdict = runtime.evaluate_fetch_evidence_snapshot_manifest_gate(
        fetch_evidence_paths=paths,
        snapshot_manifest_path=snapshot_manifest_path,
        run_id="run_gate_pass_001",
    )

    assert verdict["rule"] == runtime.FETCH_EVIDENCE_SNAPSHOT_MANIFEST_GATE_FAIL_RULE
    assert verdict["gate_status"] == "pass"
    assert verdict["gate_pass"] is True
    assert verdict["run_id"] == "run_gate_pass_001"
    assert verdict["missing_fetch_evidence"] == []
    assert verdict["snapshot_manifest_present"] is True
    assert verdict["failure_reasons"] == []
    assert verdict["status_message"] == "fetch evidence + snapshot manifest gate pass"


@pytest.mark.parametrize(
    ("missing_evidence", "create_manifest", "expected_failure_reasons"),
    [
        (True, True, ["missing_fetch_evidence:fetch_steps_index_path"]),
        (False, False, ["missing_snapshot_manifest"]),
        (True, False, ["missing_fetch_evidence:fetch_steps_index_path", "missing_snapshot_manifest"]),
    ],
)
def test_enforce_fetch_evidence_snapshot_manifest_gate_fails_for_missing_artifacts(
    tmp_path,
    missing_evidence: bool,
    create_manifest: bool,
    expected_failure_reasons: list[str],
) -> None:
    evidence_dir = tmp_path / "fetch_evidence"
    paths = runtime.write_fetch_evidence(
        request_payload={"intent": {"asset": "stock", "freq": "day"}},
        result=_dummy_result(),
        out_dir=evidence_dir,
    )
    candidate_paths = dict(paths)
    if missing_evidence:
        candidate_paths["fetch_steps_index_path"] = (tmp_path / "missing_steps_index.json").as_posix()
    snapshot_manifest_path = tmp_path / "data_lake" / "snapshot_001" / "manifest.json"
    if create_manifest:
        snapshot_manifest_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_manifest_path.write_text('{"schema_version":"data_snapshot_manifest_v1"}\n', encoding="utf-8")

    verdict = runtime.evaluate_fetch_evidence_snapshot_manifest_gate(
        fetch_evidence_paths=candidate_paths,
        snapshot_manifest_path=snapshot_manifest_path,
        run_id="run_gate_fail_001",
    )
    assert verdict["gate_status"] == "fail"
    assert verdict["gate_pass"] is False
    assert verdict["run_id"] == "run_gate_fail_001"
    assert verdict["missing_fetch_evidence"] == (["fetch_steps_index_path"] if missing_evidence else [])
    assert verdict["snapshot_manifest_present"] is create_manifest
    assert verdict["failure_reasons"] == expected_failure_reasons
    assert verdict["status_message"].startswith("run gate fail: run_id=run_gate_fail_001 missing=")

    with pytest.raises(
        ValueError,
        match=r"run must gate fail when fetch evidence / snapshot manifest is missing; run_id=run_gate_fail_001; violations=",
    ):
        runtime.enforce_fetch_evidence_snapshot_manifest_gate(
            fetch_evidence_paths=candidate_paths,
            snapshot_manifest_path=snapshot_manifest_path,
            run_id="run_gate_fail_001",
        )


def _golden_query_result(
    *,
    status: str,
    row_count: int,
    columns: list[str],
    data: list[dict[str, Any]] | None,
) -> runtime.FetchExecutionResult:
    return runtime.FetchExecutionResult(
        status=status,
        reason="ok" if status != runtime.STATUS_ERROR_RUNTIME else "error",
        source="fetch",
        source_internal="mysql_fetch",
        engine="mysql",
        provider_id="fetch",
        provider_internal="mysql_fetch",
        resolved_function="fetch_demo",
        public_function="fetch_demo",
        elapsed_sec=0.01,
        row_count=row_count,
        columns=list(columns),
        dtypes={col: "object" for col in columns},
        preview=list(data or []),
        final_kwargs={},
        mode="smoke",
        data=list(data or []),
    )


def test_build_golden_query_execution_summary_passes_fixed_query_set_expected_outputs() -> None:
    stock_request = {
        "intent": {"asset": "stock", "freq": "day"},
        "symbols": ["000001"],
        "start": "2024-01-01",
        "end": "2024-01-31",
    }
    index_request = {
        "function": "fetch_index_day",
        "kwargs": {"code": "000300", "start": "2024-01-01", "end": "2024-01-31"},
        "policy": {"mode": "smoke"},
    }

    def _fake_execute_by_intent(request_payload: dict[str, Any], **_kwargs: Any) -> runtime.FetchExecutionResult:
        assert request_payload["intent"]["asset"] == "stock"
        return _golden_query_result(
            status=runtime.STATUS_PASS_HAS_DATA,
            row_count=2,
            columns=["code", "close"],
            data=[{"code": "000001", "close": 10.0}, {"code": "000001", "close": 11.0}],
        )

    def _fake_execute_by_name(**kwargs: Any) -> runtime.FetchExecutionResult:
        assert kwargs["function"] == "fetch_index_day"
        return _golden_query_result(
            status=runtime.STATUS_PASS_EMPTY,
            row_count=0,
            columns=[],
            data=[],
        )

    summary = runtime.build_golden_query_execution_summary(
        golden_queries=[
            {
                "query_id": "q_stock_day",
                "request": stock_request,
                "expected_output": {
                    "status": runtime.STATUS_PASS_HAS_DATA,
                    "row_count": 2,
                    "columns": ["close", "code"],
                },
            },
            {
                "query_id": "q_index_day",
                "request": index_request,
                "expected_output": {
                    "status": runtime.STATUS_PASS_EMPTY,
                    "row_count": 0,
                    "columns": [],
                },
            },
        ],
        execute_by_intent=_fake_execute_by_intent,
        execute_by_name=_fake_execute_by_name,
    )

    assert summary["schema_version"] == runtime.GOLDEN_QUERY_SUMMARY_SCHEMA_VERSION
    assert summary["rule"] == runtime.GOLDEN_QUERY_FIXED_SET_RULE
    assert summary["requirement_id"] == "QF-086"
    assert summary["query_ids"] == ["q_index_day", "q_stock_day"]
    assert summary["fixed_request_output_requirement_id"] == "QF-087"
    assert summary["fixed_request_output_clause"] == "固定请求 → 产出 meta/hash/row_count/columns"
    assert summary["fixed_request_artifact_fields"] == list(runtime.GOLDEN_QUERY_FIXED_REQUEST_ARTIFACT_FIELDS)
    assert summary["regression_status"] == "no_regression"
    assert summary["regression_detected"] is False
    assert summary["regression_query_ids"] == []
    stock_artifact = summary["fixed_request_artifacts"]["q_stock_day"]
    assert set(stock_artifact.keys()) == set(runtime.GOLDEN_QUERY_FIXED_REQUEST_ARTIFACT_FIELDS)
    assert stock_artifact["request_hash"] == runtime._canonical_request_hash(stock_request)
    assert stock_artifact["row_count"] == 2
    assert stock_artifact["columns"] == ["close", "code"]
    assert stock_artifact["meta"]["request_hash"] == stock_artifact["request_hash"]
    assert stock_artifact["meta"]["row_count"] == 2
    assert stock_artifact["meta"]["columns"] == ["close", "code"]
    index_artifact = summary["fixed_request_artifacts"]["q_index_day"]
    assert index_artifact["request_hash"] == runtime._canonical_request_hash(index_request)
    assert index_artifact["row_count"] == 0
    assert index_artifact["columns"] == []
    assert index_artifact["meta"]["request_hash"] == index_artifact["request_hash"]
    assert index_artifact["meta"]["row_count"] == 0
    assert index_artifact["meta"]["columns"] == []
    assert all(report["regression_status"] == "no_regression" for report in summary["query_reports"])
    assert all(
        set(report["fixed_request_artifact"].keys()) == set(runtime.GOLDEN_QUERY_FIXED_REQUEST_ARTIFACT_FIELDS)
        for report in summary["query_reports"]
    )
    comparison = runtime.build_golden_query_drift_report(baseline_summary=summary, current_summary=summary)
    assert comparison["drift_detected"] is False
    assert comparison["regression_detected"] is False
    assert comparison["overall_status"] == "pass"


def test_build_golden_query_execution_summary_fixed_request_hash_is_deterministic_for_equivalent_requests() -> None:
    request_a = {
        "intent": {"asset": "stock", "freq": "day"},
        "symbols": ["000001"],
        "start": "2024-01-01",
        "end": "2024-01-31",
    }
    request_b = {
        "end": "2024-01-31",
        "start": "2024-01-01",
        "symbols": ["000001"],
        "intent": {"freq": "day", "asset": "stock"},
    }

    def _fake_execute_by_intent(_request_payload: dict[str, Any], **_kwargs: Any) -> runtime.FetchExecutionResult:
        return _golden_query_result(
            status=runtime.STATUS_PASS_EMPTY,
            row_count=0,
            columns=[],
            data=[],
        )

    summary = runtime.build_golden_query_execution_summary(
        golden_queries=[
            {
                "query_id": "q_a",
                "request": request_a,
                "expected_output": {
                    "status": runtime.STATUS_PASS_EMPTY,
                    "row_count": 0,
                    "columns": [],
                },
            },
            {
                "query_id": "q_b",
                "request": request_b,
                "expected_output": {
                    "status": runtime.STATUS_PASS_EMPTY,
                    "row_count": 0,
                    "columns": [],
                },
            },
        ],
        execute_by_intent=_fake_execute_by_intent,
    )

    hash_a = summary["fixed_request_artifacts"]["q_a"]["request_hash"]
    hash_b = summary["fixed_request_artifacts"]["q_b"]["request_hash"]
    assert hash_a == hash_b
    assert hash_a == runtime._canonical_request_hash(request_a)
    assert hash_b == runtime._canonical_request_hash(request_b)


def test_build_golden_query_execution_summary_orchestrator_regression_requires_host_terminal_environment() -> None:
    request = {
        "intent": {"asset": "stock", "freq": "day"},
        "symbols": ["000001"],
        "start": "2024-01-01",
        "end": "2024-01-31",
    }

    def _fake_execute_by_intent(request_payload: dict[str, Any], **_kwargs: Any) -> runtime.FetchExecutionResult:
        return _golden_query_result(
            status=runtime.STATUS_PASS_EMPTY,
            row_count=0,
            columns=[],
            data=[],
        )

    summary = runtime.build_golden_query_execution_summary(
        golden_queries=[
            {
                "query_id": "q_host_contract",
                "request": request,
                "expected_output": {
                    "status": runtime.STATUS_PASS_EMPTY,
                    "row_count": 0,
                    "columns": [],
                },
            },
        ],
        execute_by_intent=_fake_execute_by_intent,
        execution_environment=runtime.FETCHDATA_IMPL_ORCHESTRATOR_CONTRACTS_REGRESSION_EXECUTION_ENV,
    )

    assert summary["regression_status"] == "no_regression"
    assert summary["query_ids"] == ["q_host_contract"]


def test_build_golden_query_execution_summary_rejects_notebook_environment_for_contract_regressions() -> None:
    request = {
        "intent": {"asset": "stock", "freq": "day"},
        "symbols": ["000001"],
        "start": "2024-01-01",
        "end": "2024-01-31",
    }

    with pytest.raises(
        ValueError,
        match=r"contracts/orchestrator regression execution environment must be host_terminal|notebook-kernel parity is intentionally not part of contract baseline",
    ):
        runtime.build_golden_query_execution_summary(
            golden_queries=[
                {
                    "query_id": "q_notebook_contract",
                    "request": request,
                    "expected_output": {
                        "status": runtime.STATUS_PASS_EMPTY,
                        "row_count": 0,
                        "columns": [],
                    },
                },
            ],
            execution_environment="notebook_kernel",
        )


def test_build_golden_query_drift_report_detects_regression_without_hash_drift() -> None:
    report = runtime.build_golden_query_drift_report(
        baseline_summary={
            "schema_version": "qa_fetch_golden_summary_v1",
            "query_hashes": {"q_stock_day": "hash_stable"},
            "query_outputs": {
                "q_stock_day": {
                    "status": runtime.STATUS_PASS_HAS_DATA,
                    "request_hash": "a" * 64,
                    "row_count": 2,
                    "columns": ["close", "code"],
                }
            },
        },
        current_summary={
            "schema_version": "qa_fetch_golden_summary_v1",
            "query_hashes": {"q_stock_day": "hash_stable"},
            "query_outputs": {
                "q_stock_day": {
                    "status": runtime.STATUS_PASS_HAS_DATA,
                    "request_hash": "a" * 64,
                    "row_count": 1,
                    "columns": ["close", "code"],
                }
            },
        },
    )

    assert report["drift_detected"] is False
    assert report["regression_detected"] is True
    assert report["regression_status"] == "regression_detected"
    assert report["regression_query_ids"] == ["q_stock_day"]
    assert report["overall_status"] == "fail"


def test_build_golden_query_drift_report_detects_drift_without_regression_payloads() -> None:
    report = runtime.build_golden_query_drift_report(
        baseline_summary={
            "schema_version": "qa_fetch_golden_summary_v1",
            "query_hashes": {"q_stock_day": "hash_old"},
        },
        current_summary={
            "schema_version": "qa_fetch_golden_summary_v1",
            "query_hashes": {"q_index_day": "hash_new"},
        },
    )

    assert report["correctness_requirement_id"] == "QF-086"
    assert report["drift_detected"] is True
    assert report["regression_detected"] is False
    assert report["regression_query_ids"] == []
    assert report["overall_status"] == "fail"


def test_build_golden_query_drift_report_detects_added_removed_and_changed_queries() -> None:
    report = runtime.build_golden_query_drift_report(
        baseline_summary={
            "schema_version": "qa_fetch_golden_summary_v1",
            "query_hashes": {
                "q_removed": "hash_old_1",
                "q_changed": "hash_old_2",
                "q_same": "hash_same",
            },
        },
        current_summary={
            "schema_version": "qa_fetch_golden_summary_v1",
            "query_hashes": {
                "q_changed": "hash_new_2",
                "q_same": "hash_same",
                "q_added": "hash_new_3",
            },
        },
    )

    assert report["schema_version"] == runtime.GOLDEN_QUERY_DRIFT_REPORT_SCHEMA_VERSION
    assert report["rule"] == runtime.GOLDEN_QUERY_DRIFT_REPORT_PATH_RULE
    assert report["requirement_id"] == "QF-088"
    assert report["source_document"] == "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
    assert report["clause"] == "漂移必须产出报告（报告文件位置由主控定义，但必须可被 CI 或 nightly 读取）"
    assert report["minimum_set_rule"] == runtime.FETCHDATA_IMPL_GOLDEN_QUERIES_MIN_SET_RULE
    assert report["minimum_set_min_queries"] == runtime.GOLDEN_QUERY_MIN_SET_MIN_QUERIES
    assert report["drift_status"] == "drift_detected"
    assert report["drift_detected"] is True
    assert report["regression_status"] == "no_regression"
    assert report["regression_detected"] is False
    assert report["overall_status"] == "fail"
    assert report["baseline_query_count"] == 3
    assert report["current_query_count"] == 3
    assert report["added_query_ids"] == ["q_added"]
    assert report["removed_query_ids"] == ["q_removed"]
    assert report["changed_query_ids"] == ["q_changed"]
    assert report["changed_query_hashes"] == [
        {
            "query_id": "q_changed",
            "baseline_hash": "hash_old_2",
            "current_hash": "hash_new_2",
        }
    ]


def test_build_golden_query_drift_report_detects_drift_and_regression_simultaneously() -> None:
    report = runtime.build_golden_query_drift_report(
        baseline_summary={
            "schema_version": "qa_fetch_golden_summary_v1",
            "query_hashes": {
                "q_keep": "hash_keep",
                "q_removed": "hash_removed",
            },
            "query_outputs": {
                "q_keep": {
                    "status": runtime.STATUS_PASS_HAS_DATA,
                    "request_hash": "a" * 64,
                    "row_count": 2,
                    "columns": ["close", "code"],
                },
            },
        },
        current_summary={
            "schema_version": "qa_fetch_golden_summary_v1",
            "query_hashes": {
                "q_keep": "hash_keep",
                "q_added": "hash_added",
            },
            "query_outputs": {
                "q_keep": {
                    "status": runtime.STATUS_PASS_EMPTY,
                    "request_hash": "a" * 64,
                    "row_count": 0,
                    "columns": ["close", "code"],
                },
            },
        },
    )

    assert report["drift_detected"] is True
    assert report["regression_detected"] is True
    assert report["drift_status"] == "drift_detected"
    assert report["regression_status"] == "regression_detected"
    assert report["overall_status"] == "fail"
    assert report["added_query_ids"] == ["q_added"]
    assert report["removed_query_ids"] == ["q_removed"]
    assert report["regression_query_ids"] == ["q_keep"]


def test_write_golden_query_drift_report_writes_controller_defined_path_for_ci_or_nightly(tmp_path) -> None:
    baseline_summary_path = tmp_path / "baseline" / "golden_summary.json"
    current_summary_path = tmp_path / "current" / "golden_summary.json"
    report_out_path = tmp_path / "ci" / "nightly" / "qa_fetch" / "golden_drift_report.json"

    baseline_summary_path.parent.mkdir(parents=True, exist_ok=True)
    current_summary_path.parent.mkdir(parents=True, exist_ok=True)
    _write_golden_summary_payload(
        baseline_summary_path,
        query_hashes={
            "q_stock_day": "hash_v1",
            "q_index_day": "hash_stable",
        },
    )
    _write_golden_summary_payload(
        current_summary_path,
        query_hashes={
            "q_stock_day": "hash_v2",
            "q_index_day": "hash_stable",
            "q_etf_day": "hash_new",
        },
    )

    report = runtime.write_golden_query_drift_report(
        baseline_summary_path=baseline_summary_path,
        current_summary_path=current_summary_path,
        report_out_path=report_out_path,
    )

    assert report_out_path.is_file()
    persisted = json.loads(report_out_path.read_text(encoding="utf-8"))
    assert persisted["schema_version"] == runtime.GOLDEN_QUERY_DRIFT_REPORT_SCHEMA_VERSION
    assert persisted["rule"] == runtime.GOLDEN_QUERY_DRIFT_REPORT_PATH_RULE
    assert persisted["requirement_id"] == "QF-088"
    assert persisted["drift_status"] == "drift_detected"
    assert persisted["drift_detected"] is True
    assert persisted["baseline_summary_path"] == baseline_summary_path.as_posix()
    assert persisted["current_summary_path"] == current_summary_path.as_posix()
    assert persisted["report_path"] == report_out_path.as_posix()
    assert persisted["added_query_ids"] == ["q_etf_day"]
    assert persisted["removed_query_ids"] == []
    assert persisted["changed_query_ids"] == ["q_stock_day"]
    assert "generated_at" in persisted
    assert report == persisted


def test_build_golden_query_drift_report_rejects_empty_minimal_query_set() -> None:
    with pytest.raises(ValueError, match=r"baseline_summary.query_hashes must contain at least 1 query"):
        runtime.build_golden_query_drift_report(
            baseline_summary={
                "schema_version": "qa_fetch_golden_summary_v1",
                "query_hashes": {},
            },
            current_summary={
                "schema_version": "qa_fetch_golden_summary_v1",
                "query_hashes": {"q_stock_day": "hash_v1"},
            },
        )


def test_build_golden_query_drift_report_rejects_total_queries_mismatch() -> None:
    with pytest.raises(ValueError, match=r"baseline_summary.total_queries mismatch: expected 1, got 2"):
        runtime.build_golden_query_drift_report(
            baseline_summary={
                "schema_version": "qa_fetch_golden_summary_v1",
                "total_queries": 2,
                "query_hashes": {"q_stock_day": "hash_v1"},
            },
            current_summary={
                "schema_version": "qa_fetch_golden_summary_v1",
                "total_queries": 1,
                "query_hashes": {"q_stock_day": "hash_v1"},
            },
        )


def test_execute_fetch_by_intent_rejects_non_mapping_payload_before_fetch_resolution() -> None:
    called: dict[str, bool] = {}

    def _fake_resolve_fetch(*_args, **_kwargs) -> None:
        called["resolve_fetch"] = True
        raise AssertionError("resolve_fetch should not be called for invalid fetch_request payload")

    original_resolve_fetch = runtime.resolve_fetch
    runtime.resolve_fetch = _fake_resolve_fetch
    try:
        with pytest.raises(ValueError, match=r"intent must be FetchIntent or dict"):
            runtime.execute_fetch_by_intent("bad")
    finally:
        runtime.resolve_fetch = original_resolve_fetch

    assert "resolve_fetch" not in called


def test_execute_fetch_by_intent_rejects_invalid_fetch_result_meta_before_return() -> None:
    if runtime._contracts_validate is None:
        pytest.skip("contracts schema validator unavailable")

    original_validate = runtime._contracts_validate.validate_fetch_result_meta
    original_execute_fetch_by_name = runtime.execute_fetch_by_name

    def _fake_validate_fetch_result_meta(_payload):
        return runtime._contracts_validate.EXIT_INVALID, "contract violation"

    def _fake_execute_fetch_by_name(**_kwargs):
        return runtime.FetchExecutionResult(
            status=runtime.STATUS_PASS_HAS_DATA,
            reason="ok",
            source="fetch",
            source_internal="mongo_fetch",
            engine="mongo",
            provider_id="fetch",
            provider_internal="mongo_fetch",
            resolved_function="fetch_stock_day",
            public_function="fetch_stock_day",
            elapsed_sec=0.01,
            row_count=1,
            columns=["code"],
            dtypes={"code": "object"},
            preview=[],
            final_kwargs={"symbol": "000001"},
            mode="smoke",
            data=None,
        )

    runtime._contracts_validate.validate_fetch_result_meta = _fake_validate_fetch_result_meta
    runtime.execute_fetch_by_name = _fake_execute_fetch_by_name
    try:
        with pytest.raises(
            ValueError, match=r"fetch_result_meta validation failed before orchestration"
        ):
            runtime.execute_fetch_by_intent(
                {
                    "function": "fetch_stock_day",
                    "strong_control_function": True,
                    "kwargs": {
                        "symbol": "000001",
                        "start": "2024-01-01",
                        "end": "2024-01-02",
                    },
                }
            )
    finally:
        runtime._contracts_validate.validate_fetch_result_meta = original_validate
        runtime.execute_fetch_by_name = original_execute_fetch_by_name
