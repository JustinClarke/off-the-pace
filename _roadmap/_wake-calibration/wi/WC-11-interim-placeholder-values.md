# WC-11: interim placeholder wake values (WC-10 paused)

**Owner decision, 2026-10-30.** The WC-10 chain (WC-10e to WC-10l, and the WC-10m fallback) is paused. Instead we ship arbitrary, clearly labelled per-circuit placeholder values for "a car within about 1 s of another car loses about Y s per lap". The aim is only to do better than what production does today, and to be replaceable by calibrated values later with no downstream change. In the owner's words: "we can always do more research later."

**Nothing here is fitted or measured.** The values are assumptions. No pre-registration applies, because nothing is estimated (rule 4 covers fits, coefficients and gate results).

## What production did before

- **The cost page** (`app/src/features/dirty-air-cost`) showed `int_dirty_air_tax_component`. That is one coefficient, θ_air = 0.331 s/lap (`theta_air_label_value`, W40), for every circuit and season. A lap was charged 0.331 s if the *previous* lap's middle-third median gap (DistanceToDriverAhead divided by point speed) was under 1.5 s, and 0 s otherwise. It took no account of how close the car was or which circuit it was. The page presented the result as seconds lost, with no modelled label and no disclaimer.
- **The ML label spine** subtracts the same `dirty_air_tax_s` in `int_lap_residual_decomposed`, so it is inside `driver_skill_residual_s`, and through that inside the ML targets (`next_5_lap_cumulative_jump_s` and others). It also feeds `fct_lap_residuals`, `fct_ghost_car_pace`, `fct_stint_features.cumulative_dirty_air_tax_s` and the season and race summary marts.
- **ML features** (`ml/src/schema.py`) already use measured traffic only: the `dirty_air` group (air-state share and thermal loads) and the `proximity` group (crossing-time gaps: `share_lap_within_1s/2s`, `gap_ahead_min_s`, `gap_ahead_median_s`, `share_lap_behind_within_1s` and others). The ML side reads no loss column directly.

## What WC-11 changes

| File | Change |
| :-- | :-- |
| `transform/seeds/wake_placeholder_values.csv` | **The config.** Three `class_default` rows (the per-class loss), one `unlisted_default` row (the class used for an unknown circuit), and one `circuit` row per `race_to_track` circuit. A blank loss means the circuit inherits its class value; a value overrides it. Each row has a `basis` saying why. |
| `transform/seeds/schema.yml`, `transform/dbt_project.yml` | Seed tests and column types. |
| `transform/models/intermediate/int_lap_wake_placeholder_cost.sql` (+ `schema.yml`) | Per-lap placeholder cost, with the label, reason and disclaimer columns. |
| `transform/tests/assert_wake_placeholder_labels.sql` | Modelled means a value and no reason. Unavailable means NULL and a reason, never 0. The cost is never more than the assumed loss. |
| `transform/tasks/wake_calibration/tests/test_wc11_placeholder.py` | Seed checks, the DA-03 number and identifier grep, the DD-WC2 text verbatim, and an isolation check (nothing in `ml/` or in any other dbt model reads the placeholder). |
| `app/src/features/dirty-air-cost/*` | The page now reads the placeholder table. Every value is labelled modelled/placeholder, "—" plus a reason marks an unavailable lap, the field total is printed with its modelled share, and both disclaimer lines are shown. |
| `scripts/export_app_data.py` | Exports `int_lap_wake_placeholder_cost`, partitioned by `race_year`. |
| `docs/app/dirty-air-cost.mdx`, `app/src/nav/pageSummaries.generated.json` | Page docs and the AI copy. |

**Not changed:** `int_dirty_air_tax_component`, θ_air, the ML feature contract and the ML targets. The placeholder never enters ML. If a model were trained on assumed values, it would learn the assumption back and then look validated. ML keeps the measured gap features it already has.

## The formula

```
wake_cost_placeholder_s = loss_s_per_lap_within_1s(circuit) × wake_exposure
wake_exposure           = share_lap_within_1s + 0.5 × (share_lap_within_2s − share_lap_within_1s)
```

The full loss applies inside 1.0 s and tapers linearly to zero at 2.0 s. The factor 0.5 is the average of that linear taper over the 1–2 s band. Nothing applies beyond 2 s. The shares are `int_lap_proximity` crossing-time gaps, which are measured. The cost uses the current lap, not the lagged one, because it is a display cost and not an identified estimate. A lap with no measured gap, or a SC/VSC/red-flag lap, is unavailable (NULL plus a reason). A measured lap with no car within 2 s is a modelled 0.

## Assumed values and why

| Class | s per lap, full lap within 1 s | Why |
| :-- | :-- | :-- |
| fast | **0.45** | The wake (aero) loss is largest where the lap is made in high-speed corners. This is the top of the "few tenths per lap" range. |
| medium | **0.30** | The middle of the few-tenths range commonly reported for following within about 1 s. |
| slow | **0.20** | Low-speed corners rely on mechanical grip. Being held up is not included. |

- **Fast circuits:** Silverstone (both), Spa, Zandvoort, Suzuka, Lusail, Jeddah, Barcelona, Mugello, Istanbul, COTA.
- **Slow circuits:** Baku, Montreal, Monza (low downforce), Las Vegas, Mexico City (both keys), Monaco, Singapore.
- **Medium:** all other circuits. A circuit that is not listed also gets medium, flagged `class_source = unlisted_circuit_default`.

There are no per-circuit overrides yet.

**Why 0.45 and not 0.40.** The grep test compares the seed with every number in the archived DA-03 fit at 3 decimal places. 0.400 matched three of DA-03's CI upper bounds (0.3999…), so the fast value is 0.45. The match was a coincidence, but rule 6 is mechanical.

**Known simplifications:** one value for all eras (2022+ cars are said to follow better), no tow gain, no held-up or blocking cost, no tyre effect.

Sanity check on the scratch copy (2026-10-30): 173,679 laps are modelled, at a mean of 0.10 s/lap and a maximum of 0.45 s. 13,745 laps are unavailable as neutralised and 1,994 because no gap was measured. Season totals are about 15–20% above what the old 0.331 rule charges on the same laps.

## Labels (BUILD-ORDER rule 7)

- Every value carries the DD-WC2 disclaimer word for word: "Normalised from other compounds, based on stints from other drivers or the general performance of the tyres after removing other factors."
- Each value also carries a second line, following the DD-WC18 precedent: "Placeholder = an assumed typical cost for a car this close at this circuit and season, not a measurement of this lap." **Owner ruling 2026-10-30 (DD-WC25): keep the second line.** With WC-12 the values are per race, so "at this type of circuit" became "at this circuit and season". The meaning is unchanged. The text is identical in the model, `assert_wake_placeholder_labels`, the schema test, the app, the docs page and the tests. **WC-13 (DD-WC26, open):** now that the value varies by tyre and car, the line reads "Placeholder = an assumed typical cost for a car this close at this circuit and season, on this tyre and car, not a measurement of this lap." everywhere.
- An unavailable value is shown as "—" with a reason, never 0.
- Totals print the modelled share, which is 100% here.

## How to swap in calibrated values later

1. Put the calibrated loss in `loss_s_per_lap_within_1s`, either per class or per circuit (use the circuit rows for overrides).
2. Set `value_kind` (for example `calibrated`) and add that value to the `accepted_values` tests in `seeds/schema.yml` and `models/intermediate/schema.yml`.
3. If the calibrated method gives a different gap curve, replace the `wake_exposure` expression in the model. The output columns stay the same, so the app and the export do not change.
4. A calibrated value with its own gate may then be labelled `measured` or `modelled` per WC-05 and WC-06.

## How to resume WC-10

Resolve **DD-WC24** in `status/build-log.json`. Remove DD-WC24 from each WC-10 item's `blocked_by_decision`, restore the stage recorded in that item's note (WC-10e was BUILDING; WC-10f, WC-10g, WC-10h and WC-10j were BLOCKED; WC-10i, WC-10k, WC-10l and WC-10m were SPEC), move the pointer back to WC-10e, then run `board.py --check` and `--write-order`. The B2 draft, the B2 code fix and its tests are untouched in the working tree. The history entry of 2026-10-30T13:27:50 is the handoff to resume from.

DD-WC21, DD-WC23 and DD-WC19 stay OPEN and deferred, as do watch rules W8, W11, W14 and W15.

## Still open

- Run `scripts/export_app_data.py` after a trusted rebuild. Until then the deployed page has no table to read.
- A `docs-claims-reviewer` verdict is needed for `reading-signal-dirty-air-cost`, then `docsDrift.mjs --update`.
- The other product surfaces still show the label's `dirty_air_tax_s` (0.331 rule): lap residuals, the lap waterfall, the ghost car and the summary marts. They were not changed, because that column is part of the ML label.

## WC-12: per-race values (follow-on, 2026-10-30)

The single value per corner class was replaced by a value per race (season and race). It is still an **assumption set by a fixed rule, not a fit**. No lap time, segment time, minimum, exit or apex speed was read to set any number, for any season. The 2024-25 outcomes stay unread (W8).

### The rule

```
corner_index = 1.00 x n_fast + 0.50 x n_medium + 0.25 x n_slow + 0.25 x n_flat
loss_raw     = era_factor(season) x 0.35 s x corner_index / 8
loss         = round(clamp(loss_raw, 0.15, 0.55), 0.01)        -> loss_s_per_lap_within_1s
```

| Input | Value | Why (full text in `seeds/wake_placeholder_rule.csv`) |
| :-- | :-- | :-- |
| fast braking corner (apex ≥ 200 km/h) | 1.00 | Downforce grows with speed squared, so wake loss matters most here |
| medium (120–200) | 0.50 | Speed squared at about 160 vs 230 km/h is about 0.48 |
| slow (< 120) | 0.25 | Speed squared alone gives about 0.15. It is raised because the car is longer in the corner and loses front grip on entry |
| kink taken flat | 0.25 | Not grip-limited in clean air. A small allowance for a lift |
| reference | 0.35 s at 8 equivalents | 2017-18 cars, a full lap within 1 s. Mid-to-upper "few tenths" |
| era 2017-18 | 1.00 | Reference: wide high-downforce cars, following markedly harder |
| era 2019-21 | 0.90 | 2019 simplified front wings and bargeboards to help following, 2021 floor trim. Modest reported gain |
| era 2022 | 0.65 | Ground-effect rules designed for following. F1's published CFD gives about 18% downforce loss at about 1 car length, against about 47% for 2021 cars. The real gain was smaller than the CFD |
| era 2023 | 0.75 | Outwash regained, floor edges raised 15 mm. Drivers reported following got harder |
| era 2024-25 | 0.80 | Mature ground effect: harder than 2022-23, easier than before 2022 |
| era 2026 on | 0.80, `era_assessed = false` | New rules and no evidence yet. The 2024-25 factor is carried forward and flagged |
| bounds | 0.15 to 0.55 s | Keep it inside a defensible "few tenths" range. The floor binds for 4 races (2022 Monza, Red Bull Ring, Paul Ricard, Yas Marina), flagged `loss_bounded`. The ceiling never binds |

**Corner counts** (`seeds/wake_placeholder_race_structure.csv`, built by `transform/tasks/wake_calibration/wc12_structure.py`) come from the WC-03 pass table's registered structure columns `corner_class` and `segment_basis`, plus `layout_checks.csv` (FastF1 corner count, lap length). `segment_basis = fixed_before_apex` is a flat kink. Each count is the **median over every season of the same layout** (circuit slug and FastF1 corner count), not the race's own count. One race's classes can be skewed by its conditions: the 2021 Belgian GP, run in the wet behind the safety car, puts 11 corners in `slow`. The race's own counts are kept beside the medians.

**Caveat on "structure".** The WC-01 builder fixed each corner's class once per race from the median clear-air apex speed. The registration lists `corner_class` as a structure column, and this rule reads only the class, never the speed. The class is still a coarse function of speed in that race, so it is not pure geometry.

**Fallback (flagged).** A race with no structure row uses `era_factor x` its circuit-class value from `wake_placeholder_values.csv`, read as a 2017-18-era value. It has `loss_source = class_fallback` and a basis that starts "Fallback:". Today that is 4 races: 2018 Australia and Bahrain (no telemetry in bronze) and 2020 Tuscan and Sakhir (no FastF1 corner table).

**How much is assumption.** All of it. Within one layout, the value changes across seasons only by the era factor. Layout changes (Barcelona 2023, Singapore 2022–23, Yas Marina 2021, Melbourne 2022) also move it. The ordering between circuits follows the corner mix, and it can disagree with reputation. Spa scores below Hungary because most of Spa's fast corners are taken flat. Monaco scores close to Spa because it has many slow corners.

### Results (scratch copy, 2026-10-30)

173 races: 169 from the rule, 4 fallback. Range 0.15–0.47 s, mean 0.26 s. Examples:

| Circuit | 2018 | 2021 | 2022 | 2023 | 2025 |
| :-- | --: | --: | --: | --: | --: |
| Silverstone | 0.41 | 0.37 | 0.27 | 0.31 | 0.33 |
| Jeddah | — | 0.47 | 0.34 | 0.39 | 0.42 |
| Hungaroring | 0.34 | 0.31 | 0.22 | 0.25 | 0.27 |
| Monaco | 0.33 | 0.30 | 0.21 | 0.25 | 0.26 |
| Spa | 0.31 | 0.28 | 0.20 | 0.23 | 0.24 |
| Monza | 0.22 | 0.20 | 0.15 (floor) | 0.16 | 0.18 |

The mean per-lap cost over modelled laps is 0.069 s in 2022 and 0.083–0.093 s in the other seasons. Under WC-11 it was about 0.10 s.

### What was deliberately not used

- **Any outcome**: lap, sector and segment times, minimum, apex and exit speed, and speed traces. Speed-derived inputs such as lateral g from telemetry speed or time at full throttle would be useful, but they are outcomes and are not used. That includes `int_track_geometry`'s lateral-acceleration proxy, which uses speed.
- **`circuit_reference.csv`** (`avg_lateral_g`, `corner_count`): its provenance is mixed with a fitted coefficient pipeline, so it is not needed.
- **The archived dirty-air corner-class map** (DA-02P), to keep DA-03 artefacts out (rule 6).
- **DRS zones and the tow**: they are a gain, not a cost, and DRS use depends on the gap. Neither is in a structure column for every season.
- **Tyre and compound regime**: the wake's tyre effect builds up over a stint, so it is not a per-lap aero loss. It stays out until WC-10 measures it.

### Replaceability

The output columns are unchanged. New columns on `int_lap_wake_placeholder_cost`: `era`, `era_factor`, `loss_source`, `loss_bounded`, `loss_basis`. Calibrated values go in `int_wake_placeholder_race_loss.loss_s_per_lap_within_1s`, by a seed join or a replacement model, with `value_kind` and `loss_source` set. Nothing downstream changes.

### DA-03 check

No rule constant equals a DA-03 number at 3 dp. Values are rounded to 0.01 s, and `test_wc11_placeholder.py` recomputes every per-race value from the seeds and checks it too, so 0.40 cannot appear by chance unnoticed.

## WC-13: tyre and car factors (follow-on, 2026-10-30)

Each lap's race value is now multiplied by two small assumed factors. It is still a **placeholder, not a fit**. No lap time, segment time, speed or per-team pace was read to set any number, for any season, and the 2024-25 outcomes stay unread (W8). From `stg_laps` the model reads only identity columns: `lap_id`, `race_id`, `race_year`, `compound` and `constructor_id`.

```
loss_s_per_lap_within_1s = ROUND(clamp(race_loss x compound_factor x constructor_factor, 0.15, 0.55), 4)
wake_cost_placeholder_s  = loss_s_per_lap_within_1s x wake_exposure            (unchanged)
```

### Tyre factor (`seeds/wake_placeholder_compound_factor.csv`)

| Lap's compound in its race | Factor | Why |
| :-- | --: | :-- |
| softest of the race's three dry compounds (SOFT) | 1.10 | In the wake the car slides more and runs hotter tyre surfaces. A softer compound has a lower working window and overheats sooner |
| middle (MEDIUM) | 1.00 | Reference: the race value is read as the cost on the middle compound |
| hardest (HARD) | 0.96 | It tolerates the heat better. The step is smaller than SOFT's because a hard tyre still slides |
| INTERMEDIATE, WET | 1.00 | Neutral by rule. The dry softness ranking does not extend to them, and in the wet the wake's main cost is spray, which is not modelled. Flagged by `compound_factor_source = neutral_wet_or_intermediate` |
| missing compound | 1.00 | Neutral and flagged (`factor_flag`) |

**Reconciling with WC-12.** WC-12 left tyre regime out because the wake's tyre effect builds up over a stint, so it is not a per-lap aero loss. That still holds. The factor here is **not tyre wear**. It is a small, bounded per-lap sensitivity (−4 % to +10 %) on the existing loss: the same wake costs a little more on a tyre that overheats sooner. Stint-cumulative wear and overheating stay out until WC-10 measures them.

**Relative class, not C-number.** Since 2019 FastF1 labels compounds SOFT, MEDIUM and HARD relative to the race. `seeds/tyre_allocations.csv` maps those labels to C1-C6, but it is user-supplied and self-verified: only 47 of its 128 source URLs resolve, and every 2025 row is carried forward. Its own docs say not to quote it until it is re-sourced. So the factor uses the relative class (DD-WC28). For **2018**, FastF1 gives absolute names (HYPERSOFT to HARD). Each 2018 race's three dry compounds are ranked by softness (`compound_hardness_scale`) and mapped to SOFT, MEDIUM and HARD. Every one of the 21 races shows exactly three. A race showing any other count would be neutral and flagged (`neutral_unresolved_compound`).

**Bounds.** The seed test holds the factors to 0.90-1.15, monotone SOFT ≥ MEDIUM ≥ HARD.

**DA-03 (rule 6).** 0.95 was the natural HARD value. It makes 0.43 × 0.95 = 0.4085 (0.409 at 3 dp) and 0.34 × 0.95 = 0.323, both archived-method numbers, so HARD is 0.96. The per-lap loss is rounded to 4 dp, not 0.01: at 0.01, every factor between 1.03 and 1.12 puts some race on 0.40. `test_wc11_placeholder.py` enumerates every race × tyre × car value from the seeds and checks it.

### Car factor (`seeds/wake_placeholder_constructor_factor.csv`)

The table has one row per (season, `constructor_id`) in `stg_laps`: 81 rows for 2018-2025 (11 names in 2018, because Force India became Racing Point mid-season). `constructor_id` is the FastF1 team name, the key the ML side uses. A rename is its own row, and `constructor_lineage_id` from `dim_constructors` groups a team's names (`force_india`, `toro_rosso`, `sauber`, `renault`).

**Every row is neutral:** 1.00, `source_type = neutral_default`, basis "neutral default, no public evidence used". A non-neutral row needs a public, non-outcome, checkable source in `basis` (`source_type = public_concept`) and must stay within 0.95-1.05. None was set. Car concepts do differ publicly (high rake in 2018-20, the 2022 sidepod concepts), but no team statement or regulation says which way a concept moves wake sensitivity, and comments on how hard a car is to follow are outcome reports. Any number would be a guess about a real company (DD-WC27). A season or team with no row would get the neutral factor and a flag. `assert_wake_placeholder_factors` fails if that ever happens.

### New columns on `int_lap_wake_placeholder_cost`

`race_loss_s_per_lap_within_1s` (the WC-12 race value), `compound`, `compound_class`, `compound_factor`, `compound_factor_source`, `compound_basis`, `constructor_id`, `constructor_lineage_id`, `constructor_factor`, `constructor_factor_source`, `constructor_basis`, `lap_loss_bounded`, `factor_flag` and `lap_loss_basis`. **Changed meaning:** `loss_s_per_lap_within_1s` is now the per-lap value (race × tyre × car), so cost = loss × exposure still holds. No column was removed or renamed.

**Replaceability.** Calibrated per-race values go in `race_loss_s_per_lap_within_1s`, through `int_wake_placeholder_race_loss`. If the calibration already includes tyre or car effects, set both seeds' factors to 1.00. Nothing downstream changes.

### Results (scratch copy, 2026-10-30)

189,418 laps. The per-lap loss runs from 0.15 to 0.517 s (mean 0.256). The race values ran from 0.15 to 0.47. 2,134 laps are held at the 0.15 floor: the HARD laps at the four 2022 floor races (Austria, France, Monza, Abu Dhabi), flagged `lap_loss_bounded`. 1,129 laps have no compound recorded (neutral, flagged). 10,120 wet or intermediate laps are neutral by rule. No constructor row is missing. The mean cost per season moves by at most 0.0015 s against WC-12. Example, 2023 Silverstone (race value 0.31 s): SOFT 0.341, MEDIUM 0.310, HARD 0.2976 s per full lap within 1 s. Every team has the same car factor.

## WC-14: page visuals (follow-on, 2026-10-31)

The page gained two visuals above the table, display only (no warehouse, dbt, export or ML change). A per-driver bar chart of the total placeholder cost, labelled "placeholder, modelled", with "—" and a reason for a driver with no value. A "how the cost is built" diagram for a selected driver, one column per lap: the measured share within 1 s and 1-2 s of the car ahead above the assumed cost per lap. Neutralised and no-gap laps are hatched, never 0. It reads the lap-level columns already exported (`lap_number`, `share_lap_within_1s/2s`, `wake_cost_placeholder_s`, `unavailable_reason`). Code: `DirtyAirVisuals.tsx`, `visuals.ts`, `visuals.test.ts`. A tyre split of the bars was skipped (it needs a per-compound query).

## WC-15: collapsible table, GAS/TSU check, correlation with the Lap Air Map (follow-on, 2026-10-31)

Display only. **Table:** `DriverCostTable.tsx` replaces the wide `RankedTable`. A collapsed row has rank, driver, team, total, avg/lap and a `modelled` pill (phone width: driver, total, avg/lap). A click on the row, or Enter or Space on the driver button (`aria-expanded`, `aria-controls`), opens the detail: tyre factors, car factor with basis, laps with a value, laps unavailable with reasons, total laps. Several rows can be open. The dense note block is split: DD-WC2, the placeholder line, the field total and modelled share stay always visible (same constants); the assumed rule, tyre legend and car note sit in one closed "Assumptions" disclosure with a one-line summary. Export CSV is unchanged (full detail columns). Tests: `DriverCostTable.test.tsx`, `transform.test.ts`.

**GAS and TSU (2025 round 5) are not a bug.** Both retired on lap 1, so each has exactly one lap in `int_lap_wake_placeholder_cost`, and lap 1 (like laps 2 and 3, for all 20 drivers) is flagged `is_neutralised_lap` (safety car / red flag). No lap has a value, so the total is NULL and shown as "—" with that reason. The Lap Air Map lists the same single lap (TSU free air, GAS tow zone) because it does not exclude neutralised laps. Across all seasons, 3449 driver-races: 0 have modelled laps and a NULL total, 1 is an all-zero driver correctly shown as a modelled 0.00 s, and 120 have no value (71 neutralised only, 49 no gap measured only, 1 both). No `wake_exposure = 0` lap is ever unavailable. Neither the SQL nor the query needs a change.

**Correlation with the Lap Air Map** (Spearman across drivers; per-driver count of laps labelled `dirty_air` or `drs_train` in `int_lap_air_state` vs total placeholder cost; 171 races with 8+ drivers, 3329 driver-races):

| | dirty_air laps | drs_train laps | dirty_air + drs_train |
| :-- | --: | --: | --: |
| mean per race | 0.76 | 0.74 | 0.88 |
| median per race | 0.78 | 0.81 | 0.90 |
| pooled | 0.69 | 0.67 | 0.81 |

Examples: 2025_5 0.79 / 0.89 / 0.92, 2018_8 0.75 / 0.74 / 0.84, 2019_12 0.93 / 0.88 / 0.94, 2021_10 0.81 / 0.81 / 0.82, 2022_6 0.91 / 0.65 / 0.88, 2023_9 0.62 / 0.85 / 0.93, 2024_14 0.82 / 0.89 / 0.88, 2025_15 0.75 / 0.94 / 0.95. They agree broadly. They differ because the map labels a lap by its sector-2 median gap under 1.5 s (dirty air) or a straight-sector gap under 1.0 s (DRS train, tow), from the speed-converted gap, with the label priority dirty_air > drs_train > tow_zone > free_air, and neutralised laps are labelled. The cost is the assumed loss times the measured crossing-time share of the lap within 1 s plus half of 1-2 s, over the whole lap, with neutralised laps excluded. In 2025_5, HAD is 9th on `dirty_air` laps (7) but first on cost: 18 of his laps are `drs_train` (a close car on a straight) and the cost counts that close time. With `dirty_air` + `drs_train` he is first on both. Other outliers: 2022_17 PER has 10 `dirty_air` laps whose crossing-time gap median is 66 s (the speed-converted gap is badly biased there), so his cost is about 0.2 s; 2025_1 BOR has 6 of 7 `dirty_air` laps neutralised, so they carry no cost; 2025_2 SAI has 3 `dirty_air` laps but 51 free-air laps with 57% of the lap within 2 s, so he ranks high on cost and low on the map.


## WC-16: C-number tyre factor, DD-WC2 rewording, car-factor research (follow-on, 2026-10-31)

Owner rulings (2026-10-31): **DD-WC26** accepted (the placeholder line stays "... on this tyre and car, not a measurement of this lap."). **DD-WC27** resolved: a public-concept search over all 81 (season, team) rows found no explicit, citable, non-outcome source saying which way a team's concept moves wake sensitivity (`_evidence/WC-16-2026-10-31/constructor_report.md`), so every car factor stays neutral 1.00; no seed value changed. **DD-WC28** resolved: the tyre factor uses Pirelli's C-numbers. **DD-WC2** reworded: every placeholder value now carries, word for word, "Modelled: an assumed typical loss for this circuit, season, tyre and car, applied to the measured time spent close behind another car. Not calibrated on this driver's own stints." The 2026-10-27 wording is kept in the decision's history.

**Open overlap (owner to decide later):** the new DD-WC2 line and the DD-WC26 placeholder line now say much the same thing (an assumed typical cost for this circuit, season, tyre and car, not a measurement). Both are kept, as ruled.

_[note 2026-11-01: overlap settled by **DD-WC30** (delegated ruling: the owner delegated it to Opus). DD-WC2 is unchanged, word for word. The placeholder line now reads, word for word: "Placeholder = an interim value set by a fixed rule, not a measurement of this lap." It supersedes the DD-WC26 text and is applied in int_lap_wake_placeholder_cost, its schema accepted_values, assert_wake_placeholder_labels, the Dirty Air Cost app page and test, docs/app/dirty-air-cost.mdx, the AI copy and test_wc11_placeholder.py.]_

**Not changed (outside the ruling):** `contest.py` `DD_WC2_DISCLAIMER` and `test_contest.py` (WC-03/04, no modelled value), `run_wc10.py` `DD_WC2` (WC-10, paused), and the specs WC-05, WC-06, WC-08, WC-design-note and the WC-10 drafts, which still quote the 2026-10-27 text.

### The rule

New seeds: `wake_placeholder_tyre_allocation.csv` (173 races: C-code trio 2019-2025, Pirelli names in 2018 with NULL C-numbers, `compound_scale` = `c_number` / `named_2018`, fetched `source_url` per row; from `_evidence/WC-16-2026-10-31/c_numbers.csv`) and `wake_placeholder_c_number_factor.csv` (the constants, each with a basis). Per 2019+ dry lap, its label (HARD / MEDIUM / SOFT) is mapped to the race's C-number:

```
compound_factor = ROUND(clamp(step(C_lap - C_medium) x medium_shift(C_medium), 0.90, 1.17), 4)
step:  <= -2: 0.93   -1: 0.96   0: 1.00   +1: 1.10   >= +2: 1.17     (positive = softer, counted in C-numbers)
shift: C2 1.00   C3 1.00   C4 1.00   C5 1.00                          (DD-WC29: dropped; C1 / C6 as medium fails assert_wake_placeholder_tyre_allocation)
```

**DD-WC29 (owner, 2026-10-31): the medium shift is dropped.** The research proposed C2 0.97, C3 1.00, C4 1.03 and C5 1.06. That put 23 per-lap values on archived-method numbers at 3 dp (see below), so all four shift rows are 1.00 and rule 6 stays strict. The rows are kept so a calibrated shift can slot in later. The tyre factor is therefore the step alone: 0.93, 0.96, 1.00, 1.10 or 1.17.

2018 (named compounds) and any race without a trio keep the WC-13 relative factors (1.10 / 1.00 / 0.96). Wet, intermediate and missing compounds stay neutral and flagged as before. New columns: `compound_factor_scale` (`c_number` / `relative_class` / `neutral`; the brief's name `compound_basis` was already taken by the basis text, so it was not reused), `tyre_c_number`, `race_medium_c`. `compound_factor_source` gains `assumed_c_number`. `lap_loss_basis` names the C-number (for example "tyre 1.10 (SOFT C4)"). The user-supplied `tyre_allocations.csv` is neither read nor edited.

### Corrections to the user-supplied `tyre_allocations.csv` (fixed for this model only)

The new seed differs from that file at 12 rows, and it adds 2025_6 Miami (C3/C4/C5), which the file is missing. The owner may want to correct the original file:

| race_id | tyre_allocations.csv | verified |
| :-- | :-- | :-- |
| 2024_16 Italy | C2/C3/C4 | C3/C4/C5 |
| 2025_5 Saudi Arabia | C2/C3/C4 | C3/C4/C5 |
| 2025_7 Emilia Romagna | C3/C4/C5 | C4/C5/C6 |
| 2025_8 Monaco | C3/C4/C5 | C4/C5/C6 |
| 2025_10 Canada | C3/C4/C5 | C4/C5/C6 |
| 2025_12 Britain | C1/C2/C3 | C2/C3/C4 |
| 2025_13 Belgium | C2/C3/C4 | C1/C3/C4 |
| 2025_15 Netherlands | C1/C2/C3 | C2/C3/C4 |
| 2025_16 Italy | C2/C3/C4 | C3/C4/C5 |
| 2025_17 Azerbaijan | C3/C4/C5 | C4/C5/C6 |
| 2025_19 United States | C2/C3/C4 | C1/C3/C4 |
| 2025_20 Mexico City | C3/C4/C5 | C2/C4/C5 |

### Results (after DD-WC29; scratch copy, then the real warehouse, 2026-10-31)

The scratch copy and the real warehouse give identical results, down to a per-lap hash of cost, factor and loss. There are 189,418 laps, 173,679 of them with a value (unchanged).

Laps by `compound_factor_scale`:

| Scale | Laps |
| :-- | --: |
| c_number | 156,211 |
| relative_class (all 2018) | 21,958 |
| neutral (10,120 wet or intermediate, 1,129 with no compound) | 11,249 |

Tyre factors in use: 0.93 on 223 laps, 0.96 on 77,863, 1.00 on 80,251, 1.10 on 31,080 and 1.17 on 1. The per-lap loss still runs from 0.15 to 0.517 s (mean 0.2560), and 2,134 laps are still held at the floor. The mean cost goes from 0.085599 to 0.085597 s per lap.

Against WC-13, only the skip races change, 224 laps in all:

| Race | Laps | Change |
| :-- | --: | :-- |
| 2025_13, HARD C1 | 72 | 0.96 → 0.93 |
| 2025_19, HARD C1 | 59 | 0.96 → 0.93 |
| 2025_20, HARD C2 | 92 | 0.96 → 0.93 |
| 2022_3, SOFT C5 | 1 | 1.10 → 1.17 |

Season mean costs are unchanged to 4 dp, except 2025, which goes from 0.0910 to 0.0909 (−0.00002). The C-numbers now appear on the page (for example "HARD (C3) x0.96, MEDIUM (C4) x1.00" at 2025_5). 2018's observed dry compounds agree with the verified names at every race. DA-03: 0 of the 11,544 race × tyre × car values collide.

### DA-03 (rule 6): history of the collision and the DD-WC29 ruling

`test_combined_value_bounded_and_off_da03` fails. 23 race × tyre per-lap values land on an archived-method number at 3 dp, for example 2019_5 MEDIUM 0.26 × 0.97 = 0.2522 and 2023_8 HARD 0.19 × 0.9888 = 0.1879. The constants themselves and the per-race values are clear. The collisions come only from the medium shift. With the shift alone dropped (step only), 0 values collide. No ±0.01 or ±0.02 nudge to any combination of the seven non-reference constants reaches 0 (the best is 5, at C2 0.96 and C4 1.04), so the "nudge one constant" remedy does not work. Rounding the factor to 2 dp leaves 19 collisions, and rounding the per-lap loss to 0.01 leaves 4. The test was left failing, not weakened, and the owner ruled option (a): drop the shift. With the shift at 1.00 for every medium, 0 of the 11,544 race × tyre × car values collide, and the test passes unchanged.
