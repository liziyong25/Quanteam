# Phase G343: Requirement Gap Closure (QF-109/QF-110/QF-111/QF-112)

## Goal
- Close requirement gap bundle `QF-109/QF-110/QF-111/QF-112` from `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:209`.

## Requirements
- Requirement IDs: QF-109/QF-110/QF-111/QF-112
- Owner Track: impl_fetchdata
- Clause[QF-109]: 在 Jupyter notebook kernel 内执行（notebooks/qa_fetch_manual_params_v3.ipynb 对应 kernel）。
- Clause[QF-110]: 使用 notebook kernel 的 sys.executable 执行命令，不得替换为宿主 /usr/bin/python3。
- Clause[QF-111]: 适用于验证“notebook 参数集是否可拿到数据”。
- Clause[QF-112]: 在仓库宿主终端执行命令（cwd 必须为 repo root）。

## Architecture
- Single SSOT source: docs/12_workflows/skeleton_ssot_v1.yaml
- Requirement-gap-only planning path.
- Interface-first dependency gate for impl goals.
- Bundling criterion: same owner track + same source document + same parent requirement + near-adjacent source lines.

## DoD
- Acceptance commands pass.
- Packet validator passes.
- SSOT writeback marks linked requirement implemented.

## Implementation Plan
1. Verify G342 completion and load its outputs as hard dependency evidence.
2. Confirm QF-109~QF-112 clauses in `docs/05_data_plane/QA_Fetch_FetchData_Impl_Spec_v1.md:209-214`.
3. Execute `notebooks/qa_fetch_manual_params_v3.ipynb` in its bound kernel and run the parameter-set fetch flow, validating at least one `pass_has_data` result.
4. Enforce notebook command execution via kernel `sys.executable` (not host `/usr/bin/python3`) during fetch flow validation.
5. Run repo-root acceptance checks and update SSOT to mark QF-109~QF-112 as implemented.
