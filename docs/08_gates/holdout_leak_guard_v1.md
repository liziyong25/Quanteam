# Gate: holdout_leak_guard_v1

Purpose: detect **second-order holdout leakage** into iteration-facing artifacts (leaderboards, proposals, reports).

This gate does not judge strategy quality. It enforces a hard governance boundary:

- Allowed: holdout pass/fail and a tiny text summary (no numbers).
- Forbidden: any numeric holdout metrics, curves, trades, or optimization-relevant details leaking into artifacts that can be iterated on.

## Scanned Targets (MVP)

The gate scans (when present):

- `jobs/*/outputs/sweep/leaderboard.json`
- `jobs/*/outputs/sweep/trials.jsonl`
- `jobs/*/outputs/proposals/*.json`
- `dossiers/*/attribution_report.json`
- current dossier:
  - `reports/report.md`
  - `segments_summary.json`

## Rules (MVP)

- JSON/JSONL: any key containing `"holdout"` must not carry numeric values (including percentages) in its value.
- Markdown: any line mentioning `"holdout"` that also contains a numeric token is considered leakage.

## Semantics

- Leakage found: **FAIL** (not INVALID).
- Parse errors on existing files: **INVALID** (evidence cannot be trusted).

## Evidence

Gate results include:

- `leak_count`
- up to 50 leak examples (`file`, `location`, `snippet`)
- scanned file list (truncated)

