# Codex Phase Prompt Footer (Append to Every Phase Task Card)

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

