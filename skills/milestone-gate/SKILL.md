---
name: milestone-gate
description: Execute capability-cluster milestone strict gates, whitelist commit staging, and push fallback logic.
---

# Milestone Gate

## Use When

- A capability cluster reaches implemented readiness.
- Controller must run strict acceptance gates before commit/push.

## Strict Gate

1. `python3 scripts/check_docs_tree.py`
2. `python3 scripts/check_subagent_packet.py --phase-id <latest_phase_id>`
3. Cluster acceptance commands and required tests pass.
4. Commit scope is whitelist-only.
5. Redlines are blocked unless explicit policy waiver exists.

## Commit/Push Flow

1. Stage explicit whitelist paths only.
2. Commit with milestone message format.
3. Push `origin/master` first.
4. On failure, push fallback branch `autopilot/milestone-<id>`.
5. Record milestone artifacts and SSOT history.

## Guardrails

- Never use destructive git commands.
- Never stage unrelated dirty files.
