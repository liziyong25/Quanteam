# Ruff Lint Coverage Plan (v1)

Purpose: avoid a false sense of quality from a too-small `ruff check` scope. We keep a small, stable gate now,
and expand deterministically over time.

## Current Gate Scope (ci_local.sh)

The current enforced scope is intentionally narrow and focuses on high-churn kernel surfaces.

## Expansion Plan

Next expansions should:

- Add directories in small batches (per phase), with explicit rationale.
- Prefer `ruff check` first (no formatting changes), then later expand `ruff format`.

## Machine-Readable Plan

The block below is parsed by `scripts/check_lint_scope.py`.

```yaml
version: lint_coverage_plan_v1
current_in_ci_local:
  - src/quant_eam/index
  - src/quant_eam/api/read_only_api.py
  - scripts/check_prompts_tree.py
  - scripts/check_contracts_examples.py
  - tests/test_artifacts_index_phase25.py
next_expand:
  - src/quant_eam/llm
  - src/quant_eam/agents
  - src/quant_eam/gates
  - src/quant_eam/gaterunner
  - src/quant_eam/compiler
  - src/quant_eam/runner
  - src/quant_eam/dossier
```

