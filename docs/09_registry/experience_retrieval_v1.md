# Experience Retrieval v1 (Phase-29)

This document specifies a deterministic, evidence-first experience retrieval layer built on top of:

- Registry (TrialLog + Experience Cards)
- Dossiers (run evidence bundles)
- Artifacts index (Phase-25), when available

No embeddings, no network IO.

## ExperienceQuery (MVP)

Inputs:

- `query` (free text)
- `symbols` (optional list)
- `frequency` (optional)
- `tags` (optional)
- `top_k`

## Ranking (Deterministic)

MVP scoring uses field matches only:

- token matches in card `title` / `extensions.tags` / card event `notes`
- symbol intersection against dossier `config_snapshot.json` runspec extensions
- frequency match against card applicability

Tie-break is deterministic:

1. score desc
2. effective_status (`champion` > `challenger` > `draft` > `retired`)
3. `card_id` lexicographic

Each result must include a `ranking_explain` list (why matched).

## ExperiencePack (Job Evidence, Append-Only)

Written under:

- `jobs/<job_id>/outputs/experience/experience_pack.json`

This is reference material only:

- Agents may cite it, but must not arbitrate PASS/FAIL.
- The pack must not include holdout internals (curve/trades), only minimal references.

Recommended contract schema:

- `contracts/experience_pack_schema_v1.json`

## UI Review

`/ui/jobs/{job_id}` renders ExperiencePack:

- top matches
- links to `/ui/cards/{card_id}` and `/ui/runs/{run_id}`
- `ranking_explain` evidence for matching

