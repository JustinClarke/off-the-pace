# Forensic audit of the transform layer — audit charter

**What this is.** A runnable brief for a full semantic audit of `transform/` and its ML consumers:
does the warehouse produce F1 data that is *true*, not merely *present*. It is the generic
"audit my F1 pipeline" prompt re-pointed at this repository, with the parts that have no referent
here removed and the parts this repository actually gets wrong named explicitly.

**Written for** the agent or engineer running the audit — not for a reader who already knows the
tree. It assumes `_improvements/README.md` and `foundations/epistemics.md` have been read.

**Status.** Charter only. Nothing here is a landed finding except §4, which was traced on
2026-09-24 and is handed over as the audit's starting evidence. This document has no entry in
`status/build-log.json` and is not a work item; §9 says what to do with the output.

**Companion to** [`transform_gaps.md`](transform_gaps.md), which ran the same exercise on
2026-07-30 and found seven defects, all since fixed. That document is the *shape* of a good result
here: measured against `data/dev.duckdb`, ranked, blast radius named, each finding traced to the
line that creates it. Read its "Findings, ranked" table before starting — three of its four defect
*classes* recur in §4 below, which is itself a finding about the tree.

---

## 0. Read this first — the brief's false premises

The generic brief assumes a results-and-standings warehouse: race winners, points tables,
championship positions, sprint classifications, Lance Stroll implausibly leading, Haas implausibly
top of the constructors'. **Almost none of that exists in this repository.** An auditor who works
the generic checklist top-to-bottom will manufacture findings about models that were never built.

| The brief assumes | What is actually here |
| :--- | :--- |
| Points and championship standings models | **None.** No dbt model computes points, cumulative points, standings, or position change between rounds. `stg_results.points` is passed through from FastF1 and **consumed by nothing in `marts/`** — verify this before relying on it |
| Sprint sessions | **Not ingested.** `data/bronze/laps/` holds race-depth files and `session=Q/` only. No sprint, no sprint shootout. "Sprint mixed into race" has no mechanism *unless* §5.1 finds one |
| Practice sessions | **Not ingested.** Item `02f` (FP1/2/3 ingest) is CLOSED. This matters for §5.1: the guard that would keep FP laps out of race laps does not exist |
| A championship round number | `dim_events.round_number` exists, from a **manual seed**, and is not the join key anywhere. The identity key is `race_id` (a FastF1 event slug like `2018_4`), not (season, round) |
| Stable constructor IDs | `constructor_id` **is the FastF1 `TeamName` string**. It is season-scoped and changes when a team renames. See §4.4 |
| Stable driver IDs | `driver_id` **is the three-letter code**. `driver_number` is a **VARCHAR**. See §4.5 |
| A circuit dimension used as the cohort key | `stg_laps` aliases the *same source column* to both `race_id` and `circuit_key`. `circuit_key` is an **event slug, not a venue**. See §4.3 |
| Grid/finish/classified position confusion as a live risk | Positions barely enter the ML lineage at all. The label is **tyre degradation in seconds**, not finishing position. Grid/finish confusion is a low-yield search here |

**What this repository is instead.** A lap-time decomposition warehouse. Every clean lap is split
into seven additive components; the residual is called driver skill. The five models predict tyre
degradation (p10/p50/p90), a tyre-cliff class, and remaining stint life. So the semantic risks that
matter are **not** "did Stroll win" but:

- is the residual that we call skill actually the label, reached by another path?
- does a window that claims to look backward reach forward?
- is a missing physical quantity being filled with a plausible default and then learned from?
- is a hand-maintained seed or an offline fit silently governing a feature?
- does the eval split still hold out anything?

Re-point the checklist accordingly. §5 does that re-pointing; do not re-derive it.

**Report absence explicitly.** For every generic category with no referent here, say so in one line
with the evidence (e.g. "no points model: `grep -rn 'points' transform/models/marts/` returns
nothing"). A silent omission is indistinguishable from a missed check.

---

## 1. Scope

**In scope**

| Layer | Path | Why |
| :--- | :--- | :--- |
| Sources | `transform/models/staging/src_formula1.yml` | The declared contract against bronze. §4.1 found it already lying |
| Staging | `transform/models/staging/stg_*.sql` (16) | Unit casts, validity flags, session separation |
| Reference | `transform/models/reference/dim_*.sql` (5) | Identity. §4.4, §4.5 live here |
| Intermediate | `transform/models/intermediate/int_*.sql` (45) | Where every window, fit and residual is |
| Marts | `transform/models/marts/` (10) | `fct_cliff_prediction_features` is the ML mart |
| Seeds | `transform/seeds/*.csv` | Hand-maintained parameters that enter features |
| Offline fits | `data/fits/*.parquet`, `make coefficients-fit`, `car-fe-fit`, `deg-iso-fit` | Parameters fitted *outside* dbt, pooled over seasons — a leakage surface dbt tests cannot see |
| Guards | `transform/tests/` (65 singular + schema tests), `ml/src/features.py` audits | **In scope as objects of audit**, see §6 |
| ML consumers | `ml/src/{schema,features,train,evaluate,predict,export_onnx}.py` | The feature contract and the split |
| Shipped surface | `app/src/features/*/queries.ts`, `scripts/export_app_data.py` | App SQL runs in the browser and is **not** covered by the 620 dbt tests |

**Out of scope**

- `ingestion/` correctness against FastF1's API. Treat bronze as given, but **do not treat it as
  correct** — when a defect is already in bronze, say so and stop there (§9's `earliest_point`).
- Model quality, hyperparameters, metric choice. This is a data-truth audit, not an ML review.
- `transform/dbt_packages/` (vendored).
- Anything in `_improvements/reference/` older than its own "measured on" date, except as history.

---

## 2. Standing rules

These are `epistemics.md`'s standing constraints, restated with the audit's specifics.

1. **Read-only, always.** `duckdb.connect(path, read_only=True)`. No `dbt run`, no `dbt build`, no
   `make` target that writes (`coefficients-promote`, `*-fit`, `ml-*`, `app-data`, `dbt-dev` are all
   forbidden). `make dbt-test`, `make data-profile-check` and `make lint-oracle-check` are
   read-only against an existing build and are permitted.
2. **Do not modify the repository.** No fixes, no test files, no `build-log.json` edit, no commit.
   The output is a document plus scratchpad artefacts. Nothing is committed without being asked.
3. **Scratchpad only** for probes and intermediate CSVs. Never `ml/models/*`, never
   `transform/seeds/*`, never warehouse files.
4. **Two gotchas that will cost time.** (a) Staging models are **views over an external glob with a
   relative path** (`../data/bronze/...`), so a query touching `stg_*` must run with cwd
   `transform/` or it dies with `No files found that match the pattern`. Materialized `int_*`/`fct_*`
   tables query fine from the repo root. (b) `data/dev.duckdb` is the dev build; `data/ci.duckdb` is
   built on the tiny fixture set and will not support distributional claims. Say which you used.
5. **Reuse production code paths** for anything ML-side — `ml/src/features.load_features` rather
   than a hand-rolled split. A reimplemented loader is a new instrument with its own bugs.

---

## 3. The evidence standard

`epistemics.md`'s Verified/Assumed line is the whole of this section, applied per finding.

**Every finding carries a verdict, and the verdict is about the evidence, not the vibe.**

| Verdict | Requires |
| :--- | :--- |
| **Definitely wrong** | A query or code path that produces the wrong value, plus the correct value computed independently, plus the line that creates the difference. Reproducible command included |
| **Probably wrong** | The mechanism is traced and the defect follows from it, but the magnitude is not measured, or the correct value needs a source the tree does not hold |
| **Requires investigation** | A named suspicion with the specific query that would settle it. Allowed only with that query written out |

**Two rules that override the generic brief.**

- **Surprising is not wrong.** The brief already says this; here is the concrete case. The mart holds
  **20 races for 2018 and 21 for 2021, against 21 and 22 in bronze** — two seasons each lose one
  race. Before writing that up, check the obvious legitimate cause: 2021 Belgian GP was three laps
  behind the safety car, so `is_valid_lap` (which excludes lap 1 and any lap with track status
  `[4567]`) can legitimately leave that race with zero valid laps and drop it from the mart
  entirely. That is correct behaviour, not a defect — though *silently* dropping a whole event is
  worth a note on its own terms. Find and state the 2018 cause too; do not assume it is the same.
- **No unfalsifiable findings.** "Joins should be checked for cardinality" is not a finding. Name
  the join, the keys, the observed row multiplication, and the query. If a category comes back
  clean, §9's clean-list is where it goes.

**Protocol anchoring.** If you quote a number that exists elsewhere in the tree, say whether your
population matches. Two row counts over different filters are not a disagreement.

---

## 4. Primed findings — traced 2026-09-24

Eight things found while scoping this charter. They are handed over so the audit starts from
evidence rather than from a checklist. **Each needs its blast radius established** — that work is
not done. Verified/Assumed is marked per item.

### 4.1 The `session_type` column the source declares does not exist, and session separation is positional

**Verified.** `src_formula1.yml:16` declares `session_type` on source `raw_laps`. The column is
**absent from every bronze lap parquet** — `select session_type from read_parquet('data/bronze/laps/*/*/*.parquet')`
fails with `Binder Error: Referenced column "session_type" not found`. `stg_laps.sql` neither
selects nor filters it. (`stg_laps_qualifying`, by contrast, *synthesises* `CAST('Q' AS VARCHAR) AS
session_type` at line 25 — a literal, not a read.)

So race-versus-qualifying separation rests entirely on **glob depth**: `raw_laps` is
`laps/*/*/*.parquet` and `raw_laps_qualifying` is `laps/*/*/session=Q/*.parquet`. Nothing asserts
what session a file at race depth contains.

**Currently clean** — 173 race-depth files, 173 `session=Q` directories, no other `session=*`
directory anywhere. **Structurally unguarded**: any ingester writing a practice or sprint file at
race depth silently becomes race laps, and item `02f` (FP1/2/3 ingest) is exactly that change.
*Severity now: low. Severity the day 02f reopens: critical.* Verdict: definitely wrong as a
declared contract; a latent defect as a guard.

### 4.2 The holdout season resolves to a season with no data, and 2025 is in training

**Verified as data and code path; the artefact consequence is Assumed.**

`ml/src/features.py:54-57` — `resolve_holdout_season` returns `SELECT MAX(race_year) + 1 FROM
fct_cliff_prediction_features`. Its docstring reads "Holdout = next (not-yet-ingested) season =
latest ingested + 1. 2025 today (absent from the mart); becomes live the moment 2025 ingests."

Item `12a-1` (LANDED, 2026-09-22) ingested 2025. The mart now holds **2025: 24 races, 22,760 rows**.
So `MAX(race_year)` is 2025 and `holdout_season` is **2026**. Lines 123-128 then split
`train = race_year < 2026` and `holdout = race_year = 2026`:

- training seasons are **2018–2025 inclusive**, 2025 included;
- the holdout frame is **empty**.

The intent recorded in `work/12-season-coverage.md` — "Ingesting 2025 makes 2025 the holdout and
folds 2024 into training with no code change" — is **false as implemented**. The resolver is
off-by-one against its own documented purpose: it names the first *absent* season, which by
construction never has rows. The promise is repeated in `ml/model_card.yml:26` and `:787`,
`README.md:167`, and `ml/tests/test_predict.py:36` ("no holdout rows expected before 2025 ingests"),
so four documents and one test now describe a state the code cannot reach.

**What the audit must establish, and this is the single highest-priority item in the charter:**
whether the shipped v13/v14 artefacts were trained on 2018–2025 with no out-of-sample season, and
therefore whether every published out-of-sample figure is now a cross-validation figure wearing a
holdout's label. Check `ml/models/*manifest*`, the model card, and `evaluate.py`'s split against the
current mart. Do not assume the intent; read what ran.

### 4.3 `circuit_key` is an event slug aliased from `race_id`, and it is the ML cohort key

**Verified.** `stg_laps.sql:22-23` assigns the same source column twice:

```sql
CAST(race_id AS VARCHAR) AS circuit_key,
CAST(race_id AS VARCHAR) AS race_id,
```

`ml/src/schema.py` documents `circuit_key` as "the L0-1 cohort key", and it is an
`IDENTIFIER_COLUMNS` member used for cohort evaluation. But it identifies an **event**, not a
venue — and the tree already knows the difference: `macros/circuit_id_from_name.sql` exists solely
to collapse `british_grand_prix` + `70th_anniversary_grand_prix` (both Silverstone),
`austrian_grand_prix` + `styrian_grand_prix` (both Red Bull Ring), and `mexican_grand_prix` →
`mexico_city_grand_prix` into one `circuit_id`. `transform_gaps.md` finding #3 fixed precisely this
bug in `race_to_track`.

**The audit question:** which consumers of `circuit_key` meant venue and got event? Any
"same circuit, different race" cohort, any per-circuit shrinkage or pooling, and `01b`'s
matched-pair design (whose pre-registration says "every 2024 circuit hosts exactly one race") all
change meaning under the two readings. Enumerate every `circuit_key` group-by in the lineage and
classify each as event-correct or venue-intended.

### 4.4 One constructor under four names, two of which silently get `unknown_pu`

**Verified.** `dim_constructors.sql` hardcodes a 16-row `pu_mapping` and `LEFT JOIN`s it, defaulting
to `'unknown_pu'`. Against the current build:

```
ferrari_pu   : Alfa Romeo, Ferrari, Haas F1 Team, Sauber
honda_pu     : AlphaTauri, RB, Red Bull Racing, Toro Rosso
mercedes_pu  : Aston Martin, Force India, McLaren, Mercedes, Racing Point, Williams
renault_pu   : Alpine, Renault
unknown_pu   : Alfa Romeo Racing, Kick Sauber, Racing Bulls
```

The Sauber entity appears as four distinct `constructor_id` values — `Sauber`, `Alfa Romeo`,
`Alfa Romeo Racing`, `Kick Sauber` — of which two get `ferrari_pu` and two fall to `unknown_pu`,
**despite all four running a Ferrari power unit in every one of those seasons.** The Faenza entity
appears as `Toro Rosso`, `AlphaTauri`, `RB`, `Racing Bulls`; the first three get `honda_pu` and the
fourth falls through.

This is the generic brief's "historical team names merged incorrectly" in its mirror image: the same
constructor is *split* by rename, and the split is filled with a **plausible-looking default** that
a model will read as a real PU family. `dim_constructors`' own header says `pu_family` conditions
`constructor_pace_index` in Layer 04 "on similar-engine teams", so the defect is feature-facing. The
`LEFT JOIN` + `COALESCE` pattern means adding a season can only ever fail silently. Verdict:
definitely wrong. Establish whether `constructor_id` itself (the rename-split) is intended as
season-scoped — it may be correct for pace estimation and wrong for PU grouping, and those need
separate rulings.

### 4.5 `dim_drivers.driver_number` is a lexicographic max described as "most recent"

**Verified.** `dim_drivers.sql` computes `MAX(driver_number) AS driver_number` under the comment
`-- Most recent number (drivers sometimes change numbers)`. Two defects in one line:

- `MAX` is not recency. There is no ordering by year.
- `driver_number` is a **VARCHAR** (`stg_laps` casts `drivernumber AS VARCHAR`), so `MAX` is
  lexicographic.

Observed: `VER → '33'`. Verstappen ran 33 in 2018–2021 and **1** from 2022, so the "most recent
number" is four years stale — and would be wrong even with a correct `MAX`, because `'33' > '1'`
as strings. Blast radius is probably small (establish it — find every consumer of
`dim_drivers.driver_number`), but the pattern is the brief's "driver numbers joined incorrectly
across seasons" and it is live.

### 4.6 The event-corrections seed covers one season, and the correction is applied to all

**Assumed — needs measurement.** `stg_events.sql`'s header: "Currently sourced from the
`raw_dim_events` seed (manual entries for 2021)." `dim_events` lifts the same seed and supplies
`event_severity_multiplier` → `correction_weight`, consumed by `fct_lap_residuals` and
`int_lap_anomaly_flags`.

If the seed is 2021-only, then laps in 2021 are down-weighted for damage/reliability events and
identical laps in every other season are not. That is a **systematic, season-shaped bias in the
training weights**, not a data gap. Measure the seed's coverage by season and by driver, then
measure what fraction of each season's laps carry a non-default `correction_weight`. State whether
the default is 1.0 and whether any consumer treats a missing correction as "no event occurred"
rather than "unknown".

### 4.7 The mart header names a target the ML layer stopped using

**Verified.** `fct_cliff_prediction_features.sql` header: "Targets:
`next_lap_degradation_jump_detrended_s` (PRIMARY, detrended)". `ml/src/schema.py:283`:
`DEGRADATION_TARGET = "next_5_lap_cumulative_jump_s"  # was next_lap_degradation_jump_detrended_s (C1)`.

Doc drift in the header of the model that *defines the label*. Low ML risk on its own — the
`EXCLUDED_LEAKAGE_COLUMNS` set bars every horizon, which is the property `test_feature_contract`
keeps — but it is the file a future auditor reads first to learn what the label is. Sweep the other
mart headers for the same drift as part of §5.

### 4.8 Standings and pit-stop ground truth is ingested and consumed by nothing

**Verified.** `data/bronze/reference/jolpica/` holds `driver_standings`, `constructor_standings`,
`laps`, `pit_stops` and `stints` for **season=2011 … season=2025**. `grep -rn jolpica
transform/models transform/seeds` returns **nothing** — no dbt model reads any of it.

Two consequences, and the second is the useful one:

1. It is the `FreshTyre` pattern `transform_gaps.md` named: data staged and never consumed.
2. **It is an independent oracle this audit should use.** Official classifications, points and pit
   stops from a second provider, covering every ingested season plus six more. §7 lists what to
   reconcile against it.

---

## 5. The real risk surface

Each subsection states what to check *in this tree*, with the model names. Work them in order;
§5.5 and §5.6 are where the yield is.

### 5.1 Session and event identity

- Prove or disprove §4.1 beyond the current file listing: does any bronze lap file at race depth
  contain non-race laps? Check row counts per `(season, race_id)` against scheduled distances, and
  `lap_number` maxima against `data/bronze/schedule/`.
- `race_id` (`2018_4`) is the identity key. Verify it is unique per event per season and that no
  model joins on `race_slug` or `circuit_name` where `race_id` was meant. `stg_results` carries
  both `race_id` and `race_slug` — find every consumer of the latter.
- Weather, track status, race control and telemetry attach by `(race_year, race_id)` plus a time
  axis. Verify no weather row from session Q is joined onto a race lap and vice versa — the
  qualifying chain has its own `stg_*_qualifying` models, so the risk is a missing `session`
  predicate, not a wrong one.
- `dim_events.round_number` comes from a manual seed. Check it against
  `data/bronze/schedule/` rather than trusting it, and find whether anything joins on it.

### 5.2 Drivers and constructors

- §4.4 and §4.5 are the entry points. Beyond them: does any model assume a driver has one
  constructor per season? Mid-season changes in the window (e.g. 2023 AlphaTauri, 2024 Sauber and
  RB seat changes, every reserve-driver appearance) will break that. Query
  `count(distinct constructor_id)` per `(driver_id, race_year)` and per `(driver_id, race_id)` — the
  second must be 1 everywhere, and if it is not, that is a definite defect.
- `dim_drivers` derives `debut_year` from **available data**, so it means "first season in this
  dataset", not "F1 debut". Check no consumer reads it as experience.
- Nationality is absent from both dimensions (the `dim_drivers` header says so). Confirm nothing
  fabricates it.
- Reserve/substitute drivers: find drivers with very few races and check they are not being shrunk
  toward a mean that then reads as a real skill estimate. `bayesian_shrinkage.sql` and the
  `assert_affinity_min_races` test are the relevant guards — verify the floors actually bind.

### 5.3 Classification and status

Low-yield here by construction (the label is not a finishing position), so bound the effort. Check:

- `stg_results`' three-way split — `is_classified`, `is_dnf`, `dnf_cause` — is mutually consistent
  and exhaustive. The logic keys on `TRY_CAST(classifiedposition AS INTEGER) IS NOT NULL` plus
  `status NOT LIKE '%Lap%'`. Find every distinct `status` value in bronze and classify each by hand
  against that expression. `'%Lap%'` is a substring match — check nothing else contains "Lap".
- Disqualifications: `dnf_cause` routes `disqualif|withdr|did not` to `'non_classified'` **only when
  `classifiedposition` does not parse**. A DSQ that retains a numeric classified position would be
  read as a normal finisher. Check whether any exists in the window.
- Whether `is_dnf` and `int_stint_end_regime`'s `retirement` cause agree. They are derived
  independently and both feed stint-life censoring.

### 5.4 Points and standings

There is nothing to recalculate in `transform/` (§0). Do this instead:

- Confirm the absence, with the grep, and state it.
- Establish whether `stg_results.points` reaches **anything** — any mart, any app query, any
  exported parquet. If it does, that consumer is now in scope and the season-correct scoring system
  (2018 vs 2019+ fastest-lap point, 2010–2024 top-10 table) becomes a real check.
- Check `app/src/features/ghost-race-standings/` — the name promises standings. It reads
  `int_driver_circuit_era_affinity` and `int_driver_race_skill_loro`, i.e. equal-car pace, not
  points; confirm that and confirm the app's methodology text does not claim championship points it
  does not compute. Note that `int_driver_race_skill_loro` is a **barred leakage column** in the ML
  contract (`schema.py`, correction `00c`) and is nonetheless shipped to the browser — that is
  legitimate (a descriptive surface, not a predictor) but it must be labelled as contemporaneous,
  not predictive. Verify the app says so.

### 5.5 Temporal leakage — the priority

The tree has already found and fixed four leakage defects (`08e` thermal baseline, `08f` pooled
cross-season statistics, `02a`/`02g` corner field median, `02d` SC hazard). Assume the class is not
exhausted. Search these shapes, in this order:

1. **Every window function in `int_*`.** For each, state the frame and whether the scored row is
   inside it. `ROWS BETWEEN n PRECEDING AND CURRENT ROW` includes the current row — legitimate for a
   *state* feature (fuel, tyre age), leakage for a *baseline* the current lap is compared against.
   `08e` was exactly this distinction.
2. **Offline fits, which dbt tests cannot see.** `data/fits/constructor_car_fe.parquet`,
   `degradation_isotonic.parquet`, and the `seeds/compound_cliff_params.csv` fitted by
   `make coefficients-fit`, are estimated by **pooling the whole window** and then joined onto every
   lap, including the laps that produced them. Establish for each: what population was it fitted on,
   does it include the holdout season, and is the resulting feature therefore contaminated. This is
   the highest-probability untouched leakage surface in the tree, because `audit_forward_window`
   reads compiled dbt SQL and a parquet fit is not compiled dbt SQL.
3. **Cross-season pooled statistics** that `08f` rebuilt — verify the rebuild covers every instance,
   not the ones that were found. `int_driver_circuit_era_affinity`, `int_era_normalized_driver_rating`
   and `int_sc_hazard_history` are the era/history-shaped models; check each for a season-lag rule.
4. **The label's own lineage.** `next_5_lap_cumulative_jump_s` looks forward five laps by
   construction. Verify no *feature* shares a CTE with it, and that the detrending
   (`int_lap_residual_stint_detrend`, `drift_s_per_lap`) is fitted per stint on laps at or before
   the scored lap. `drift_s_per_lap` is already barred as a feature for exactly this reason —
   check nothing else derived from it survives.
5. **The split.** §4.2. Also verify `_build_encoders` runs on training rows only (it appears to) and
   that `is_training_eligible` is not itself a function of the label.
6. **Overlapping target windows.** A 5-lap cumulative target on consecutive laps means adjacent rows
   share four laps of outcome. `schema.py` mentions "thin overlapping windows" in the ceiling
   arithmetic. Establish whether the season-grouped CV folds can leak through this overlap at a
   season boundary, and whether within-season fold splits would.

For every feature in the 39-column contract, produce the table the brief asks for: **effective
information timestamp** vs the scored lap. That table is the single most valuable artefact this
audit can produce.

### 5.6 Joins, grain, duplication

State the intended grain for every model from its header (they all declare one) and verify it:

| Model | Declared grain |
| :--- | :--- |
| `stg_laps` | one row per recorded race lap |
| `stg_results` | one row per driver × race |
| `stg_pits` | one row per pit stop (guarded by `assert_pit_stop_grain`) |
| `fct_cliff_prediction_features` | one row per valid race lap (`lap_id` unique, tested) |
| `fct_stint_features` | one row per stint |
| `fct_ghost_car_pace` / `fct_ghost_race_finish` | one row per (host constructor, race, driver) scenario |
| `int_*` | per header — several are lap-grain, several are weekend- or circuit×season-grain **broadcast onto laps** |

The broadcast ones are where duplication hides. `marts/schema.yml` already annotates some as
"Weekend-grain (race_year, race_id, driver_id), broadcast onto every lap of the weekend" — verify
each broadcast join cannot multiply rows, and that the `lap_id` uniqueness test is the only thing
standing between a many-to-many and a silently inflated training set. Specifically:

- Count rows before and after every join in the mart's CTE chain. `fct_cliff_prediction_features`
  joins at least six `int_*` models on `lap_id`; a duplicate `lap_id` in any one of them multiplies.
- `lap_id` is `CONCAT(season, race_id, driver, lap_number)` and `race_id` already contains the
  season (`2018_4`), so the key is redundant but not ambiguous — confirm no delimiter collision.
- Find every `LEFT JOIN` whose null branch is then `COALESCE`d to a number. That is §5.8.
- Find every `INNER JOIN` in the mart chain and state which rows it silently drops. The 2018/2021
  missing races (§3) may be one of these rather than the validity filter.

### 5.7 Units and physical plausibility

- Nanosecond→second conversion (`/1e9`) appears in `stg_laps`, `stg_results`, `stg_pits`,
  `stg_sector_times`, `stg_laps_qualifying`. Verify every duration column is converted exactly once
  and none twice. A doubly-divided lap time is ~85 nanoseconds and would look like a null-ish
  outlier, not an error.
- `stg_results.time_or_gap_s` is **the winner's total race time for P1 and the gap for everyone
  else** — one column, two meanings. Verify no consumer averages it or treats it as a single
  quantity.
- `stg_pits.pit_duration_s` spans pit entry to exit, not stationary time, and its header states
  **388 of 5,109 stops exceed 60 s** (red flags, garage returns). Verify every consumer filters, and
  that no negative or zero durations exist.
- Distributional sanity, against `transform/tests/data_profile.baseline.json`: lap times within
  plausible per-circuit bounds, speeds positive, `tyre_life` non-negative and monotone within a
  stint, `fuel_mass_kg` monotone decreasing within a stint and non-negative, ambient/track temps in
  range, `age_in_stint` ≥ `lap_in_stint` never violated.
- Tyre compound sequence: `normalize_compound` maps the 2018 SUPERSOFT/ULTRASOFT/HYPERSOFT family
  (`08a` backfilled `dim_compounds_season` for these). Verify no 2018 compound silently becomes a
  modern C1–C5 code, and that `int_stint_geometry`'s `compound_code` is NULL for 2018 exactly as
  `assert_stint_geometry_2018_compound_code_null` claims — then check that the NULL is not
  downstream-filled.

### 5.8 Imputation and plausible defaults

The brief's strongest category for this tree. `08q` already found one instance — `theta_air` was a
`COALESCE` default, not an estimate, and the app billed drivers 0.5 s/lap off it. Find the rest:

- Grep every `COALESCE`, `IFNULL`, `nullif`, `fillna` and `LEFT JOIN … ELSE` in `transform/models/`
  and `ml/src/`. For each, state what the default means when it fires, how often it fires, and
  whether a consumer can tell it apart from a measured value.
- `MISSING_ORDINAL` in `ml/src/schema.py` is the categorical sentinel. Verify it cannot collide with
  a real encoded level, and that an unseen-at-scoring category maps to it rather than to level 0.
- Continuous features keep native NaN for XGBoost. Verify no upstream model zero-fills a continuous
  feature before it reaches the mart — `marts/schema.yml` has a comment about columns "zeroed at
  source on neutralised laps", which is exactly the pattern to inspect: a zero that means "no dirty
  air" is indistinguishable from a zero that means "not measured".
- `pu_family → 'unknown_pu'` (§4.4) and `correction_weight`'s default (§4.6) are two known
  instances; treat them as the pattern, not the total.

### 5.9 The shipped surface

The 620 dbt tests stop at the warehouse. Two things escape them:

- **App SQL.** `app/src/features/*/queries.ts` runs its own SQL in DuckDB-Wasm against exported
  parquet. Any aggregation, filter or join there is untested by dbt. Read every query for the same
  defect classes, especially anything that re-derives a ranking or an aggregate the warehouse
  already computes differently.
- **ONNX export.** `ml/tests/test_onnx_parity.py` and `make app-parity` prove booster == ONNX. What
  they cannot prove is that the browser feeds the model the same *feature values* the warehouse
  computed. Verify the app's feature assembly matches `FEATURE_COLUMNS` order, the encoder maps in
  `app/public/models/encoders.json` match `ml/models/encoders.json`, and the per-target mask is
  applied identically.

---

## 6. Audit the guards

The 620 tests, the two Python audits and the leakage column set are **objects of this audit**, not
its foundation. Four named structural weaknesses to verify and extend:

1. **`EXCLUDED_LEAKAGE_COLUMNS` is a name-set intersection.** `test_features.py` computes
   `set(X.columns) & EXCLUDED_LEAKAGE_COLUMNS`, so **an unlisted leaky column passes straight
   through**. `schema.py` says this in its own comment about the three `driver_skill_loro_*`
   columns: they were unlisted, and the mart merely happened not to carry them, "which made the
   safety accidental rather than designed." The guard cannot catch a column nobody thought of.
   Propose a guard with the opposite polarity — an allow-list, or a provenance check that every
   feature's lineage excludes the label's CTEs.
2. **An identity test can be tautological.** `assert_lap_7term_identity` and
   `assert_additive_identity` check that seven components sum to `pace_delta_s`. If the seventh
   component (`driver_skill_residual_s`) is *defined* as the remainder, the identity closes by
   construction and the test proves arithmetic, not correctness. Read
   `int_lap_residual_decomposed.sql` and state which of the two it is. If it is definitional, the
   README's headline claim ("an enforced invariant is worth more than a claimed one") is weaker than
   it reads, and the real invariants are the *component-level* ones
   (`assert_fuel_curve_monotonicity`, `assert_constructor_coefficient_signs`, and so on). This is a
   finding about the tree's epistemics, and it belongs in the report.
3. **Duplicated parameters between a model and its test.** `assert_no_future_leakage.sql` documents
   its own copy of `min_observations=1` and warns that it "must move with any floor change in
   `int_lap_thermal_proxy.sql`". Find every other test that re-states a model constant rather than
   reading it, and list them as a drift surface. `08i` already flagged this one.
4. **`audit_forward_window` / `audit_aggregation_scope` read compiled dbt SQL** from
   `transform/target/`. They therefore cannot see: an offline parquet fit (§5.5.2), a seed, app SQL,
   or a model that is not on the mart lineage (`_mart_lineage` bounds the scope, and
   `survey_aggregation_scope` is explicitly report-only/off-lineage). Establish exactly what is
   outside their reach and say so — a guard's *coverage boundary* is as important as its logic.
   Also check whether `_declared_known_leaks` holds exemptions that have outlived their reason.

Then: run the guards. `make dbt-test`, `python -m ml.src.features --check`,
`make data-profile-check`, `make lint-oracle-check`. Report what passes, what fails, and — the
point of this section — **what passing does and does not establish.**

---

## 7. Oracles

Independent ground truth already in the repo. Use it; do not hand-check against memory of F1
results.

| Oracle | Location | Reconcile |
| :--- | :--- | :--- |
| Jolpica standings | `data/bronze/reference/jolpica/{driver,constructor}_standings/season=2011…2025` | Official points and championship position per round. The check `transform/` cannot do internally (§5.4) |
| Jolpica pit stops | `…/jolpica/pit_stops/` | `stg_pits`' stop count and lap number per driver per race, against a second provider. Duration definitions differ — compare counts and laps, not seconds |
| Jolpica laps / stints | `…/jolpica/laps/`, `…/stints/` | `03b` measured 84.2% exact stint-boundary match against 2018 FastF1. Use the same method on other seasons to bound `int_stint_geometry`'s error |
| FastF1 results | `data/bronze/results/` | `stg_results`' classification split, grid and finish positions |
| Schedule | `data/bronze/schedule/` | Round numbers, event names, dates, circuit — against `dim_events`' manual seed and against `race_id` |
| Pirelli compound allocation | `seeds/tyre_allocations.csv`, hand-sourced per `08d` | Compound identity per race 2019+ |
| Data profile baseline | `transform/tests/data_profile.baseline.json` | Row counts, null rates, means — build-over-build drift |
| Output oracle snapshot | `make lint-oracle-check` | Byte-stability of every `fct_*` output |

Reconciling `stg_results` against Jolpica standings is the closest this repository can come to the
generic brief's "recalculate the championship", and it is worth doing once: if FastF1's per-race
points sum to the official standings for every season, the results table's classification and points
columns are jointly validated by an independent source.

---

## 8. F1 invariants, re-specified

The generic list, with the ones that have a referent here, each as a checkable predicate. Exceptions
noted — a violation is a finding only if the exception does not apply.

| Invariant | Exception that makes a violation legitimate |
| :--- | :--- |
| Exactly one `finish_position = 1` per `(race_year, race_id)` in `stg_results` | None. A tie is impossible |
| No driver appears twice per `(race_year, race_id)` in `stg_results` | None |
| `count(distinct constructor_id) = 1` per `(driver_id, race_id)` | None in this window. A mid-weekend seat change would be source-supported but has not occurred 2018–2025 |
| `is_classified`, `is_dnf` are not both true; `dnf_cause` is non-null iff not classified and not a lapped finish | None — this is `stg_results`' own definition, so a violation is a logic error |
| `lap_number` ≥ 1, contiguous per `(driver_id, race_id)`, max ≤ scheduled laps | Red-flagged races restart lap numbering in some sources; check before flagging |
| `lap_in_stint` ≥ 1 and contiguous; `stint_number` increases with `lap_number` | A stint-boundary miss in reconstruction (Jolpica seasons) is known and quantified |
| `tyre_life` non-decreasing within a stint | Used tyres start `tyre_life > 0`; `is_fresh_tyre` distinguishes. A *reset* mid-stint is a defect |
| `fuel_mass_kg` non-increasing within a race, ≥ 0 | None if modelled; it is a model, so check the model's floor |
| Pit stop `pit_in_lap_number` within [1, race laps]; `pit_out_lap_number = pit_in + 1` or NULL | NULL is legitimate for the 227 documented stops with no out-lap (retired in pit lane, or race ended) |
| `pit_duration_s > 0` | The 388 stops > 60 s are legitimate (red flag / garage); a *negative* duration is not |
| A neutralised lap is never `is_valid_lap` | None — `is_valid_lap` is defined to exclude track status `[4567]` |
| A whole event never silently disappears from the mart | 2021 Belgian GP plausibly legitimate (§3). Any *other* disappearance needs a stated cause |
| Weather rows attach to the same `(season, race_id, session)` as the lap | None |
| Qualifying models never read `stg_laps`; race models never read `stg_laps_qualifying` | None. Check both directions |
| `pu_family` is identical across every name of the same constructor entity | **Currently violated** — §4.4 |

Invariants from the brief with **no referent here** — state this and move on: points-per-position
correctness, sprint double-counting, fastest-lap point eligibility, championship tie-breaks,
cumulative-points-by-round, qualifying-position-used-as-finishing-position (no model consumes either
as a feature).

---

## 9. Deliverable

One document, written to `scratchpad/` and handed over — **not** committed, and **not** filed as a
work item (that needs a `build-log.json` edit, which §2 forbids). If findings justify a work item,
*propose* it at the end with a suggested group, stage and blocker, and let the user place it.

Structure, in this order:

1. **Verdict** — safe for training / partially trustworthy / unsafe, in one sentence, with the two
   or three findings that decide it. §4.2 alone may decide it.
2. **Findings**, ranked by severity × blast radius. Per finding:
   `severity · file:line · column or transformation · intended grain · observed behaviour ·
   reproducible query · why it is wrong · verdict (§3) · earliest point in the pipeline ·
   isolated or systematic · ML impact · recommended fix · the test that would have caught it ·
   how I could be wrong.`
   The last field is mandatory. A finding with no stated falsifier has not been thought through.
3. **Verified / Assumed**, as two explicit lists, per `epistemics.md`. An empty Assumed list means
   the audit did not look hard enough.
4. **Clean list** — every category checked with no defect found, each with the query or grep that
   establishes it. This is as valuable as the findings and is the part audits usually skip.
5. **Information-timestamp table** for all 39 contract features (§5.5).
6. **Grain table** — declared vs actual, per model (§5.6).
7. **Guard coverage map** — what each guard in §6 does and does not reach.
8. **Recommended tests**, in the tree's existing style: singular tests as
   `transform/tests/assert_*.sql` returning failing rows, schema tests in the relevant `schema.yml`,
   Python tests under `ml/tests/`. Each specifies: what it checks, which model, what a failure
   means, **and whether it blocks the build**. Follow `assert_no_future_leakage.sql`'s standard —
   an independent re-derivation, not a restatement of the model's own logic.
9. **Remediation plan**, four tiers: before training · before evaluation · lower-risk cleanup ·
   post-build monitoring. Order by whether a published number moves.

Cite `file:line` throughout. A finding without a line number is a suspicion.

---

## 10. Phases

Bounded so the audit does not become the programme. Each phase ends with its findings written down
before the next begins.

| Phase | Work | Ends when |
| :--- | :--- | :--- |
| **A** | Settle §4.2. Read the artefacts, the manifest and the model card against the current mart | The training/holdout question is answered yes or no |
| **B** | Run every guard (§6), record pass/fail and coverage boundaries | The guard coverage map exists |
| **C** | §5.5 leakage sweep — windows, then offline fits, then the information-timestamp table | The 39-row table exists |
| **D** | §5.6 grain and duplication; §5.8 defaults | Grain table exists; every `COALESCE` classified |
| **E** | §5.1–5.3, §5.7 identity and units; reconcile against §7 oracles | Clean list is complete |
| **F** | §5.9 shipped surface | App SQL and ONNX feature assembly read |
| **G** | Write §9 | — |

Phase A is the one that cannot be skipped. If it comes back the way §4.2 suggests, say so
immediately rather than at the end — it changes what every other phase is for.

---

## 11. Non-goals

- Fixing anything. This audit produces a document.
- Re-litigating settled rulings. `00c` (LORO barred), `02a` (the 5-lap bucket), `08q` (`theta_air`),
  `08l`/`08m` (the seed compound curve) are closed with recorded reasoning. Cite them; reopen one
  only with new evidence, and say what the new evidence is.
- Model quality. A well-specified model learning a true relationship badly is not this audit's
  concern.
- Bronze ingestion correctness against FastF1's API.
- Finding something. A clean audit with a complete §9.4 clean list is a successful audit. Manufacture
  nothing.
