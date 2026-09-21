# 00 — Standing corrections

**Group:** 00 · **Depends on:** nothing · **Cost:** hours

Three stale or wrong facts found 2026-09-07 that other work items cite. None is research;
all three are cheap; two of them silently break an item further down the ladder if left.

---

## 00a — The feature count is 33, not 24

**Objective.** Every document in `reference/` says the contract is 24 features. It has been
**33** since v11.

**Verified.** `ml/src/schema.py`'s `FEATURE_GROUPS` sums 4 (`stint_position`) + 7 (`compound`)
+ 5 (`cliff_prior`) + 4 (`thermal`) + 4 (`dirty_air`) + 9 (`proximity`) = 33, and
`MODEL_VERSION_DEFAULT`'s note records the v11 move as "contract, 24 -> 33".
`PER_TARGET_FEATURE_MASK` masks only `stint_length_laps`, for `stint_life_regressor`, and that
column is not in `FEATURE_COLUMNS` anyway — so all three degradation quantiles see all 33.

**Why it is not cosmetic.** `reference/ml_research_program.md` §3b's fix 2 is *"match in the
model's own feature space, not hand-picked keys"*, and its closing command specifies "the
scaled 24-feature space". Building that space from 24 columns drops `proximity` — the nine
columns that were the v11 win — and reintroduces a milder form of the failure mode §3a found.
The same section's §3a parenthetical also names "throttle decay, braking drift", which are
`racing_line` candidates that were measured and **not shipped**; they are not in the contract
at all.

**Method.**
```bash
grep -rn "24 features\|24-feature\|24 columns\|24 -> 33\|42 columns" _improvements/reference/ docs/
```
Correct each hit, and at each one check whether the surrounding argument survives the change
rather than only the number.

**Definition of done.** No document claims a 24-column contract; `reference/ml_research_program.md`
§3a/§3b and its closing command name 33 and drop the two non-contract feature names; the
history entry records which arguments changed as well as which numbers.

---

## 00b — §1a's "no safety-car signal exists" claim is false

**Objective.** `reference/ml_research_program.md` §1a caps the stint-life target at 0.80–0.85
of attainable on this reasoning:

> *"Remaining stint life is set partly by pit-wall strategy calls and safety-car timing —
> events that are not a tyre-degradation question at all and carry no signal in any feature
> this warehouse could build."*

**Verified.** The clause after the dash is wrong. `int_sc_hazard_history` holds
`sc_hazard_per_lap`, `vsc_hazard_per_lap`, `any_hazard_per_lap` and empirical-Bayes-shrunk
variants of each, for 36 circuits, estimated from `stg_track_status` deployment events with
racing-lap exposure from `stg_laps`.

**Scope of the correction.** §1a marks the paragraph "Inference, not measurement", so this
corrects an **Assumed** claim, not a Verified one. The 0.80–0.85 range was never measured; it
should be either deleted or replaced with a measurement, since the SC/VSC share of stint ends
*is* computable from `stg_track_status` now that it has landed.

**Definition of done.** §1a no longer asserts the signal cannot exist; it either cites
`int_sc_hazard_history` and states the cap as open, or replaces the range with a measured
SC/VSC share of stint ends. Work item `02d` is unblocked.

---

## 00c — LORO leakage ruling · RULED 2026-09-07

**This item was written on a false premise, and the premise is the whole item.** It is kept
here in corrected form because the mistake is instructive: an acronym was read, not traced.

**What it claimed.** That `int_driver_race_skill_loro.driver_skill_loro_s` is
*leave-one-race-out* — "precisely the construction that makes a skill term admissible in
principle — the focal race is excluded from the estimate that scores it" — and that D1 was
therefore a genuine judgement call between losing a legitimate feature and walking past a
leakage list.

**What the model actually does.** `LORO` there is **leave-one-DRIVER-out**. The model's own
first line says so: *"De-confounded absolute driver skill: leave-one-driver-out (LORO) car
baseline."* A driver is graded against the **other same-car drivers in the same race** —
for a two-car team, his teammate. The focal race is never excluded. The output is

```sql
d.driver_p20_pace_delta_s - d.loro_car_baseline_s AS driver_skill_loro_s
```

where `driver_p20_pace_delta_s` is the focal driver's own 20th-percentile clean-lap pace delta
**in the race being predicted**. Every CTE groups by `(race_year, race_id, ...)`; there is no
cross-race window anywhere in the file.

**Verified by construction, not by reading.** A driver with exactly one race in the entire
table still receives a non-NULL value — `DOO` (2024_24) = 0.0468 from 45 clean laps, `AIT`
(2020_16) = −1.3164 from 61. Under leave-one-race-out there is no other race to estimate from,
so the value would have to be NULL. It is not. The column is contemporaneous with the target.

**Ruling.** Barred, and not on the principle D1 was framed around. The column is built from
the focal race's own lap times, so for a model predicting that race's degradation it is
textbook leakage. `driver_skill_loro_s`, `driver_skill_field_s` and `driver_skill_loro_mean_s`
are now named in `EXCLUDED_LEAKAGE_COLUMNS` with the trace recorded beside them.

**A guard gap found on the way.** The leakage test is a set intersection on names —
`set(X.columns) & EXCLUDED_LEAKAGE_COLUMNS` (`ml/tests/test_features.py:45`) — so any column
not on the list passes straight through. These three were not on it. Nothing leaked, because
`fct_cliff_prediction_features` (64 columns) does not carry them; but that made the safety
**accidental rather than designed**, and a later session joining the rating chain into the mart
would have met no guard at all.

**What remains open, and it is not this.** Whether a *genuine* leave-one-race-out skill term
would be admissible is still unanswered — because nobody has built one. D1 as posed cannot
answer it, since its example turned out not to be an instance of the thing. If such a column is
ever built, it needs its own decision and its own trace.

**Definition of done.** Met: ruling written into `schema.py` beside `EXCLUDED_LEAKAGE_COLUMNS`;
the three columns barred; `int_synthetic_teammate` stays barred regardless, since
`driver_skill_proxy_s` is not leave-anything-out.

---

## 00d — `corner_skill_index` counts braking earlier as skill

**Found 2026-09-18** by the build-order audit, which ran the falsification `06c`'s own checklist
named and left unrun ("inspect SQL for braking z-score sign convention"). `06b` supplied the
candidate.

**Verified from source.**

- `int_corner_skill_residuals.sql:170-178` — `braking_loss_s = (own braking_point_m − field
  median) × dt_per_dm`. `braking_point_m` is the first braking sample's distance along the lap, so
  **positive = braking later = faster**.
- The other two phases are built the other way round: `mid_corner_residual_s = (field v_min − own
  v_min)` scaled by the field's apex speed, and `exit_residual_s = (own throttle_point_m − field
  median) × dt_per_dm`. **Positive = worse** for both.
- `mart_corner_skill_driver.sql:316-317` — `corner_skill_index = braking_skill_z +
  mid_corner_skill_z + exit_skill_z`, ordered `ASC` (lower = better). Nothing in `standardized`
  or upstream negates the braking term.

So the braking phase enters the index with the wrong sign. `06b` reached the same conclusion
independently, from a treatment whose physical direction is known a priori: dirty air produces
negative `braking_loss_s` in every corner class and both eras, and dirty air can only make a driver
brake earlier.

**Blast radius.**

- **The app.** `app/src/features/corner-phase-skill/queries.ts:37` ranks drivers by
  `corner_skill_index ASC`, and `transform.ts` passes the values through unchanged. The shipped
  leaderboard is built on the inverted term.
- **`06c`.** Its headline anomaly — VER braking `+0.0745` against PER — reads as *braking later
  than the same-car baseline*: the received wisdom, not a contradiction of it.
- **`corner_residual_total_s`** sums the three phases with one sign, so it is not "seconds lost"
  either. `06b` noticed and moved its headline to the mid phase.
- **`02c`'s mart-only braking aggregates** in `int_lap_corner_inputs` inherit the convention. A
  monotone sign flip leaves a tree's predictions unchanged, so `02c`'s arm results are unaffected in
  substance. Only how they read changes.

**The ruling this item makes.** There are two places to fix it. (a) At the
source: redefine `braking_loss_s` as `(field median − own) × dt_per_dm`, so all three phases read
"positive = loss" and `corner_residual_total_s` means what its name says. (b) In the mart only:
negate the braking z inside the index. (a) is the cleaner contract but touches `02c`'s columns and
the residual total. (b) is one line, but it leaves a column named "loss" that measures a gain.
Argue it in writing before editing, as `08m` did.

---

### The ruling (2026-09-20): **(a), at the source.**

**The consumer trace first**, because the argument for (b) was entirely "(a) might silently flip
the meaning for a consumer that relies on the old sign". Every consumer of `braking_loss_s` in the
repo was enumerated by grep over `transform/`, `ml/`, `app/` and `scripts/`, and read:

| Consumer | What it does with it | Effect of (a) |
| :--- | :--- | :--- |
| `mart_corner_skill_driver.sql:77,108,129,153,169,203,235,238,277` | `SUM` → LORO subtraction → symmetric winsorize → `AVG` → `/ STDDEV` | **Exact sign flip.** Every step is linear or odd; `STDDEV` and the `COUNT`-based cell floors are invariant. This is the bug site. |
| `int_lap_corner_inputs.sql:90,91,92` | `AVG` / `STDDEV_SAMP` / **`MAX`** | mean flips sign, sd unchanged, **`MAX` does not flip** — it becomes `−MIN(old)`. The one non-monotone consumer in the tree. |
| `fct_cliff_prediction_features.sql:106-108,360-362,678-680` | carries those three through unchanged | inherits the above; **mart-only, not a model input** (see next row) |
| `ml/src/schema.py` `FEATURE_COLUMNS` | — | **zero corner columns.** Verified this session: 32 columns, none matching `corner` or `brak`. `grep -n corner ml/src/schema.py` returns nothing. No model retrains. |
| `int_corner_skill_residuals.sql:226-228` | `corner_residual_total_s = braking + mid + exit` | becomes a genuine "seconds lost" total for the first time — the defect `06b` worked around by moving its headline to the mid phase |
| `transform/tests/assert_corner_closure.sql:13` | identity on the three columns' own sum | sign-agnostic, still passes |
| `transform/tests/assert_corner_trailing_window_no_forward_reach.sql:99` | `braking_loss_s IS NOT NULL` on lap 2 | NULL-pattern only, sign-agnostic |
| `transform/tests/assert_corner_inputs_lap_grain_closure.sql:29` | `COUNT(braking_loss_s)` | count only, sign-agnostic |
| `app/src/features/corner-phase-skill/{queries,transform,page}.tsx` | reads `mart_corner_skill_driver`'s published columns; `transform.ts:16-17` is `rows.map((r,i)=>({rank:i+1,...r}))` | **no app code change needed** — see below |
| `app/src/features/query-lab/examples.ts:49-54` | example SQL, `ORDER BY corner_skill_index ASC` | still correct once the index is correct |
| `app/src/features/corner-phase-skill/transform.test.ts:5-28` | hard-coded literal rows | not warehouse-coupled |
| `ml/tests/test_features.py:119-131` | a *synthetic SQL string* reproducing the old block-bucket shape for the aggregation auditor | not a consumer of the column |
| `scripts/arms_02c_corner_inputs.py:56-62` | `02c`'s arm definitions over the mart columns | the arms are already declared **void** (build-log `02c`: "THE EVIDENCE BASE IS VOID, not merely stale") and must re-run; `00d` is already in `02c`'s `depends_on` for exactly this |
| `_improvements/implementations/06b/`, `06c/` | finished throwaway analysis artefacts | not re-run by this item |

**Nothing relies on the old sign.** The only consumer whose *values* move by more than a sign flip
is `corner_braking_loss_max_s`, and it is mart-only, outside `FEATURE_COLUMNS`, and belongs to an
arm whose evidence base is already void. So the "(b), because some consumer depends on the old
sign" branch is closed on evidence: there is no such consumer.

**Three reasons for (a) over (b), in order of weight.**

1. **(b) breaks an arithmetic identity the app displays.** `page.tsx:28-60` renders `braking_skill_z`,
   `mid_corner_skill_z`, `exit_skill_z` *and* `corner_skill_index` side by side, under a legend that
   says "Negative z-scores = faster than field average for that phase" (`page.tsx:79`) and "Skill
   Index sums all three phases". Negating only inside the sum makes the printed index **not** the
   sum of the three printed columns, and leaves the braking column's legend false. (b) is therefore
   not "one line and no app change" — it is one line plus an app-side fix plus a permanently
   surprising table. (a) needs no app change at all, which is the point below.
2. **The column's own name asserts (a).** `braking_loss_s` under (b) keeps measuring a gain. Every
   future reader, every future mart, and `corner_residual_total_s` itself inherit a column that
   means the opposite of its name. That is the defect class this tree exists to stop, not a style
   preference — `06b` already lost its headline to it once.
3. **(a) is the house convention, already in the feature contract.** `int_lap_telemetry_aggregates.sql:274-280`
   defines the telemetry-cliff group as "positive = fading vs own early-stint baseline" and writes
   `braking_point_drift_m = base_brake_onset_m − lap_brake_onset_m` — **(baseline − own)**, which is
   exactly fix (a)'s orientation, on the repo's *other* braking-vs-baseline residual. The corner
   model is the outlier, not the proposal.

**The cost of (a), stated rather than discovered later.** It touches four models
(`int_corner_skill_residuals` → `int_lap_corner_inputs` → `fct_cliff_prediction_features`, plus
`mart_corner_skill_driver`; `dbt ls --select int_corner_skill_residuals+` returns exactly those
four). `fct_cliff_prediction_features` is in the mandatory byte-stable `fct_*` subset, so
`transform/tests/model_hashes.baseline.json` must be re-snapshotted from a `--target ci` build, and
`transform/tests/data_profile.baseline.json` from `dev`. Both are documented, deliberate
regeneration steps (`snapshot_model_hashes.py`'s own docstring: "regenerate + commit it when model
*logic* changes intentionally"). (b) would have avoided both — that is its entire remaining
advantage, and it is not worth a column that lies about its name on a public page.

**What actually changed.**

- `int_corner_skill_residuals.sql:176-177` — `(ck.braking_point_m − fm.field_corner_braking_point_m)`
  → `(fm.field_corner_braking_point_m − ck.braking_point_m)`, with the convention stated in the
  model header.
- `transform/tests/assert_corner_skill_sign_convention.sql` — new singular test, two assertions
  (below).
- `schema.yml` descriptions in both `intermediate/` and `marts/`.
- Both baseline snapshots regenerated.

**The direction test, and why it is not vacuous.** `assert_corner_skill_sign_convention.sql` pins
the direction without re-deriving the median it is testing. Within one `(race_year, race_id,
corner_name, lap_number)` group every row shares one field median `M`, and `dt_per_dm > 0`, so the
*sign* of `braking_loss_s` is a step function of `braking_point_m` at `M`. The test joins
`int_corner_metrics` back on and asserts that no group contains a row with `braking_loss_s > 0`
(claimed to have lost time) at a *later* braking point than some row with `braking_loss_s < 0`
(claimed to have gained it). Measured on `dev.duckdb` before the fix: **98,769 violating groups out
of 98,769 groups that contain both signs — a 100% failure rate.** After: 0. A second assertion
pins the mart, `corner_skill_index = braking_skill_z + mid_corner_skill_z + exit_skill_z` within
rounding, which is the identity the app prints and the one option (b) would have broken.

**The app needs no code change.** Verified by reading the whole feature: `queries.ts:25-38` selects
the mart's columns and orders by `corner_skill_index ASC`; `transform.ts:16-17` adds a rank and
spreads the row unchanged; `page.tsx` renders them. Every semantic the page states — "negative =
faster", "lower index = faster", "index sums all three phases" — becomes **true** once the mart is
correct, and was false only because of the warehouse. The one app-side action is a data refresh
(`make app-data`), not an edit. `app/src/features/corner-phase-skill/transform.test.ts` uses
literal fixture rows and is unaffected.

**Definition of done.**

- ✅ The sign convention is ruled and argued in writing — above.
- ✅ All three phases share one convention in whatever the index sums — fixed at the source, so the
  three `*_residual_s` columns, `corner_residual_total_s`, the nine `02c` aggregates and the mart
  all share it, not just the index.
- ✅ `mart_corner_skill_driver` is rebuilt and its before/after reported — see the table below. This
  also discharges `02g`'s one outstanding clause.
- ✅ A dbt test pins the direction — `assert_corner_skill_sign_convention.sql`, shown non-vacuous at
  98,769/98,769.
- ✅ The `schema.yml` descriptions of `braking_loss_s` and `corner_skill_index` state the direction.
- ✅ The app page is re-checked against the rebuilt mart — no code change required; see above.

### Before / after — `mart_corner_skill_driver`

Rebuilt on `data/dev.duckdb`, 141 driver-seasons (139 scored; `NOR 2019` and `SAI 2019` hold a
NULL index at `exit_cells_n = 21`, below the 30 floor, before and after). This is also `02g`'s
outstanding clause discharged: the mart re-run whose output change was never reported.

**Column level.** Exactly the braking family moves, and it moves as an exact sign flip — every step
from `braking_loss_s` to `braking_skill_z` is linear or odd (`SUM` → LORO subtraction → symmetric
winsorize → `AVG` → `/ STDDEV`), and the `STDDEV` divisor, the standard errors and all three cell
counts are invariant. Verified row by row, not argued:

| Column | mean before | mean after | corr(before, after) | max &#124;Δ&#124; |
| :--- | ---: | ---: | ---: | ---: |
| `braking_skill_s` | −0.000208 | +0.000208 | **−1.0000** | 0.3440 |
| `braking_skill_z` | −0.002766 | +0.002766 | **−1.0000** | 4.9600 |
| `corner_skill_index` | −0.001079 | +0.004604 | **+0.2097** | 4.9500 |
| `mid_corner_skill_s` / `_z` | — | unchanged | +1.0000 | 0.0000 |
| `exit_skill_s` / `_z` | — | unchanged | +1.0000 | 0.0000 |
| `braking_skill_se_s`, `*_cells_n`, `mapped_corners` | — | unchanged | +1.0000 | 0.0000 |

`corner_skill_index` moves by exactly `−2 × (old braking_skill_z)` on every row (max residual 0.01,
which is the `ROUND(·, 2)` on each term). **corr(index before, index after) = +0.21** — the
leaderboard is not a perturbation of itself, it is a different ordering.

**Rank level.** **122 of 139** scored driver-seasons change rank. Max move 17 places. The season
winner changes in **six of seven seasons**:

| Season | No. 1 before | No. 1 after | n | changed rank | max move | mean &#124;move&#124; |
| :--- | :--- | :--- | ---: | ---: | ---: | ---: |
| 2018 | GAS | **HUL** | 20 | 20 | 17 | 9.20 |
| 2019 | MAG | **VER** | 18 | 16 | 13 | 6.11 |
| 2020 | VER | VER | 20 | 18 | 12 | 6.50 |
| 2021 | NOR | **ALO** | 20 | 19 | 12 | 5.70 |
| 2022 | NOR | **ALO** | 20 | 18 | 15 | 6.20 |
| 2023 | NOR | **GAS** | 21 | 15 | 15 | 3.14 |
| 2024 | NOR | **GAS** | 20 | 16 | 16 | 5.70 |

**2024 in full** — the season `app/src/features/corner-phase-skill` defaults to, ordered as the page
orders it (`corner_skill_index ASC`):

| # after | # before | move | Driver | `braking_skill_s` before → after | `braking_skill_z` before → after | `corner_skill_index` before → after |
| ---: | ---: | ---: | :--- | ---: | ---: | ---: |
| 1 | 17 | ▲16 | GAS | +0.1250 → −0.1250 | +2.18 → −2.18 | +0.60 → **−3.76** |
| 2 | 7 | ▲5 | **VER** | **+0.0745 → −0.0745** | **+1.30 → −1.30** | −0.37 → **−2.96** |
| 3 | 3 | — | ZHO | +0.0461 → −0.0461 | +0.80 → −0.80 | −0.62 → −2.22 |
| 4 | 1 | ▼3 | NOR | −0.0424 → +0.0424 | −0.74 → +0.74 | **−3.17 → −1.69** |
| 5 | 15 | ▲10 | RUS | +0.0514 → −0.0514 | +0.89 → −0.89 | +0.38 → −1.41 |
| 6 | 9 | ▲3 | SAR | +0.0168 → −0.0168 | +0.29 → −0.29 | −0.10 → −0.68 |
| 7 | 19 | ▲12 | LEC | +0.0555 → −0.0555 | +0.97 → −0.97 | +1.51 → −0.42 |
| 8 | 13 | ▲5 | TSU | +0.0171 → −0.0171 | +0.30 → −0.30 | +0.21 → −0.39 |
| 9 | 5 | ▼4 | STR | −0.0081 → +0.0081 | −0.14 → +0.14 | −0.50 → −0.22 |
| 10 | 10 | — | HUL | +0.0041 → −0.0041 | +0.07 → −0.07 | +0.05 → −0.09 |
| 11 | 8 | ▼3 | ALB | −0.0066 → +0.0066 | −0.12 → +0.12 | −0.21 → +0.02 |
| 12 | 12 | — | MAG | +0.0007 → −0.0007 | +0.01 → −0.01 | +0.20 → +0.17 |
| 13 | 16 | ▲3 | ALO | +0.0081 → −0.0081 | +0.14 → −0.14 | +0.50 → +0.22 |
| 14 | 2 | ▼12 | SAI | −0.0588 → +0.0588 | −1.02 → +1.02 | −1.60 → +0.45 |
| 15 | 11 | ▼4 | RIC | −0.0141 → +0.0141 | −0.25 → +0.25 | +0.10 → +0.59 |
| 16 | 6 | ▼10 | HAM | −0.0514 → +0.0514 | −0.89 → +0.89 | −0.38 → +1.41 |
| 17 | 20 | ▲3 | PIA | +0.0424 → −0.0424 | +0.74 → −0.74 | +3.17 → +1.69 |
| 18 | 18 | — | BOT | −0.0461 → +0.0461 | −0.80 → +0.80 | +0.62 → +2.22 |
| 19 | 14 | ▼5 | **PER** | **−0.0745 → +0.0745** | **−1.30 → +1.30** | +0.37 → **+2.96** |
| 20 | 4 | ▼16 | OCO | −0.1235 → +0.1235 | −2.15 → +2.15 | −0.60 → +3.71 |

The mart is a pure **teammate differential** — with two drivers per car the LORO baseline is the
other driver, so every pair is exactly antisymmetric (VER ±0.0745 against PER, NOR ±0.0424 against
PIA). Worth stating in any post built on it: these are not field-wide numbers.

**Upstream, `int_lap_corner_inputs` (134,948 laps).** `corner_braking_loss_mean_s` −0.006475 →
+0.006475 (exact flip); `corner_braking_loss_sd_s` 0.328866 unchanged (a sample sd is invariant to
negation); `corner_braking_loss_max_s` 0.545874 → 0.647518, **not** a flip, `corr(old, new) = 0.080`
— `MAX` does not commute with negation, so this column changed meaning from "the corner braked
latest" to "the corner where most time was lost on entry". `fct_cliff_prediction_features` carries
the same three columns (137,447 rows, means +0.006503 / 0.330080 / 0.650262). Neither is in
`FEATURE_COLUMNS`, so **no model input and no model artefact changed**.

### Rebuild, tests and CI gates

- `dbt run --target dev --select int_corner_skill_residuals+` — 4 models, all PASS. That selector
  returns exactly `int_corner_skill_residuals`, `int_lap_corner_inputs`, `mart_corner_skill_driver`,
  `fct_cliff_prediction_features`, which is the whole blast radius.
- `dbt test --target dev --select int_corner_skill_residuals+` — **45/45 PASS**.
- `dbt build --target ci` on the three fixture races (`make test-all`'s build step) — **740/740 PASS,
  0 ERROR**, including the new test.
- The same CI build with the fix stashed: **ERROR=1**, and the one error is
  `assert_corner_skill_sign_convention`. The guard fails on `main` and passes on the fix, on CI
  fixtures as well as on `dev` — it is not a formality.
- `sqlfluff lint` on the touched model: **15 `LT05` long-line findings, all pre-existing** — the
  identical 15 appear at `git stash`-ed HEAD, shifted by the 14 lines of new header. No new lint
  debt added.

**Neither baseline snapshot was regenerated, deliberately.** Both are stale on `main` for reasons
that have nothing to do with `00d`, and re-snapshotting either would launder that drift into a
committed baseline under this item's name. Measured, not inferred — the CI fixture warehouse was
built twice, once with the fix and once with it stashed:

- **`model_hashes.baseline.json`.** Six `fct_*` models drift from the baseline. Five of them
  (`fct_driver_skill_features`, `fct_ghost_car_pace`, `fct_ghost_race_finish`, `fct_lap_residuals`,
  `fct_stint_features`) produce **byte-identical hashes with and without `00d`** — entirely
  pre-existing. `00d`'s footprint on the oracle is exactly three models:
  `fct_cliff_prediction_features` (`b549956e` without → `2ac73103` with), plus the non-mandatory
  `int_corner_skill_residuals` and `int_lap_corner_inputs`. Whoever re-snapshots should expect those
  three from this item and the other five from elsewhere.
- **`data_profile.baseline.json`.** Drifts across `fct_lap_residuals`, `fct_stint_features`,
  `fct_ghost_*` and more. The `00d`-attributable lines are exactly two:
  `mart_corner_skill_driver.braking_skill_s.mean` (−0.000208 → +0.000208) and
  `braking_skill_z.mean` (−0.002766 → +0.002766), plus `corner_skill_index.mean`
  (−0.001079 → +0.004604). The baseline's own numbers for those (−0.000135, −0.001844, +0.001007)
  are themselves stale, so the check's printed "before" is not the pre-`00d` value.

### Found on the way — two defects outside `00d`'s scope, recorded not fixed

1. **`mart_corner_skill_driver.constructor_id` is non-deterministic build to build.** The mart was
   rebuilt twice from an unchanged model and unchanged inputs: every numeric column was identical,
   and `constructor_id` flipped on three driver-seasons (`2018 OCO`, `2018 PER` between Force India
   and Racing Point; `2019 GAS` between Red Bull Racing and Toro Rosso). Cause is
   `ANY_VALUE(constructor_id)` at `mart_corner_skill_driver.sql:234` for drivers who changed team
   mid-season, under DuckDB's parallel hash aggregate. It is why
   `data_profile.baseline.json`'s `constructor_id.share` entries drift on a no-op rebuild, and it
   would block this mart ever joining the byte-stable set. Not caused by `00d` and not fixed here.
2. **`scripts/export_app_data.py --table NAME` silently truncates the manifest.**
   `manifest_entries` (`:538`) collects only the tables actually exported (`:546` skips the rest),
   and `:589-596` writes `"tables": manifest_entries` wholesale. Running the documented
   "fast re-export of one table" path (`:14`) rewrote `app/public/data/_manifest.json` from **37
   tables to 1**, orphaning every other app page's parquet path. Caught and reverted here
   (`git checkout -- app/public/data/_manifest.json`); the flag should either merge into the
   existing manifest or refuse to write one.

### The app

**No app code change is needed, and none was made.** `queries.ts:25-38` selects the mart's published
columns and orders `corner_skill_index ASC`; `transform.ts:16-17` adds a rank and spreads the row
unchanged; `page.tsx:28-60` renders them. Every claim the page makes — "Negative z-scores = faster
than field average for that phase", "Skill Index sums all three phases", "Lower = faster overall
corner driver" (`page.tsx:79`, `:105`) — is **true for the first time** once the mart is correct.

**But the page reads a committed parquet, not the warehouse.**
`app/public/data/marts/mart_corner_skill_driver/{2018..2024}.parquet` are **tracked in git**
(16 files are tracked under `app/public/data`), so the mart fix alone does not change the live page.
Those seven files were re-exported from the rebuilt `dev.duckdb` and verified: reading
`2024.parquet` and ordering `corner_skill_index ASC` now returns GAS, VER, ZHO, NOR, …, and the
printed index equals the sum of the three printed z-scores on every row.

One loose end left for the deploy step, not for this item: `_manifest.json`'s `version` field is a
content hash used purely as a CDN cache-busting query param (`manifest.ts:48-57`, written against
"the CDN cache-poisoning failure of 2026-06-11"). It is now stale against the re-exported parquets.
It was **not** hand-edited, because `_content_hash` (`export_app_data.py:153-159`) ranges over all
393 files in `app/public/data`, 377 of which are untracked local build output — writing a hash
derived from that into a tracked file would be exactly the laundering avoided above. A full
`make app-data` before publish regenerates it correctly. That publish is **D2**.

### What this means for `06c`

`06c` stays `MEASURED` and is **not run here**. Its dependency on `00d` is now discharged, so it is
runnable. What its next session needs to know:

**Explanation 1 is confirmed and Explanation 2 is not needed.** `06c_findings_summary.md:57-75`
posed two candidates for the VER braking anomaly — a sign inversion, or a genuine
Pérez-braking-strength effect — and named the falsification ("inspect the SQL that constructs
`braking_skill_z`... check whether the sign of `braking_loss_s` is inverted relative to the other
phases"). That falsification has now been run and the answer is yes. It also names the wrong model
to inspect (`fct_cliff_prediction_features.sql`); the sign was set in
`int_corner_skill_residuals.sql`, two models upstream.

**The anomaly dissolves, and dissolves in the direction of received wisdom.** VER 2024 braking is
now `braking_skill_s = −0.0745 s`, `braking_skill_z = −1.30` — negative is faster, so Verstappen
**does** brake later than Pérez, by 0.0745 s per corner-cell on 282 braking corners
(`se ±0.0151`, unchanged: the SE is invariant to the flip). The post cannot run as "a finding or a
baseline bug, posted as an open question". It was a baseline bug.

**Three specific numbers in the existing draft and summary are now wrong and must be rewritten, not
re-signed:**

1. `06c_findings_summary.md:22` — "**Braking** | **+0.0745 s** | −0.0745 s | **+0.1169 s (worse)**".
   The sign is inverted and the delta column is mislabelled: VER is now −0.0745 and it is *better*,
   not worse.
2. `06c_findings_summary.md:26` — "This contradicts public perception of Verstappen as a braking
   specialist." It confirms it.
3. **The NOR headline moves.** `06c_findings_summary.md:16` — "Norris's 2024 edge was traction, not
   braking" — survives as a statement about *exit* (NOR's exit z is unchanged at −2.19, still the
   largest single term in the 2024 table), but **NOR is no longer the 2024 leader**: he falls from
   1st (−3.17) to 4th (−1.69), behind GAS, VER and ZHO. Any sentence of the form "NOR tops the 2024
   corner-skill index" is now false. NOR was the before-fix leader in **four** seasons — 2021,
   2022, 2023 and 2024 — and leads none of them after the fix (ALO takes 2021 and 2022, GAS takes
   2023 and 2024). If the draft leans anywhere on "Norris is the corner-skill leader", that is the
   sentence the sign defect was writing, not the data.

**Two things worth saying in the post that the old draft could not.** (i) The index is a pure
**teammate differential** — with two drivers per car the LORO baseline *is* the other driver, so
every pair is exactly antisymmetric; VER ±0.0745 against PER is one number, not two. (ii) The
"anomaly" was found by `06b` arriving at the same conclusion from a completely independent
direction — dirty air produces negative `braking_loss_s` in every corner class and both eras, and
dirty air can only make a driver brake *earlier*. Two independent routes to the same sign defect is
a better story than the anomaly ever was.

**Also outstanding for that session, unchanged by this item:** the draft still lives only in a temp
scratchpad (`/private/tmp/claude-501/-Users-justin-github-off-the-pace/747de893-7d95-4054-83b7-5d43716c3ec5/scratchpad/06c_blog_post_draft.md`)
and should be rescued into `_improvements/implementations/06c/`; publishing is **D15**.


`06c`'s post is rewritten after this lands, not before.

**This is the pointer** (2026-09-20, the fan-value reprioritisation: `order_hint` 2 → 1). The
2026-09-19 argument for putting it second is the argument for putting it *first* once winning is
defined as giving F1 fans stats they can use. It is 0.5 day; `corner-phase-skill/queries.ts:37`
ranks a public leaderboard `ASC` on an index with one of its three terms inverted; and it is the
sole blocker on `06c`, a finished argument-settler post about Verstappen's braking that cannot be
published until this lands. Nothing about the item itself changed — only what sits behind it.

**Three items now depend on this one** (recorded 2026-09-19 by the build-order restructure, which
moved `00d` to `order_hint` 2 — behind `01c` only). `06c` was already on it. `02g` joins it because
this item carries `02g`'s one outstanding definition-of-done clause (the `mart_corner_skill_driver`
re-run whose output change was never reported), which its own build-log note already said in prose
without it being in `depends_on`. `02c` joins it because arm B's nine corner-residual aggregates
include three braking-phase columns that inherit this convention — the arm's *predictions* are
invariant to a monotone flip, but its per-phase attribution, which is the deliverable, is not.

**Cost:** ~0.5 day.
