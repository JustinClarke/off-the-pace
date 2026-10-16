# CO-09 — Stint labels: join same-tyre splits, censor red-flag tyre changes

**Status:** SPEC (raised 2026-10-16 from the CO-08 flag-chance follow-up).
**Group:** D carry-over · **Depends on:** none · **Blocker:** none. Shipping it is a version bump of the stint-life target, so the promotion call is the owner's.

**Sources:** `transform/models/intermediate/int_stint_end_regime.sql`, `transform/models/intermediate/fct_stint_features` (or its current name in the repo), the stint-life target in `ml/src/schema.py`.

---

## Problem

The stint labels split one tyre run into several "stints" in two ways:

1. **Same tyres, new stint.** A pit-lane drive-through under a safety car, or a red-flag pause, starts a new FastF1 stint on the same tyres, and the tyre age keeps counting. Canada 2025 (`2025_10`) is the clearest case: every car gets three fake one-lap stints at the end, so real final stints are labelled `sc_pit` = 0. Same-compound, continuous-age "pit" ends number 96 in 2025 and 97 in 2021, plus 13 to 51 `red` ends per season.
2. **Red-flag tyre changes counted as "did not reach the flag".** A free tyre change at a red flag is labelled 0 even though it was not a strategic stop.

Both feed the flag-chance event (`reached_flag`) and the stint-life target, which treats the fake short stints as uncensored.

## Evidence (from the 2026-10-16 agent run, scratch only)

- Joining same-tyre runs flips 210 eligible rows from 0 to 1 in 2025 and 97 in 2020.
- Training on a tyre-run label with red-flag changes censored improved 2023 Brier from 0.0839 to 0.0781 for the GBM direct model. 2024 unchanged.

## Method

1. Build a tyre-run key: consecutive stints with the same compound and continuous tyre age (no age reset) form one run. Run end = last stint's end.
2. Red-flag tyre changes: treat as censored for the flag question, not 0.
3. Keep the existing `stint_end_cause` for everything else. Document the new rule in the schema text.
4. Re-run the dbt tests on the touched models, and the stint-life gates. Check the change in row counts per season and list every affected race.

## Acceptance

- Row-count changes per season listed, with the affected races named (Canada 2025 must show the fix).
- No change for seasons with no drive-through or red-flag splits, or the change is explained.
- Stint-life v-bump gates re-run; the new target version is named and not promoted without the owner's yes.

## Out of scope

Promotion of any model. The chance line itself (CO-08). The 2025 holdout is already burned, so any judgement on the fixed label must be made on 2023–2024.
