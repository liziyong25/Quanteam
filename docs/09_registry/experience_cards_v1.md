# Experience Cards v1

Experience Cards are governed experience assets created only from Gate PASS runs.

## Purpose

- Producer: Registry (`create-card`)
- Consumers: UI (future), Composer/Allocator (future)

Cards are **not** subjective summaries. A card must anchor to evidence:

- dossier path
- gate results path
- key dossier artifacts list

## Admission Rules (Hard)

- A card can only be created if the referenced run has:
  - a TrialLog record
  - `overall_pass == true` in `gate_results.json`
- No agent/human text can directly create or promote a card without Gate PASS evidence.

## Append-only / Event Sourcing

- `card_v1.json` is immutable once created.
- Status evolution is recorded in `events.jsonl` (append-only).

State machine (minimal):

- `draft -> challenger -> champion -> retired`

## Contract

- Schema: `contracts/experience_card_schema_v1.json`
- Discriminator: `schema_version="experience_card_v1"`

