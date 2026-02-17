# Registry v1 (TrialLog + Experience Cards)

Registry is the append-only system of record for:

- TrialLog: record every run as a structured event referencing dossier + gate results
- Experience Cards: governed experience assets created only from Gate PASS runs

Registry exists to prevent "text arbitration" and enforce the hard boundary:

- any admission/promotion must reference `gate_results.json` + dossier artifacts
- no agent/human free-text can directly decide PASS/FAIL or registry writes

## Storage Layout (v1)

Default root:

- env `EAM_REGISTRY_ROOT`, else `${EAM_ARTIFACT_ROOT}/registry`

Layout:

- `<registry_root>/trial_log.jsonl` (append-only)
- `<registry_root>/cards/<card_id>/card_v1.json` (immutable base record)
- `<registry_root>/cards/<card_id>/events.jsonl` (append-only event sourcing)

## Entry Points

CLI:

```bash
python -m quant_eam.registry.cli record-trial --dossier /artifacts/dossiers/<run_id>
python -m quant_eam.registry.cli create-card --run-id <run_id> --title "buyhold_demo"
python -m quant_eam.registry.cli list-cards
python -m quant_eam.registry.cli show-card --card-id <card_id>
```

Docs:

- TrialLog: `docs/09_registry/trial_log_v1.md`
- Experience Cards: `docs/09_registry/experience_cards_v1.md`

