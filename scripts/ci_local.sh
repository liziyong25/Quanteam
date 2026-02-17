#!/usr/bin/env bash
set -euo pipefail

UID_NOW="$(id -u)"
GID_NOW="$(id -g)"

echo "[ci_local] ruff"
# Ensure lint scope plan is present and well-formed (prevents shrinking/phantom gates).
EAM_UID="${UID_NOW}" EAM_GID="${GID_NOW}" docker compose run --rm api python3 scripts/check_lint_scope.py

# Progressive linting: keep the gate focused on Phase-25 surfaces first.
# Expanding to the full repo is expected in later hardening phases.
EAM_UID="${UID_NOW}" EAM_GID="${GID_NOW}" docker compose run --rm api ruff check \
  src/quant_eam/index \
  src/quant_eam/api/read_only_api.py \
  scripts/check_prompts_tree.py \
  scripts/check_contracts_examples.py \
  tests/test_artifacts_index_phase25.py

echo "[ci_local] docs tree"
EAM_UID="${UID_NOW}" EAM_GID="${GID_NOW}" docker compose run --rm api python3 scripts/check_docs_tree.py

echo "[ci_local] prompts tree"
EAM_UID="${UID_NOW}" EAM_GID="${GID_NOW}" docker compose run --rm api python3 scripts/check_prompts_tree.py

echo "[ci_local] contracts examples"
EAM_UID="${UID_NOW}" EAM_GID="${GID_NOW}" docker compose run --rm api python3 scripts/check_contracts_examples.py

echo "[ci_local] pytest"
EAM_UID="${UID_NOW}" EAM_GID="${GID_NOW}" docker compose run --rm api pytest -q

echo "[ci_local] OK"
