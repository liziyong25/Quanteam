# Profile Tuning Guide

## Keys

1. `include_heading_regex`: Keep clauses under headings matching any regex.
2. `exclude_heading_regex`: Drop clauses under headings matching any regex.
3. `keep_clause_regex`: Force-keep clause lines even if heading filter misses.
4. `min_clause_len`: Filter out short noisy bullets.
5. `max_requirements`: Hard cap extracted rows for a source document.
6. `dedup`: Drop semantically repeated clauses after normalization.

## Suggested Targets

1. `WV` (framework): 100-160 rows.
2. `QF` (fetch impl): 70-120 rows.
3. `WB` (workbench): 40-80 rows.

## Phase Bundling Standard

Use requirement-to-goal bundling to avoid line-by-line phases.
Bundle sibling requirements into one phase when all are true:
1. Same `owner_track`.
2. Same `source_document`.
3. Same parent requirement (`depends_on_req_ids` share one parent).
4. Source lines are near-adjacent (`<= 6` lines).
5. Parent clause indicates multi-condition closure (for example: `必须同时满足` / `simultaneously satisfy`) or sibling density is high (>= 3).

## Tuning Sequence

1. Adjust `include_heading_regex` first to keep only requirement-dense chapters.
2. Tighten `exclude_heading_regex` to remove narrative sections.
3. Use `keep_clause_regex` to preserve critical FR/NFR/API lines.
4. Apply `max_requirements` only as a final guardrail, not as the primary filter.
5. Run `--mode plan` after migrate to ensure non-empty selectable goals.
