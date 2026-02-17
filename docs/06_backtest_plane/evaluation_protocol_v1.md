# Evaluation Protocol v1 (Segments + Walk-Forward + Purge/Embargo)

This document defines a deterministic evaluation protocol that expands the single `train/test/holdout` split into a canonical **segments list**.

Goals:

- deterministic segment generation (compiler)
- segment evidence written under a single dossier run (runner)
- gating supports segment-level review, with **holdout restricted to minimal output only**
- UI can switch between segments for review (holdout is minimal-only)

## 1) Terminology

- Segment kinds: `train`, `test`, `holdout`
- A segment has: `start` (YYYY-MM-DD), `end` (YYYY-MM-DD), `as_of` (ISO datetime)
- `holdout=true` indicates the segment is holdout and must obey output restrictions.

## 2) Blueprint Inputs

Blueprint v1 already contains:

- `evaluation_protocol.segments.train/test/holdout`
- `evaluation_protocol.purge.bars`
- `evaluation_protocol.embargo.bars`

Evaluation Protocol v1 adds (forward-compatible fields under `evaluation_protocol` or `blueprint.extensions`):

- `protocol`: `"fixed_split"` | `"walk_forward"`
- `train_window_days`, `test_window_days`, `step_days` (walk-forward)
- `holdout_range`: `{start,end}` override for holdout
- `purge_days`, `embargo_days` (optional override of `purge/embargo` bars; for `1d` treat bars as days)

## 3) Compiler Output (RunSpec v1 compatible)

RunSpec v1 keeps legacy anchors:

- `runspec.segments.train/test/holdout` (single objects; required by schema)

And adds a canonical list under:

- `runspec.segments.list` (array, stable order)

Each list item includes:

- `segment_id` (stable id like `test_000`, `train_001`, `holdout_000`)
- `kind`, `start`, `end`, `as_of`
- `holdout` boolean
- `purge_days`, `embargo_days` (for auditability)

## 4) Walk-Forward Semantics (v1)

Given:

- blueprint `test` date range `[test_start, test_end]`
- `train_window_days`, `test_window_days`, `step_days`

We generate windows:

- `test_i = [test_start + i*step, test_start + i*step + test_window_days - 1]` within `test_end`
- `train_i` ends at the day before the unpurged `test_i.start`

Purge/embargo are applied deterministically around the boundary:

- `train_end_adj = train_end - embargo_days`
- `test_start_adj = test_start + purge_days`

## 5) Runner Evidence Layout (Single Dossier Run)

Under `${EAM_ARTIFACT_ROOT}/dossiers/<run_id>/`:

- top-level artifacts remain for backward compatibility: `metrics.json`, `curve.csv`, `trades.csv`
- segments evidence:
  - `segments_summary.json` (index of segments and artifact refs)
  - `segments/<segment_id>/metrics.json`
  - `segments/<segment_id>/curve.csv`
  - `segments/<segment_id>/trades.csv`

Holdout restriction:

- holdout segment must not write `curve.csv`/`trades.csv` under the dossier segments tree.
- holdout evaluation is performed via HoldoutVault with minimal-only output (pass/fail + tiny summary).

## 6) GateRunner + Holdout Restriction

- test segments: gates may compute full metrics and reference segment artifacts.
- holdout: only minimal summary is emitted (no curves/trades written).

Gate results store segment-level outputs under `gate_results.json.extensions.segment_results`.

