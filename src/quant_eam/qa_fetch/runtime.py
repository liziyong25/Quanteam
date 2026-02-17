from __future__ import annotations

import hashlib
import inspect
import json
import os
import random
import signal
import shutil
import sys
import time
from dataclasses import asdict, dataclass, field, replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .resolver import resolve_fetch
from .mongo_bridge import resolve_mongo_fetch_callable
from .mysql_bridge import resolve_mysql_fetch_callable
from .source import is_mongo_source, is_mysql_source, normalize_source

try:
    from quant_eam.contracts import validate as _contracts_validate
except Exception:  # pragma: no cover
    _contracts_validate = None

# Keep contract validation stable when tests/runtime temporarily change cwd.
os.environ.setdefault("EAM_REPO", Path(__file__).resolve().parents[3].as_posix())


STATUS_PASS_HAS_DATA = "pass_has_data"
STATUS_PASS_EMPTY = "pass_empty"
STATUS_BLOCKED_SOURCE_MISSING = "blocked_source_missing"
STATUS_ERROR_RUNTIME = "error_runtime"

DEFAULT_WINDOW_PROFILE_PATH = Path("docs/05_data_plane/qa_fetch_smoke_window_profile_v1.json")
DEFAULT_EXCEPTION_DECISIONS_PATH = Path("docs/05_data_plane/qa_fetch_exception_decisions_v1.md")
DEFAULT_FUNCTION_REGISTRY_PATH = Path("docs/05_data_plane/qa_fetch_function_registry_v1.json")
DEFAULT_ROUTING_REGISTRY_PATH = Path("docs/05_data_plane/qa_fetch_registry_v1.json")
DEFAULT_PROBE_SUMMARY_PATH = Path("docs/05_data_plane/qa_fetch_probe_v3/probe_summary_v3_notebook_params.json")
DEFAULT_UI_LLM_EVIDENCE_ROOT = Path("artifacts/qa_fetch/ui_llm_query_evidence")
DEFAULT_RUNTIME_FETCH_EVIDENCE_ROOT = Path("artifacts/qa_fetch/runtime_fetch_evidence")
DEFAULT_DOSSIER_ROOT = Path("artifacts/dossiers")
DOSSIER_FETCH_SUBDIR_NAME = "fetch"
# QF-001 top-level clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:1
FETCHDATA_IMPL_SPEC_REQUIREMENT_ID = "QF-001"
FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT = "docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md"
FETCHDATA_IMPL_SPEC_CLAUSE = "QA-Fetch FetchData Implementation Spec (v1)"
# QF-002 purpose/positioning clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:7
FETCHDATA_IMPL_PURPOSE_REQUIREMENT_ID = "QF-002"
FETCHDATA_IMPL_PURPOSE_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_PURPOSE_CLAUSE = "QA-Fetch FetchData Implementation Spec (v1) / 0. 目的与定位"
# QF-003 purpose objective clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:8
FETCHDATA_IMPL_PURPOSE_OBJECTIVE_REQUIREMENT_ID = "QF-003"
FETCHDATA_IMPL_PURPOSE_OBJECTIVE_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_PURPOSE_OBJECTIVE_CLAUSE = "QA-Fetch FetchData Implementation Spec (v1) / 0. 目的与定位 / 0.1 目的"
# QF-004 purpose positioning/system-boundary clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:13
FETCHDATA_IMPL_PURPOSE_POSITIONING_REQUIREMENT_ID = "QF-004"
FETCHDATA_IMPL_PURPOSE_POSITIONING_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_PURPOSE_POSITIONING_CLAUSE = "QA-Fetch FetchData Implementation Spec (v1) / 0. 目的与定位 / 0.2 定位（系统边界）"
# QF-005 fetch_request intent-priority clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:15
FETCHDATA_IMPL_FETCH_REQUEST_INTENT_PRIORITY_REQUIREMENT_ID = "QF-005"
FETCHDATA_IMPL_FETCH_REQUEST_INTENT_PRIORITY_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_FETCH_REQUEST_INTENT_PRIORITY_CLAUSE = "接受来自主链路的 `fetch_request`（intent 优先）；"
# QF-006 unified runtime execution clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:16
FETCHDATA_IMPL_RUNTIME_UNIFIED_EXECUTION_REQUIREMENT_ID = "QF-006"
FETCHDATA_IMPL_RUNTIME_UNIFIED_EXECUTION_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_RUNTIME_UNIFIED_EXECUTION_CLAUSE = "通过统一 runtime 解析/执行 fetch；"
# QF-007 forced evidence persistence clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:17
FETCHDATA_IMPL_FORCED_EVIDENCE_REQUIREMENT_ID = "QF-007"
FETCHDATA_IMPL_FORCED_EVIDENCE_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_FORCED_EVIDENCE_CLAUSE = "为每次取数强制落盘证据；"
# QF-008 datacatalog/time-travel/gates audit-input clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:18
FETCHDATA_IMPL_DATACATALOG_TIME_TRAVEL_GATES_REQUIREMENT_ID = "QF-008"
FETCHDATA_IMPL_DATACATALOG_TIME_TRAVEL_GATES_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_DATACATALOG_TIME_TRAVEL_GATES_CLAUSE = "为 DataCatalog/time‑travel 与 gates 提供可审计输入基础；"
# QF-009 multi-step planner traceability clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:19
FETCHDATA_IMPL_MULTI_STEP_TRACEABILITY_REQUIREMENT_ID = "QF-009"
FETCHDATA_IMPL_MULTI_STEP_TRACEABILITY_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_MULTI_STEP_TRACEABILITY_CLAUSE = "支持多步取数（如 list→sample→day）并可追溯。"
# QF-010 backtest plane/kernel boundary clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:22
FETCHDATA_IMPL_BACKTEST_PLANE_KERNEL_BOUNDARY_REQUIREMENT_ID = "QF-010"
FETCHDATA_IMPL_BACKTEST_PLANE_KERNEL_BOUNDARY_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_BACKTEST_PLANE_KERNEL_BOUNDARY_CLAUSE = "策略逻辑生成、回测引擎实现（属于 Backtest Plane / Kernel）；"
# QF-011 GateRunner-only arbitration boundary clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:23
FETCHDATA_IMPL_GATERUNNER_ARBITRATION_BOUNDARY_REQUIREMENT_ID = "QF-011"
FETCHDATA_IMPL_GATERUNNER_ARBITRATION_BOUNDARY_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_GATERUNNER_ARBITRATION_BOUNDARY_CLAUSE = "策略是否有效的裁决（只允许 GateRunner 裁决）；"
# QF-012 UI interaction boundary and reviewable evidence contract clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:24
FETCHDATA_IMPL_UI_REVIEWABLE_EVIDENCE_REQUIREMENT_ID = "QF-012"
FETCHDATA_IMPL_UI_REVIEWABLE_EVIDENCE_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_UI_REVIEWABLE_EVIDENCE_CLAUSE = "UI 的交互实现（但必须规定 UI 可审阅的证据接口与产物）。"
# QF-013 existing-facts baseline clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:28
FETCHDATA_IMPL_BASELINE_REGRESSION_REQUIREMENT_ID = "QF-013"
FETCHDATA_IMPL_BASELINE_REGRESSION_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_BASELINE_REGRESSION_CLAUSE = "QA‑Fetch FetchData Implementation Spec (v1) / 1. 现有事实基线（必须保持可回归）"
# QF-014 function baseline clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:29
FETCHDATA_IMPL_FUNCTION_BASELINE_REQUIREMENT_ID = "QF-014"
FETCHDATA_IMPL_FUNCTION_BASELINE_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_FUNCTION_BASELINE_CLAUSE = (
    "QA‑Fetch FetchData Implementation Spec (v1) / 1. 现有事实基线（必须保持可回归） / 1.1 函数基线"
)
# QF-015 function registry clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:31
FETCHDATA_IMPL_FUNCTION_REGISTRY_REQUIREMENT_ID = "QF-015"
FETCHDATA_IMPL_FUNCTION_REGISTRY_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_FUNCTION_REGISTRY_CLAUSE = "函数注册表：`docs/05_data_plane/qa_fetch_function_registry_v1.json`"
FETCHDATA_IMPL_FUNCTION_REGISTRY_CONTRACT_PATH = "docs/05_data_plane/qa_fetch_function_registry_v1.json"
# QF-016 external semantic source clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:32
FETCHDATA_IMPL_SOURCE_SEMANTIC_REQUIREMENT_ID = "QF-016"
FETCHDATA_IMPL_SOURCE_SEMANTIC_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_SOURCE_SEMANTIC_CLAUSE = "对外语义：`source=fetch`"
FETCHDATA_IMPL_SOURCE_SEMANTIC_VALUE = "fetch"
# QF-017 engine split clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:33
FETCHDATA_IMPL_ENGINE_SPLIT_REQUIREMENT_ID = "QF-017"
FETCHDATA_IMPL_ENGINE_SPLIT_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_ENGINE_SPLIT_CLAUSE = "引擎拆分：`engine=mongo|mysql`（分布：mongo 48、mysql 23）"
# QF-018 machine routing and availability evidence clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:35
FETCHDATA_IMPL_MACHINE_ROUTING_AVAILABILITY_REQUIREMENT_ID = "QF-018"
FETCHDATA_IMPL_MACHINE_ROUTING_AVAILABILITY_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_MACHINE_ROUTING_AVAILABILITY_CLAUSE = (
    "QA‑Fetch FetchData Implementation Spec (v1) / 1. 现有事实基线（必须保持可回归） / 1.2 机器路由与可用性证据"
)
FETCHDATA_IMPL_MACHINE_ROUTING_REGISTRY_CONTRACT_PATH = "docs/05_data_plane/qa_fetch_registry_v1.json"
FETCHDATA_IMPL_MACHINE_ROUTING_PROBE_SUMMARY_CONTRACT_PATH = (
    "docs/05_data_plane/qa_fetch_probe_v3/probe_summary_v3_notebook_params.json"
)
FETCHDATA_IMPL_MACHINE_ROUTING_AVAILABILITY_EVIDENCE_PATHS = (
    FETCHDATA_IMPL_MACHINE_ROUTING_REGISTRY_CONTRACT_PATH,
    FETCHDATA_IMPL_MACHINE_ROUTING_PROBE_SUMMARY_CONTRACT_PATH,
)
# QF-019 routing registry clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:36
FETCHDATA_IMPL_ROUTING_REGISTRY_REQUIREMENT_ID = "QF-019"
FETCHDATA_IMPL_ROUTING_REGISTRY_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_ROUTING_REGISTRY_CLAUSE = "路由注册表：`docs/05_data_plane/qa_fetch_registry_v1.json`"
FETCHDATA_IMPL_ROUTING_REGISTRY_CONTRACT_PATH = FETCHDATA_IMPL_MACHINE_ROUTING_REGISTRY_CONTRACT_PATH
# QF-020 probe evidence clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:37
FETCHDATA_IMPL_PROBE_EVIDENCE_REQUIREMENT_ID = "QF-020"
FETCHDATA_IMPL_PROBE_EVIDENCE_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_PROBE_EVIDENCE_CLAUSE = "probe 证据：`docs/05_data_plane/qa_fetch_probe_v3/probe_summary_v3_notebook_params.json`"
FETCHDATA_IMPL_PROBE_EVIDENCE_CONTRACT_PATH = FETCHDATA_IMPL_MACHINE_ROUTING_PROBE_SUMMARY_CONTRACT_PATH
# QF-021 pass_has_data baseline clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:39
FETCHDATA_IMPL_PASS_HAS_DATA_REQUIREMENT_ID = "QF-021"
FETCHDATA_IMPL_PASS_HAS_DATA_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_PASS_HAS_DATA_CLAUSE = "pass_has_data=52"
# QF-022 pass_empty baseline clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:40
FETCHDATA_IMPL_PASS_EMPTY_REQUIREMENT_ID = "QF-022"
FETCHDATA_IMPL_PASS_EMPTY_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_PASS_EMPTY_CLAUSE = "pass_empty=19"
# QF-023 callable/no-runtime-blockage smoke conclusion anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:41
FETCHDATA_IMPL_CALLABLE_NO_RUNTIME_BLOCKAGE_REQUIREMENT_ID = "QF-023"
FETCHDATA_IMPL_CALLABLE_NO_RUNTIME_BLOCKAGE_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_CALLABLE_NO_RUNTIME_BLOCKAGE_CLAUSE = "结论：基线函数均可调用（按当前 smoke 口径），无 runtime 阻塞。"
# QF-024 runtime entrypoint baseline clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:43
FETCHDATA_IMPL_RUNTIME_ENTRYPOINTS_BASELINE_REQUIREMENT_ID = "QF-024"
FETCHDATA_IMPL_RUNTIME_ENTRYPOINTS_BASELINE_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_RUNTIME_ENTRYPOINTS_BASELINE_CLAUSE = (
    "QA‑Fetch FetchData Implementation Spec (v1) / 1. 现有事实基线（必须保持可回归） / 1.3 运行入口（已存在）"
)
RUNTIME_ENTRYPOINT_NAMES = ("execute_fetch_by_intent", "execute_fetch_by_name")
UI_REVIEWABLE_FETCH_EVIDENCE_INTERFACE_FIELDS = (
    "query_result",
    "fetch_evidence_summary",
    "evidence_pointer",
    "fetch_evidence_paths",
)
# QF-025 runtime entrypoint contract path from QA_Fetch_FetchData_Impl_Spec_v1.md:44
FETCHDATA_IMPL_RUNTIME_MODULE_REQUIREMENT_ID = "QF-025"
FETCHDATA_IMPL_RUNTIME_MODULE_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_RUNTIME_MODULE_CLAUSE = "runtime：`src/quant_eam/qa_fetch/runtime.py`"
RUNTIME_MODULE_CONTRACT_PATH = "src/quant_eam/qa_fetch/runtime.py"
# QF-026 runtime entrypoint clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:45
FETCHDATA_IMPL_RUNTIME_INTENT_ENTRYPOINT_REQUIREMENT_ID = "QF-026"
FETCHDATA_IMPL_RUNTIME_INTENT_ENTRYPOINT_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_RUNTIME_INTENT_ENTRYPOINT_CLAUSE = "`execute_fetch_by_intent(...)`"
RUNTIME_INTENT_ENTRYPOINT_NAME = RUNTIME_ENTRYPOINT_NAMES[0]
# QF-027 runtime entrypoint clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:46
FETCHDATA_IMPL_RUNTIME_NAME_ENTRYPOINT_REQUIREMENT_ID = "QF-027"
FETCHDATA_IMPL_RUNTIME_NAME_ENTRYPOINT_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_RUNTIME_NAME_ENTRYPOINT_CLAUSE = "`execute_fetch_by_name(...)`"
RUNTIME_NAME_ENTRYPOINT_NAME = RUNTIME_ENTRYPOINT_NAMES[1]
# QF-028 top-level goals clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:50
FETCHDATA_IMPL_TOP_LEVEL_GOALS_REQUIREMENT_ID = "QF-028"
FETCHDATA_IMPL_TOP_LEVEL_GOALS_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_TOP_LEVEL_GOALS_CLAUSE = "QA‑Fetch FetchData Implementation Spec (v1) / 2. 顶层设计目标（Goals）"
# QF-029 single data access channel clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:51
FETCHDATA_IMPL_SINGLE_DATA_ACCESS_CHANNEL_REQUIREMENT_ID = "QF-029"
FETCHDATA_IMPL_SINGLE_DATA_ACCESS_CHANNEL_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_SINGLE_DATA_ACCESS_CHANNEL_CLAUSE = (
    "QA‑Fetch FetchData Implementation Spec (v1) / 2. 顶层设计目标（Goals） / "
    "G1 单一取数通道（Single Data Access Channel）"
)
# QF-030 auditability clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:55
FETCHDATA_IMPL_AUDITABILITY_REQUIREMENT_ID = "QF-030"
FETCHDATA_IMPL_AUDITABILITY_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_AUDITABILITY_CLAUSE = (
    "QA‑Fetch FetchData Implementation Spec (v1) / 2. 顶层设计目标（Goals） / "
    "G2 证据链可审计（Auditability）"
)
# QF-031 no-lookahead clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:61
FETCHDATA_IMPL_NO_LOOKAHEAD_REQUIREMENT_ID = "QF-031"
FETCHDATA_IMPL_NO_LOOKAHEAD_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_NO_LOOKAHEAD_CLAUSE = "no‑lookahead（防前视）；"
NO_LOOKAHEAD_GATE_NAME = "no_lookahead"
# QF-032 structural sanity checks clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:62
FETCHDATA_IMPL_STRUCTURAL_SANITY_REQUIREMENT_ID = "QF-032"
FETCHDATA_IMPL_STRUCTURAL_SANITY_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_STRUCTURAL_SANITY_CLAUSE = "数据结构性 sanity checks；"
# QF-033 golden-query minimal-set regression/drift clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:63
FETCHDATA_IMPL_GOLDEN_QUERIES_REQUIREMENT_ID = "QF-033"
FETCHDATA_IMPL_GOLDEN_QUERIES_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_GOLDEN_QUERIES_CLAUSE = "Golden Queries 回归与漂移报告（最小集）。"
FETCHDATA_IMPL_GOLDEN_QUERIES_MIN_SET_RULE = "golden_query_minimal_set_non_empty"
GOLDEN_QUERY_MIN_SET_MIN_QUERIES = 1
# QF-034 adaptive data planning top-level goal clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:65
FETCHDATA_IMPL_ADAPTIVE_DATA_PLANNING_REQUIREMENT_ID = "QF-034"
FETCHDATA_IMPL_ADAPTIVE_DATA_PLANNING_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_ADAPTIVE_DATA_PLANNING_CLAUSE = (
    "QA‑Fetch FetchData Implementation Spec (v1) / 2. 顶层设计目标（Goals） / "
    "G4 自适应取数（Adaptive Data Planning）"
)
# QF-035 list->sample->day adaptive planning clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:67
FETCHDATA_IMPL_LIST_SAMPLE_DAY_REQUIREMENT_ID = "QF-035"
FETCHDATA_IMPL_LIST_SAMPLE_DAY_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_LIST_SAMPLE_DAY_CLAUSE = "*_list → 选择样本 → *_day（例如 MA250 年线用例）"
AUTO_SYMBOLS_MA250_STEP_SEQUENCE = ("list", "sample", "day")
# QF-036 review/rollback top-level goal clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:70
FETCHDATA_IMPL_REVIEW_ROLLBACK_REQUIREMENT_ID = "QF-036"
FETCHDATA_IMPL_REVIEW_ROLLBACK_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_REVIEW_ROLLBACK_CLAUSE = (
    "QA‑Fetch FetchData Implementation Spec (v1) / 2. 顶层设计目标（Goals） / "
    "G5 UI 可审阅与可回退（Review & Rollback）"
)
# QF-037 section-3 interfaces/contracts umbrella clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:75
FETCHDATA_IMPL_INTERFACES_UMBRELLA_REQUIREMENT_ID = "QF-037"
FETCHDATA_IMPL_INTERFACES_UMBRELLA_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_INTERFACES_UMBRELLA_CLAUSE = (
    "QA‑Fetch FetchData Implementation Spec (v1) / 3. 对外接口与 Contracts（Interfaces）"
)
# QF-038 FetchRequest v1 intent-first clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:76
FETCHDATA_IMPL_FETCH_REQUEST_V1_REQUIREMENT_ID = "QF-038"
FETCHDATA_IMPL_FETCH_REQUEST_V1_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_FETCH_REQUEST_V1_CLAUSE = (
    "QA‑Fetch FetchData Implementation Spec (v1) / 3. 对外接口与 Contracts（Interfaces） "
    "/ 3.1 FetchRequest v1（intent-first）"
)
FETCH_REQUEST_V1_MODE_OPTIONS = ("demo", "backtest")
FETCH_REQUEST_V1_INTENT_MODE = "intent_first"
FETCH_REQUEST_V1_FUNCTION_MODE = "strong_control_function"
FETCH_REQUEST_V1_SAMPLE_KEYS = ("n", "method")
# QF-039 FetchRequest v1 mode clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:80
FETCHDATA_IMPL_FETCH_REQUEST_MODE_REQUIREMENT_ID = "QF-039"
FETCHDATA_IMPL_FETCH_REQUEST_MODE_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_FETCH_REQUEST_MODE_CLAUSE = "mode: demo | backtest"
# QF-040 FetchRequest v1 intent core selectors clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:82
FETCHDATA_IMPL_FETCH_REQUEST_INTENT_CORE_REQUIREMENT_ID = "QF-040"
FETCHDATA_IMPL_FETCH_REQUEST_INTENT_CORE_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_FETCH_REQUEST_INTENT_CORE_CLAUSE = "asset, freq, (universe/venue), adjust"
FETCH_REQUEST_V1_INTENT_CORE_FIELDS = ("asset", "freq", "universe_or_venue", "adjust")
# QF-041 FetchRequest v1 optional symbols clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:83
FETCHDATA_IMPL_FETCH_REQUEST_SYMBOLS_OPTIONAL_REQUIREMENT_ID = "QF-041"
FETCHDATA_IMPL_FETCH_REQUEST_SYMBOLS_OPTIONAL_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_FETCH_REQUEST_SYMBOLS_OPTIONAL_CLAUSE = "symbols（可为空/缺省）"
FETCH_REQUEST_V1_SYMBOLS_OPTIONAL_BEHAVIOR = "symbols_optional_allow_empty_or_omitted"
# QF-042 FetchRequest v1 optional fields/default OHLCV clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:85
FETCHDATA_IMPL_FETCH_REQUEST_FIELDS_OPTIONAL_REQUIREMENT_ID = "QF-042"
FETCHDATA_IMPL_FETCH_REQUEST_FIELDS_OPTIONAL_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_FETCH_REQUEST_FIELDS_OPTIONAL_CLAUSE = "fields（可选，技术指标默认 OHLCV）"
FETCH_REQUEST_V1_FIELDS_DEFAULT_ALIAS = "OHLCV"
FETCH_REQUEST_V1_SYMBOLS_NORMALIZATION_BEHAVIOR = "empty_or_missing_symbols_normalize_to_omitted_selector"
FETCH_REQUEST_V1_FIELDS_DEFAULT_BEHAVIOR = "when_fields_omitted_runtime_defaults_to_ohlcv_for_technical_indicators"
# QF-076 correctness umbrella clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:144
FETCHDATA_IMPL_CORRECTNESS_UMBRELLA_REQUIREMENT_ID = "QF-076"
FETCHDATA_IMPL_CORRECTNESS_UMBRELLA_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_CORRECTNESS_UMBRELLA_CLAUSE = "QA‑Fetch FetchData Implementation Spec (v1) / 6. 正确性保障（Correctness）"
# QF-077 time-travel availability clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:145
FETCHDATA_IMPL_TIME_TRAVEL_AVAILABILITY_REQUIREMENT_ID = "QF-077"
FETCHDATA_IMPL_TIME_TRAVEL_AVAILABILITY_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_TIME_TRAVEL_AVAILABILITY_CLAUSE = (
    "QA‑Fetch FetchData Implementation Spec (v1) / 6. 正确性保障（Correctness） / 6.1 time-travel 可得性"
)
# QF-078 DataCatalog available_at<=as_of enforcement clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:146
FETCHDATA_IMPL_DATACATALOG_AVAILABLE_AT_AS_OF_REQUIREMENT_ID = "QF-078"
FETCHDATA_IMPL_DATACATALOG_AVAILABLE_AT_AS_OF_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_DATACATALOG_AVAILABLE_AT_AS_OF_CLAUSE = "DataCatalog 层必须强制 available_at <= as_of；"
# QF-079 fetch evidence as_of/availability summary clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:147
FETCHDATA_IMPL_FETCH_EVIDENCE_AS_OF_AVAILABILITY_REQUIREMENT_ID = "QF-079"
FETCHDATA_IMPL_FETCH_EVIDENCE_AS_OF_AVAILABILITY_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_FETCH_EVIDENCE_AS_OF_AVAILABILITY_CLAUSE = (
    "fetch 证据必须记录 as_of 与可得性相关摘要（用于复盘与 gate 解释）。"
)
FETCH_EVIDENCE_AS_OF_NORMALIZED_UTC_FORMAT = "YYYY-MM-DDTHH:MM:SSZ"
# time-travel availability rule anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:60
TIME_TRAVEL_AVAILABILITY_RULE = "available_at<=as_of"
TIME_TRAVEL_HISTORICAL_SELECTION_RULE = "select_historical_rows_where_available_at_lte_as_of"
TIME_TRAVEL_UNAVAILABLE_REASON = "time_travel_unavailable"
# QF-081 GateRunner dual-gate clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:150
FETCHDATA_IMPL_GATERUNNER_DUAL_GATES_REQUIREMENT_ID = "QF-081"
FETCHDATA_IMPL_GATERUNNER_DUAL_GATES_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_GATERUNNER_DUAL_GATES_CLAUSE = (
    "GateRunner 必须包含 no_lookahead 与 data_snapshot_integrity（或等价 gates）；"
)
DATA_SNAPSHOT_INTEGRITY_GATE_NAME = "data_snapshot_integrity"
GATERUNNER_REQUIRED_GATES = (NO_LOOKAHEAD_GATE_NAME, DATA_SNAPSHOT_INTEGRITY_GATE_NAME)
# QF-088 run gate-fail clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:151
FETCH_EVIDENCE_SNAPSHOT_MANIFEST_GATE_FAIL_RULE = "gate_fail_when_fetch_evidence_or_snapshot_manifest_missing"
# QF-107 hard-fail gate semantics anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:203
FETCHDATA_IMPL_DIRECT_GATE_FAIL_REQUIREMENT_ID = "QF-107"
FETCHDATA_IMPL_DIRECT_GATE_FAIL_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_DIRECT_GATE_FAIL_CLAUSE = "违规直接 gate fail。"
FETCH_RESULT_GATES_VIOLATION_RULE = "gate_fail_when_fetch_result_gate_summary_has_violations"
FETCHDATA_IMPL_CORRECTNESS_UMBRELLA_SUBCLAUSE_REQUIREMENT_IDS = ("QF-077", "QF-078", "QF-079", "QF-087", "QF-088")
FETCHDATA_IMPL_CORRECTNESS_UMBRELLA_CLAUSE_MAPPING: dict[str, tuple[str, ...]] = {
    "6.1 time-travel 可得性": (TIME_TRAVEL_AVAILABILITY_RULE,),
    "6.2 Gate 双重约束": (
        NO_LOOKAHEAD_GATE_NAME,
        DATA_SNAPSHOT_INTEGRITY_GATE_NAME,
        FETCH_EVIDENCE_SNAPSHOT_MANIFEST_GATE_FAIL_RULE,
    ),
}
# QF-084 structural sanity clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:155
SANITY_TIMESTAMP_ORDER_RULE = "timestamp_monotonic_increasing_and_no_duplicates_or_record_allow_rule"
# QF-084 explicit duplicate policy record rule from QA_Fetch_FetchData_Impl_Spec_v1.md:155
SANITY_TIMESTAMP_DUPLICATE_POLICY = "no_duplicates_allowed"
SANITY_TIMESTAMP_ORDER_COMPARE_MODE = "pairwise_datetime_or_lexicographic_fallback"
# QF-083 structural sanity dtype clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:156
SANITY_DTYPE_REASONABLENESS_RULE = "dtype_reasonableness_against_preview_non_missing_values"
# QF-083 structural sanity missing-ratio clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:157
SANITY_MISSING_RATIO_RULE = "column_level_missing_ratio_statistics"
# QF-091 empty-data semantics clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:158
SANITY_EMPTY_DATA_POLICY_RULE = "empty_data_semantics_consistent_with_policy_on_no_data"
# QF-086 golden-query correctness clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:160
FETCHDATA_IMPL_CORRECTNESS_GOLDEN_QUERIES_REQUIREMENT_ID = "QF-086"
FETCHDATA_IMPL_CORRECTNESS_GOLDEN_QUERIES_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_CORRECTNESS_GOLDEN_QUERIES_CLAUSE = (
    "QA‑Fetch FetchData Implementation Spec (v1) / 6. 正确性保障（Correctness） / 6.4 Golden Queries（回归与漂移）"
)
# QF-087 fixed-request output artifact clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:162
FETCHDATA_IMPL_CORRECTNESS_FIXED_REQUEST_OUTPUT_REQUIREMENT_ID = "QF-087"
FETCHDATA_IMPL_CORRECTNESS_FIXED_REQUEST_OUTPUT_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_CORRECTNESS_FIXED_REQUEST_OUTPUT_CLAUSE = "固定请求 → 产出 meta/hash/row_count/columns"
GOLDEN_QUERY_FIXED_SET_RULE = "fixed_query_set_with_expected_outputs"
GOLDEN_QUERY_EXPECTED_OUTPUT_FIELDS = ("status", "request_hash", "row_count", "columns")
GOLDEN_QUERY_FIXED_REQUEST_ARTIFACT_FIELDS = ("meta", "request_hash", "row_count", "columns")
GOLDEN_QUERY_EXPECTED_STATUS_OPTIONS = (
    STATUS_PASS_HAS_DATA,
    STATUS_PASS_EMPTY,
    STATUS_BLOCKED_SOURCE_MISSING,
    STATUS_ERROR_RUNTIME,
)
# QF-088 golden-query drift report path clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:163
FETCHDATA_IMPL_CORRECTNESS_DRIFT_REPORT_REQUIREMENT_ID = "QF-088"
FETCHDATA_IMPL_CORRECTNESS_DRIFT_REPORT_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_CORRECTNESS_DRIFT_REPORT_CLAUSE = (
    "漂移必须产出报告（报告文件位置由主控定义，但必须可被 CI 或 nightly 读取）"
)
GOLDEN_QUERY_DRIFT_REPORT_PATH_RULE = "controller_defined_report_path_ci_nightly_readable"
GOLDEN_QUERY_DRIFT_REPORT_SCHEMA_VERSION = "qa_fetch_golden_drift_report_v1"
GOLDEN_QUERY_SUMMARY_SCHEMA_VERSION = "qa_fetch_golden_summary_v1"
# QF-113 contracts/orchestrator regression execution semantics anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:215
FETCHDATA_IMPL_ORCHESTRATOR_CONTRACTS_REGRESSION_REQUIREMENT_ID = "QF-113"
FETCHDATA_IMPL_ORCHESTRATOR_CONTRACTS_REGRESSION_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_ORCHESTRATOR_CONTRACTS_REGRESSION_CLAUSE = (
    "用于 contracts/orchestrator/tests 的自动化回归，不等价于 notebook kernel 结果。"
)
FETCHDATA_IMPL_ORCHESTRATOR_CONTRACTS_REGRESSION_EXECUTION_ENV = "host_terminal"
FETCHDATA_IMPL_ORCHESTRATOR_CONTRACTS_REGRESSION_EXECUTION_ENV_RULE = (
    "contracts/orchestrator_tests_host_terminal"
)
# QF-114 host terminal baseline sample recording anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:217
FETCHDATA_IMPL_HOST_TERMINAL_BASELINE_SAMPLE_REQUIREMENT_ID = "QF-114"
FETCHDATA_IMPL_HOST_TERMINAL_BASELINE_SAMPLE_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_HOST_TERMINAL_BASELINE_SAMPLE_CLAUSE = (
    "QA‑Fetch FetchData Implementation Spec (v1) / 8. Definition of Done（主路闭环验收） / "
    "8.2 本轮已记录的宿主终端环境（基线样例）"
)
FETCHDATA_IMPL_HOST_TERMINAL_BASELINE_SAMPLE_RULE = (
    "record_host_terminal_environment_baseline_sample_for_contract_regression"
)
FETCHDATA_IMPL_HOST_TERMINAL_BASELINE_SAMPLE_REQUIRED_FIELDS = (
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
# QF-118 notebook-kernel acceptance clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:209
NOTEBOOK_KERNEL_MANUAL_PARAMS_NOTEBOOK_PATH = "notebooks/qa_fetch_manual_params_v3.ipynb"
NOTEBOOK_KERNEL_EXECUTION_ENV = "jupyter_notebook_kernel"
# QF-119 notebook-kernel interpreter clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:210
NOTEBOOK_KERNEL_PYTHON_EXECUTABLE_RULE = "use_notebook_kernel_sys_executable"
NOTEBOOK_KERNEL_FORBIDDEN_HOST_EXECUTABLE = "/usr/bin/python3"
# QF-120 notebook-params data verification clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:211
NOTEBOOK_PARAMS_DATA_VERIFICATION_RULE = "notebook_params_probe_requires_pass_has_data"
# QF-044 intent window clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:84
INTENT_REQUIRED_WINDOW_FIELDS = ("start", "end")
# QF-045 intent optional fields clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:85
INTENT_DEFAULT_FIELDS_OHLCV = ("open", "high", "low", "close", "volume")
# QF-073 technical-indicator default freq clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:138
TECHNICAL_INDICATOR_DEFAULT_FREQ = "day"
# QF-074 technical-indicator minimum default fields clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:139
FETCHDATA_IMPL_PLANNER_TECHNICAL_INDICATOR_DEFAULT_FIELDS_REQUIREMENT_ID = "QF-074"
FETCHDATA_IMPL_PLANNER_TECHNICAL_INDICATOR_DEFAULT_FIELDS_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_PLANNER_TECHNICAL_INDICATOR_DEFAULT_FIELDS_CLAUSE = "默认 fields 至少包含 OHLCV"
TECHNICAL_INDICATOR_MIN_FIELDS_OHLCV = INTENT_DEFAULT_FIELDS_OHLCV
# technical-indicator default adjust clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:140
TECHNICAL_INDICATOR_DEFAULT_ADJUST = "raw"
# QF-043 intent optional auto_symbols clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:86
FETCHDATA_IMPL_FETCH_REQUEST_AUTO_SYMBOLS_REQUIREMENT_ID = "QF-043"
FETCHDATA_IMPL_FETCH_REQUEST_AUTO_SYMBOLS_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_FETCH_REQUEST_AUTO_SYMBOLS_CLAUSE = "auto_symbols（bool，可选）"
INTENT_OPTIONAL_AUTO_SYMBOLS_BOOL = ("auto_symbols", "bool", "optional")
# QF-044 intent optional sample clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:87
FETCHDATA_IMPL_FETCH_REQUEST_SAMPLE_REQUIREMENT_ID = "QF-044"
FETCHDATA_IMPL_FETCH_REQUEST_SAMPLE_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_FETCH_REQUEST_SAMPLE_CLAUSE = "sample（可选：n/method）"
# QF-045 policy on_no_data clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:89
FETCHDATA_IMPL_FETCH_REQUEST_ON_NO_DATA_REQUIREMENT_ID = "QF-045"
FETCHDATA_IMPL_FETCH_REQUEST_ON_NO_DATA_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_FETCH_REQUEST_ON_NO_DATA_CLAUSE = "on_no_data: error | pass_empty | retry"
POLICY_ON_NO_DATA_OPTIONS = ("error", "pass_empty", "retry")
# QF-046 policy optional execution controls anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:90
FETCHDATA_IMPL_FETCH_REQUEST_LIMITS_REQUIREMENT_ID = "QF-046"
FETCHDATA_IMPL_FETCH_REQUEST_LIMITS_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_FETCH_REQUEST_LIMITS_CLAUSE = "（可选）max_symbols/max_rows/retry_strategy"
POLICY_OPTIONAL_EXECUTION_CONTROLS = ("max_symbols", "max_rows", "retry_strategy")
# QF-047 pre-orchestrator fail-fast validation clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:93
FETCHDATA_IMPL_FETCH_REQUEST_FAIL_FAST_REQUIREMENT_ID = "QF-047"
FETCHDATA_IMPL_FETCH_REQUEST_FAIL_FAST_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_FETCH_REQUEST_FAIL_FAST_CLAUSE = "FetchRequest 必须在编排前通过 schema+逻辑校验（非法直接 fail-fast）。"
FETCH_REQUEST_V1_FAIL_FAST_ERROR_PREFIX = "fetch_request validation failed before orchestration"
FETCH_RESULT_META_PRE_ORCHESTRATOR_VALIDATION_ERROR_PREFIX = (
    "fetch_result_meta validation failed before orchestration: "
)
# QF-048 intent/function exclusivity + strong-control function-mode gate from QA_Fetch_FetchData_Impl_Spec_v1.md:94
FETCHDATA_IMPL_FETCH_REQUEST_INTENT_FUNCTION_EXCLUSIVE_REQUIREMENT_ID = "QF-048"
FETCHDATA_IMPL_FETCH_REQUEST_INTENT_FUNCTION_EXCLUSIVE_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_FETCH_REQUEST_INTENT_FUNCTION_EXCLUSIVE_CLAUSE = (
    "intent 与 function 只能二选一：默认 intent；只有“强控函数”场景才允许 function 模式。"
)
FETCH_REQUEST_V1_STRONG_CONTROL_FUNCTION_FIELD = "strong_control_function"
ADAPTIVE_SOURCE_FALLBACK_RULE = "fallback_sources_follow_profile_order_then_alternate_engine"
ADAPTIVE_WINDOW_ADAPTATION_RULE = "shrink_query_window_by_end_aligned_lookback_days"
ADAPTIVE_PROFILE_SOURCE_ORDER_KEY = "adaptive_source_order"
ADAPTIVE_PROFILE_SOURCE_FALLBACK_KEY = "enable_source_fallback"
ADAPTIVE_PROFILE_WINDOW_LOOKBACK_DAYS_KEY = "adaptive_window_lookback_days"
ADAPTIVE_SOURCE_ORDER_OPTIONS = ("mongo_fetch", "mysql_fetch")
# QF-050 FetchResultMeta selected_function clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:98
FETCH_RESULT_META_SELECTED_FUNCTION_FIELD = "selected_function"
# QF-051 FetchResultMeta engine clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:99
FETCH_RESULT_META_ENGINE_FIELD = "engine"
FETCH_RESULT_META_ENGINE_OPTIONS = ("mongo", "mysql")
# QF-052 FetchResultMeta row_count/col_count clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:100
FETCH_RESULT_META_ROW_COL_COUNT_FIELDS = ("row_count", "col_count")
# FetchResultMeta min_ts/max_ts clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:101
FETCH_RESULT_META_MIN_MAX_TS_FIELDS = ("min_ts", "max_ts")
# QF-053 FetchResultMeta request_hash clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:102
FETCH_RESULT_META_REQUEST_HASH_FIELD = "request_hash"
FETCH_RESULT_META_REQUEST_HASH_VERSION_SALT = "qa_fetch_request_hash_v1"
# QF-054 FetchResultMeta coverage clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:103
FETCH_RESULT_META_COVERAGE_FIELD = "coverage"
FETCH_RESULT_META_AS_OF_FIELD = "as_of"
FETCH_RESULT_META_AVAILABILITY_SUMMARY_FIELD = "availability_summary"
FETCH_RESULT_META_COVERAGE_SYMBOL_SCOPE = "requested_symbols_only"
FETCH_RESULT_META_COVERAGE_REPORTING_GRANULARITY = "request_level"
FETCH_RESULT_META_COVERAGE_MISSING_RATE_FORMULA = "missing_symbol_count/requested_symbol_count"
FETCH_RESULT_META_COVERAGE_EMPTY_REQUEST_POLICY = "requested_symbol_count=0 => coverage=1.0, missing=0.0"
# QF-055 FetchResultMeta probe_status clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:104
FETCH_RESULT_META_OPTIONAL_PROBE_STATUS_OPTIONS = (STATUS_PASS_HAS_DATA, STATUS_PASS_EMPTY)
# QF-056 Evidence bundle umbrella clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:109
FETCHDATA_IMPL_EVIDENCE_BUNDLE_REQUIREMENT_ID = "QF-056"
FETCHDATA_IMPL_EVIDENCE_BUNDLE_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_EVIDENCE_BUNDLE_CLAUSE = "QA‑Fetch FetchData Implementation Spec (v1) / 4. Evidence Bundle 规范（必须进入 Dossier）"
# QF-057 Evidence bundle single-step quartet clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:110
FETCHDATA_IMPL_EVIDENCE_BUNDLE_SINGLE_STEP_REQUIREMENT_ID = "QF-057"
FETCHDATA_IMPL_EVIDENCE_BUNDLE_SINGLE_STEP_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_EVIDENCE_BUNDLE_SINGLE_STEP_CLAUSE = (
    "QA‑Fetch FetchData Implementation Spec (v1) / 4. Evidence Bundle 规范（必须进入 Dossier） / 4.1 单步证据（四件套）"
)
FETCH_EVIDENCE_DOSSIER_ROOT_TEMPLATE = "artifacts/dossiers/<run_id>/fetch"
FETCH_EVIDENCE_DOSSIER_ONE_HOP_RULE = "ui_reads_dossier_fetch_evidence_without_jobs_output_jumps"
FETCH_EVIDENCE_DOSSIER_RUN_ID_KEYS = ("run_id", "dossier_run_id")
FETCH_SNAPSHOT_MANIFEST_PATH_KEYS = ("snapshot_manifest_path",)
# FetchResultMeta warnings field anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:105
FETCH_RESULT_META_WARNINGS_FIELD = "warnings"
# QF-058 Evidence bundle single-step request filename clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:112
FETCHDATA_IMPL_EVIDENCE_FETCH_REQUEST_REQUIREMENT_ID = "QF-058"
FETCHDATA_IMPL_EVIDENCE_FETCH_REQUEST_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_EVIDENCE_FETCH_REQUEST_CLAUSE = "fetch_request.json"
FETCH_EVIDENCE_REQUEST_FILENAME = "fetch_request.json"
# QF-059 Evidence bundle single-step result meta filename clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:113
FETCHDATA_IMPL_EVIDENCE_FETCH_RESULT_META_REQUIREMENT_ID = "QF-059"
FETCHDATA_IMPL_EVIDENCE_FETCH_RESULT_META_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_EVIDENCE_FETCH_RESULT_META_CLAUSE = "fetch_result_meta.json"
FETCH_EVIDENCE_RESULT_META_FILENAME = "fetch_result_meta.json"
# QF-060 Evidence bundle single-step preview filename clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:114
FETCHDATA_IMPL_EVIDENCE_FETCH_PREVIEW_REQUIREMENT_ID = "QF-060"
FETCHDATA_IMPL_EVIDENCE_FETCH_PREVIEW_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_EVIDENCE_FETCH_PREVIEW_CLAUSE = "fetch_preview.csv"
FETCH_EVIDENCE_PREVIEW_FILENAME = "fetch_preview.csv"
# QF-061 Evidence bundle single-step error filename clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:115
FETCHDATA_IMPL_EVIDENCE_FETCH_ERROR_REQUIREMENT_ID = "QF-061"
FETCHDATA_IMPL_EVIDENCE_FETCH_ERROR_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_EVIDENCE_FETCH_ERROR_CLAUSE = "fetch_error.json（仅失败时，但失败必须有）"
FETCH_EVIDENCE_ERROR_FILENAME = "fetch_error.json"
# QF-062 Evidence bundle multi-step clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:117
FETCHDATA_IMPL_EVIDENCE_BUNDLE_MULTI_STEP_REQUIREMENT_ID = "QF-062"
FETCHDATA_IMPL_EVIDENCE_BUNDLE_MULTI_STEP_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_EVIDENCE_BUNDLE_MULTI_STEP_CLAUSE = (
    "QA‑Fetch FetchData Implementation Spec (v1) / 4. Evidence Bundle 规范（必须进入 Dossier） / 4.2 多步证据（step index）"
)
FETCH_EVIDENCE_MULTI_STEP_STEP_INDEX_RULE = "dossier_multistep_steps_must_include_explicit_step_index"
FETCH_EVIDENCE_SINGLE_STEP_REQUIRED_FILES = (
    FETCH_EVIDENCE_REQUEST_FILENAME,
    FETCH_EVIDENCE_RESULT_META_FILENAME,
    FETCH_EVIDENCE_PREVIEW_FILENAME,
)
FETCH_EVIDENCE_SINGLE_STEP_FAILURE_FILE = FETCH_EVIDENCE_ERROR_FILENAME
FETCH_EVIDENCE_SINGLE_STEP_FAILURE_RULE = "failure_requires_fetch_error_json"
FETCH_EVIDENCE_SINGLE_STEP_SUCCESS_RULE = "success_must_not_emit_fetch_error_json"
# QF-063 Evidence bundle multi-step index filename clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:119
FETCHDATA_IMPL_EVIDENCE_FETCH_STEPS_INDEX_REQUIREMENT_ID = "QF-063"
FETCHDATA_IMPL_EVIDENCE_FETCH_STEPS_INDEX_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_EVIDENCE_FETCH_STEPS_INDEX_CLAUSE = "fetch_steps_index.json"
FETCH_EVIDENCE_STEPS_INDEX_FILENAME = "fetch_steps_index.json"
FETCH_EVIDENCE_STEPS_INDEX_SCHEMA_VERSION = "qa_fetch_steps_index_v1"
# QF-089 UI integration umbrella clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:167
FETCHDATA_IMPL_UI_REVIEW_ROLLBACK_UMBRELLA_REQUIREMENT_ID = "QF-089"
FETCHDATA_IMPL_UI_REVIEW_ROLLBACK_UMBRELLA_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_UI_REVIEW_ROLLBACK_UMBRELLA_CLAUSE = (
    "QA‑Fetch FetchData Implementation Spec (v1) / 7. UI 集成要求（Review & Rollback）"
)
FETCHDATA_IMPL_UI_REVIEW_ROLLBACK_UMBRELLA_SUBCLAUSE_REQUIREMENT_IDS = (
    "QF-090",
    "QF-091",
    "QF-092",
    "QF-093",
    "QF-094",
    "QF-095",
    "QF-096",
)
# QF-090 UI Fetch Evidence Viewer clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:168
UI_FETCH_EVIDENCE_VIEWER_STEPS_INDEX_FILENAME = FETCH_EVIDENCE_STEPS_INDEX_FILENAME
# QF-091 UI Fetch Evidence Viewer step meta/preview clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:171
UI_FETCH_EVIDENCE_VIEWER_STEP_META_PREVIEW_FIELDS = ("result_meta_path", "preview_path")
UI_FETCH_EVIDENCE_VIEWER_STEP_META_PREVIEW_RULE = "step_meta_preview_exposed_via_fetch_steps_index_steps"
# QF-092 UI Fetch Evidence Viewer error.json clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:172
UI_FETCH_EVIDENCE_VIEWER_ERROR_FILENAME = "error.json"
UI_FETCH_EVIDENCE_VIEWER_FETCH_ERROR_PATH_OUTPUT_KEY = "fetch_error_path"
UI_FETCH_EVIDENCE_VIEWER_ERROR_PATH_OUTPUT_KEY = "error_path"
UI_FETCH_EVIDENCE_VIEWER_ERROR_EXPOSURE_RULE = "error_json_exposed_via_fetch_evidence_paths_error_path_when_failure"
UI_FETCH_EVIDENCE_VIEWER_STATE_SCHEMA_VERSION = "qa_fetch_evidence_viewer_state_v1"
UI_FETCH_EVIDENCE_VIEWER_REVIEW_ROLLBACK_RULE = "fetch_evidence_viewer_exposes_review_checkpoint_rollback_entrypoint"
# QF-094 fetch review checkpoint approve clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:176
FETCH_REVIEW_CHECKPOINT_APPROVE_ACTION = "approve"
# QF-094 approve transition clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:176
FETCH_REVIEW_CHECKPOINT_APPROVE_TRANSITION = "enter_next_stage"
# QF-095 fetch review checkpoint reject clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:177
FETCH_REVIEW_CHECKPOINT_REJECT_ACTION = "reject"
# QF-095 reject transition clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:177
FETCH_REVIEW_CHECKPOINT_REJECT_TRANSITION = "rollback_and_allow_fetch_request_edit_or_rerun"
# QF-096 append-only attempt history clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:178
FETCH_EVIDENCE_APPEND_ONLY_RULE = "append_only_keep_attempt_history"
FETCH_EVIDENCE_ATTEMPT_DIR_PREFIX = "attempt_"
FETCH_EVIDENCE_ATTEMPT_DIRNAME_TEMPLATE = "attempt_{attempt_index:06d}"
FETCH_EVIDENCE_ATTEMPTS_INDEX_FILENAME = "fetch_attempts_index.json"
FETCH_REVIEW_CHECKPOINT_STATE_SCHEMA_VERSION = "qa_fetch_review_checkpoint_state_v1"
FETCH_REVIEW_ROLLBACK_RESULT_SCHEMA_VERSION = "qa_fetch_review_rollback_result_v1"
FETCH_REVIEW_ROLLBACK_LOG_FILENAME = "fetch_review_rollback_log.jsonl"
FETCH_REVIEW_ROLLBACK_STATE_FILENAME = "fetch_review_rollback_state.json"
FETCH_REVIEW_ROLLBACK_STATE_SCHEMA_VERSION = "qa_fetch_review_rollback_state_v1"
FETCH_REVIEW_ROLLBACK_SCOPE_CANONICAL_FILES = "canonical_files"
FETCH_REVIEW_ROLLBACK_SCOPE_CANONICAL_FILES_WITH_ERRORS = "canonical_files_with_errors"
FETCH_REVIEW_ROLLBACK_SCOPE_OPTIONS = (
    FETCH_REVIEW_ROLLBACK_SCOPE_CANONICAL_FILES,
    FETCH_REVIEW_ROLLBACK_SCOPE_CANONICAL_FILES_WITH_ERRORS,
)
FETCH_REVIEW_ROLLBACK_CONFIRMATION_RULE = "confirm_true_required_before_rollback_apply"
FETCH_REVIEW_ROLLBACK_STALE_PREVIEW_RULE = "reject_when_latest_preview_hash_mismatch"
FETCH_REVIEW_ROLLBACK_TARGET_IDENTITY_RULE = "target_attempt_request_hash_must_match_when_provided"
FETCHDATA_IMPL_UI_REVIEW_ROLLBACK_UMBRELLA_CLAUSE_MAPPING: dict[str, tuple[str, ...]] = {
    "7.1 Fetch Evidence Viewer": (
        UI_FETCH_EVIDENCE_VIEWER_STEPS_INDEX_FILENAME,
        UI_FETCH_EVIDENCE_VIEWER_STEP_META_PREVIEW_RULE,
        UI_FETCH_EVIDENCE_VIEWER_ERROR_FILENAME,
        UI_FETCH_EVIDENCE_VIEWER_ERROR_EXPOSURE_RULE,
    ),
    "7.2 审阅点与回退": (
        FETCH_REVIEW_CHECKPOINT_APPROVE_TRANSITION,
        FETCH_REVIEW_CHECKPOINT_REJECT_TRANSITION,
        FETCH_EVIDENCE_APPEND_ONLY_RULE,
    ),
}
# QF-097 main-path closed-loop DoD umbrella clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:182
FETCHDATA_IMPL_CLOSED_LOOP_DOD_REQUIREMENT_ID = "QF-097"
FETCHDATA_IMPL_CLOSED_LOOP_DOD_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_CLOSED_LOOP_DOD_CLAUSE = "QA‑Fetch FetchData Implementation Spec (v1) / 8. Definition of Done（主路闭环验收）"

# QF-105 contract validation heading clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:185
FETCH_CONTRACT_VALIDATION_RULE = "pre_orchestrator_contract_validation_required"
# QF-064 Evidence bundle multi-step step-artifacts clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:120
FETCHDATA_IMPL_EVIDENCE_STEP_ARTIFACTS_REQUIREMENT_ID = "QF-064"
FETCHDATA_IMPL_EVIDENCE_STEP_ARTIFACTS_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_EVIDENCE_STEP_ARTIFACTS_CLAUSE = (
    "step_XXX_fetch_request.json / step_XXX_fetch_result_meta.json / "
    "step_XXX_fetch_preview.csv / step_XXX_fetch_error.json"
)
# QF-064 Evidence bundle multi-step request filename clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:120
FETCH_EVIDENCE_STEP_REQUEST_FILENAME_TEMPLATE = "step_{step_index:03d}_fetch_request.json"
# QF-064 Evidence bundle multi-step result meta filename clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:120
FETCH_EVIDENCE_STEP_RESULT_META_FILENAME_TEMPLATE = "step_{step_index:03d}_fetch_result_meta.json"
# QF-064 Evidence bundle multi-step preview filename clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:120
FETCH_EVIDENCE_STEP_PREVIEW_FILENAME_TEMPLATE = "step_{step_index:03d}_fetch_preview.csv"
# QF-064 Evidence bundle multi-step error filename clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:120
FETCH_EVIDENCE_STEP_ERROR_FILENAME_TEMPLATE = "step_{step_index:03d}_fetch_error.json"
# QF-065 Dossier archive clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:122
FETCHDATA_IMPL_EVIDENCE_DOSSIER_ARCHIVE_REQUIREMENT_ID = "QF-065"
FETCHDATA_IMPL_EVIDENCE_DOSSIER_ARCHIVE_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_EVIDENCE_DOSSIER_ARCHIVE_CLAUSE = (
    "QA‑Fetch FetchData Implementation Spec (v1) / 4. Evidence Bundle 规范（必须进入 Dossier） / 4.3 Dossier 归档要求"
)
FETCH_EVIDENCE_DOSSIER_ARCHIVE_ROOT_TEMPLATE = FETCH_EVIDENCE_DOSSIER_ROOT_TEMPLATE
FETCH_EVIDENCE_DOSSIER_ARCHIVE_ONE_HOP_RULE = FETCH_EVIDENCE_DOSSIER_ONE_HOP_RULE
REQUIRED_FETCH_EVIDENCE_CONTRACT_FILES: tuple[tuple[str, str], ...] = (
    ("fetch_request_path", FETCH_EVIDENCE_REQUEST_FILENAME),
    ("fetch_result_meta_path", FETCH_EVIDENCE_RESULT_META_FILENAME),
    ("fetch_preview_path", FETCH_EVIDENCE_PREVIEW_FILENAME),
    ("fetch_steps_index_path", FETCH_EVIDENCE_STEPS_INDEX_FILENAME),
)
UI_REVIEWABLE_FETCH_EVIDENCE_ARTIFACT_KEYS = tuple(key for key, _ in REQUIRED_FETCH_EVIDENCE_CONTRACT_FILES)
# QF-066 UI dossier-only fetch evidence viewer clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:124
FETCHDATA_IMPL_UI_DOSSIER_FETCH_EVIDENCE_REQUIREMENT_ID = "QF-066"
FETCHDATA_IMPL_UI_DOSSIER_FETCH_EVIDENCE_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_UI_DOSSIER_FETCH_EVIDENCE_CLAUSE = "UI 只读 Dossier 即可展示 fetch evidence（不需要跳转 jobs outputs 路径）。"
# QF-067 planner requirements umbrella clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:128
FETCHDATA_IMPL_PLANNER_REQUIREMENTS_UMBRELLA_REQUIREMENT_ID = "QF-067"
FETCHDATA_IMPL_PLANNER_REQUIREMENTS_UMBRELLA_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_PLANNER_REQUIREMENTS_UMBRELLA_CLAUSE = (
    "QA‑Fetch FetchData Implementation Spec (v1) / 5. 自适应规划规则（Planner Requirements）"
)
# QF-068 planner required behavior when symbols are omitted from QA_Fetch_FetchData_Impl_Spec_v1.md:129
FETCHDATA_IMPL_PLANNER_SYMBOLS_OMITTED_REQUIREMENT_ID = "QF-068"
FETCHDATA_IMPL_PLANNER_SYMBOLS_OMITTED_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_PLANNER_SYMBOLS_OMITTED_CLAUSE = (
    "QA‑Fetch FetchData Implementation Spec (v1) / 5. 自适应规划规则（Planner Requirements） / "
    "5.1 symbols 缺省时的必备行为"
)
# QF-069 planner clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:131
FETCHDATA_IMPL_PLANNER_LIST_CANDIDATES_REQUIREMENT_ID = "QF-069"
FETCHDATA_IMPL_PLANNER_LIST_CANDIDATES_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_PLANNER_LIST_CANDIDATES_CLAUSE = "先执行对应 *_list 获取候选集合；"
# QF-070 planner clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:132
FETCHDATA_IMPL_PLANNER_SAMPLE_STRATEGY_REQUIREMENT_ID = "QF-070"
FETCHDATA_IMPL_PLANNER_SAMPLE_STRATEGY_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_PLANNER_SAMPLE_STRATEGY_CLAUSE = "执行 sample（随机/流动性/行业分层等，具体策略由主控决定）；"
# QF-071 planner clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:133
FETCHDATA_IMPL_PLANNER_DAY_FETCH_REQUIREMENT_ID = "QF-071"
FETCHDATA_IMPL_PLANNER_DAY_FETCH_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_PLANNER_DAY_FETCH_CLAUSE = "再执行 *_day 拉取行情数据；"
# QF-072 planner clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:134
FETCHDATA_IMPL_PLANNER_STEP_EVIDENCE_REQUIREMENT_ID = "QF-072"
FETCHDATA_IMPL_PLANNER_STEP_EVIDENCE_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_PLANNER_STEP_EVIDENCE_CLAUSE = "每一步必须落 step evidence（可审计）。"
# QF-073 planner technical-indicator default data-shape clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:136
FETCHDATA_IMPL_PLANNER_TECHNICAL_INDICATOR_DEFAULT_DATA_SHAPE_REQUIREMENT_ID = "QF-073"
FETCHDATA_IMPL_PLANNER_TECHNICAL_INDICATOR_DEFAULT_DATA_SHAPE_SOURCE_DOCUMENT = FETCHDATA_IMPL_SPEC_SOURCE_DOCUMENT
FETCHDATA_IMPL_PLANNER_TECHNICAL_INDICATOR_DEFAULT_DATA_SHAPE_CLAUSE = (
    "QA‑Fetch FetchData Implementation Spec (v1) / 5. 自适应规划规则（Planner Requirements） / "
    "5.2 技术指标默认数据形态"
)
TECHNICAL_INDICATOR_DEFAULT_DATA_SHAPE_RULE = "default_freq_day_fields_ohlcv_adjust_raw_for_technical_indicator_tasks"
AUTO_SYMBOLS_REQUIRED_TRIGGER_RULE = "when_symbols_missing_and_auto_symbols_true_run_planner"
AUTO_SYMBOLS_DEFAULT_DERIVATION_RULE = "derive_symbols_from_list_candidates_then_sample"
AUTO_SYMBOLS_FALLBACK_RULE = "fallback_to_error_runtime_when_no_sampled_symbols"
AUTO_SYMBOLS_SAMPLE_STRATEGY_CONFIG_RULE = "controller_configurable_sample_strategy_with_params"
AUTO_SYMBOLS_STEP_EVIDENCE_REQUIRED_FIELDS = ("generated_at", "input_summary", "output_summary", "trace_id")
UI_DOSSIER_FETCH_EVIDENCE_FIELD = "dossier_fetch_evidence"
UI_DOSSIER_FETCH_EVIDENCE_READ_MODE = "read_only_dossier"
UI_DOSSIER_FETCH_EVIDENCE_ATTEMPTS_FIELD = "attempts_timeline"
UI_DOSSIER_FETCH_EVIDENCE_STEPS_FIELD = "steps_timeline"
UI_DOSSIER_FETCH_EVIDENCE_RETRY_ROLLBACK_FIELD = "retry_rollback_map"
UI_DOSSIER_FETCH_EVIDENCE_PATH_RULE = "dossier_payload_paths_must_resolve_under_artifacts_dossiers_run_id_fetch"
UI_DOSSIER_FETCH_EVIDENCE_REQUIRED_PATH_KEYS = tuple(key for key, _ in REQUIRED_FETCH_EVIDENCE_CONTRACT_FILES)
RETRY_STRATEGY_MAX_ATTEMPTS_KEY = "max_attempts"
BASELINE_ENGINE_SPLIT = {"mongo": 48, "mysql": 23}
BASELINE_FUNCTION_COUNT = sum(BASELINE_ENGINE_SPLIT.values())
FETCHDATA_IMPL_PASS_HAS_DATA_BASELINE_COUNT = 52
BASELINE_PASS_HAS_DATA_COUNT = FETCHDATA_IMPL_PASS_HAS_DATA_BASELINE_COUNT
FETCHDATA_IMPL_PASS_EMPTY_BASELINE_COUNT = 19
BASELINE_PASS_EMPTY_COUNT = FETCHDATA_IMPL_PASS_EMPTY_BASELINE_COUNT
FETCHDATA_IMPL_CALLABLE_BASELINE_COUNT = BASELINE_FUNCTION_COUNT
FETCHDATA_IMPL_RUNTIME_BLOCKED_SOURCE_MISSING_BASELINE_COUNT = 0
FETCHDATA_IMPL_RUNTIME_ERROR_BASELINE_COUNT = 0
ENGINE_INTERNAL_SOURCE = {"mongo": "mongo_fetch", "mysql": "mysql_fetch"}
BACKTEST_PLANE_FORBIDDEN_PAYLOAD_KEYS = frozenset(
    {
        "strategy_spec",
        "signal_dsl",
        "variable_dictionary",
        "calc_trace_plan",
        "runspec",
        "run_spec",
        "backtest_engine",
        "engine_contract",
    }
)
GATERUNNER_ONLY_FORBIDDEN_PAYLOAD_KEYS = frozenset(
    {
        "strategy_verdict",
        "strategy_validity",
        "strategy_is_valid",
        "strategy_valid",
        "gate_verdict",
        "gate_result",
        "gate_results",
        "gate_status",
        "gate_pass_fail",
    }
)
AUTO_SYMBOLS_DEFAULT_SAMPLE_N = 5
AUTO_SYMBOLS_DEFAULT_SAMPLE_METHOD = "stable_first_n"
AUTO_SYMBOLS_DEFAULT_SAMPLE_SEED = 0
AUTO_SYMBOLS_DEFAULT_ENABLED = False
AUTO_SYMBOLS_SAMPLE_PARAM_KEYS = ("n", "method", "seed", "liquidity_field", "industry_field")
AUTO_SYMBOLS_LIQUIDITY_FIELD_CANDIDATES = ("liquidity", "turnover", "amount", "volume")
AUTO_SYMBOLS_INDUSTRY_FIELD_CANDIDATES = ("industry", "industry_code", "sector", "sw_l1", "sw_level1")
SUPPORTED_SAMPLE_METHOD_ALIASES = {
    "stable_first_n": AUTO_SYMBOLS_DEFAULT_SAMPLE_METHOD,
    "random_shuffle": "random",
    "random": "random",
    "liquidity": "liquidity",
    "industry_stratified": "industry_stratified",
}
SUPPORTED_SAMPLE_METHOD_TOKENS = tuple(SUPPORTED_SAMPLE_METHOD_ALIASES.keys())
# QF-074 planner clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:131
AUTO_SYMBOLS_LIST_FIRST_RULE = "resolve_corresponding_list_before_sample_day"
# QF-071 planner clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:133
AUTO_SYMBOLS_DAY_EXECUTION_RULE = "execute_corresponding_day_after_sample"
# QF-072 planner clause anchor from QA_Fetch_FetchData_Impl_Spec_v1.md:134
AUTO_SYMBOLS_STEP_EVIDENCE_RULE = "emit_step_evidence_for_each_planner_step"
PLANNER_SOURCE_INTERNAL = "planner"
SUPPORTED_FETCH_POLICY_MODES = frozenset({"demo", "backtest", "smoke", "research"})
SUPPORTED_ON_NO_DATA_POLICIES = frozenset(POLICY_ON_NO_DATA_OPTIONS)
ON_NO_DATA_RETRY_TOTAL_ATTEMPTS = 2
FETCH_REQUEST_MODE_TO_POLICY_MODE = {"demo": "demo", "backtest": "backtest"}
AUTO_LIST_BY_ASSET: dict[str, list[str]] = {
    "stock": ["fetch_stock_list"],
    "future": ["fetch_future_list", "fetch_ctp_future_list"],
    "etf": ["fetch_etf_list"],
    "index": ["fetch_index_list"],
    "hkstock": ["fetch_get_hkstock_list"],
    "bond": ["fetch_bond_date_list"],
}
FETCH_REQUEST_INTENT_FIELD_KEYS = (
    "asset",
    "freq",
    "venue",
    "universe",
    "adjust",
    "symbols",
    "start",
    "end",
    "fields",
    "as_of",
    "auto_symbols",
    "sample",
)
FETCH_REQUEST_INTENT_VALIDATION_ASSET_OPTIONS = ("bond", "etf", "future", "hkstock", "index", "stock")
FETCH_REQUEST_INTENT_VALIDATION_FREQ_OPTIONS = ("day", "dk", "min", "transaction")
FETCH_REQUEST_INTENT_VALIDATION_ADJUST_OPTIONS = ("raw", "qfq", "hfq")


@dataclass(frozen=True)
class FetchIntent:
    asset: str | None = None
    freq: str | None = None
    venue: str | None = None
    universe: str | None = None
    adjust: str = TECHNICAL_INDICATOR_DEFAULT_ADJUST
    symbols: str | list[str] | None = None
    start: str | None = None
    end: str | None = None
    fields: list[str] | None = None
    function_override: str | None = None
    source_hint: str | None = None
    public_function: str | None = None
    auto_symbols: bool | None = None
    sample: dict[str, Any] | None = None
    extra_kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FetchExecutionPolicy:
    mode: str = "smoke"  # demo | smoke | research | backtest
    timeout_sec: int | None = None
    on_no_data: str = "pass_empty"  # pass_empty | error | retry
    max_symbols: int | None = None
    max_rows: int | None = None
    retry_strategy: dict[str, Any] | None = None
    snapshot_manifest_path: str | None = None


@dataclass
class FetchExecutionResult:
    status: str
    reason: str
    source: str | None
    source_internal: str | None
    engine: str | None
    provider_id: str | None
    provider_internal: str | None
    resolved_function: str | None
    public_function: str | None
    elapsed_sec: float
    row_count: int
    columns: list[str]
    dtypes: dict[str, str]
    preview: Any
    final_kwargs: dict[str, Any]
    mode: str
    data: Any | None = None


def execute_fetch_by_intent(
    intent: FetchIntent | dict[str, Any],
    *,
    policy: FetchExecutionPolicy | dict[str, Any] | None = None,
    window_profile_path: str | Path = DEFAULT_WINDOW_PROFILE_PATH,
    exception_decisions_path: str | Path = DEFAULT_EXCEPTION_DECISIONS_PATH,
    function_registry_path: str | Path = DEFAULT_FUNCTION_REGISTRY_PATH,
    routing_registry_path: str | Path = DEFAULT_ROUTING_REGISTRY_PATH,
    evidence_out_dir: str | Path | None = None,
    dossier_run_id: str | None = None,
    write_evidence: bool = True,
    _allow_evidence_opt_out: bool = False,
) -> FetchExecutionResult:
    raw_intent_payload = dict(intent) if isinstance(intent, dict) else None
    raw_policy_payload = dict(policy) if isinstance(policy, dict) else None
    resolved_dossier_run_id = _resolve_dossier_run_id(
        explicit_run_id=dossier_run_id,
        request_payload=raw_intent_payload,
        policy_payload=raw_policy_payload,
    )
    if isinstance(intent, dict):
        intent = _validate_fetch_request_v1_fail_fast(intent)
    normalized_intent, normalized_policy = _unwrap_fetch_request_payload(intent, policy)
    it = _coerce_intent(normalized_intent)
    pl = _coerce_policy(normalized_policy)
    effective_write_evidence = _resolve_effective_write_evidence(
        write_evidence=write_evidence,
        allow_opt_out=_allow_evidence_opt_out,
    )

    if it.function_override:
        source_hint = it.source_hint.strip() if isinstance(it.source_hint, str) and it.source_hint.strip() else None
        public_function = (
            it.public_function.strip() if isinstance(it.public_function, str) and it.public_function.strip() else None
        )
        kwargs = _intent_effective_kwargs(it)
        result = execute_fetch_by_name(
            function=it.function_override,
            kwargs=kwargs,
            policy=pl,
            source_hint=source_hint,
            window_profile_path=window_profile_path,
            exception_decisions_path=exception_decisions_path,
            function_registry_path=function_registry_path,
            public_function=public_function or it.function_override,
            write_evidence=False,
            _allow_evidence_opt_out=True,
        )
        request_payload = _build_intent_request_payload_for_evidence(
            intent=it,
            policy=pl,
            resolved_function=it.function_override,
            kwargs=kwargs,
            source_hint=source_hint,
            public_function=public_function or it.function_override,
        )
        return _finalize_fetch_execution_result(
            request_payload=request_payload,
            result=result,
            evidence_out_dir=evidence_out_dir,
            dossier_run_id=resolved_dossier_run_id,
            write_evidence=effective_write_evidence,
        )

    if not it.asset or not it.freq:
        raise ValueError("intent must provide asset/freq or function_override")

    it = _enforce_required_intent_window(it)
    kwargs = _intent_effective_kwargs(it)
    if _should_apply_auto_symbols_planner(it):
        planner_request_payload = _build_intent_request_payload_for_evidence(
            intent=it,
            policy=pl,
            resolved_function=None,
            kwargs=kwargs,
            source_hint=it.source_hint,
            public_function=it.public_function,
        )
        planner_result, step_records = _run_auto_symbols_planner_for_intent(
            intent=it,
            policy=pl,
            base_kwargs=kwargs,
            window_profile_path=window_profile_path,
            exception_decisions_path=exception_decisions_path,
            function_registry_path=function_registry_path,
            routing_registry_path=routing_registry_path,
        )
        return _finalize_fetch_execution_result(
            request_payload=planner_request_payload,
            result=planner_result,
            evidence_out_dir=evidence_out_dir,
            dossier_run_id=resolved_dossier_run_id,
            write_evidence=effective_write_evidence,
            step_records=step_records,
        )

    resolution = resolve_fetch(asset=it.asset, freq=it.freq, venue=_effective_intent_venue(it), adjust=it.adjust)
    _validate_routing_registry_resolution(
        routing_registry_path=routing_registry_path,
        public_function=resolution.public_name,
    )

    result = execute_fetch_by_name(
        function=resolution.public_name,
        kwargs=kwargs,
        policy=pl,
        source_hint=resolution.source,
        public_function=resolution.public_name,
        window_profile_path=window_profile_path,
        exception_decisions_path=exception_decisions_path,
        function_registry_path=function_registry_path,
        write_evidence=False,
        _allow_evidence_opt_out=True,
    )
    request_payload = _build_intent_request_payload_for_evidence(
        intent=it,
        policy=pl,
        resolved_function=resolution.public_name,
        kwargs=kwargs,
        source_hint=resolution.source,
        public_function=resolution.public_name,
    )
    return _finalize_fetch_execution_result(
        request_payload=request_payload,
        result=result,
        evidence_out_dir=evidence_out_dir,
        dossier_run_id=resolved_dossier_run_id,
        write_evidence=effective_write_evidence,
    )


def execute_fetch_by_name(
    *,
    function: str,
    kwargs: dict[str, Any] | None = None,
    policy: FetchExecutionPolicy | dict[str, Any] | None = None,
    source_hint: str | None = None,
    public_function: str | None = None,
    window_profile_path: str | Path = DEFAULT_WINDOW_PROFILE_PATH,
    exception_decisions_path: str | Path = DEFAULT_EXCEPTION_DECISIONS_PATH,
    function_registry_path: str | Path = DEFAULT_FUNCTION_REGISTRY_PATH,
    evidence_out_dir: str | Path | None = None,
    dossier_run_id: str | None = None,
    write_evidence: bool = True,
    _allow_evidence_opt_out: bool = False,
) -> FetchExecutionResult:
    raw_policy_payload = dict(policy) if isinstance(policy, dict) else None
    resolved_dossier_run_id = _resolve_dossier_run_id(
        explicit_run_id=dossier_run_id,
        request_payload=dict(kwargs) if isinstance(kwargs, dict) else None,
        policy_payload=raw_policy_payload,
    )
    pl = _coerce_policy(policy)
    effective_write_evidence = _resolve_effective_write_evidence(
        write_evidence=write_evidence,
        allow_opt_out=_allow_evidence_opt_out,
    )
    profile = load_smoke_window_profile(window_profile_path)
    decisions = load_exception_decisions(exception_decisions_path)
    registry = load_function_registry(function_registry_path)
    fn_name = str(function).strip()
    if not fn_name:
        raise ValueError("function must be non-empty")
    selected_public_function = public_function or fn_name
    request_payload = _build_function_request_payload_for_evidence(
        function=fn_name,
        kwargs=kwargs or {},
        policy=pl,
        source_hint=source_hint,
        public_function=selected_public_function,
    )

    registry_row = registry.get(fn_name)
    if registry_row is None:
        normalized_hint = normalize_source(source_hint)
        result = FetchExecutionResult(
            status=STATUS_BLOCKED_SOURCE_MISSING,
            reason="not_in_baseline",
            source="fetch",
            source_internal=normalized_hint,
            engine=_engine_from_source(normalized_hint),
            provider_id="fetch",
            provider_internal=normalized_hint,
            resolved_function=None,
            public_function=selected_public_function,
            elapsed_sec=0.0,
            row_count=0,
            columns=[],
            dtypes={},
            preview=[],
            final_kwargs=dict(kwargs or {}),
            mode=pl.mode,
            data=None,
        )
        return _finalize_fetch_execution_result(
            request_payload=request_payload,
            result=result,
            evidence_out_dir=evidence_out_dir,
            dossier_run_id=resolved_dossier_run_id,
            write_evidence=effective_write_evidence,
        )

    target_name = str(registry_row.get("target_name") or fn_name).strip()
    resolved_source_hint = (
        str(registry_row.get("source_internal") or registry_row.get("provider_internal") or "").strip().lower()
        or str(registry_row.get("source") or source_hint or "").strip().lower()
        or None
    )

    decision = decisions.get(fn_name, {})
    decision_status = str(decision.get("decision", "")).strip().lower()
    if decision_status in {"pending", "drop", "disabled"}:
        result = FetchExecutionResult(
            status=STATUS_BLOCKED_SOURCE_MISSING,
            reason=f"disabled_by_exception_policy: decision={decision_status}",
            source="fetch",
            source_internal=normalize_source(resolved_source_hint),
            engine=_engine_from_source(resolved_source_hint),
            provider_id="fetch",
            provider_internal=normalize_source(resolved_source_hint),
            resolved_function=target_name,
            public_function=selected_public_function,
            elapsed_sec=0.0,
            row_count=0,
            columns=[],
            dtypes={},
            preview=[],
            final_kwargs=dict(kwargs or {}),
            mode=pl.mode,
            data=None,
        )
        return _finalize_fetch_execution_result(
            request_payload=request_payload,
            result=result,
            evidence_out_dir=evidence_out_dir,
            dossier_run_id=resolved_dossier_run_id,
            write_evidence=effective_write_evidence,
        )

    merged_kwargs = dict(kwargs or {})
    prof = profile.get(fn_name, {})
    smoke_kwargs = prof.get("smoke_kwargs") if isinstance(prof, dict) else None
    if pl.mode == "smoke" and isinstance(smoke_kwargs, dict):
        for key, value in smoke_kwargs.items():
            merged_kwargs.setdefault(str(key), value)
    merged_kwargs = _apply_max_symbols_to_kwargs(merged_kwargs, max_symbols=pl.max_symbols)

    timeout_sec = _effective_timeout(pl, prof)
    adaptive_source_candidates = _adaptive_source_candidates(
        registry_source_hint=resolved_source_hint,
        request_source_hint=source_hint,
        profile_item=prof,
    )
    adaptive_window_candidates = _adaptive_window_kwargs_candidates(
        base_kwargs=merged_kwargs,
        profile_item=prof,
    )
    adaptive_plan_meta = _build_adaptive_plan_meta(
        source_candidates=adaptive_source_candidates,
        window_candidates=adaptive_window_candidates,
    )
    if adaptive_plan_meta is not None:
        request_payload["adaptive_plan"] = adaptive_plan_meta

    started = time.time()
    max_attempts = _effective_on_no_data_attempts(pl)
    last_result: FetchExecutionResult | None = None

    for source_index, source_candidate in enumerate(adaptive_source_candidates):
        has_more_source_candidates = source_index < (len(adaptive_source_candidates) - 1)
        try:
            fn, resolved_source = _resolve_callable(target_name, source_hint=source_candidate)
        except Exception as exc:  # noqa: BLE001
            normalized_source = normalize_source(source_candidate)
            status, reason = _classify_exception(normalized_source, exc)
            if status == STATUS_PASS_EMPTY and pl.on_no_data == "error":
                status = STATUS_ERROR_RUNTIME
            result = FetchExecutionResult(
                status=status,
                reason=reason,
                source="fetch",
                source_internal=normalized_source,
                engine=_engine_from_source(normalized_source),
                provider_id="fetch",
                provider_internal=normalized_source,
                resolved_function=target_name,
                public_function=selected_public_function,
                elapsed_sec=time.time() - started,
                row_count=0,
                columns=[],
                dtypes={},
                preview=[] if status == STATUS_PASS_EMPTY else None,
                final_kwargs=_json_safe({}),
                mode=pl.mode,
                data=None,
            )
            last_result = result
            if has_more_source_candidates and _should_continue_adaptive_plan(status=status, policy=pl):
                continue
            return _finalize_fetch_execution_result(
                request_payload=request_payload,
                result=result,
                evidence_out_dir=evidence_out_dir,
                dossier_run_id=resolved_dossier_run_id,
                write_evidence=effective_write_evidence,
            )

        for window_index, window_kwargs in enumerate(adaptive_window_candidates):
            has_more_candidates = has_more_source_candidates or window_index < (len(adaptive_window_candidates) - 1)
            final_kwargs = _prepare_kwargs_for_callable(fn, window_kwargs)
            final_kwargs = _apply_max_symbols_to_kwargs(final_kwargs, max_symbols=pl.max_symbols)
            request_as_of = _extract_request_as_of(request_payload)

            advance_to_next_candidate = False
            for attempt in range(1, max_attempts + 1):
                try:
                    out = _call_with_timeout(lambda: fn(**final_kwargs), timeout_sec=timeout_sec)
                    payload, _typ, _, _, _, raw_preview = _normalize_payload(out)
                    payload, time_travel_unavailable = _apply_datacatalog_available_at_as_of_guard(
                        payload=payload,
                        as_of=request_as_of,
                    )
                    if time_travel_unavailable:
                        if has_more_candidates:
                            advance_to_next_candidate = True
                            break
                        elapsed = time.time() - started
                        result = FetchExecutionResult(
                            status=STATUS_ERROR_RUNTIME,
                            reason=TIME_TRAVEL_UNAVAILABLE_REASON,
                            source="fetch",
                            source_internal=resolved_source,
                            engine=_engine_from_source(resolved_source),
                            provider_id="fetch",
                            provider_internal=resolved_source,
                            resolved_function=target_name,
                            public_function=selected_public_function,
                            elapsed_sec=elapsed,
                            row_count=0,
                            columns=[],
                            dtypes={},
                            preview=[],
                            final_kwargs=_json_safe(final_kwargs),
                            mode=pl.mode,
                            data=[],
                        )
                        last_result = result
                        return _finalize_fetch_execution_result(
                            request_payload=request_payload,
                            result=result,
                            evidence_out_dir=evidence_out_dir,
                            dossier_run_id=resolved_dossier_run_id,
                            write_evidence=effective_write_evidence,
                        )
                    payload = _apply_max_rows_to_payload(payload, max_rows=pl.max_rows)
                    payload, _typ, row_count, cols, dtypes, preview = _normalize_payload(payload)
                    if row_count <= 0 and pl.on_no_data == "retry" and attempt < max_attempts:
                        continue
                    raw_request_hash = _canonical_request_hash(request_payload)
                    raw_gate_input_summary = _build_gate_input_summary(
                        request_hash=raw_request_hash,
                        availability_summary=_build_availability_summary(
                            preview=raw_preview,
                            as_of=request_as_of,
                        ),
                        sanity_checks=_build_preview_sanity_checks(
                            preview,
                            dtypes=dtypes,
                            columns=cols,
                        ),
                    )

                    elapsed = time.time() - started
                    if row_count > 0:
                        status = STATUS_PASS_HAS_DATA
                        reason = "ok"
                    elif pl.on_no_data == "error":
                        status = STATUS_ERROR_RUNTIME
                        reason = "no_data"
                    else:
                        status = STATUS_PASS_EMPTY
                        reason = "no_data"

                    result = FetchExecutionResult(
                        status=status,
                        reason=reason,
                        source="fetch",
                        source_internal=resolved_source,
                        engine=_engine_from_source(resolved_source),
                        provider_id="fetch",
                        provider_internal=resolved_source,
                        resolved_function=target_name,
                        public_function=selected_public_function,
                        elapsed_sec=elapsed,
                        row_count=row_count,
                        columns=cols,
                        dtypes=dtypes,
                        preview=preview,
                        final_kwargs=_json_safe(final_kwargs),
                        mode=pl.mode,
                        data=payload,
                    )
                    last_result = result
                    if row_count <= 0 and has_more_candidates and _should_continue_adaptive_plan(status=status, policy=pl):
                        advance_to_next_candidate = True
                    else:
                        return _finalize_fetch_execution_result(
                            request_payload=request_payload,
                            result=result,
                            evidence_out_dir=evidence_out_dir,
                            dossier_run_id=resolved_dossier_run_id,
                            write_evidence=effective_write_evidence,
                            run_gate_input_summary=raw_gate_input_summary,
                        )
                    break
                except Exception as exc:  # noqa: BLE001
                    status, reason = _classify_exception(resolved_source, exc)
                    if status == STATUS_PASS_EMPTY and pl.on_no_data == "retry" and attempt < max_attempts:
                        continue
                    if status == STATUS_PASS_EMPTY and pl.on_no_data == "error":
                        status = STATUS_ERROR_RUNTIME

                    elapsed = time.time() - started
                    result = FetchExecutionResult(
                        status=status,
                        reason=reason,
                        source="fetch",
                        source_internal=resolved_source,
                        engine=_engine_from_source(resolved_source),
                        provider_id="fetch",
                        provider_internal=resolved_source,
                        resolved_function=target_name,
                        public_function=selected_public_function,
                        elapsed_sec=elapsed,
                        row_count=0,
                        columns=[],
                        dtypes={},
                        preview=[] if status == STATUS_PASS_EMPTY else None,
                        final_kwargs=_json_safe(final_kwargs),
                        mode=pl.mode,
                        data=None,
                    )
                    last_result = result
                    if has_more_candidates and _should_continue_adaptive_plan(status=status, policy=pl):
                        advance_to_next_candidate = True
                    else:
                        return _finalize_fetch_execution_result(
                            request_payload=request_payload,
                            result=result,
                            evidence_out_dir=evidence_out_dir,
                            dossier_run_id=resolved_dossier_run_id,
                            write_evidence=effective_write_evidence,
                        )
                    break

            if advance_to_next_candidate:
                continue

    if last_result is not None:
        return _finalize_fetch_execution_result(
            request_payload=request_payload,
            result=last_result,
            evidence_out_dir=evidence_out_dir,
            dossier_run_id=resolved_dossier_run_id,
            write_evidence=effective_write_evidence,
        )

    raise RuntimeError("unreachable: adaptive execution plan exhausted without terminal result")


def _should_continue_adaptive_plan(*, status: str, policy: FetchExecutionPolicy) -> bool:
    if status == STATUS_BLOCKED_SOURCE_MISSING:
        return True
    if status == STATUS_PASS_EMPTY and policy.on_no_data != "error":
        return True
    return False


def _adaptive_source_candidates(
    *,
    registry_source_hint: str | None,
    request_source_hint: str | None,
    profile_item: dict[str, Any],
) -> tuple[str | None, ...]:
    out: list[str] = []

    def _append(source_value: Any) -> None:
        normalized = normalize_source(source_value)
        if normalized and normalized not in out:
            out.append(normalized)

    primary_source = normalize_source(registry_source_hint) or normalize_source(request_source_hint)
    _append(primary_source)

    for source_value in _coerce_adaptive_source_order(profile_item.get(ADAPTIVE_PROFILE_SOURCE_ORDER_KEY)):
        _append(source_value)

    if bool(profile_item.get(ADAPTIVE_PROFILE_SOURCE_FALLBACK_KEY)):
        for source_value in ADAPTIVE_SOURCE_ORDER_OPTIONS:
            _append(source_value)

    if out:
        return tuple(out)
    return (None,)


def _coerce_adaptive_source_order(raw: Any) -> tuple[str, ...]:
    if not isinstance(raw, (list, tuple)):
        return ()
    out: list[str] = []
    for item in raw:
        normalized = normalize_source(item)
        if normalized and normalized not in out:
            out.append(normalized)
    return tuple(out)


def _adaptive_window_kwargs_candidates(
    *,
    base_kwargs: dict[str, Any],
    profile_item: dict[str, Any],
) -> tuple[dict[str, Any], ...]:
    base = dict(base_kwargs)
    candidates: list[dict[str, Any]] = [base]
    seen = {_window_kwargs_signature(base)}

    lookback_days = _coerce_adaptive_window_lookback_days(
        profile_item.get(ADAPTIVE_PROFILE_WINDOW_LOOKBACK_DAYS_KEY)
    )
    if not lookback_days:
        return tuple(candidates)

    start = _normalize_window_bound(base.get("start"))
    end = _normalize_window_bound(base.get("end"))
    if start is None or end is None:
        return tuple(candidates)

    start_dt = _parse_dt_for_compare(start)
    end_dt = _parse_dt_for_compare(end)
    if start_dt is None or end_dt is None or start_dt > end_dt:
        return tuple(candidates)

    for days in lookback_days:
        shifted_start_dt = end_dt - timedelta(days=max(0, int(days) - 1))
        if shifted_start_dt <= start_dt:
            continue
        adapted = dict(base)
        adapted["start"] = _format_window_bound_for_kwargs(shifted_start_dt, template=start)
        adapted["end"] = end
        key = _window_kwargs_signature(adapted)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(adapted)

    return tuple(candidates)


def _coerce_adaptive_window_lookback_days(raw: Any) -> tuple[int, ...]:
    values: list[int] = []
    items: list[Any]
    if isinstance(raw, (list, tuple)):
        items = list(raw)
    elif raw is None:
        items = []
    else:
        items = [raw]
    for item in items:
        try:
            candidate = int(item)
        except Exception:
            continue
        if candidate <= 0:
            continue
        if candidate not in values:
            values.append(candidate)
    return tuple(values)


def _format_window_bound_for_kwargs(value: datetime, *, template: str) -> str:
    normalized_template = str(template or "").strip()
    as_utc = value.astimezone(timezone.utc)
    if len(normalized_template) == 10 and normalized_template.count("-") == 2 and "T" not in normalized_template:
        return as_utc.date().isoformat()
    if normalized_template.endswith("Z"):
        return as_utc.isoformat().replace("+00:00", "Z")
    return as_utc.isoformat()


def _window_kwargs_signature(kwargs: dict[str, Any]) -> tuple[Any, ...]:
    return (
        _json_safe(kwargs.get("start")),
        _json_safe(kwargs.get("end")),
        _json_safe(kwargs.get("as_of")),
    )


def _build_adaptive_plan_meta(
    *,
    source_candidates: tuple[str | None, ...],
    window_candidates: tuple[dict[str, Any], ...],
) -> dict[str, Any] | None:
    if len(source_candidates) <= 1 and len(window_candidates) <= 1:
        return None
    return {
        "source_rule": ADAPTIVE_SOURCE_FALLBACK_RULE,
        "window_rule": ADAPTIVE_WINDOW_ADAPTATION_RULE,
        "source_candidates": [src for src in source_candidates if src],
        "window_candidates": [
            {
                "start": _json_safe(row.get("start")),
                "end": _json_safe(row.get("end")),
                "as_of": _json_safe(row.get("as_of")),
            }
            for row in window_candidates
        ],
        "candidate_count": len(source_candidates) * len(window_candidates),
    }


def _build_policy_payload(policy: FetchExecutionPolicy) -> dict[str, Any]:
    payload = {
        "mode": policy.mode,
        "timeout_sec": policy.timeout_sec,
        "on_no_data": policy.on_no_data,
    }
    if policy.max_symbols is not None:
        payload["max_symbols"] = policy.max_symbols
    if policy.max_rows is not None:
        payload["max_rows"] = policy.max_rows
    if isinstance(policy.retry_strategy, dict):
        payload["retry_strategy"] = _json_safe(dict(policy.retry_strategy))
    if policy.snapshot_manifest_path is not None:
        payload["snapshot_manifest_path"] = policy.snapshot_manifest_path
    return payload


def _build_function_request_payload_for_evidence(
    *,
    function: str,
    kwargs: dict[str, Any],
    policy: FetchExecutionPolicy,
    source_hint: str | None,
    public_function: str | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "function": function,
        "kwargs": _json_safe(dict(kwargs)),
        "policy": _build_policy_payload(policy),
    }
    normalized_source_hint = normalize_source(source_hint)
    if normalized_source_hint:
        payload["source_hint"] = normalized_source_hint
    if public_function:
        payload["public_function"] = public_function
    return payload


def _build_intent_request_payload_for_evidence(
    *,
    intent: FetchIntent,
    policy: FetchExecutionPolicy,
    resolved_function: str | None,
    kwargs: dict[str, Any],
    source_hint: str | None,
    public_function: str | None,
) -> dict[str, Any]:
    intent_payload: dict[str, Any] = {}
    if intent.asset is not None:
        intent_payload["asset"] = intent.asset
    if intent.freq is not None:
        intent_payload["freq"] = intent.freq
    if intent.venue is not None:
        intent_payload["venue"] = intent.venue
    if intent.universe is not None:
        intent_payload["universe"] = intent.universe
    if intent.adjust is not None:
        intent_payload["adjust"] = intent.adjust
    if intent.symbols is not None:
        intent_payload["symbols"] = _json_safe(intent.symbols)
    if intent.start is not None:
        intent_payload["start"] = intent.start
    if intent.end is not None:
        intent_payload["end"] = intent.end
    if intent.fields is not None:
        intent_payload["fields"] = _json_safe(intent.fields)
    if intent.function_override is not None:
        intent_payload["function_override"] = intent.function_override
    if intent.source_hint is not None:
        intent_payload["source_hint"] = intent.source_hint
    if intent.public_function is not None:
        intent_payload["public_function"] = intent.public_function
    if intent.auto_symbols is not None:
        intent_payload["auto_symbols"] = intent.auto_symbols
    if intent.sample is not None:
        intent_payload["sample"] = _json_safe(intent.sample)
    if intent.extra_kwargs:
        intent_payload["extra_kwargs"] = _json_safe(dict(intent.extra_kwargs))

    payload: dict[str, Any] = {
        "intent": intent_payload,
        "policy": _build_policy_payload(policy),
        "kwargs": _json_safe(dict(kwargs)),
    }
    if intent.symbols is not None:
        payload["symbols"] = _json_safe(intent.symbols)
    if intent.start is not None:
        payload["start"] = intent.start
    if intent.end is not None:
        payload["end"] = intent.end
    if resolved_function:
        payload["function"] = resolved_function
    normalized_source_hint = normalize_source(source_hint)
    if normalized_source_hint:
        payload["source_hint"] = normalized_source_hint
    if public_function:
        payload["public_function"] = public_function
    return payload


def _resolve_runtime_fetch_evidence_out_dir(
    *,
    request_payload: dict[str, Any],
    out_dir: str | Path | None,
    dossier_run_id: str | None,
) -> Path:
    if out_dir is not None:
        return Path(out_dir)
    resolved_dossier_run_id = _resolve_dossier_run_id(
        explicit_run_id=dossier_run_id,
        request_payload=request_payload,
    )
    if resolved_dossier_run_id:
        return DEFAULT_DOSSIER_ROOT / resolved_dossier_run_id / DOSSIER_FETCH_SUBDIR_NAME
    return DEFAULT_RUNTIME_FETCH_EVIDENCE_ROOT / _canonical_request_hash(request_payload)


def _normalize_dossier_run_id(raw: Any) -> str | None:
    if raw is None:
        return None
    token = str(raw).strip()
    if not token:
        return None
    token = "".join(ch if (ch.isalnum() or ch in {"-", "_"}) else "_" for ch in token).strip("_")
    return token or None


def _extract_dossier_run_id_from_mapping(payload: dict[str, Any] | None) -> str | None:
    if not isinstance(payload, dict):
        return None

    for key in FETCH_EVIDENCE_DOSSIER_RUN_ID_KEYS:
        normalized = _normalize_dossier_run_id(payload.get(key))
        if normalized is not None:
            return normalized

    for nested_key in ("policy", "intent", "kwargs"):
        nested_obj = payload.get(nested_key)
        if not isinstance(nested_obj, dict):
            continue
        for key in FETCH_EVIDENCE_DOSSIER_RUN_ID_KEYS:
            normalized = _normalize_dossier_run_id(nested_obj.get(key))
            if normalized is not None:
                return normalized
    return None


def _resolve_dossier_run_id(
    *,
    explicit_run_id: str | None,
    request_payload: dict[str, Any] | None = None,
    policy_payload: dict[str, Any] | None = None,
) -> str | None:
    return (
        _normalize_dossier_run_id(explicit_run_id)
        or _extract_dossier_run_id_from_mapping(request_payload)
        or _extract_dossier_run_id_from_mapping(policy_payload)
    )


def _extract_snapshot_manifest_path_from_mapping(payload: dict[str, Any] | None) -> Path | None:
    if not isinstance(payload, dict):
        return None

    for key in FETCH_SNAPSHOT_MANIFEST_PATH_KEYS:
        resolved = _coerce_optional_path(payload.get(key))
        if resolved is not None:
            return resolved

    for nested_key in ("policy", "intent", "kwargs", "fetch_request"):
        nested_obj = payload.get(nested_key)
        if not isinstance(nested_obj, dict):
            continue
        for key in FETCH_SNAPSHOT_MANIFEST_PATH_KEYS:
            resolved = _coerce_optional_path(nested_obj.get(key))
            if resolved is not None:
                return resolved
    return None


def _resolve_snapshot_manifest_path(
    *,
    explicit_path: str | Path | None = None,
    request_payload: dict[str, Any] | None = None,
    policy_payload: dict[str, Any] | None = None,
) -> Path | None:
    return (
        _coerce_optional_path(explicit_path)
        or _extract_snapshot_manifest_path_from_mapping(request_payload)
        or _extract_snapshot_manifest_path_from_mapping(policy_payload)
    )


def _resolve_effective_write_evidence(*, write_evidence: bool, allow_opt_out: bool) -> bool:
    if allow_opt_out:
        return bool(write_evidence)
    return True


def _finalize_fetch_execution_result(
    *,
    request_payload: dict[str, Any],
    result: FetchExecutionResult,
    evidence_out_dir: str | Path | None,
    dossier_run_id: str | None,
    write_evidence: bool,
    run_gate_input_summary: dict[str, Any] | None = None,
    step_records: list[dict[str, Any]] | None = None,
) -> FetchExecutionResult:
    if not write_evidence:
        if dossier_run_id is not None:
            fetch_meta_gate_input_summary = run_gate_input_summary
            if isinstance(fetch_meta_gate_input_summary, dict):
                enforce_fetch_execution_gates(
                    gate_input_summary=fetch_meta_gate_input_summary,
                    run_id=dossier_run_id,
                )
        return result
    out_dir = _resolve_runtime_fetch_evidence_out_dir(
        request_payload=request_payload,
        out_dir=evidence_out_dir,
        dossier_run_id=dossier_run_id,
    )
    paths = write_fetch_evidence(
        request_payload=request_payload,
        result=result,
        out_dir=out_dir,
        step_records=step_records,
    )
    if dossier_run_id is not None:
        enforce_fetch_evidence_snapshot_manifest_gate(
            fetch_evidence_paths=paths,
            fetch_evidence_dir=out_dir,
            snapshot_manifest_path=_resolve_snapshot_manifest_path(request_payload=request_payload),
            run_id=dossier_run_id,
        )
        fetch_meta_gate_input_summary = run_gate_input_summary
        if not isinstance(fetch_meta_gate_input_summary, dict):
            fetch_meta = _build_fetch_meta_doc(request_payload=request_payload, result=result)
            fetch_meta_gate_input_summary = fetch_meta.get("gate_input_summary")
        enforce_fetch_execution_gates(
            gate_input_summary=fetch_meta_gate_input_summary,
            run_id=dossier_run_id,
        )
    return result


def _collect_missing_ui_reviewable_fetch_artifacts(*, paths: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for key in UI_REVIEWABLE_FETCH_EVIDENCE_ARTIFACT_KEYS:
        token = paths.get(key)
        if not isinstance(token, str) or not token.strip():
            missing.append(key)

    has_fetch_error_path = isinstance(paths.get(UI_FETCH_EVIDENCE_VIEWER_FETCH_ERROR_PATH_OUTPUT_KEY), str) and bool(
        str(paths.get(UI_FETCH_EVIDENCE_VIEWER_FETCH_ERROR_PATH_OUTPUT_KEY)).strip()
    )
    has_ui_error_path = isinstance(paths.get(UI_FETCH_EVIDENCE_VIEWER_ERROR_PATH_OUTPUT_KEY), str) and bool(
        str(paths.get(UI_FETCH_EVIDENCE_VIEWER_ERROR_PATH_OUTPUT_KEY)).strip()
    )
    if has_fetch_error_path and not has_ui_error_path:
        missing.append(UI_FETCH_EVIDENCE_VIEWER_ERROR_PATH_OUTPUT_KEY)
    if has_ui_error_path and not has_fetch_error_path:
        missing.append(UI_FETCH_EVIDENCE_VIEWER_FETCH_ERROR_PATH_OUTPUT_KEY)
    return missing


def _extract_fetch_evidence_viewer_step_rows(steps_index_payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_steps = steps_index_payload.get("steps")
    if not isinstance(raw_steps, list):
        return []

    viewer_steps: list[dict[str, Any]] = []
    for position, raw_step in enumerate(raw_steps, start=1):
        if not isinstance(raw_step, dict):
            continue
        row: dict[str, Any] = {}
        step_index = _coerce_attempt_index_token(raw_step.get("step_index"))
        if step_index is not None:
            row["step_index"] = step_index
        missing_fields: list[str] = []
        for field in UI_FETCH_EVIDENCE_VIEWER_STEP_META_PREVIEW_FIELDS:
            value = raw_step.get(field)
            if isinstance(value, str) and value.strip():
                row[field] = value
            else:
                missing_fields.append(field)
        if missing_fields:
            step_label = step_index if step_index is not None else position
            raise ValueError(
                "fetch_steps_index step "
                f"{step_label} missing required meta/preview fields: {', '.join(missing_fields)}"
            )
        error_value = raw_step.get("error_path")
        if isinstance(error_value, str) and error_value.strip():
            row["error_path"] = error_value
        viewer_steps.append(row)
    return viewer_steps


def build_fetch_evidence_viewer_state(
    *,
    fetch_evidence_paths: dict[str, Any],
    fetch_review_checkpoint: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(fetch_evidence_paths, dict):
        raise ValueError("fetch_evidence_paths must be an object")

    raw_steps_index_path = fetch_evidence_paths.get("fetch_steps_index_path")
    steps_index_path = str(raw_steps_index_path).strip() if isinstance(raw_steps_index_path, str) else ""
    if not steps_index_path:
        raise ValueError("fetch_evidence_paths.fetch_steps_index_path must be a non-empty string")

    steps_index_payload = _read_json_file_if_object(Path(steps_index_path))
    viewer_steps = _extract_fetch_evidence_viewer_step_rows(steps_index_payload)
    review_checkpoint = fetch_review_checkpoint if isinstance(fetch_review_checkpoint, dict) else {}
    rollback_entrypoint = review_checkpoint.get("rollback_entrypoint")

    review_integration: dict[str, Any] | None = None
    if isinstance(rollback_entrypoint, dict):
        review_integration = {
            "rule": UI_FETCH_EVIDENCE_VIEWER_REVIEW_ROLLBACK_RULE,
            "review_status": str(review_checkpoint.get("review_status") or ""),
            "active_attempt_index": _coerce_attempt_index_token(review_checkpoint.get("active_attempt_index")),
            "latest_attempt_index": _coerce_attempt_index_token(review_checkpoint.get("latest_attempt_index")),
            "action": str(rollback_entrypoint.get("action") or ""),
            "transition": str(rollback_entrypoint.get("transition") or ""),
            "target_scope_options": list(rollback_entrypoint.get("target_scope_options") or []),
            "target_attempt_index_options": list(rollback_entrypoint.get("target_attempt_index_options") or []),
        }

    return {
        "schema_version": UI_FETCH_EVIDENCE_VIEWER_STATE_SCHEMA_VERSION,
        "steps_index_filename": UI_FETCH_EVIDENCE_VIEWER_STEPS_INDEX_FILENAME,
        "steps_index_path": steps_index_path,
        "steps_index_schema_version": str(steps_index_payload.get("schema_version") or ""),
        "step_meta_preview_rule": UI_FETCH_EVIDENCE_VIEWER_STEP_META_PREVIEW_RULE,
        "steps_count": len(viewer_steps),
        "steps": viewer_steps,
        "fetch_error_path": fetch_evidence_paths.get("fetch_error_path"),
        "error_path": fetch_evidence_paths.get("error_path"),
        "review_integration": review_integration,
    }


def execute_ui_llm_query(
    query_envelope: dict[str, Any],
    *,
    out_dir: str | Path | None = None,
    dossier_run_id: str | None = None,
    step_records: list[dict[str, Any]] | None = None,
    policy: FetchExecutionPolicy | dict[str, Any] | None = None,
    window_profile_path: str | Path = DEFAULT_WINDOW_PROFILE_PATH,
    exception_decisions_path: str | Path = DEFAULT_EXCEPTION_DECISIONS_PATH,
) -> dict[str, Any]:
    if not isinstance(query_envelope, dict):
        raise ValueError("query_envelope must be an object")

    fetch_request = _validate_fetch_request_v1_fail_fast(_extract_fetch_request_from_query_envelope(query_envelope))
    resolved_dossier_run_id = _resolve_dossier_run_id(
        explicit_run_id=dossier_run_id,
        request_payload=query_envelope,
        policy_payload=dict(policy) if isinstance(policy, dict) else None,
    ) or _extract_dossier_run_id_from_mapping(fetch_request)
    result = execute_fetch_by_intent(
        fetch_request,
        policy=policy,
        window_profile_path=window_profile_path,
        exception_decisions_path=exception_decisions_path,
        write_evidence=False,
        _allow_evidence_opt_out=True,
    )

    query_result = _build_query_result_doc(result)
    fetch_evidence_summary = _build_fetch_meta_doc(fetch_request, result)
    out: dict[str, Any] = {field: None for field in UI_REVIEWABLE_FETCH_EVIDENCE_INTERFACE_FIELDS}
    out["query_result"] = _json_safe(query_result)
    out["fetch_evidence_summary"] = _json_safe(fetch_evidence_summary)

    query_id = str(query_envelope.get("query_id") or "").strip()
    if query_id:
        out["query_id"] = query_id

    evidence_out_dir = _resolve_ui_llm_evidence_out_dir(
        query_envelope=query_envelope,
        request_payload=fetch_request,
        out_dir=out_dir,
        dossier_run_id=resolved_dossier_run_id,
    )
    paths = write_fetch_evidence(
        request_payload=fetch_request,
        result=result,
        out_dir=evidence_out_dir,
        step_records=step_records,
    )
    missing_ui_artifacts = _collect_missing_ui_reviewable_fetch_artifacts(paths=paths)
    if missing_ui_artifacts:
        joined = ", ".join(missing_ui_artifacts)
        raise ValueError(f"ui-reviewable fetch evidence artifact paths missing required keys: {joined}")
    out["fetch_evidence_paths"] = paths
    out["evidence_pointer"] = paths.get("fetch_result_meta_path")
    checkpoint_state = build_fetch_review_checkpoint_state(fetch_evidence_dir=evidence_out_dir)
    if resolved_dossier_run_id is not None:
        enforce_fetch_evidence_snapshot_manifest_gate(
            fetch_evidence_paths=paths,
            fetch_evidence_dir=evidence_out_dir,
            snapshot_manifest_path=_resolve_snapshot_manifest_path(
                request_payload=query_envelope,
                policy_payload=fetch_request,
            ),
            run_id=resolved_dossier_run_id,
        )
    out[UI_DOSSIER_FETCH_EVIDENCE_FIELD] = _build_ui_dossier_fetch_evidence_payload(
        dossier_run_id=resolved_dossier_run_id,
        fetch_evidence_paths=paths,
        fetch_review_checkpoint=checkpoint_state,
    )
    out["fetch_review_checkpoint"] = checkpoint_state
    out["fetch_evidence_viewer"] = build_fetch_evidence_viewer_state(
        fetch_evidence_paths=paths,
        fetch_review_checkpoint=checkpoint_state,
    )

    return out


def execute_ui_llm_query_path(
    query_envelope: dict[str, Any],
    *,
    out_dir: str | Path | None = None,
    dossier_run_id: str | None = None,
    step_records: list[dict[str, Any]] | None = None,
    policy: FetchExecutionPolicy | dict[str, Any] | None = None,
    window_profile_path: str | Path = DEFAULT_WINDOW_PROFILE_PATH,
    exception_decisions_path: str | Path = DEFAULT_EXCEPTION_DECISIONS_PATH,
) -> dict[str, Any]:
    return execute_ui_llm_query(
        query_envelope,
        out_dir=out_dir,
        dossier_run_id=dossier_run_id,
        step_records=step_records,
        policy=policy,
        window_profile_path=window_profile_path,
        exception_decisions_path=exception_decisions_path,
    )


def write_fetch_evidence(
    *,
    request_payload: dict[str, Any],
    result: FetchExecutionResult,
    out_dir: str | Path,
    step_records: list[dict[str, Any]] | None = None,
) -> dict[str, str]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # If caller already targets an attempt folder, do a direct write only.
    if _parse_fetch_attempt_index(out_path.name) is not None:
        return _write_fetch_evidence_bundle(
            request_payload=request_payload,
            result=result,
            out_dir=out_path,
            step_records=step_records,
        )

    attempt_index = _next_fetch_attempt_index(out_path)
    attempt_dir = out_path / _format_fetch_attempt_dirname(attempt_index=attempt_index)
    attempt_dir.mkdir(parents=True, exist_ok=False)
    attempt_paths = _write_fetch_evidence_bundle(
        request_payload=request_payload,
        result=result,
        out_dir=attempt_dir,
        step_records=step_records,
    )
    paths = _write_fetch_evidence_bundle(
        request_payload=request_payload,
        result=result,
        out_dir=out_path,
        step_records=step_records,
    )

    attempts_index_path = _append_fetch_attempt_index(
        out_path=out_path,
        attempt_index=attempt_index,
        attempt_path=attempt_dir,
        attempt_paths=attempt_paths,
    )
    paths["fetch_attempts_index_path"] = attempts_index_path.as_posix()
    paths["attempt_path"] = attempt_dir.as_posix()
    paths["append_only_rule"] = FETCH_EVIDENCE_APPEND_ONLY_RULE
    return paths


def _utc_now_iso_z() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _build_step_bundle_trace_id(*, request_payload: dict[str, Any], out_path: Path) -> str:
    payload = {
        "trace_version": "qa_fetch_step_trace_v1",
        "request_hash": _canonical_request_hash(request_payload),
        "out_dir": out_path.as_posix(),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "fetch_trace_" + hashlib.sha256(encoded).hexdigest()[:24]


def _build_step_trace_id(
    *,
    bundle_trace_id: str,
    step_index: int,
    step_kind: str,
    step_request: dict[str, Any],
) -> str:
    payload = {
        "bundle_trace_id": bundle_trace_id,
        "step_index": int(step_index),
        "step_kind": str(step_kind or "").strip() or "step",
        "request_hash": _canonical_request_hash(step_request),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"{bundle_trace_id}:{int(step_index):03d}:{hashlib.sha256(encoded).hexdigest()[:16]}"


def _resolve_step_selected_function(step_request: dict[str, Any]) -> str | None:
    candidates: list[Any] = [step_request.get("function"), step_request.get("public_function")]
    intent_obj = step_request.get("intent")
    if isinstance(intent_obj, dict):
        candidates.extend([intent_obj.get("function_override"), intent_obj.get("public_function")])
    for raw in candidates:
        if not isinstance(raw, str):
            continue
        token = raw.strip()
        if token:
            return token
    return None


def _build_step_input_summary(*, step_request: dict[str, Any]) -> dict[str, Any]:
    requested_symbols = _extract_request_symbols(step_request)
    return {
        "request_hash": _canonical_request_hash(step_request),
        "top_level_keys": sorted(str(key) for key in step_request.keys()),
        "requested_symbol_count": len(requested_symbols),
        "requested_symbols_preview": requested_symbols[:20],
        "selected_function": _resolve_step_selected_function(step_request),
    }


def _build_step_output_summary(*, step_result: FetchExecutionResult) -> dict[str, Any]:
    row_count, columns = _resolve_result_table_shape(result=step_result)
    return {
        "status": step_result.status,
        "reason": step_result.reason,
        "row_count": int(row_count),
        "col_count": len(columns),
        "columns": columns,
        "resolved_function": step_result.resolved_function,
        "public_function": step_result.public_function,
        "engine": step_result.engine,
        "source_internal": step_result.source_internal,
        "elapsed_sec": float(step_result.elapsed_sec),
    }


def _write_fetch_evidence_bundle(
    *,
    request_payload: dict[str, Any],
    result: FetchExecutionResult,
    out_dir: str | Path,
    step_records: list[dict[str, Any]] | None = None,
) -> dict[str, str]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    request_path = out_path / FETCH_EVIDENCE_REQUEST_FILENAME
    meta_path = out_path / FETCH_EVIDENCE_RESULT_META_FILENAME
    preview_path = out_path / FETCH_EVIDENCE_PREVIEW_FILENAME
    error_path = out_path / FETCH_EVIDENCE_ERROR_FILENAME
    ui_error_path = out_path / UI_FETCH_EVIDENCE_VIEWER_ERROR_FILENAME
    steps_index_path = out_path / FETCH_EVIDENCE_STEPS_INDEX_FILENAME

    normalized_steps = _normalize_step_records_for_evidence(
        step_records=step_records,
        request_payload=request_payload,
        result=result,
    )

    multi_step = len(normalized_steps) > 1
    step_entries: list[dict[str, Any]] = []
    step_written_paths: list[tuple[Path, Path, Path, Path | None]] = []
    bundle_trace_id = _build_step_bundle_trace_id(request_payload=request_payload, out_path=out_path)

    for idx, (step_kind, step_request, step_result) in enumerate(normalized_steps, start=1):
        if multi_step:
            req_file = out_path / _step_evidence_filename(
                FETCH_EVIDENCE_STEP_REQUEST_FILENAME_TEMPLATE,
                step_index=idx,
            )
            meta_file = out_path / _step_evidence_filename(
                FETCH_EVIDENCE_STEP_RESULT_META_FILENAME_TEMPLATE,
                step_index=idx,
            )
            preview_file = out_path / _step_evidence_filename(
                FETCH_EVIDENCE_STEP_PREVIEW_FILENAME_TEMPLATE,
                step_index=idx,
            )
            err_file = out_path / _step_evidence_filename(
                FETCH_EVIDENCE_STEP_ERROR_FILENAME_TEMPLATE,
                step_index=idx,
            )
        else:
            req_file = request_path
            meta_file = meta_path
            preview_file = preview_path
            err_file = error_path

        req_file.write_text(
            json.dumps(_json_safe(step_request), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        step_meta = _build_fetch_meta_doc(step_request, step_result)
        meta_file.write_text(json.dumps(_json_safe(step_meta), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        _write_preview_csv(preview_file, step_result)

        wrote_error = None
        if step_result.status in {STATUS_BLOCKED_SOURCE_MISSING, STATUS_ERROR_RUNTIME}:
            err_obj = {
                "status": step_result.status,
                "reason": step_result.reason,
                "source": "fetch",
                "source_internal": step_result.source_internal,
                "engine": step_result.engine,
                "provider_id": step_result.provider_id,
                "provider_internal": step_result.provider_internal,
                "resolved_function": step_result.resolved_function,
                "public_function": step_result.public_function,
                "mode": step_result.mode,
                "final_kwargs": _json_safe(step_result.final_kwargs),
            }
            err_file.write_text(json.dumps(err_obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            wrote_error = err_file
        elif err_file.exists():
            err_file.unlink()

        generated_at = _utc_now_iso_z()
        input_summary = _build_step_input_summary(step_request=step_request)
        output_summary = _build_step_output_summary(step_result=step_result)
        trace_id = _build_step_trace_id(
            bundle_trace_id=bundle_trace_id,
            step_index=idx,
            step_kind=step_kind,
            step_request=step_request,
        )
        step_entry = {
            "step_index": idx,
            "step_kind": step_kind,
            "status": step_result.status,
            "generated_at": generated_at,
            "trace_id": trace_id,
            "input_summary": input_summary,
            "output_summary": output_summary,
            "request_path": req_file.as_posix(),
            "result_meta_path": meta_file.as_posix(),
            "preview_path": preview_file.as_posix(),
        }
        if wrote_error is not None:
            step_entry["error_path"] = wrote_error.as_posix()
        step_entries.append(step_entry)
        step_written_paths.append((req_file, meta_file, preview_file, wrote_error))

    if multi_step and step_written_paths:
        final_req, final_meta, final_preview, final_err = step_written_paths[-1]
        shutil.copy2(final_req, request_path)
        shutil.copy2(final_meta, meta_path)
        shutil.copy2(final_preview, preview_path)
        if final_err is not None and final_err.is_file():
            shutil.copy2(final_err, error_path)
        elif error_path.exists():
            error_path.unlink()

    if error_path.exists():
        shutil.copy2(error_path, ui_error_path)
    elif ui_error_path.exists():
        ui_error_path.unlink()

    steps_index = {
        "schema_version": FETCH_EVIDENCE_STEPS_INDEX_SCHEMA_VERSION,
        "generated_at": _utc_now_iso_z(),
        "trace_id": bundle_trace_id,
        "steps": step_entries,
    }
    steps_index_path.write_text(
        json.dumps(_json_safe(steps_index), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if not multi_step:
        _assert_single_step_quartet_contract(
            out_path=out_path,
            step_entries=step_entries,
            result_status=result.status,
            request_path=request_path,
            meta_path=meta_path,
            preview_path=preview_path,
            error_path=error_path,
            ui_error_path=ui_error_path,
        )
    else:
        _assert_multistep_step_index_contract(
            out_path=out_path,
            step_entries=step_entries,
        )

    paths = {
        "fetch_request_path": request_path.as_posix(),
        "fetch_result_meta_path": meta_path.as_posix(),
        "fetch_preview_path": preview_path.as_posix(),
        "fetch_steps_index_path": steps_index_path.as_posix(),
    }
    if error_path.exists():
        paths["fetch_error_path"] = error_path.as_posix()
    if ui_error_path.exists():
        paths["error_path"] = ui_error_path.as_posix()
    return paths


def _is_fetch_failure_status(status: str) -> bool:
    return status in {STATUS_BLOCKED_SOURCE_MISSING, STATUS_ERROR_RUNTIME}


def _normalize_step_records_for_evidence(
    *,
    step_records: list[dict[str, Any]] | None,
    request_payload: dict[str, Any],
    result: FetchExecutionResult,
) -> list[tuple[str, dict[str, Any], FetchExecutionResult]]:
    normalized_rows: list[tuple[int | None, str, dict[str, Any], FetchExecutionResult]] = []
    if isinstance(step_records, list):
        for row in step_records:
            if not isinstance(row, dict):
                continue
            step_kind = str(row.get("step_kind") or "").strip() or "step"
            req = row.get("request_payload")
            res = row.get("result")
            if not isinstance(req, dict) or not isinstance(res, FetchExecutionResult):
                continue
            raw_step_index = row.get("step_index")
            step_index: int | None = None
            if raw_step_index is not None:
                if isinstance(raw_step_index, bool):
                    raise RuntimeError("multi-step fetch evidence step_index must be a positive integer")
                try:
                    step_index = int(raw_step_index)
                except Exception as exc:
                    raise RuntimeError("multi-step fetch evidence step_index must be a positive integer") from exc
                if step_index <= 0:
                    raise RuntimeError("multi-step fetch evidence step_index must be a positive integer")
            normalized_rows.append((step_index, step_kind, req, res))

    if not normalized_rows:
        return [("single_fetch", request_payload, result)]

    explicit_count = sum(1 for step_index, *_rest in normalized_rows if step_index is not None)
    if explicit_count == 0:
        return [(step_kind, req, res) for _step_index, step_kind, req, res in normalized_rows]
    if explicit_count != len(normalized_rows):
        raise RuntimeError(
            "multi-step fetch evidence requires explicit contiguous step_index values "
            "for every step when step_index is provided"
        )

    by_step_index: dict[int, tuple[str, dict[str, Any], FetchExecutionResult]] = {}
    for step_index, step_kind, req, res in normalized_rows:
        assert step_index is not None
        if step_index in by_step_index:
            raise RuntimeError(f"multi-step fetch evidence contains duplicate step_index: {step_index}")
        by_step_index[step_index] = (step_kind, req, res)

    ordered_rows: list[tuple[str, dict[str, Any], FetchExecutionResult]] = []
    total = len(normalized_rows)
    for expected_index in range(1, total + 1):
        row = by_step_index.get(expected_index)
        if row is None:
            raise RuntimeError(
                "multi-step fetch evidence requires explicit contiguous step_index values "
                f"(missing {expected_index})"
            )
        ordered_rows.append(row)
    return ordered_rows


def _assert_single_step_quartet_contract(
    *,
    out_path: Path,
    step_entries: list[dict[str, Any]],
    result_status: str,
    request_path: Path,
    meta_path: Path,
    preview_path: Path,
    error_path: Path,
    ui_error_path: Path,
) -> None:
    if len(step_entries) != 1:
        raise RuntimeError("single-step fetch evidence must contain exactly one step entry")

    for required_path in (request_path, meta_path, preview_path):
        if not required_path.is_file():
            raise RuntimeError(
                f"single-step fetch evidence missing required file: {required_path.name}"
            )

    step = step_entries[0]
    _assert_step_entry_audit_fields(step=step, step_label="single-step")
    raw_step_index = step.get("step_index")
    if raw_step_index != 1:
        raise RuntimeError(
            "single-step fetch evidence requires explicit contiguous step_index values "
            f"(expected 1, got {raw_step_index!r})"
        )

    expected_paths = {
        "request_path": request_path,
        "result_meta_path": meta_path,
        "preview_path": preview_path,
    }
    for field, canonical_path in expected_paths.items():
        field_path = Path(str(step.get(field) or ""))
        if field_path != canonical_path:
            raise RuntimeError(
                f"single-step fetch evidence path drift for {field}: expected {canonical_path.as_posix()}"
            )
        if field_path.parent != out_path:
            raise RuntimeError(
                f"single-step fetch evidence path must stay in canonical out_dir for {field}: {field_path.as_posix()}"
            )

    has_error = error_path.is_file()
    if _is_fetch_failure_status(result_status):
        if not has_error:
            raise RuntimeError(
                f"single-step fetch evidence missing required failure file: {FETCH_EVIDENCE_SINGLE_STEP_FAILURE_FILE}"
            )
        if not ui_error_path.is_file():
            raise RuntimeError("single-step fetch evidence missing ui error mirror file")
    else:
        if has_error:
            raise RuntimeError(
                "single-step fetch evidence emitted failure file on non-failure status"
            )
        if ui_error_path.exists():
            raise RuntimeError("single-step fetch evidence emitted ui error file on non-failure status")


def _assert_multistep_step_index_contract(
    *,
    out_path: Path,
    step_entries: list[dict[str, Any]],
) -> None:
    if len(step_entries) < 2:
        raise RuntimeError("multi-step fetch evidence must contain at least two step entries")

    for expected_index, step in enumerate(step_entries, start=1):
        _assert_step_entry_audit_fields(step=step, step_label=f"step {expected_index}")
        raw_step_index = step.get("step_index")
        if not isinstance(raw_step_index, int) or raw_step_index != expected_index:
            raise RuntimeError(
                "multi-step fetch evidence requires explicit contiguous step_index values "
                f"(expected {expected_index}, got {raw_step_index!r})"
            )

        expected_paths = {
            "request_path": out_path
            / _step_evidence_filename(
                FETCH_EVIDENCE_STEP_REQUEST_FILENAME_TEMPLATE,
                step_index=expected_index,
            ),
            "result_meta_path": out_path
            / _step_evidence_filename(
                FETCH_EVIDENCE_STEP_RESULT_META_FILENAME_TEMPLATE,
                step_index=expected_index,
            ),
            "preview_path": out_path
            / _step_evidence_filename(
                FETCH_EVIDENCE_STEP_PREVIEW_FILENAME_TEMPLATE,
                step_index=expected_index,
            ),
        }

        for field, expected_path in expected_paths.items():
            raw_path = step.get(field)
            if not isinstance(raw_path, str) or not raw_path.strip():
                raise RuntimeError(f"multi-step fetch evidence missing {field} for step {expected_index}")
            actual_path = Path(raw_path)
            if actual_path != expected_path:
                raise RuntimeError(
                    f"multi-step fetch evidence path drift for {field}: expected {expected_path.as_posix()}"
                )
            if actual_path.parent != out_path:
                raise RuntimeError(
                    f"multi-step fetch evidence path must stay in canonical out_dir for {field}: {actual_path.as_posix()}"
                )
            if not actual_path.is_file():
                raise RuntimeError(f"multi-step fetch evidence missing required file: {actual_path.name}")

        status = str(step.get("status") or "").strip()
        raw_error_path = step.get("error_path")
        if _is_fetch_failure_status(status):
            if not isinstance(raw_error_path, str) or not raw_error_path.strip():
                raise RuntimeError(
                    f"multi-step fetch evidence missing error_path for failure step {expected_index}"
                )
            expected_error_path = out_path / _step_evidence_filename(
                FETCH_EVIDENCE_STEP_ERROR_FILENAME_TEMPLATE,
                step_index=expected_index,
            )
            actual_error_path = Path(raw_error_path)
            if actual_error_path != expected_error_path:
                raise RuntimeError(
                    "multi-step fetch evidence failure path drift for error_path: "
                    f"expected {expected_error_path.as_posix()}"
                )
            if not actual_error_path.is_file():
                raise RuntimeError(f"multi-step fetch evidence missing required file: {actual_error_path.name}")
        elif raw_error_path is not None:
            raise RuntimeError(
                f"multi-step fetch evidence emitted failure file on non-failure status at step {expected_index}"
            )


def _assert_step_entry_audit_fields(*, step: dict[str, Any], step_label: str) -> None:
    for field in AUTO_SYMBOLS_STEP_EVIDENCE_REQUIRED_FIELDS:
        if field not in step:
            raise RuntimeError(f"step evidence missing required audit field {field!r} at {step_label}")

    generated_at = step.get("generated_at")
    if not isinstance(generated_at, str) or not generated_at.strip():
        raise RuntimeError(f"step evidence generated_at must be non-empty at {step_label}")

    trace_id = step.get("trace_id")
    if not isinstance(trace_id, str) or not trace_id.strip():
        raise RuntimeError(f"step evidence trace_id must be non-empty at {step_label}")

    input_summary = step.get("input_summary")
    if not isinstance(input_summary, dict):
        raise RuntimeError(f"step evidence input_summary must be an object at {step_label}")
    request_hash = input_summary.get("request_hash")
    if not isinstance(request_hash, str) or len(request_hash.strip()) != 64:
        raise RuntimeError(f"step evidence input_summary.request_hash must be a 64-char hash at {step_label}")

    output_summary = step.get("output_summary")
    if not isinstance(output_summary, dict):
        raise RuntimeError(f"step evidence output_summary must be an object at {step_label}")
    for count_key in ("row_count", "col_count"):
        raw = output_summary.get(count_key)
        if isinstance(raw, bool):
            raise RuntimeError(f"step evidence output_summary.{count_key} must be a non-negative integer at {step_label}")
        try:
            normalized = int(raw)
        except Exception as exc:
            raise RuntimeError(
                f"step evidence output_summary.{count_key} must be a non-negative integer at {step_label}"
            ) from exc
        if normalized < 0:
            raise RuntimeError(f"step evidence output_summary.{count_key} must be a non-negative integer at {step_label}")


def _parse_fetch_attempt_index(dirname: str) -> int | None:
    token = str(dirname or "").strip()
    if not token.startswith(FETCH_EVIDENCE_ATTEMPT_DIR_PREFIX):
        return None
    suffix = token[len(FETCH_EVIDENCE_ATTEMPT_DIR_PREFIX) :]
    if not suffix.isdigit():
        return None
    return int(suffix)


def _format_fetch_attempt_dirname(*, attempt_index: int) -> str:
    return FETCH_EVIDENCE_ATTEMPT_DIRNAME_TEMPLATE.format(attempt_index=int(attempt_index))


def _next_fetch_attempt_index(out_path: Path) -> int:
    max_index = 0
    for child in out_path.iterdir():
        if not child.is_dir():
            continue
        parsed = _parse_fetch_attempt_index(child.name)
        if parsed is None:
            continue
        max_index = max(max_index, parsed)
    return max_index + 1


def _append_fetch_attempt_index(
    *,
    out_path: Path,
    attempt_index: int,
    attempt_path: Path,
    attempt_paths: dict[str, str],
) -> Path:
    index_path = out_path / FETCH_EVIDENCE_ATTEMPTS_INDEX_FILENAME
    attempts: list[dict[str, Any]] = []
    if index_path.is_file():
        try:
            existing = json.loads(index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
        if isinstance(existing, dict) and isinstance(existing.get("attempts"), list):
            attempts = [row for row in existing["attempts"] if isinstance(row, dict)]

    attempts.append(
        {
            "attempt_index": int(attempt_index),
            "attempt_path": attempt_path.as_posix(),
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "fetch_request_path": attempt_paths.get("fetch_request_path"),
            "fetch_result_meta_path": attempt_paths.get("fetch_result_meta_path"),
            "fetch_preview_path": attempt_paths.get("fetch_preview_path"),
            "fetch_steps_index_path": attempt_paths.get("fetch_steps_index_path"),
            "fetch_error_path": attempt_paths.get("fetch_error_path"),
            "error_path": attempt_paths.get("error_path"),
        }
    )

    index_doc = {
        "schema_version": "qa_fetch_attempts_index_v1",
        "rule": FETCH_EVIDENCE_APPEND_ONLY_RULE,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "latest_attempt_index": int(attempt_index),
        "attempt_count": len(attempts),
        "attempts": attempts,
    }
    index_path.write_text(json.dumps(_json_safe(index_doc), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return index_path


def build_fetch_review_checkpoint_state(
    *,
    fetch_evidence_dir: str | Path,
) -> dict[str, Any]:
    evidence_dir = Path(fetch_evidence_dir)
    attempt_rows = _load_fetch_attempt_rows(evidence_dir=evidence_dir)
    attempt_views = [_build_fetch_review_attempt_view(evidence_dir=evidence_dir, attempt_row=row) for row in attempt_rows]
    attempt_views = [row for row in attempt_views if row is not None]
    latest_attempt_index = attempt_views[-1]["attempt_index"] if attempt_views else None
    latest_preview_hash = str(attempt_views[-1].get("preview_hash") or "") if attempt_views else ""
    target_attempt_options = [row["attempt_index"] for row in attempt_views]
    rollback_state = _read_json_file_if_object(evidence_dir / FETCH_REVIEW_ROLLBACK_STATE_FILENAME)
    state_latest_attempt_index = _coerce_attempt_index_token(rollback_state.get("latest_attempt_index"))
    state_active_attempt_index = _coerce_attempt_index_token(rollback_state.get("active_attempt_index"))

    active_attempt_index = latest_attempt_index
    if (
        state_latest_attempt_index is not None
        and latest_attempt_index is not None
        and state_latest_attempt_index == latest_attempt_index
        and state_active_attempt_index in target_attempt_options
    ):
        active_attempt_index = state_active_attempt_index
    for row in attempt_views:
        row["is_active"] = row["attempt_index"] == active_attempt_index

    return {
        "schema_version": FETCH_REVIEW_CHECKPOINT_STATE_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "fetch_evidence_dir": evidence_dir.as_posix(),
        "review_status": "ready" if attempt_views else "empty",
        "attempt_count": len(attempt_views),
        "latest_attempt_index": latest_attempt_index,
        "latest_preview_hash": latest_preview_hash,
        "active_attempt_index": active_attempt_index,
        "attempts": attempt_views,
        "reviewable_changes": _build_fetch_reviewable_changes(attempt_views),
        "rollback_entrypoint": {
            "action": FETCH_REVIEW_CHECKPOINT_REJECT_ACTION,
            "transition": FETCH_REVIEW_CHECKPOINT_REJECT_TRANSITION,
            "confirmation_required": True,
            "confirmation_rule": FETCH_REVIEW_ROLLBACK_CONFIRMATION_RULE,
            "stale_preview_rule": FETCH_REVIEW_ROLLBACK_STALE_PREVIEW_RULE,
            "target_identity_rule": FETCH_REVIEW_ROLLBACK_TARGET_IDENTITY_RULE,
            "target_scope_options": list(FETCH_REVIEW_ROLLBACK_SCOPE_OPTIONS),
            "target_attempt_index_options": target_attempt_options,
            "latest_attempt_index": latest_attempt_index,
            "latest_preview_hash": latest_preview_hash,
        },
    }


def apply_fetch_review_rollback(
    *,
    fetch_evidence_dir: str | Path,
    action: str = FETCH_REVIEW_CHECKPOINT_REJECT_ACTION,
    target_attempt_index: int,
    target_scope: str = FETCH_REVIEW_ROLLBACK_SCOPE_CANONICAL_FILES_WITH_ERRORS,
    confirm: bool = False,
    expected_latest_attempt_index: int | None = None,
    expected_latest_preview_hash: str | None = None,
    expected_target_request_hash: str | None = None,
) -> dict[str, Any]:
    evidence_dir = Path(fetch_evidence_dir)
    normalized_action = str(action or "").strip().lower()
    normalized_scope = str(target_scope or "").strip().lower()
    normalized_target_attempt_index = _coerce_attempt_index_token(target_attempt_index)
    normalized_expected_latest = _coerce_attempt_index_token(expected_latest_attempt_index)
    normalized_expected_latest_preview_hash = _normalize_hash_token(expected_latest_preview_hash)
    normalized_expected_target_request_hash = _normalize_hash_token(expected_target_request_hash)
    normalized_action_transition = {
        FETCH_REVIEW_CHECKPOINT_APPROVE_ACTION: FETCH_REVIEW_CHECKPOINT_APPROVE_TRANSITION,
        FETCH_REVIEW_CHECKPOINT_REJECT_ACTION: FETCH_REVIEW_CHECKPOINT_REJECT_TRANSITION,
    }.get(normalized_action)

    if normalized_action_transition is None:
        return _record_fetch_review_rollback_feedback(
            evidence_dir=evidence_dir,
            feedback={
                "schema_version": FETCH_REVIEW_ROLLBACK_RESULT_SCHEMA_VERSION,
                "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "action": normalized_action,
                "transition": "",
                "success": False,
                "status": "rollback_rejected",
                "message": "",
                "failure_reason": "invalid_review_action",
                "fetch_evidence_dir": evidence_dir.as_posix(),
                "target_scope": normalized_scope,
                "target_attempt_index": normalized_target_attempt_index,
                "expected_latest_attempt_index": normalized_expected_latest,
                "expected_latest_preview_hash": normalized_expected_latest_preview_hash,
                "expected_target_request_hash": normalized_expected_target_request_hash,
                "latest_attempt_index": None,
                "latest_preview_hash": "",
                "attempt_count": 0,
                "reviewable_changes": [],
            },
        )

    attempt_rows = _load_fetch_attempt_rows(evidence_dir=evidence_dir)
    attempt_views = [_build_fetch_review_attempt_view(evidence_dir=evidence_dir, attempt_row=row) for row in attempt_rows]
    attempt_views = [row for row in attempt_views if row is not None]
    latest_attempt_index = attempt_views[-1]["attempt_index"] if attempt_views else None
    latest_preview_hash = str(attempt_views[-1].get("preview_hash") or "") if attempt_views else ""
    reviewable_changes = _build_fetch_reviewable_changes(attempt_views)

    feedback: dict[str, Any] = {
        "schema_version": FETCH_REVIEW_ROLLBACK_RESULT_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "action": normalized_action,
        "transition": normalized_action_transition,
        "success": False,
        "status": "rollback_rejected",
        "message": "",
        "failure_reason": "",
        "fetch_evidence_dir": evidence_dir.as_posix(),
        "target_scope": normalized_scope,
        "target_attempt_index": normalized_target_attempt_index,
        "expected_latest_attempt_index": normalized_expected_latest,
        "expected_latest_preview_hash": normalized_expected_latest_preview_hash,
        "expected_target_request_hash": normalized_expected_target_request_hash,
        "latest_attempt_index": latest_attempt_index,
        "latest_preview_hash": latest_preview_hash,
        "attempt_count": len(attempt_views),
        "reviewable_changes": reviewable_changes,
    }

    if normalized_action == FETCH_REVIEW_CHECKPOINT_REJECT_ACTION and normalized_scope not in FETCH_REVIEW_ROLLBACK_SCOPE_OPTIONS:
        feedback["failure_reason"] = "invalid_target_scope"
        feedback["message"] = (
            "rollback target_scope must be one of: "
            + ", ".join(FETCH_REVIEW_ROLLBACK_SCOPE_OPTIONS)
        )
        return _record_fetch_review_rollback_feedback(evidence_dir=evidence_dir, feedback=feedback)

    if normalized_target_attempt_index is None:
        feedback["failure_reason"] = "invalid_target_attempt_index"
        feedback["message"] = "rollback target_attempt_index must be a positive integer"
        return _record_fetch_review_rollback_feedback(evidence_dir=evidence_dir, feedback=feedback)

    if expected_latest_attempt_index is not None and normalized_expected_latest is None:
        feedback["failure_reason"] = "invalid_expected_latest_attempt_index"
        feedback["message"] = "rollback expected_latest_attempt_index must be a positive integer when provided"
        return _record_fetch_review_rollback_feedback(evidence_dir=evidence_dir, feedback=feedback)
    if expected_latest_preview_hash is not None and normalized_expected_latest_preview_hash is None:
        feedback["failure_reason"] = "invalid_expected_latest_preview_hash"
        feedback["message"] = "rollback expected_latest_preview_hash must be a 64-char hex sha256 token when provided"
        return _record_fetch_review_rollback_feedback(evidence_dir=evidence_dir, feedback=feedback)
    if expected_target_request_hash is not None and normalized_expected_target_request_hash is None:
        feedback["failure_reason"] = "invalid_expected_target_request_hash"
        feedback["message"] = "rollback expected_target_request_hash must be a 64-char hex sha256 token when provided"
        return _record_fetch_review_rollback_feedback(evidence_dir=evidence_dir, feedback=feedback)

    if not attempt_views:
        feedback["failure_reason"] = "attempt_history_missing"
        feedback["message"] = "rollback requires existing fetch attempt history"
        return _record_fetch_review_rollback_feedback(evidence_dir=evidence_dir, feedback=feedback)

    if (
        normalized_expected_latest is not None
        and latest_attempt_index is not None
        and normalized_expected_latest != latest_attempt_index
    ):
        feedback["failure_reason"] = "stale_review_state"
        feedback["message"] = (
            "rollback aborted because review state is stale; refresh review snapshot before retrying"
        )
        return _record_fetch_review_rollback_feedback(evidence_dir=evidence_dir, feedback=feedback)
    if (
        normalized_expected_latest_preview_hash is not None
        and latest_preview_hash
        and normalized_expected_latest_preview_hash != latest_preview_hash
    ):
        feedback["failure_reason"] = "stale_review_preview"
        feedback["message"] = (
            "rollback aborted because latest preview hash changed; refresh review snapshot before retrying"
        )
        return _record_fetch_review_rollback_feedback(evidence_dir=evidence_dir, feedback=feedback)

    if (
        normalized_action == FETCH_REVIEW_CHECKPOINT_REJECT_ACTION
        and not bool(confirm)
    ):
        feedback["failure_reason"] = "confirmation_required"
        feedback["message"] = "rollback confirmation required; set confirm=true"
        return _record_fetch_review_rollback_feedback(evidence_dir=evidence_dir, feedback=feedback)

    target_attempt = next(
        (row for row in attempt_views if row["attempt_index"] == normalized_target_attempt_index),
        None,
    )
    if target_attempt is None:
        feedback["failure_reason"] = "target_attempt_not_found"
        feedback["message"] = f"rollback target attempt {normalized_target_attempt_index} not found"
        return _record_fetch_review_rollback_feedback(evidence_dir=evidence_dir, feedback=feedback)
    target_request_hash = _normalize_hash_token(target_attempt.get("request_hash"))
    feedback["target_request_hash"] = target_request_hash
    if (
        normalized_expected_target_request_hash is not None
        and target_request_hash != normalized_expected_target_request_hash
    ):
        feedback["failure_reason"] = "target_attempt_identity_mismatch"
        feedback["message"] = "rollback target identity mismatch; refresh review state and select the latest attempt snapshot"
        return _record_fetch_review_rollback_feedback(evidence_dir=evidence_dir, feedback=feedback)

    if normalized_action == FETCH_REVIEW_CHECKPOINT_APPROVE_ACTION:
        feedback["success"] = True
        feedback["status"] = "review_approved"
        feedback["failure_reason"] = ""
        feedback["message"] = f"review approved for attempt {normalized_target_attempt_index}"
        feedback["active_attempt_index"] = normalized_target_attempt_index
        return _record_fetch_review_rollback_feedback(evidence_dir=evidence_dir, feedback=feedback)

    target_attempt_path = Path(target_attempt["attempt_path"])
    missing_required_files = [
        filename
        for _key, filename in REQUIRED_FETCH_EVIDENCE_CONTRACT_FILES
        if not (target_attempt_path / filename).is_file()
    ]
    if missing_required_files:
        feedback["failure_reason"] = "target_attempt_artifacts_missing"
        feedback["missing_required_files"] = missing_required_files
        feedback["message"] = (
            f"rollback target attempt {normalized_target_attempt_index} is missing required artifacts"
        )
        return _record_fetch_review_rollback_feedback(evidence_dir=evidence_dir, feedback=feedback)

    try:
        restored_paths, removed_paths = _restore_canonical_fetch_bundle_from_attempt(
            evidence_dir=evidence_dir,
            target_attempt_path=target_attempt_path,
            target_scope=normalized_scope,
        )
    except Exception as exc:
        feedback["failure_reason"] = "rollback_apply_failed"
        feedback["message"] = f"rollback failed while restoring canonical evidence bundle: {type(exc).__name__}: {exc}"
        return _record_fetch_review_rollback_feedback(evidence_dir=evidence_dir, feedback=feedback)

    feedback["success"] = True
    feedback["status"] = "rollback_applied"
    feedback["failure_reason"] = ""
    feedback["message"] = f"rollback applied to attempt {normalized_target_attempt_index}"
    feedback["active_attempt_index"] = normalized_target_attempt_index
    feedback["restored_paths"] = restored_paths
    feedback["removed_paths"] = removed_paths
    return _record_fetch_review_rollback_feedback(evidence_dir=evidence_dir, feedback=feedback)


def _normalize_hash_token(raw: Any) -> str | None:
    if raw is None:
        return None
    token = str(raw).strip().lower()
    if not token:
        return None
    if len(token) != 64:
        return None
    try:
        int(token, 16)
    except Exception:
        return None
    return token


def _hash_file_sha256(path: Path) -> str:
    if not path.is_file():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _coerce_attempt_index_token(raw: Any) -> int | None:
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    try:
        token = int(raw)
    except Exception:
        return None
    if token <= 0:
        return None
    return token


def _load_fetch_attempt_rows(*, evidence_dir: Path) -> list[dict[str, Any]]:
    if not evidence_dir.is_dir():
        return []

    out_by_index: dict[int, dict[str, Any]] = {}
    index_payload = _read_json_file_if_object(evidence_dir / FETCH_EVIDENCE_ATTEMPTS_INDEX_FILENAME)
    index_rows = index_payload.get("attempts") if isinstance(index_payload, dict) else None
    if isinstance(index_rows, list):
        for row in index_rows:
            if not isinstance(row, dict):
                continue
            resolved_path = _resolve_fetch_attempt_path(evidence_dir=evidence_dir, attempt_row=row)
            if resolved_path is None:
                continue
            attempt_index = _coerce_attempt_index_token(row.get("attempt_index"))
            if attempt_index is None:
                attempt_index = _parse_fetch_attempt_index(resolved_path.name)
            if attempt_index is None:
                continue
            out_by_index[attempt_index] = {
                "attempt_index": attempt_index,
                "attempt_path": resolved_path.as_posix(),
                "generated_at": row.get("generated_at"),
            }

    if not out_by_index:
        for child in evidence_dir.iterdir():
            if not child.is_dir():
                continue
            attempt_index = _parse_fetch_attempt_index(child.name)
            if attempt_index is None:
                continue
            out_by_index[attempt_index] = {
                "attempt_index": attempt_index,
                "attempt_path": child.as_posix(),
                "generated_at": None,
            }

    return [out_by_index[idx] for idx in sorted(out_by_index)]


def _resolve_fetch_attempt_path(*, evidence_dir: Path, attempt_row: dict[str, Any]) -> Path | None:
    raw_path = _coerce_optional_path(attempt_row.get("attempt_path"))
    if raw_path is not None:
        if raw_path.is_absolute():
            return raw_path
        if _path_within_root(path_value=raw_path, root_path=evidence_dir):
            return raw_path
        return evidence_dir / raw_path

    attempt_index = _coerce_attempt_index_token(attempt_row.get("attempt_index"))
    if attempt_index is None:
        return None
    return evidence_dir / _format_fetch_attempt_dirname(attempt_index=attempt_index)


def _read_json_file_if_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def _build_fetch_review_attempt_view(
    *,
    evidence_dir: Path,
    attempt_row: dict[str, Any],
) -> dict[str, Any] | None:
    attempt_index = _coerce_attempt_index_token(attempt_row.get("attempt_index"))
    attempt_path = _resolve_fetch_attempt_path(evidence_dir=evidence_dir, attempt_row=attempt_row)
    if attempt_index is None or attempt_path is None:
        return None

    request_path = attempt_path / FETCH_EVIDENCE_REQUEST_FILENAME
    meta_path = attempt_path / FETCH_EVIDENCE_RESULT_META_FILENAME
    preview_path = attempt_path / FETCH_EVIDENCE_PREVIEW_FILENAME
    steps_index_path = attempt_path / FETCH_EVIDENCE_STEPS_INDEX_FILENAME
    fetch_error_path = attempt_path / FETCH_EVIDENCE_ERROR_FILENAME
    ui_error_path = attempt_path / UI_FETCH_EVIDENCE_VIEWER_ERROR_FILENAME

    meta_payload = _read_json_file_if_object(meta_path)
    steps_payload = _read_json_file_if_object(steps_index_path)
    step_rows = steps_payload.get("steps")
    step_count = len(step_rows) if isinstance(step_rows, list) else 0
    try:
        row_count = int(meta_payload.get("row_count") or 0)
    except Exception:
        row_count = 0

    return {
        "attempt_index": attempt_index,
        "attempt_path": attempt_path.as_posix(),
        "generated_at": attempt_row.get("generated_at"),
        "fetch_request_path": request_path.as_posix(),
        "fetch_result_meta_path": meta_path.as_posix(),
        "fetch_preview_path": preview_path.as_posix(),
        "fetch_steps_index_path": steps_index_path.as_posix(),
        "request_path": request_path.as_posix(),
        "result_meta_path": meta_path.as_posix(),
        "preview_path": preview_path.as_posix(),
        "steps_index_path": steps_index_path.as_posix(),
        "fetch_error_path": fetch_error_path.as_posix() if fetch_error_path.is_file() else None,
        "error_path": ui_error_path.as_posix() if ui_error_path.is_file() else None,
        "status": str(meta_payload.get("status") or ""),
        "reason": str(meta_payload.get("reason") or ""),
        "selected_function": str(meta_payload.get("selected_function") or ""),
        "request_hash": _normalize_hash_token(meta_payload.get("request_hash")) or "",
        "preview_hash": _hash_file_sha256(preview_path),
        "row_count": row_count,
        "step_count": int(step_count),
        "required_artifacts_ready": all(
            (attempt_path / filename).is_file()
            for _key, filename in REQUIRED_FETCH_EVIDENCE_CONTRACT_FILES
        ),
    }


def _build_fetch_reviewable_changes(attempt_views: list[dict[str, Any]]) -> dict[str, Any] | None:
    if len(attempt_views) < 2:
        return None

    base = attempt_views[-2]
    candidate = attempt_views[-1]
    changed_fields: list[str] = []
    for field in ("request_hash", "preview_hash", "selected_function", "status", "reason", "row_count", "step_count"):
        if base.get(field) != candidate.get(field):
            changed_fields.append(field)

    try:
        row_count_delta = int(candidate.get("row_count") or 0) - int(base.get("row_count") or 0)
    except Exception:
        row_count_delta = 0

    return {
        "base_attempt_index": base["attempt_index"],
        "candidate_attempt_index": candidate["attempt_index"],
        "changed_fields": changed_fields,
        "request_hash_changed": base.get("request_hash") != candidate.get("request_hash"),
        "preview_hash_changed": base.get("preview_hash") != candidate.get("preview_hash"),
        "selected_function_changed": base.get("selected_function") != candidate.get("selected_function"),
        "status_changed": base.get("status") != candidate.get("status"),
        "row_count_delta": row_count_delta,
    }


def _restore_canonical_fetch_bundle_from_attempt(
    *,
    evidence_dir: Path,
    target_attempt_path: Path,
    target_scope: str,
) -> tuple[dict[str, str], list[str]]:
    source_artifacts: list[tuple[str, str, Path]] = [
        (key, filename, target_attempt_path / filename)
        for key, filename in REQUIRED_FETCH_EVIDENCE_CONTRACT_FILES
    ]
    include_error_files = target_scope == FETCH_REVIEW_ROLLBACK_SCOPE_CANONICAL_FILES_WITH_ERRORS
    optional_error_artifacts = (
        ("fetch_error_path", FETCH_EVIDENCE_ERROR_FILENAME),
        ("error_path", UI_FETCH_EVIDENCE_VIEWER_ERROR_FILENAME),
    )
    for key, filename in optional_error_artifacts:
        source_path = target_attempt_path / filename
        if include_error_files and source_path.is_file():
            source_artifacts.append((key, filename, source_path))

    source_bytes_by_filename: dict[str, tuple[str, bytes]] = {}
    for key, filename, source_path in source_artifacts:
        source_bytes_by_filename[filename] = (key, source_path.read_bytes())

    managed_filenames = {filename for _key, filename in REQUIRED_FETCH_EVIDENCE_CONTRACT_FILES}
    managed_filenames.update(filename for _key, filename in optional_error_artifacts)
    original_bytes_by_filename: dict[str, bytes | None] = {}
    for filename in sorted(managed_filenames):
        destination_path = evidence_dir / filename
        original_bytes_by_filename[filename] = destination_path.read_bytes() if destination_path.is_file() else None

    temp_paths: dict[str, Path] = {}
    rollback_token = f"{time.time_ns()}"
    restored_paths: dict[str, str] = {}
    removed_paths: list[str] = []
    try:
        for filename, (_key, payload_bytes) in source_bytes_by_filename.items():
            temp_path = evidence_dir / f".rollback_tmp_{rollback_token}_{filename}"
            temp_path.write_bytes(payload_bytes)
            temp_paths[filename] = temp_path

        for filename, (key, _payload_bytes) in source_bytes_by_filename.items():
            destination_path = evidence_dir / filename
            temp_paths[filename].replace(destination_path)
            restored_paths[key] = destination_path.as_posix()

        for _key, filename in optional_error_artifacts:
            if include_error_files and filename in source_bytes_by_filename:
                continue
            destination_path = evidence_dir / filename
            if destination_path.exists():
                destination_path.unlink()
                removed_paths.append(destination_path.as_posix())
    except Exception:
        for filename, original in original_bytes_by_filename.items():
            destination_path = evidence_dir / filename
            if original is None:
                if destination_path.exists():
                    destination_path.unlink()
                continue
            destination_path.write_bytes(original)
        raise
    finally:
        for temp_path in temp_paths.values():
            if temp_path.exists():
                temp_path.unlink()

    return restored_paths, removed_paths


def _record_fetch_review_rollback_feedback(
    *,
    evidence_dir: Path,
    feedback: dict[str, Any],
) -> dict[str, Any]:
    if not evidence_dir.is_dir():
        return feedback

    log_path = evidence_dir / FETCH_REVIEW_ROLLBACK_LOG_FILENAME
    state_path = evidence_dir / FETCH_REVIEW_ROLLBACK_STATE_FILENAME
    line = json.dumps(_json_safe(feedback), ensure_ascii=False, sort_keys=True)
    with log_path.open("a", encoding="utf-8") as fp:
        fp.write(line + "\n")

    state_payload = {
        "schema_version": FETCH_REVIEW_ROLLBACK_STATE_SCHEMA_VERSION,
        "generated_at": feedback.get("generated_at"),
        "action": feedback.get("action"),
        "transition": feedback.get("transition"),
        "success": bool(feedback.get("success")),
        "status": feedback.get("status"),
        "message": feedback.get("message"),
        "failure_reason": feedback.get("failure_reason"),
        "fetch_evidence_dir": feedback.get("fetch_evidence_dir"),
        "target_scope": feedback.get("target_scope"),
        "target_attempt_index": feedback.get("target_attempt_index"),
        "target_request_hash": feedback.get("target_request_hash"),
        "active_attempt_index": feedback.get("active_attempt_index"),
        "latest_attempt_index": feedback.get("latest_attempt_index"),
        "latest_preview_hash": feedback.get("latest_preview_hash"),
        "attempt_count": feedback.get("attempt_count"),
        "reviewable_changes": feedback.get("reviewable_changes"),
        "restored_paths": feedback.get("restored_paths"),
        "removed_paths": feedback.get("removed_paths"),
    }
    state_path.write_text(json.dumps(_json_safe(state_payload), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    out = dict(feedback)
    out["rollback_log_path"] = log_path.as_posix()
    out["rollback_state_path"] = state_path.as_posix()
    return out


def evaluate_fetch_evidence_snapshot_manifest_gate(
    *,
    fetch_evidence_paths: dict[str, Any] | None = None,
    fetch_evidence_dir: str | Path | None = None,
    snapshot_manifest_path: str | Path | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    normalized_paths = fetch_evidence_paths if isinstance(fetch_evidence_paths, dict) else {}
    evidence_dir = Path(fetch_evidence_dir) if fetch_evidence_dir is not None else None
    resolved_run_id = _normalize_dossier_run_id(run_id) or _extract_dossier_run_id_from_mapping(normalized_paths)
    if resolved_run_id is None and evidence_dir is not None:
        evidence_parts = evidence_dir.parts
        for idx, token in enumerate(evidence_parts):
            if token != "dossiers":
                continue
            if idx + 2 >= len(evidence_parts):
                continue
            if evidence_parts[idx + 2] != DOSSIER_FETCH_SUBDIR_NAME:
                continue
            resolved_run_id = _normalize_dossier_run_id(evidence_parts[idx + 1])
            if resolved_run_id is not None:
                break
    missing_fetch_evidence: list[str] = []
    for key, filename in REQUIRED_FETCH_EVIDENCE_CONTRACT_FILES:
        resolved_path = _resolve_required_evidence_path(
            key=key,
            filename=filename,
            fetch_evidence_paths=normalized_paths,
            fetch_evidence_dir=evidence_dir,
        )
        if resolved_path is None or not resolved_path.is_file():
            missing_fetch_evidence.append(key)

    normalized_snapshot_manifest_path = _coerce_optional_path(snapshot_manifest_path)
    snapshot_manifest_present = bool(
        normalized_snapshot_manifest_path is not None and normalized_snapshot_manifest_path.is_file()
    )

    failure_reasons = [f"missing_fetch_evidence:{key}" for key in missing_fetch_evidence]
    if not snapshot_manifest_present:
        failure_reasons.append("missing_snapshot_manifest")

    missing_labels: list[str] = [f"fetch_evidence.{key}" for key in missing_fetch_evidence]
    if not snapshot_manifest_present:
        missing_labels.append("snapshot_manifest")
    gate_pass = not failure_reasons
    status_message = (
        "fetch evidence + snapshot manifest gate pass"
        if gate_pass
        else "run gate fail: run_id="
        f"{resolved_run_id or 'unknown'} missing={', '.join(missing_labels) or 'unknown'}"
    )
    return {
        "rule": FETCH_EVIDENCE_SNAPSHOT_MANIFEST_GATE_FAIL_RULE,
        "gate_status": "pass" if gate_pass else "fail",
        "gate_pass": gate_pass,
        "run_id": resolved_run_id,
        "missing_fetch_evidence": missing_fetch_evidence,
        "snapshot_manifest_path": (
            normalized_snapshot_manifest_path.as_posix() if normalized_snapshot_manifest_path is not None else None
        ),
        "snapshot_manifest_present": snapshot_manifest_present,
        "failure_reasons": failure_reasons,
        "status_message": status_message,
    }


def enforce_fetch_evidence_snapshot_manifest_gate(
    *,
    fetch_evidence_paths: dict[str, Any] | None = None,
    fetch_evidence_dir: str | Path | None = None,
    snapshot_manifest_path: str | Path | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    verdict = evaluate_fetch_evidence_snapshot_manifest_gate(
        fetch_evidence_paths=fetch_evidence_paths,
        fetch_evidence_dir=fetch_evidence_dir,
        snapshot_manifest_path=snapshot_manifest_path,
        run_id=run_id,
    )
    if verdict["gate_pass"]:
        return verdict
    joined = ", ".join(verdict["failure_reasons"]) or "missing_artifacts"
    run_token = str(verdict.get("run_id") or "unknown")
    raise ValueError(
        "run must gate fail when fetch evidence / snapshot manifest is missing; "
        f"run_id={run_token}; violations={joined}"
    )


def enforce_fetch_execution_gates(
    *,
    gate_input_summary: dict[str, Any] | None,
    run_id: str | None,
) -> None:
    violations: list[str] = []
    if isinstance(gate_input_summary, dict):
        no_lookahead = gate_input_summary.get(NO_LOOKAHEAD_GATE_NAME, {})
        if isinstance(no_lookahead, dict):
            raw_violation_count = no_lookahead.get("available_at_violation_count")
            try:
                violation_count = int(raw_violation_count or 0)
            except Exception:
                violation_count = 0
            if violation_count > 0:
                violations.append(f"{NO_LOOKAHEAD_GATE_NAME}.available_at_violation_count={violation_count}")
            summary_rule = str(no_lookahead.get("rule") or "")
            if summary_rule and summary_rule != TIME_TRAVEL_AVAILABILITY_RULE:
                violations.append(f"{NO_LOOKAHEAD_GATE_NAME}.rule={summary_rule}")

    if violations:
        run_token = _normalize_dossier_run_id(run_id) or "unknown"
        raise ValueError(
            "run must gate fail when fetch execution gates are violated; "
            f"run_id={run_token}; violations={', '.join(violations)}"
        )


def _resolve_golden_query_orchestrator_environment(*, execution_environment: str | None) -> str:
    token = str(execution_environment or "").strip().lower()
    if not token:
        return FETCHDATA_IMPL_ORCHESTRATOR_CONTRACTS_REGRESSION_EXECUTION_ENV
    if token == FETCHDATA_IMPL_ORCHESTRATOR_CONTRACTS_REGRESSION_EXECUTION_ENV:
        return token
    if token in {"notebook", "notebook_kernel", "jupyter_notebook_kernel"}:
        raise ValueError(
            "contracts/orchestrator regression execution must run in host terminal; "
            "notebook-kernel parity is intentionally not part of contract baseline."
        )
    raise ValueError(
        "contracts/orchestrator regression execution environment must be host_terminal "
        f"(got={token!r})"
    )


def build_golden_query_execution_summary(
    *,
    golden_queries: list[dict[str, Any]],
    execute_by_intent: Any | None = None,
    execute_by_name: Any | None = None,
    execution_environment: str | None = None,
) -> dict[str, Any]:
    if not isinstance(golden_queries, list) or not golden_queries:
        raise ValueError("golden_queries must be a non-empty list")
    _resolve_golden_query_orchestrator_environment(execution_environment=execution_environment)

    intent_executor = execute_by_intent if callable(execute_by_intent) else execute_fetch_by_intent
    name_executor = execute_by_name if callable(execute_by_name) else execute_fetch_by_name
    seen_query_ids: set[str] = set()
    query_hashes: dict[str, str] = {}
    expected_outputs: dict[str, dict[str, Any]] = {}
    query_outputs: dict[str, dict[str, Any]] = {}
    fixed_request_artifacts: dict[str, dict[str, Any]] = {}
    query_reports: list[dict[str, Any]] = []
    regression_query_ids: list[str] = []

    for index, row in enumerate(golden_queries, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"golden_queries[{index}] must be an object")

        query_id = str(row.get("query_id") or "").strip()
        if not query_id:
            raise ValueError(f"golden_queries[{index}].query_id must be non-empty")
        if query_id in seen_query_ids:
            raise ValueError(f"golden_queries contains duplicate query_id: {query_id}")
        seen_query_ids.add(query_id)

        request_payload = row.get("request")
        if not isinstance(request_payload, dict) or not request_payload:
            raise ValueError(f"golden_queries[{index}].request must be a non-empty object")

        query_hash = _canonical_request_hash(request_payload)
        expected_output = _normalize_golden_query_expected_output(
            output=row.get("expected_output"),
            request_hash=query_hash,
            label=f"golden_queries[{index}].expected_output",
        )
        actual_result = _execute_golden_query_request(
            request_payload=request_payload,
            intent_executor=intent_executor,
            name_executor=name_executor,
        )
        normalized_row_count, normalized_columns = _resolve_result_table_shape(result=actual_result)
        actual_output = {
            "status": str(actual_result.status),
            "request_hash": query_hash,
            "row_count": int(normalized_row_count),
            "columns": _normalize_golden_query_columns(
                value=normalized_columns,
                label=f"golden_queries[{index}].actual_output.columns",
            ),
        }
        fixed_request_meta = _build_fetch_meta_doc(request_payload, actual_result)
        fixed_request_meta[FETCH_RESULT_META_REQUEST_HASH_FIELD] = query_hash
        fixed_request_meta["row_count"] = int(actual_output["row_count"])
        fixed_request_meta["columns"] = list(actual_output["columns"])
        fixed_request_meta["col_count"] = len(actual_output["columns"])
        fixed_request_artifact = {
            "meta": fixed_request_meta,
            "request_hash": query_hash,
            "row_count": int(actual_output["row_count"]),
            "columns": list(actual_output["columns"]),
        }

        mismatch_fields = [
            field_name
            for field_name in GOLDEN_QUERY_EXPECTED_OUTPUT_FIELDS
            if expected_output[field_name] != actual_output[field_name]
        ]
        regression_status = "regression_detected" if mismatch_fields else "no_regression"
        if mismatch_fields:
            regression_query_ids.append(query_id)

        query_hashes[query_id] = query_hash
        expected_outputs[query_id] = expected_output
        query_outputs[query_id] = actual_output
        fixed_request_artifacts[query_id] = fixed_request_artifact
        query_reports.append(
            {
                "query_id": query_id,
                "query_hash": query_hash,
                "regression_status": regression_status,
                "mismatch_fields": mismatch_fields,
                "expected_output": expected_output,
                "actual_output": actual_output,
                "fixed_request_artifact": fixed_request_artifact,
            }
        )

    sorted_query_ids = sorted(query_hashes)
    regression_query_ids = sorted(set(regression_query_ids))
    return {
        "schema_version": GOLDEN_QUERY_SUMMARY_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "rule": GOLDEN_QUERY_FIXED_SET_RULE,
        "requirement_id": FETCHDATA_IMPL_CORRECTNESS_GOLDEN_QUERIES_REQUIREMENT_ID,
        "source_document": FETCHDATA_IMPL_CORRECTNESS_GOLDEN_QUERIES_SOURCE_DOCUMENT,
        "clause": FETCHDATA_IMPL_CORRECTNESS_GOLDEN_QUERIES_CLAUSE,
        "expected_output_fields": list(GOLDEN_QUERY_EXPECTED_OUTPUT_FIELDS),
        "fixed_request_output_requirement_id": FETCHDATA_IMPL_CORRECTNESS_FIXED_REQUEST_OUTPUT_REQUIREMENT_ID,
        "fixed_request_output_clause": FETCHDATA_IMPL_CORRECTNESS_FIXED_REQUEST_OUTPUT_CLAUSE,
        "fixed_request_artifact_fields": list(GOLDEN_QUERY_FIXED_REQUEST_ARTIFACT_FIELDS),
        "total_queries": len(sorted_query_ids),
        "query_ids": sorted_query_ids,
        "query_hashes": {query_id: query_hashes[query_id] for query_id in sorted_query_ids},
        "expected_outputs": {query_id: expected_outputs[query_id] for query_id in sorted_query_ids},
        "query_outputs": {query_id: query_outputs[query_id] for query_id in sorted_query_ids},
        "fixed_request_artifacts": {
            query_id: fixed_request_artifacts[query_id] for query_id in sorted_query_ids
        },
        "regression_status": "regression_detected" if regression_query_ids else "no_regression",
        "regression_detected": bool(regression_query_ids),
        "regression_query_ids": regression_query_ids,
        "query_reports": sorted(query_reports, key=lambda row: str(row.get("query_id") or "")),
    }


def _execute_golden_query_request(
    *,
    request_payload: dict[str, Any],
    intent_executor: Any,
    name_executor: Any,
) -> FetchExecutionResult:
    if isinstance(request_payload.get("intent"), dict):
        return _call_golden_query_intent_executor(intent_executor=intent_executor, request_payload=request_payload)

    function_name = str(request_payload.get("function") or "").strip()
    if function_name:
        kwargs_obj = request_payload.get("kwargs")
        policy_obj = request_payload.get("policy")
        source_hint = request_payload.get("source_hint")
        public_function = request_payload.get("public_function")
        return _call_golden_query_name_executor(
            name_executor=name_executor,
            function=function_name,
            kwargs=kwargs_obj if isinstance(kwargs_obj, dict) else None,
            policy=policy_obj,
            source_hint=str(source_hint).strip() if isinstance(source_hint, str) and source_hint.strip() else None,
            public_function=(
                str(public_function).strip()
                if isinstance(public_function, str) and str(public_function).strip()
                else None
            ),
        )

    raise ValueError("golden query request must include either intent object or function name")


def _call_golden_query_intent_executor(*, intent_executor: Any, request_payload: dict[str, Any]) -> FetchExecutionResult:
    try:
        parameters = inspect.signature(intent_executor).parameters
    except (TypeError, ValueError):
        parameters = {}
    call_kwargs: dict[str, Any] = {}
    if "write_evidence" in parameters:
        call_kwargs["write_evidence"] = False
    if "_allow_evidence_opt_out" in parameters:
        call_kwargs["_allow_evidence_opt_out"] = True
    return intent_executor(request_payload, **call_kwargs)


def _call_golden_query_name_executor(
    *,
    name_executor: Any,
    function: str,
    kwargs: dict[str, Any] | None,
    policy: Any,
    source_hint: str | None,
    public_function: str | None,
) -> FetchExecutionResult:
    try:
        parameters = inspect.signature(name_executor).parameters
    except (TypeError, ValueError):
        parameters = {}
    call_kwargs: dict[str, Any] = {
        "function": function,
        "kwargs": kwargs,
        "policy": policy,
        "source_hint": source_hint,
        "public_function": public_function,
    }
    if "write_evidence" in parameters:
        call_kwargs["write_evidence"] = False
    if "_allow_evidence_opt_out" in parameters:
        call_kwargs["_allow_evidence_opt_out"] = True
    return name_executor(**call_kwargs)


def _normalize_golden_query_expected_output(
    *,
    output: Any,
    request_hash: str,
    label: str,
) -> dict[str, Any]:
    if not isinstance(output, dict):
        raise ValueError(f"{label} must be an object")
    return _normalize_golden_query_output(
        output=output,
        label=label,
        fallback_request_hash=request_hash,
        require_request_hash=False,
    )


def _normalize_golden_query_output(
    *,
    output: Any,
    label: str,
    fallback_request_hash: str | None,
    require_request_hash: bool,
) -> dict[str, Any]:
    if not isinstance(output, dict):
        raise ValueError(f"{label} must be an object")
    status = str(output.get("status") or "").strip()
    if status not in GOLDEN_QUERY_EXPECTED_STATUS_OPTIONS:
        raise ValueError(f"{label}.status must be one of {list(GOLDEN_QUERY_EXPECTED_STATUS_OPTIONS)}")
    request_hash = _normalize_golden_query_request_hash(
        value=output.get("request_hash"),
        label=f"{label}.request_hash",
        fallback=fallback_request_hash,
        required=require_request_hash,
    )
    row_count = _normalize_non_negative_int(value=output.get("row_count"), label=f"{label}.row_count")
    columns = _normalize_golden_query_columns(value=output.get("columns"), label=f"{label}.columns")
    return {
        "status": status,
        "request_hash": request_hash,
        "row_count": row_count,
        "columns": columns,
    }


def _normalize_golden_query_request_hash(
    *,
    value: Any,
    label: str,
    fallback: str | None,
    required: bool,
) -> str:
    token = str(value).strip() if value is not None else ""
    if not token:
        token = str(fallback or "").strip()
    if not token:
        if required:
            raise ValueError(f"{label} must be a non-empty sha256 token")
        return ""
    if len(token) != 64 or any(ch not in "0123456789abcdefABCDEF" for ch in token):
        raise ValueError(f"{label} must be a 64-char hex sha256 token")
    return token.lower()


def _normalize_non_negative_int(*, value: Any, label: str) -> int:
    try:
        parsed = int(value)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"{label} must be a non-negative integer") from exc
    if parsed < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return parsed


def _normalize_golden_query_columns(*, value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    normalized: list[str] = []
    for idx, item in enumerate(value, start=1):
        token = str(item).strip()
        if not token:
            raise ValueError(f"{label}[{idx}] must be a non-empty string")
        normalized.append(token)
    return sorted(set(normalized))


def build_golden_query_drift_report(
    *,
    baseline_summary: dict[str, Any],
    current_summary: dict[str, Any],
    baseline_summary_path: str | Path | None = None,
    current_summary_path: str | Path | None = None,
) -> dict[str, Any]:
    baseline_hashes = _extract_golden_query_hashes(summary=baseline_summary, label="baseline_summary")
    current_hashes = _extract_golden_query_hashes(summary=current_summary, label="current_summary")
    baseline_outputs = _extract_golden_query_outputs(summary=baseline_summary, label="baseline_summary")
    current_outputs = _extract_golden_query_outputs(summary=current_summary, label="current_summary")

    baseline_ids = set(baseline_hashes)
    current_ids = set(current_hashes)

    added_query_ids = sorted(current_ids - baseline_ids)
    removed_query_ids = sorted(baseline_ids - current_ids)
    changed_query_ids = sorted(
        query_id
        for query_id in (baseline_ids & current_ids)
        if baseline_hashes[query_id] != current_hashes[query_id]
    )
    changed_query_hashes = [
        {
            "query_id": query_id,
            "baseline_hash": baseline_hashes[query_id],
            "current_hash": current_hashes[query_id],
        }
        for query_id in changed_query_ids
    ]

    drift_detected = bool(added_query_ids or removed_query_ids or changed_query_ids)
    regression_query_ids = sorted(
        query_id
        for query_id in (set(baseline_outputs) | set(current_outputs))
        if baseline_outputs.get(query_id) != current_outputs.get(query_id)
    )
    regression_details = [
        {
            "query_id": query_id,
            "baseline_output": baseline_outputs.get(query_id),
            "current_output": current_outputs.get(query_id),
        }
        for query_id in regression_query_ids
    ]
    regression_detected = bool(regression_query_ids)
    return {
        "schema_version": GOLDEN_QUERY_DRIFT_REPORT_SCHEMA_VERSION,
        "rule": GOLDEN_QUERY_DRIFT_REPORT_PATH_RULE,
        "requirement_id": FETCHDATA_IMPL_CORRECTNESS_DRIFT_REPORT_REQUIREMENT_ID,
        "source_document": FETCHDATA_IMPL_CORRECTNESS_DRIFT_REPORT_SOURCE_DOCUMENT,
        "clause": FETCHDATA_IMPL_CORRECTNESS_DRIFT_REPORT_CLAUSE,
        "correctness_requirement_id": FETCHDATA_IMPL_CORRECTNESS_GOLDEN_QUERIES_REQUIREMENT_ID,
        "correctness_source_document": FETCHDATA_IMPL_CORRECTNESS_GOLDEN_QUERIES_SOURCE_DOCUMENT,
        "correctness_clause": FETCHDATA_IMPL_CORRECTNESS_GOLDEN_QUERIES_CLAUSE,
        "fixed_set_rule": GOLDEN_QUERY_FIXED_SET_RULE,
        "expected_output_fields": list(GOLDEN_QUERY_EXPECTED_OUTPUT_FIELDS),
        "minimum_set_rule": FETCHDATA_IMPL_GOLDEN_QUERIES_MIN_SET_RULE,
        "minimum_set_min_queries": GOLDEN_QUERY_MIN_SET_MIN_QUERIES,
        "drift_status": "drift_detected" if drift_detected else "no_drift",
        "drift_detected": drift_detected,
        "baseline_summary_path": _optional_path_as_posix(baseline_summary_path),
        "current_summary_path": _optional_path_as_posix(current_summary_path),
        "baseline_query_count": len(baseline_hashes),
        "current_query_count": len(current_hashes),
        "added_query_ids": added_query_ids,
        "removed_query_ids": removed_query_ids,
        "changed_query_ids": changed_query_ids,
        "changed_query_hashes": changed_query_hashes,
        "regression_status": "regression_detected" if regression_detected else "no_regression",
        "regression_detected": regression_detected,
        "regression_query_ids": regression_query_ids,
        "regression_details": regression_details,
        "overall_status": "pass" if (not drift_detected and not regression_detected) else "fail",
    }


def write_golden_query_drift_report(
    *,
    baseline_summary_path: str | Path,
    current_summary_path: str | Path,
    report_out_path: str | Path,
) -> dict[str, Any]:
    baseline_path = Path(baseline_summary_path)
    current_path = Path(current_summary_path)
    report_path = Path(report_out_path)

    baseline_summary = _load_json_object_from_path(path=baseline_path, label="baseline_summary_path")
    current_summary = _load_json_object_from_path(path=current_path, label="current_summary_path")
    report = build_golden_query_drift_report(
        baseline_summary=baseline_summary,
        current_summary=current_summary,
        baseline_summary_path=baseline_path,
        current_summary_path=current_path,
    )
    report["generated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    report["report_path"] = report_path.as_posix()

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(_json_safe(report), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def _extract_golden_query_hashes(*, summary: dict[str, Any], label: str) -> dict[str, str]:
    schema_version = str(summary.get("schema_version") or "").strip()
    if schema_version != GOLDEN_QUERY_SUMMARY_SCHEMA_VERSION:
        raise ValueError(f"{label}.schema_version must be {GOLDEN_QUERY_SUMMARY_SCHEMA_VERSION}")

    raw_hashes = summary.get("query_hashes")
    if not isinstance(raw_hashes, dict):
        raise ValueError(f"{label}.query_hashes must be an object")

    out: dict[str, str] = {}
    for raw_query_id, raw_hash in raw_hashes.items():
        query_id = str(raw_query_id).strip()
        query_hash = str(raw_hash).strip()
        if not query_id:
            raise ValueError(f"{label}.query_hashes contains empty query_id")
        if not query_hash:
            raise ValueError(f"{label}.query_hashes[{query_id!r}] must be non-empty")
        if query_id in out:
            raise ValueError(f"{label}.query_hashes contains duplicate query_id after normalization: {query_id}")
        out[query_id] = query_hash

    if len(out) < GOLDEN_QUERY_MIN_SET_MIN_QUERIES:
        raise ValueError(
            f"{label}.query_hashes must contain at least {GOLDEN_QUERY_MIN_SET_MIN_QUERIES} query"
        )

    raw_total_queries = summary.get("total_queries")
    if raw_total_queries is not None:
        try:
            total_queries = int(raw_total_queries)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"{label}.total_queries must be an integer") from exc
        if total_queries != len(out):
            raise ValueError(
                f"{label}.total_queries mismatch: expected {len(out)}, got {total_queries}"
            )
    return out


def _extract_golden_query_outputs(*, summary: dict[str, Any], label: str) -> dict[str, dict[str, Any]]:
    raw_outputs = summary.get("query_outputs")
    if raw_outputs is None:
        return {}
    if not isinstance(raw_outputs, dict):
        raise ValueError(f"{label}.query_outputs must be an object when provided")

    out: dict[str, dict[str, Any]] = {}
    for raw_query_id, raw_output in raw_outputs.items():
        query_id = str(raw_query_id).strip()
        if not query_id:
            raise ValueError(f"{label}.query_outputs contains empty query_id")
        if query_id in out:
            raise ValueError(f"{label}.query_outputs contains duplicate query_id after normalization: {query_id}")
        out[query_id] = _normalize_golden_query_output(
            output=raw_output,
            label=f"{label}.query_outputs[{query_id!r}]",
            fallback_request_hash=None,
            require_request_hash=True,
        )
    return out


def _load_json_object_from_path(*, path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"{label} not found: {path.as_posix()}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"{label} is not valid JSON: {path.as_posix()}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object: {path.as_posix()}")
    return payload


def _optional_path_as_posix(path_like: str | Path | None) -> str | None:
    path = _coerce_optional_path(path_like)
    if path is None:
        return None
    return path.as_posix()


def resolve_notebook_kernel_python_executable(*, sys_executable: str | None = None) -> str:
    raw = sys.executable if sys_executable is None else sys_executable
    token = str(raw or "").strip()
    if not token:
        raise ValueError("notebook kernel sys.executable must be non-empty")
    normalized = token.replace("\\", "/")
    if normalized == NOTEBOOK_KERNEL_FORBIDDEN_HOST_EXECUTABLE:
        raise ValueError(
            "notebook kernel execution must use sys.executable and must not use host /usr/bin/python3"
        )
    return token


def build_notebook_kernel_python_command(args: list[str] | tuple[str, ...], *, sys_executable: str | None = None) -> list[str]:
    if not isinstance(args, (list, tuple)):
        raise ValueError("args must be a list or tuple of command arguments")
    argv: list[str] = []
    for raw in args:
        token = str(raw).strip()
        if token:
            argv.append(token)
    return [resolve_notebook_kernel_python_executable(sys_executable=sys_executable), *argv]


def _resolve_required_evidence_path(
    *,
    key: str,
    filename: str,
    fetch_evidence_paths: dict[str, Any],
    fetch_evidence_dir: Path | None,
) -> Path | None:
    raw = fetch_evidence_paths.get(key)
    coerced = _coerce_optional_path(raw)
    if coerced is not None:
        return coerced
    if fetch_evidence_dir is None:
        return None
    return fetch_evidence_dir / filename


def _coerce_optional_path(raw: Any) -> Path | None:
    if raw is None:
        return None
    if isinstance(raw, Path):
        return raw
    if isinstance(raw, str):
        token = raw.strip()
        if not token:
            return None
        return Path(token)
    try:
        candidate = Path(raw)
    except Exception:
        return None
    token = str(candidate).strip()
    if not token:
        return None
    return candidate


def _extract_fetch_request_from_query_envelope(query_envelope: dict[str, Any]) -> dict[str, Any]:
    fetch_request = query_envelope.get("fetch_request")
    if fetch_request is not None:
        if not isinstance(fetch_request, dict):
            raise ValueError("query_envelope.fetch_request must be an object when provided")
        return dict(fetch_request)

    request_markers = {
        "intent",
        "function",
        "kwargs",
        "asset",
        "freq",
        "venue",
        "universe",
        "adjust",
        "symbols",
        "start",
        "end",
        "fields",
        "auto_symbols",
        "sample",
        "strong_control_function",
        "policy",
        "source_hint",
        "public_function",
    }
    if any(key in query_envelope for key in request_markers):
        return dict(query_envelope)

    raise ValueError("query_envelope must include fetch_request or fetch intent/function fields")


def validate_fetch_request_v1(fetch_request: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(fetch_request, dict):
        raise ValueError("fetch_request must be an object")
    _validate_fetch_request_wrapper_contract(fetch_request)
    _validate_fetch_request_v1_intent_contract(fetch_request)
    _validate_fetch_request_v1_logic_contract(fetch_request)
    return dict(fetch_request)


def _validate_fetch_request_v1_fail_fast(fetch_request: dict[str, Any]) -> dict[str, Any]:
    try:
        return validate_fetch_request_v1(fetch_request)
    except ValueError as exc:
        raise ValueError(f"{FETCH_REQUEST_V1_FAIL_FAST_ERROR_PREFIX}: {exc}") from exc


def _coerce_required_fetch_request_selector(
    value: Any,
    *,
    location: str,
    options: tuple[str, ...],
) -> str:
    if not isinstance(value, str):
        supported = ", ".join(options)
        raise ValueError(f"{location} must be one of: {supported}")
    token = value.strip().lower()
    if token not in options:
        supported = ", ".join(options)
        raise ValueError(f"{location} must be one of: {supported}")
    return token


def _coerce_optional_fetch_request_selector(
    value: Any,
    *,
    location: str,
    options: tuple[str, ...],
) -> str | None:
    if value is None:
        return None
    return _coerce_required_fetch_request_selector(value, location=location, options=options)


def _coerce_optional_fetch_request_symbols(value: Any, *, location: str) -> str | list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        token = value.strip()
        return token or None
    if isinstance(value, (list, tuple)):
        normalized: list[str] = []
        for idx, item in enumerate(value):
            if not isinstance(item, str):
                raise ValueError(f"{location}[{idx}] must be a string when provided")
            token = item.strip()
            if token:
                normalized.append(token)
        return normalized
    raise ValueError(f"{location} must be a string or list[str] when provided")


def _resolve_fetch_request_intent_for_validation(fetch_request: dict[str, Any]) -> tuple[dict[str, Any], str] | None:
    intent_obj = fetch_request.get("intent")
    if isinstance(intent_obj, dict):
        merged_intent = dict(intent_obj)
        for key in FETCH_REQUEST_INTENT_FIELD_KEYS:
            if key in merged_intent and merged_intent.get(key) is not None:
                continue
            if fetch_request.get(key) is not None:
                merged_intent[key] = fetch_request.get(key)
        return merged_intent, "fetch_request.intent"

    if _coerce_optional_text(fetch_request.get("function")) is not None:
        return None

    if any(fetch_request.get(key) is not None for key in FETCH_REQUEST_INTENT_FIELD_KEYS):
        return ({key: fetch_request.get(key) for key in FETCH_REQUEST_INTENT_FIELD_KEYS}, "fetch_request")
    return None


def _validate_fetch_request_v1_intent_contract(fetch_request: dict[str, Any]) -> None:
    resolved = _resolve_fetch_request_intent_for_validation(fetch_request)
    if resolved is None:
        return
    intent_obj, intent_location = resolved
    mode_raw = fetch_request.get("mode")
    strict_required = mode_raw is not None

    asset_location = f"{intent_location}.asset"
    freq_location = f"{intent_location}.freq"
    adjust_location = f"{intent_location}.adjust"
    venue_location = f"{intent_location}.venue"
    universe_location = f"{intent_location}.universe"

    asset = _coerce_optional_fetch_request_selector(
        intent_obj.get("asset"),
        location=asset_location,
        options=FETCH_REQUEST_INTENT_VALIDATION_ASSET_OPTIONS,
    )
    freq = _coerce_optional_fetch_request_selector(
        intent_obj.get("freq"),
        location=freq_location,
        options=FETCH_REQUEST_INTENT_VALIDATION_FREQ_OPTIONS,
    )
    _adjust = _coerce_optional_fetch_request_selector(
        intent_obj.get("adjust"),
        location=adjust_location,
        options=FETCH_REQUEST_INTENT_VALIDATION_ADJUST_OPTIONS,
    )

    venue = _normalize_optional_selector(intent_obj.get("venue"))
    universe = _normalize_optional_selector(intent_obj.get("universe"))
    if venue is not None and not isinstance(venue, str):
        raise ValueError(f"{venue_location} must be a non-empty string when provided")
    if universe is not None and not isinstance(universe, str):
        raise ValueError(f"{universe_location} must be a non-empty string when provided")

    if strict_required:
        if asset is None:
            raise ValueError(f"{asset_location} is required when fetch_request.mode is provided")
        if freq is None:
            raise ValueError(f"{freq_location} is required when fetch_request.mode is provided")
        if venue is None and universe is None:
            raise ValueError(f"{intent_location} must include one of: venue, universe")

    _coerce_optional_fetch_request_symbols(intent_obj.get("symbols"), location=f"{intent_location}.symbols")
    _coerce_fields_selector(intent_obj.get("fields"), location=f"{intent_location}.fields")


def _validate_fetch_request_v1_logic_contract(fetch_request: dict[str, Any]) -> None:
    resolved = _resolve_fetch_request_intent_for_validation(fetch_request)
    if resolved is None:
        return

    intent_obj, intent_location = resolved
    mode_raw = fetch_request.get("mode")
    strict_required = mode_raw is not None
    start_location = f"{intent_location}.start"
    end_location = f"{intent_location}.end"

    start = _normalize_window_bound(intent_obj.get("start"))
    end = _normalize_window_bound(intent_obj.get("end"))

    if strict_required:
        if start is None:
            raise ValueError(f"{start_location} is required when fetch_request.mode is provided")
        if end is None:
            raise ValueError(f"{end_location} is required when fetch_request.mode is provided")

    if start is None or end is None:
        return

    start_dt = _parse_dt_for_compare(start)
    end_dt = _parse_dt_for_compare(end)
    if start_dt is not None and end_dt is not None and start_dt > end_dt:
        raise ValueError(f"{start_location} must be <= {end_location}")


def _build_query_result_doc(result: FetchExecutionResult) -> dict[str, Any]:
    return {
        "status": result.status,
        "reason": result.reason,
        "source": "fetch",
        "source_internal": result.source_internal,
        "engine": result.engine,
        "provider_id": result.provider_id,
        "provider_internal": result.provider_internal,
        "resolved_function": result.resolved_function,
        "public_function": result.public_function,
        "elapsed_sec": result.elapsed_sec,
        "row_count": result.row_count,
        "columns": list(result.columns),
        "dtypes": dict(result.dtypes),
        "preview": _json_safe(result.preview),
        "data": _json_safe(result.data),
        "mode": result.mode,
    }


def _resolve_ui_llm_evidence_out_dir(
    *,
    query_envelope: dict[str, Any],
    request_payload: dict[str, Any],
    out_dir: str | Path | None,
    dossier_run_id: str | None = None,
) -> Path:
    resolved_dossier_run_id = _resolve_dossier_run_id(
        explicit_run_id=dossier_run_id,
        request_payload=query_envelope,
    ) or _extract_dossier_run_id_from_mapping(request_payload)
    if resolved_dossier_run_id:
        return _build_dossier_fetch_root_path(resolved_dossier_run_id)
    if out_dir is not None:
        return Path(out_dir)

    query_id = str(query_envelope.get("query_id") or "").strip()
    if query_id:
        token = _sanitize_path_token(query_id)
    else:
        token = _canonical_request_hash(request_payload)
    return DEFAULT_UI_LLM_EVIDENCE_ROOT / token


def _sanitize_path_token(value: str) -> str:
    token = "".join(ch if (ch.isalnum() or ch in {"-", "_"}) else "_" for ch in str(value))
    token = token.strip("_")
    return token or "query"


def _build_dossier_fetch_root_path(dossier_run_id: str) -> Path:
    return DEFAULT_DOSSIER_ROOT / str(dossier_run_id) / DOSSIER_FETCH_SUBDIR_NAME


def _path_within_root(*, path_value: str | Path, root_path: Path) -> bool:
    try:
        Path(path_value).resolve().relative_to(root_path.resolve())
    except ValueError:
        return False
    return True


def _build_ui_dossier_fetch_evidence_payload(
    *,
    dossier_run_id: str | None,
    fetch_evidence_paths: dict[str, Any],
    fetch_review_checkpoint: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if dossier_run_id is None:
        return None

    dossier_fetch_root = _build_dossier_fetch_root_path(dossier_run_id)
    required_paths: dict[str, str] = {}
    for key in UI_DOSSIER_FETCH_EVIDENCE_REQUIRED_PATH_KEYS:
        raw = fetch_evidence_paths.get(key)
        token = str(raw).strip() if isinstance(raw, str) else ""
        if not token:
            raise ValueError(f"dossier fetch evidence payload missing required path key: {key}")
        if not _path_within_root(path_value=token, root_path=dossier_fetch_root):
            raise ValueError(
                "dossier fetch evidence path must stay under dossier fetch root "
                f"({dossier_fetch_root.as_posix()}): {key}={token}"
            )
        required_paths[key] = Path(token).as_posix()

    payload: dict[str, Any] = {
        "run_id": dossier_run_id,
        "read_mode": UI_DOSSIER_FETCH_EVIDENCE_READ_MODE,
        "one_hop_rule": FETCH_EVIDENCE_DOSSIER_ONE_HOP_RULE,
        "path_rule": UI_DOSSIER_FETCH_EVIDENCE_PATH_RULE,
        "fetch_root_path": dossier_fetch_root.as_posix(),
        "required_paths": required_paths,
        "evidence_pointer": required_paths["fetch_result_meta_path"],
    }
    checkpoint = fetch_review_checkpoint if isinstance(fetch_review_checkpoint, dict) else {}
    attempt_views = checkpoint.get("attempts")
    if not isinstance(attempt_views, list):
        fallback_attempt_rows = _load_fetch_attempt_rows(evidence_dir=dossier_fetch_root)
        attempt_views = []
        for attempt_row in fallback_attempt_rows:
            attempt_view = _build_fetch_review_attempt_view(
                evidence_dir=dossier_fetch_root,
                attempt_row=attempt_row,
            )
            if attempt_view is not None:
                attempt_views.append(attempt_view)

    def _to_dossier_path(raw_path: Any) -> str | None:
        candidate = _coerce_optional_path(raw_path)
        if candidate is None:
            return None
        if not candidate.is_absolute():
            if not _path_within_root(path_value=candidate, root_path=dossier_fetch_root):
                candidate = dossier_fetch_root / candidate
        if not _path_within_root(path_value=candidate, root_path=dossier_fetch_root):
            return None
        return candidate.as_posix()

    def _coerce_non_negative_int(raw: Any) -> int:
        try:
            value = int(raw)
        except Exception:
            return 0
        return value if value >= 0 else 0

    attempts_timeline: list[dict[str, Any]] = []
    steps_timeline: list[dict[str, Any]] = []
    for attempt_view in attempt_views:
        if not isinstance(attempt_view, dict):
            continue
        attempt_index = _coerce_attempt_index_token(attempt_view.get("attempt_index"))
        if attempt_index is None:
            continue

        attempt_path = _to_dossier_path(attempt_view.get("attempt_path"))
        if attempt_path is None:
            continue

        attempt_payload = {
            "attempt_index": attempt_index,
            "attempt_path": attempt_path,
            "generated_at": attempt_view.get("generated_at"),
            "is_active": bool(attempt_view.get("is_active")),
            "status": str(attempt_view.get("status") or ""),
            "reason": str(attempt_view.get("reason") or ""),
            "selected_function": str(attempt_view.get("selected_function") or ""),
            "request_hash": _normalize_hash_token(attempt_view.get("request_hash")) or "",
            "preview_hash": str(attempt_view.get("preview_hash") or ""),
            "row_count": _coerce_non_negative_int(attempt_view.get("row_count")),
            "step_count": _coerce_non_negative_int(attempt_view.get("step_count")),
            "required_artifacts_ready": bool(attempt_view.get("required_artifacts_ready")),
        }
        for key in (
            "request_path",
            "result_meta_path",
            "preview_path",
            "steps_index_path",
            "fetch_error_path",
            "error_path",
        ):
            attempt_payload[key] = _to_dossier_path(attempt_view.get(key))
        attempts_timeline.append(attempt_payload)

        steps_index_path = attempt_payload.get("steps_index_path")
        step_payloads = (
            _read_json_file_if_object(Path(steps_index_path)).get("steps")
            if isinstance(steps_index_path, str)
            else []
        )
        if isinstance(step_payloads, list):
            for expected_step_index, step_row in enumerate(step_payloads, start=1):
                if not isinstance(step_row, dict):
                    continue
                step_index = _coerce_attempt_index_token(step_row.get("step_index"))
                if step_index is None:
                    step_index = expected_step_index
                step_payload = {
                    "attempt_index": attempt_index,
                    "attempt_path": attempt_path,
                    "step_index": step_index,
                    "step_kind": str(step_row.get("step_kind") or "step"),
                    "generated_at": step_row.get("generated_at"),
                    "status": str(step_row.get("status") or ""),
                    "trace_id": str(step_row.get("trace_id") or ""),
                }
                for key in ("request_path", "result_meta_path", "preview_path", "error_path"):
                    step_payload[key] = _to_dossier_path(step_row.get(key))
                steps_timeline.append(step_payload)

    rollback_entrypoint = checkpoint.get("rollback_entrypoint") if isinstance(checkpoint.get("rollback_entrypoint"), dict) else {}
    payload[UI_DOSSIER_FETCH_EVIDENCE_ATTEMPTS_FIELD] = attempts_timeline
    payload[UI_DOSSIER_FETCH_EVIDENCE_STEPS_FIELD] = steps_timeline
    payload[UI_DOSSIER_FETCH_EVIDENCE_RETRY_ROLLBACK_FIELD] = {
        "rule": UI_FETCH_EVIDENCE_VIEWER_REVIEW_ROLLBACK_RULE,
        "review_status": str(checkpoint.get("review_status") or ""),
        "active_attempt_index": _coerce_attempt_index_token(checkpoint.get("active_attempt_index")),
        "latest_attempt_index": _coerce_attempt_index_token(checkpoint.get("latest_attempt_index")),
        "latest_preview_hash": _normalize_hash_token(checkpoint.get("latest_preview_hash")) or "",
        "reviewable_changes": checkpoint.get("reviewable_changes"),
        "rollback_entrypoint": {
            "action": str(rollback_entrypoint.get("action") or ""),
            "transition": str(rollback_entrypoint.get("transition") or ""),
            "confirmation_required": bool(rollback_entrypoint.get("confirmation_required")),
            "confirmation_rule": str(rollback_entrypoint.get("confirmation_rule") or ""),
            "target_scope_options": list(rollback_entrypoint.get("target_scope_options") or []),
            "target_attempt_index_options": list(rollback_entrypoint.get("target_attempt_index_options") or []),
            "latest_attempt_index": _coerce_attempt_index_token(rollback_entrypoint.get("latest_attempt_index")),
            "latest_preview_hash": _normalize_hash_token(rollback_entrypoint.get("latest_preview_hash")) or "",
            "target_identity_rule": str(rollback_entrypoint.get("target_identity_rule") or ""),
            "stale_preview_rule": str(rollback_entrypoint.get("stale_preview_rule") or ""),
        },
    }
    raw_error_path = fetch_evidence_paths.get("fetch_error_path")
    if isinstance(raw_error_path, str) and raw_error_path.strip():
        if not _path_within_root(path_value=raw_error_path, root_path=dossier_fetch_root):
            raise ValueError(
                "dossier fetch evidence path must stay under dossier fetch root "
                f"({dossier_fetch_root.as_posix()}): fetch_error_path={raw_error_path}"
            )
        payload["fetch_error_path"] = Path(raw_error_path).as_posix()
    return payload


def _step_evidence_filename(template: str, *, step_index: int) -> str:
    return str(template).format(step_index=int(step_index))


def _validate_fetch_result_meta_payload(meta_payload: dict[str, Any]) -> dict[str, Any]:
    if _contracts_validate is None:
        return meta_payload
    validate_result = _contracts_validate.validate_fetch_result_meta(meta_payload)
    if validate_result[0] != _contracts_validate.EXIT_OK:
        raise ValueError(
            f"{FETCH_RESULT_META_PRE_ORCHESTRATOR_VALIDATION_ERROR_PREFIX}{validate_result[1]}"
        )
    return meta_payload


def _build_fetch_meta_doc(request_payload: dict[str, Any], result: FetchExecutionResult) -> dict[str, Any]:
    meta = asdict(result)
    meta.pop("data", None)
    meta["source"] = "fetch"
    meta[FETCH_RESULT_META_ENGINE_FIELD] = _resolve_result_engine(request_payload=request_payload, result=result)
    min_ts, max_ts = _extract_time_bounds_from_preview(result.preview)
    as_of = _extract_request_as_of(request_payload)
    availability_summary = _build_availability_summary(preview=result.preview, as_of=as_of)
    sanity_checks = _build_preview_sanity_checks(
        result.preview,
        dtypes=result.dtypes,
        columns=result.columns,
    )
    sanity_checks = _annotate_empty_data_policy_consistency(
        sanity_checks=sanity_checks,
        request_payload=request_payload,
        result=result,
    )
    meta[FETCH_RESULT_META_SELECTED_FUNCTION_FIELD] = _resolve_selected_function(
        request_payload=request_payload,
        result=result,
    )
    normalized_row_count, normalized_columns = _resolve_result_table_shape(result=result)
    meta["columns"] = normalized_columns
    row_count_key, col_count_key = FETCH_RESULT_META_ROW_COL_COUNT_FIELDS
    meta[row_count_key] = int(normalized_row_count)
    meta[col_count_key] = len(normalized_columns)
    request_hash_key = FETCH_RESULT_META_REQUEST_HASH_FIELD
    meta[request_hash_key] = _canonical_request_hash(request_payload)
    meta[FETCH_RESULT_META_COVERAGE_FIELD] = _build_coverage_summary(request_payload, result.preview)
    min_ts_key, max_ts_key = FETCH_RESULT_META_MIN_MAX_TS_FIELDS
    meta[min_ts_key] = min_ts
    meta[max_ts_key] = max_ts
    meta[FETCH_RESULT_META_AS_OF_FIELD] = as_of
    meta[FETCH_RESULT_META_AVAILABILITY_SUMMARY_FIELD] = availability_summary
    meta["probe_status"] = _resolve_required_probe_status(result.status)
    meta["sanity_checks"] = sanity_checks
    meta["gate_input_summary"] = _build_gate_input_summary(
        request_hash=meta[request_hash_key],
        availability_summary=availability_summary,
        sanity_checks=sanity_checks,
    )
    warnings: list[str] = []
    if result.status in {STATUS_BLOCKED_SOURCE_MISSING, STATUS_ERROR_RUNTIME} and result.reason:
        warnings.append(str(result.reason))
    elif result.status == STATUS_PASS_EMPTY:
        warnings.append("no_data")
    meta[FETCH_RESULT_META_WARNINGS_FIELD] = warnings
    return _validate_fetch_result_meta_payload(meta)


def _resolve_result_table_shape(*, result: FetchExecutionResult) -> tuple[int, list[str]]:
    row_count = max(0, int(result.row_count))
    columns = [str(col) for col in list(result.columns) if str(col)]

    if result.data is not None:
        _, _, normalized_rows, normalized_columns, _, _ = _normalize_payload(result.data)
        row_count = max(0, int(normalized_rows))
        if normalized_columns:
            columns = normalized_columns
    elif not columns and result.preview is not None:
        _, _, preview_rows, preview_columns, _, _ = _normalize_payload(result.preview)
        if row_count <= 0:
            row_count = max(0, int(preview_rows))
        if preview_columns:
            columns = preview_columns

    return row_count, columns


def _resolve_selected_function(*, request_payload: dict[str, Any], result: FetchExecutionResult) -> str | None:
    candidates: list[Any] = [result.resolved_function, result.public_function]
    if isinstance(request_payload, dict):
        candidates.extend([request_payload.get("function"), request_payload.get("public_function")])
        intent_obj = request_payload.get("intent")
        if isinstance(intent_obj, dict):
            candidates.extend([intent_obj.get("function_override"), intent_obj.get("public_function")])
    for raw in candidates:
        if isinstance(raw, str):
            token = raw.strip()
            if token:
                return token
    return None


def _resolve_result_engine(*, request_payload: dict[str, Any], result: FetchExecutionResult) -> str | None:
    candidates: list[str | None] = [
        result.engine,
        _engine_from_source(result.source_internal),
        _engine_from_source(result.provider_internal),
    ]
    for raw in candidates:
        if not isinstance(raw, str):
            continue
        token = raw.strip().lower()
        if token in FETCH_RESULT_META_ENGINE_OPTIONS:
            return token
    return None


def _resolve_optional_probe_status(status: str | None) -> str | None:
    if not isinstance(status, str):
        return None
    token = status.strip()
    if token in FETCH_RESULT_META_OPTIONAL_PROBE_STATUS_OPTIONS:
        return token
    return None


def _resolve_required_probe_status(status: str | None) -> str:
    if not isinstance(status, str):
        raise ValueError("fetch_result_meta probe_status requires a non-empty status")
    token = status.strip()
    if token in GOLDEN_QUERY_EXPECTED_STATUS_OPTIONS:
        return token
    raise ValueError(f"fetch_result_meta probe_status unsupported status: {status}")


def _canonical_request_hash(request_payload: dict[str, Any]) -> str:
    canonical = _json_safe(request_payload)
    hash_input = {
        "request_hash_version": FETCH_RESULT_META_REQUEST_HASH_VERSION_SALT,
        "request_payload": canonical,
    }
    encoded = json.dumps(hash_input, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _normalize_symbols(value: Any) -> list[str]:
    if isinstance(value, str):
        s = value.strip()
        return [s] if s else []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, str):
                s = item.strip()
                if s:
                    out.append(s)
        return out
    return []


def _extract_request_symbols(request_payload: dict[str, Any]) -> list[str]:
    intent_obj = request_payload.get("intent")
    kwargs_obj = request_payload.get("kwargs")
    values: list[str] = []
    values.extend(_normalize_symbols(request_payload.get("symbols")))
    if isinstance(intent_obj, dict):
        values.extend(_normalize_symbols(intent_obj.get("symbols")))
        extra_obj = intent_obj.get("extra_kwargs")
        if isinstance(extra_obj, dict):
            values.extend(_normalize_symbols(extra_obj.get("symbol")))
            values.extend(_normalize_symbols(extra_obj.get("symbols")))
            values.extend(_normalize_symbols(extra_obj.get("code")))
    if isinstance(kwargs_obj, dict):
        values.extend(_normalize_symbols(kwargs_obj.get("symbol")))
        values.extend(_normalize_symbols(kwargs_obj.get("symbols")))
        values.extend(_normalize_symbols(kwargs_obj.get("code")))
    deduped = sorted({x for x in values if x})
    return deduped


def _extract_observed_symbols(preview: Any) -> list[str]:
    if not isinstance(preview, list):
        return []
    out: set[str] = set()
    for row in preview:
        if not isinstance(row, dict):
            continue
        for key in ("code", "symbol", "symbols", "ticker"):
            if key in row:
                out.update(_normalize_symbols(row.get(key)))
    return sorted(out)


def _extract_time_bounds_from_preview(preview: Any) -> tuple[str | None, str | None]:
    if not isinstance(preview, list):
        return None, None
    stamps: list[str] = []
    for row in preview:
        if not isinstance(row, dict):
            continue
        for key in ("date", "datetime", "trade_date", "dt", "timestamp"):
            raw = row.get(key)
            if raw is None:
                continue
            val = _json_safe(raw)
            sval = str(val).strip()
            if sval:
                stamps.append(sval)
    if not stamps:
        return None, None
    ordered = sorted(stamps)
    return ordered[0], ordered[-1]


def _build_coverage_summary(request_payload: dict[str, Any], preview: Any) -> dict[str, Any]:
    requested = _extract_request_symbols(request_payload)
    observed = _extract_observed_symbols(preview)
    requested_set = set(requested)
    observed_set = set(observed)
    covered = sorted(requested_set & observed_set)
    missing = sorted(requested_set - observed_set)
    requested_count = len(requested)
    if requested_count > 0:
        coverage_ratio = round(len(covered) / requested_count, 6)
        missing_ratio = round(len(missing) / requested_count, 6)
    else:
        coverage_ratio = 1.0
        missing_ratio = 0.0
    return {
        "symbol_coverage_scope": FETCH_RESULT_META_COVERAGE_SYMBOL_SCOPE,
        "reporting_granularity": FETCH_RESULT_META_COVERAGE_REPORTING_GRANULARITY,
        "symbol_missing_rate_formula": FETCH_RESULT_META_COVERAGE_MISSING_RATE_FORMULA,
        "empty_request_policy": FETCH_RESULT_META_COVERAGE_EMPTY_REQUEST_POLICY,
        "requested_symbol_count": requested_count,
        "requested_symbols": requested,
        "observed_symbol_count": len(observed),
        "observed_symbols": observed,
        "covered_symbol_count": len(covered),
        "covered_symbols": covered,
        "missing_symbol_count": len(missing),
        "missing_symbols": missing,
        "symbol_missing_rate_numerator": len(missing),
        "symbol_missing_rate_denominator": requested_count,
        "symbol_coverage_rate": coverage_ratio,
        "symbol_missing_rate": missing_ratio,
        "symbol_coverage_ratio": coverage_ratio,
        "symbol_missing_ratio": missing_ratio,
    }


def _pick_timestamp_field(preview: Any) -> str:
    if not isinstance(preview, list):
        return ""
    candidates = ("date", "datetime", "trade_date", "dt", "timestamp")
    for key in candidates:
        for row in preview:
            if isinstance(row, dict) and key in row:
                return key
    return ""


def _timestamp_duplicate_policy_allows_duplicates(policy: str) -> bool:
    token = str(policy or "").strip().lower()
    return token in {"allow_duplicates", "allow_duplicates_with_audit_record"}


def _normalize_declared_dtype_family(dtype_name: Any) -> str:
    token = str(dtype_name or "").strip().lower()
    if not token:
        return "unknown"
    if any(part in token for part in ("datetime", "timestamp", "date", "time64")):
        return "datetime"
    if "bool" in token:
        return "bool"
    if any(part in token for part in ("int", "float", "double", "decimal", "numeric", "number", "long", "short")):
        return "numeric"
    if any(part in token for part in ("str", "string", "object", "category", "text")):
        return "string"
    return "unknown"


def _is_numeric_string_token(token: str) -> bool:
    if not token:
        return False
    lowered = token.lower()
    if lowered in {"nan", "+nan", "-nan", "inf", "+inf", "-inf", "infinity", "+infinity", "-infinity"}:
        return False
    try:
        float(token)
    except Exception:
        return False
    return True


def _is_datetime_string_token(token: str) -> bool:
    if not token:
        return False
    normalized = token.replace("Z", "+00:00")
    try:
        datetime.fromisoformat(normalized)
        return True
    except Exception:
        pass
    try:
        date.fromisoformat(token)
        return True
    except Exception:
        return False


def _classify_preview_value_family(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        if isinstance(value, float) and value != value:
            return None
        return "numeric"
    if isinstance(value, (datetime, date)):
        return "datetime"
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        if _is_datetime_string_token(stripped):
            return "datetime_string"
        if _is_numeric_string_token(stripped):
            return "numeric_string"
        return "text_string"
    if isinstance(value, (dict, list, tuple, set)):
        return "object"
    return "unknown"


def _is_dtype_family_compatible_with_observed(*, declared_family: str, observed_families: set[str]) -> bool:
    if not observed_families:
        return True
    if declared_family in {"string", "unknown"}:
        return True
    if declared_family == "numeric":
        return observed_families.issubset({"numeric", "numeric_string"})
    if declared_family == "datetime":
        return observed_families.issubset({"datetime", "datetime_string"})
    if declared_family == "bool":
        return observed_families.issubset({"bool", "numeric", "numeric_string"})
    return True


def _build_dtype_reasonableness_summary(
    *,
    rows: list[dict[str, Any]],
    dtypes: dict[str, Any] | None,
    columns: list[str] | tuple[str, ...] | None,
) -> dict[str, Any]:
    declared_dtypes: dict[str, str] = {}
    if isinstance(dtypes, dict):
        for col, dtype_name in dtypes.items():
            col_token = str(col).strip()
            if not col_token:
                continue
            dtype_token = str(dtype_name or "").strip()
            if not dtype_token:
                continue
            declared_dtypes[col_token] = dtype_token

    observed_columns: set[str] = set()
    for row in rows:
        observed_columns.update(str(key) for key in row.keys() if str(key))

    expected_columns: set[str] = set()
    if isinstance(columns, (list, tuple)):
        expected_columns.update(str(col) for col in columns if str(col))

    all_columns = sorted(observed_columns | set(declared_dtypes.keys()) | expected_columns)
    mismatch_columns: list[str] = []
    untyped_columns: list[str] = []
    unknown_declared_columns: list[str] = []
    checked_column_count = 0

    for col in all_columns:
        observed_families: set[str] = set()
        for row in rows:
            if col not in row:
                continue
            family = _classify_preview_value_family(row.get(col))
            if family is not None:
                observed_families.add(family)

        declared_dtype = declared_dtypes.get(col)
        if not declared_dtype:
            if observed_families:
                untyped_columns.append(col)
            continue

        declared_family = _normalize_declared_dtype_family(declared_dtype)
        if declared_family == "unknown":
            unknown_declared_columns.append(col)
            continue

        checked_column_count += 1
        if not _is_dtype_family_compatible_with_observed(
            declared_family=declared_family,
            observed_families=observed_families,
        ):
            mismatch_columns.append(col)

    mismatch_columns = sorted(set(mismatch_columns))
    untyped_columns = sorted(set(untyped_columns))
    unknown_declared_columns = sorted(set(unknown_declared_columns))
    return {
        "dtype_reasonableness_rule": SANITY_DTYPE_REASONABLENESS_RULE,
        "dtype_reasonable": len(mismatch_columns) == 0,
        "dtype_mismatch_columns": mismatch_columns,
        "dtype_untyped_columns": untyped_columns,
        "dtype_unknown_declared_columns": unknown_declared_columns,
        "dtype_checked_column_count": checked_column_count,
    }


def _build_preview_sanity_checks(
    preview: Any,
    *,
    dtypes: dict[str, Any] | None = None,
    columns: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    duplicate_policy = SANITY_TIMESTAMP_DUPLICATE_POLICY
    duplicates_allowed = _timestamp_duplicate_policy_allows_duplicates(duplicate_policy)
    if not isinstance(preview, list):
        dtype_summary = _build_dtype_reasonableness_summary(rows=[], dtypes=dtypes, columns=columns)
        return {
            "timestamp_field": "",
            "timestamp_order_rule": SANITY_TIMESTAMP_ORDER_RULE,
            "timestamp_duplicate_policy": duplicate_policy,
            "timestamp_duplicates_allowed": duplicates_allowed,
            "timestamp_order_compare_mode": SANITY_TIMESTAMP_ORDER_COMPARE_MODE,
            "timestamp_total_count": 0,
            "timestamp_parseable_count": 0,
            "timestamp_monotonic_non_decreasing": True,
            "timestamp_duplicate_count": 0,
            "timestamp_rule_satisfied": True,
            "missing_ratio_rule": SANITY_MISSING_RATIO_RULE,
            "missing_ratio_by_column": {},
            "preview_row_count": 0,
            **dtype_summary,
        }

    rows = [row for row in preview if isinstance(row, dict)]
    row_count = len(rows)
    dtype_summary = _build_dtype_reasonableness_summary(rows=rows, dtypes=dtypes, columns=columns)
    if row_count == 0:
        return {
            "timestamp_field": "",
            "timestamp_order_rule": SANITY_TIMESTAMP_ORDER_RULE,
            "timestamp_duplicate_policy": duplicate_policy,
            "timestamp_duplicates_allowed": duplicates_allowed,
            "timestamp_order_compare_mode": SANITY_TIMESTAMP_ORDER_COMPARE_MODE,
            "timestamp_total_count": 0,
            "timestamp_parseable_count": 0,
            "timestamp_monotonic_non_decreasing": True,
            "timestamp_duplicate_count": 0,
            "timestamp_rule_satisfied": True,
            "missing_ratio_rule": SANITY_MISSING_RATIO_RULE,
            "missing_ratio_by_column": {},
            "preview_row_count": 0,
            **dtype_summary,
        }

    ts_field = _pick_timestamp_field(rows)
    ts_values: list[str] = []
    ts_normalized: list[str] = []
    parsed_cache: dict[str, datetime | None] = {}
    parseable_count = 0

    def _parse_ts_token(token: str) -> datetime | None:
        cached = parsed_cache.get(token)
        if cached is not None or token in parsed_cache:
            return cached
        parsed = _parse_dt_for_compare(token)
        parsed_cache[token] = parsed
        return parsed

    if ts_field:
        for row in rows:
            if ts_field not in row:
                continue
            val = row.get(ts_field)
            if val is None:
                continue
            sval = str(_json_safe(val)).strip()
            if sval:
                ts_values.append(sval)
                parsed = _parse_ts_token(sval)
                if parsed is not None:
                    parseable_count += 1
                    ts_normalized.append(_format_datetime_utc_z(parsed))
                else:
                    ts_normalized.append(sval)

    monotonic = True
    for idx in range(1, len(ts_values)):
        prev_token = ts_values[idx - 1]
        curr_token = ts_values[idx]
        prev_dt = _parse_ts_token(prev_token)
        curr_dt = _parse_ts_token(curr_token)
        if prev_dt is not None and curr_dt is not None:
            out_of_order = curr_dt < prev_dt
        else:
            out_of_order = curr_token < prev_token
        if out_of_order:
            monotonic = False
            break
    duplicate_count = len(ts_normalized) - len(set(ts_normalized))
    timestamp_rule_satisfied = monotonic and (duplicates_allowed or duplicate_count == 0)

    all_cols: set[str] = set()
    for row in rows:
        all_cols.update(str(k) for k in row.keys())

    missing_ratio: dict[str, float] = {}
    for col in sorted(all_cols):
        miss = 0
        for row in rows:
            val = row.get(col) if col in row else None
            if val is None:
                miss += 1
                continue
            if isinstance(val, str) and not val.strip():
                miss += 1
        missing_ratio[col] = round(miss / row_count, 6)

    return {
        "timestamp_field": ts_field,
        "timestamp_order_rule": SANITY_TIMESTAMP_ORDER_RULE,
        "timestamp_duplicate_policy": duplicate_policy,
        "timestamp_duplicates_allowed": duplicates_allowed,
        "timestamp_order_compare_mode": SANITY_TIMESTAMP_ORDER_COMPARE_MODE,
        "timestamp_total_count": len(ts_values),
        "timestamp_parseable_count": parseable_count,
        "timestamp_monotonic_non_decreasing": monotonic,
        "timestamp_duplicate_count": int(duplicate_count),
        "timestamp_rule_satisfied": timestamp_rule_satisfied,
        "missing_ratio_rule": SANITY_MISSING_RATIO_RULE,
        "missing_ratio_by_column": missing_ratio,
        "preview_row_count": row_count,
        **dtype_summary,
    }


def _annotate_empty_data_policy_consistency(
    *,
    sanity_checks: dict[str, Any],
    request_payload: dict[str, Any],
    result: FetchExecutionResult,
) -> dict[str, Any]:
    out = dict(sanity_checks)
    on_no_data = _extract_request_on_no_data_policy(request_payload)
    expected_status = _expected_terminal_status_on_no_data(on_no_data)
    no_data_terminal = _is_no_data_terminal_outcome(result)
    out["empty_data_policy_rule"] = SANITY_EMPTY_DATA_POLICY_RULE
    out["on_no_data_policy"] = on_no_data
    if no_data_terminal:
        out["empty_data_expected_status"] = expected_status
        out["empty_data_observed_status"] = result.status
    out["empty_data_semantics_consistent"] = (result.status == expected_status) if no_data_terminal else True
    return out


def _extract_request_on_no_data_policy(request_payload: dict[str, Any]) -> str:
    policy_obj = request_payload.get("policy")
    raw_policy = policy_obj.get("on_no_data") if isinstance(policy_obj, dict) else None
    token = str(raw_policy or "pass_empty").strip().lower()
    if not token or token not in SUPPORTED_ON_NO_DATA_POLICIES:
        return "pass_empty"
    return token


def _expected_terminal_status_on_no_data(on_no_data: str) -> str:
    if on_no_data == "error":
        return STATUS_ERROR_RUNTIME
    return STATUS_PASS_EMPTY


def _reason_is_no_data(reason: Any) -> bool:
    if not isinstance(reason, str):
        return False
    token = reason.strip().lower()
    return token == "no_data" or token.startswith("no_data:")


def _is_no_data_terminal_outcome(result: FetchExecutionResult) -> bool:
    if result.status == STATUS_PASS_HAS_DATA:
        return False
    if result.status == STATUS_PASS_EMPTY:
        return True
    return _reason_is_no_data(result.reason)


def _build_gate_input_summary(
    *,
    request_hash: str,
    availability_summary: dict[str, Any],
    sanity_checks: dict[str, Any],
) -> dict[str, Any]:
    no_lookahead_gate, snapshot_integrity_gate = GATERUNNER_REQUIRED_GATES
    has_as_of = bool(availability_summary.get("has_as_of"))
    available_at_field_present = bool(availability_summary.get("available_at_field_present"))

    try:
        available_at_violation_count = int(availability_summary.get("available_at_violation_count") or 0)
    except Exception:
        available_at_violation_count = 0
    available_at_violation_count = max(0, available_at_violation_count)

    try:
        preview_row_count = int(sanity_checks.get("preview_row_count") or 0)
    except Exception:
        preview_row_count = 0
    preview_row_count = max(0, preview_row_count)

    timestamp_field = str(sanity_checks.get("timestamp_field") or "")
    timestamp_order_rule = str(sanity_checks.get("timestamp_order_rule") or SANITY_TIMESTAMP_ORDER_RULE)
    timestamp_duplicate_policy = str(sanity_checks.get("timestamp_duplicate_policy") or SANITY_TIMESTAMP_DUPLICATE_POLICY)
    timestamp_duplicates_allowed = bool(
        sanity_checks.get(
            "timestamp_duplicates_allowed",
            _timestamp_duplicate_policy_allows_duplicates(timestamp_duplicate_policy),
        )
    )
    timestamp_order_compare_mode = str(
        sanity_checks.get("timestamp_order_compare_mode") or SANITY_TIMESTAMP_ORDER_COMPARE_MODE
    )
    try:
        timestamp_total_count = int(sanity_checks.get("timestamp_total_count") or 0)
    except Exception:
        timestamp_total_count = 0
    timestamp_total_count = max(0, timestamp_total_count)
    try:
        timestamp_parseable_count = int(sanity_checks.get("timestamp_parseable_count") or 0)
    except Exception:
        timestamp_parseable_count = 0
    timestamp_parseable_count = max(0, timestamp_parseable_count)
    timestamp_monotonic_non_decreasing = bool(sanity_checks.get("timestamp_monotonic_non_decreasing", True))

    try:
        timestamp_duplicate_count = int(sanity_checks.get("timestamp_duplicate_count") or 0)
    except Exception:
        timestamp_duplicate_count = 0
    timestamp_duplicate_count = max(0, timestamp_duplicate_count)
    timestamp_rule_satisfied = bool(
        sanity_checks.get(
            "timestamp_rule_satisfied",
            timestamp_monotonic_non_decreasing and timestamp_duplicate_count == 0,
        )
    )

    nonzero_missing_ratio_columns: list[str] = []
    missing_ratio_by_column = sanity_checks.get("missing_ratio_by_column")
    if isinstance(missing_ratio_by_column, dict):
        for col, ratio in missing_ratio_by_column.items():
            try:
                value = float(ratio)
            except Exception:
                continue
            if value > 0:
                nonzero_missing_ratio_columns.append(str(col))
    nonzero_missing_ratio_columns = sorted(set(nonzero_missing_ratio_columns))

    dtype_reasonable = bool(sanity_checks.get("dtype_reasonable", True))
    dtype_mismatch_columns: list[str] = []
    raw_dtype_mismatch_columns = sanity_checks.get("dtype_mismatch_columns")
    if isinstance(raw_dtype_mismatch_columns, list):
        for col in raw_dtype_mismatch_columns:
            token = str(col).strip()
            if token:
                dtype_mismatch_columns.append(token)
    dtype_mismatch_columns = sorted(set(dtype_mismatch_columns))

    return {
        no_lookahead_gate: {
            "rule": str(availability_summary.get("rule") or TIME_TRAVEL_AVAILABILITY_RULE),
            "has_as_of": has_as_of,
            "available_at_field_present": available_at_field_present,
            "available_at_violation_count": available_at_violation_count,
        },
        snapshot_integrity_gate: {
            "request_hash": request_hash,
            "preview_row_count": preview_row_count,
            "timestamp_field": timestamp_field,
            "timestamp_order_rule": timestamp_order_rule,
            "timestamp_duplicate_policy": timestamp_duplicate_policy,
            "timestamp_duplicates_allowed": timestamp_duplicates_allowed,
            "timestamp_order_compare_mode": timestamp_order_compare_mode,
            "timestamp_total_count": timestamp_total_count,
            "timestamp_parseable_count": timestamp_parseable_count,
            "timestamp_monotonic_non_decreasing": timestamp_monotonic_non_decreasing,
            "timestamp_duplicate_count": timestamp_duplicate_count,
            "timestamp_rule_satisfied": timestamp_rule_satisfied,
            "nonzero_missing_ratio_columns": nonzero_missing_ratio_columns,
            "dtype_reasonable": dtype_reasonable,
            "dtype_mismatch_columns": dtype_mismatch_columns,
        },
    }


def _extract_request_as_of(request_payload: dict[str, Any]) -> str | None:
    candidates: list[Any] = [request_payload.get("as_of")]
    intent_obj = request_payload.get("intent")
    if isinstance(intent_obj, dict):
        candidates.append(intent_obj.get("as_of"))
    kwargs_obj = request_payload.get("kwargs")
    if isinstance(kwargs_obj, dict):
        candidates.append(kwargs_obj.get("as_of"))
    fallback_raw: str | None = None
    for raw in candidates:
        if raw is None:
            continue
        sval = str(_json_safe(raw)).strip()
        if sval:
            normalized = _normalize_as_of_to_utc(raw)
            if normalized is not None:
                return normalized
            if fallback_raw is None:
                fallback_raw = sval
    return fallback_raw


def _format_datetime_utc_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _normalize_as_of_to_utc(raw: Any) -> str | None:
    sval = str(_json_safe(raw)).strip()
    if not sval:
        return None
    parsed = _parse_dt_for_compare(sval)
    if parsed is None:
        return None
    return _format_datetime_utc_z(parsed)


def _parse_dt_for_compare(raw: str) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except Exception:
        if len(text) == 10 and text.count("-") == 2:
            try:
                return datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except Exception:
                return None
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _has_available_at_value(raw: Any) -> bool:
    safe_raw = _json_safe(raw)
    if safe_raw is None:
        return False
    return bool(str(safe_raw).strip())


def _available_at_exceeds_as_of(raw: Any, *, as_of_dt: datetime) -> bool:
    if not _has_available_at_value(raw):
        return True
    text = str(_json_safe(raw)).strip()
    available_dt = _parse_dt_for_compare(text)
    if available_dt is None:
        return True
    return available_dt > as_of_dt


def _apply_datacatalog_available_at_as_of_guard(*, payload: Any, as_of: str | None) -> tuple[Any, bool]:
    as_of_dt = _parse_dt_for_compare(as_of or "")
    if as_of_dt is None:
        return payload, False

    try:
        import pandas as pd
    except Exception:
        pd = None

    if pd is not None and isinstance(payload, pd.DataFrame):
        if "available_at" not in payload.columns:
            return payload, False
        has_available_at = bool(payload["available_at"].map(_has_available_at_value).any())
        if not has_available_at:
            return payload, False
        keep_mask = payload["available_at"].map(
            lambda value: not _available_at_exceeds_as_of(value, as_of_dt=as_of_dt)
        )
        filtered = payload.loc[keep_mask].copy()
        time_travel_unavailable = bool(int(len(payload.index)) > 0 and int(len(filtered.index)) <= 0)
        return filtered, time_travel_unavailable

    if isinstance(payload, list):
        dict_rows = [row for row in payload if isinstance(row, dict)]
        has_available_at = any(
            "available_at" in row and _has_available_at_value(row.get("available_at"))
            for row in dict_rows
        )
        if not has_available_at:
            return payload, False
        filtered_rows: list[Any] = []
        eligible_dict_rows = 0
        for row in payload:
            if isinstance(row, dict):
                if _available_at_exceeds_as_of(row.get("available_at"), as_of_dt=as_of_dt):
                    continue
                eligible_dict_rows += 1
            filtered_rows.append(row)
        time_travel_unavailable = bool(dict_rows and eligible_dict_rows <= 0)
        return filtered_rows, time_travel_unavailable

    return payload, False


def _apply_no_lookahead_to_payload(*, payload: Any, as_of: str | None) -> tuple[Any, bool]:
    return _apply_datacatalog_available_at_as_of_guard(payload=payload, as_of=as_of)


def _build_availability_summary(*, preview: Any, as_of: str | None) -> dict[str, Any]:
    out = {
        "has_as_of": as_of is not None,
        "as_of": as_of,
        "available_at_field_present": False,
        "available_at_min": None,
        "available_at_max": None,
        "available_at_violation_count": 0,
        "rule": TIME_TRAVEL_AVAILABILITY_RULE,
    }
    if not isinstance(preview, list):
        return out

    rows = [row for row in preview if isinstance(row, dict)]
    if not rows:
        return out

    if not any("available_at" in row for row in rows):
        return out

    out["available_at_field_present"] = True
    available_rows: list[str] = []
    available_rows_dt: list[datetime] = []
    for row in rows:
        val = row.get("available_at")
        if val is None:
            continue
        sval = str(_json_safe(val)).strip()
        if sval:
            available_rows.append(sval)
            parsed = _parse_dt_for_compare(sval)
            if parsed is not None:
                available_rows_dt.append(parsed)
    if not available_rows:
        return out

    if available_rows_dt:
        ordered_dt = sorted(available_rows_dt)
        out["available_at_min"] = _format_datetime_utc_z(ordered_dt[0])
        out["available_at_max"] = _format_datetime_utc_z(ordered_dt[-1])
    else:
        ordered = sorted(available_rows)
        out["available_at_min"] = ordered[0]
        out["available_at_max"] = ordered[-1]

    as_of_dt = _parse_dt_for_compare(as_of or "")
    if as_of_dt is None:
        return out

    violations = 0
    for row_val in available_rows:
        av_dt = _parse_dt_for_compare(row_val)
        if av_dt is None:
            continue
        if av_dt > as_of_dt:
            violations += 1
    out["available_at_violation_count"] = violations
    return out


def load_smoke_window_profile(path: str | Path = DEFAULT_WINDOW_PROFILE_PATH) -> dict[str, dict[str, Any]]:
    p = Path(path)
    if not p.is_file():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    _validate_smoke_window_profile_notebook_ref_contract(path=p, payload=payload)
    rows = payload.get("functions") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        fn = str(row.get("function", "")).strip()
        if not fn:
            continue
        out[fn] = row
    return out


def _validate_smoke_window_profile_notebook_ref_contract(*, path: Path, payload: Any) -> None:
    if not isinstance(payload, dict):
        return
    raw_notebook_ref = payload.get("notebook_ref")
    if raw_notebook_ref is None:
        return

    notebook_ref = str(raw_notebook_ref).strip().replace("\\", "/")
    if not notebook_ref:
        raise ValueError(
            "smoke window profile notebook_ref contract missing: "
            f"expected={NOTEBOOK_KERNEL_MANUAL_PARAMS_NOTEBOOK_PATH} path={path.as_posix()}"
        )
    if notebook_ref != NOTEBOOK_KERNEL_MANUAL_PARAMS_NOTEBOOK_PATH:
        raise ValueError(
            "smoke window profile notebook_ref mismatch: "
            f"expected={NOTEBOOK_KERNEL_MANUAL_PARAMS_NOTEBOOK_PATH} got={notebook_ref} path={path.as_posix()}"
        )


def load_probe_summary(path: str | Path = DEFAULT_PROBE_SUMMARY_PATH) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    _validate_probe_summary_pass_has_data_contract(path=p, payload=payload)
    _validate_probe_summary_pass_empty_contract(path=p, payload=payload)
    _validate_probe_summary_callable_runtime_contract(path=p, payload=payload)
    _validate_probe_summary_notebook_params_data_contract(path=p, payload=payload)
    return payload


def _validate_probe_summary_pass_has_data_contract(*, path: Path, payload: dict[str, Any]) -> None:
    declared_total = payload.get("total")
    try:
        total = int(declared_total)
    except Exception:
        return
    if total != BASELINE_FUNCTION_COUNT:
        return

    pass_has_data = _extract_probe_status_count(payload, STATUS_PASS_HAS_DATA)
    if pass_has_data is None:
        raise ValueError(
            "probe summary baseline pass_has_data contract missing: "
            f"expected={BASELINE_PASS_HAS_DATA_COUNT} path={path.as_posix()}"
        )
    if pass_has_data != BASELINE_PASS_HAS_DATA_COUNT:
        raise ValueError(
            "probe summary baseline pass_has_data mismatch: "
            f"expected={BASELINE_PASS_HAS_DATA_COUNT} got={pass_has_data} path={path.as_posix()}"
        )


def _validate_probe_summary_pass_empty_contract(*, path: Path, payload: dict[str, Any]) -> None:
    declared_total = payload.get("total")
    try:
        total = int(declared_total)
    except Exception:
        return
    if total != BASELINE_FUNCTION_COUNT:
        return

    pass_empty = _extract_probe_status_count(payload, STATUS_PASS_EMPTY)
    if pass_empty is None:
        raise ValueError(
            "probe summary baseline pass_empty contract missing: "
            f"expected={BASELINE_PASS_EMPTY_COUNT} path={path.as_posix()}"
        )
    if pass_empty != BASELINE_PASS_EMPTY_COUNT:
        raise ValueError(
            "probe summary baseline pass_empty mismatch: "
            f"expected={BASELINE_PASS_EMPTY_COUNT} got={pass_empty} path={path.as_posix()}"
        )


def _validate_probe_summary_callable_runtime_contract(*, path: Path, payload: dict[str, Any]) -> None:
    declared_total = payload.get("total")
    try:
        total = int(declared_total)
    except Exception:
        return
    if total != FETCHDATA_IMPL_CALLABLE_BASELINE_COUNT:
        return

    callable_raw = payload.get("pass_has_data_or_empty")
    if callable_raw is None:
        pass_has_data = _extract_probe_status_count(payload, STATUS_PASS_HAS_DATA)
        pass_empty = _extract_probe_status_count(payload, STATUS_PASS_EMPTY)
        if pass_has_data is None or pass_empty is None:
            raise ValueError(
                "probe summary baseline callable coverage contract missing: "
                f"expected={FETCHDATA_IMPL_CALLABLE_BASELINE_COUNT} path={path.as_posix()}"
            )
        callable_total = int(pass_has_data) + int(pass_empty)
    else:
        try:
            callable_total = int(callable_raw)
        except Exception:
            raise ValueError(
                "probe summary baseline callable coverage contract invalid: "
                f"expected integer pass_has_data_or_empty path={path.as_posix()}"
            ) from None

    if callable_total != FETCHDATA_IMPL_CALLABLE_BASELINE_COUNT:
        raise ValueError(
            "probe summary baseline callable coverage mismatch: "
            f"expected={FETCHDATA_IMPL_CALLABLE_BASELINE_COUNT} got={callable_total} path={path.as_posix()}"
        )

    blocked_source_missing_count = _extract_optional_probe_status_count(payload, STATUS_BLOCKED_SOURCE_MISSING)
    error_runtime_count = _extract_optional_probe_status_count(payload, STATUS_ERROR_RUNTIME)
    if (
        blocked_source_missing_count != FETCHDATA_IMPL_RUNTIME_BLOCKED_SOURCE_MISSING_BASELINE_COUNT
        or error_runtime_count != FETCHDATA_IMPL_RUNTIME_ERROR_BASELINE_COUNT
    ):
        raise ValueError(
            "probe summary baseline runtime blockage mismatch: "
            "expected "
            f"blocked_source_missing={FETCHDATA_IMPL_RUNTIME_BLOCKED_SOURCE_MISSING_BASELINE_COUNT} "
            f"error_runtime={FETCHDATA_IMPL_RUNTIME_ERROR_BASELINE_COUNT} "
            f"got blocked_source_missing={blocked_source_missing_count} error_runtime={error_runtime_count} "
            f"path={path.as_posix()}"
        )


def _validate_probe_summary_notebook_params_data_contract(*, path: Path, payload: dict[str, Any]) -> None:
    normalized_path = path.as_posix().replace("\\", "/")
    if not normalized_path.endswith("probe_summary_v3_notebook_params.json"):
        return

    pass_has_data = _extract_probe_status_count(payload, STATUS_PASS_HAS_DATA)
    if pass_has_data is None:
        raise ValueError(
            "probe summary notebook params data contract missing: "
            "expected status_counts.pass_has_data > 0 "
            f"path={path.as_posix()}"
        )
    if pass_has_data <= 0:
        raise ValueError(
            "probe summary notebook params data availability mismatch: "
            f"expected pass_has_data>0 got={pass_has_data} path={path.as_posix()}"
        )


def _extract_probe_status_count(payload: dict[str, Any], status: str) -> int | None:
    raw = payload.get(status)
    if raw is None:
        status_counts = payload.get("status_counts")
        if isinstance(status_counts, dict):
            raw = status_counts.get(status)
    try:
        return int(raw)
    except Exception:
        return None


def _extract_optional_probe_status_count(payload: dict[str, Any], status: str) -> int:
    count = _extract_probe_status_count(payload, status)
    if count is None:
        return 0
    return int(count)


def load_exception_decisions(path: str | Path = DEFAULT_EXCEPTION_DECISIONS_PATH) -> dict[str, dict[str, str]]:
    p = Path(path)
    if not p.is_file():
        return {}
    out: dict[str, dict[str, str]] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| "):
            continue
        if line.startswith("|---") or "function | issue_type" in line:
            continue
        parts = [x.strip() for x in line.strip("|").split("|")]
        if len(parts) < 6:
            continue
        fn = parts[0].strip("`")
        if not fn.startswith("fetch_"):
            continue
        out[fn] = {
            "issue_type": parts[1],
            "smoke_policy": parts[2],
            "research_policy": parts[3],
            "decision": parts[4],
            "notes": parts[5],
        }
    return out


def load_function_registry(path: str | Path = DEFAULT_FUNCTION_REGISTRY_PATH) -> dict[str, dict[str, Any]]:
    p = Path(path)
    if not p.is_file():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    rows = payload.get("functions") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    engine_counts = {"mongo": 0, "mysql": 0}
    for row in rows:
        if not isinstance(row, dict):
            continue
        fn = str(row.get("function", "")).strip()
        status = str(row.get("status", "")).strip().lower()
        if not fn.startswith("fetch_"):
            continue
        if status not in {"active", "allow", "review", ""}:
            continue
        engine = _derive_registry_engine(row, function=fn)
        _validate_registry_row_engine_contract(row, function=fn, engine=engine)
        engine_counts[engine] += 1
        out[fn] = row
    _validate_registry_engine_split_contract(
        path=p,
        payload=payload,
        loaded_function_count=len(out),
        engine_counts=engine_counts,
    )
    return out


def load_routing_registry(path: str | Path = DEFAULT_ROUTING_REGISTRY_PATH) -> set[str]:
    p = Path(path)
    if not p.is_file():
        return set()
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return set()
    rows = payload.get("resolver_entries") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return set()

    out: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue

        raw = row.get("raw")
        if isinstance(raw, dict):
            public_name = str(raw.get("public_name") or "").strip()
            if public_name.startswith("fetch_"):
                out.add(public_name)

        adjustment = row.get("adjustment")
        adv = adjustment.get("adv") if isinstance(adjustment, dict) else None
        if isinstance(adv, dict):
            adv_public_name = str(adv.get("public_name") or "").strip()
            if adv_public_name.startswith("fetch_"):
                out.add(adv_public_name)

    return out


def _validate_routing_registry_resolution(
    *,
    routing_registry_path: str | Path,
    public_function: str | None,
) -> None:
    public_name = str(public_function or "").strip()
    if not public_name:
        return
    routing_public_names = load_routing_registry(routing_registry_path)
    if not routing_public_names:
        return
    if public_name not in routing_public_names:
        raise ValueError(
            f"resolved function {public_name!r} is not declared in routing registry {Path(routing_registry_path).as_posix()}"
        )


def _derive_registry_engine(row: dict[str, Any], *, function: str) -> str:
    raw_engine = row.get("engine")
    if isinstance(raw_engine, str) and raw_engine.strip():
        engine = raw_engine.strip().lower()
        if engine in ENGINE_INTERNAL_SOURCE:
            return engine
        raise ValueError(
            f"function registry row {function!r} has unsupported engine={raw_engine!r}; expected mongo|mysql"
        )

    for field in ("source_internal", "provider_internal", "source"):
        normalized = normalize_source(row.get(field))
        if is_mongo_source(normalized):
            return "mongo"
        if is_mysql_source(normalized):
            return "mysql"

    raise ValueError(
        f"function registry row {function!r} is missing engine/source_internal contract metadata"
    )


def _validate_registry_row_engine_contract(
    row: dict[str, Any],
    *,
    function: str,
    engine: str,
) -> None:
    source_token = str(row.get("source") or "").strip().lower()
    if source_token != FETCHDATA_IMPL_SOURCE_SEMANTIC_VALUE:
        raise ValueError(
            f"function registry row {function!r} has source={row.get('source')!r}; "
            f"expected semantic source={FETCHDATA_IMPL_SOURCE_SEMANTIC_VALUE!r}"
        )

    expected_source = ENGINE_INTERNAL_SOURCE[engine]
    for field in ("source_internal", "provider_internal"):
        raw = row.get(field)
        if raw is None:
            continue
        normalized = normalize_source(raw)
        if normalized and normalized != expected_source:
            raise ValueError(
                f"function registry row {function!r} has engine={engine!r} but {field}={raw!r}; "
                f"expected {expected_source!r}"
            )


def _validate_registry_engine_split_contract(
    *,
    path: Path,
    payload: dict[str, Any],
    loaded_function_count: int,
    engine_counts: dict[str, int],
) -> None:
    declared_function_count = payload.get("function_count")
    try:
        declared_total = int(declared_function_count)
    except Exception:
        return

    if declared_total != BASELINE_FUNCTION_COUNT:
        return

    if loaded_function_count != BASELINE_FUNCTION_COUNT:
        raise ValueError(
            f"function registry baseline count mismatch: expected={BASELINE_FUNCTION_COUNT} "
            f"loaded={loaded_function_count} path={path.as_posix()}"
        )

    mongo_count = int(engine_counts.get("mongo", 0))
    mysql_count = int(engine_counts.get("mysql", 0))
    if mongo_count != BASELINE_ENGINE_SPLIT["mongo"] or mysql_count != BASELINE_ENGINE_SPLIT["mysql"]:
        raise ValueError(
            "function registry baseline engine split mismatch: "
            f"expected mongo={BASELINE_ENGINE_SPLIT['mongo']} mysql={BASELINE_ENGINE_SPLIT['mysql']} "
            f"got mongo={mongo_count} mysql={mysql_count} path={path.as_posix()}"
        )


def _normalize_optional_selector(value: Any) -> Any:
    if isinstance(value, str):
        token = value.strip()
        return token or None
    return value


def _normalize_window_bound(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        token = value.isoformat()
    elif isinstance(value, date):
        token = value.isoformat()
    else:
        token = str(value).strip()
    return token or None


def _enforce_required_intent_window(intent: FetchIntent) -> FetchIntent:
    kwargs = dict(intent.extra_kwargs)
    start = _normalize_window_bound(intent.start)
    end = _normalize_window_bound(intent.end)
    if start is None:
        start = _normalize_window_bound(kwargs.get("start"))
    if end is None:
        end = _normalize_window_bound(kwargs.get("end"))

    if start is None or end is None:
        required = ", ".join(INTENT_REQUIRED_WINDOW_FIELDS)
        raise ValueError(f"intent must provide non-empty {required}")

    start_dt = _parse_dt_for_compare(start)
    end_dt = _parse_dt_for_compare(end)
    if start_dt is not None and end_dt is not None and start_dt > end_dt:
        raise ValueError("intent.start must be <= intent.end")

    if "start" in kwargs:
        kwargs["start"] = start
    if "end" in kwargs:
        kwargs["end"] = end

    if intent.start == start and intent.end == end and kwargs == intent.extra_kwargs:
        return intent
    return replace(intent, start=start, end=end, extra_kwargs=kwargs)


def _resolve_venue_universe_alias(*, venue: Any, universe: Any) -> tuple[Any, Any]:
    normalized_venue = _normalize_optional_selector(venue)
    normalized_universe = _normalize_optional_selector(universe)
    if normalized_venue is None and normalized_universe is not None:
        normalized_venue = normalized_universe
    return normalized_venue, normalized_universe


def _effective_intent_venue(intent: FetchIntent) -> Any:
    venue, _universe = _resolve_venue_universe_alias(venue=intent.venue, universe=intent.universe)
    return venue


def _coerce_intent(intent: FetchIntent | dict[str, Any]) -> FetchIntent:
    if isinstance(intent, FetchIntent):
        _enforce_data_plane_boundary(intent.extra_kwargs, location="intent.extra_kwargs")
        _coerce_fields_selector(intent.extra_kwargs.get("fields"), location="intent.extra_kwargs.fields")
        _effective_intent_venue(intent)
        normalized_auto_symbols = _coerce_optional_bool(intent.auto_symbols, location="intent.auto_symbols")
        normalized_adjust = _coerce_intent_adjust(intent.adjust, location="intent.adjust")
        normalized_sample = _coerce_optional_sample_plan(intent.sample, location="intent.sample")
        coerced_intent = replace(
            intent,
            adjust=normalized_adjust,
            auto_symbols=normalized_auto_symbols,
            fields=_coerce_fields_selector(intent.fields, location="intent.fields"),
            sample=normalized_sample,
        )
        return _apply_technical_indicator_default_data_shape(coerced_intent)
    if not isinstance(intent, dict):
        raise ValueError("intent must be FetchIntent or dict")
    _enforce_data_plane_boundary(intent, location="intent")
    extra_kwargs_raw = intent.get("extra_kwargs")
    if isinstance(extra_kwargs_raw, dict):
        extra_kwargs = dict(extra_kwargs_raw)
    else:
        extra_kwargs = {}
    if intent.get("as_of") is not None and "as_of" not in extra_kwargs:
        extra_kwargs["as_of"] = intent.get("as_of")
    _enforce_data_plane_boundary(extra_kwargs, location="intent.extra_kwargs")
    _coerce_fields_selector(extra_kwargs.get("fields"), location="intent.extra_kwargs.fields")
    venue, universe = _resolve_venue_universe_alias(venue=intent.get("venue"), universe=intent.get("universe"))
    coerced_intent = FetchIntent(
        asset=intent.get("asset"),
        freq=intent.get("freq"),
        venue=venue,
        universe=universe,
        adjust=_coerce_intent_adjust(intent.get("adjust"), location="intent.adjust"),
        symbols=intent.get("symbols"),
        start=intent.get("start"),
        end=intent.get("end"),
        fields=_coerce_fields_selector(intent.get("fields"), location="intent.fields"),
        function_override=intent.get("function_override"),
        source_hint=intent.get("source_hint"),
        public_function=intent.get("public_function"),
        auto_symbols=_coerce_optional_bool(intent.get("auto_symbols"), location="intent.auto_symbols"),
        sample=_coerce_optional_sample_plan(intent.get("sample"), location="intent.sample"),
        extra_kwargs=extra_kwargs,
    )
    return _apply_technical_indicator_default_data_shape(coerced_intent)


def _unwrap_fetch_request_payload(
    intent: FetchIntent | dict[str, Any],
    policy: FetchExecutionPolicy | dict[str, Any] | None,
) -> tuple[FetchIntent | dict[str, Any], FetchExecutionPolicy | dict[str, Any] | None]:
    if isinstance(intent, FetchIntent) or not isinstance(intent, dict):
        return intent, policy

    function_name = _validate_fetch_request_wrapper_contract(intent)
    _enforce_data_plane_boundary(intent, location="fetch_request")
    wrapper_policy = _resolve_wrapper_policy_boundary(policy=policy, wrapper_policy=intent.get("policy"))
    wrapper_mode = intent.get("mode")
    wrapper_policy = _merge_wrapper_mode_into_policy(wrapper_policy, wrapper_mode=wrapper_mode)
    intent_obj = intent.get("intent")

    if intent_obj is not None:
        if not isinstance(intent_obj, dict):
            raise ValueError("fetch_request.intent must be an object when provided")
        _enforce_data_plane_boundary(intent_obj, location="fetch_request.intent")
        merged_intent: dict[str, Any] = dict(intent_obj)
        for key in (
            "asset",
            "freq",
            "venue",
            "universe",
            "adjust",
            "symbols",
            "start",
            "end",
            "fields",
            "as_of",
            "auto_symbols",
            "sample",
        ):
            if merged_intent.get(key) is None and intent.get(key) is not None:
                merged_intent[key] = intent.get(key)

        if merged_intent.get("source_hint") is None and intent.get("source_hint") is not None:
            merged_intent["source_hint"] = intent.get("source_hint")
        if merged_intent.get("public_function") is None and intent.get("public_function") is not None:
            merged_intent["public_function"] = intent.get("public_function")

        function_override = _coerce_optional_text(merged_intent.get("function_override"))
        if function_override is not None:
            raise ValueError(
                "fetch_request.intent.function_override is not allowed in intent-first mode; "
                "use top-level function wrapper for strong-control function mode"
            )

        kwargs_obj = intent.get("kwargs")
        if isinstance(kwargs_obj, dict):
            _enforce_data_plane_boundary(kwargs_obj, location="fetch_request.kwargs")

        extra_kwargs = merged_intent.get("extra_kwargs")
        if extra_kwargs is not None and not isinstance(extra_kwargs, dict):
            raise ValueError("intent.extra_kwargs must be an object when provided")
        if isinstance(extra_kwargs, dict):
            _enforce_data_plane_boundary(extra_kwargs, location="intent.extra_kwargs")

        merged_kwargs: dict[str, Any] = {}
        if isinstance(kwargs_obj, dict):
            merged_kwargs.update(kwargs_obj)
        if isinstance(extra_kwargs, dict):
            merged_kwargs.update(extra_kwargs)
        if merged_kwargs:
            merged_intent["extra_kwargs"] = merged_kwargs
        return merged_intent, wrapper_policy

    # Compatibility with function+kwargs shaped fetch_request without an explicit intent block.
    kwargs_obj = intent.get("kwargs")
    if kwargs_obj is not None or function_name is not None or "policy" in intent or "mode" in intent:
        if isinstance(kwargs_obj, dict):
            _enforce_data_plane_boundary(kwargs_obj, location="fetch_request.kwargs")
        merged_intent = {
            "asset": intent.get("asset"),
            "freq": intent.get("freq"),
            "venue": intent.get("venue"),
            "universe": intent.get("universe"),
            "adjust": intent.get("adjust", TECHNICAL_INDICATOR_DEFAULT_ADJUST),
            "symbols": intent.get("symbols"),
            "start": intent.get("start"),
            "end": intent.get("end"),
            "fields": intent.get("fields"),
            "as_of": intent.get("as_of"),
            "auto_symbols": intent.get("auto_symbols"),
            "sample": intent.get("sample"),
            "function_override": function_name,
            "source_hint": intent.get("source_hint"),
            "public_function": intent.get("public_function"),
            "extra_kwargs": dict(kwargs_obj or {}),
        }
        return merged_intent, wrapper_policy

    return intent, wrapper_policy


def _resolve_wrapper_policy_boundary(
    *,
    policy: FetchExecutionPolicy | dict[str, Any] | None,
    wrapper_policy: FetchExecutionPolicy | dict[str, Any] | None,
) -> FetchExecutionPolicy | dict[str, Any] | None:
    if policy is None:
        return wrapper_policy
    if wrapper_policy is None:
        return policy

    entrypoint_policy = _build_policy_payload(_coerce_policy(policy))
    request_policy = _build_policy_payload(_coerce_policy(wrapper_policy))
    if entrypoint_policy != request_policy:
        raise ValueError(
            "fetch_request.policy conflicts with execute_fetch_by_intent(..., policy=...); "
            "provide one normalized policy source"
        )
    return policy


def _validate_fetch_request_wrapper_contract(fetch_request: dict[str, Any]) -> str | None:
    intent_obj = fetch_request.get("intent")
    if intent_obj is not None and not isinstance(intent_obj, dict):
        raise ValueError("fetch_request.intent must be an object when provided")

    kwargs_obj = fetch_request.get("kwargs")
    if kwargs_obj is not None and not isinstance(kwargs_obj, dict):
        raise ValueError("fetch_request.kwargs must be an object when provided")

    policy_obj = fetch_request.get("policy")
    if policy_obj is not None and not isinstance(policy_obj, (dict, FetchExecutionPolicy)):
        raise ValueError("fetch_request.policy must be an object when provided")

    if fetch_request.get("mode") is not None:
        _coerce_fetch_request_v1_mode(fetch_request.get("mode"))

    _coerce_optional_sample_plan(fetch_request.get("sample"), location="fetch_request.sample")
    if isinstance(intent_obj, dict):
        _coerce_optional_sample_plan(intent_obj.get("sample"), location="fetch_request.intent.sample")

    top_level_auto_symbols = _coerce_optional_bool(
        fetch_request.get("auto_symbols"),
        location="fetch_request.auto_symbols",
    )
    intent_auto_symbols = None
    if isinstance(intent_obj, dict):
        intent_auto_symbols = _coerce_optional_bool(
            intent_obj.get("auto_symbols"),
            location="intent.auto_symbols",
        )
    if (
        top_level_auto_symbols is not None
        and intent_auto_symbols is not None
        and top_level_auto_symbols != intent_auto_symbols
    ):
        raise ValueError("fetch_request.intent.auto_symbols conflicts with fetch_request.auto_symbols")

    function_name = _coerce_optional_text(fetch_request.get("function"))
    strong_control_function = _coerce_optional_bool(
        fetch_request.get(FETCH_REQUEST_V1_STRONG_CONTROL_FUNCTION_FIELD),
        location=f"fetch_request.{FETCH_REQUEST_V1_STRONG_CONTROL_FUNCTION_FIELD}",
    )
    if isinstance(intent_obj, dict) and function_name is not None:
        raise ValueError("fetch_request intent and function modes are mutually exclusive in v1")

    if function_name is not None:
        if strong_control_function is not True:
            raise ValueError(
                "fetch_request.function requires explicit strong-control-function mode; "
                "set fetch_request.strong_control_function=true"
            )
        mixed_keys = [key for key in FETCH_REQUEST_INTENT_FIELD_KEYS if fetch_request.get(key) is not None]
        if mixed_keys:
            raise ValueError(
                "fetch_request function mode is only allowed for strong-control wrappers; "
                f"remove intent-first fields: {', '.join(mixed_keys)}"
            )
    elif strong_control_function:
        raise ValueError(
            "fetch_request.strong_control_function=true requires fetch_request.function in strong-control mode"
        )
    return function_name


def _merge_wrapper_mode_into_policy(
    policy: FetchExecutionPolicy | dict[str, Any] | None,
    *,
    wrapper_mode: Any,
) -> FetchExecutionPolicy | dict[str, Any] | None:
    if wrapper_mode is None:
        return policy

    normalized_wrapper_mode = _coerce_fetch_request_v1_mode_to_policy_mode(wrapper_mode)
    if policy is None:
        return {"mode": normalized_wrapper_mode}

    if isinstance(policy, FetchExecutionPolicy):
        normalized_policy_mode = _coerce_policy_mode(policy.mode)
        if normalized_policy_mode != normalized_wrapper_mode:
            raise ValueError(
                "fetch_request.mode conflicts with policy.mode; provide one normalized mode value"
            )
        if policy.mode == normalized_policy_mode:
            return policy
        return FetchExecutionPolicy(
            mode=normalized_policy_mode,
            timeout_sec=policy.timeout_sec,
            on_no_data=policy.on_no_data,
            max_symbols=policy.max_symbols,
            max_rows=policy.max_rows,
            retry_strategy=_coerce_policy_retry_strategy(policy.retry_strategy),
        )

    if isinstance(policy, dict):
        merged_policy = dict(policy)
        policy_mode = merged_policy.get("mode")
        if policy_mode is None:
            merged_policy["mode"] = normalized_wrapper_mode
            return merged_policy
        normalized_policy_mode = _coerce_policy_mode(policy_mode)
        if normalized_policy_mode != normalized_wrapper_mode:
            raise ValueError(
                "fetch_request.mode conflicts with policy.mode; provide one normalized mode value"
            )
        merged_policy["mode"] = normalized_policy_mode
        return merged_policy

    return policy


def _forbidden_backtest_plane_fields(payload: dict[str, Any]) -> list[str]:
    out: set[str] = set()
    for raw_key, value in payload.items():
        key = str(raw_key).strip().lower()
        if key in BACKTEST_PLANE_FORBIDDEN_PAYLOAD_KEYS and value is not None:
            out.add(key)
    return sorted(out)


def _forbidden_gaterunner_only_fields(payload: dict[str, Any]) -> list[str]:
    out: set[str] = set()
    for raw_key, value in payload.items():
        key = str(raw_key).strip().lower()
        if key in GATERUNNER_ONLY_FORBIDDEN_PAYLOAD_KEYS and value is not None:
            out.add(key)
    return sorted(out)


def _enforce_data_plane_boundary(payload: dict[str, Any] | None, *, location: str) -> None:
    if not isinstance(payload, dict):
        return
    forbidden_backtest = _forbidden_backtest_plane_fields(payload)
    if forbidden_backtest:
        joined = ", ".join(forbidden_backtest)
        raise ValueError(
            f"{location} contains Backtest Plane / Kernel fields not executable by qa_fetch: {joined}; "
            "route strategy/backtest execution to deterministic kernel"
        )

    forbidden_gaterunner = _forbidden_gaterunner_only_fields(payload)
    if forbidden_gaterunner:
        joined = ", ".join(forbidden_gaterunner)
        raise ValueError(
            f"{location} contains GateRunner-only arbitration fields not executable by qa_fetch: {joined}; "
            "route strategy validity verdicts to deterministic GateRunner"
        )


def _coerce_policy(policy: FetchExecutionPolicy | dict[str, Any] | None) -> FetchExecutionPolicy:
    if policy is None:
        return FetchExecutionPolicy()
    if isinstance(policy, FetchExecutionPolicy):
        return FetchExecutionPolicy(
            mode=_coerce_policy_mode(policy.mode),
            timeout_sec=policy.timeout_sec,
            on_no_data=_coerce_policy_on_no_data(policy.on_no_data),
            max_symbols=_coerce_policy_optional_positive_int(policy.max_symbols, location="policy.max_symbols"),
            max_rows=_coerce_policy_optional_positive_int(policy.max_rows, location="policy.max_rows"),
            retry_strategy=_coerce_policy_retry_strategy(policy.retry_strategy),
            snapshot_manifest_path=_coerce_optional_text(policy.snapshot_manifest_path),
        )
    if not isinstance(policy, dict):
        raise ValueError("policy must be FetchExecutionPolicy or dict")
    return FetchExecutionPolicy(
        mode=_coerce_policy_mode(policy.get("mode", "smoke")),
        timeout_sec=policy.get("timeout_sec"),
        on_no_data=_coerce_policy_on_no_data(policy.get("on_no_data", "pass_empty")),
        max_symbols=_coerce_policy_optional_positive_int(policy.get("max_symbols"), location="policy.max_symbols"),
        max_rows=_coerce_policy_optional_positive_int(policy.get("max_rows"), location="policy.max_rows"),
        retry_strategy=_coerce_policy_retry_strategy(policy.get("retry_strategy")),
        snapshot_manifest_path=_coerce_optional_text(policy.get("snapshot_manifest_path")),
    )


def _coerce_policy_mode(value: Any) -> str:
    mode = str(value or "smoke").strip().lower()
    if not mode:
        mode = "smoke"
    if mode not in SUPPORTED_FETCH_POLICY_MODES:
        supported = ", ".join(sorted(SUPPORTED_FETCH_POLICY_MODES))
        raise ValueError(f"policy.mode must be one of: {supported}")
    return mode


def _coerce_fetch_request_v1_mode(value: Any) -> str:
    mode = str(value or "").strip().lower()
    if mode not in FETCH_REQUEST_V1_MODE_OPTIONS:
        supported = ", ".join(FETCH_REQUEST_V1_MODE_OPTIONS)
        raise ValueError(f"fetch_request.mode must be one of: {supported}")
    return mode


def _coerce_fetch_request_v1_mode_to_policy_mode(value: Any) -> str:
    mode = _coerce_fetch_request_v1_mode(value)
    return FETCH_REQUEST_MODE_TO_POLICY_MODE[mode]


def _coerce_policy_on_no_data(value: Any) -> str:
    on_no_data = str(value or "pass_empty").strip().lower()
    if not on_no_data:
        on_no_data = "pass_empty"
    if on_no_data not in SUPPORTED_ON_NO_DATA_POLICIES:
        supported = ", ".join(POLICY_ON_NO_DATA_OPTIONS)
        raise ValueError(f"policy.on_no_data must be one of: {supported}")
    return on_no_data


def _coerce_policy_optional_positive_int(value: Any, *, location: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{location} must be a positive integer when provided")
    try:
        out = int(value)
    except Exception as exc:
        raise ValueError(f"{location} must be a positive integer when provided") from exc
    if out <= 0:
        raise ValueError(f"{location} must be a positive integer when provided")
    return out


def _coerce_optional_integer(value: Any, *, location: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{location} must be an integer when provided")
    try:
        return int(value)
    except Exception as exc:
        raise ValueError(f"{location} must be an integer when provided") from exc


def _coerce_policy_retry_strategy(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("policy.retry_strategy must be an object when provided")
    out: dict[str, Any] = dict(value)
    if RETRY_STRATEGY_MAX_ATTEMPTS_KEY in out:
        out[RETRY_STRATEGY_MAX_ATTEMPTS_KEY] = _coerce_policy_optional_positive_int(
            out.get(RETRY_STRATEGY_MAX_ATTEMPTS_KEY),
            location=f"policy.retry_strategy.{RETRY_STRATEGY_MAX_ATTEMPTS_KEY}",
        )
    return out


def _effective_on_no_data_attempts(policy: FetchExecutionPolicy) -> int:
    if policy.on_no_data != "retry":
        return 1
    max_attempts = ON_NO_DATA_RETRY_TOTAL_ATTEMPTS
    retry_strategy = policy.retry_strategy
    if isinstance(retry_strategy, dict):
        raw = retry_strategy.get(RETRY_STRATEGY_MAX_ATTEMPTS_KEY)
        if raw is not None:
            max_attempts = int(raw)
    return max(1, int(max_attempts))


def _coerce_optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    token = value.strip()
    return token or None


def _coerce_optional_bool(value: Any, *, location: str = "auto_symbols") -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    raise ValueError(f"{location} must be bool when provided")


def _apply_technical_indicator_default_data_shape(intent: FetchIntent) -> FetchIntent:
    if not _should_enforce_technical_indicator_default_data_shape(intent):
        return intent
    normalized_freq = _coerce_optional_text(intent.freq) or TECHNICAL_INDICATOR_DEFAULT_FREQ
    normalized_adjust = _coerce_intent_adjust(intent.adjust, location="intent.adjust")
    if intent.freq == normalized_freq and intent.adjust == normalized_adjust:
        return intent
    return replace(intent, freq=normalized_freq, adjust=normalized_adjust)


def _should_enforce_technical_indicator_default_data_shape(intent: FetchIntent) -> bool:
    auto_symbols_enabled = intent.auto_symbols
    if auto_symbols_enabled is None:
        auto_symbols_enabled = AUTO_SYMBOLS_DEFAULT_ENABLED
    return auto_symbols_enabled is True


def _coerce_intent_adjust(value: Any, *, location: str = "intent.adjust") -> str:
    if value is None:
        return TECHNICAL_INDICATOR_DEFAULT_ADJUST
    token = str(value).strip()
    if not token:
        return TECHNICAL_INDICATOR_DEFAULT_ADJUST
    return token


def _coerce_fields_selector(value: Any, *, location: str) -> list[str] | None:
    if value is None:
        return None

    if isinstance(value, str):
        raw_tokens = value.split(",")
    elif isinstance(value, (list, tuple)):
        raw_tokens = list(value)
    else:
        raise ValueError(f"{location} must be a string or list[str] when provided")

    out: list[str] = []
    seen: set[str] = set()
    for idx, item in enumerate(raw_tokens):
        if not isinstance(item, str):
            raise ValueError(f"{location}[{idx}] must be a non-empty string")
        token = item.strip()
        if not token:
            continue
        expanded = list(TECHNICAL_INDICATOR_MIN_FIELDS_OHLCV) if token.lower() == "ohlcv" else [token]
        for field_name in expanded:
            if field_name in seen:
                continue
            seen.add(field_name)
            out.append(field_name)

    if not out:
        return None
    return out


def _coerce_optional_sample_plan(value: Any, *, location: str) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError(f"{location} must be an object when provided")

    out = dict(value)
    if "n" in out:
        out["n"] = _coerce_policy_optional_positive_int(out.get("n"), location=f"{location}.n")
    if "method" in out:
        method = _coerce_optional_text(out.get("method"))
        if method is None:
            raise ValueError(f"{location}.method must be a non-empty string when provided")
        out["method"] = _normalize_sample_method(method, location=f"{location}.method")
    if "seed" in out:
        out["seed"] = _coerce_optional_integer(out.get("seed"), location=f"{location}.seed")
    if "liquidity_field" in out:
        liquidity_field = _coerce_optional_text(out.get("liquidity_field"))
        if liquidity_field is None:
            raise ValueError(f"{location}.liquidity_field must be a non-empty string when provided")
        out["liquidity_field"] = liquidity_field
    if "industry_field" in out:
        industry_field = _coerce_optional_text(out.get("industry_field"))
        if industry_field is None:
            raise ValueError(f"{location}.industry_field must be a non-empty string when provided")
        out["industry_field"] = industry_field
    return out


def _intent_effective_kwargs(intent: FetchIntent) -> dict[str, Any]:
    kwargs = dict(intent.extra_kwargs)
    extra_fields = _coerce_fields_selector(kwargs.get("fields"), location="intent.extra_kwargs.fields")
    intent_fields = _coerce_fields_selector(intent.fields, location="intent.fields")
    _normalize_symbol_selectors_in_kwargs(kwargs)
    if intent.symbols is not None and not _has_any_symbol_selector(kwargs):
        normalized_intent_symbols = _normalize_symbol_selector_for_provider(intent.symbols)
        if normalized_intent_symbols is not None:
            kwargs["symbols"] = normalized_intent_symbols
    if intent.start is not None and "start" not in kwargs:
        kwargs["start"] = intent.start
    if intent.end is not None and "end" not in kwargs:
        kwargs["end"] = intent.end
    kwargs["fields"] = extra_fields or intent_fields or list(TECHNICAL_INDICATOR_MIN_FIELDS_OHLCV)
    return kwargs


def _normalize_symbol_selector_for_provider(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        token = value.strip()
        return token or None
    if isinstance(value, (list, tuple)):
        normalized: list[Any] = []
        for item in value:
            if isinstance(item, str):
                token = item.strip()
                if token:
                    normalized.append(token)
                continue
            normalized.append(item)
        if not normalized:
            return None
        return normalized
    return value


def _normalize_symbol_selectors_in_kwargs(kwargs: dict[str, Any]) -> None:
    for key in ("symbols", "symbol", "code"):
        if key not in kwargs:
            continue
        normalized_value = _normalize_symbol_selector_for_provider(kwargs.get(key))
        if normalized_value is None:
            kwargs.pop(key, None)
            continue
        kwargs[key] = normalized_value


def _has_any_symbol_selector(kwargs: dict[str, Any]) -> bool:
    return any(key in kwargs for key in ("symbols", "symbol", "code"))


def _should_apply_auto_symbols_planner(intent: FetchIntent) -> bool:
    auto_symbols_enabled = intent.auto_symbols
    if auto_symbols_enabled is None:
        auto_symbols_enabled = AUTO_SYMBOLS_DEFAULT_ENABLED
    if auto_symbols_enabled is not True:
        return False
    if _has_explicit_symbol_or_code_selector(intent):
        return False
    return True


def _has_explicit_symbol_or_code_selector(intent: FetchIntent) -> bool:
    if _normalize_symbol_tokens(intent.symbols):
        return True
    extra = intent.extra_kwargs if isinstance(intent.extra_kwargs, dict) else {}
    for key in ("symbol", "symbols", "code"):
        if _normalize_symbol_tokens(extra.get(key)):
            return True
    return False


def _normalize_symbol_tokens(value: Any) -> list[str]:
    if isinstance(value, str):
        token = value.strip()
        return [token] if token else []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, str):
                token = item.strip()
                if token:
                    out.append(token)
        return out
    return []


def _extract_candidates_from_preview(preview: Any) -> list[dict[str, Any]]:
    if not isinstance(preview, list):
        return []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in preview:
        if not isinstance(row, dict):
            continue
        symbols: list[str] = []
        for key in ("code", "symbol", "symbols", "ticker", "secid", "wind_code"):
            symbols.extend(_normalize_symbol_tokens(row.get(key)))
        for token in symbols:
            if token in seen:
                continue
            seen.add(token)
            out.append({"symbol": token, "row": dict(row)})
    return out


def _extract_sample_plan(intent: FetchIntent) -> dict[str, Any]:
    sample_plan: dict[str, Any] = {
        "n": AUTO_SYMBOLS_DEFAULT_SAMPLE_N,
        "method": AUTO_SYMBOLS_DEFAULT_SAMPLE_METHOD,
        "seed": None,
        "liquidity_field": None,
        "industry_field": None,
    }
    sample_obj = intent.sample
    if not isinstance(sample_obj, dict):
        return sample_plan
    raw_n = sample_obj.get("n")
    if isinstance(raw_n, (int, float)):
        try:
            sample_plan["n"] = max(1, int(raw_n))
        except Exception:
            sample_plan["n"] = AUTO_SYMBOLS_DEFAULT_SAMPLE_N
    raw_method = sample_obj.get("method")
    if isinstance(raw_method, str) and raw_method.strip():
        sample_plan["method"] = _normalize_sample_method(raw_method)
    raw_seed = sample_obj.get("seed")
    if raw_seed is not None:
        sample_plan["seed"] = _coerce_optional_integer(raw_seed, location="intent.sample.seed")
    raw_liquidity_field = _coerce_optional_text(sample_obj.get("liquidity_field"))
    if raw_liquidity_field:
        sample_plan["liquidity_field"] = raw_liquidity_field
    raw_industry_field = _coerce_optional_text(sample_obj.get("industry_field"))
    if raw_industry_field:
        sample_plan["industry_field"] = raw_industry_field
    return sample_plan


def _normalize_sample_method(sample_method: str, *, location: str | None = None) -> str:
    token = str(sample_method).strip().lower()
    normalized = SUPPORTED_SAMPLE_METHOD_ALIASES.get(token)
    if normalized is not None:
        return normalized
    if location is not None:
        supported = ", ".join(SUPPORTED_SAMPLE_METHOD_TOKENS)
        raise ValueError(f"{location} must be one of: {supported}")
    return AUTO_SYMBOLS_DEFAULT_SAMPLE_METHOD


def _coerce_numeric(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        token = value.strip().replace(",", "")
        if not token:
            return None
        try:
            return float(token)
        except Exception:
            return None
    return None


def _resolve_sample_metric_field(
    *,
    candidates: list[dict[str, Any]],
    preferred_field: str | None,
    fallback_fields: tuple[str, ...],
    numeric: bool,
) -> str | None:
    field_candidates: list[str] = []
    if isinstance(preferred_field, str):
        token = preferred_field.strip()
        if token:
            field_candidates.append(token)
    field_candidates.extend(fallback_fields)
    seen: set[str] = set()
    for field in field_candidates:
        if field in seen:
            continue
        seen.add(field)
        has_valid = False
        for candidate in candidates:
            row = candidate.get("row")
            if not isinstance(row, dict):
                continue
            raw = row.get(field)
            if numeric:
                if _coerce_numeric(raw) is not None:
                    has_valid = True
                    break
            elif _coerce_optional_text(raw) is not None:
                has_valid = True
                break
        if has_valid:
            return field
    return field_candidates[0] if field_candidates else None


def _candidate_metric(candidate: dict[str, Any], *, field: str | None, numeric: bool) -> Any:
    if not isinstance(field, str) or not field:
        return None
    row = candidate.get("row")
    if not isinstance(row, dict):
        return None
    raw = row.get(field)
    if numeric:
        return _coerce_numeric(raw)
    return _coerce_optional_text(raw)


def _industry_stratified_candidates(
    candidates: list[dict[str, Any]],
    *,
    sample_n: int,
    industry_field: str | None,
    seed: int | None,
) -> list[dict[str, Any]]:
    if not candidates:
        return []
    groups: dict[str, list[dict[str, Any]]] = {}
    group_order: list[str] = []
    for candidate in candidates:
        industry = _candidate_metric(candidate, field=industry_field, numeric=False)
        token = str(industry).strip() if industry is not None else ""
        if not token:
            token = "__unknown__"
        if token not in groups:
            groups[token] = []
            group_order.append(token)
        groups[token].append(candidate)

    if seed is not None:
        rng = random.Random(seed)
        for key in group_order:
            rng.shuffle(groups[key])

    out: list[dict[str, Any]] = []
    active = list(group_order)
    while active and len(out) < sample_n:
        next_active: list[str] = []
        for key in active:
            bucket = groups.get(key, [])
            if bucket and len(out) < sample_n:
                out.append(bucket.pop(0))
            if bucket:
                next_active.append(key)
        active = next_active
    return out


def _select_sample_symbols(
    candidates: list[dict[str, Any]],
    *,
    sample_n: int,
    sample_method: str,
    seed: int | None,
    liquidity_field: str | None,
    industry_field: str | None,
) -> tuple[list[str], dict[str, Any]]:
    method = _normalize_sample_method(sample_method)
    sample_n = max(1, int(sample_n))
    selected_rows: list[dict[str, Any]]
    strategy_params: dict[str, Any] = {
        "n": sample_n,
        "method": method,
    }
    if method == "random":
        seed_value = AUTO_SYMBOLS_DEFAULT_SAMPLE_SEED if seed is None else int(seed)
        rng = random.Random(seed_value)
        shuffled = list(candidates)
        rng.shuffle(shuffled)
        selected_rows = shuffled[:sample_n]
        strategy_params["seed"] = seed_value
    elif method == "liquidity":
        selected_liquidity_field = _resolve_sample_metric_field(
            candidates=candidates,
            preferred_field=liquidity_field,
            fallback_fields=AUTO_SYMBOLS_LIQUIDITY_FIELD_CANDIDATES,
            numeric=True,
        )
        strategy_params["liquidity_field"] = selected_liquidity_field
        if selected_liquidity_field:
            ranked_rows: list[tuple[int, dict[str, Any]]] = list(enumerate(candidates))
            ranked_rows.sort(
                key=lambda pair: (
                    _candidate_metric(pair[1], field=selected_liquidity_field, numeric=True) is not None,
                    _candidate_metric(pair[1], field=selected_liquidity_field, numeric=True) or float("-inf"),
                    -pair[0],
                ),
                reverse=True,
            )
            selected_rows = [candidate for _idx, candidate in ranked_rows[:sample_n]]
        else:
            selected_rows = candidates[:sample_n]
            strategy_params["fallback"] = AUTO_SYMBOLS_DEFAULT_SAMPLE_METHOD
    elif method == "industry_stratified":
        selected_industry_field = _resolve_sample_metric_field(
            candidates=candidates,
            preferred_field=industry_field,
            fallback_fields=AUTO_SYMBOLS_INDUSTRY_FIELD_CANDIDATES,
            numeric=False,
        )
        strategy_params["industry_field"] = selected_industry_field
        if seed is not None:
            strategy_params["seed"] = int(seed)
        if selected_industry_field:
            selected_rows = _industry_stratified_candidates(
                candidates,
                sample_n=sample_n,
                industry_field=selected_industry_field,
                seed=seed,
            )
        else:
            selected_rows = candidates[:sample_n]
            strategy_params["fallback"] = AUTO_SYMBOLS_DEFAULT_SAMPLE_METHOD
    else:
        selected_rows = candidates[:sample_n]
    selected_symbols = [str(row.get("symbol")).strip() for row in selected_rows if str(row.get("symbol")).strip()]
    strategy_params["candidate_count"] = len(candidates)
    strategy_params["selected_count"] = len(selected_symbols)
    strategy_params["selected_symbols"] = list(selected_symbols)
    return selected_symbols, strategy_params


def _planner_sample_result(
    *,
    mode: str,
    symbols: list[str],
    sample_n: int,
    sample_method: str,
    strategy_params: dict[str, Any] | None = None,
) -> FetchExecutionResult:
    status = STATUS_PASS_HAS_DATA if symbols else STATUS_PASS_EMPTY
    reason = "ok" if symbols else "no_candidates"
    rows = [{"symbol": token, "rank": idx + 1} for idx, token in enumerate(symbols)]
    final_kwargs: dict[str, Any] = {"sample_n": sample_n, "sample_method": sample_method}
    if isinstance(strategy_params, dict):
        final_kwargs["sample_strategy"] = _json_safe(dict(strategy_params))
    return FetchExecutionResult(
        status=status,
        reason=reason,
        source="fetch",
        source_internal=PLANNER_SOURCE_INTERNAL,
        engine=None,
        provider_id="fetch",
        provider_internal=PLANNER_SOURCE_INTERNAL,
        resolved_function="planner_sample_symbols",
        public_function="planner_sample_symbols",
        elapsed_sec=0.0,
        row_count=len(rows),
        columns=["symbol", "rank"] if rows else [],
        dtypes={"symbol": "object", "rank": "int64"} if rows else {},
        preview=rows,
        final_kwargs=final_kwargs,
        mode=mode,
        data=rows,
    )


def _planner_error_result(
    *,
    reason: str,
    mode: str,
    source_internal: str | None = None,
    engine: str | None = None,
    resolved_function: str | None = None,
    public_function: str | None = None,
    kwargs: dict[str, Any] | None = None,
) -> FetchExecutionResult:
    return FetchExecutionResult(
        status=STATUS_ERROR_RUNTIME,
        reason=reason,
        source="fetch",
        source_internal=source_internal,
        engine=engine,
        provider_id="fetch",
        provider_internal=source_internal,
        resolved_function=resolved_function,
        public_function=public_function or resolved_function,
        elapsed_sec=0.0,
        row_count=0,
        columns=[],
        dtypes={},
        preview=[],
        final_kwargs=dict(kwargs or {}),
        mode=mode,
        data=None,
    )


def _resolve_list_function(
    *,
    day_function: str,
    asset: str | None,
    preferred_source: str | None,
    function_registry_path: str | Path,
) -> str | None:
    registry_rows = load_function_registry(function_registry_path)
    candidates: list[str] = []
    if day_function.endswith("_day"):
        candidates.append(day_function[:-4] + "_list")
    if day_function.endswith("_min"):
        candidates.append(day_function[:-4] + "_list")
    if day_function.endswith("_transaction"):
        candidates.append(day_function[:-12] + "_list")
    normalized_asset = str(asset or "").strip().lower()
    if normalized_asset in AUTO_LIST_BY_ASSET:
        candidates.extend(AUTO_LIST_BY_ASSET[normalized_asset])
    preferred = normalize_source(preferred_source)
    seen: set[str] = set()
    fallback_candidate: str | None = None
    for name in candidates:
        normalized_name = str(name).strip()
        if not normalized_name or normalized_name in seen:
            continue
        seen.add(normalized_name)
        row = registry_rows.get(normalized_name)
        if not isinstance(row, dict):
            continue
        if fallback_candidate is None:
            fallback_candidate = normalized_name
        if preferred is None:
            return normalized_name
        row_source = normalize_source(row.get("source_internal") or row.get("provider_internal") or row.get("source"))
        if row_source == preferred:
            return normalized_name
    return fallback_candidate


def _inject_symbols_into_intent(
    *,
    intent: FetchIntent,
    symbols: list[str],
) -> FetchIntent:
    payload: str | list[str]
    if len(symbols) == 1:
        payload = symbols[0]
    else:
        payload = symbols

    kwargs = dict(intent.extra_kwargs)
    if "symbol" in kwargs:
        kwargs["symbol"] = payload
    else:
        kwargs["symbols"] = payload
    return FetchIntent(
        asset=intent.asset,
        freq=intent.freq,
        venue=intent.venue,
        universe=intent.universe,
        adjust=intent.adjust,
        symbols=payload,
        start=intent.start,
        end=intent.end,
        function_override=intent.function_override,
        source_hint=intent.source_hint,
        public_function=intent.public_function,
        auto_symbols=False,
        sample=intent.sample,
        extra_kwargs=kwargs,
    )


def _run_auto_symbols_planner_for_intent(
    *,
    intent: FetchIntent,
    policy: FetchExecutionPolicy,
    base_kwargs: dict[str, Any],
    window_profile_path: str | Path,
    exception_decisions_path: str | Path,
    function_registry_path: str | Path,
    routing_registry_path: str | Path,
) -> tuple[FetchExecutionResult, list[dict[str, Any]]]:
    resolution = resolve_fetch(
        asset=intent.asset or "",
        freq=intent.freq or "",
        venue=_effective_intent_venue(intent),
        adjust=intent.adjust,
    )
    _validate_routing_registry_resolution(
        routing_registry_path=routing_registry_path,
        public_function=resolution.public_name,
    )
    list_function = _resolve_list_function(
        day_function=resolution.public_name,
        asset=intent.asset,
        preferred_source=resolution.source,
        function_registry_path=function_registry_path,
    )
    step_records: list[dict[str, Any]] = []

    list_kwargs: dict[str, Any] = {}
    for key in ("start", "end", "venue", "adjust"):
        if key in base_kwargs and base_kwargs.get(key) is not None:
            list_kwargs[key] = base_kwargs.get(key)
    if not list_function:
        list_result = _planner_error_result(
            reason="auto_symbols: list function is not resolvable",
            mode=policy.mode,
            source_internal=PLANNER_SOURCE_INTERNAL,
        )
        list_request = {
            "mode": policy.mode,
            "policy": _build_policy_payload(policy),
            "reason": "auto_symbols_list_function_missing",
        }
    else:
        list_result = execute_fetch_by_name(
            function=list_function,
            kwargs=dict(list_kwargs),
            policy=policy,
            source_hint=resolution.source,
            public_function=list_function,
            window_profile_path=window_profile_path,
            exception_decisions_path=exception_decisions_path,
            function_registry_path=function_registry_path,
            write_evidence=False,
            _allow_evidence_opt_out=True,
        )
        list_request = _build_function_request_payload_for_evidence(
            function=list_function,
            kwargs=list_kwargs,
            policy=policy,
            source_hint=resolution.source,
            public_function=list_function,
        )
    step_records.append(
        {
            "step_kind": AUTO_SYMBOLS_MA250_STEP_SEQUENCE[0],
            "request_payload": list_request,
            "result": list_result,
        }
    )

    sample_plan = _extract_sample_plan(intent)
    sample_n = int(sample_plan["n"])
    sample_method = str(sample_plan["method"])
    sample_seed = sample_plan.get("seed")
    sample_liquidity_field = sample_plan.get("liquidity_field")
    sample_industry_field = sample_plan.get("industry_field")
    if policy.max_symbols is not None:
        sample_n = min(sample_n, int(policy.max_symbols))
    strategy_params: dict[str, Any] = {
        "n": sample_n,
        "method": sample_method,
    }
    if sample_seed is not None:
        strategy_params["seed"] = int(sample_seed)
    if isinstance(sample_liquidity_field, str) and sample_liquidity_field.strip():
        strategy_params["liquidity_field"] = sample_liquidity_field.strip()
    if isinstance(sample_industry_field, str) and sample_industry_field.strip():
        strategy_params["industry_field"] = sample_industry_field.strip()
    sampled_symbols: list[str] = []
    if list_result.status == STATUS_PASS_HAS_DATA:
        candidates = _extract_candidates_from_preview(list_result.preview)
        if not candidates:
            candidates = _extract_candidates_from_preview(list_result.data)
        sampled_symbols, strategy_params = _select_sample_symbols(
            candidates,
            sample_n=sample_n,
            sample_method=sample_method,
            seed=sample_seed,
            liquidity_field=sample_liquidity_field,
            industry_field=sample_industry_field,
        )
        sample_n = int(strategy_params.get("n", sample_n))
        sample_method = str(strategy_params.get("method", sample_method))
        sample_result = _planner_sample_result(
            mode=policy.mode,
            symbols=sampled_symbols,
            sample_n=sample_n,
            sample_method=sample_method,
            strategy_params=strategy_params,
        )
    elif list_result.status == STATUS_PASS_EMPTY:
        strategy_params["candidate_count"] = 0
        strategy_params["selected_count"] = 0
        strategy_params["selected_symbols"] = []
        sample_result = _planner_sample_result(
            mode=policy.mode,
            symbols=[],
            sample_n=sample_n,
            sample_method=sample_method,
            strategy_params=strategy_params,
        )
    else:
        strategy_params["candidate_count"] = 0
        strategy_params["selected_count"] = 0
        strategy_params["selected_symbols"] = []
        sample_result = FetchExecutionResult(
            status=STATUS_BLOCKED_SOURCE_MISSING,
            reason=f"upstream_list_failed: {list_result.status}",
            source="fetch",
            source_internal=PLANNER_SOURCE_INTERNAL,
            engine=None,
            provider_id="fetch",
            provider_internal=PLANNER_SOURCE_INTERNAL,
            resolved_function="planner_sample_symbols",
            public_function="planner_sample_symbols",
            elapsed_sec=0.0,
            row_count=0,
            columns=[],
            dtypes={},
            preview=[],
            final_kwargs={
                "sample_n": sample_n,
                "sample_method": sample_method,
                "sample_strategy": _json_safe(dict(strategy_params)),
            },
            mode=policy.mode,
            data=None,
        )
    sample_request = {
        "mode": policy.mode,
        "planner_step": "sample",
        "sample": {"n": sample_n, "method": sample_method},
        "sample_strategy": _json_safe(dict(strategy_params)),
        "candidates_preview_count": int(getattr(list_result, "row_count", 0)),
    }
    step_records.append(
        {
            "step_kind": AUTO_SYMBOLS_MA250_STEP_SEQUENCE[1],
            "request_payload": sample_request,
            "result": sample_result,
        }
    )

    if sampled_symbols:
        day_intent = _inject_symbols_into_intent(intent=intent, symbols=sampled_symbols)
        day_kwargs = _intent_effective_kwargs(day_intent)
        day_result = execute_fetch_by_name(
            function=resolution.public_name,
            kwargs=day_kwargs,
            policy=policy,
            source_hint=resolution.source,
            public_function=resolution.public_name,
            window_profile_path=window_profile_path,
            exception_decisions_path=exception_decisions_path,
            function_registry_path=function_registry_path,
            write_evidence=False,
            _allow_evidence_opt_out=True,
        )
        day_request = _build_intent_request_payload_for_evidence(
            intent=day_intent,
            policy=policy,
            resolved_function=resolution.public_name,
            kwargs=day_kwargs,
            source_hint=resolution.source,
            public_function=resolution.public_name,
        )
    else:
        day_intent = _inject_symbols_into_intent(intent=intent, symbols=[])
        day_kwargs = _intent_effective_kwargs(day_intent)
        day_result = _planner_error_result(
            reason="auto_symbols: sample step produced no symbols",
            mode=policy.mode,
            source_internal=resolution.source,
            engine=_engine_from_source(resolution.source),
            resolved_function=resolution.public_name,
            public_function=resolution.public_name,
            kwargs=day_kwargs,
        )
        day_request = _build_intent_request_payload_for_evidence(
            intent=day_intent,
            policy=policy,
            resolved_function=resolution.public_name,
            kwargs=day_kwargs,
            source_hint=resolution.source,
            public_function=resolution.public_name,
        )
    step_records.append(
        {
            "step_kind": AUTO_SYMBOLS_MA250_STEP_SEQUENCE[2],
            "request_payload": day_request,
            "result": day_result,
        }
    )
    return day_result, step_records


def _effective_timeout(policy: FetchExecutionPolicy, profile_item: dict[str, Any]) -> int | None:
    if policy.timeout_sec is not None:
        return int(policy.timeout_sec)
    if policy.mode == "smoke":
        raw = profile_item.get("smoke_timeout_sec") if isinstance(profile_item, dict) else None
        if raw is None:
            return 30
        try:
            return int(raw)
        except Exception:
            return 30
    return None


def _engine_from_source(source_internal: str | None) -> str | None:
    normalized = normalize_source(source_internal)
    if is_mongo_source(normalized):
        return "mongo"
    if is_mysql_source(normalized):
        return "mysql"
    return None


def _resolve_callable(function: str, *, source_hint: str | None) -> tuple[Any, str]:
    hint = normalize_source(source_hint)
    if is_mongo_source(hint):
        return resolve_mongo_fetch_callable(function), "mongo_fetch"
    if is_mysql_source(hint):
        return resolve_mysql_fetch_callable(function), "mysql_fetch"
    try:
        return resolve_mongo_fetch_callable(function), "mongo_fetch"
    except Exception:
        return resolve_mysql_fetch_callable(function), "mysql_fetch"


def _prepare_kwargs_for_callable(fn: Any, kwargs: dict[str, Any]) -> dict[str, Any]:
    sig = inspect.signature(fn)
    params = sig.parameters
    out = dict(kwargs)

    if "symbols" in out:
        symbols = out.pop("symbols")
        if "code" in params and "code" not in out:
            out["code"] = symbols
        elif "symbol" in params and "symbol" not in out:
            out["symbol"] = symbols
        elif _has_var_kw(params):
            out["symbols"] = symbols

    if "freq" in out and "frequence" in params and "frequence" not in out:
        out["frequence"] = out.pop("freq")

    if "format" in params and "format" not in out:
        out["format"] = "pd"

    if not _has_var_kw(params):
        out = {k: v for k, v in out.items() if k in params}

    missing = []
    for name, p in params.items():
        if p.kind in (inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL):
            continue
        if p.default is inspect._empty and name not in out:
            missing.append(name)
    if missing:
        raise ValueError(f"missing required params for {fn.__name__}: {', '.join(missing)}")

    return out


def _apply_max_symbols_to_kwargs(kwargs: dict[str, Any], *, max_symbols: int | None) -> dict[str, Any]:
    if max_symbols is None:
        return dict(kwargs)
    limited = dict(kwargs)
    for key in ("symbols", "symbol", "code"):
        if key in limited:
            limited[key] = _truncate_symbol_selector(limited.get(key), max_symbols=max_symbols)
    return limited


def _truncate_symbol_selector(value: Any, *, max_symbols: int) -> Any:
    if max_symbols <= 0:
        return value
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, tuple):
        return list(value)[:max_symbols]
    if isinstance(value, list):
        return list(value)[:max_symbols]
    return value


def _apply_max_rows_to_payload(payload: Any, *, max_rows: int | None) -> Any:
    if max_rows is None:
        return payload
    limited_rows = max(1, int(max_rows))

    try:
        import pandas as pd
    except Exception:
        pd = None

    if pd is not None and isinstance(payload, pd.DataFrame):
        return payload.head(limited_rows).copy()
    if isinstance(payload, list):
        return payload[:limited_rows]
    return payload


def _has_var_kw(params: dict[str, inspect.Parameter]) -> bool:
    return any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())


def _is_semantically_missing_value(value: Any, *, pd_module: Any = None) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if pd_module is not None:
        try:
            is_na = pd_module.isna(value)
        except Exception:
            is_na = False
        try:
            if bool(is_na):
                return True
        except Exception:
            pass
    try:
        same = value == value
    except Exception:
        same = True
    return same is False


def _payload_has_observable_data(data: Any, *, pd_module: Any = None) -> bool:
    if data is None:
        return False
    if pd_module is not None and isinstance(data, pd_module.DataFrame):
        if data.empty:
            return False
        for row in data.itertuples(index=False, name=None):
            for value in row:
                if not _is_semantically_missing_value(value, pd_module=pd_module):
                    return True
        return False
    if isinstance(data, list):
        if not data:
            return False
        if all(isinstance(item, dict) for item in data):
            for row in data:
                for value in row.values():
                    if not _is_semantically_missing_value(value, pd_module=pd_module):
                        return True
            return False
        for value in data:
            if not _is_semantically_missing_value(value, pd_module=pd_module):
                return True
        return False
    if isinstance(data, tuple):
        return _payload_has_observable_data(list(data), pd_module=pd_module)
    if isinstance(data, dict):
        if not data:
            return False
        for value in data.values():
            if not _is_semantically_missing_value(value, pd_module=pd_module):
                return True
        return False
    return not _is_semantically_missing_value(data, pd_module=pd_module)


def _normalize_payload(payload: Any) -> tuple[Any, str, int, list[str], dict[str, str], Any]:
    try:
        import pandas as pd
    except Exception:
        pd = None

    data = payload
    typ = type(payload).__name__
    if pd is not None and isinstance(payload, pd.DataFrame):
        pass
    else:
        data_attr = getattr(payload, "data", None)
        if pd is not None and isinstance(data_attr, pd.DataFrame):
            data = data_attr
            typ = type(payload).__name__

    if data is None:
        return None, typ, 0, [], {}, None

    if pd is not None and isinstance(data, pd.DataFrame):
        cols = [str(c) for c in data.columns]
        dtypes = {str(k): str(v) for k, v in data.dtypes.items()}
        row_count = int(len(data)) if _payload_has_observable_data(data, pd_module=pd) else 0
        preview = _json_safe(data.head(5).to_dict(orient="records")) if row_count > 0 else []
        return data, "DataFrame", row_count, cols, dtypes, preview

    if isinstance(data, list):
        row_count = int(len(data))
        if row_count <= 0:
            return data, typ, 0, [], {}, []
        if all(isinstance(item, dict) for item in data):
            cols: list[str] = []
            dtypes: dict[str, str] = {}
            for row in data:
                for raw_col, value in row.items():
                    col = str(raw_col)
                    if col not in cols:
                        cols.append(col)
                    if col not in dtypes and value is not None:
                        dtypes[col] = type(value).__name__
            if not _payload_has_observable_data(data, pd_module=pd):
                return data, typ, 0, cols, dtypes, []
            return data, typ, row_count, cols, dtypes, _json_safe(data)
        if not _payload_has_observable_data(data, pd_module=pd):
            return data, typ, 0, [], {}, []
        return data, typ, row_count, [], {}, _json_safe(data)

    if isinstance(data, dict):
        cols = [str(col) for col in data.keys()]
        dtypes = {str(col): type(value).__name__ for col, value in data.items() if value is not None}
        if not _payload_has_observable_data(data, pd_module=pd):
            return data, typ, 0, cols, dtypes, []
        return data, typ, 1, cols, dtypes, _json_safe(data)

    if not _payload_has_observable_data(data, pd_module=pd):
        return data, typ, 0, [], {}, []

    try:
        row_count = int(len(data))
    except Exception:
        row_count = 1
    return data, typ, row_count, [], {}, _json_safe(data)


def _classify_exception(source: str | None, exc: Exception) -> tuple[str, str]:
    msg = f"{type(exc).__name__}: {exc}"
    lower = msg.lower()
    if isinstance(exc, TimeoutError):
        return STATUS_ERROR_RUNTIME, msg

    blocked_markers = [
        "unknown table",
        "doesn't exist",
        "does not exist",
        "no such table",
        "can't connect to mysql",
        "connection refused",
        "serverselectiontimeout",
    ]
    if any(marker in lower for marker in blocked_markers):
        return STATUS_BLOCKED_SOURCE_MISSING, msg

    if is_mongo_source(source):
        no_data_markers = [
            "none",
            "empty",
            "no data",
            "not found",
            "dataframe' object has no attribute 'datetime'",
        ]
        if any(marker in lower for marker in no_data_markers):
            return STATUS_PASS_EMPTY, f"no_data: {msg}"

    return STATUS_ERROR_RUNTIME, msg


def _call_with_timeout(fn: Any, *, timeout_sec: int | None) -> Any:
    if timeout_sec is None or timeout_sec <= 0 or not hasattr(signal, "SIGALRM"):
        return fn()

    def _handler(_signum: int, _frame: Any) -> None:
        raise TimeoutError(f"timeout_skip_{timeout_sec}s")

    prev = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, _handler)
    signal.alarm(timeout_sec)
    try:
        return fn()
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, prev)


def _write_preview_csv(path: Path, result: FetchExecutionResult) -> None:
    try:
        import pandas as pd
    except Exception:
        pd = None

    data = result.data
    if pd is not None and isinstance(data, pd.DataFrame):
        data.head(20).to_csv(path, index=False)
        return

    preview = result.preview
    if isinstance(preview, list) and preview and isinstance(preview[0], dict):
        if pd is not None:
            pd.DataFrame(preview).to_csv(path, index=False)
        else:
            path.write_text(json.dumps(preview, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return

    row = {
        "status": result.status,
        "reason": result.reason,
        "row_count": result.row_count,
        "source": "fetch",
        "source_internal": result.source_internal,
        "engine": result.engine,
        "resolved_function": result.resolved_function,
    }
    path.write_text(",".join(row.keys()) + "\n" + ",".join(str(v) for v in row.values()) + "\n", encoding="utf-8")


def _json_safe(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, list):
        return [_json_safe(x) for x in obj]
    if isinstance(obj, tuple):
        return [_json_safe(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    try:
        import pandas as pd

        if isinstance(obj, pd.Timestamp):
            return obj.isoformat()
    except Exception:
        pass
    return str(obj)
