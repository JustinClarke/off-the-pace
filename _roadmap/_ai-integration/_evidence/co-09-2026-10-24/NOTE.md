# CO-09 stint label fix: evidence, 2026-10-24

Scratch copies of the 2026-10-22 dev warehouse. This is not the trusted build; CO-17
makes that. "Before" means HEAD code rebuilt on a copy. "After" means the CO-09 working
tree rebuilt on a second copy. Commands, hashes and paths are in `PROVENANCE.txt`.

## What was built

- **Tyre-run key (D4: re-key `stint_id` everywhere, no separate run id).** The key is
  built in one place, `int_stint_geometry`, and every other model reads it from there.
  Consecutive FastF1 stints of a driver-race join into one run when all of these hold:
  - the compound is the same and known;
  - the next stint's first tyre age is the previous stint's last age + 1 (CD14 1a);
  - the previous stint did not end on a green-flag lap (CD14 (2): green same-tyre stops
    stay split).

  The run ends where its last fragment ends. A run that was never joined keeps its old
  `stint_id`, byte for byte. A joined run takes its first fragment's id and
  `stint_number`. All 8,968 stint_ids after the change already existed before it.
- **Labels in `int_stint_end_regime`, passed through `fct_stint_features`:**
  - `is_stint_life_censored`: TRUE unless the run ended in a green-flag tyre change.
    Red-flag changes (D5) and safety-car or VSC stops (D6) are censored, along with the
    flag and retirements.
  - `reached_flag`: TRUE for race_end and FALSE for a green, SC or VSC stop. It is NULL
    (censored) for a red-flag tyre change, a retirement, or an unassigned stint.
  - `stint_end_cause` and `is_censored_stint` keep their old meanings.
- **ML side:**
  - `schema.STINT_LIFE_CENSOR_COLUMN` changes to `is_stint_life_censored`, with the rule
    written into the schema text.
  - `features.py` reads that column.
  - `flag_chance.EVENT_NOT_REACHED` drops `red`. This takes effect at the next fit; the
    shipped lookup is unchanged.
- **Label version:** v16 is recorded in `ml/README.md`. It is still open because CO-15
  joins it.

## Row-count changes per season (stints, `int_stint_end_regime`)

| season | before | after | change | sc_pit before→after | red before→after | affected races |
|---|---:|---:|---:|---|---|---|
| 2018 | 951 | 950 | -1 | 86→85 | 0→0 | 2018_4 |
| 2019 | 1,067 | 1,066 | -1 | 100→99 | 0→0 | 2019_13 |
| 2020 | 934 | 890 | -44 | 139→113 | 61→43 | 2020_1, 2020_8, 2020_9, 2020_15, 2020_16 |
| 2021 | 1,234 | 1,106 | -128 | 144→50 | 114→80 | 2021_2, 2021_3, 2021_6, 2021_10, 2021_19, 2021_21 |
| 2022 | 1,241 | 1,218 | -23 | 126→109 | 53→47 | 2022_4, 2022_7, 2022_10, 2022_15 |
| 2023 | 1,350 | 1,275 | -75 | 135→100 | 110→70 | 2023_3, 2023_9, 2023_10, 2023_13, 2023_16, 2023_19, 2023_20 |
| 2024 | 1,302 | 1,260 | -42 | 111→78 | 51→42 | 2024_4, 2024_6, 2024_8, 2024_21, 2024_23 |
| 2025 | 1,295 | 1,203 | -92 | 214→122 | 0→0 | 2025_1, 2025_10 |
| **total** | **9,374** | **8,968** | **-406** | | | **31 races** |

- **What was folded:** the 406 stints split into 299 safety-car drive-throughs and 107
  red-flag pauses. This matches CD14's count of 442 age + 1 pairs minus the 36 green ones.
  Per-race and per-regime detail is in `joined_runs_by_race.csv` and
  `joined_boundaries_by_regime.csv`.
- **Unchanged:** green_pit, vsc_pit, race_end and retirement counts, and the number of
  final runs (`is_censored_stint`), are the same in every season.
- **Lap grain:** unchanged. There are 189,418 laps both before and after, and
  `fct_cliff_prediction_features` keeps the same rows in every season. At the lap grain,
  end causes change on 3, 1, 328, 663, 90, 153, 54 and 333 laps (2018 to 2025); see
  `label_flips_lap_grain.csv`.
- **Side effects of re-keying everywhere:**
  - `next_5_lap_cumulative_jump_s` labelled rows: 2020 goes from 9,360 to 9,383.
  - Training-eligible rows: 2020 drops by 3 and 2023 drops by 1.
  - Means of the degradation label move in 2020-2023, because per-stint detrending now
    runs per run. Details in `labels_frozen_failures.txt`.

## Canada 2025 (2025_10)

| cause | before (one-lap) | after (one-lap) |
|---|---|---|
| sc_pit | 53 (36) | 4 (0) |
| race_end | 17 (17) | 17 (0) |
| green_pit | 29 | 29 |
| retirement | 3 | 3 |

All 49 fake one-lap stints across 17 drivers are gone. For example, VER stint 3 (laps
38-67) used to end sc_pit, followed by three one-lap stints. It is now a single 33-lap
run ending at lap 70 as race_end, with `reached_flag` TRUE. The 17 real final stints are
no longer labelled sc_pit. Per-driver detail is in `canada_2025.csv`.

## Verdict per acceptance line

1. **Row-count changes per season listed, affected races named, Canada 2025 shows the
   fix: PASS.** See the tables above.
2. **No change for seasons with no drive-through or red-flag splits, or the change is
   explained: PASS (explained).**
   - No season is free of splits. 2018 and 2019 have one SC drive-through join each
     (2018_4, 2019_13), so each moves by one stint. 2025 has no red-flag joins.
   - Separately and by design, D5/D6 change the stint-life censoring flag in every
     season, on 1,564 to 3,129 laps per season. This happens because sc_pit, vsc_pit
     and red endings are now censored, which is a rule change rather than a split
     effect.
   - The degradation-label move in 2020-2023 comes from re-keying the detrend window
     (D4), as described above.
3. **New label version named in `ml/README.md`, shared with CO-15; nothing promoted:
   PASS.** v16 is recorded as OPEN until CO-15 lands. No model was trained or promoted,
   and `MODEL_VERSION_DEFAULT` stays v14.

## Method step 4 and checks that are not clean

- **dbt tests on `int_stint_geometry+`:** before 827 pass / 1 fail out of 828. After
  831 pass / 2 fail out of 833. The after run includes 4 new column tests and the new
  `assert_tyre_run_key`.
  - `assert_field_pace_honest_range` FAIL 15: this was already failing before the
    change. It is the Monaco 2024 defect, which CO-15 fixes.
  - `assert_prior_season_labels_frozen` FAIL 4 (2020-2023): **new, caused by this
    change**, and expected for a deliberate label bump. The test's own instructions say
    to refresh `label_stability_baseline.csv` in the same change. It was **not**
    refreshed here because v16 is shared with CO-15, and the build order gives the
    frozen-label refresh to CO-17's trusted rebuild. Refreshing it on a stale copy would
    freeze an untrusted baseline. It stays failing until CO-17.
  - `assert_stint_boundaries_match_pits` failed on 7 races (check 4, "broken tyre feed")
    once served stints became runs. Check 4 now reads the feed's own numbering
    (`stg_lap_tyre_qa`). With that change it passes on both copies.
  - `assert_tyre_run_key` (new) passes after the change and fails on the before copy
    with 406 rows, so it catches the defect it guards.
- **Stint-life gates: NOT RUN.** They need a retrain on the new label (CO-18), and the
  label is not final until CO-15. `pytest` for test_targets, test_features and
  test_survival ran on the after copy: 75 passed. Stint-life training rows are 124,497
  and the censored share is 53.5%. `test_flag_chance.py` could not be collected because
  `onnxmltools` is missing from the venv.
- **Interpretation to confirm with the owner:** D6 says "safety-car and pit ends are cut
  short too". It was read as sc_pit **and vsc_pit** censored for stint life, so only
  green_pit is an observed life (the earlier `10b` arm). The flag question keeps SC and
  VSC stops as 0; only red is censored there.

## stint_id reference audit (`stint_id_grep_counts.txt`, 132 files)

- **The only constructor is `int_stint_geometry.sql`, which was changed.** A grep for
  `AS stint_id` and for code that builds or parses stint_id finds no other constructor in
  transform, ml, scripts or app/src.
- **Edited:**
  - `int_stint_end_regime.sql`, `fct_stint_features.sql`, both `schema.yml` files.
  - `assert_stint_boundaries_match_pits.sql`, new `assert_tyre_run_key.sql`,
    `transform/tests/README.md`.
  - `ml/src/schema.py`, `features.py`, `flag_chance.py`, `ml/README.md`.
  - `app/src/features/degradation-simulator/queries.ts`, comment only. It is the one
    place that parses the stint number out of stint_id. The number can now skip, and it
    was deliberately not re-counted there.
- **Inherit through `ref()` with no edit needed:**
  - All other models under `transform/models` (34 SQL files).
  - The macros `trailing_median` and `driver_isolation_identity_terms`, which partition
    on whatever stint_id they are given.
  - 14 singular tests.
  - The Python fitters in `transform/tasks/coefficients`, which read `sg.stint_id`.
  - The ML code in `ml/src` that groups or joins on stint_id (attribution, ceiling,
    evaluate, evaluate_10c, intervals, powerlaw_*, predict).
  - Historical scripts under `scripts/`.
  - The app queries for blind-test, pit-strategy and tyre-cliff-survival. These read
    exported tables, so they pick up the runs at the next export.
- **Synthetic ids in tests, unaffected:** test_fit_compound_cliff, test_fit_weight_penalty,
  test_seed_param_provenance, ml/tests/test_fit_parity, test_attribution, and the app's
  tyre-cliff-survival transform test.
- **Generated or baseline files, not edited:**
  - `docs/reference/**`: autogenerated by `scripts/gen_dbt_reference.py`, so it needs a
    regeneration run.
  - `transform/tests/data_profile.baseline.json`: owned by CO-25.
  - `ml/models/manifest.json`, `ml/model_card.yml`, `app/public/models/*`: these list
    stint_id as an identifier column and do not change.
- **Downstream effect to note for CO-17 and CO-18:** a coefficient refit, such as the
  compound cliff seed, now sees runs instead of fragments. The seeds are frozen and were
  not refit here.
