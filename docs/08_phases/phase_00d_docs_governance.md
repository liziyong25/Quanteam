# Phase-00D: Docs & Governance Bootstrap

## 1) 目标（Goal）

- Establish `docs/` as SSOT for governance, protocols, runbooks, and phase execution logs.
- Standardize templates (phase log, ADR) and a Codex phase prompt footer snippet.

## 2) 范围（Scope）

### In Scope

- `docs/` structure and content: overview, governance, protocols, runbooks, phases, ADR template, snippets
- Record Phase-00A execution results into `docs/08_phases/phase_00a_repo_bootstrap.md`
- Optional docs tree checker script

### Out of Scope

- No changes to runtime/business code: `src/**`, `docker-compose.yml`, `pyproject.toml`, `Makefile`, `docker/**`, `tests/**`
- No touching `contracts/**` or `policies/**` content in this phase

## 3) 验收标准（Acceptance / DoD）

- Key files exist:
  - `docs/README.md`
  - `docs/01_governance.md`
  - `docs/02_protocols.md`
  - `docs/07_runbooks/local_dev.md`
  - `docs/07_runbooks/troubleshooting.md`
  - `docs/08_phases/phase_template.md`
  - `docs/08_phases/phase_00a_repo_bootstrap.md`
  - `docs/09_adr/0000_template.md`
  - `docs/_snippets/codex_phase_footer.md`
  - `GOVERNANCE.md`

## 4) 完成记录（Execution Log）

- Start Date: 2026-02-09 (Asia/Taipei)
- End Date: 2026-02-09 (Asia/Taipei)
- PR/Commit: unknown (repo is not a git repository; `git rev-parse --short HEAD` fails)
- Notes:
  - SSOT 收敛：明确 `docs/README.md` 为唯一 canonical 入口，删除重复入口文件以避免漂移
  - Governance/Protocols 去重与结构化：以“规则 + 禁止项 + enforcement”写法明确由 CI/review、Kernel、UI 分别阻断越权行为
  - 增强可执行检查：保留 `scripts/check_docs_tree.py` 并提供 `make docs-check`（若存在）

## 5) 遗留问题（Open Issues）

- [ ] Add a CI check to enforce docs tree and lint markdown (optional, future phase).
