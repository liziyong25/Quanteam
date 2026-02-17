# Phase-18: LLM Provider + Cassette Replay v1

## Goal

- Add a pluggable LLM provider interface for Agents Plane.
- Add deterministic cassette record/replay (JSONL) for offline verification.
- Add input sanitization/redaction to prevent holdout/secret leaks.
- Evidence all LLM calls for UI review (read-only).

## Scope

- In scope: `src/quant_eam/llm/**`, agent harness upgrades, UI job page evidence display, contracts (llm_call/llm_session), tests, docs.
- Out of scope: changing kernel arbitration chain (compiler/runner/gaterunner/registry), changing policies v1.

## Deliverables

- LLM modules:
  - `src/quant_eam/llm/provider.py`
  - `src/quant_eam/llm/cassette.py`
  - `src/quant_eam/llm/redaction.py`
- Harness evidence:
  - `llm_calls.jsonl`, `llm_session.json`, `redaction_summary.json`
- Contracts:
  - `contracts/llm_call_schema_v1.json`
  - `contracts/llm_session_schema_v1.json`
- UI:
  - `/ui/jobs/{job_id}` shows “LLM Evidence” section (read-only)

## Execution Log

- Start Date (Asia/Taipei): 2026-02-10
- End Date (Asia/Taipei): 2026-02-10
- Commit: unknown
- Notes:
  - Implemented cassette replay keyed by prompt_hash derived from sanitized input + prompt template.
  - Implemented redaction rules to block holdout/secret leaks into any LLM call record.

