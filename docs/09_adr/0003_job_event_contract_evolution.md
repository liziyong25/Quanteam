# ADR-0003: JobEvent Contract Evolution (v1 -> v2)

## Status

Accepted

## Context

`contracts/job_event_schema_v1.json` originally defined the append-only `JobEvent` used by the Orchestrator workflow.

Repo-internal development extended workflow behavior (e.g. improvement proposals/spawn, budget/stop evidence). This is non-breaking for the repo itself, but external tools that vendor/pin an old copy of `job_event_schema_v1` can become out of sync.

We also need an explicit, evidence-carrying stop signal for budget enforcement (LAN-exposed workflow writes should leave an auditable trace).

## Decision

1) Add `contracts/job_event_schema_v2.json` (`schema_version = "job_event_v2"`).

- v2 includes all existing event types plus `STOPPED_BUDGET`.
- Event payload remains append-only and additionalProperties-friendly.

2) Writers emit `job_event_v2` for new events.

- Existing jobs with `job_event_v1` remain replayable (we do not mutate historical event lines).

3) Validators accept both v1 and v2 via `schema_version` dispatch.

## Consequences

- External consumers should treat `schema_version` as the authoritative discriminator and support v1 + v2 during a transition period.
- Repo governance gains a stable stop/budget evidence surface (`STOPPED_BUDGET`) without modifying v1 contract files.

