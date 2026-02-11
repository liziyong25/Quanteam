# PromptPack + Output Guard + Regression v1 (Agents Plane)

This document standardizes how Agents evolve prompts and outputs **without drift**:

- prompt content is versioned (PromptPack)
- each run records prompt evidence + hashes
- outputs are checked by deterministic governance guardrails
- regression cases run offline (mock + replay)

## 1) PromptPack v1

### Directory layout

Prompts live under:

- `prompts/agents/<agent_id>/prompt_v1.md`
- `prompts/agents/<agent_id>/prompt_v2.md` (future)

Agent harness loads by env:

- `EAM_AGENT_PROMPTPACK_ROOT` (optional override; default: repo `prompts/agents/`)
- `EAM_AGENT_PROMPT_VERSION` (default: `v1`)

### File format

PromptPack file uses a minimal header, then `---`, then the prompt body:

```text
prompt_version: v1
output_schema_version: blueprint_v1
---
<system prompt body...>
```

Rules:

- `prompt_version` is required (defaults to filename version if missing).
- `output_schema_version` is required (e.g. `blueprint_v1`, `signal_dsl_v1`, `improvement_proposals_v1`).
- Body is treated as the system prompt text; it is recorded for evidence and hashing.

## 2) Evidence + Hashing

Each agent run writes read-only evidence under its output directory:

- `llm_calls.jsonl` (`llm_call_v1`, append-only evidence)
- `llm_session.json` (`llm_session_v1`, summary)
- `redaction_summary.json` (sanitized input hash + removal/truncation evidence)
- `output_guard_report.json` (`output_guard_report_v1`)

### prompt_hash rules (anti-drift)

`prompt_hash` MUST change when any of the following changes:

- `prompt_version`
- `output_schema_version`
- sanitized input (redaction hash)
- prompt content (promptpack sha256)

This prevents cassette replay mis-hits when prompts evolve.

## 3) Output Guard v1 (Hard Rules)

Agents can propose/analyze only; they must not bypass governance boundaries.

Hard guard rules (fail if violated):

- No inline policy params in outputs:
  - e.g. `commission_bps`, `slippage_bps`, `default_latency_seconds`, `asof_rule`, `max_leverage`, etc.
  - outputs may only reference `policy_bundle_id` / `policy_id` (read-only).
- No executable scripts in outputs:
  - forbid keys like `code`, `python`, `script`, `bash`, `shell`.
- No holdout detail leakage:
  - forbid keys / references like `holdout_curve`, `holdout_trades`.
- No policy override blocks:
  - forbid keys like `policy_overrides`, `execution_policy`, `risk_policy`, etc.

Guard report is persisted as `output_guard_report.json` and displayed by UI as evidence.

## 4) Regression Suite v1 (Offline)

Regression cases live under:

- `tests/fixtures/agents/<agent_id>/<case_name>/input.json`
- `tests/fixtures/agents/<agent_id>/<case_name>/expected_output.json`

Runner (offline):

```bash
python -m quant_eam.agents.regression --agent intent_agent_v1 --cases tests/fixtures/agents/intent_agent_v1
```

Notes:

- CI/tests must remain deterministic and offline: use `mock` provider and cassette replay when needed.
- When outputs contain host-specific absolute paths, regression should either:
  - assert a stable subset, or
  - use cassette-based assertions (hash + schema checks).

