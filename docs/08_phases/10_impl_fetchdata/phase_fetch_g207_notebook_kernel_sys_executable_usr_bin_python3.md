# Phase G207: Requirement Gap Closure (QF-119)

## Goal
- Close requirement gap `QF-119` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:210`.

## Requirements
- Requirement ID: QF-119
- Owner Track: impl_fetchdata
- Clause: 使用 notebook kernel 的 `sys.executable` 执行命令，不得替换为宿主 `/usr/bin/python3`。

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
### 1) Runtime contract closure for notebook-kernel `sys.executable`
- Add deterministic runtime anchors:
  - `NOTEBOOK_KERNEL_PYTHON_EXECUTABLE_RULE = use_notebook_kernel_sys_executable`
  - `NOTEBOOK_KERNEL_FORBIDDEN_HOST_EXECUTABLE = /usr/bin/python3`
- Add runtime helpers in `src/quant_eam/qa_fetch/runtime.py`:
  - `resolve_notebook_kernel_python_executable(...)` to enforce non-empty notebook-kernel executable and reject host `/usr/bin/python3`.
  - `build_notebook_kernel_python_command(...)` to construct command argv prefixed by validated notebook-kernel Python executable.

### 2) Regression test coverage for QF-119
- Extend `tests/test_qa_fetch_runtime.py` with:
  - a QF-119 anchor test for constants,
  - a positive test that resolves from `sys.executable`,
  - a negative test that rejects `/usr/bin/python3`,
  - a command-construction test that verifies notebook-kernel executable prefixing.

### 3) SSOT writeback
- Update `docs/12_workflows/skeleton_ssot_v1.yaml`:
  - goal `G207` status to `implemented`,
  - requirement `QF-119` status to `implemented`,
  - capability cluster `CL_FETCH_207` status to `implemented`,
  - linked interface-contract rows for `QF-119` status to `implemented`.

## Execution Record
- Date: 2026-02-14.
- Implemented notebook-kernel executable contract enforcement in:
  - `src/quant_eam/qa_fetch/runtime.py`
- Added regression coverage in:
  - `tests/test_qa_fetch_runtime.py`
- Scope outcome:
  - Notebook-kernel command execution is now explicitly constrained to `sys.executable`, with host `/usr/bin/python3` rejected by contract.

## Acceptance Record
- `python3 scripts/check_docs_tree.py`
- `python3 -m pytest -q tests/test_qa_fetch_runtime.py`
- `rg -n "G207|QF-119" docs/12_workflows/skeleton_ssot_v1.yaml`
