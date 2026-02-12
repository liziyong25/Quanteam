# Phase-XX: <Phase Title>

## 1) 目标（Goal）
- <一句话：本 Phase 完成什么能力>

## 2) 背景（Background）
- 为什么要做这个 Phase？
- 与整体架构（Kernel/Agents/UI/Contracts/Policies）关系是什么？

## 3) 范围（Scope）
### In Scope
- <列出将实现的内容>

### Out of Scope
- <明确不做的内容，防止跑偏>

## 4) 实施方案（Implementation Plan）
- 架构/模块拆分
- 数据流与控制流
- 关键边界（deterministic vs agent）
- 风险点与规避策略

## 4.1) Subagent Control Packet（必填）
- `phase_id`: `phase_XX`
- `packet_root`: `artifacts/subagent_control/<phase_id>/`
- 发布阶段（主控）必须生成：`task_card.yaml`
- 执行阶段（subagent）必须生成：`executor_report.yaml`
- 验收阶段（主控）必须生成：`validator_report.yaml`

## 5) 编码内容（Code Deliverables）
- 修改目录范围（必须写清楚）：`<allowed_dirs>`
- 新增/修改文件清单（按模块分组）
- 对外接口（函数/CLI/API）定义
- 示例命令（Linux+Docker）

## 6) 文档编写（Docs Deliverables）
- 必须更新的 docs：
  - `docs/08_phases/<track>/phase_XX_*.md`（本文件，`<track>`=`00_skeleton` 或 `10_impl`）
  - （如涉及契约）`docs/03_contracts/...`
  - （如涉及 policy）`docs/04_policies/...`
- 若影响协议/边界：新增 ADR（`docs/09_adr/`）

## 7) 验收标准（Acceptance Criteria / DoD）
### 必须可执行的验收命令
- `docker compose up -d`
- `pytest -q`
- `python -m <module> ...`（给出确切命令）
- `python3 scripts/check_subagent_packet.py --phase-id <phase_id>`

### 预期产物（Artifacts）
- 运行后必须生成的文件路径列表（例如 dossier 目录结构）
- 关键字段/指标必须存在且符合 schema

### 质量门槛
- 性能/耗时（可选）
- 可复现性（同输入同输出）
- 无网络 IO（如要求）

## 8) 完成记录（Execution Log）
- Start Date:
- End Date:
- PR/Commit:
- Notes:

## 9) 遗留问题（Open Issues）
- [ ] ...

## 10) Codex Prompt Footer

Append `docs/_snippets/codex_phase_footer.md` to the phase task card prompt for consistency.
