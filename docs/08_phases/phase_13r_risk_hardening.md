# Phase-13R: Non-blocking Risk Hardening (Budget/Lineage/Auth/Contracts)

## Goal

Address Phase-13 non-blocking risk points with:

- documentation completion (SSOT + governance wording)
- small governance convergence (canonical ids, lineage semantics)
- minimal guardrails (budget stop evidence, optional write auth)

Constraints:

- do not refactor Phase-13 features
- no external LLM
- deterministic behavior
- do not modify any existing `*_v1.yaml` policy assets (v1 immutable)
- do not modify any existing v1 contract schema files (add v2 only)

## Scope

In scope:

- Policy bundle canonicalization: `policy_bundle_path` is convenience only; canonical is `policy_bundle_id` + bundle sha256 evidence
- JobEvent contract evolution: add `job_event_v2` (includes `STOPPED_BUDGET`)
- Budget/stop enforcement improvements:
  - lineage fields for spawned jobs (`root_job_id`, `parent_job_id`, `generation`)
  - budget stop reason is evidence-logged as `STOPPED_BUDGET`
  - proposals generation is skipped when no spawn is legally possible (max_total_iterations)
- Optional BasicAuth for write endpoints (LAN hardening), default off

Out of scope:

- full auth/user system
- external consumers migration tooling
- changing existing policy semantics or rewriting historical job artifacts

## Background (Risk Points)

1) `policy_bundle_path` is an input convenience, but without canonicalization it risks drift between path and the actual governance handle (`policy_bundle_id`).

2) `job_event_schema_v1` enum evolution is repo-internal non-breaking, but can break external tools that pin old schemas. We need a governed v2.

3) Budget/stop must be enforced with clear lineage semantics and evidence-carrying stop reasons.

4) With LAN exposure, write endpoints should have an optional lightweight guardrail.

## Implementation Notes

- Canonical policy bundle reference is recorded as:
  - `job_spec.json` / `idea_spec.json`: `policy_bundle_id`
  - `outputs/policy_bundle_ref.json`: `policy_bundle_id` + `policy_bundle_sha256`
- Spawn/proposals budget stops append `STOPPED_BUDGET` with reason + limit + current counters.
- `job_event_v2` is the current writer output; `job_event_v1` remains replayable.
- Write endpoints can be protected by HTTP Basic Auth when enabled via env.

## Execution Log

- Start Date (Asia/Taipei): 2026-02-10
- End Date (Asia/Taipei): 2026-02-10
- Commit: unknown (repo has no git metadata or HEAD not available)

## Acceptance Evidence

1) Build:

```bash
docker compose build api worker
```

2) Tests:

```bash
EAM_UID=$(id -u) EAM_GID=$(id -g) docker compose run --rm api pytest -q
```

3) Policy validate (v1 immutable):

```bash
docker compose run --rm api python -m quant_eam.policies.validate policies/budget_policy_v1.yaml
```

4) Docs tree:

```bash
python3 scripts/check_docs_tree.py
```

5) Optional manual smoke (write auth):

```bash
export EAM_WRITE_AUTH_MODE=basic
export EAM_WRITE_AUTH_USER=admin
export EAM_WRITE_AUTH_PASS=secret

curl -i -X POST http://localhost:8002/jobs/idea -H 'Content-Type: application/json' -d '{}'   # expect 401
curl -i -X POST http://localhost:8002/jobs/idea -u admin:secret -H 'Content-Type: application/json' -d '{}'  # expect 4xx/2xx depending on body, but not 401
```

