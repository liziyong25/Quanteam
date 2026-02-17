# Composer (Phase-09)

This directory documents the **Composer/Allocator MVP**: a deterministic kernel component that combines multiple **Experience Cards** into a new **composed run**.

## What It Does (MVP)

- Input: a set of `card_id` and `weights` (sum=1.0)
- Evidence source: each card's `primary_run_id` -> its dossier artifacts (especially `curve.csv`) + `gate_results.json`
- Output: a new dossier + gate_results for the composed portfolio
- Optional: if Gate PASS, record TrialLog + create a new Experience Card for the composed run

## What It Does Not Do (Non-goals)

- No signal-level/order-level merging (this MVP is **curve-level sleeve composition**)
- No parameter search / budgeted exploration
- No Agents / LLM involvement

## Docs

- `docs/11_composer/composer_curve_level_mvp.md`: composition rules, determinism, and evidence chain

