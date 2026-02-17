---
name: phase-authoring
description: Author phase documents with stable sections and DoD-focused structure for skeleton/impl tracks.
---

# Phase Authoring

## Use When

- Creating new phase docs under `docs/08_phases/00_skeleton/`.
- Creating new phase docs under `docs/08_phases/10_impl_fetchdata/`.

## Required Structure

1. `# Phase <id>: <title>`
2. `## Goal`
3. `## Requirements`
4. `## Architecture`
5. `## DoD`
6. `## Implementation Plan`

Implementation plan line must be:

- `TBD by controller at execution time.`

## Guardrails

- Keep content concise and requirement-linked.
- Do not include speculative implementation not required by DoD.
- Keep references aligned with SSOT goal id and requirement ids.
