# Phase-21: Evaluation Protocol v1 (Segments + Walk-Forward + Purge/Embargo)

## 1) 目标（Goal）
- 将 `train/test/holdout` 多段评估协议固化为确定性产物，贯穿 Compiler -> RunSpec -> Runner -> Dossier -> GateRunner -> UI。
- 支持 `fixed_split` 与 `walk_forward`，并明确 `purge/embargo` 的确定性口径。
- Holdout 输出仍严格最小化（pass/fail + minimal summary），不得落盘曲线/逐笔到可被迭代消费的位置。

## 2) 背景（Background）
- v1 MVP 仅有单一 test 段回测与 gate；在引入 walk-forward 后，需要统一协议与证据结构，避免评估漂移与 holdout 泄漏。

## 3) 范围（Scope）
### In Scope
- Compiler 生成 `runspec.segments.list`（在不破坏 `run_spec_v1` schema 的前提下）。
- Runner 按 segment 执行并写入 `dossiers/<run_id>/segments/...` 证据，同时写 `segments_summary.json`。
- GateRunner 按 test segment 运行 segment-specific gates；holdout 只输出 minimal summary。
- UI `/ui/runs/{run_id}` 支持 segment 切换；holdout 视图禁止展示曲线/逐笔。

### Out of Scope
- 不修改 `policies/**` 的任何 v1 文件。
- 不引入网络 IO；tests 离线 deterministic。

## 4) 实施方案（Implementation Plan）
- RunSpec v1 兼容：
  - 保留 `runspec.segments.train/test/holdout`（schema required）
  - 追加 `runspec.segments.list`（additionalProperties 允许）
- Runner：
  - 顶层保留 legacy `metrics.json/curve.csv/trades.csv`
  - 追加 `segments_summary.json` + `segments/<segment_id>/...`
  - holdout segment 不写曲线/逐笔，交由 HoldoutVault + holdout gate 输出 minimal summary
- GateRunner：
  - run-level gates 保持不变
  - test segments 运行 no-lookahead / stress_lag / stress_cost 等 segment-specific gates
  - holdout gate 只运行一次，产出 minimal summary

## 7) 验收标准（Acceptance Criteria / DoD）
- `EAM_UID=$(id -u) EAM_GID=$(id -g) docker compose run --rm api pytest -q`
- `python3 scripts/check_docs_tree.py`

## 8) 完成记录（Execution Log）
- Start Date: 2026-02-10
- End Date: 2026-02-10

## 10) Codex Prompt Footer

Append `docs/_snippets/codex_phase_footer.md` to the phase task card prompt for consistency.

