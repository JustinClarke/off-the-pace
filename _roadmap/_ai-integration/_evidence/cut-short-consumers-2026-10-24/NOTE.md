# Who should read the cut-short pace fields? 2026-10-24

Read-only. No model, label, ML, app or board file changed; `data/dev.duckdb` not touched. All
claims below are from code and the CO-09 evidence notes, not from new queries. Numbers about
the fields come from `../co-09-2026-10-24-b/` (NOTE.md, `cut_fields_by_season.csv`) and are on
the stale 2026-10-22 warehouse.

## 1. What reads the stint features now

- **Stint-life model.** `ml/src/features.py:139-143` selects only `stint_id, stint_length_laps,
  is_stint_life_censored` (plus `stint_end_cause` for the 10b variant) from `fct_stint_features`.
  The target is `clip(stint_length_laps - lap_in_stint, 0)` (`features.py:172-175`).
  `stint_length_laps` is barred as a feature (`ml/src/schema.py:75`, mask at `schema.py:445`).
  None of the nine new fields is read anywhere in `ml/src` (grep of `ml/src`, `scripts/` and `app/src`).
- **Other ML readers of the table:** `ml/src/flag_chance.py:201-206` (`is_censored_stint`,
  `stint_end_cause`), `ml/src/evaluate.py:201-204` (`stint_length_laps`), `ml/src/evaluate_10c.py:135`.
- **Starting tyre age.** `starting_tyre_age_laps` is defined at
  `transform/models/marts/fct_stint_features.sql:36` and read by no ML or app code (grep).
  The models see the tyre's age only through the lap-grain `age_in_stint`
  (`schema.py:138`, in the `stint_position` group) together with `lap_in_stint`; their
  difference is the starting age, so it is available implicitly. The stint-life baseline
  buckets `age_in_stint` in 5-lap bins (`evaluate.py:67, 209-210`).
- **Pace or slope features.** No stint-level observed pace or slope feature exists. Nearest:
  - `expected_compound_pace_s`, `expected_degradation_rate_s_per_lap` (`schema.py:144-147`):
    model-expected curves from `int_compound_cliff_predicted`, not the stint's own laps
    (`marts/schema.yml:564-569`).
  - `push_residual` and the thermal loads (`schema.py:148-151`): lap pace against the stint's
    point-in-time baseline (`marts/schema.yml:276-280`), a per-lap residual, not a slope.
  - The old per-stint `drift_s_per_lap` is explicitly barred as "causally encodes the target"
    (`schema.py:77`). That is the precedent for these fields.
- **App.** `fct_stint_features` is exported whole (`scripts/export_app_data.py:63`, no column
  filter), so the new columns will ship in the parquet. App code selects named columns
  (`app/src/features/pit-strategy/queries.ts:49,128`); none selects the new ones.

## 2. The gap, and does the model learn anything from a censored row?

A censored stint-life row is `[y+1, +inf)` (`ml/src/survival.py:32-48`): "at least N more laps".
`is_stint_life_censored` is TRUE for every end but `green_pit` (`schema.py:299-304`;
`features.py:169-172`). The row contributes its lap-grain features (the 32-wide vector at
that lap) and the bound, nothing stint-level. So yes: **beyond the lap count and the lap-grain
features, a censored stint carries no information to the model.** What the model cannot see is
"this tyre was already going off at the cut". That is the gap the fields name.

How big: 1,021 cut runs of about 8,945 (11%); 754 with a reliable slope (8%), on the stale
warehouse (`co-09-2026-10-24-b/NOTE.md`, Coverage). Slopes are noisy: median -0.06 to +0.07 s/lap
by season, with p10/p90 spanning about -0.64 to +0.35 s/lap
(`cut_fields_by_season.csv`). Median clean laps per cut run is 0 to 23 by season and reason.
The signal on top of that noise is small, and the neutral-laps note already judges neutral-stop
tyre lives "confounded" (`neutral-laps-2026-10-24/NOTE.md` section 8, rows b1, b2).

## 3. Candidate consumers

| | Consumer | Fields | Home | Verdict | Risk |
|---|---|---|---|---|---|
| a | Covariate in the stint-life model | `slope_to_cut_s_per_lap`, `mean_clean_pace_s` | ML | **Do not build** | Leakage (section 4); filled only on cut runs, so a model learns the cause from missingness; 8% of runs |
| b | Diagnostic: were reliable-slope cut runs on a faster or slower wear track than green-pit runs? | `slope_to_cut_s_per_lap`, `slope_reliable`, `cut_reason` | Evidence note, not a product | **Possible, one-off; not with these fields as stored** | The fields are NULL on green_pit runs, so there is no comparison group in the table. The same slope would have to be recomputed for green runs. Even then it measures strategy (who pits under SC), not tyres |
| c | Assistant or app fact card, "tyre pace before the SC stop" | `mean_clean_pace_s`, `slope_*`, `clean_laps_to_cut` | AI-01 | **No** | AI-01 requires `n` and an interval for each card (`wi/AI-01-grounding-contract.md`, Method 1-2). These have n (clean laps) but no interval, and the slope is noisy. A fan reading would be "his tyres were fine / dying when the SC came", which the data cannot back at 5-15 laps. No docs page explains it (needs `source_page`) |
| d | Flag-chance or tyre-cliff (CO-08, CO-20) | `cut_reason`, `laps_completed` | ML | **No new use** | flag-chance already reads `stint_end_cause` (`flag_chance.py:206`). CO-20 is a plain average of past outcomes by compound and laps-to-flag (`wi/CO-20...md`, "What context means"), so a pace field is not an input. Cliff targets use lap-grain data, not stint cuts |
| e | Drop the fields | all nine | n/a | **Reasonable** | Cost to keep is low (nullable columns with schema tests); cost is a standing invitation to leak |

Note on `tyre_age_at_fit`, `fresh_at_fit`, `laps_completed`: duplicates of what the lap grain
and `stint_length_laps` already give (`starting_tyre_age_laps + 1`, `stint_length_laps`).
Nothing needs them. `is_fresh_tyre_raw` is audit only (disagrees on 286 runs).

## 4. Leakage check (the key risk)

**Definition.** The run_fit CTE (`fct_stint_features.sql:180-197`) groups all laps of the stint
(run) and takes `REGR_SLOPE(weight_corrected_lap_time, age_in_stint)` over `is_valid_lap` laps.
`is_valid_lap` (`stg_laps.sql:131-138`) drops any lap with a 4/5/6/7 in track status, pit laps, lap
1 and inaccurate laps. The run ends at the cut, so every lap used is **at or before the cut**:
no lap after the cut exists in the run, and neutral laps are excluded. On that narrow point the
definition is clean.

**It still leaks for the stint-life model, in three ways.**
1. **Within-stint look-ahead.** The model is lap-grain; each row at `lap_in_stint = k` predicts
   `stint_length - k`. A stint-level slope is computed over all clean laps to the cut, so it
   contains laps after k. For a lap-5 row it uses laps 6..N. A column that is the same for every
   lap of the stint and is built from the whole stint is exactly the "carried in base, causally
   encodes the target" case ruled out for `drift_s_per_lap` (`schema.py:77`). To be legal, it would
   have to be recomputed per lap over laps up to k only (a different, lap-grain feature).
2. **Missingness reveals the label.** The slope is non-NULL only for `sc_pit`/`vsc_pit` runs
   (`fct_stint_features.sql:274-279`). A boosted tree splits on NaN, so "slope present" means
   "censored, cause SC/VSC". Censored rows are the ones the AFT scores as half-lines, so this is
   label leakage in training and cannot exist at serving time (a live stint has no cut yet).
   Filling the slope for green runs would remove this but not (1).
3. **`clean_laps_to_cut` is nearly the target.** It is the stint length minus pit/in/out/neutral
   laps, so it nearly reproduces `stint_length_laps`, which is barred for exactly that reason
   (`schema.py:419-421`).

**Other biases (no leak, but they limit meaning).** Early-run warm-up gives a negative slope on
short runs (5-10 clean laps, the median for 2019-2023 SC runs). The fuel correction is the
project's linear burn model; its error projects onto the slope because age and lap number move
together. Runs that pit under SC are opportunistic (neutral-laps note, section 8).

**Answer: a model using the slope as a stint feature would leak.** It would not leak future laps
beyond the cut, but it would leak the stint's own later laps and its end cause.

## 5. Recommendation

- **Build nothing now** on these fields; no consumer is worth the risk or the 8% coverage.
- If one thing is wanted, it is (b) as a one-off evidence note after CO-17, recomputing a slope
  for green_pit runs on the same clean laps so there is a comparison group. It would answer
  whether D6 censoring hides a slower or faster wear population, and informs CD10. It needs no
  stored column to run.
- **Keep** `clean_laps_to_cut`, `slope_to_cut_s_per_lap`, `slope_reliable`, `cut_reason` as
  stored diagnostics with the existing "not model features" notes. **Drop** (or leave unused)
  `laps_completed`, `tyre_age_at_fit`, `fresh_at_fit` as redundant. Add a note to
  `ml/src/schema.py` that these columns are in `EXCLUDED_LEAKAGE_COLUMNS` territory so a later
  change cannot admit them by accident (the guard is a name-set intersection, `schema.py:23-28`).
  That edit is the owner's call and was not made here.
