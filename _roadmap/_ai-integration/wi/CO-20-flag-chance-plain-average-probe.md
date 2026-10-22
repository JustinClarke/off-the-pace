# CO-20 — Chance line: does a plain average of past outcomes work, across all seasons?

**Group:** 4 chance line (not gating) · **Depends on:** `CO-17` (trusted rebuild, which carries the stint-label fix `CO-09`) · **Blocker:** `CD4` (acceptance rule), `CD5` (where the number may appear), `CD6` (fold scheme). Run it after those rulings, not before. Raised 2026-10-22 on the owner's instruction.

**Sources:** `ml/src/flag_chance.py`, `ml/src/survival.py`, `transform/models/intermediate/int_stint_end_regime.sql`, `app/public/models/flag_chance_lookup.json`, `_roadmap/_ai-integration/wi/CO-08-flag-chance-calibration.md`.

**This is a probe.** It changes no shipped output: not the simulator, not `flag_chance_lookup.json`, not any export. It gates nothing in groups 1–3. Its result is evidence for a later ruling on the chance number, nothing more.

---

## Question

Before deciding anything more about the chance-to-make-the-flag number, the owner wants to know whether the simplest possible version works. That version is a plain average of what happened before: for a given context, the share of past final stints that reached the chequered flag. Is that a usable chance number, judged on every season available, not only 2025?

## Why it runs after the rulings

- `CD4` sets the acceptance rule. The pass/fail here uses it, so it must exist first.
- `CD6` sets the fold scheme (expanding window or leave-one-season-out). The averages are computed from the training seasons of each fold, so the scheme decides which past seasons feed each prediction.
- `CD5` decides where a chance number may appear. A plain average needs only simulator-known inputs, so the answer changes what a pass would be used for.

## Why it depends on CO-17

The outcome being averaged is the stint label. `CO-09` fixes two known errors in it: same-tyre runs split into several stints, and red-flag tyre changes counted as "did not reach the flag". Averaging the old label would bake those errors in. `CO-17` is the trusted rebuild that carries `CO-09`; `data/dev.duckdb` is not trusted until it lands (watch W3).

## Data limits (from the log)

- **2018–2025** are the seasons available. All of them have been used for some earlier choice, so any result is provisional.
- **2025** has been used for selection at least twice (`CO-08`). Report it, but do not let it decide the result alone.
- **2018** has its cliff values fitted on its own data (`CD2`, in-sample). Australia and Bahrain 2018 have no telemetry. If a context uses cliff-derived fields, mark 2018 as in-sample.
- **2026** is not ingested (`CO-12` is BLOCKED on `CD12`), is a mixed-era season that `CD8` rejected for stint life, and `CD11` schedules no 2026 test. It is out of this probe unless the owner reverses `CD11` and `CO-12` lands.
- With an expanding window, the first season has no earlier seasons to average. State which seasons can be scored under the chosen scheme.

## What "context" means

A small, declared set of cells, fixed before scoring. Default, unless changed before the run: compound × laps remaining to the flag (bands, for example 1–5, 6–10, 11–15, 16–20, 21–30, 31+). Optional third key: circuit. A cell with fewer than a stated number of past final stints (default 30) falls back to the coarser cell (compound only, then all). Record the fallback rate per season.

## The main thing to test: drift across seasons

`CO-08` found that, where the model said about 50%, the share of final stints reaching the flag was 46% in 2020, 65% in 2021, 54% in 2022, 63% in 2023, 74% in 2024 and 77% in 2025. A plain average of past seasons will lag a trend like that, and 2025's 77% is higher than any earlier season. This is the first thing to look at: per season, the gap between the average's prediction and what happened.

## Caveat (state it in the result)

A plain average ignores the stint's own tyre age, the tyre's condition and anything else about the car in front of you. It answers "how often did stints like this reach the flag", not "will this one". It can also miss drift: if the share reaching the flag keeps rising, every average of the past is low. A pass here does not remove either caveat.

## Rule written before any scoring

Before any outcome is computed, write into this item's note in the log: the cells, the minimum cell size and fallback, the fold scheme (`CD6`), the seasons scored, the acceptance rule (`CD4`) and the comparison below. Do not change them after.

- **Comparison:** the current experimental line (the refit of the v14 configuration in `flag_chance_lookup.json`) on the same stints and folds.
- **Report per season:** n final stints, Brier score, the `CD4` rule's verdict, the average gap between predicted and observed, and the fallback rate. Pooled numbers go after the per-season table, not instead of it.
- **PASS** (default, to be confirmed in the log before scoring): the plain average meets the `CD4` rule on every scored season, and its pooled Brier score is no worse than the current line's.
- **FAIL** otherwise. A partial result (passes some seasons, fails others) is a FAIL, reported with the seasons named.

## Output

Per-season table, pooled table, the drift picture (predicted vs observed by season), PASS or FAIL against the rule above, and two or three plain sentences saying whether a simple average is good enough to show fans and why. Evidence goes in `_roadmap/_ai-integration/_evidence/co-20-<date>/` with a `PROVENANCE.txt`.

## Definition of done

Rule recorded in the log before scoring. Every scorable season reported. PASS or FAIL stated. No shipped file changed. Do not commit.
