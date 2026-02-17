---
name: packet-evidence-guard
description: Enforce subagent packet evidence completeness and consistency across task/executor/validator artifacts.
---

# Packet Evidence Guard

## Use When

- Generating `artifacts/subagent_control/<phase_id>/` packet files.
- Hardening evidence (`workspace_before/after` + acceptance log).
- Validating changed-files claims against actual snapshots.

## Checklist

1. `task_card.yaml` complete and schema-correct.
2. `executor_report.yaml` includes changed files, command history, skills, reasoning tier.
3. `validator_report.yaml` includes base checks and skill checks.
4. Hardened mode evidence files exist and are cross-consistent.
5. Packet passes:

```bash
python3 scripts/check_subagent_packet.py --phase-id <phase_id>
```

## Guardrails

- Reject empty non-noop changed file sets.
- Reject out-of-scope path changes.
- Reject missing acceptance evidence for required commands.
