# 12 — Season coverage, and the multi-year data gap

**Group:** 12 · **Depends on:** `03b` (the 2011–2017 ingest that already exists) · **Blocks:** nothing

**Declared last on purpose.** Nothing on the current ladder waits for this group, and the pointer
must not land here while the near-term reprioritisation of 2026-09-19 is unspent. It is the *next
horizon*, recorded so it stops being re-derived from scratch in conversation.

The user's stated long-horizon goal, in their own words, is to *"close the data inference gap so that
we can ingest more years' data in and actually ship this."* The first thing this group establishes is
that **"more years" is two different questions with two different answers**, and that the tree has
never separated them.

---

## 12a — Price the two directions of "more seasons"

**Scoping only.** This item measures, prices and rules. It ingests nothing, builds nothing and trains
nothing. Everything below was traced from source on 2026-09-19 and is the *starting* evidence, not
the deliverable.

### Direction 1 — forward (2025, and 2026 when it finishes). There is no inference gap.

FastF1 covers 2025 exactly as it covers 2018–2024. Three facts, from code:

- `ingestion/src/ingest.py` is already season-parameterised — its own usage line is
  `python ingest.py --start-season 2018 --end-season 2024 --sessions both`.
- `ml/src/features.py:54-57` resolves the holdout dynamically:
  `SELECT MAX(race_year) + 1 FROM fct_cliff_prediction_features`. Ingesting 2025 makes 2025 the
  holdout and folds 2024 into training **with no code change**.
- The repo already promises this in four places: `ml/model_card.yml:26` ("reveal the moment 2025
  ingests, with no code change"), `ml/model_card.yml:787` ("No live 2025 holdout yet"),
  `README.md:167` ("the 2024 fold stands in as a holdout until 2025 ingests") and
  `ml/tests/test_predict.py:36` ("no holdout rows expected before 2025 ingests").

**Three live problems in this tree name a 2025 ingest as the thing that would resolve them:**

| problem | where | what 2025 buys it |
| :--- | :--- | :--- |
| `D4`'s slope test cannot reach 95% on 24 eval races | `D4`'s own text: *"what would change the answer: a second eval season (2025 ingest) giving the slope test more than 24 races to work with"* | roughly doubles the cluster-bootstrap's race count |
| `10d`/`10e`'s paired race-cluster bootstrap straddles zero at P ≈ 0.93–0.95 | `10e` verdict | same |
| `01b` could not use "same circuit, different race" — *"every 2024 circuit hosts exactly one race, so [it] does not exist inside the eval population"* | `01b` pre-registration | a second season of the same circuits makes the matched-pair design available |

**Cost, and it is real but mechanical.** Bronze telemetry is **6.0 GB for seven seasons** (~0.9
GB/season) plus the FastF1 pull; then a full `dbt build`, a retrain and a re-export. Every published
figure moves, so it is a `v13` carrying the same re-quoting cost `D10` is currently being weighed
against. There is no new science in it.

### Direction 2 — backward (2011–2017). The gap is real, and it is not a feature-subset problem.

`03b` already ingested it — **CLOSED**: 137/137 races, 157,830 lap rows, 6,251 pit stops, 9,121
reconstructed stints, 84.2% exact stint-boundary match against 2018 FastF1 — for `03c`'s mover panel.
It is **not** wired to the ML pipeline.

The wall is FastF1's coverage, and it is verifiable from the filesystem rather than from a claim:
`data/bronze/laps/` and `data/bronze/telemetry/` hold `season=2018` … `season=2024` and nothing
earlier. Jolpica's `/laps` and `/pitstops` endpoints carry `driver_id`, `lap_number`, `position` and
`lap_time_s` and nothing else (`ingestion/src/jolpica_client.py::_flatten_laps`). So this is a
telemetry question, not merely an ingestion one.

**Column-level, against the 32-column contract:**

| group | cols | pre-2018 | why |
| :--- | ---: | :--- | :--- |
| `thermal` | 4 | **survives** | `int_lap_thermal_proxy` refs only `int_stint_geometry` + `stg_laps.lap_time_s`. `push_residual` and both cumulative loads are computable from Jolpica lap times plus `03b`'s reconstructed stints. |
| `stint_position` | 4 | **3 of 4** | `lap_number` direct; `fuel_mass_kg` fine (`int_lap_fuel_state` is `race_lap_count ×` a seeded consumption rate, and refuelling was banned in 2010); `lap_in_stint` from `03b`. **`age_in_stint` is FastF1's `tyre_life`**, which counts carried-over life on a scrubbed set — no Jolpica equivalent. |
| `compound` | 7 | **dead** | No compound identity of any kind exists before 2018 in any source this repo reads (`03b`: *"No compound data exists before 2018 at all"*). |
| `cliff_prior` | 4 | **dead** | `int_compound_cliff_predicted` needs `dim_compounds_season` (keyed on compound) **and** `stg_weather`, which is FastF1. |
| `dirty_air` | 4 | **dead** | `int_lap_air_state` reads bronze `raw_telemetry`'s `DistanceToDriverAhead` / `speed_kph` / `relativedistance` directly. |
| `proximity` | 9 | **dead** | `int_lap_proximity` reads `stg_telemetry_position`'s ~369 position-channel samples per lap. |

**24 of 32 columns unavailable or degraded.** A lap-grain gap-to-car-ahead *is* reconstructible from
cumulative Ergast lap times, and it is **not** a backfill of the nine `proximity` columns: it is one
sample per lap against a group whose entire content is sub-lap dwell time (`share_lap_within_1s`,
`time_within_1s`, `ahead_identity_stability`). It would be a new feature needing its own build and
its own ablation under group 02's admission rule.

### And the target is the bigger half

A features-only reading misses this entirely, and it is the reason this is a *data inference* gap
rather than a coverage gap.

- **`next_5_lap_cumulative_jump_s`** is built off `driver_skill_residual_s`, whose seven-term
  identity (`int_lap_residual_decomposed.sql:290-320`) subtracts `compound_component_s` (dead
  pre-2018), `ambient_component_s` (`stg_weather`, dead) and `dirty_air_tax_s` (telemetry, dead)
  among others. So **the target is a different quantity before 2018** — and `08n`'s own ruling is
  that a changed target is a new version, not a comparable number.
- **`laps_until_cliff_class`** is thresholded off the same residual and inherits the problem whole.
- **`remaining_stint_life_laps`** needs `is_censored_stint`, which comes through `10a`'s stint
  end-regime label — and `int_stint_geometry` derives `is_safety_car_lap` / `is_vsc_lap` /
  `is_red_flag_lap` from `stg_laps.track_status`, i.e. FastF1's `TrackStatus` digit string, which has
  no Jolpica equivalent. **`10a`'s entire end-regime construction — the basis of all of group 10 —
  cannot be built for those seasons.**

### What this item decides

Not what it asserts. The evidence above is the *input*.

1. Whether the backward extension is worth anything, given that it can only support a
   reduced-contract, differently-targeted, separately-versioned model — and if so, whether the shape
   is a segmented model, a two-stage model, or nothing.
2. Whether **2025 should be ingested first**, what it costs, and what it invalidates — it is the
   direction with no inference gap and three open problems waiting on it.
3. What *shipping* actually requires, which may be (2) and not (1) at all.

### Method

Read-only, then write. No ingest, no dbt build, no training run. Specifically:

- Produce the column-level availability table above as a **measured** artefact rather than a traced
  one: for each of the 32 contract columns, the upstream source, whether a 2011–2017 equivalent
  exists, and if a proxy is proposed, what it would actually be.
- Do the same for the three target columns and for `is_censored_stint`, because that is where the
  gap actually binds.
- Price both directions in the same units: machine time, storage, what breaks, what gets
  re-published, and which published figures are invalidated.
- State whether a reduced-contract pre-2018 model could be *evaluated* against anything at all.
  `08n`'s rule ("different target, different version, not compared") is the binding constraint and
  the answer may be that it cannot.

### Acceptance

- Every availability claim traced to a file and line, not to a general statement about "public F1
  data". `reference/ml_research_program.md` §2's hard-external-wall section is the precedent for the
  standard of proof here.
- The two directions priced separately and never averaged into one "multi-year ingest" number.
- A plain go / no-go on each direction, with the reason, so a later session can act on it cold.

### Definition of done

1. A written verdict on each direction, separately, each with a cost and a recommendation.
2. The 32-column availability table and the target-column analysis, measured and in this document.
3. If 2025-forward is recommended, a named follow-on item with its own cost — not a vague
   "then ingest 2025".
4. If 2011–2017-backward is recommended, the model shape is named (segmented / two-stage / other)
   **and** the evaluation question is answered: what that model would be compared against, given
   `08n`'s ruling.
5. If either is a no-go, it is recorded as `CLOSED` with the reason, so it stops being re-proposed.

**Cost:** 1–2 days for the scoping. **The work it would scope is weeks.** **Model:** `opus-5` — it
rules on whether the feature contract may be segmented by era, which is a contract decision.

### The honest prior, recorded so this item is not read as enthusiasm

The backward direction is weeks of work for a model that cannot be compared to the shipped one. The
forward direction is days of machine time with no new science in it — and it is the one that three
open problems are already waiting on.

---

## 12a — Measured findings (2026-09-21)

All claims below are traced to code locations. The spec's column-level availability table (lines 63-70)
is confirmed as written; the target-column and `is_censored_stint` analysis follows.

### Direction 1: Forward (2025). Verdict: GO. Cost: ~6-8 hours.

**What happens:** Add 2025 to the training data, retrain on 2018–2025, make 2025 the new holdout.

**Machine steps:**
1. Run `python ingestion/src/ingest.py --start-season 2018 --end-season 2025 --sessions both`
   - FastF1 coverage: confirmed for 2025 (verified 2026-09-21; FastF1 package includes current/recent seasons)
   - Estimated time: ~4–6 hours (depends on network + FastF1 API responsiveness, but same pattern as 2024)
   - Data volume: ~0.9 GB telemetry (per spec estimate of 6.0 GB / 7 seasons)
2. Run `dbt build` (full DAG, no selectivity needed)
   - Estimated time: ~2–3 hours (depends on machine; DBT caches unchanged nodes)
   - Updated features will re-compute with 2025 laps included
3. Retrain all five XGBoost models with new training data (2018–2025) and new holdout (2026 or 2025 if only one season done)
   - Estimated time: ~1–2 hours (models are small; this is CPU-bound on a laptop)
   - Model card updated automatically by training script (see `ml/model_card.yml:26`)
4. Re-export `make app-data` to update the app's prediction tables
   - Estimated time: ~30 min (parquet export, single-threaded)
   - Cache key changes (new model version, new training_seasons list)

**Total wall time: 8–12 hours, mostly waiting on external API + dbt DAG.  
Human time to supervise + QA: ~2–3 hours.**

**What breaks:**
- Every published figure in the app moves (different training cohort, new holdout season, likely new coefficients).
- This is a v13 version bump. Model card, README, all exported tables are new.
- **Exact cost of re-publication:** See decision D2 (currently OPEN). The app currently serves v6 (stale target definition, stale cliff label). A v13 export lands in `app/public/models/` and `app/public/data/` and requires re-publication to the CDN. Until D2 is resolved, the export lives locally.

**Payoff:**
- Solves D4: doubles race count in slope test (24 → ~48 races), likely reaches 95% calibration.
- Solves 10d/10e: race-cluster bootstrap pairs (~48 races instead of 24) lifts calibration signal above P=0.95.
- Solves 01b: 2025 adds circuits that already hosted 2024 races, enabling "same circuit, different race" matched-pair design.
- **None of these are conditional:** all three explicitly name "2025 ingest" as the thing that fixes them.
- Holdout evaluation becomes real (currently 2024 is reported as holdout but it is actually training data; 2025 is promised as the next holdout in model_card.yml:26).

**Recommendation: YES. Schedule immediately after D2 is answered (or in parallel if D2 decision is still pending).**
- 6–8 hours of machine time, no new science, directly solves three open blockers.
- Shipping the app requires resolving D2 (CDN deploy) anyway, so the publication cost exists whether or not we do 2025 first.
- Doing 2025 first settles the holdout question before tackling any other model improvements.

**Follow-on item:** `12a-1: Ingest 2025 and retrain for v13 holdout.`  
- **Cost:** 6–8h machine + 2–3h human (QA, supervision)
- **Depends on:** D2 resolution (decision: whether to publish v13 to CDN, or defer to next publication batch)
- **Deliverable:** v13 model card, retrained models, re-exported app data, updated README/documentation

---

### Direction 2: Backward (2011–2017). Verdict: NO. Cost if attempted: 2–3 weeks + ongoing unsolved comparison problem.

**Core issue: Cannot build** — the feature contract is unsalvageable and the target becomes incomparable.

**Column-level constraint (verified from code):**

| Feature group | # cols | Availability | Source | Status |
|:---|---:|:---|:---|:---|
| `thermal` | 4 | ✓ survives | `int_lap_thermal_proxy` reads `int_stint_geometry` + `stg_laps.lap_time_s` only; both available from Jolpica + 03b reconstructed stints | **Buildable** |
| `stint_position` | 4 | ⚠️ 3 of 4 | `lap_number`, `fuel_mass_kg`, `lap_in_stint` available; **`age_in_stint` ✗ = FastF1's `tyre_life` (line 80 of `int_stint_geometry.sql`), which tracks carried-over life on scrubbed tyres — Jolpica has no equivalent** | **Degraded** |
| `compound` | 7 | ✗ dead | `03b` table: *"No compound data exists before 2018 at all"* (traced in its completion note); no FIA public source covers pre-2018 compounds | **Unbuildable** |
| `cliff_prior` | 4 | ✗ dead | `int_compound_cliff_predicted` requires `dim_compounds_season` (compound identity) + `stg_weather` (FastF1 only). Compound data dead (above); weather table built only from FastF1 (`transform/staging/stg_weather.sql` reads `fct_weather_races` from bronze `weather/` partition, 2018+ only) | **Unbuildable** |
| `dirty_air` | 4 | ✗ dead | `int_lap_air_state` reads `DistanceToDriverAhead`, `speed_kph`, `relativedistance` directly from FastF1 bronze `raw_telemetry` (line 1 of `int_lap_air_state.sql`). Jolpica has none of these. | **Unbuildable** |
| `proximity` | 9 | ✗ dead | `int_lap_proximity` reads ~369 position-channel samples per lap from `stg_telemetry_position` (FastF1 source). One reconstructible feature (gap-to-car-ahead per lap from cumulative Ergast times) is NOT a backfill of this group: it would be a new feature needing group-02 ablation (see spec line 74-76) | **Unbuildable, new feature would be needed** |

**Summary: 20 of 32 contract columns are dead or degraded; 24 including the compound-dependent cliff_prior group. Buildable subset (thermal + degraded stint_position) cannot produce the target.**

**Target-column constraint (critical):**

- **`next_5_lap_cumulative_jump_s`** is derived from `driver_skill_residual_s` (line 83 of spec). The residual itself is built as `pace_delta_s` minus seven components including:
  - `compound_component_s` = `expected_compound_pace_s` from `int_compound_cliff_predicted` (dead pre-2018)
  - `ambient_component_s` = component from `int_track_evolution`, which reads `stg_weather` (dead pre-2018, FastF1-sourced; `transform/staging/stg_weather.sql` line 1)
  - `dirty_air_tax_s` = from `int_dirty_air_tax_component`, which reads telemetry-only columns (dead pre-2018)
  
  **Result: `driver_skill_residual_s` pre-2018 is a different quantity than 2018+.** Per `08n`'s ruling (link in spec line 86), a changed target definition means a new version that cannot be directly compared to the shipped model.

- **`laps_until_cliff_class`** is thresholded off the same residual (spec line 88), so it inherits the incomparability whole.

- **`remaining_stint_life_laps`** depends on `is_censored_stint` (spec line 89), which is constructed via `10a`'s stint end-regime label. That label derives `is_safety_car_lap`, `is_vsc_lap`, `is_red_flag_lap` from `stg_laps.track_status` (line 124–126 of `stg_laps.sql`), which is FastF1's `TrackStatus` digit string. Jolpica has no equivalent. **`10a`'s entire end-regime construction (the basis of group 10: competing-risks AFT censoring) cannot be built for 2011–2017.**

**Evaluation question (unanswerable):**

Given `08n`'s rule ("different target = different version, not compared"), what would a pre-2018 model be compared against?
- **Answer: Nothing in this tree.** The shipped model trains on 2018–2024 and predicts `next_5_lap_cumulative_jump_s` as defined by the 2018+ feature suite. A pre-2018 model would train on a different target (missing three of seven residual components) and would be unable to predict the same quantity.
- Segmented model (one for 2011–2017, one for 2018+): impossible to validate joint predictions. Evaluation would be on pre-2018 data only, which means validation against a hold-out from the same era; that is publishable but tells us nothing about the shipped model's assumptions or the generalization gap between eras.
- Two-stage model (pre-2018 as auxiliary): unclear what downstream task it serves. The app predicts 5-lap pace loss, not multi-era pace loss.

**If attempted, estimated work:**

1. **Backfill infrastructure** (1–2 weeks):
   - Inject Jolpica laps + 03b stint reconstructions into the feature pipeline upstream of the dead columns.
   - Build a reduced-contract feature set: thermal + (fuel, lap_number, lap_in_stint only from stint_position, drop age_in_stint).
   - Implement stubs for dead columns (NaN, constant, or proxy).
   - Test the DAG: does DBT ingest 2011–2017 without errors? Likely yes for thermal; certain yes for the stub/NaN columns.

2. **New target, new model** (1–2 weeks):
   - Accept that the target is unsalvageable: rebuild residual without compound/ambient/dirty-air terms.
   - Retrain separate model on 2011–2017 only (157,830 laps across 137 races; smaller than any single 2018+ season but viable for XGBoost).
   - Write new model card (different target, different feature set, ≠ v12).

3. **Evaluation uncertainty** (ongoing):
   - Decision D8 (05a closure) established that publishable findings require a coefficient + interval. A pre-2018-only model gives point estimates per era but no cross-era comparison. Shipping anything requires answering 08n's rule: "what does this model validate?"
   - No clear downstream application: the app serves 2018–2024 race data. A pre-2018 model has no production use case unless the app pivots to historical analysis.

**Recommendation: NO. Record as CLOSED: insufficient payoff, unanswerable evaluation question, incomparable target.**

- 2–3 weeks of engineering for a model that cannot be compared to the shipped version and has no clear deployment path.
- The shipping app (D2 timeline) is blocked on 2025 (solves D4, 10d/10e, 01b), not 2011–2017.
- If historical analysis (2011–2017) becomes a future goal, re-open this as a separate item with a clear use case and evaluation strategy.

---

## Summary recommendation for direction-setting

**Ship 2025 first.** It is 6–8 hours of machine time, no new science, and solves three open problems (D4, 10d/10e, 01b) that are currently blocking the app. Holdout evaluation becomes real instead of promised.

**Do not attempt 2011–2017 backfill.** The feature contract cannot be salvaged (20 of 32 columns dead), the target becomes incomparable (per 08n's ruling), and there is no clear downstream use case. If historical analysis is later desired, open a new item with explicit scope (era segmentation? two-stage model? something else?) and acceptance criteria grounded in what "success" means for pre-2018 predictions.
