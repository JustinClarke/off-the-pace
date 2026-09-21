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
