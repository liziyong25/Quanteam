# LLM Provider + Cassette Replay v1 (Agents Plane)

This doc defines the engineering plumbing for integrating real LLM providers **without breaking determinism, replayability, or governance redlines**.

## Core Rules

- Default tests/CI must be offline and deterministic.
- Any LLM interaction must be **recordable and replayable** (cassette).
- Before any LLM call, inputs must be sanitized:
  - remove sensitive keys (at minimum: `holdout`, `vault`, `secret`, `token`, `auth`)
  - truncate large payloads deterministically
  - replace absolute local paths (`/data`, `/artifacts`, etc.) with placeholders
- **Holdout must not be sent** to the LLM. (Only minimal holdout summary is allowed for UI; LLM inputs must not include it.)

## Configuration (env)

- `EAM_LLM_PROVIDER`: `mock` (default) or `real_stub`
- `EAM_LLM_MODE`: `live` | `record` | `replay` (default: `live`)
- `EAM_LLM_CASSETTE_DIR`: directory for cassette storage (default: agent output dir)

Notes:
- In this MVP, agent implementations are deterministic and do not require an external model.
- `record` and `replay` are still supported via cassette files (see below).

## Cassette v1

Cassette format is JSONL (append-only), one call per line.

- File: `<cassette_dir>/cassette.jsonl`
- Lookup key: `prompt_hash` (sha256 of a canonical, sanitized request object)

Replay semantics:
- In `replay` mode, the harness **must** find a matching `prompt_hash` in the cassette.
- If missing: treat as INVALID (do not proceed silently).

## Evidence Files (per agent run)

Agent output directories (Job outputs) store additional read-only evidence:

`<job_outputs>/agents/<agent_step>/`

- `llm_calls.jsonl`: evidence of the call used for this run (sanitized request + response)
- `llm_session.json`: summary (provider/mode/call_count/prompt_hashes + cassette path)
- `redaction_summary.json`: what was removed/truncated and the `sanitized_sha256`

These files are intended for UI review and audit.

