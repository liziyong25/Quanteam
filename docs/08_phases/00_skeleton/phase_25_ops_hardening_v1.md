# Phase-25: Operational Hardening v1

## Goal

- Add local/CI quality gates for sustainable delivery (offline deterministic verification).
- Add artifacts index files to reduce UI/API directory scans.
- Document build performance tips (non-semantic).

## Changes

- Scripts (quality gates):
  - Added `scripts/check_prompts_tree.py` (promptpack structure + front matter validation).
  - Added `scripts/check_contracts_examples.py` (progressive contracts examples coverage check).
  - Added `scripts/ci_local.sh` to run: ruff + docs tree + prompts tree + contracts examples + pytest (inside docker compose).
- Artifacts index:
  - Added `src/quant_eam/index/` (append-only JSONL index builder + reader).
  - Added read-only endpoints:
    - `GET /index/runs`
    - `GET /index/jobs`
  - Updated `GET /runs` to prefer index when present.
- Docs:
  - Added `docs/07_runbooks/build_performance.md`.

## Index Files (Append-Only)

Under `${EAM_ARTIFACT_ROOT}/index/`:

- `runs_index.jsonl`
- `jobs_index.jsonl`

Index build command:

```bash
docker compose run --rm api python -m quant_eam.index
```

## Acceptance Evidence

Run:

```bash
bash scripts/ci_local.sh
python3 scripts/check_docs_tree.py
```

## Files Touched

- `scripts/check_prompts_tree.py`
- `scripts/check_contracts_examples.py`
- `scripts/ci_local.sh`
- `src/quant_eam/index/indexer.py`
- `src/quant_eam/index/reader.py`
- `src/quant_eam/index/cli.py`
- `src/quant_eam/api/read_only_api.py`
- `tests/test_artifacts_index_phase25.py`
- `docs/07_runbooks/build_performance.md`
- `docs/08_phases/00_skeleton/phase_25_ops_hardening_v1.md`
- `scripts/check_docs_tree.py`

---

# Codex Phase Prompt Footer (Appendix, SSOT)

## Required Reading (SSOT)

- `docs/01_governance.md`
- `docs/02_protocols.md`
- The current phase log under `docs/08_phases/` (create/update it)

## Required Deliverables

- Code (only within allowed change scope for this phase)
- Tests (if code changes impact behavior)
- Docs: update `docs/08_phases/00_skeleton/phase_XX_*.md` with execution log and acceptance evidence
- ADR: required when changing any boundary/protocol of contracts/policies/dossier/gates/holdout/determinism

## Hard No (Non-Negotiables)

- Policies are read-only references by `policy_id`. No overriding or inline policy edits in strategy modules.
- Strategy generation must output **Blueprint/DSL** (declarative). No direct executable strategy scripts that bypass the compiler/kernel.
- Arbitration is only via **Gate + Dossier**:
  - PASS/FAIL/registry writes must reference dossier artifacts.
  - Agents must never "decide"; they can propose or analyze only.
- Final Holdout isolation:
  - Must not leak holdout internals into iterative loops.
  - Holdout output is restricted: pass/fail + minimal summary only.
- Dossier is append-only:
  - No rewriting past runs, no overwriting artifacts; new runs create new dossiers.
- Budget/stop conditions are mandatory to prevent unbounded search.
- Every agent must be harnessed:
  - Input/output schema, tests, deterministic replay, and recorded artifacts.

## Acceptance (Evidence Checklist)

- `docker compose up -d` works (if this phase includes runtime changes)
- `pytest -q` passes
- Artifacts path list (host + container mapping) is stated and verified

