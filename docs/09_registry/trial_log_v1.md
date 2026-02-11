# TrialLog v1

TrialLog is an **append-only** JSONL log of every run recorded into the Registry.

## Purpose

- Producer: Registry (`record-trial`)
- Consumers: auditing, UI (future), promotion pipelines

TrialLog provides a deterministic record that references the evidence anchors:

- dossier directory
- `gate_results.json`

## Admission Rules (Hard)

- A TrialLog event must reference:
  - `dossier_manifest.json` evidence (run identity + policy bundle + snapshot)
  - `gate_results.json` evidence (overall_pass + gate suite)
- TrialLog recording must validate `gate_results.json` against `gate_results_v1`.
- TrialLog is append-only. Re-recording the same `run_id` is a no-op by default.

## Contract

- Schema: `contracts/trial_event_schema_v1.json`
- Discriminator: `schema_version="trial_event_v1"`

## File

- `<registry_root>/trial_log.jsonl`

Each line is a single JSON object (no multi-line JSON).

