# CO-09 follow-up: penalty join and cut-short fields, evidence, 2026-10-24

This builds on CO-09's working tree (`../co-09-2026-10-24/`). "Before" is CO-09 as built,
on a scratch copy of the 2026-10-22 dev warehouse. "After" is this change rebuilt on a
second copy. That warehouse is stale until CO-17 (W3), so every number here will move on
the trusted rebuild. Commands, hashes and paths are in `PROVENANCE.txt`.

## Task A: join the penalty pairs (owner, 2026-10-24, recorded on CD14)

**Rule.** `int_stint_geometry` already joins two consecutive FastF1 stints when:
- the compound is the same;
- the tyre age goes up by exactly 1;
- the first stint did not end on a green-flag lap.

The new rule (2b) also joins a green-flag boundary when race control recorded a
**drive-through, stop-go or time penalty for that same car** within the first stint's
last lap plus or minus one (same race, same driver). All other CO-09 behaviour is
unchanged.

**How the message is matched.**
- `stg_race_control.driver_id` is NULL on all 349 penalty messages, because the FIA leaves
  the car-number field empty on steward decisions.
- So the car number is read from the text with
  `(DRIVE[ -]?THROUGH|STOP ?/ ?GO|STOP-GO|TIME) PENALTY FOR CAR (n)`. It is resolved to a
  driver through `stg_results` on the same race, the same way `stg_race_control` resolves
  numbers.
- "Under investigation" and "noted" messages do not count, because they do not contain
  "PENALTY FOR CAR".

**Result: 23 of the 36 green age + 1 pairs join and 13 stay split.** A pair joins exactly
when it has a penalty message (23/23 and 13/13 in `evidence_output.txt`). This matches
the investigation's 23 / 13 split. The full list with messages is in `green_pairs_36.csv`.

| season | pairs | joined | left split |
|---|---:|---:|---:|
| 2018 | 4 | 3 | 1 |
| 2019 | 7 | 7 | 0 |
| 2020 | 5 | 1 | 4 |
| 2021 | 5 | 2 | 3 |
| 2022 | 2 | 2 | 0 |
| 2023 | 3 | 1 | 2 |
| 2024 | 7 | 4 | 3 |
| 2025 | 3 | 3 | 0 |
| **total** | **36** | **23** | **13** |

**The 13 left split**, none of which has a penalty message for the car within the window:

| race | driver | lap | note |
|---|---|---:|---|
| 2018_13 | RAI | 7 | |
| 2020_8 | GIO | 30 | a stop-go message on lap 25 falls outside the ±1 window |
| 2020_14 | OCO | 1 | **flagged** below |
| 2020_15 | BOT | 38 | |
| 2020_15 | OCO | 17 | |
| 2021_2 | GIO | 40 | |
| 2021_8 | RUS | 26 | |
| 2021_19 | NOR | 37 | |
| 2023_20 | PIA | 2 | **flagged** below |
| 2023_20 | RIC | 2 | **flagged** below |
| 2024_4 | ZHO | 11 | |
| 2024_22 | OCO | 11 | |
| 2024_24 | LAW | 24 | his lap-29 stop-go matches his next pair, which joins |

**Flagged, not changed: three stops that look neutralised, though the flags missed it.**
- 2023_20 PIA and RIC, lap 2.
- 2020_14 OCO, lap 1, on wets.

They stay split under the penalty-only rule, and their first fragment stays `green_pit`
(an observed tyre life). If they were in fact neutralised stops, CO-09's existing rule
would have joined them, so they need the owner's or the track-status owner's look.

**Effect on the label columns: small, and only through the joined pairs.**
- **Stints:** 8,968 → 8,945 (−23).
- **End causes:** every one of the 23 removed stints is a `green_pit` end. sc_pit,
  vsc_pit, red, race_end and retirement counts are identical in every season.
- **Censoring flags:** `is_stint_life_censored` = FALSE (observed life) and
  `reached_flag` = FALSE each drop by 23. Per season: 2018 −3, 2019 −7, 2020 −1, 2021 −2,
  2022 −2, 2023 −1, 2024 −4, 2025 −3.
- **Lap grain:** the stint end cause, life censoring and reached_flag change on 113 laps
  (2018: 23, 2019: 9, 2020: 2, 2021: 2, 2022: 11, 2024: 28, 2025: 38). Where the run
  ended differently, the first fragment's laps move from green_pit to the run's cause:
  race_end on 59 laps, retirement on 43, vsc_pit on 9 and red on 2. Where the run itself
  ended green_pit (for example 2023_1 OCO), the lap labels are unchanged. stint_id
  changes on 362 laps.
- Every after-stint_id already existed before.
- **Stint-life training rows:** 124,497 → 124,496, with the censored share at 53.5%.
- **Degradation label (side effect):** the per-run detrend now spans the penalty stop. The
  largest move is 2018_15 PER, with a summed next-5 change of +128 s across 22 laps (at
  most 8.65 s on a single lap). The 2018 season mean of next_5_lap_cumulative_jump_s
  moves from −0.2810 to −0.2642. `assert_prior_season_labels_frozen` now fails for 6
  seasons instead of 4 (2018 and 2024 are added), see `labels_frozen_failures.txt`. This
  is the same deliberate v16 bump, and the seed refresh is still CO-17's.

## Task B: cut-short fields (stored, NOT model features)

**Where:** the fields are in `fct_stint_features` (the stint table the ML reads) and are
documented with tests in `transform/models/marts/schema.yml`. No model reads them. The
ML code selects named columns from this table, and `load_features` feature_columns
contains none of them. Admitting any of them as a feature is a later decision.

| field | filled on | definition |
|---|---|---|
| laps_completed | every run | = stint_length_laps |
| tyre_age_at_fit | every run with an age | TyreLife on the run's first lap. Equals starting_tyre_age_laps + 1 on all but 1 run: 2018_13 VET_2, whose first lap has no TyreLife. NULL on 207 runs, mostly quarantined units whose age stg_lap_tyre_qa withholds |
| fresh_at_fit | where the age is known | tyre_age_at_fit <= 1 |
| is_fresh_tyre_raw | every run | raw FastF1 FreshTyre on the first lap, for audit only. It disagrees with fresh_at_fit on 286 runs |
| compound | every run | already present, not duplicated |
| clean_laps_to_cut | sc_pit / vsc_pit runs | count of is_valid_lap laps |
| slope_to_cut_s_per_lap | sc_pit / vsc_pit runs with ≥ 5 clean laps and a tyre age | OLS of `int_lap_fuel_state.weight_corrected_lap_time` (the project's fuel model, not 0.035 s/kg) on age_in_stint, over clean laps |
| mean_clean_pace_s | sc_pit / vsc_pit runs with ≥ 1 clean lap | mean fuel-corrected time over clean laps |
| cut_reason | sc_pit / vsc_pit runs | stint_end_cause |
| slope_reliable | sc_pit / vsc_pit runs | clean_laps_to_cut ≥ 5 AND a slope could be fitted |

**Two departures from the brief:**
1. **slope_reliable** also requires that a slope exists. Eleven cut runs are quarantined
   units: they have ≥ 5 clean laps but no tyre age to regress on, so they read FALSE
   instead of TRUE-with-NULL-slope.
2. **"Or the stint is censored"** was read as the D6 cut-short censoring, which applies to
   exactly the sc_pit and vsc_pit runs. Race_end, retirement and red runs get no pace
   fields. If the owner meant every censored run, widen the CASE in
   `fct_stint_features.sql`.

**Coverage:**
- 1,021 cut runs. 754 have a reliable slope (73.8%).
- 765 have ≥ 5 clean laps, against the investigation's 78% of 976.
- Median slope by season and reason is −0.06 to +0.07 s/lap (`cut_fields_by_season.csv`).

**Samples** (`cut_fields_sample.csv`):
- 2022_5 MAG_2: HARD, 30 laps, age at fit 1, sc_pit, 25 clean laps, slope +0.0132 s/lap,
  mean 93.405 s, reliable.
- 2025_7 STR_2: HARD, 32 laps, age 2 (not fresh), sc_pit, 26 clean laps, +0.0671 s/lap,
  mean 80.645 s, reliable.
- 2019_11 HAM_3: SOFT, 1 lap, age 4, sc_pit, 0 clean laps, no slope, not reliable.
- On a green_pit run every pace field is NULL.

**D6 is unconfirmed.** vsc_pit is censored as CO-09 built it (only green_pit counts as an
observed life), and cut_reason includes vsc_pit. Whether vsc_pit should be censored is
still the owner's open question.

## The 2018 safety-car count: 47 in the investigation vs 85 in CO-09

`mismatch2018.py` re-runs the investigation's raw-bronze logic and reproduces its counts
exactly: 47 SC and 976 total cut runs. The arithmetic is 85 = 47 − 3 + 31 + 10.

**31 lap-1-only stints (the main cause).**
- Bronze leaves `Stint` NULL on 325 lap-1 laps in 2018 (F25), and the investigation
  filtered `Stint IS NOT NULL`, so those laps vanished.
- The warehouse's `stg_lap_tyre_qa` (WI-05 lap-1 repair) gives each of them a lap-1 stint
  wherever the pit record shows a lap-1 in-lap. The repaired lap has no compound or age,
  so CO-09 cannot fold it into the next stint.
- Most of these stints are in 2018_13 (17 stints), with 2018_4, 2018_8, 2018_14, 2018_5
  and 2018_7 making up the rest.
- 17 lap-1 stops in one race (Spa 2018) looks implausible, so these are probably an
  artefact of the lap-1 repair rather than real stops. **Not verified.** It belongs to
  the WI-05 / stg_lap_tyre_qa owner, and it inflates 2018 sc_pit.
- These runs have 0 clean laps, so they carry no pace fields. They do still count as
  censored stint-life rows.

**10 quarantined units.** Their stints are served from the pit record (9 in 2018_3, 1 in
2018_4), and bronze's numbering puts the boundary somewhere else.

**3 boundary differences.** In 2018_5 SIR and HAR, and in 2018_4 RAI, bronze puts the run
end at lap 2 to 4 while the warehouse puts it at lap 1.

Other seasons agree within 2 to 5 runs. The 976 vs 1,021 total gap is mostly 2018 (+42).

## Tests

**dbt test -s int_stint_geometry+:** before (CO-09) 831 pass / 2 fail of 833. After, 835
pass / 2 fail of 837; the 4 extra are new column tests.
- `assert_field_pace_honest_range` FAIL 15: unchanged, owned by CO-15.
- `assert_prior_season_labels_frozen` FAIL 6, up from 4. 2018 and 2024 are added by the
  penalty joins. This is expected until CO-17.
- `assert_tyre_run_key` was extended to cover the penalty rule and gained a third check
  (`green_join_without_penalty`). It passes after the change. On the before copy it fails
  with 23 rows, the unjoined penalty pairs. In the after build all 23 green boundaries
  inside a run carry a penalty message, so check 3 is not vacuous.

**Other checks:**
- **pytest** (test_targets, test_features, test_survival): 75 passed, the same as CO-09.
  test_flag_chance.py still cannot be collected because onnxmltools is not installed.
- **sqlfluff** on the three edited SQL files: clean.

## Not verified

- The CI-fixture build (`--target ci`). int_stint_geometry now reads `stg_race_control`.
  The fixture has race-control files, but the build was not run here because it writes a
  shared CI database.
- The oracle model-hash and data-profile baselines (`transform/tests/model_hashes.baseline.json`,
  `data_profile.baseline.json`). These will differ: they already did after CO-09, and the
  new columns change them further.
- `docs/reference/**`, which needs to be regenerated.
- The app export (`scripts/export_app_data.py`). It will carry the new columns in
  fct_stint_features.
- Whether the 2018 lap-1 stints and the three flagged neutralised stops are real.
- Stint-life gates. These need the CO-18 retrain.
