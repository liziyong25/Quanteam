# Protocols Index（开发协议总表）

This document defines executable rules for how modules interact. Each section follows:

- Rules: what must be true
- Forbidden: what must never happen
- Enforcement: who blocks violations (CI/review, Kernel, UI)

## 1) Contracts Protocol

Rules:

- Cross-module I/O must be defined by versioned contracts (schema).
- Breaking changes are disallowed; use v2+ and adapters to keep replayability.

Forbidden:

- Ad-hoc payloads or "implicit schema" between modules.
- Mutating stored contract meaning without version bump + ADR.

Enforcement:

- CI / review: require schema versioning + ADR for semantic changes.
- Kernel: validate inputs/outputs against schema at runtime.

## 2) Policies Protocol

Rules:

- Policies are read-only governance inputs selected by `policy_id`.
- Any policy change must be a new version and must have ADR + regression evidence.

Forbidden:

- Overriding, inlining, or temporarily injecting policy behavior in strategy modules.

Enforcement:

- CI / review: block direct policy edits without versioning + ADR.
- Kernel: reject runs if required `policy_id` is missing/invalid; persist `policy_id` into dossier evidence.

## 3) Dossier Protocol（证据包规范）

Rules:

- Dossier is the SSOT for UI and review (no alternative sources).
- Append-only: a run produces a new dossier; old dossiers are never overwritten.
- Any PASS/FAIL/Registry write must reference dossier artifacts (evidence chain).

Forbidden:

- Rewriting past run artifacts/metrics to "fix history" without ADR + migration plan.
- "Pass by log": decisions based on ad-hoc logs without dossier artifacts references.

Enforcement:

- Kernel: produce dossier artifacts + structured metadata; refuse to emit gate/registry decisions without artifacts refs.
- UI: only renders from dossier/gate results; blocks promotion if evidence is missing.

## 4) Agent Harness Protocol

Rules:

- Every agent must be a harness: explicit input/output schema, tests, deterministic replay, recorded artifacts.
- Agents can propose or analyze; they do not arbitrate strategy validity.

Forbidden:

- Agent output directly marking PASS/FAIL or writing to registry without gates/dossier.
- Hidden network IO or non-replayable side effects as part of the agent harness.

Enforcement:

- CI / review: require schema + tests for each agent harness.
- Kernel/UI: only accept agent outputs as proposals; arbitration remains gate-based.

## 5) Diagnostics Protocol（DiagnosticSpec → Promote → GateSpec）

Rules:

- Diagnostics are declared as `DiagnosticSpec` (inputs/steps/outputs) and produce dossier artifacts.
- If a diagnostic becomes a standard check, promote it into a `GateSpec` and add it to a gate suite via policy versioning.
- Any PASS/FAIL outcome must reference dossier artifacts produced by diagnostics/gates.

Forbidden:

- Running one-off diagnostic scripts that bypass dossier output and still influence arbitration.

Enforcement:

- CI / review: promotion requires tests + docs + (if needed) ADR.
- Kernel: executes declared specs and writes artifacts into dossier; gate runner consumes artifacts.

## 6) Holdout Protocol（隔离与输出约束）

Rules:

- Holdout evaluation is isolated from iterative loops (no leakage of holdout internals).
- Holdout output is restricted to pass/fail plus minimal summary, and must reference dossier artifacts.

Forbidden:

- Exposing holdout curves/trades/metrics into tuning loops.
- Using holdout details to adjust parameters without going through governed phases.

Enforcement:

- Kernel: enforce restricted output surface for holdout runs; persist only allowed summaries and artifacts refs.
- UI / review: blocks promotion if holdout evidence chain is missing or too detailed.

