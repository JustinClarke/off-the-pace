# AI-01 — Grounding contract: fact cards

**Group:** A grounding · **Depends on:** `CO-01` · **Blocker:** none.

**Sources:** `transform/models/marts/mart_race_driver_summary.sql`, `mart_driver_season_summary.sql`, `mart_metric_benchmark.sql`; `mart_degradation_predictions` (written by `ml/src/predict.py`); `transform/models/intermediate/int_pit_strategy_value.sql`; `scripts/export_app_data.py`; the family pages under `docs/app/families/`.

---

## What exists today

- The three rating marts carry per-driver, per-race and per-season numbers. `mart_race_driver_summary` has `ci_low` / `ci_high` and `n_clean_laps`; its header says the band is a lap-noise band, not the season Bayesian interval. CO-01 fixes three of their columns first.
- `mart_degradation_predictions` (160k laps) already carries p10/p50/p90 degradation, cliff-class probabilities, stint-life p10/p90, `model_version` and `is_in_envelope`. It is the tyre-question source, with its own band and range flag.
- `int_pit_strategy_value` carries the optimal pit lap, opportunity cost, a confidence and a verdict per stint.
- **None of the three rating marts is exported.** The live CDN has 39 tables and none of them (checked 2026-10-15).

Nothing yet defines which numbers the assistant may quote, or what must travel with a number.

## Method

1. Define a fact card: `id`, `metric`, `value`, `unit`, `n` (laps, stints or races behind it), `interval` (low, high, and what kind of interval it is), `scope` (driver, race, season, stint), `source_table`, `source_page` (the docs/app page that explains it), `model_version` where it applies, and `caveats` (codes from AI-02).
2. Generate cards at export time from the sources above into one published table, added to `scripts/export_app_data.py`. The browser only looks them up. A column with no `n` or interval becomes no card and goes on the ungrounded list.
3. Publish the card schema as JSON Schema, for AI-04 and AI-07.

## Acceptance

- Every card has every field, or is refused with a reason.
- Cards for a clean race and a thin one (few clean laps) differ visibly in `n` and interval.
- A prediction outside `is_in_envelope` carries an out-of-range caveat.
- The interval kind is never relabelled (a lap-noise band stays a lap-noise band).

## Output

Card counts per source and metric, and the ungrounded list. Together they show what share of the app's numbers the assistant can quote.

## Definition of done

Cards generate for a fixed sample of 20 (driver, race) pairs across at least 3 seasons, all pass the schema, the table is in the export, and the ungrounded list is written down. Tests re-run by the orchestrator.
