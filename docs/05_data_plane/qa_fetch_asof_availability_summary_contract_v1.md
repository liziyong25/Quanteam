# QA Fetch AsOf Availability Summary Contract v1

## Purpose

Freeze deterministic evidence metadata fields for `as_of` and preview-level `available_at` availability summary, aligned with `available_at<=as_of` policy semantics.

## Scope

Applies to fetch result meta documents:
- canonical: `fetch_result_meta.json`
- step-level: `step_XXX_fetch_result_meta.json`

## Required Metadata Fields

- `as_of`: normalized as_of value extracted from fetch request in stable UTC format
  `YYYY-MM-DDTHH:MM:SSZ` (nullable string when absent/unparseable).
- `availability_summary`:
  - `has_as_of`: boolean
  - `as_of`: same normalized UTC value (nullable string)
  - `available_at_field_present`: boolean
  - `available_at_min`: minimum preview available_at value (nullable string)
  - `available_at_max`: maximum preview available_at value (nullable string)
  - `available_at_violation_count`: integer count of preview rows with `available_at > as_of` (when both are parseable)
  - `rule`: fixed text `available_at<=as_of`

## Determinism Rules

- Summary must be computed from request + preview only; no external state/network.
- Missing/invalid timestamps must not fail fetch execution; emit safe nullable fields.
- Summary is additive metadata and must not alter existing status or result payload.
