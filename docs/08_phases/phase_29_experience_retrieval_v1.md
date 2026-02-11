# Phase-29: Experience Retrieval v1 (deterministic, evidence-first)

## Goal

- Add deterministic experience retrieval over Registry/Cards (+ Phase-25 index when available).
- Extract results into an evidence-first `ExperiencePack` for jobs so agents can reference prior runs without drift.
- Render ExperiencePack on the job review UI.

## Changes

- Experience searcher:
  - Added `src/quant_eam/registry/experience_retrieval.py` (ExperienceQuery + deterministic ranking + explanations).
- ExperiencePack:
  - Added `src/quant_eam/agents/experience_pack.py` to write append-only:
    - `jobs/<job_id>/outputs/experience/experience_pack.json`
- Agent integration (minimal):
  - IntentAgent writes ExperiencePack before drafting blueprint.
  - ImprovementAgent writes ExperiencePack before proposing improvements.
- API:
  - Added read-only endpoint `GET /experience/search`.
- UI:
  - `/ui/jobs/{job_id}` renders ExperiencePack (top matches + why matched + links).
- Contracts:
  - Added `contracts/experience_pack_schema_v1.json` (validated via forced schema in tests).
- Docs:
  - Added `docs/09_registry/experience_retrieval_v1.md`.

## Acceptance Evidence

```bash
EAM_UID=$(id -u) EAM_GID=$(id -g) docker compose run --rm api pytest -q
python3 scripts/check_docs_tree.py
```

## Files Touched

- `src/quant_eam/registry/experience_retrieval.py`
- `src/quant_eam/agents/experience_pack.py`
- `src/quant_eam/agents/intent_agent.py`
- `src/quant_eam/agents/improvement_agent.py`
- `src/quant_eam/api/read_only_api.py`
- `src/quant_eam/api/ui_routes.py`
- `src/quant_eam/ui/templates/job.html`
- `contracts/experience_pack_schema_v1.json`
- `tests/test_experience_retrieval_phase29.py`
- `docs/09_registry/experience_retrieval_v1.md`
- `docs/08_phases/phase_29_experience_retrieval_v1.md`
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
- Docs: update `docs/08_phases/phase_XX_*.md` with execution log and acceptance evidence
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

