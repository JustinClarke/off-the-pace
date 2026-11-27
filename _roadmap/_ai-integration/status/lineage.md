# Lineage and robustness: what feeds what, and where it can break

Snapshot taken 2026-11-24 of the transform pipeline: lineage, bronze storage, schemas and robustness signals. Built by reading the model, schema, test, app and ML code. No dbt run, no data queried, no tests executed in sections A to E. Section F (Race Control and Safety Car hazard) was checked against the built exports, the CI fixture and the test suites on the same day.

**Current status.** Sections A to F describe the findings as checked on their dates. Current work status is in the snapshot below and in section G. Nothing in G changes a finding above.

## Repo status snapshot (2026-11-24)

- **Main.** Branch `main`, HEAD `baa0c82` (Task 2B merge). Not pushed; `origin/main` is at `9def077`.
- **Task 2A.** Deferred. Functional changes are reverted and not active. The patch and tests are archived in [`_roadmap/_archive/compound-cliff-2a/`](../../_archive/compound-cliff-2a/ARCHIVED.md).
- **Task 2B.** Merged into main (`6a891a5` on the branch, merged as `baa0c82`). Not pushed or deployed.
- **Warehouses.** `data/dev.duckdb` is near-empty (under 1 MB) and is not a trusted build. `data/ci.duckdb` is the CI fixture. Neither is a canonical full build.
- **Pipeline in brief.**
  1. Raw bronze parquet (FastF1, Jolpica) is declared as sources in `transform/models/staging/src_*.yml`.
  2. Staging (`stg_*`) cleans one raw table each.
  3. Intermediate (`int_*`) holds the logic. The compound path is `dim_compounds_season` (reference, fitted coefficients) feeding `int_compound_cliff_predicted`.
  4. Marts include `fct_cliff_prediction_features`, which reads `int_compound_cliff_predicted`.
  5. Readers: ML (`ml/src`) reads the marts from the warehouse, and `scripts/export_app_data.py` exports tables to parquet for the app.

**Top findings**

1. Almost every number the app and the ML model show passes through [int_stint_geometry](../../../transform/models/intermediate/int_stint_geometry.sql), [int_lap_fuel_state](../../../transform/models/intermediate/int_lap_fuel_state.sql) and [int_lap_residual_decomposed](../../../transform/models/intermediate/int_lap_residual_decomposed.sql). A mistake in any of these spreads to 30 to 60 other models.
2. Robustness varies widely by component. Short chains close to raw data (staging, stint geometry, the power-law chain, the lap residual identity) carry few assumptions. Long chains that stack several assumptions (qualifying features, ghost car, corner skill, cliff defaults) carry many. Section C lists the signals for each component.
3. The worst habit in the code is a default that looks like data: 0.0 constructor pace, `LEAST(slope, 0)` in track evolution, 0.5 thermal ratio, default tyre-cliff cells, 0.0 qualifying race-average. Some now carry a flag column (`constructor_pace_is_filled`, `*_is_prior`), but the downstream averages mostly ignore the flag.
4. The ML contract (39 features) comes from one mart, [fct_cliff_prediction_features](../../../transform/models/marts/fct_cliff_prediction_features.sql). Its leakage guards are strong and tested. Its weakest inputs are the seven qualifying features and the compound and cliff-prior features, which sit on seed-fitted defaults.

---

## A. How the pipeline works

**Sources.** Raw race data is read from "bronze" parquet files (FastF1 laps, telemetry, weather, results, track status, race control, circuit info, qualifying versions of these) plus Jolpica pit stops. They are declared in [src_formula1.yml](../../../transform/models/staging/src_formula1.yml) and [src_jolpica.yml](../../../transform/models/staging/src_jolpica.yml). One more source, `fits`, is a parquet file written by a Python fit script outside dbt ([src_fits.yml](../../../transform/models/intermediate/src_fits.yml)). Hand-kept lookup tables ("seeds") sit in [transform/seeds](../../../transform/seeds): `race_to_track`, `circuit_reference`, `compound_cliff_params`, `compound_hardness_scale`, `race_scheduled_laps`, `tyre_allocations`, `seed_manual_lap_exceptions`, `raw_dim_events`, `driver_isolation_method_scores`.

**Staging (`stg_*`).** One cleaning step per raw table: rename columns, fix types, map tyre names, flag valid laps. Almost no logic. Output is in [transform/models/staging](../../../transform/models/staging).

**Intermediate (`int_*`).** Where the logic lives. 60 SQL models and 5 Python models. They build, in order: the stint (one continuous run on one set of tyres) per lap; fuel mass per lap; the field pace curve (what a normal lap time is on that lap); track evolution (the track getting faster as rubber builds); the dirty-air state (time spent close behind another car); expected tyre wear and "cliff" (the lap where a tyre suddenly drops off); and then the lap residual. The residual is lap time minus all those terms, and it is used as the driver skill signal. Driver ratings, qualifying, corner skill and pit strategy build on top. Files are in [transform/models/intermediate](../../../transform/models/intermediate).

**Reference (`dim_*`).** Small lookup tables built from seeds (circuits, compounds per season, constructors, drivers, corners). In [transform/models/reference](../../../transform/models/reference).

**Marts (`fct_*`, `mart_*`).** The tables other things read. `fct_cliff_prediction_features` is the ML training table. `fct_lap_residuals`, `fct_stint_features`, `fct_ghost_*`, `fct_driver_skill_features` and the `mart_*` summaries feed the app. In [transform/models/marts](../../../transform/models/marts). Five scratch marts under `new_data/` have no reader yet.

**Readers.**
- **Export.** [scripts/export_app_data.py](../../../scripts/export_app_data.py) copies a fixed list of tables to parquet in `app/public/data`. The app can only read tables on that list (plus one derived table, `race_caution_timeline`, built from `int_stint_geometry`).
- **App.** Pages in [app/src/features](../../../app/src/features) run SQL against those parquet files in the browser.
- **Assistant.** [app/src/assistant](../../../app/src/assistant) builds answer "cards" from the same exported tables. Some cards are held stubs that name a table that does not exist (`fct_constructor_structural_pace`, in [heldStubs.ts](../../../app/src/assistant/cards/sql/heldStubs.ts)).
- **ML.** [ml/src/features.py](../../../ml/src/features.py) and [ml/src/schema.py](../../../ml/src/schema.py) read `fct_cliff_prediction_features` and `fct_stint_features` straight from the DuckDB warehouse. [ml/src/powerlaw.py](../../../ml/src/powerlaw.py) reads `fct_power_law_training`. [ml/src/predict.py](../../../ml/src/predict.py) writes `mart_degradation_predictions.parquet`, which the app reads for the model pages. This table is not a dbt model.

---

## A1. Bronze storage: what the raw layer holds and how it is laid out

Auditor's note. Every figure in this section was checked against the ingestion code, [ingestion/DESIGN.md](../../../ingestion/DESIGN.md), [ingestion/SCHEMA.md](../../../ingestion/SCHEMA.md), the dbt source files and a `DESCRIBE` of sample parquet files. Nothing was computed from the warehouse.

- **Where it lives.** `data/bronze/` (the dbt variable `bronze_base` defaults to `../data/bronze`). Bronze is a directory of Parquet files, not a database table. dbt declares each dataset as an external source (`database: read_only`, with an `external_location` glob) and DuckDB reads the files in place at query time. Nothing is copied into a bronze table.
- **Who writes it.** The Python ingestion in [ingestion/src](../../../ingestion/src) pulls from FastF1 (and Jolpica for pit stops and standings). It writes each file once. A rerun skips any file that already exists, unless `--force` is given. Every run also writes one manifest row per session (status, row count, DQ result, schema fingerprint) to `data/bronze/manifests/run_<id>.parquet`.
- **Layout.** Hive-partitioned folders: `<dataset>/season=YYYY/race=<slug>/<file>.parquet`. Qualifying sits one level deeper under `session=Q/`. The race folder names are text slugs (for example `italian_grand_prix`), while the dbt `race_id` is a numeric FastF1 id (`YYYY_R`). The mapping between the two lives in the seed `race_to_track`.
- **Dataset files.**

  | Dataset (folder) | File | One row per | Used by dbt? |
  |---|---|---|---|
  | `laps` | `laps/season=/race=/YYYY_<slug>_laps.parquet` (quali under `session=Q/`) | driver × lap | yes, `raw_laps` and `raw_laps_qualifying` |
  | `telemetry` | `telemetry/season=/race=/telemetry.parquet` | telemetry sample (about 10 ms), all drivers in one file | yes, `raw_telemetry` |
  | `telemetry_full` | `telemetry_full/season=/race=/driver=N/car_data.parquet` | car-channel sample per driver | not found in the dbt sources (not traced further) |
  | `pos_data` | `pos_data/season=/race=/driver=N/pos_data.parquet` | position sample per driver | not found in the dbt sources (not traced further) |
  | `weather` | `weather/season=/race=/weather.parquet` | weather sample (about 1 Hz) | yes, `raw_weather` |
  | `results` | `results/season=/race=/results.parquet` (quali under `session=Q/`) | driver × session | yes, `raw_results` and the quali variant |
  | `track_status` | `track_status/season=/race=/…` (quali under `session=Q/`) | status change event | yes |
  | `session_status` | `session_status/season=/race=/…` (quali under `session=Q/`) | session lifecycle event | yes |
  | `race_control` | `race_control/season=/race=/race_control.parquet` (quali under `session=Q/`) | FIA message | yes, `raw_race_control` |
  | `circuit_info` | `circuit_info/season=/race=/[session=Q/]circuit_info.parquet` | corner | yes, `raw_circuit_info` (and quali) |
  | `circuit_markers` | `circuit_markers/season=/race=/[session=Q/]circuit_markers.parquet` | corner, marshal light, marshal sector, rotation | not found in the dbt sources (not traced further) |
  | `session_info` | `session_info/season=/race=/[session=Q/]session_info.parquet` | one row per session | not found in the dbt sources (not traced further) |
  | `schedule` | `schedule/season=YYYY/schedule.parquet` | event in a season | not found in the dbt sources (not traced further) |
  | `reference/jolpica` | `reference/jolpica/pit_stops/season=/round=/pit_stops.parquet`, plus `driver_standings` | pit stop | yes, `raw_jolpica_pit_stops` (cross-check only) |
  | `manifests` | `manifests/run_<run_id>.parquet` | ingestion attempt per session | no (read by `make manifest-report`) |

- **How values are stored.**
  - Column names mostly keep FastF1's own names (for example `LapTime`, `Driver`, `Stint`, `Compound`), with a few lower-case additions. Most datasets also carry `race_id`, `season` and `race` as columns, so they do not need the path. Qualifying and race files add `session_type` and `session` as columns in about half the files only (see A3). The `DESIGN.md` line about renaming to snake_case applies only in part. The dbt source YAML is the reference for what dbt reads.
  - Times are integers in **nanoseconds** (`LapTime`, `Sector1Time`, `SessionTime`, `Time` in telemetry and race control). Some fields are in seconds (`session_time_s` on weather and track status). Staging divides by 1e9 for the lap and results columns.
  - Telemetry is one long, interleaved table. A column named `Source` says which of three FastF1 channels each row came from: `car` (car channel), `pos` (position channel) or `interpolation` (a few joined samples). Staging splits these apart (`stg_telemetry`, `stg_telemetry_position`).
  - Telemetry positions (`X`, `Y`) are in FastF1 units (1/10 m), and distance is in metres.
  - Nothing is computed in bronze: no lap validity flags, no joins, no derived metrics. Those are written in dbt staging and intermediate models. The exception is the file split described above.
  - Known gaps and the data-quality rules are in [ingestion/known_gaps.txt](../../../ingestion/known_gaps.txt) and the dbt source YAML.
- **What an auditor should check first.** Confirm the file and column names with `DESCRIBE` before relying on the dbt source YAML, because `SCHEMA.md` warns that older versions of that document were wrong. Check the manifest for `error` rows and for schema drift between runs. Remember that bronze is a read-only copy of FastF1, so a transform bug never needs a re-ingestion.

### A2. What each model does to the data

One sentence per model, in the order of the layers. The sentence is my reading of each model's header comment and SQL. It is not a check of the output. Model files live under `transform/models/<layer>/`.

**Staging (`stg_*`, 21 models)**

| Model | What it does |
|---|---|
| `stg_circuit_info` | Reads FastF1 corner geometry and orders corners by distance along the lap (one row per corner per race). |
| `stg_events` | Lists race events (upgrades, penalties, DNFs, format changes) from the manual `raw_dim_events` seed; only 2021 has entries. |
| `stg_jolpica_pit_stops` | Renames Jolpica pit-stop rows to one row per stop, keyed by `race_id`; used only by the pit-stop cross-check. |
| `stg_lap_tyre_qa` | Checks each race lap's bronze stint, tyre age and compound against stint-change evidence, and fills or quarantines the gaps under documented rules (F24, F25). |
| `stg_laps` | Renames race laps to snake_case, converts nanoseconds to seconds, and sets `is_valid_lap` (timed, not a pit lap, not deleted, accurate from 2019, not lap 1, no neutralisation, not hand-excluded). |
| `stg_laps_qualifying` | Mirrors `stg_laps` for Q1, Q2 and Q3 laps. |
| `stg_physical_ahead_laps` | Gives the physical-ahead chain its race-lap input (driver × lap), with pit windows and reference laps. |
| `stg_physical_ahead_telemetry` | Keeps only position-channel samples for the physical-ahead chain and flags placeholder rows where X and Y are both 0 (none are dropped here). |
| `stg_pits` | Produces one row per pit stop by joining the in-lap (`PitInTime`) to the following out-lap (`PitOutTime`). |
| `stg_race_control` | Renames the FIA message feed to one row per message, with no other logic. |
| `stg_red_flags` | Produces one row per race red flag, taken from track-status code 5 because the session-status feed is incomplete. |
| `stg_red_flags_qualifying` | Qualifying version of `stg_red_flags`, also from track-status code 5. |
| `stg_results` | Produces one row per driver per race with the classified position, status and times (nanoseconds converted to seconds). |
| `stg_results_qualifying` | Produces one row per driver per qualifying session, with the Q1, Q2 and Q3 times. |
| `stg_sector_times` | Splits each lap into three sector rows (sector times and speed traps; `SpeedI2` on S2, `SpeedST` on the main straight). |
| `stg_session_status_qualifying` | Records qualifying session lifecycle events (start, end, red and so on). |
| `stg_telemetry` | Renames every telemetry sample (all three channels) to snake_case and casts distance to double, without filtering. |
| `stg_telemetry_position` | Keeps only position-channel samples and their X, Y and relative-distance columns. |
| `stg_track_status` | Decodes the numeric track-status codes into named flags (yellow, SC, VSC, red) and orders the events by session time. |
| `stg_tyre_allocations` | Maps each race's Pirelli compound nominations (C-codes) to the actual hard, medium and soft compounds. |
| `stg_weather` | Attaches to each lap the weather sample nearest its start, using an as-of join. |

**Intermediate (`int_*`, 60 SQL and 5 Python models)**

| Model | What it does |
|---|---|
| `int_stint_geometry` | Foundation of the physics layer: one row per lap with its stint id, tyre age, compound and flags, which all later window functions partition on. |
| `int_lap_fuel_state` | Estimates fuel mass per lap by an even burn over the scheduled distance, and turns it into a weight-penalty correction in seconds. |
| `int_compound_cliff_predicted` | Predicts each lap's expected tyre pace, wear and cliff from the compound parameters (grip peak, linear wear, saturating post-onset loss). |
| `int_field_pace_curve` | Builds the reference "normal lap" time per race lap, as a 10% trimmed mean of fuel- and compound-corrected times from eligible laps. |
| `int_track_evolution` | Splits the track-evolution term into a capped linear trend (rubber) and an ambient temperature component, per lap. |
| `int_lap_rain_state` | Labels each lap DRY, WET or NO_WEATHER from weather rainfall; it does not read the pace curve. |
| `int_event_corrections` | Flags laps affected by SC, VSC, red flag or yellow, and assigns each lap a correction weight. |
| `int_lap_anomaly_flags` | Classifies each lap as normal or anomalous by combining control-event contamination with MAD-based residual outliers; it gates ML training rows. |
| `int_lap_residual_decomposed` | The core model: lap time minus the fuel, compound, constructor and dirty-air terms (plus the other inputs listed in section B1), leaving the driver-skill residual, and publishes `base_pace_status`. |
| `int_lap_residual_decomposed_qualifying` | Applies the same residual identity to qualifying laps, without a fuel term. |
| `int_lap_residual_stint_detrend` | Fits a linear drift of the residual against lap-in-stint for each stint, using pre-cliff clean laps. |
| `int_lap_thermal_proxy` | Produces a per-lap push-intensity proxy (residual against the stint's own baseline) used for tyre thermal load. |
| `int_lap_air_state` | Classifies each lap's air state (clear or dirty air) from the gap to the car ahead, and computes the dirty-air thermal load, reading bronze telemetry directly. |
| `int_dirty_air_tax_component` | Converts the dirty-air state into a seconds-lost term per lap. |
| `int_lap_proximity` | Computes per-lap gaps to the cars ahead and behind from the position channel (time within 1 s and 2 s, gap ahead, car count). |
| `int_lap_telemetry_aggregates` | Summarises each lap's car-channel telemetry; kept in the mart but dropped from the ML contract. |
| `int_lap_normalized_pace` | Normalises lap times for fuel and compound and keeps them for analysis; a deliberate leaf with no downstream model. |
| `int_constructor_structural_pace` | Estimates one pace offset per constructor per race as the median of lap residuals after the other terms. |
| `int_constructor_structural_pace_qualifying` | Estimates the constructor pace coefficient for qualifying sessions. |
| `int_constructor_deg_sensitivity` | Estimates each constructor's tyre-degradation sensitivity (cliff-onset shift), used by the ghost car. |
| `int_circuit_x_constructor_interaction` | Estimates how each constructor's pace varies by circuit, including car development. |
| `int_driver_race_paired_laps` | Builds the paired lap-time gaps between teammates in each race, the input to driver ratings. |
| `int_driver_race_skill_loro` | Estimates each driver's skill against teammates in the same car, leave-one-driver-out, per race. |
| `int_driver_season_ratings` | Produces a shrunk per-driver-season residual rating. |
| `int_era_normalized_driver_rating` | Puts season ratings on one scale across the 2022 regulation change. |
| `int_driver_circuit_affinity` | Estimates driver × circuit affinity with Bayesian shrinkage. |
| `int_driver_circuit_era_affinity` | Estimates each driver's "equal-car" record at each circuit within each regulation era. |
| `int_driver_isolation_lap_panel` | Builds the clean-lap panel (Ω) and the field-centred isolated lap time for the driver-isolation chain. |
| `int_driver_isolation_lap_pace` | Gives the isolated pace per Ω lap, with the car removed. |
| `int_driver_isolation_lap_values` | Gives the tier-1 pure skill gain per Ω lap. |
| `int_driver_isolation_stint_tyre` | Gives each stint's pace line (the stint layer of driver isolation). |
| `int_synthetic_teammate` | For each driver lap, builds a comparison lap from the same-constructor teammate. |
| `int_corner_metrics` | Computes driver × lap × corner metrics (throttle, brake and speed) from telemetry windows. |
| `int_corner_lap_measured` | Records which corner windows were measured on each driver lap. |
| `int_corner_length_measured` | Measures each corner's length per race (corners with an apex). |
| `int_corner_drift_from_early_stint` | Measures each corner's drift against the driver's own early-stint baseline. |
| `int_lap_corner_drift` | Aggregates corner drift to lap grain. |
| `int_lap_corner_inputs` | Aggregates corner-level driver inputs to lap grain. |
| `int_corner_skill_residuals` | Produces the corner-level skill residual per corner per lap (the corner analogue of the lap residual). |
| `int_sector_residual_decomposed` | Splits the lap residual across the three sectors in proportion to sector time. |
| `int_microsector_corner_class` | Classifies each race micro-sector by corner type. |
| `int_microsector_crossings` | Records when each driver crosses each micro-sector boundary on each lap. |
| `int_microsector_proximity` | Records driver proximity within each micro-sector per lap. |
| `int_track_geometry` | Builds track geometry in distance bins per race; no reader and no tests. |
| `int_physical_ahead_pair_race` | Lists the follower and leader car pairs that were physically ahead of each other in each race. |
| `int_traffic_exposure_driver_race` | Measures how long each driver spent in traffic in each race, from physical-ahead pairs. |
| `int_traffic_exposure_race` | Summarises traffic exposure at race level. |
| `int_pit_loss_circuit` | Gives the empirical pit-lane time loss per circuit, used as a prior. |
| `int_pit_strategy_cost_curve` | Gives the time-cost curve for each stint and candidate pit-lap offset. |
| `int_pit_strategy_value` | Finds each stint's optimal pit lap and the seconds it costs. |
| `int_stint_end_regime` | Records why each stint ended (pit, cliff and so on), the label for stint-life targets. |
| `int_tyre_surface_vs_bulk_decoupling` | After the cliff, splits tyre degradation between surface and bulk temperature. |
| `int_power_law_lap` | Holds the single lap set that every power-law fit uses, with the identification check. |
| `int_cell_power_law_fit` | Fits the pooled power-law degradation curve per race and compound-hardness cell (the training target for the power-law model). |
| `int_stint_power_law_fit` | Fits a power-law degradation curve for each stint; kept only as a parity reference. |
| `int_sc_hazard_history` | One row per (circuit_slug, season) of safety-car and VSC onset rates per racing lap, estimated only from earlier seasons, raw and empirical-Bayes shrunk. Feeds the race-control page and the `circuit_*_hazard` columns of `fct_cliff_prediction_features`. See section F. |
| `int_qualifying_segments` | Recovers the Q1, Q2 and Q3 time windows from session status and official segment times. |
| `int_qualifying_push_laps` | Flags which qualifying laps count as push laps. |
| `int_qualifying_decomposed` | Decomposes qualifying residuals and combines them with the quali-vs-race skill measure. |
| `int_qualifying_driver_summary` | Summarises each driver's qualifying weekend, as the ML qualifying feature input. |
| `int_constructor_car_fe` (Python) | Fits constructor car fixed effects within the warehouse build. |
| `int_constructor_car_fe_isolation` (Python) | Gives isolated constructor car effects over the clean-lap panel (Ω). |
| `int_lap_physical_ahead` (Python) | Gives each race lap its physical-ahead status, on the stint-geometry spine. |
| `int_physical_ahead_pairs` (Python) | Lists follower and leader pairs that were physically ahead, per race. |
| `int_physical_ahead_pairs_lapped` (Python) | Same as `int_physical_ahead_pairs`, also covering lapped cars. |

**Reference (`dim_*`, 6 models)**

| Model | What it does |
|---|---|
| `dim_circuits` | Turns the `circuit_reference` seed into a typed table of lap length, corners and related values, one row per event slug. |
| `dim_compounds_season` | Gives the cliff and compound parameters per circuit, compound and season, from the `compound_cliff_params` seed (this includes fallback cells). |
| `dim_constructors` | Gives constructor reference data (power-unit family and team lineage). |
| `dim_corners` | Gives telemetry corner windows per race and circuit turn, taken from FastF1 corner data. |
| `dim_driver_seasons` | Gives one row per season and driver code (codes are reused and names change between seasons). |
| `dim_drivers` | Gives the stable driver reference, keyed by three-letter code, derived from the laps source. |

**Marts (`fct_*`, `mart_*`, 19 models)**

| Model | What it does |
|---|---|
| `fct_cliff_prediction_features` | Builds the 39-feature ML training table (one row per valid race lap), with leakage guards. |
| `fct_lap_residuals` | Lap-grain residual table read by the app pages; adds `constructor_pace_is_filled` and passes the residual through. |
| `fct_stint_features` | Stint-grain table of features and the stint-life label for pit strategy and the ML stint-life model. |
| `fct_power_law_training` | Gives the training frame for `powerlaw.py`, one row per race × compound cell that is eligible for fitting. |
| `fct_driver_skill_features` | Gives the driver-race skill feature table for the driver-skill model. |
| `fct_driver_isolation_lap` | Gives the rolling ~5-lap driver rating per Ω lap. |
| `fct_driver_isolation_pair_lap` | Compares car pairs with same-strategy peers and splits the difference into driver, car and residual terms. |
| `fct_driver_isolation_race` | Gives the driver-isolation rating per driver-race. |
| `fct_driver_isolation_stint` | Gives the driver-isolation rating per stint phase (early, mid, late). |
| `fct_ghost_car_pace` | Reconstructs the counterfactual lap time of each ego driver in each host constructor's car, per lap. |
| `fct_ghost_race_finish` | Projects each host constructor's race finish in the ghost scenario. |
| `fct_telemetry_deltas` | Gives teammate deltas per lap per circuit turn; its consumers were not traced. |
| `mart_race_driver_summary` | Gives one row per driver per race: rating, constructor rank and reasons for the result. |
| `mart_driver_season_summary` | Gives one row per driver per season, with its rank, for assistant explanations. |
| `mart_race_coverage` | Gives one row per race saying what was measured and why a rating is missing. |
| `mart_metric_benchmark` | Gives the per-season distribution of each metric over ML-eligible laps. |
| `mart_corner_skill_driver` | Gives each driver's corner skill as time gained against the LORO car baseline. |
| `mart_degradation_history_envelope` | Gives the degradation envelope per circuit, era, compound and lap of stint, using an external fit. |
| `mart_build_provenance` | Gives one row per build, recording the label, coefficients, data window and dbt run that produced it. |

**New-data scratch marts (`marts/new_data/`, 5 models, not exported)**

| Model | What it does |
|---|---|
| `fct_pit_stop_crosscheck` | Sets Jolpica pit stops beside FastF1 stops per driver and race, as two separate sources. |
| `fct_speed_traps` | Gives speed-trap readings per driver, race and session. |
| `fct_speed_traps_season` | Rolls speed traps up per season and team, with the count behind each value. |
| `fct_track_limits` | Lists deleted laps (track-limit violations), one row per lap. |
| `fct_track_limits_driver_session` | Counts deleted laps per driver and session, with the laps run as the denominator. |

### A3. Schema: bronze columns and model output columns

Two parts. Part 1 lists the columns that each bronze dataset holds, read from the Parquet files themselves with DuckDB `DESCRIBE`. Part 2 lists the column names that each dbt model declares in its `schema.yml`. dbt YAML in this repo gives names and descriptions but no data types, so model types are not shown here.

**Caveats.** Bronze has schema drift. The union below covers every column seen in a sample of the files (at most 400 per dataset, spread across the seasons). Where a column appears in only some files, the table says how many sampled files had it. Types that differ between files are shown with a slash. Model lists come from YAML and may lag the SQL. Compare the two before relying on either.

#### Part 1. Bronze columns (`data/bronze/`)

**laps (race and quali; quali under session=Q)**: 384 files; 37 columns in the union.

| Column | Type | Note |
|---|---|---|
| `Time` | BIGINT |  |
| `Driver` | VARCHAR |  |
| `DriverNumber` | VARCHAR |  |
| `LapTime` | BIGINT |  |
| `LapNumber` | DOUBLE |  |
| `Stint` | DOUBLE |  |
| `PitOutTime` | BIGINT |  |
| `PitInTime` | BIGINT |  |
| `Sector1Time` | BIGINT |  |
| `Sector2Time` | BIGINT |  |
| `Sector3Time` | BIGINT |  |
| `Sector1SessionTime` | BIGINT |  |
| `Sector2SessionTime` | BIGINT |  |
| `Sector3SessionTime` | BIGINT |  |
| `SpeedI1` | DOUBLE |  |
| `SpeedI2` | DOUBLE |  |
| `SpeedFL` | DOUBLE |  |
| `SpeedST` | DOUBLE |  |
| `IsPersonalBest` | BOOLEAN |  |
| `Compound` | VARCHAR |  |
| `TyreLife` | DOUBLE |  |
| `FreshTyre` | BOOLEAN |  |
| `Team` | VARCHAR |  |
| `LapStartTime` | BIGINT |  |
| `LapStartDate` | TIMESTAMP_NS |  |
| `TrackStatus` | VARCHAR |  |
| `Position` | DOUBLE |  |
| `Deleted` | BOOLEAN |  |
| `DeletedReason` | VARCHAR |  |
| `FastF1Generated` | BOOLEAN |  |
| `IsAccurate` | BOOLEAN |  |
| `race_id` | VARCHAR |  |
| `season` | BIGINT |  |
| `race` | VARCHAR |  |
| `race_name` | VARCHAR | in 193 of 384 sampled files |
| `session_type` | VARCHAR | in 193 of 384 sampled files |
| `session` | VARCHAR | in 193 of 384 sampled files |

**telemetry (one file per race, all drivers, three channels)**: 382 files; 26 columns in the union.

| Column | Type | Note |
|---|---|---|
| `index` | BIGINT |  |
| `Date` | TIMESTAMP_NS |  |
| `SessionTime` | BIGINT |  |
| `DriverAhead` | VARCHAR |  |
| `DistanceToDriverAhead` | DOUBLE |  |
| `Time` | BIGINT |  |
| `RPM` | DOUBLE |  |
| `speed_kph` | DOUBLE |  |
| `nGear` | BIGINT |  |
| `throttle_pct` | DOUBLE |  |
| `brake` | BOOLEAN |  |
| `DRS` | BIGINT |  |
| `Source` | VARCHAR |  |
| `distance_m` | DOUBLE |  |
| `RelativeDistance` | DOUBLE |  |
| `Status` | VARCHAR |  |
| `X` | DOUBLE |  |
| `Y` | DOUBLE |  |
| `Z` | DOUBLE |  |
| `driver_id` | VARCHAR |  |
| `lap_number` | DOUBLE |  |
| `race_id` | VARCHAR |  |
| `season` | BIGINT |  |
| `session_type` | VARCHAR | in 193 of 382 sampled files |
| `race` | VARCHAR |  |
| `session` | VARCHAR | in 193 of 382 sampled files |

**telemetry_full (per driver, car_data)**: 7735 files; 16 columns in the union.

| Column | Type | Note |
|---|---|---|
| `Date` | TIMESTAMP_NS |  |
| `RPM` | DOUBLE |  |
| `Speed` | DOUBLE |  |
| `nGear` | BIGINT |  |
| `Throttle` | DOUBLE |  |
| `Brake` | BOOLEAN |  |
| `DRS` | BIGINT |  |
| `Source` | VARCHAR |  |
| `Time` | BIGINT |  |
| `SessionTime` | BIGINT |  |
| `driver_id` | VARCHAR |  |
| `race_id` | VARCHAR |  |
| `season` | BIGINT |  |
| `driver` | BIGINT |  |
| `race` | VARCHAR |  |
| `session` | VARCHAR | in 204 of 408 sampled files |

**pos_data (per driver, position samples)**: 7715 files; 14 columns in the union.

| Column | Type | Note |
|---|---|---|
| `Date` | TIMESTAMP_NS |  |
| `Status` | VARCHAR |  |
| `X` | DOUBLE |  |
| `Y` | DOUBLE |  |
| `Z` | DOUBLE |  |
| `Source` | VARCHAR |  |
| `Time` | BIGINT |  |
| `SessionTime` | BIGINT |  |
| `driver_id` | VARCHAR |  |
| `race_id` | VARCHAR |  |
| `season` | BIGINT |  |
| `driver` | BIGINT |  |
| `race` | VARCHAR |  |
| `session` | VARCHAR | in 205 of 407 sampled files |

**weather**: 384 files; 15 columns in the union.

| Column | Type | Note |
|---|---|---|
| `index` | BIGINT |  |
| `Time` | BIGINT |  |
| `ambient_temp_c` | DOUBLE |  |
| `humidity_pct` | DOUBLE |  |
| `pressure_hpa` | DOUBLE |  |
| `rainfall_flag` | BOOLEAN |  |
| `track_temp_c` | DOUBLE |  |
| `wind_direction` | BIGINT |  |
| `wind_speed_ms` | DOUBLE |  |
| `race_id` | VARCHAR |  |
| `season` | BIGINT |  |
| `session_type` | VARCHAR | in 193 of 384 sampled files |
| `session_time_s` | DOUBLE |  |
| `race` | VARCHAR |  |
| `session` | VARCHAR | in 193 of 384 sampled files |

**results (race and quali)**: 384 files; 28 columns in the union.

| Column | Type | Note |
|---|---|---|
| `index` | VARCHAR |  |
| `DriverNumber` | VARCHAR |  |
| `BroadcastName` | VARCHAR |  |
| `Abbreviation` | VARCHAR |  |
| `DriverId` | VARCHAR |  |
| `TeamName` | VARCHAR |  |
| `TeamColor` | VARCHAR |  |
| `TeamId` | VARCHAR |  |
| `FirstName` | VARCHAR |  |
| `LastName` | VARCHAR |  |
| `FullName` | VARCHAR |  |
| `HeadshotUrl` | VARCHAR |  |
| `CountryCode` | VARCHAR |  |
| `Position` | DOUBLE |  |
| `ClassifiedPosition` | VARCHAR |  |
| `GridPosition` | DOUBLE |  |
| `Q1` | BIGINT |  |
| `Q2` | BIGINT |  |
| `Q3` | BIGINT |  |
| `Time` | BIGINT |  |
| `Status` | VARCHAR |  |
| `Points` | DOUBLE |  |
| `Laps` | DOUBLE |  |
| `race_id` | VARCHAR |  |
| `season` | BIGINT |  |
| `race` | VARCHAR |  |
| `session_type` | VARCHAR | in 193 of 384 sampled files |
| `session` | VARCHAR | in 193 of 384 sampled files |

**track_status**: 384 files; 10 columns in the union.

| Column | Type | Note |
|---|---|---|
| `index` | BIGINT |  |
| `Time` | BIGINT |  |
| `Status` | VARCHAR |  |
| `Message` | VARCHAR |  |
| `race_id` | VARCHAR |  |
| `season` | BIGINT |  |
| `session_type` | VARCHAR | in 193 of 384 sampled files |
| `session_time_s` | DOUBLE |  |
| `race` | VARCHAR |  |
| `session` | VARCHAR | in 193 of 384 sampled files |

**session_status**: 384 files; 9 columns in the union.

| Column | Type | Note |
|---|---|---|
| `index` | BIGINT |  |
| `Time` | BIGINT |  |
| `Status` | VARCHAR |  |
| `race_id` | VARCHAR |  |
| `season` | BIGINT |  |
| `session_type` | VARCHAR | in 193 of 384 sampled files |
| `session_time_s` | DOUBLE |  |
| `race` | VARCHAR |  |
| `session` | VARCHAR | in 193 of 384 sampled files |

**race_control**: 384 files; 17 columns in the union.

| Column | Type | Note |
|---|---|---|
| `index` | BIGINT |  |
| `Time` | TIMESTAMP_NS |  |
| `category` | VARCHAR |  |
| `message` | VARCHAR |  |
| `Status` | VARCHAR / INTEGER |  |
| `Flag` | VARCHAR |  |
| `Scope` | VARCHAR |  |
| `Sector` | DOUBLE / INTEGER |  |
| `RacingNumber` | VARCHAR / INTEGER |  |
| `Lap` | BIGINT / INTEGER / DOUBLE |  |
| `race_id` | VARCHAR |  |
| `season` | BIGINT |  |
| `session_time_corrected_s` | DOUBLE |  |
| `session_time_s` | DOUBLE |  |
| `race` | VARCHAR |  |
| `session_type` | VARCHAR | in 193 of 384 sampled files |
| `session` | VARCHAR | in 193 of 384 sampled files |

**circuit_info (corners)**: 378 files; 12 columns in the union.

| Column | Type | Note |
|---|---|---|
| `index` | BIGINT |  |
| `X` | DOUBLE / INTEGER |  |
| `Y` | DOUBLE / INTEGER |  |
| `Number` | BIGINT / INTEGER |  |
| `Letter` | VARCHAR / INTEGER |  |
| `Angle` | DOUBLE / INTEGER |  |
| `Distance` | DOUBLE |  |
| `race_id` | VARCHAR / INTEGER |  |
| `season` | BIGINT |  |
| `race` | VARCHAR |  |
| `session_type` | VARCHAR / INTEGER | in 191 of 378 sampled files |
| `session` | VARCHAR | in 191 of 378 sampled files |

**circuit_markers**: 376 files; 13 columns in the union.

| Column | Type | Note |
|---|---|---|
| `X` | DOUBLE |  |
| `Y` | DOUBLE |  |
| `Number` | BIGINT |  |
| `Letter` | VARCHAR |  |
| `Angle` | DOUBLE |  |
| `Distance` | DOUBLE |  |
| `marker_type` | VARCHAR |  |
| `rotation_deg` | DOUBLE |  |
| `race_id` | VARCHAR |  |
| `season` | BIGINT |  |
| `race` | VARCHAR |  |
| `session_type` | VARCHAR | in 190 of 376 sampled files |
| `session` | VARCHAR | in 190 of 376 sampled files |

**session_info**: 384 files; 30 columns in the union.

| Column | Type | Note |
|---|---|---|
| `Key` | BIGINT |  |
| `Type` | VARCHAR |  |
| `Name` | VARCHAR |  |
| `StartDate` | TIMESTAMP_NS |  |
| `EndDate` | TIMESTAMP_NS |  |
| `GmtOffset` | BIGINT |  |
| `Path` | VARCHAR |  |
| `Meeting_Key` | BIGINT |  |
| `Meeting_Name` | VARCHAR |  |
| `Meeting_Location` | VARCHAR |  |
| `Meeting_Country_Key` | BIGINT |  |
| `Meeting_Country_Code` | VARCHAR |  |
| `Meeting_Country_Name` | VARCHAR |  |
| `Meeting_Circuit_Key` | BIGINT |  |
| `Meeting_Circuit_ShortName` | VARCHAR |  |
| `ArchiveStatus_Status` | VARCHAR |  |
| `total_laps` | BIGINT |  |
| `session_start_time_s` | DOUBLE |  |
| `t0_date` | TIMESTAMP_NS / INTEGER |  |
| `session_date_utc` | TIMESTAMP_NS |  |
| `api_path` | VARCHAR |  |
| `f1_api_support` | INTEGER |  |
| `race_id` | VARCHAR |  |
| `season` | BIGINT |  |
| `session_type` | VARCHAR |  |
| `race` | VARCHAR |  |
| `session` | VARCHAR | in 193 of 384 sampled files |
| `Meeting_OfficialName` | VARCHAR | in 223 of 384 sampled files |
| `Meeting_Number` | BIGINT | in 99 of 384 sampled files |
| `SessionStatus` | VARCHAR | in 73 of 384 sampled files |

**schedule (per season)**: 9 files; 24 columns in the union.

| Column | Type | Note |
|---|---|---|
| `RoundNumber` | BIGINT |  |
| `Country` | VARCHAR |  |
| `Location` | VARCHAR |  |
| `OfficialEventName` | VARCHAR |  |
| `EventDate` | TIMESTAMP_NS |  |
| `EventName` | VARCHAR |  |
| `EventFormat` | VARCHAR |  |
| `Session1` | VARCHAR |  |
| `Session1Date` | TIMESTAMP WITH TIME ZONE |  |
| `Session1DateUtc` | TIMESTAMP_NS |  |
| `Session2` | VARCHAR |  |
| `Session2Date` | TIMESTAMP WITH TIME ZONE |  |
| `Session2DateUtc` | TIMESTAMP_NS |  |
| `Session3` | VARCHAR |  |
| `Session3Date` | TIMESTAMP WITH TIME ZONE |  |
| `Session3DateUtc` | TIMESTAMP_NS |  |
| `Session4` | VARCHAR |  |
| `Session4Date` | TIMESTAMP WITH TIME ZONE |  |
| `Session4DateUtc` | TIMESTAMP_NS |  |
| `Session5` | VARCHAR |  |
| `Session5Date` | TIMESTAMP WITH TIME ZONE |  |
| `Session5DateUtc` | TIMESTAMP_NS |  |
| `F1ApiSupport` | BOOLEAN |  |
| `season` | BIGINT |  |

**reference/jolpica/pit_stops (Jolpica)**: 192 files; 8 columns in the union.

| Column | Type | Note |
|---|---|---|
| `season` | BIGINT |  |
| `round` | BIGINT |  |
| `race_name` | VARCHAR |  |
| `driver_id` | VARCHAR |  |
| `stop` | BIGINT |  |
| `lap` | BIGINT |  |
| `time_of_day` | VARCHAR |  |
| `duration_s` | DOUBLE |  |

**reference/jolpica/driver_standings (Jolpica)**: 9 files; 14 columns in the union.

| Column | Type | Note |
|---|---|---|
| `season` | BIGINT |  |
| `round` | BIGINT |  |
| `position` | BIGINT |  |
| `position_text` | VARCHAR |  |
| `points` | DOUBLE |  |
| `wins` | BIGINT |  |
| `driver_id` | VARCHAR |  |
| `driver_number` | BIGINT |  |
| `driver_code` | VARCHAR |  |
| `given_name` | VARCHAR |  |
| `family_name` | VARCHAR |  |
| `constructor_id` | VARCHAR |  |
| `constructor_name` | VARCHAR |  |
| `constructor_ids` | VARCHAR |  |

**manifests (one row per ingestion attempt)**: 10 files; 29 columns in the union.

| Column | Type | Note |
|---|---|---|
| `run_id` | VARCHAR |  |
| `ingested_at_utc` | VARCHAR |  |
| `season` | BIGINT |  |
| `round_number` | BIGINT |  |
| `race_slug` | VARCHAR |  |
| `session_type` | VARCHAR |  |
| `status` | VARCHAR |  |
| `row_count` | BIGINT |  |
| `dq_passed` | BOOLEAN |  |
| `duplicate_lap_keys` | BIGINT |  |
| `schema_fingerprint` | VARCHAR |  |
| `thin_reasons` | VARCHAR |  |
| `known_gap_note` | VARCHAR |  |
| `telemetry_laps_attempted` | DOUBLE / INTEGER / BIGINT |  |
| `telemetry_laps_merged` | DOUBLE / INTEGER / BIGINT |  |
| `telemetry_coverage` | DOUBLE / INTEGER |  |
| `telemetry_car_drivers` | DOUBLE / INTEGER / BIGINT |  |
| `telemetry_pos_drivers` | DOUBLE / INTEGER / BIGINT |  |
| `telemetry_note` | VARCHAR |  |
| `telemetry_full_status` | VARCHAR |  |
| `telemetry_full_note` | VARCHAR |  |
| `circuit_info_status` | VARCHAR |  |
| `venue_note` | VARCHAR |  |
| `reason` | VARCHAR |  |
| `attempts` | BIGINT |  |
| `rate_limit_waits` | BIGINT |  |
| `rate_limit_wait_s` | DOUBLE |  |
| `session_info_status` | VARCHAR | in 3 of 10 sampled files |
| `fill_note` | VARCHAR | in 3 of 10 sampled files |

#### Part 2. dbt model output columns (from `schema.yml`)

Each line is a model and the column names it declares. Listed in name order within each layer. Layers follow the folder under `transform/models/`.

**staging** (19 models)

- `stg_circuit_info` (10): `corner_id`, `race_year`, `race_id`, `race_slug`, `corner_number`, `corner_letter`, `corner_x`, `corner_y`, `corner_angle_deg`, `corner_distance_m`
- `stg_events` (9): `stg_event_id`, `event_id`, `race_id`, `driver_id`, `event_type`, `event_severity`, `source`, `is_performance_impact`, `is_reliability_impact`
- `stg_jolpica_pit_stops` (9): `race_id`, `race_year`, `round_number`, `race_name`, `driver_ergast_id`, `stop_number`, `lap_number`, `time_of_day`, `duration_s`
- `stg_lap_tyre_qa` (14): `lap_id`, `stint_number`, `tyre_life`, `compound`, `stint_source`, `tyre_life_offset_laps`, `tyre_qa_status`, `n_unexplained_stint_changes`, `n_racing_stops`, `n_unmatched_racing_stops`, `is_unexplained_stint_change`, `bronze_stint_number`, `bronze_tyre_life`, `bronze_compound`
- `stg_laps` (35): `lap_id`, `race_year`, `circuit_key`, `race_id`, `driver_id`, `driver_number`, `constructor_id`, `lap_number`, `stint_number`, `tyre_life`, `is_fresh_tyre`, `is_personal_best`, `position`, `lap_time_s`, `lap_start_time_s`, `sector1_time_s`, `sector2_time_s`, `sector3_time_s`, `sector1_session_time_s`, `sector2_session_time_s`, `sector3_session_time_s`, `speed_i1_kph`, `speed_i2_kph`, `speed_fl_kph`, `speed_st_kph`, `track_status`, `is_pit_lap`, `is_deleted`, `is_accurate`, `is_fastf1_generated`, `compound`, `is_safety_car_lap`, `is_vsc_lap`, `is_red_flag_lap`, `is_valid_lap`
- `stg_laps_qualifying` (36): `lap_id`, `race_year`, `circuit_key`, `race_id`, `session_type`, `driver_id`, `driver_number`, `constructor_id`, `lap_number`, `stint_number`, `tyre_life`, `is_fresh_tyre`, `is_personal_best`, `position`, `lap_time_s`, `lap_start_time_s`, `sector1_time_s`, `sector2_time_s`, `sector3_time_s`, `sector1_session_time_s`, `sector2_session_time_s`, `sector3_session_time_s`, `speed_i1_kph`, `speed_i2_kph`, `speed_fl_kph`, `speed_st_kph`, `track_status`, `is_pit_lap`, `is_deleted`, `is_accurate`, `is_fastf1_generated`, `compound`, `is_safety_car_lap`, `is_vsc_lap`, `is_red_flag_lap`, `is_valid_lap`
- `stg_pits` (12): `lap_id`, `race_year`, `race_id`, `driver_id`, `pit_in_lap_number`, `pit_out_lap_number`, `stint_number`, `compound_in`, `compound_out`, `pit_in_time_s`, `pit_out_time_s`, `pit_duration_s`
- `stg_race_control` (7): `message_index`, `race_year`, `race_id`, `message_time_s`, `flag`, `driver_id`, `is_blue_flag_event`
- `stg_red_flags` (6): `red_flag_id`, `race_year`, `race_id`, `race_slug`, `session_time_s`, `track_message`
- `stg_red_flags_qualifying` (6): `red_flag_id`, `race_year`, `race_id`, `race_slug`, `session_time_s`, `track_message`
- `stg_results` (17): `result_id`, `race_year`, `race_id`, `race_slug`, `driver_id`, `driver_number`, `constructor_id`, `finish_position`, `classified_position`, `grid_position`, `points`, `time_or_gap_s`, `status`, `is_classified`, `is_dnf`, `is_disqualified`, `dnf_cause`
- `stg_results_qualifying` (14): `quali_result_id`, `race_year`, `race_id`, `race_slug`, `session_type`, `driver_id`, `driver_number`, `constructor_id`, `quali_position`, `q1_time_s`, `q2_time_s`, `q3_time_s`, `final_segment_reached`, `segment_source`
- `stg_sector_times` (12): `sector_id`, `lap_id`, `race_year`, `race_id`, `driver_id`, `lap_number`, `sector`, `sector_time_s`, `sector_time_missing`, `sector_session_time_s`, `speed_trap_kph`, `is_valid_lap`
- `stg_session_status_qualifying` (10): `session_status_id`, `race_year`, `race_id`, `race_slug`, `session_type`, `session_time_s`, `status`, `is_red_flag_stop`, `is_green_light`, `is_chequered_flag`
- `stg_telemetry` (16): `telemetry_id`, `race_year`, `race_id`, `driver_id`, `lap_number`, `distance_m`, `session_time_s`, `speed_kph`, `throttle_pct`, `brake_applied`, `rpm`, `n_gear`, `drs_active`, `drs_code`, `drs_state`, `source_channel`
- `stg_telemetry_position` (15): `lap_number`, `driver_id`, `race_id`, `race_year`, `session_time_s`, `relative_distance`, `relative_distance_source`, `relative_clamp`, `pos_x`, `pos_y`, `driver_ahead_number`, `distance_to_ahead_m`, `distance_m`, `drs_code`, `drs_state`
- `stg_track_status` (12): `track_status_id`, `race_year`, `race_id`, `race_slug`, `session_time_s`, `status_code`, `status_message`, `status_label`, `is_safety_car`, `is_vsc`, `is_red_flag`, `status_duration_s`
- `stg_tyre_allocations` (6): `race_year`, `circuit_key`, `compound_code`, `compound_label`, `allocated_sets_per_driver`, `source_url`
- `stg_weather` (20): `lap_id`, `race_year`, `race_id`, `driver_id`, `lap_number`, `weather_session_time_s`, `ambient_temp_c`, `track_temp_c`, `rainfall_flag`, `humidity_pct`, `rainfall_flag_bronze`, `field_wet_tyre_share`, `wet_signal_votes`, `wet_signal_available`, `weather_sample_age_s`, `weather_sample_stale`, `rain_signal_disagreement`, `wind_speed_ms`, `wind_direction`, `pressure_hpa`

**intermediate** (66 models)

- `int_cell_power_law_fit` (6): `cell_id`, `compound_hardness_rank`, `n_compound_labels`, `beta`, `r2_within`, `fit_eligible`
- `int_circuit_x_constructor_interaction` (2): `constructor_race_id`, `circuit_constructor_interaction_s`
- `int_compound_cliff_predicted` (4): `lap_id`, `compound_wear_s`, `compound_wear_gradient`, `expected_compound_pace_s`
- `int_constructor_car_fe` (5): `constructor_car_fe_id`, `race_year`, `race_id`, `constructor_id`, `car_fe_s`
- `int_constructor_car_fe_isolation` (13): `constructor_car_fe_isolation_id`, `race_year`, `race_id`, `constructor_id`, `era`, `n_laps`, `car_fe_raw_s`, `car_iso_s`, `car_term_source`, `race_components_n`, `connectivity_note`, `fit_method`, `fit_timestamp`
- `int_constructor_deg_sensitivity` (26): `deg_sensitivity_id`, `race_year`, `constructor_id`, `compound`, `deg_slope_s_per_lap`, `deg_slope_raw_s_per_lap`, `field_mean_slope_s_per_lap`, `deg_slope_se_s_per_lap`, `deg_slope_posterior_sd_s_per_lap`, `shrink_factor`, `tau_s_per_lap`, `n_laps`, `n_stints`, `is_low_sample`, `cliff_onset_shift_laps`, `cliff_onset_shift_se_laps`, `cliff_hinge_coef_s_per_lap`, `cliff_hinge_field_mean_s_per_lap`, `cliff_severity_used_s_per_lap`, `cliff_ref_depth_laps`, `cliff_hinge_tau_s_per_lap`, `n_post_cliff_laps`, `n_deep_cliff_laps`, `n_stints_cliff`, `is_low_sample_cliff`, `fit_timestamp`
- `int_constructor_structural_pace` (12): `constructor_race_id`, `race_year`, `race_id`, `constructor_id`, `constructor_structural_pace_s`, `constructor_structural_pace_se_s`, `constructor_structural_pace_ci_low_s`, `constructor_structural_pace_ci_high_s`, `panel_observations_n`, `clean_teammate_pair_laps_n`, `r_squared_within`, `fit_timestamp`
- `int_corner_drift_from_early_stint` (9): `corner_id`, `lap_id`, `stint_id`, `corner_name`, `valid_lap_in_stint`, `drift_in_baseline_window`, `braking_drift_s`, `mid_drift_s`, `exit_drift_s`
- `int_corner_lap_measured` (8): `race_id`, `driver_id`, `lap_number`, `corner_name`, `length_m`, `exclusion_reason`, `linked_corner_flag`, `linked_corner_reason`
- `int_corner_length_measured` (16): `race_id`, `corner_name`, `corner_length_m`, `corner_length_raw_m`, `n_laps_measured`, `n_laps_raw`, `n_excluded_stopped`, `n_excluded_near_stopped`, `n_excluded_misaligned_lap`, `n_excluded_misaligned_corner`, `length_iqr_m`, `linked_corner_share`, `throttle_past_next_share`, `brake_before_prev_share`, `linked_corner_cell_flag`, `null_reason`
- `int_corner_metrics` (9): `driver_id`, `lap_number`, `race_id`, `race_year`, `corner_name`, `track_id`, `braking_point_m`, `v_min_kph`, `throttle_point_m`
- `int_corner_skill_residuals` (11): `corner_id`, `lap_id`, `corner_name`, `braking_loss_s`, `mid_corner_residual_s`, `mid_corner_residual_raw_s`, `mid_corner_outlier_flag`, `exit_residual_s`, `corner_residual_total_s`, `field_corner_sample_n`, `corner_unmapped_flag`
- `int_dirty_air_tax_component` (7): `lap_id`, `dirty_air_intensity_lag1`, `dirty_air_tax_s`, `dirty_air_tax_se_s`, `tax_calibration_confidence`, `cumulative_dirty_air_tax_race_s`, `dirtiest_air_lap_in_race_flag`
- `int_driver_circuit_affinity` (14): `driver_circuit_id`, `driver_id`, `circuit_id`, `circuit_name`, `n_obs`, `seasons_observed_n`, `raw_affinity_s`, `shrunk_affinity_s`, `global_driver_mean_s`, `affinity_vs_driver_mean_s`, `shrunk_affinity_se_s`, `shrunk_affinity_ci_low_s`, `shrunk_affinity_ci_high_s`, `affinity_confidence`
- `int_driver_circuit_era_affinity` (14): `driver_circuit_era_id`, `driver_id`, `circuit_id`, `circuit_name`, `era_key`, `era_label`, `n_obs`, `seasons_observed_n`, `raw_affinity_s`, `shrunk_affinity_s`, `shrunk_affinity_se_s`, `shrunk_affinity_ci_low_s`, `shrunk_affinity_ci_high_s`, `affinity_confidence`
- `int_driver_isolation_lap_pace` (31): `lap_id`, `stint_id`, `race_year`, `race_id`, `driver_id`, `constructor_id`, `stint_number`, `lap_number`, `compound`, `age_in_stint`, `lap_in_stint`, `valid_lap_in_stint`, `laps_past_cliff`, `fuel_mass_kg`, `era`, `anomaly_class`, `air_state_dominant`, `is_dirty_air_lap`, `field_n`, `lap_time_s`, `compound_component_s`, `dirty_air_tax_s`, `x_s`, `y_s`, `tyre_offset_vs_field_s`, `tyre_phase`, `is_recovery`, `stint_phase`, `car_iso_s`, `car_term_source`, `pace_isolated_gain_s`
- `int_driver_isolation_lap_panel` (31): `lap_id`, `stint_id`, `race_year`, `race_id`, `driver_id`, `constructor_id`, `stint_number`, `lap_number`, `compound`, `age_in_stint`, `lap_in_stint`, `valid_lap_in_stint`, `laps_past_cliff`, `fuel_mass_kg`, `era`, `driver_era`, `anomaly_class`, `air_state_dominant`, `is_dirty_air_lap`, `field_n`, `lap_time_s`, `compound_component_s`, `dirty_air_tax_s`, `is_thin_cell_tax`, `x_s`, `field_median_x_s`, `y_s`, `tyre_offset_vs_field_s`, `tyre_phase`, `is_recovery`, `stint_phase`
- `int_driver_isolation_lap_values` (38): `lap_id`, `stint_id`, `race_year`, `race_id`, `driver_id`, `constructor_id`, `stint_number`, `lap_number`, `compound`, `age_in_stint`, `lap_in_stint`, `valid_lap_in_stint`, `laps_past_cliff`, `fuel_mass_kg`, `era`, `anomaly_class`, `air_state_dominant`, `is_dirty_air_lap`, `field_n`, `tyre_phase`, `is_recovery`, `stint_phase`, `lap_time_s`, `compound_component_s`, `dirty_air_tax_s`, `x_s`, `y_s`, `tyre_offset_vs_field_s`, `car_iso_s`, `car_term_source`, `pace_isolated_gain_s`, `pure_skill_gain_s`, `pure_season_offset_gain_s`, `pure_is_extrapolated`, `n_line_laps`, `line_ref_age_laps`, `season_sigma_w_s`, `season_neff_factor`
- `int_driver_isolation_stint_tyre` (21): `stint_id`, `race_year`, `race_id`, `driver_id`, `constructor_id`, `stint_number`, `compound`, `era`, `n_omega_laps`, `n_pace_laps`, `n_cliff_laps`, `n_line_laps`, `line_mean_pace_gain_s`, `line_mean_age_laps`, `line_ref_age_laps`, `line_age_sxx`, `line_slope_s_per_lap2`, `line_slope_se_s_per_lap2`, `season_sigma_w_s`, `season_rho1`, `season_neff_factor`
- `int_driver_race_paired_laps` (18): `race_year`, `race_id`, `constructor_id`, `driver_id`, `teammate_id`, `lap_number`, `paired_delta_s`, `own_tyre_component_s`, `teammate_tyre_component_s`, `tyre_component_diff_s`, `adjusted_paired_delta_s`, `tyre_adjustment_missing`, `own_compound`, `teammate_compound`, `own_tyre_life`, `teammate_tyre_life`, `pair_is_comparable`, `pair_exclusion_reason`
- `int_driver_race_skill_loro` (8): `driver_race_skill_id`, `driver_id`, `race_year`, `race_id`, `driver_skill_loro_s`, `driver_skill_field_s`, `clean_lap_count`, `paired_lap_count`
- `int_driver_season_ratings` (8): `driver_season_id`, `driver_id`, `season`, `n_races`, `raw_residual_mean_s`, `shrunk_residual_s`, `shrunk_residual_se_s`, `rating_confidence`
- `int_era_normalized_driver_rating` (13): `driver_season_id`, `driver_id`, `season`, `raw_residual_mean_s`, `shrunk_residual_s`, `era_adjusted_rating`, `era_adjusted_rating_se_s`, `era_adjusted_rating_ci_low_s`, `era_adjusted_rating_ci_high_s`, `rating_confidence`, `bridge_driver_anchor_flag`, `era_shift_global_s`, `low_anchor_sample_flag`
- `int_event_corrections` (5): `lap_id`, `race_year`, `race_id`, `driver_id`, `lap_number`
- `int_field_pace_curve` (9): `race_year`, `race_id`, `lap_number`, `field_pace_smoothed_s`, `low_sample_flag`, `is_neutralised_lap`, `is_restart_adjacent_lap`, `smoothing_window_first_lap`, `smoothing_window_last_lap`
- `int_lap_air_state` (5): `lap_id`, `dirty_air_share_lap`, `s2_gap_median_s`, `s2_drs_active`, `time_in_dirty_air_s`
- `int_lap_anomaly_flags` (6): `lap_id`, `rain_state`, `race_year`, `race_id`, `driver_id`, `lap_number`
- `int_lap_corner_drift` (16): `lap_id`, `corners_total_n`, `corners_drift_mapped_n`, `corner_drift_coverage`, `corner_braking_drift_n`, `corner_mid_drift_n`, `corner_exit_drift_n`, `corner_braking_drift_mean_s`, `corner_braking_drift_sd_s`, `corner_braking_drift_max_s`, `corner_mid_drift_mean_s`, `corner_mid_drift_sd_s`, `corner_mid_drift_max_s`, `corner_exit_drift_mean_s`, `corner_exit_drift_sd_s`, `corner_exit_drift_max_s`
- `int_lap_corner_inputs` (16): `lap_id`, `corners_total_n`, `corners_mapped_n`, `corner_input_coverage`, `corner_braking_n`, `corner_mid_n`, `corner_exit_n`, `corner_braking_loss_mean_s`, `corner_braking_loss_sd_s`, `corner_braking_loss_max_s`, `corner_mid_residual_mean_s`, `corner_mid_residual_sd_s`, `corner_mid_residual_max_s`, `corner_exit_residual_mean_s`, `corner_exit_residual_sd_s`, `corner_exit_residual_max_s`
- `int_lap_fuel_state` (7): `lap_id`, `fuel_mass_kg`, `weight_penalty_s`, `weight_corrected_lap_time`, `race_lap_count`, `initial_fuel_kg`, `fuel_consumption_rate_kg_per_lap`
- `int_lap_normalized_pace` (3): `lap_id`, `normalized_pace_s`, `dirty_air_penalty_s`
- `int_lap_physical_ahead` (20): `lap_id`, `race_id`, `season`, `driver_id`, `lap_number`, `validity_class`, `is_within_1s_of_car_ahead`, `gap_ahead_phys_s`, `gap_ahead_phys_median_s`, `gap_ahead_phys_min_m`, `gap_ahead_phys_min_driver_id`, `time_within_1s_phys_s`, `time_measured_s`, `is_neutralised_lap`, `is_lapped_lap`, `lapped_seconds_within_1s`, `lapped_time_measured_s`, `lapped_gap_phys_min_s`, `n_ahead_flips`, `zero_xy_guard_on`
- `int_lap_proximity` (9): `lap_id`, `proximity_bin_count`, `gap_ahead_min_s`, `share_lap_within_1s`, `share_lap_in_train`, `ahead_identity_stability`, `ff_ahead_identity_agreement`, `gap_ahead_min_driver_id`, `gap_ahead_min_crossing_s`
- `int_lap_rain_state` (7): `race_year`, `race_id`, `lap_number`, `track_temp_c`, `humidity_pct`, `rainfall_flag`, `rain_state`
- `int_lap_residual_decomposed` (14): `lap_id`, `valid_lap_in_stint`, `stint_length_valid`, `constructor_component_s`, `constructor_pace_is_filled`, `constructor_component_se_s`, `rubber_component_s`, `ambient_component_s`, `track_evolution_unavailable_reason`, `dirty_air_tax_s`, `driver_skill_residual_s`, `base_pace_status`, `base_eligible_lap_count`, `total_explained_s`
- `int_lap_residual_decomposed_qualifying` (6): `lap_id`, `quali_driver_skill_residual_s`, `quali_segment`, `base_track_pace_s`, `ratio_to_segment_best`, `track_unexplained_s`
- `int_lap_residual_stint_detrend` (2): `stint_id`, `drift_s_per_lap`
- `int_lap_telemetry_aggregates` (6): `lap_id`, `stint_id`, `pct_full_throttle`, `pct_drs_active`, `traction_wheelspin_proxy`, `lift_coast_share`
- `int_lap_thermal_proxy` (7): `lap_id`, `weight_corrected_lap_time`, `stint_baseline_pace`, `baseline_observations_n`, `push_residual`, `cumulative_push_load_surface`, `cumulative_push_load_bulk`
- `int_microsector_corner_class` (5): `race_microsector_id`, `race_id`, `microsector`, `lap_length_m`, `corner_class`
- `int_microsector_crossings` (4): `crossing_time_s`, `microsector`, `bracket_s`, `drs_state`
- `int_microsector_proximity` (12): `microsector_id`, `lap_id`, `race_id`, `driver_id`, `microsector`, `entry_time_s`, `timing_invalid_reason`, `invalid_reason`, `gap_band`, `drs_state_entry`, `drs_state_exit`, `drs_open`
- `int_physical_ahead_pair_race` (5): `race_id`, `follower_driver_id`, `leader_driver_id`, `seconds_within_1s`, `n_laps_within_1s`
- `int_physical_ahead_pairs` (11): `race_id`, `season`, `follower_driver_id`, `leader_driver_id`, `lap_number`, `seconds_within_1s`, `n_samples_within_1s`, `min_gap_s`, `median_gap_s`, `validity_class`, `zero_xy_guard_on`
- `int_physical_ahead_pairs_lapped` (12): `race_id`, `season`, `follower_driver_id`, `leader_driver_id`, `lap_number`, `pair_class`, `seconds_within_1s`, `n_samples_within_1s`, `min_gap_s`, `median_gap_s`, `validity_class`, `zero_xy_guard_on`
- `int_pit_loss_circuit` (5): `circuit_slug`, `circuit_id`, `n_stops`, `pit_loss_s_empirical`, `pit_loss_s_shrunk`
- `int_pit_strategy_cost_curve` (13): `stint_id`, `horizon_scope`, `horizon_laps`, `candidate_pit_lap_offset`, `laps_on_new_set`, `old_wear_cost_s`, `new_wear_cost_s`, `baseline_cost_s`, `sc_hazard_per_lap`, `sc_probability`, `pit_discount_factor`, `wear_cost_s`, `total_cost_s`
- `int_pit_strategy_value` (17): `stint_id`, `optimal_pit_lap`, `optimal_pit_lap_in_stint`, `actual_pit_lap`, `end_lap_number`, `overrun_laps`, `opportunity_cost_s`, `strategy_verdict`, `optimal_pit_lap_confidence`, `pit_lane_loss_s`, `pit_loss_source`, `pit_loss_imputed_flag`, `horizon_source`, `horizon_laps`, `optimal_pit_lap_race_in_stint`, `optimal_pit_lap_race`, `opportunity_cost_race_s`
- `int_power_law_lap` (11): `lap_id`, `stint_id`, `race_id`, `age_in_stint`, `compound_label`, `hardness_era`, `hardness_identity`, `compound_hardness_rank`, `y_s`, `track_temp_c`, `constructor_pace_s`
- `int_qualifying_decomposed` (6): `lap_id`, `quali_skill_residual_s`, `quali_vs_race_skill_delta_s`, `quali_skill_session_avg_s`, `quali_segments_contested_n`, `quali_segment`
- `int_qualifying_driver_summary` (11): `race_year`, `race_id`, `driver_id`, `quali_push_laps_n`, `quali_constructor_pace_mean_s`, `quali_constructor_pace_se_mean_s`, `quali_pace_delta_best_s`, `quali_ratio_to_segment_best_min`, `quali_top_segment`, `quali_skill_session_avg_s`, `quali_segments_contested_n`
- `int_qualifying_push_laps` (9): `lap_id`, `race_year`, `race_id`, `driver_id`, `quali_segment`, `segment_best_s`, `driver_segment_best_s`, `ratio_to_segment_best`, `is_push_lap`
- `int_qualifying_segments` (12): `quali_segment_id`, `race_year`, `race_id`, `quali_segment`, `segment_index`, `segment_start_s`, `segment_end_s`, `segment_span_s`, `stoppage_n`, `anchor_lap_n`, `window_start_s`, `window_end_s`
- `int_sc_hazard_history` (15): `circuit_slug`, `season`, `season_races_n`, `prior_seasons_n`, `prior_races_n`, `prior_racing_laps`, `prior_sc_onsets`, `prior_vsc_onsets`, `prior_any_onsets`, `sc_hazard_per_lap`, `vsc_hazard_per_lap`, `any_hazard_per_lap`, `sc_hazard_per_lap_shrunk`, `vsc_hazard_per_lap_shrunk`, `any_hazard_per_lap_shrunk`
- `int_sector_residual_decomposed` (8): `sector_id`, `lap_id`, `sector`, `sector_time_s`, `sector_pace_delta_s`, `sector_driver_skill_residual_s`, `sector_total_explained_s`, `dominant_component_class`
- `int_stint_end_regime` (17): `stint_id`, `race_year`, `race_id`, `driver_id`, `stint_number`, `end_lap_id`, `end_lap_number`, `end_lap_in_stint`, `is_censored_stint`, `end_regime`, `is_multi_regime_end`, `ended_on_pit_lap`, `was_running_at_flag`, `stint_end_cause`, `end_cause_confidence`, `is_stint_life_censored`, `reached_flag`
- `int_stint_geometry` (18): `stint_id`, `lap_id`, `lap_in_stint`, `valid_lap_in_stint`, `stint_length_actual`, `stint_length_valid`, `is_valid_lap`, `is_pit_lap`, `is_safety_car_lap`, `is_vsc_lap`, `is_red_flag_lap`, `stint_source`, `tyre_qa_status`, `age_in_stint`, `compound_code`, `race_year`, `race_id`, `driver_id`
- `int_stint_power_law_fit` (6): `stint_id`, `beta`, `r2`, `r2_linear`, `beta_at_grid_edge`, `fit_eligible`
- `int_synthetic_teammate` (4): `race_year`, `race_id`, `ego_driver_id`, `lap_number`
- `int_track_evolution` (9): `race_year`, `race_id`, `lap_number`, `rainfall_flag`, `rain_state`, `rubber_slope_raw_s_per_lap`, `rubber_slope_s_per_lap`, `rubber_fit_lap_count`, `rubber_status`
- `int_track_geometry` (7): `race_year`, `track_id`, `distance_bin`, `gradient_dz_ds`, `curvature_per_m`, `curvature_guard_reason`, `lateral_accel_proxy_ms2`
- `int_traffic_exposure_driver_race` (2): `share_time_close_behind`, `bunching_share`
- `int_traffic_exposure_race` (12): `race_id`, `quality_flag`, `is_low_measured_share`, `min_measured_share_floor`, `zero_xy_guard_on`, `share_laps_measured`, `share_laps_lapped`, `share_laps_overlapping`, `share_laps_unknown`, `share_laps_neutralised`, `share_time_close_behind`, `bunching_share`
- `int_tyre_surface_vs_bulk_decoupling` (5): `lap_id`, `surface_bulk_ratio`, `degradation_source`, `recovery_probability`, `thermal_attribution_s`
- `stg_physical_ahead_laps` (3): `race_id`, `driver_id`, `lap_number`
- `stg_physical_ahead_telemetry` (3): `race_id`, `driver_id`, `session_time_s`

**reference** (6 models)

- `dim_circuits` (12): `circuit_key`, `circuit_id`, `circuit_name`, `lap_length_km`, `corner_count`, `avg_lateral_g`, `fuel_consumption_rate_kg_per_lap`, `track_energy_index`, `abrasiveness_index`, `weight_penalty_factor`, `era_start_year`, `calibration_flag`
- `dim_compounds_season` (17): `circuit_key`, `compound_code`, `season`, `compound_grip_peak`, `compound_wear_gradient`, `compound_optimal_temp_low`, `compound_optimal_temp_high`, `compound_cliff_onset_laps`, `compound_cliff_severity`, `fit_date`, `data_window`, `fit_source`, `onset_source`, `gradient_source`, `severity_source`, `notes`, `is_measured`
- `dim_constructors` (3): `constructor_id`, `pu_family`, `constructor_lineage_id`
- `dim_corners` (13): `corner_key`, `race_year`, `race_id`, `track_id`, `circuit_id`, `corner_name`, `corner_number`, `corner_letter`, `apex_distance_m`, `start_distance_m`, `end_distance_m`, `geometry_race_id`, `geometry_source`
- `dim_driver_seasons` (7): `season`, `driver_code`, `driver_id`, `full_name`, `first_name`, `last_name`, `team_name`
- `dim_drivers` (4): `driver_id`, `driver_number`, `debut_year`, `career_races_in_dataset`

**marts** (24 models)

- `fct_cliff_prediction_features` (97): `lap_id`, `stint_id`, `race_year`, `race_id`, `circuit_key`, `driver_id`, `constructor_id`, `lap_number`, `lap_in_stint`, `age_in_stint`, `compound`, `compound_grip_peak`, `compound_wear_gradient`, `compound_optimal_temp_low`, `compound_optimal_temp_high`, `compound_cliff_onset_laps`, `compound_cliff_severity`, `push_residual`, `cumulative_push_load_surface`, `cumulative_push_load_bulk`, `baseline_observations_n`, `dirty_air_share_lap`, `dirty_air_thermal_load_surface`, `dirty_air_thermal_load_bulk`, `air_state_dominant`, `share_lap_within_1s`, `share_lap_within_2s`, `share_lap_in_train`, `share_lap_behind_within_1s`, `time_within_1s`, `gap_ahead_min_s`, `gap_ahead_median_s`, `ahead_identity_stability`, `n_distinct_cars_ahead_3s`, `corner_input_coverage`, `corner_braking_loss_mean_s`, `corner_braking_loss_sd_s`, `corner_braking_loss_max_s`, `corner_mid_residual_mean_s`, `corner_mid_residual_sd_s`, `corner_mid_residual_max_s`, `corner_exit_residual_mean_s`, `corner_exit_residual_sd_s`, `corner_exit_residual_max_s`, `corner_drift_coverage`, `corner_braking_drift_mean_s`, `corner_braking_drift_sd_s`, `corner_braking_drift_max_s`, `corner_mid_drift_mean_s`, `corner_mid_drift_sd_s`, `corner_mid_drift_max_s`, `corner_exit_drift_mean_s`, `corner_exit_drift_sd_s`, `corner_exit_drift_max_s`, `quali_push_laps_n`, `quali_constructor_pace_mean_s`, `quali_constructor_pace_se_mean_s`, `quali_pace_delta_best_s`, `quali_ratio_to_segment_best_min`, `quali_skill_session_avg_s`, `quali_segments_contested_n`, `circuit_sc_hazard_per_lap`, `circuit_vsc_hazard_per_lap`, `circuit_any_hazard_per_lap`, `circuit_hazard_prior_racing_laps`, `circuit_hazard_prior_seasons_n`, `expected_compound_pace_s`, `expected_degradation_rate_s_per_lap`, `cliff_onset_passed`, `laps_past_cliff`, `ambient_temp_delta`, `track_energy_index`, `circuit_abrasiveness_index`, `n_gear_changes`, `mean_rpm`, `max_rpm`, `pct_full_throttle`, `pct_drs_active`, `short_shift_index`, `mid_corner_speed_loss_kph`, `traction_wheelspin_proxy`, `throttle_trace_decay`, `braking_point_drift_m`, `lift_coast_share`, `fuel_mass_kg`, `event_flag_any`, `cliff_candidate_flag`, `anomaly_class`, `is_rain_lap`, `surface_bulk_ratio`, `survival_weight`, `next_lap_degradation_jump_detrended_s`, `next_lap_degradation_jump_s`, `next_3_lap_cumulative_jump_s`, `next_5_lap_cumulative_jump_s`, `laps_until_cliff_class`, `is_training_eligible`
- `fct_driver_isolation_lap` (60): `lap_id`, `stint_id`, `race_year`, `race_id`, `driver_id`, `constructor_id`, `stint_number`, `lap_number`, `compound`, `age_in_stint`, `valid_lap_in_stint`, `laps_past_cliff`, `era`, `tyre_phase`, `is_recovery`, `stint_phase`, `air_state_dominant`, `is_dirty_air_lap`, `field_n`, `lap_time_s`, `compound_component_s`, `dirty_air_tax_s`, `y_s`, `car_iso_s`, `car_term_source`, `tyre_offset_vs_field_s`, `lift_coast_share`, `lift_coast_excess_share`, `pace_isolated_gain_s`, `pure_skill_gain_s`, `pure_is_extrapolated`, `season_sigma_w_s`, `season_neff_factor`, `n_peers`, `n_teammate_peers`, `relative_pace_gain_s`, `relative_pace_raw_gain_s`, `identity_n_pair_laps`, `identity_relative_pace_gain_s`, `identity_pace_gap_gain_s`, `identity_car_advantage_gain_s`, `identity_traffic_advantage_gain_s`, `window_first_lap_number`, `window_n_laps`, `window_mixed_phase`, `window_n_pure_laps`, `window_n_pair_laps`, `window_n_relative_laps`, `pure_skill_5lap_gain_s`, `pure_skill_5lap_se_s`, `pure_skill_5lap_lambda`, `pure_skill_5lap_shrunk_gain_s`, `pure_skill_5lap_confidence_pct`, `pure_skill_5lap_trust_label`, `relative_pace_5lap_gain_s`, `relative_pace_5lap_se_s`, `relative_pace_5lap_lambda`, `relative_pace_5lap_shrunk_gain_s`, `relative_pace_5lap_confidence_pct`, `relative_pace_5lap_trust_label`
- `fct_driver_isolation_pair_lap` (27): `lap_id`, `peer_lap_id`, `race_year`, `race_id`, `lap_number`, `compound`, `driver_id`, `peer_driver_id`, `constructor_id`, `peer_constructor_id`, `is_teammate`, `stint_id`, `peer_stint_id`, `age_in_stint`, `peer_age_in_stint`, `stint_phase`, `peer_stint_phase`, `tyre_phase`, `peer_tyre_phase`, `is_dirty_air_lap`, `peer_is_dirty_air_lap`, `relative_pace_raw_gain_s`, `relative_pace_gain_s`, `pace_gap_gain_s`, `pure_gap_gain_s`, `car_advantage_gain_s`, `traffic_advantage_gain_s`
- `fct_driver_isolation_race` (37): `driver_race_id`, `race_year`, `race_id`, `driver_id`, `constructor_id`, `era`, `car_iso_s`, `car_term_source`, `n_stints`, `n_laps`, `pace_isolated_gain_s`, `n_pure_laps`, `n_pair_laps`, `n_relative_laps`, `n_teammate_pair_laps`, `relative_pace_raw_gain_s`, `identity_n_pair_laps`, `identity_relative_pace_gain_s`, `identity_pace_gap_gain_s`, `identity_car_advantage_gain_s`, `identity_traffic_advantage_gain_s`, `tyre_offset_vs_field_s`, `lift_coast_excess_share`, `dirty_air_lap_share`, `pure_skill_gain_s`, `pure_season_offset_gain_s`, `pure_skill_se_s`, `pure_skill_lambda`, `pure_skill_shrunk_gain_s`, `pure_skill_confidence_pct`, `pure_skill_trust_label`, `relative_pace_gain_s`, `relative_pace_se_s`, `relative_pace_lambda`, `relative_pace_shrunk_gain_s`, `relative_pace_confidence_pct`, `relative_pace_trust_label`
- `fct_driver_isolation_stint` (47): `stint_phase_id`, `stint_id`, `stint_phase`, `race_year`, `race_id`, `driver_id`, `constructor_id`, `stint_number`, `compound`, `era`, `n_laps`, `first_lap_number`, `last_lap_number`, `min_age_in_stint`, `max_age_in_stint`, `pace_isolated_gain_s`, `n_pure_laps`, `n_pair_laps`, `n_relative_laps`, `n_teammate_pair_laps`, `relative_pace_raw_gain_s`, `identity_n_pair_laps`, `identity_relative_pace_gain_s`, `identity_pace_gap_gain_s`, `identity_car_advantage_gain_s`, `identity_traffic_advantage_gain_s`, `n_line_laps`, `line_slope_s_per_lap2`, `tyre_offset_vs_field_s`, `lift_coast_excess_share`, `dirty_air_lap_share`, `stint_end_cause`, `is_censored_stint`, `strategy_verdict`, `opportunity_cost_s`, `pure_skill_gain_s`, `pure_skill_se_s`, `pure_skill_lambda`, `pure_skill_shrunk_gain_s`, `pure_skill_confidence_pct`, `pure_skill_trust_label`, `relative_pace_gain_s`, `relative_pace_se_s`, `relative_pace_lambda`, `relative_pace_shrunk_gain_s`, `relative_pace_confidence_pct`, `relative_pace_trust_label`
- `fct_driver_skill_features` (23): `driver_race_id`, `driver_id`, `race_year`, `race_id`, `constructor_id`, `circuit_key`, `pu_family`, `driver_debut_year`, `driver_residual_mean_s`, `driver_residual_stddev_s`, `driver_residual_median_s`, `clean_lap_count`, `driver_skill_proxy_mean_s`, `pair_quality_weight_mean`, `teammate_available_flag`, `strategic_divergence_share`, `constructor_power_pace_index_final`, `constructor_index_confidence_final`, `race_wet_flag`, `circuit_energy_index`, `circuit_abrasiveness_index`, `total_race_laps`, `ml_eligible_lap_share`
- `fct_ghost_car_pace` (26): `ghost_id`, `predicted_lap_time_s`, `actual_lap_time_s`, `predicted_residual_pace_s`, `actual_residual_pace_s`, `delta_vs_actual_lap_s`, `deg_interaction_s`, `host_deg_slope_s_per_lap`, `ego_deg_slope_s_per_lap`, `host_constructor_pace_is_prior`, `circuit_interaction_is_prior`, `host_deg_slope_is_prior`, `ego_deg_slope_is_prior`, `cliff_params_is_prior`, `compound_cliff_severity`, `cliff_interaction_s`, `host_cliff_shift_laps`, `ego_cliff_shift_laps`, `recombination_confidence`, `host_constructor_pace_se_s`, `host_deg_slope_sd_s_per_lap`, `ego_deg_slope_sd_s_per_lap`, `host_cliff_shift_se_laps`, `ego_cliff_shift_se_laps`, `host_cliff_active`, `ego_cliff_active`
- `fct_ghost_race_finish` (19): `ghost_race_id`, `is_self_scenario`, `predicted_finish_position`, `actual_finish_position`, `actual_is_dnf`, `actual_dnf_cause`, `finish_from_results`, `delta_vs_actual_position`, `predicted_mean_lap_s`, `predicted_mean_residual_pace_s`, `actual_mean_residual_pace_s`, `n_laps_prior_filled`, `lap_coverage`, `is_short_run`, `avg_recombination_confidence`, `predicted_mean_lap_se_s`, `p_beats_next`, `finish_pos_se`, `finish_pos_se_unavailable_reason`
- `fct_lap_residuals` (23): `lap_id`, `race_year`, `race_id`, `driver_id`, `constructor_id`, `lap_number`, `lap_time_s`, `compound`, `fuel_component_s`, `compound_component_s`, `rubber_component_s`, `ambient_component_s`, `constructor_component_s`, `constructor_pace_is_filled`, `dirty_air_tax_s`, `dirty_air_tax_se_s`, `driver_skill_residual_s`, `base_track_pace_s`, `pace_delta_s`, `base_pace_status`, `base_eligible_lap_count`, `ml_eligible`, `correction_weight`
- `fct_pit_stop_crosscheck` (2): `crosscheck_id`, `crosscheck_status`
- `fct_power_law_training` (11): `cell_id`, `n_laps`, `compound_hardness_rank`, `era_code`, `track_energy_index`, `circuit_abrasiveness_index`, `stint_start_fuel_kg`, `dirty_air_share`, `constructor_pace_s`, `curve_incr_20_s`, `beta`
- `fct_speed_traps` (3): `driver_session_id`, `n_valid_laps`, `n_st_missing_all_laps`
- `fct_speed_traps_season` (1): `season_entity_id`
- `fct_stint_features` (28): `stint_id`, `driver_id`, `race_id`, `race_year`, `stint_length_laps`, `compound`, `starting_tyre_age_laps`, `cumulative_thermal_load_end`, `cumulative_dirty_air_tax_s`, `n_dirty_air_measured_laps`, `dirty_air_unavailable_reason`, `cliff_lap_in_stint`, `tyre_management_score`, `end_of_stint_pace_falloff_s_per_lap`, `short_stint_flag`, `pit_decision_class`, `is_censored_stint`, `end_regime`, `stint_end_cause`, `end_cause_confidence`, `is_stint_life_censored`, `reached_flag`, `is_fresh_tyre_raw`, `clean_laps_to_cut`, `slope_to_cut_s_per_lap`, `mean_clean_pace_s`, `cut_reason`, `slope_reliable`
- `fct_telemetry_deltas` (9): `race_id`, `driver_a`, `driver_b`, `corner_name`, `track_id`, `lap_number`, `braking_point_delta_m`, `v_min_delta_kph`, `throttle_point_delta_m`
- `fct_track_limits` (3): `deleted_lap_id`, `deleted_reason`, `turn_number`
- `fct_track_limits_driver_session` (3): `driver_session_id`, `n_laps_run`, `deleted_unavailable_reason`
- `mart_build_provenance` (15): `label_version`, `label_sealed_on`, `theta_air_label_value`, `theta_air_fit_season_max`, `dirty_air_method`, `era_boundary`, `holdout_season`, `data_season_min`, `data_season_max`, `n_races`, `n_races_scheduled`, `model_version`, `dbt_invocation_id`, `built_at`, `dbt_version`
- `mart_corner_skill_driver` (18): `race_year`, `driver_id`, `constructor_id`, `constructors_driven`, `braking_skill_s`, `mid_corner_skill_s`, `exit_skill_s`, `braking_skill_se_s`, `mid_corner_skill_se_s`, `exit_skill_se_s`, `braking_skill_z`, `mid_corner_skill_z`, `exit_skill_z`, `corner_skill_index`, `braking_cells_n`, `mid_cells_n`, `exit_cells_n`, `mapped_corners`
- `mart_degradation_history_envelope` (13): `circuit_id`, `circuit_name`, `era`, `compound`, `lap_in_stint`, `n_observations`, `ref_green_pace_s`, `obs_fuel_removed_pace_p10_s`, `obs_fuel_removed_pace_p50_s`, `obs_fuel_removed_pace_p90_s`, `obs_deg_from_fresh_p10_s`, `obs_deg_from_fresh_p50_s`, `obs_deg_from_fresh_p90_s`
- `mart_driver_season_summary` (29): `driver_id`, `race_year`, `rating_s`, `teammate_gap_rank`, `n_drivers`, `teammate_gap_percentile`, `ci_low`, `ci_high`, `n_races`, `teammate_id`, `teammate_gap_s`, `constructor_id`, `constructor_rank`, `constructor_measured_laps_n`, `constructor_filled_share`, `constructor_rank_status`, `mean_fuel_component_s`, `mean_compound_component_s`, `mean_constructor_component_s`, `mean_dirty_air_tax_s`, `n_dirty_air_measured_laps`, `dirty_air_unavailable_reason`, `n_races_unrated`, `rating_se_s`, `rating_confidence`, `total_clean_laps_n`, `bridge_driver_anchor_flag`, `low_anchor_sample_flag`, `rank_separated_from_next`
- `mart_metric_benchmark` (9): `metric_name`, `race_year`, `p05`, `p50`, `p95`, `mean`, `sd`, `unit`, `sample_size`
- `mart_race_coverage` (16): `race_id`, `race_year`, `circuit_id`, `n_bronze_lap_rows`, `n_lap_rows`, `n_ml_eligible_laps`, `base_measured_share`, `residual_measured_share`, `rain_lap_share`, `air_measured_share`, `bronze_tyre_life_share`, `tyre_qa_status`, `has_telemetry`, `n_rated_drivers`, `has_rating`, `coverage_reason`
- `mart_race_driver_summary` (30): `driver_id`, `race_id`, `race_year`, `circuit_id`, `rating_s`, `n_drivers`, `ci_low`, `ci_high`, `n_clean_laps`, `teammate_id`, `teammate_gap_s`, `constructor_id`, `constructor_rank`, `constructor_measured_laps_n`, `constructor_filled_share`, `constructor_rank_status`, `mean_fuel_component_s`, `mean_compound_component_s`, `mean_constructor_component_s`, `mean_dirty_air_tax_s`, `avg_lap_time_s`, `laps_completed`, `positions_gained`, `has_dnf`, `paired_lap_count`, `rating_trust_label`, `ci_unavailable_reason`, `residual_unavailable_reason`, `n_dirty_air_measured_laps`, `dirty_air_unavailable_reason`

> Note: `int_constructor_structural_pace_qualifying` has a SQL file but no entry in any schema YAML, so it has no column list above.

---

## B. Lineage by feature

Notation: `->` means "is read by". Seeds are in brackets. Paths are given once at first use; every model lives under `transform/models/<layer>/<name>.sql` (layer: staging, intermediate, marts, reference).

### B1. Shared spine (almost everything below passes through these)

```
bronze raw_laps [+ seed_manual_lap_exceptions] -> stg_laps
bronze raw_laps -> stg_pits -> (with stg_laps) stg_lap_tyre_qa
bronze raw_results -> stg_results -> stg_race_control
[tyre_allocations] -> stg_tyre_allocations
stg_laps + stg_lap_tyre_qa + stg_tyre_allocations + stg_race_control + stg_results + [race_to_track]
   -> int_stint_geometry        (one row per lap with its stint, tyre age, compound, flag laps)
int_stint_geometry + dim_circuits ([circuit_reference]) + [race_scheduled_laps] + [race_to_track] + stg_laps
   -> int_lap_fuel_state        (fuel mass per lap)
int_stint_geometry + dim_compounds_season ([compound_cliff_params]) + stg_weather + [race_to_track]
   -> int_compound_cliff_predicted   (expected tyre pace, wear and cliff per lap)
int_compound_cliff_predicted + int_lap_fuel_state + int_lap_air_state + int_stint_geometry
   -> int_field_pace_curve -> int_track_evolution (rain state from int_lap_rain_state)
stg_laps + stg_weather + [race_to_track]
   -> int_lap_rain_state   (one row per lap: DRY, WET or NO_WEATHER; does not read the pace curve)
stg_laps + [seed_manual_lap_exceptions] -> int_event_corrections   (weights for restart, outlier laps)
... + int_constructor_structural_pace + int_dirty_air_tax_component
   -> int_lap_residual_decomposed   (the lap residual, "driver skill" signal; 8 int inputs; also reads int_track_evolution and int_lap_rain_state, and publishes base_pace_status = MEASURED / THIN_CELL / NO_CELL)
```
Notes: `int_lap_air_state` reads bronze `raw_telemetry` directly, not `stg_telemetry`. `dim_compounds_season` is built from the seed [compound_cliff_params.csv](../../../transform/seeds/compound_cliff_params.csv), which is written by [fit_compound_cliff.py](../../../transform/tasks/coefficients/fit_compound_cliff.py).

### B2. ML features (the contract in [ml/src/schema.py](../../../ml/src/schema.py))

All 39 feature columns come from the one mart [fct_cliff_prediction_features](../../../transform/models/marts/fct_cliff_prediction_features.sql). The degradation and stint-life models use 32 (qualifying group masked); the cliff classifier uses all 39. The chain per group:

| Group (features) | Chain to the mart |
|---|---|
| **stint_position**: `lap_number`, `lap_in_stint`, `age_in_stint`, `fuel_mass_kg` | B1 spine -> `int_lap_residual_decomposed` (carries stint fields and fuel) -> mart. Fuel: `int_lap_fuel_state`. |
| **compound** (7): `compound`, `compound_grip_peak`, `compound_wear_gradient`, `compound_optimal_temp_low/high`, `compound_cliff_onset_laps`, `compound_cliff_severity` | [compound_cliff_params] -> `dim_compounds_season` -> mart |
| **cliff_prior** (4): `expected_compound_pace_s`, `expected_degradation_rate_s_per_lap`, `cliff_onset_passed`, `laps_past_cliff` | `dim_compounds_season` + `int_stint_geometry` + `stg_weather` -> `int_compound_cliff_predicted` -> mart |
| **thermal** (4): `push_residual`, `cumulative_push_load_surface/bulk`, `surface_bulk_ratio` | `int_lap_fuel_state` + `int_stint_geometry` + `stg_laps` -> `int_lap_thermal_proxy` -> mart (the ratio is finished in the mart using the two weight-sum vars in [dbt_project.yml](../../../transform/dbt_project.yml)) |
| **dirty_air** (4): `dirty_air_share_lap`, `dirty_air_thermal_load_surface/bulk`, `air_state_dominant` | bronze `raw_telemetry` + `stg_laps` + `int_stint_geometry` -> `int_lap_air_state` -> mart |
| **proximity** (9): `share_lap_within_1s/2s`, `share_lap_in_train`, `share_lap_behind_within_1s`, `time_within_1s`, `gap_ahead_min_s`, `gap_ahead_median_s`, `ahead_identity_stability`, `n_distinct_cars_ahead_3s` | `stg_telemetry_position` + `stg_pits` + `stg_results` + `int_stint_geometry` -> `int_lap_proximity` -> mart |
| **qualifying** (7): `quali_push_laps_n`, `quali_constructor_pace_mean_s`, `quali_constructor_pace_se_mean_s`, `quali_pace_delta_best_s`, `quali_ratio_to_segment_best_min`, `quali_skill_session_avg_s`, `quali_segments_contested_n` | bronze qualifying files -> `stg_laps_qualifying`, `stg_results_qualifying`, `stg_session_status_qualifying`, `stg_red_flags_qualifying` -> `int_qualifying_segments` -> `int_qualifying_push_laps` -> (`int_constructor_structural_pace_qualifying`, `int_lap_residual_decomposed_qualifying`) -> `int_qualifying_decomposed` (also reads `int_lap_residual_decomposed`) -> `int_qualifying_driver_summary` -> mart |

Targets and gates (not features, but they decide which rows train):
- **5-lap degradation target** `next_5_lap_cumulative_jump_s` and **cliff class** `laps_until_cliff_class`: built in the mart from `int_lap_residual_decomposed` residuals and the per-stint drift from [int_lap_residual_stint_detrend](../../../transform/models/intermediate/int_lap_residual_stint_detrend.sql).
- **Stint-life target** `remaining_stint_life_laps` and its censoring flag: [fct_stint_features](../../../transform/models/marts/fct_stint_features.sql) <- `int_stint_end_regime` (<- `int_stint_geometry`, `stg_results`). Joined in [features.py](../../../ml/src/features.py).
- **Training eligibility** (`is_training_eligible`, on the cliff mart): `int_lap_anomaly_flags` (anomaly class), `int_event_corrections` (restart, weight), `int_lap_residual_decomposed`, and `base_pace_status = 'MEASURED'` (THIN_CELL and NO_CELL laps are excluded). WET laps are excluded through the anomaly class; NO_WEATHER laps stay trainable. On the 2018–2025 scratch build the training population went from 124,370 to 120,441 laps (3,575 of the drop in 2018–2024). `fct_lap_residuals.ml_eligible` is analytical and was not changed (see F).
- **Circuit hazard columns** (`circuit_sc_hazard_per_lap`, `circuit_vsc_hazard_per_lap`, `circuit_any_hazard_per_lap`, prior racing laps and prior seasons) in [fct_cliff_prediction_features](../../../transform/models/marts/fct_cliff_prediction_features.sql): `int_sc_hazard_history` (<- `stg_laps`, `stg_track_status`), joined on (circuit_slug, season). Not in the `ml/src/schema.py` feature list, so the model does not see them.
- **Survival weight** (`survival_weight` on the cliff mart): NOT from `int_sc_hazard_history`. It is `1 / survival_prob`, clamped to [0.25, 4.0], from a stint survival CTE in the same mart. Corrected 2026-11-23; the earlier line here was wrong.

In the mart but not in the shipped contract (dropped by ablation, per the long comment in schema.py): `int_lap_telemetry_aggregates` (powertrain and telemetry-cliff groups), `int_lap_corner_inputs`, `int_lap_corner_drift` (<- `int_corner_drift_from_early_stint` <- `int_corner_skill_residuals`). They still build and still cost build time.

Other ML code:
- **Power-law model** ([powerlaw.py](../../../ml/src/powerlaw.py), [powerlaw_fit.py](../../../ml/src/powerlaw_fit.py)): `int_power_law_lap` (<- `int_lap_residual_decomposed`, `int_stint_geometry`, `dim_circuits`, [compound_hardness_scale]) -> `int_cell_power_law_fit` -> `fct_power_law_training` (also reads `fct_cliff_prediction_features` and `int_lap_fuel_state`). `powerlaw_fit.py` also reads `int_power_law_lap` directly and treats `int_stint_power_law_fit` as a parity reference.
- **Flag chance** ([flag_chance.py](../../../ml/src/flag_chance.py)): `int_stint_geometry`, `fct_stint_features`, the ML mart.
- **Predictions parquet** -> app model pages (not a dbt model).

### B3. App pages

"Mart" in the chain below means the table the app SQL actually reads. Where I name a feature folder, the code is in `app/src/features/<folder>`. Core chain is always B1 first.

| App feature (folder) | Table read | Chain behind it (beyond B1) |
|---|---|---|
| lap-waterfall, race-lost, constructor-team-averages, pit-strategy (laps), race-control (lap table), ghost-race-standings | `fct_lap_residuals` | `int_lap_residual_decomposed` + `dim_constructors` + `dim_drivers` |
| race-control | `int_sc_hazard_history` (joined through `race_to_track.track_id`, season filter in the page query), `race_caution_timeline` (derived in `export_app_data.py` from `int_stint_geometry`, not from `stg_laps`) | `stg_laps` + `stg_track_status` (hazard only); `int_stint_geometry` (timeline) |
| field-pace-curve | `int_field_pace_curve` | B1 |
| track-evolution | `int_track_evolution` | `int_field_pace_curve` + `int_lap_rain_state` (rain state from `stg_weather`) |
| dirty-air-cost | `int_dirty_air_tax_component`, `fct_cliff_prediction_features` | `int_lap_air_state`, `int_compound_cliff_predicted`, `int_field_pace_curve`, `int_track_evolution`, `int_event_corrections`, `int_lap_fuel_state` |
| dirty-air-lap-map | `int_lap_air_state`, `fct_cliff_prediction_features` | `int_lap_air_state`; proximity group via `int_lap_proximity` |
| driver-workload | `fct_cliff_prediction_features` | `push_residual` via `int_lap_thermal_proxy` |
| tyre-cliff-survival, stint-degradation-timeline | `fct_cliff_prediction_features`, `dim_compounds_season`, `dim_circuits` | cliff and compound columns; default cells now shown as "estimate, no data for this track" via [cliffEstimate.ts](../../../app/src/features/shared/cliffEstimate.ts) |
| degradation-simulator | `mart_degradation_history_envelope`, `fct_power_law_training`, `fct_cliff_prediction_features`, `int_constructor_structural_pace`, `dim_compounds_season` | envelope <- `int_lap_residual_decomposed`, `dim_circuits`, external `fits.degradation_isotonic` parquet |
| blind-test-scoreboard, model-metrics, ml routes | `mart_degradation_predictions` (ML output), `fct_cliff_prediction_features`, `fct_stint_features` | ML chain in B2 |
| pit-strategy | `int_pit_strategy_value`, `fct_stint_features`, `fct_lap_residuals`, `int_stint_end_regime` (name appears in a code comment only), `int_lap_air_state` | `int_pit_strategy_value` <- `int_pit_strategy_cost_curve`, `int_pit_loss_circuit`, `int_stint_end_regime`, `int_compound_cliff_predicted`, `int_lap_air_state`, `stg_pits`, `stg_lap_tyre_qa`, [circuit_reference] |
| tyre-recovery-forecast | `int_tyre_surface_vs_bulk_decoupling` | `int_lap_residual_decomposed` + `int_lap_thermal_proxy` |
| constructor-structural-pace, party-mode | `int_constructor_structural_pace`, `int_constructor_structural_pace_qualifying` | `int_event_corrections`, `int_field_pace_curve`, `int_lap_fuel_state`, `int_track_evolution`; quali side <- `int_qualifying_push_laps` |
| constructor-circuit-interaction | `int_circuit_x_constructor_interaction` | `int_constructor_structural_pace`, [circuit_reference] |
| era-ratings-timeline, era-translator, hidden-performance (rating part) | `int_era_normalized_driver_rating`, `int_driver_season_ratings` | `int_driver_race_skill_loro` <- `int_driver_race_paired_laps` + `int_constructor_car_fe` + B1 corrections/fuel/pace/evolution |
| driver-circuit-affinity | `int_driver_circuit_affinity` | `int_driver_race_skill_loro`, [circuit_reference] |
| ghost-race-standings, hidden-performance | `int_driver_circuit_era_affinity`, `int_driver_race_skill_loro`, `fct_ghost_race_finish` | as above |
| counterfactual-championship, hidden-performance | `fct_ghost_race_finish` | `fct_ghost_car_pace` <- `int_lap_residual_decomposed`, `int_constructor_structural_pace`, `int_circuit_x_constructor_interaction`, `int_constructor_deg_sensitivity` (<- `int_compound_cliff_predicted`), `int_compound_cliff_predicted`, `stg_laps`, `stg_results` |
| driver-consistency, wet-race-specialist | `fct_driver_skill_features` | `int_lap_residual_decomposed`, `int_constructor_structural_pace`, `int_lap_anomaly_flags`, `int_synthetic_teammate`, `dim_*` |
| synthetic-teammate | `int_synthetic_teammate` | `int_compound_cliff_predicted`, `int_lap_fuel_state`, B1 |
| quali-vs-race-skill | `int_qualifying_decomposed` | B2 qualifying chain + `int_lap_residual_decomposed` |
| corner-phase-skill | `mart_corner_skill_driver` | `int_corner_skill_residuals` <- `int_corner_metrics`, `int_corner_lap_measured`, `int_corner_length_measured` (<- `dim_corners`, `stg_telemetry`, `stg_laps`), `stg_sector_times`, `int_stint_geometry` |
| sector-decomposition | `int_sector_residual_decomposed` | `int_lap_residual_decomposed`, `int_lap_air_state`, `stg_sector_times`, `stg_lap_tyre_qa` |
| data-quality-audit | `int_lap_anomaly_flags`, `mart_race_coverage` | `int_lap_residual_decomposed` -> flags; coverage <- `int_driver_race_skill_loro`, `stg_lap_tyre_qa`, `int_lap_air_state` |
| query-lab | `fct_driver_skill_features`, `fct_ghost_race_finish`, `fct_stint_features`, `mart_corner_skill_driver`, `dim_circuits` | as above |
| assistant cards | `mart_race_driver_summary`, `mart_driver_season_summary`, `mart_race_coverage`, `mart_metric_benchmark`, `mart_build_provenance`, `fct_driver_isolation_race/stint`, `int_driver_isolation_lap_panel` (held), `stg_results`, `stg_pits`, plus most of the tables above | summary marts <- `fct_lap_residuals`, `int_dirty_air_tax_component`, `int_driver_race_paired_laps`, `int_driver_race_skill_loro`, `int_era_normalized_driver_rating`, `stg_results` |

Not exported or comment-only in the app (checked by grep): `int_lap_proximity` and `int_lap_residual_decomposed` appear only in comments or docs text, not in a live query. Routes such as `drivers/dna-clusters`, `deep-dives/telemetry-fingerprint`, `ghost-car/standings`, `ghost-car/lap-chart` are stubs that name `stg_telemetry` or `fct_ghost_car_pace` in a header comment.

### B4. Built but with no reader (checked by grep over app, ml, scripts and the dbt graph)

`stg_events`, `stg_red_flags` (new), `dim_driver_seasons`, `int_lap_normalized_pace` (a deliberate leaf), `int_track_geometry`, `int_microsector_crossings` -> `int_microsector_proximity`, `int_microsector_corner_class`, the physical-ahead chain (`stg_physical_ahead_laps/telemetry` -> `int_lap_physical_ahead` -> `int_physical_ahead_pairs`, `_pairs_lapped`, `_pair_race`, `int_traffic_exposure_driver_race` -> `int_traffic_exposure_race`), and the five `new_data` marts. `fct_telemetry_deltas`, `fct_driver_isolation_lap/pair_lap` and `fct_power_law_training` have no app reader but have an ML or assistant reader or feed other models. `fct_telemetry_deltas` is handled outside the main export list (the export script says it is derived inline); I did not trace it.

---

## C. Robustness signals by component

No ordering is given here. Each bullet lists the evidence for one component: what it reads from, what fills or clamps it, what its tests cover, what is open, and who reads it. Use these to judge how risky a change is.

Before changing a model, check in this order: (1) its downstream readers in B1 (shared spine) and B3 (app pages) and its ML group in B2, since a change spreads along those edges; (2) any zero, constant or clamp fill it feeds, listed in D, because a fill that looks like data is easy to misread; (3) whether a flag column already marks the fill, and whether the consumer reads that flag; (4) the tests listed below and whether they already fail on baseline, so a new failure is not mistaken for an old one. A component with many upstream layers, zero or constant fills, few logic tests, or open failing tests needs more checking before it changes. Test counts are singular tests that call ref() on the model, so they are a rough guide only. The signals come from reading the code, not from measurement.


- **Staging reads** (`stg_laps` 16 tests, `stg_weather` 9, `stg_telemetry*`, `stg_circuit_info`, `stg_tyre_allocations`, `stg_race_control`, `stg_track_status`). One step from raw, little logic. Open items: `stg_results` misses about 69 classified retirements (DNF flag), `stg_lap_tyre_qa` has stint 0 on 3 driver-races (accepted as DQ-01), and several relationships tests fail on 2026 rows missing from `race_to_track`.
- **`int_stint_geometry`** (20 tests). The most tested model. Five staging inputs, so a bad stint here spreads to about 63 models. Open: `assert_stint_geometry_2018_compound_code_null` fails (1 row on the scratch build).
- **Power-law chain** (`int_power_law_lap` -> `int_cell_power_law_fit` -> `fct_power_law_training`). It is built to avoid the seed-derived cliff chain, and tests pin that (`assert_power_law_no_seed_columns`, `assert_power_law_fit_bounds`). It restricts fits to 2018 to 2024 through a var. It still sits on `int_lap_residual_decomposed`.
- **`int_sc_hazard_history`** (race-control page and the ML cliff mart's `circuit_*_hazard` columns; not the survival weight, see B2). Reads only `stg_laps` and `stg_track_status`. Schema tests plus three singular tests (no-future-leakage, probability bounds, flag partition in `stg_laps`). Season-lagged, so 2018 rates are NULL by design (documented in the model header and schema). Verified in section F. Open: a race with laps but no track-status timeline is silently dropped, and nothing tests for it.
- **Lap residual identity** (`int_lap_residual_decomposed` -> `fct_lap_residuals`, used by waterfall, race-lost, team averages). 18 tests including the exact-sum identity (`assert_lap_7term_identity`, `assert_residual_decomposition_identity`). Weak points: eight inputs, constructor term filled with 0.0 where no constructor row exists (now flagged by `constructor_pace_is_filled`), dirty-air tax filled with 0.0 where no row exists. The flagged fill is not excluded in `mart_race_driver_summary` / `mart_driver_season_summary` constructor ranks (they average `constructor_component_s` directly). The residual also publishes `base_pace_status` (MEASURED, THIN_CELL, NO_CELL) and `base_eligible_lap_count`. `total_explained_s` stays numeric on non-MEASURED laps and is documented as not fully measured there.
- **Stint-life labels** (`int_stint_end_regime` -> `fct_stint_features`). 4 and 3 tests, including censoring partition and the falloff-slope test that pins the old unit bug fix. Dirty-air fields are now NULL when unmeasured . Open: relationships test fails on `race_to_track` (1,107 rows, baseline). Used for the ML stint-life target.
- **ML `proximity` group** (`int_lap_proximity`). Built from the position sensor, not from speed, so it avoids the follower-speed assumption in `int_lap_air_state`. 5 tests; pit-lane exclusion and crossing order are tested. Open: `assert_proximity_agrees_with_blue_flags` fails on baseline. The admission to the ML contract was measured with permutation controls (see schema.py).
- **`fuel_mass_kg`** (`int_lap_fuel_state`, 7 tests). Burns fuel evenly over scheduled distance, per race, not per driver. Owner kept this on purpose, with an error bound of about 0.05 s per driver (from older archive data, not the current build). Open: `assert_fuel_load_matches_scheduled_distance` fails on baseline (38 rows). Everything depends on it, so a bad value is costly, but its logic is simple.
   **- **ML `thermal` group** (`int_lap_thermal_proxy`). 3 tests, but `assert_push_residual_fuel_neutral` fails on baseline (18,585 rows) and is untriaged. The model has many constant-style fills and clamps (counts from my grep: 11 zero-fills, 14 `LEAST/GREATEST`; I did not read each). The ratio constants must be kept in step with literal weights in the SQL (comment in dbt_project.yml).
- **Driver rating chain** (`int_driver_race_paired_laps` -> `int_driver_race_skill_loro` -> `int_driver_season_ratings` -> `int_era_normalized_driver_rating` -> `mart_race_driver_summary` / `mart_driver_season_summary`). Has real logic tests and a [unit-test file](../../../transform/models/intermediate/unit_tests_rating_chain.yml) with worked numbers, plus tests for antisymmetry and shrinkage bounds. Weak points: a fixed prior weight of 5, zero-fill for variance when a driver has one race (NULL SE becoming a zero-width interval, HD27), and an input (`int_constructor_car_fe`) whose fit lives in Python and was never checked. `mart_race_coverage` has an open logic case (2021_12 labelled OK with no rating).
- **ML `compound` and `cliff_prior` groups** (`dim_compounds_season`, `int_compound_cliff_predicted`, 9 tests on the latter). Many cells are not measured: the seed rows are tagged `cross_season_fallback`, and a backtest says default cells are about 2x worse than measured ones and biased 12 to 16 laps late. `int_compound_cliff_predicted` prices a lap with no seed cell as a free tyre. The seed has source columns (`fit_source`, `onset_source`) that say which cells are fallbacks, but the ML contract carries only the numeric columns, so the model cannot tell a default from a fit (based on the feature list in schema.py).
- **Field pace curve and track evolution** (`int_field_pace_curve` 8 tests, `int_track_evolution` 7 tests). Track evolution's slope clamp is an explicit CASE, so a NULL raw slope stays NULL. The unclamped `rubber_slope_raw_s_per_lap`, `rubber_fit_lap_count` and `rubber_status` (MEASURED, CLAMPED_POSITIVE, INSUFFICIENT_LAPS, NO_FIELD_BASE) are now published. The clamp policy itself is unchanged, so the flat-line effect remains on races with a positive raw slope (62% on an older build; not re-measured). A lap with no pace cell has no row. That is documented, not padded.
- **Dirty-air chain** (`int_lap_air_state` 7 tests -> `int_dirty_air_tax_component` 10 tests -> dirty-air-cost page, ML `dirty_air` group). Good test coverage including NULL-when-unmeasured. Weak: the gap is estimated using the follower's speed, `dt_s` is not clamped, the uncertainty is declared as a flat 15%, and the model reads bronze telemetry directly. The baseline test `assert_prior_season_labels_frozen` fails on this chain.
- **Pit strategy chain** (`int_pit_loss_circuit` -> `int_pit_strategy_cost_curve` -> `int_pit_strategy_value` -> pit-strategy page, `fct_stint_features`). Very long (21 CTEs in the last model, six int inputs), fixed constants (stop-loss truncated to 8 to 60 s), new tyre priced from age 1, a free tyre when no curve exists, and `GREATEST(..., 0.0)` that hides a missing opportunity cost. A test pins the baseline units (`assert_pit_cost_curve_baseline_units`).
- **Tyre-cliff survival and stint-degradation pages.** Display chain is fine, but the numbers come from the defaults in item 11. The app now labels default cells as an estimate with a range, which is the right fix. Still open: promotion of the pooled tier, and the simulator averaging over defaults (queries.ts lines 191 and 192; I did not open that file).
- **Constructor pace, circuit interaction, party mode** (`int_constructor_structural_pace` 2 tests, `int_circuit_x_constructor_interaction` 0 tests, `int_constructor_structural_pace_qualifying` 0 tests). Not neutral to fuel or compound, standard error falls back to 0 when there is one observation. The interaction model includes car development, not just circuit fit.
- **Ghost car chain** (`fct_ghost_car_pace` -> `fct_ghost_race_finish`, counterfactual championship, hidden performance). Eight upstream int models and 46 `COALESCE(...)` hits in one file. Now partly defended: the code adds `*_is_prior` flags and a `lap_has_prior_fill` flag, drops low-confidence laps, and has self-consistency tests. It still contains the WRONG `int_constructor_deg_sensitivity` (cliff-onset shift divides a value by itself, I did not re-derive this) and an ego-side constructor term that comes from the 0.0-filled residual column.
- **Corner skill** (`mart_corner_skill_driver` <- `int_corner_skill_residuals`). The mid-corner unit bug was fixed by measuring corner length (two new models, 8 and 9 passing tests, not audited). No value test pins the units. The mart z-score is not centred, and `int_corner_metrics` uses an exact throttle = 100 test and truncated windows. The sign convention is pinned by a test. Throttle threshold under investigation.
- **ML `qualifying` group and quali-vs-race page** (`int_qualifying_decomposed` -> `int_qualifying_driver_summary`). Deepest feature chain (about eight models), with known defects. Race average is filled with 0.0 in `quali_vs_race_skill_delta_s` (line 145 of the model), `quali_traffic_flag` is always NULL, `dnq_flag` is always FALSE, no test pins the sign. The ML only reads qualifying columns that do not use that 0.0 fill, and 1.9% of rows are missing (7.98% in 2018). `int_qualifying_driver_summary` and `int_qualifying_decomposed` have 0 and 1 tests that touch their own logic.
- **Tyre recovery forecast** (`int_tyre_surface_vs_bulk_decoupling`, 1 test). Missing thermal load imputed as 0.5, and the output "probability" is not fitted.
- **Degradation envelope and simulator** (`mart_degradation_history_envelope`). Reads an external parquet fit; default coefficients (`temp_headroom_c` 8.0, `temp_penalty_s_per_deg` 0.010, `dirty_air_deg_mult` 1.0) are filled in and shown as if fitted; age and lap index mismatch. The `data/fits/.gitkeep` file is deleted in the working tree, so the source parquet's location is worth checking.
- **Driver skill features, synthetic teammate, data-quality audit, sector decomposition.** `fct_driver_skill_features` has 0 tests that call it; `strategic_divergence_share` is filled with 0.0; NULL proxies sit in a weight divisor. `int_synthetic_teammate` has a constant TRUE flag and weights from its own outcome spread. `int_lap_anomaly_flags` uses an unscaled MAD (about 2 sigma) and calls NULL-residual laps normal, and it gates ML training rows. `int_sector_residual_decomposed` uses a different baseline from the lap model.
- **Models with no reader** (B4). They cannot hurt a user today. The microsector and physical-ahead chains have many tests; `int_track_geometry` has none and was changed by dividing positions by 10.

---

## D. Where logic is most likely to break (top 10)

1. **`int_lap_residual_decomposed` constructor term filled with 0.0.** Wet races and constructors with no dry clean lap get "average car". The flag exists, but rank and average columns in the two summary marts ignore it, so the 0.0 reads as a real car term.
2. **`int_compound_cliff_predicted` and `dim_compounds_season` default cells.** A lap with no fitted cell is priced as a free tyre or as a default cliff. This feeds the ML cliff and compound features, the field pace curve, the pit-strategy chain, and the ghost car.
3. **`int_lap_fuel_state` even burn.** One assumption sits under 48 downstream models. Bounded at about 0.05 s per driver, but measured on old data, and a baseline test on it still fails. The per-circuit penalty factor is a hand-set prior: the fitter cannot identify it from the data, and none of the current calibrated values is trusted (see the `fuel_mass_kg` bullet in section C). Calibration-policy question still open: whether a factor around 0.001 s/kg is acceptable at all.
4. **`int_track_evolution` slope clamp.** The published rubber slope is still clamped at 0 by policy. The clamp is an explicit CASE, so a NULL raw slope stays NULL, and the raw slope and a status are published. Only `int_lap_residual_decomposed` reads the rubber and ambient columns, and it carries them as informational columns outside the residual identity.
5. **`int_stint_geometry` and `stg_lap_tyre_qa`.** Everything is keyed on the stint. A fault in tyre run joining, compound mapping (2018 compound code NULL test fails) or stint 0 affects the ML labels and every tyre page.
6. **`race_to_track` seed gap.** All 19 2026 races are missing, and 26 relationships tests fail on it. The per-model caps to 2025 hide the problem. The ML holdout is pinned to 2026 ([holdout_config.py](../../../ml/src/holdout_config.py)), so ML evaluation depends on 2026 rows that this seed does not cover. I did not check whether 2026 rows exist in the warehouse.
7. **`int_qualifying_decomposed` fills and dead flags.** 0.0 race average, constant flags, no sign test, and it is the parent of seven ML features (only the columns that avoid the 0.0 fill reach the ML).
8. **`int_constructor_deg_sensitivity` (known defect) into `fct_ghost_car_pace`.** The cliff-onset shift has a units fault per the audit, and it drives the ghost-car finishing positions shown in the app.
9. **Zero-width uncertainty.** Constructor pace, era rating, circuit interaction and the shrinkage models turn a missing standard error into 0, so the app can show a confidence band of no width. `assert_ghost_se_never_zero_filled` covers the ghost car only.
10. **Training gate `int_lap_anomaly_flags` + `int_event_corrections`.** They decide which laps train the ML models. MAD is unscaled (about 2 sigma, so it flags more laps than intended), outlier thresholds come from one fastest lap, and two weights (0.3, 0.6) are unused. A silent change here moves every ML metric. ML training also requires `base_pace_status = 'MEASURED'` (see B2).

---

## E. Caveats and disagreements

**What I did not verify**
- I did not run dbt, the tests, the ML code or the app. Test pass and fail statements (for example "fails on baseline") were not re-run here.
- I did not query the warehouse, so I have not confirmed row counts, the presence of 2026 data, or whether the `data/fits` parquet files exist.
- Zero-fill and `LEAST/GREATEST` counts in section C come from a text search of the SQL. I read the key ones (residual decomposition, qualifying, track evolution, ghost car, the ML mart) but not every hit.
- Test counts are for singular tests that use `ref('<model>')`. Schema tests (column tests, `dbt_utils` tests, unit tests) were not counted per model.
- I did not read the fit scripts under `transform/tasks/coefficients`, the macros, or the seeds' values. 
- I did not open the degradation simulator `queries.ts`, so the claim that it averages over defaults was not checked.
- Which app routes are live and which are stubs: some `routes/*.tsx` files say "STATUS: stub" while a feature folder with the same name has real code (for example `drivers/consistency`, `ml/metrics`). I treated the feature folder as the live code.
- I did not trace `fct_telemetry_deltas`, `driver_network_rating.parquet`, or the assistant's `int_driver_isolation_lap_panel` use beyond a grep.
- The signals in section C are my reading of the code. They are not measurements.
- **Assistant stubs.** [heldStubs.ts](../../../app/src/assistant/cards/sql/heldStubs.ts) and [export_app_data.py](../../../scripts/export_app_data.py) name tables that are not models (`fct_constructor_structural_pace`, `int_coast_tax_component`). [verifyParity.ts](../../../app/src/ml/verifyParity.ts) names `int_air_density` and `int_lap_powertrain_signature`, which its own comment says were folded away.

---

## F. Race Control and Safety Car hazard (updated 2026-11-24)

This section replaces the 2026-11-23 audit snapshot. Figures from that snapshot that no longer hold (173 hazard rows, the pre-fix 2026 Barcelona key, "99 of 110" style model counts) are noted as historical in F7 and are not repeated as current. Sections F2 to F6 describe the state after the circuit-identity correction. Everything labelled "verified" below was checked by reading files or by read-only queries. Nothing here was re-run in the full warehouse.

### F1. Architecture and lineage

```
bronze track_status  --raw_track_status-->  stg_track_status  --\
bronze laps (race)   --raw_laps---------->  stg_laps           ---> int_sc_hazard_history
                                                                       |  (key: macro hazard_circuit_key)
                                                                       v
                          app/public/data/intermediates/int_sc_hazard_history.parquet
                                                                       |  (_manifest.json -> getTablePath)
race_to_track seed --> dimensions/race_to_track.parquet --join--> queryCircuitHazard --> hazard panel
```

| Layer | Object | Role |
|---|---|---|
| Source | `raw_track_status` (glob `track_status/*/*/*.parquet`), `raw_laps` (glob `laps/*/*/*.parquet`, race depth only; qualifying is `raw_laps_qualifying`) in [src_formula1.yml](../../../transform/models/staging/src_formula1.yml) | Race-level bronze files. A race with no bronze file has no rows downstream. |
| Not a dbt source | bronze `session_info` | Read directly by `assert_sc_hazard_circuit_key_per_season` for `Meeting_Circuit_Key` (physical circuit identity). The model itself does not read it. |
| Staging | [stg_track_status](../../../transform/models/staging/stg_track_status.sql) | `SELECT DISTINCT` removes exact duplicate bronze rows. One row per (race, `session_time_s`, `status_code`). `status_duration_s` is a `LEAD` over `session_time_s, status_code`. |
| Staging | [stg_laps](../../../transform/models/staging/stg_laps.sql) | Per driver and lap: `race_id`, `lap_number`, and the flags `is_safety_car_lap`, `is_vsc_lap`, `is_red_flag_lap`. The hazard model uses only `race_year`, `race_id` and `lap_number`. |
| Macro | [hazard_circuit_key](../../../transform/macros/hazard_circuit_key.sql) | Maps (race year, race slug) to the venue key. Used by the model and by `assert_sc_hazard_no_forward_leakage` (and by two other hazard tests) so they cannot drift. |
| Intermediate | [int_sc_hazard_history](../../../transform/models/intermediate/int_sc_hazard_history.sql) | One row per `circuit_slug` x `season`, season-lagged priors. Details in F2. |
| Export | `app/public/data/intermediates/int_sc_hazard_history.parquet` | One unpartitioned file, the full table, no export filter (so 2026 rows are included). |
| Manifest | `app/public/data/_manifest.json`, `tables` entry `int_sc_hazard_history` | `path`, `rows`, `hash`. The app resolves the file with `getTablePath(manifest, 'int_sc_hazard_history')`. |
| App query | `queryCircuitHazard` in [queries.ts](../../../app/src/features/race-control/queries.ts) | `race_to_track rt JOIN int_sc_hazard_history h ON rt.track_id = h.circuit_slug AND h.season = ?` where `rt.race_id = ?`. Reads only the shrunk columns plus `prior_races_n` and `prior_racing_laps`. |
| App logic | [transform.ts](../../../app/src/features/race-control/transform.ts) | `EB_PRIOR_LAPS = 600`; `hazardContext` returns `ownDataWeight = laps / (laps + 600)`, and `row: null` when the query returns nothing. |
| App page | [page.tsx](../../../app/src/features/race-control/page.tsx) (about line 198) | The hazard panel renders only when `hazard.row` exists. No row means no panel and no message. |
| Race selector | [useRaceOptions.ts](../../../app/src/features/shared/useRaceOptions.ts) | Builds the race list from `race_to_track` joined to `dim_circuits`. A race that is not in `race_to_track` cannot be selected, so it can never reach the hazard panel. |

Other readers of the table (from the 2026-11-23 audit, not re-checked on 2026-11-24): `fct_cliff_prediction_features` (`sc_hazard` CTE, `circuit_*_hazard` columns, not in the ML feature list) and `int_pit_strategy_cost_curve` (`sc_hazard_per_lap`). Both join on (`circuit_slug`, `season`).

The reference page [int_sc_hazard_history.mdx](../../../docs/reference/models/int/int_sc_hazard_history.mdx) is autogenerated. Do not edit it by hand.

### F2. Metric semantics

| Term | Definition (as coded) |
|---|---|
| Deployment rows | `stg_track_status.status_code = '4'` (SC deployed) and `'6'` (VSC deployed). Codes `'5'` (red) and `'7'` (VSC ending) are not onsets. |
| Onsets per race | `COUNT(*)` of those rows per race, after the exact-duplicate removal (`DISTINCT`) in staging. |
| Repeat guard | `assert_sc_hazard_no_repeated_status_records` fails if a `'4'` or `'6'` row is followed, in staging order, by another row with the same code. Two adjacent identical rows would be one deployment counted twice. |
| Exposure | `MAX(lap_number)` per race from `stg_laps`. It includes SC, VSC and red-flag laps and is NOT green-flag-only and not filtered by `is_valid_lap`. |
| Grain | One row per `circuit_slug` x `season`. The row for season S uses races at that venue in seasons strictly before S (`trailing_sum`, `frame='range'`, ending at 1 PRECEDING on the season axis). |
| Raw rate | `prior_*_onsets / prior_racing_laps`. NULL when the venue has no prior exposure. |
| Shrunk rate | `(prior_onsets + G x 600) / (prior_racing_laps + 600)`, where G is the season-lagged pooled rate across all circuits (`prior_global_*_rate`). 600 is the dbt var `sc_hazard_prior_laps` (default 600). |
| Own-data weight | `prior_racing_laps / (prior_racing_laps + 600)`. Computed in the app (`ownDataWeight`), not stored in the table. |
| Debut season | Prior counts are 0 (never NULL). Raw rates are NULL. Shrunk rates equal G. |
| 2018 | Every rate is NULL (raw and shrunk), because there is no earlier season. |

What the number is and is not:

- It is a historical per-full-race-lap rate of SC or VSC deployment at a venue, as seen in earlier seasons. Its denominator is every lap of the race, including neutralised laps.
- It is NOT the probability of a Safety Car during a whole race. Turning it into a race-level chance would need a model of the lap count and of clustering, which this table does not provide.
- It is NOT a prediction of when an incident will happen.
- The 600-lap prior is a shrinkage pseudo-count (a tuning choice, `sc_hazard_prior_laps`), not a physical constant. Own data carries most weight only after many prior laps (for example 1,200 prior laps gives a weight of 2/3).

### F3. Circuit identity correction

Event slugs do not always identify a physical circuit: events get renamed, a venue can host two races in a season, and in 2026 the Spanish Grand Prix is split across two circuits. The macro `hazard_circuit_key` therefore rewrites two slugs:

| 2026 event | Race id | Physical circuit | `Meeting_Circuit_Key` | Hazard key | History |
|---|---|---|---|---|---|
| Barcelona | `2026_7` | Barcelona-Catalunya | 15 | `spanish_grand_prix` (legacy key) | Inherits 2018-2025: 8 prior races and 528 prior laps |
| Madrid (Madring) | `2026_14` | Madring | 153 | `madring_grand_prix` | None (debut, raw rates NULL) |

`barcelona_grand_prix` is folded into `spanish_grand_prix` for every year, and `spanish_grand_prix` from 2026 on becomes `madring_grand_prix`. The key `spanish_grand_prix` is therefore the legacy Barcelona-Catalunya key.

Race-to-track mappings for these two 2026 races were deliberately not added (Option B, see F6). Madring has no calibrated `circuit_reference` row, and adding the mappings caused downstream relationship and coverage test failures.

Not regrouped: Silverstone 70th Anniversary (2020), Red Bull Ring double-headers, Mexico City against `mexican`, and Interlagos against `sao_paulo` still use their event slugs. A full regroup by physical circuit was assessed as a separate decision, using a read-only replica: 29 of 191 rows would change, with a maximum shift of about 0.0027 on the shrunk SC hazard. It was not applied.

Limit of the identity check: `Meeting_Circuit_Key` is not a clean physical identifier (key 149 is shared by Jeddah 2021-25 and Mugello 2020), so `assert_sc_hazard_circuit_key_per_season` can only show that one season never has two different keys under one hazard key.

### F4. Validation and publication

**Scratch-warehouse validation (not the real warehouse).** A targeted build, `dbt build --select int_sc_hazard_history`, was run against a scratch warehouse. The model was created and its 21 attached tests passed, with 0 errors. The six `assert_sc_hazard_*` singular tests passed. `assert_sc_hazard_no_repeated_status_records` is not attached to the model, so it was run separately with `dbt test --select 'assert_sc_hazard_*'`.

**Published artifact (read-only checks against `app/public/data`).**

| Check | Result |
|---|---|
| Rows, seasons, columns | 191 rows, 9 seasons (2018-2026), 15 columns |
| Key uniqueness | No duplicate (`circuit_slug`, `season`) |
| 2026 rows | 19 |
| File | SHA-256 begins `dde4856e`; 10,701 bytes |
| Manifest entry | `rows` 191; `hash` `9e10a7c086071dd49796e49bd591e5ac` (exporter's md5 and bit_xor convention) |
| Manifest top-level `version` | `f8399bc270fa752f`, computed by `final_version` over current file names and sizes. It changes whenever any Parquet file size changes. |

**App query replay.** A read-only DuckDB replay of `queryCircuitHazard` over the published `race_to_track` and hazard files: 172 of 173 published race mappings match exactly one hazard row, with no duplicate matches. The one unmatched race is `2018_14` (Italian GP 2018, `italian_grand_prix`). It has no hazard row because its race-level bronze files are missing, so the panel is hidden.

**Automated app tests.** `npx vitest run src/features/race-control src/features/shared` (in `app/`): 2 files, 20 tests, all passed. `npx tsc --noEmit -p tsconfig.app.json`: exit 0.

**Not performed.** No browser testing and no Playwright end-to-end test. No full project-wide `dbt build`. No full app-data export.

### F5. Known limitations and deferred work

This is not a claim that 2026 coverage is complete. It is not.

1. **2018 Italian GP (`2018_14`) has no hazard row.** The panel is hidden and the page gives no reason. Cause: race-level bronze files are missing (`2018 R italian_grand_prix` in [known_gaps.txt](../../../ingestion/known_gaps.txt)).
2. **2026 rows are published but unreachable.** The artifact holds 19 races for 2026 (Barcelona under `spanish_grand_prix`, Madrid under `madring_grand_prix`). No 2026 race is selectable because `race_to_track` has no 2026 mappings (Option B).
3. **Madring has no `circuit_reference` row.** Do not invent physical parameters or add NULL-filled calibration data without an explicit owner decision.
4. **Before enabling 2026 in `race_to_track`:**
   - all 19 races need modelling and mappings;
   - `assert_race_to_track_covers_all_races` requires every `race_to_track` track to resolve in `dim_circuits`;
   - downstream INNER joins (for example `int_lap_fuel_state`) would admit 2026 laps;
   - the `model_seasons` and `holdout_season` settings in [dbt_project.yml](../../../transform/dbt_project.yml) must be reconciled (`model_seasons` stops at 2025 on purpose, with the note "Widen ... when 2026 is modelled"; `holdout_season` is 2025 per HD17 and 2026 is not defined for use);
   - the app needs verification.
5. **Seven out-of-closure test errors** appeared in a targeted build of this selection. They are catalog errors from models outside the closure (for example `int_lap_air_state`, `stg_weather`, `fct_telemetry_deltas`). They are a separate, pre-existing issue and not caused by the hazard work.
6. **Model-hash baseline not updated.** [model_hashes.baseline.json](../../../transform/tests/model_hashes.baseline.json) already differed from the artifact before this work and was left as it was.
7. **Hand-updated artifact.** The published parquet and manifest were updated in-session by hand with checks, not by a full export. The manifest `version` depends on file sizes and must be recomputed if any Parquet file changes.
8. **Silent-drop risk (from the 2026-11-23 audit, not re-checked).** A race with laps but no track-status timeline is removed from both numerator and denominator by the inner join, and no test catches it.

Decisions that should not be reversed casually:

- Option B: no 2026 rows in `race_to_track`.
- `spanish_grand_prix` stays the legacy key for Barcelona-Catalunya.
- Exposure stays full-race laps (not green-flag laps).
- 2026 rows stay in the hazard artifact, with no export filter.
- The 600-lap prior stays as the shrinkage pseudo-count.

### F6. Option B in one paragraph

Option B means the hazard model and artifact know about the 2026 split, but the app and the rest of the pipeline do not. It was chosen over adding `2026_7` and `2026_14` to `race_to_track`, because the Madring venue has no calibrated reference data and the extra rows broke relationship and coverage tests. The cost is that the 2026 hazard rows are currently dead data for the app.

### F7. Historical observations (superseded)

- The earlier artifact had 173 rows. It now has 191, including 19 rows for 2026. Treat the 173 figure in older notes as historical. The reason for the exact difference was not itemised here.
- Before the fix, the 2026 Barcelona row was filed under a different key and Madrid shared the Barcelona-Catalunya history. That is the defect `assert_sc_hazard_2026_spanish_madring_distinct` and `assert_sc_hazard_circuit_key_per_season` now guard against.
- An earlier note had a 99 against 110 model-count discrepancy. It was not resolved here; treat the counts in section A2 as approximate.
- The 2026-11-23 audit's checks (bounds, exposure reconstruction, leakage, onsets against timeline runs, own-data weight maximum of 45.2%) were made on the 173-row artifact. They were not repeated on the 191-row artifact except where F4 says so.
- **Historical, unresolved: onsets against timeline runs (older 173-row artifact).** The 2026-11-23 audit found 99 SC onsets against 93 contiguous SC runs, and 69 VSC onsets against 67 contiguous VSC runs, over 2018 to 2024 for the circuits in the 2025 rows. Onsets should not be fewer than runs. These are findings from the older 173-row artifact and the earlier investigation, not current verified totals. The later 2018–2026 investigation of status-row sequences found that status-row counts match contiguous runs in the examined data: 118 SC and 83 VSC rows in 2018 to 2024, with no adjacent repeats. The older discrepancy was not independently reconciled, so it is kept here as an open historical item rather than replaced.

### F8. Navigation

| What | Path or name |
|---|---|
| Model | `transform/models/intermediate/int_sc_hazard_history.sql` |
| Model tests and docs (21 attached tests) | `transform/models/intermediate/schema.yml`, entry `int_sc_hazard_history` |
| Macro | `transform/macros/hazard_circuit_key.sql` |
| Staging | `transform/models/staging/stg_track_status.sql`, `stg_laps.sql`, sources in `src_formula1.yml` |
| Singular tests | `transform/tests/assert_sc_hazard_2026_spanish_madring_distinct.sql`, `assert_sc_hazard_circuit_key_per_season.sql`, `assert_sc_hazard_madring_debut.sql`, `assert_sc_hazard_no_forward_leakage.sql`, `assert_sc_hazard_no_repeated_status_records.sql`, `assert_sc_hazard_probability_bounds.sql` |
| Seeds and config | `transform/seeds/race_to_track.csv` (173 data rows, no 2026), `transform/seeds/circuit_reference.csv` (no Madring row), `transform/dbt_project.yml` |
| Artifact and manifest | `app/public/data/intermediates/int_sc_hazard_history.parquet`, `app/public/data/_manifest.json` |
| App | `app/src/features/race-control/queries.ts`, `transform.ts`, `page.tsx`, `app/src/features/shared/useRaceOptions.ts` |
| Exporter | `scripts/export_app_data.py` |
| Gap list | `ingestion/known_gaps.txt` |

Re-run commands (these write to the warehouse or `target/`; use a scratch copy, not the real warehouse):

- `cd app && npx vitest run src/features/race-control src/features/shared`
- `cd app && npx tsc --noEmit -p tsconfig.app.json`
- `cd transform && ../.venv/bin/dbt build --select int_sc_hazard_history`
- `cd transform && ../.venv/bin/dbt test --select 'assert_sc_hazard_*'`

---

## G. Current change status

Status taxonomy. Sections A to F stay as written. Provenance becoming visible is not a fix: no upstream model below is marked fixed by Task 2B.

### G1. Completed and verified changes

The hazard work in section F (verified there on 2026-11-24). Per-model status and risk entries in sections C and D are unchanged.

### G2. Merged: Task 2B (compound provenance)

- **Where.** Branch `task2b-compound-provenance` (commit `6a891a5`), merged into `main` as `baa0c82`.
- **Meaning.** `is_measured` now means all three parameters (onset, gradient, severity) are fitted. Cross-season, pooled, carried-forward and class-default values are not measured.
- **Propagation.** Per-parameter source and an aggregate `provenance_class` flow to `dim_compounds_season`, `fct_cliff_prediction_features` (five new columns) and the app. App messaging separates fitted, borrowed, default (estimate) and unknown values.
- **Verified.** Scratch rebuild on real data, base against post: row grain unchanged (dim 499 rows, mart 161,406 laps). Zero differing values in 39 feature and 7 target columns. Provenance invariants hold. The 3,130 'missing' laps are all NULL-compound laps. The provenance singular test and three other singular/unit tests pass. TypeScript passes. cliffEstimate tests pass 31/31.
- **Known limits.** `pooled_compound_fallback` and `carried_forward` have zero real rows (fixture-only). The real-compound 'missing' path is not exercised by real data. The simulator cell counts are returned but not consumed by any UI. 2B does NOT fix the underlying default parameter values.
- **Status.** Merged to local `main`. Not pushed. Not deployed. Its provenance labels are visible in the app only after the pipeline export is re-run.

### G3. Deferred: Task 2A (cell-less laps priced as unknown)

- **DEFERRED.** All functional changes were reverted to baseline `ac3fdd9`. No active production change.
- The patch and supporting tests are archived at [`_roadmap/_archive/compound-cliff-2a/`](../../_archive/compound-cliff-2a/README.md).
- Future work needs a feature and target impact analysis and an explicit retraining decision before any change to ML input values. The deferred fix is not implemented, so the "free tyre" pricing in `int_compound_cliff_predicted` (sections C and D) is still current behaviour.

### G4. Known pre-existing failures and unresolved risks (on main, not caused by 2B)

- `assert_prior_season_labels_frozen` fails (7 rows): the frozen `label_stability_baseline` seed is stale against current data.
- Three citation tests in `sources.node.test.ts` fail.
- Two `TestFuelCorrectedSeries` loader tests in `test_seed_param_provenance.py` fail.
- `profileLookup.test.ts` depends on a gitignored parquet that is present only in main.
- All risks in sections C, D and F5 remain open, including `int_lap_fuel_state`, `int_lap_residual_decomposed`, `int_compound_cliff_predicted`, `dim_compounds_season` default cells, `int_constructor_deg_sensitivity`, `int_qualifying_decomposed`, `int_stint_geometry` and `race_to_track`. Partial fixes are not full resolutions.
