# Dossier Manifest v1 (`dossier_v1`)

Schema: `contracts/dossier_schema_v1.json`

## Purpose

- Producer: kernel/runner (future).
- Consumer: UI + gates + registry (future).

Dossier is the evidence bundle. This schema validates the manifest metadata and artifact path mapping, not the directory itself.

## Top-Level Fields (v1)

- `schema_version`: must be `"dossier_v1"`
- `extensions`: optional object for forward-compatible metadata (must not override governance/policies)
- `run_id`
- `created_at`
- `blueprint_hash`
- `policy_bundle_id`
- `data_snapshot_id`
- `append_only`: must be `true`
- `artifacts`: logical name -> path string
- `hashes`: optional path -> sha256 map

## Evidence Chain Rule

Any PASS/FAIL/Registry write must reference dossier artifacts (e.g. `gate_results_json`) via this manifest.

## Examples

- OK: `contracts/examples/dossier_ok.json`
- BAD: `contracts/examples/dossier_bad.json` (`append_only=false` fails)
- BAD: `contracts/examples/dossier_missing_data_snapshot_id_bad.json` (missing required field)
