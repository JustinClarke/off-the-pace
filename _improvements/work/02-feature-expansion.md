# Unused Channels — What the Warehouse Already Holds That the Feature Contract Does Not

Seventh document in the `_improvements/` series, after `PLAN.md`, `transform_gaps.md`,
`ml_headroom.md`, `ml_headroom_ii.md`, `ml_execution_plan.md` and `ml_research_program.md`.

Those asked whether the transform layer is correct, whether the models extract what the
warehouse gives them, what each candidate improvement buys, and how much headroom is left.
This one asks a narrower question that none of them asked directly:

> **The feature contract reads 13 warehouse models. The warehouse has 79 tables.
> What is in the other 66, is any of it a new information channel rather than another
> transform of lap times, and what would each one cost to admit?**

**Status: INVENTORY, NOTHING BUILT.** Written 2026-09-07. Every row count and column list
below was read from `data/dev.duckdb` read-only on that date. No model, contract, artefact
or warehouse object was touched. Nothing here has been ablated, so nothing here is a claim
that any of it works — only that it exists, that it is a different channel, and that the
repo's own admission rule has not yet been pointed at it.

---

## 0. The admission rule this document is written against

This is not a wish list, because the series already has a rule for what may be added, and
it was learned expensively.

**Phase 9 (2026-09-05)** dropped 18 of 42 columns — the `powertrain` (6), `telemetry_cliff`
(5), `weather_air` (2), `track` (2) and `context` (3) groups — on a noise-floor group
ablation across all three ablation-bearing families. Every dropped group cleared in none of
them. The contract went 42 → 24.

**Phase 10a (2026-09-05)** then added nine columns and cleared: p50 pinball 1.034661 →
1.012128 (1.54× floor), cliff macro-F1 0.372960 → 0.380950 (2.17× floor). The contract went
24 → **33**, which is where it stands at v11.

The stated reason 10a worked where the Phase 9 groups did not, in `schema.py`'s own words,
is that `proximity` is *"the first group in either series sourced from a DIFFERENT SENSOR
rather than from a further transform of the car channel or of lap times."*

**So the ranking principle here is channel novelty, not intuition about mechanism.** A
candidate that is another arithmetic rearrangement of lap-time residuals should be expected
to fail, because five such groups already have. A candidate that reads a sensor or a session
the contract has never touched is the only kind with a track record of clearing.

**Correction to carry forward:** `ml_research_program.md` and its predecessors repeatedly
say "24 features". The shipped contract has been **33** since v11. Anything that defines a
feature space — including §3b's k-NN ceiling design — must use 33, not 24.

---

## 1. The constraint that caps three of the four tiers

`ml_research_program.md` §1c measured `between_stint_share = 0.0094` for
`next_5_lap_cumulative_jump_s`. **99.06% of the degradation target's variance is within
stint.**

That is not a curiosity, it is a hard filter on everything below. A feature that is constant
within a stint — a weekend-level quali number, a per-circuit hazard rate, a season-level
constructor coefficient — can only ever address the 0.94%. It may still help the cliff
classifier (`between_stint_share` 0.1943) and stint life (a different target shape
entirely), but it **cannot** move the degradation trio much, and a design that expects it to
is misreading §1c.

Only one tier below varies lap to lap. That tier is where the degradation headroom is, and
it is not the cleanest one.

| tier | channel | varies within stint? | can move the p10/p50/p90 trio? |
| :--- | :--- | :--- | :--- |
| 1 — qualifying | different session | no (weekend-constant) | no — cliff & stint life only |
| 2 — corner inputs | position/telemetry, new construct | **yes (per lap)** | **yes** |
| 3 — marshalling | track status / race control | no (circuit-constant) | no — stint life mainly |
| 4 — misc | mixed | partly | marginal |

---

## 2. Tier 1 — Qualifying: an entire session the ML has never read

**What exists, verified by row count 2026-09-07:**

| table | rows | seasons |
| :--- | ---: | :--- |
| `int_qualifying_decomposed` | 14,165 | 2018–2024 |
| `int_qualifying_push_laps` | 46,234 | 2018–2024 |
| `int_qualifying_segments` | 447 | 2018–2024 |

Plus `int_constructor_structural_pace_qualifying`, `int_lap_fuel_state_qualifying`,
`stg_results_qualifying`, `int_lap_residual_decomposed_qualifying`. None of it is referenced
by `fct_cliff_prediction_features`, which reads 13 models, all race-session.

`int_qualifying_decomposed` carries a full pace decomposition per quali lap:
`quali_pace_delta_s`, `quali_skill_residual_s`, `quali_skill_session_avg_s`,
`quali_vs_race_skill_delta_s`, `constructor_component_s` (with SE and CI),
`ratio_to_segment_best`, `tyre_life`, `track_temp_c`, `quali_traffic_flag`, `dnq_flag`.

**Leakage: zero, by construction.** Qualifying is run before the race. No lag, no expanding
window, no leave-one-out wrapper is required — the session is strictly prior in wall-clock
time to every lap of the target. This is the only candidate in this document that needs no
anti-leakage treatment at all, and it should still go through the forward-window audit as a
formality.

**Why this is not Phase 10c, and why §4's closure does not reach it.** `ml_research_program.md`
§4 closed FP1/2/3 ingest as not viable because FP long runs have no fuel anchor:
`int_lap_fuel_state.sql` estimates starting fuel from a *known* race distance, and an FP long
run has no equivalent. That objection is real and it is fatal to FP.

It does not apply here, and the repo already says so. `int_lap_fuel_state_qualifying.sql`
assumes a flat 12 kg, which §4 itself describes as *"defensible only because quali burn-off
over one push lap is negligible (~0.006 s)"*. §4 raises that sentence as the contrast that
condemns FP. Read the other way round, it is a statement that **the fuel problem is already
solved for qualifying, by a model that has been in the warehouse the whole time.**

So: §4 correctly closed the largest untapped data lever and concluded *"there is no remaining
new data source lever in the program."* That conclusion is too strong. Qualifying is a
different session, already ingested, already decomposed, already fuel-corrected, and never
read. **Assumed, not verified:** that it carries signal. Nothing below is measured.

**Mechanism, stated so the ablation has a hypothesis to falsify.** Qualifying is the car and
driver at low fuel, new tyres and maximum push — the reference point race degradation is
implicitly measured against. Two constructs look most promising:

* `quali_vs_race_skill_delta_s` — a driver fast over one lap but not over a stint is the
  definition of poor tyre management, and that is the target.
* `constructor_component_s` with its SE — a car's one-lap aero/power level, measured on a
  session where strategy and traffic are near-absent, as a cleaner car term than the race
  session can give.

**The honest ceiling on this item.** Grain is (race_year, race_id, driver_id) — one row per
driver per weekend. Joined to a lap-level matrix it is stint-invariant, so per §1 it addresses
0.94% of the degradation target's variance. **Expect this to clear on `cliff_classifier` and
`stint_life_regressor` or not at all.** If it is pitched as a degradation-trio win, the pitch
is wrong before the ablation runs.

**Cost:** ~1 day. One join, no new ingestion, no refit of anything upstream.

---

## 3. Tier 2 — Corner-level driver inputs: the only lap-varying candidate

**What exists:**

| table | rows | grain |
| :--- | ---: | :--- |
| `int_corner_skill_residuals` | **2,206,939** | lap × corner |
| `int_corner_metrics` | 2,593,635 | lap × corner |
| `fct_telemetry_deltas` | 24,501,520 | race × driver-pair × corner × lap |

`int_corner_skill_residuals` carries `braking_loss_s`, `mid_corner_residual_s`,
`exit_residual_s`, `corner_residual_total_s`, `corner_residual_unexplained_s`, each already
expressed as seconds against a 5-lap-bucket field median. **The ML has never read any of it.**

**Why this is the highest-ceiling item despite Tier 1 being cleaner.** It varies lap to lap.
Per §1 it is the only tier that can address the 99.06% of degradation variance that lives
within a stint.

**Mechanism.** Braking, rotation and throttle application are the direct physical inputs of
energy into a tyre. The incumbent `thermal` group (`push_residual`,
`cumulative_push_load_surface`/`_bulk`, `surface_bulk_ratio`) *infers* push load from
lap-time residuals. This measures the inputs instead of inferring them. That is a genuinely
different construct even though it shares the telemetry sensor with `proximity`.

**The known risk, named precisely.** Phase 9 dropped `powertrain` and `telemetry_cliff`,
which were *"the mart's entire consumption of int_lap_telemetry_aggregates"*. So a previous
attempt to feed telemetry into the contract failed. But Phase 10a then re-read the same
ingestion through a different aggregation and cleared at 1.54×/2.17×. The evidence therefore
says **the aggregation failed, not the sensor.** That puts all the risk of this item in the
aggregation design, which is where it should be stated:

* per lap, aggregate the three phase residuals across the corners of that lap — mean, sd and
  max are the obvious three, and sd is the one with a tyre-management story behind it;
* consider splitting by corner type using `dim_corners` geometry, since a slow hairpin and a
  high-speed sweep load a tyre differently;
* `field_corner_sample_n < 5` yields NULL, and `corner_unmapped_flag` exists — **count the
  coverage gap before building**, because a feature that is NULL on a biased subset of laps
  is a leakage-shaped hazard, not just a sparse column.

**Leakage: RULED 2026-09-08 — barred as constructed.** See `02a` below. Values are
contemporaneous with lap *t* and the target spans *t+1…t+5*, so the construction is prima facie
safe — and it is not. The residuals are taken against a *"5-lap-bucket field median"* whose
bucket reaches into the target window.

---

### `02a` — the 5-lap field-median bucket · RULED 2026-09-08

**The item asked a binary — centred or backward-looking — and the SQL answers neither.**
`int_corner_skill_residuals` computes `FLOOR(CAST(cm.lap_number AS DOUBLE) / 5.0) * 5.0 AS
lap_window` and then `GROUP BY race_year, race_id, corner_name, lap_window`. That is a **fixed
block bucket**, not a window function: no `LEAD`, no `FOLLOWING` frame, no self-join inequality.
R5 flagged this shape and estimated the reach at "about two laps"; measured, it is **1.877**.

**Verified — the forward reach, measured over all 2,206,939 rows** by reconstructing the
`corners_with_keys` CTE from `int_corner_metrics` ⋈ `int_stint_geometry` (valid laps only) and
counting, for every focal lap, the rows in its own median group drawn from laps that had not yet
run:

| block position | mean forward reach | % of the median drawn from the future | mean own-driver future laps in own baseline | % of rows seeing their own future |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3.739 laps | **76.00%** | 3.351 | **95.55%** |
| 1 | 2.814 | 56.44% | 2.558 | 95.00% |
| 2 | 1.909 | 40.00% | 1.751 | 92.04% |
| 3 | 0.968 | 20.67% | 0.907 | 90.67% |
| 4 | 0.000 | 0.00% | 0.000 | 0.00% |
| **all** | **1.877** | **38.45%** | — | — |

77.83% of lap-groups have some forward reach. Mean group size is ~70 rows.

**Method**, so the number is re-derivable rather than quoted. Run from `transform/` — `stg_laps`
and `stg_sector_times` are parquet-backed views with paths relative to it:

```sql
-- corners_with_keys, as the model builds it
CREATE OR REPLACE TEMP VIEW ck AS
SELECT cm.race_year, cm.race_id, cm.corner_name, cm.driver_id, cm.lap_number,
       cm.braking_point_m, FLOOR(CAST(cm.lap_number AS DOUBLE)/5.0)*5.0 AS lap_window
FROM int_corner_metrics cm
JOIN (SELECT race_year, race_id, driver_id, lap_number
      FROM int_stint_geometry WHERE is_valid_lap = TRUE) lk
  USING (race_year, race_id, driver_id, lap_number);

-- for every focal lap: rows in its own median group drawn from laps that had not yet run
WITH lapagg AS (
  SELECT race_year, race_id, corner_name, lap_window, lap_number,
         COUNT(*) FILTER (WHERE braking_point_m IS NOT NULL) AS n_lap
  FROM ck GROUP BY ALL),
gtot AS (
  SELECT race_year, race_id, corner_name, lap_window,
         SUM(n_lap) AS n_group, MAX(lap_number) AS max_lap
  FROM lapagg GROUP BY ALL),
reach AS (
  SELECT l.lap_number, g.n_group,
         g.max_lap - l.lap_number AS forward_reach_laps,
         g.n_group - SUM(l.n_lap) OVER (
           PARTITION BY l.race_year, l.race_id, l.corner_name, l.lap_window
           ORDER BY l.lap_number ROWS UNBOUNDED PRECEDING) AS n_future_rows
  FROM lapagg l JOIN gtot g USING (race_year, race_id, corner_name, lap_window))
SELECT lap_number % 5 AS block_pos,
       ROUND(AVG(forward_reach_laps), 3) AS mean_forward_reach_laps,
       ROUND(100.0*AVG(n_future_rows*1.0/n_group), 2) AS pct_from_future
FROM reach WHERE n_group >= 5 GROUP BY ALL ORDER BY 1;
```

The own-driver column is the same view self-joined on `(race_year, race_id, corner_name,
lap_window, driver_id)` with `b.lap_number > a.lap_number`. The materiality arms are the
`TRAILING` window given under `02g` below, aggregated to lap grain and joined to
`fct_cliff_prediction_features` on `lap_id`.

**The fact that decides it.** `DEGRADATION_TARGET` is `next_5_lap_cumulative_jump_s` — laps
*t+1…t+5*. Maximum forward reach is **4 laps**. So every future lap entering the median falls
*inside the label's own window*; the overlap is total containment, not partial. And it is not
only the field's future: at block position 0, **95.55% of rows are scored against a baseline
containing that driver's own future laps** — a mean of 3.351 of the 5 laps the label integrates.
The feature is not point-in-time correct.

**Verified — the contamination carries label signal, weakly.** Both arms were rebuilt from
identical source with identical formulae, differing only in the window: BLOCK (production, read
from the model's own table) and TRAILING (median over laps *t−5…t−1*, same race and corner, all
drivers, `n ≥ 5`). Aggregated to lap grain as §3 proposes (mean/sd across the lap's corners) and
joined to the real label on `is_training_eligible` rows (n = 80,381). Isolating the contamination
as `delta = BLOCK − TRAILING`, with block position 4 — zero forward reach — as the control:

| arm | n | corr(delta, label) | 95% CI (race-clustered bootstrap) |
| :--- | ---: | ---: | :--- |
| contaminated, positions 0–3 | 58,283 | **+0.0344** | [+0.0047, +0.0667] |
| control, position 4 | 15,055 | +0.0083 | [−0.0143, +0.0324] |
| paired difference | — | **+0.0261** | [−0.0008, +0.0531], one-sided *p* = 0.027 |

**Stated honestly: this half is suggestive, not decisive.** The contaminated arm's interval
excludes zero and the control's does not, and the paired difference is one-sided significant, but
its two-sided interval touches zero. The control is also imperfectly matched — at position 4 the
block and trailing windows overlap heavily, so its delta is a smaller contrast (sd 0.043 vs
0.116 at position 0). **The ruling does not rest on this table.** It rests on the row above it,
which is deterministic: the baseline contains the label's own laps, by construction, for 77.83%
of the data.

**The rebuild costs no signal.** Marginal |corr| with the label is equal or slightly *higher* for
the trailing arm at every block position (e.g. total-residual mean at position 0: −0.0666
trailing vs −0.0485 block). Contamination is behaving as noise on the baseline, not as a free
win — so nothing is lost by removing it, which is the cheap case.

**The rebuild's real cost is coverage, and it is concentrated and explainable.** Lap-grain
non-null falls 92.79% → 90.57% (−2.22pp), and the loss is almost entirely **lap 2** — the first
lap present in the table, which has no prior lap to build a backward median from:

| phase | non-null, block | non-null, trailing |
| :--- | ---: | ---: |
| lap ≤ 6 | 92.11% | **70.68%** |
| lap 7–11 | 92.61% | 91.59% |
| lap > 11 | 92.87% | 92.35% |

§3 warns that a feature NULL on a biased subset is "a leakage-shaped hazard, not just a sparse
column". This loss is deterministic on `lap_number` — an axis already in the contract via
`age_in_stint` — not correlated with the outcome, so the model can condition on it. It is
declarable, not hazardous. An expanding trailing window does not rescue lap 2 either; nothing
precedes it.

**Ruling.** **Barred as constructed.** `02c` must not ablate these columns as they stand. The fix
is the one R5 predicted — recompute the field median as a trailing window — and it is now `02g`,
which `02c` depends on instead of `02a`.

**Scope of the bar.** `mart_corner_skill_driver` consumes `braking_loss_s` /
`mid_corner_residual_s` / `exit_residual_s` today. That is a descriptive per-driver aggregate with
no forward label, so this is **not** leakage there and the mart is not barred. Its residuals are
still measured against a partly-future baseline, which is a measurement-consistency question
worth its own item — it is not this ruling.

**Confirms `08b`'s premise.** The reach lives in the scope of a `GROUP BY` and nowhere else, so
`audit_forward_window` sees nothing: no `LEAD`, no `FOLLOWING`, no self-join inequality. The
guard was clean on this model the whole time it was wrong.

Evidence: [`../research/R5-representation-and-transform.md`](../research/R5-representation-and-transform.md)
Part 2 for the shape; the measurements above are this item's, run against `data/dev.duckdb`.


### `02g` — rebuild the corner field median as a trailing window

**Created 2026-09-08 by `02a`'s ruling.** `02c` depends on this, not on `02a`.

**Objective.** Replace the `FLOOR(lap/5)*5` block bucket in `int_corner_skill_residuals` with a
backward-only field median, so the residual at lap *t* is measured against laps strictly before
*t*. Formulae, NULL rules and the `field_corner_sample_n < 5` gate stay exactly as they are; only
the window moves.

**The shape, already measured to work** (`02a`'s trailing arm):

```sql
quantile_cont(braking_point_m, 0.5) OVER (
  PARTITION BY race_year, race_id, corner_name
  ORDER BY lap_number RANGE BETWEEN 5 PRECEDING AND 1 PRECEDING)
```

`RANGE` (not `ROWS`) is load-bearing — it takes every driver's rows in the lap interval, which is
what makes it a *field* median rather than a per-driver one. `1 PRECEDING` excludes lap *t*
itself, which is what makes it backward-only.

**Two decisions this item must make and record, because `02a` did not.**

1. **Trailing-5 or expanding.** `02a` measured trailing-5 to keep the window width comparable to
   the block it replaces. An expanding window (all prior laps, `n ≥ 5`) is more stable late in a
   race but mixes early-race and late-race track states into one baseline, which is the same
   pooling defect `02d` is fixing in `int_sc_hazard_history`. Trailing-5 is the recommendation;
   whichever is chosen, record why.
2. **What to do about lap 2.** It has no predecessor and must go NULL — a 21.4pp coverage loss on
   laps ≤ 6, all of it that one lap. Declare it in `schema.yml` rather than back-filling it from
   the block median, which would reintroduce the leak on precisely the rows that cannot be built
   cleanly.

**R5's recommendation 2 applies here.** `02d` needs the same pattern for
`int_sc_hazard_history`. Write it once as a dbt macro (`{{ trailing_median(...) }}`) so the
second instance is a call, and so `08b`'s auditor has one shape to whitelist rather than two to
discover.

**Definition of done.** `int_corner_skill_residuals` uses a backward-only median; a test asserts
no row's baseline draws on `lap_number >= ` its own; the lap-2 NULL rule is declared in
`schema.yml` with the coverage figure; `mart_corner_skill_driver` is re-run and the change to its
outputs is reported, not assumed to be nil; `model_hashes.baseline.json` re-snapshotted.

**Cost:** ~0.5–1 day. The window is a two-line change; the test, the schema note and re-reading
the mart are the rest.

**Cost:** ~2–3 days, most of it in the aggregation design and the leakage check.

---

## 4. Tier 3 — The marshalling channel, and a correction to the research program

**What exists:** `int_sc_hazard_history` (36 circuits) with `sc_hazard_per_lap`,
`vsc_hazard_per_lap`, `any_hazard_per_lap` and shrunk variants of each; plus
`stg_track_status` and `stg_race_control`, neither read by the contract.

**This falsifies a load-bearing sentence in `ml_research_program.md` §1a.** That section
explains why the last 28% of stint-life headroom is probably unreachable:

> *"Remaining stint life is set partly by pit-wall strategy calls and safety-car timing —
> events that are not a tyre-degradation question at all and carry no signal in any feature
> this warehouse could build."*

The clause after the dash is false. A per-circuit safety-car hazard *per racing lap*, already
empirical-Bayes shrunk, is exactly that signal, and it has been in the warehouse the whole
time. §1a marks the paragraph "Inference, not measurement", so this is a correction to an
Assumed claim rather than to a Verified one — but it is the kind of claim that hardens into
received wisdom if left standing, and it is currently the stated reason for capping the
stint-life target at 0.80–0.85 of attainable.

**Why it should matter for stint life specifically.** Stint life is right-censored on 46.2%
of training rows, and stint ends are set by pit-wall decisions. Safety-car probability is the
largest exogenous input to those decisions. This is the one target where a circuit-constant
feature is not obviously capped by §1's within-stint argument, because the target is not
shaped like the degradation column.

**Leakage: needs an expanding window.** `int_sc_hazard_history` is a pooled historical rate
over every race with an ingested track-status timeline. Used as-is it puts 2024 races into
the hazard estimate a 2018 row sees. **Rebuild it as an expanding, season-lagged rate** —
hazard as of the start of season *S*, using seasons < *S* only — or it is a textbook temporal
leak with a plausible-looking gain attached.

**Coverage caveat:** the model's own header says track-status ingestion is *"incomplete for
some seasons"*. Establish which seasons before trusting a per-circuit rate.

**Cost:** ~1 day, most of it in the expanding-window rebuild.

---

## 5. Tier 4 — cheap, low expected value, recorded so they are not re-derived

* **`int_track_evolution`** (6,729 rows, race × lap): `track_state_index_s`,
  `rubber_component_s`, `track_temp_c`, `humidity_pct`, `rainfall_flag`. Lap-varying, which
  puts it above the rest of this tier. Note the weather closure (below) does **not** cover
  it: air density was closed as near-constant per circuit; track rubbering is a genuine
  within-race process on a different mechanism.
* **`int_sector_residual_decomposed`** (412,341 rows): `sector_consistency_index` has a
  tyre-management story. But sector times are another transform of lap times, which is the
  exact category Phase 9 dropped five groups from. Low prior.
* **`fct_telemetry_deltas`** (24,501,520 rows): pairwise driver corner deltas. The grain is
  a driver *pair*, which does not join to a lap-level feature matrix without an aggregation
  choice that is not obvious. Large, and probably not worth it before Tier 2 is settled.

**Barred, not merely unpromising — do not propose these:**

* **`int_synthetic_teammate`** (119,698 lap-level rows). Its headline column is
  `driver_skill_proxy_s`, and `driver_skill_proxy_s` is an explicit member of
  `EXCLUDED_LEAKAGE_COLUMNS` in `ml/src/schema.py`, listed under "causal leakage". The table
  is useful analysis; it is closed as a feature source.
* **`int_driver_race_skill_loro`** (2,825 rows) is the one genuine ambiguity. Its
  `driver_skill_loro_s` is leave-one-race-out, which is the correct anti-leakage construction
  and is precisely what makes a skill term admissible in principle. But the leakage list bars
  `driver_skill_residual_s` and relatives without carving out a LORO exception. **This needs a
  ruling, not an assumption.** Someone should decide explicitly whether LORO construction
  lifts the bar, and write the decision into `schema.py` beside the list. Until then, treat
  it as barred.

---

## 6. Dead ends, with reasons, so they stay closed

* **`stg_tyre_allocations` / `tyre_allocations` are EMPTY — 0 rows.** The staging model and
  its columns (`allocated_sets_per_driver`, `compound_code`, `circuit_key`) exist; nothing
  populates them. How many fresh sets of each compound a driver still has is a genuinely
  strong strategy signal and it is not derivable from anything else in the warehouse. **This
  is an ingestion gap, not a modelling one**, and it is the single clearest "new data source"
  still open now that §4 has closed FP. Raise it against ingestion, not against the ML
  contract.
* **Weather / air density.** Closed 2026-08-23 as a *measured negative*, not as unrealised
  value: built properly off bronze `pressure_hpa`, they move p50 RMSE −0.33% and cliff
  macro-F1 +0.70%, both inside harness noise, because air density is near a per-circuit
  constant and circuit identity already enters the set three times over. **Do not re-open.**
* **`int_lap_telemetry_aggregates` as previously aggregated.** Dropped Phase 9 with the
  `powertrain` and `telemetry_cliff` groups. The sensor was vindicated by Phase 10a; the
  aggregation was not. Re-approach only via a new construct (Tier 2), never by restoring the
  dropped columns.

---

## 7. The gate every candidate must pass

Unchanged from the standing protocol, restated so this document is executable without
re-reading `ml_execution_plan.md`:

1. **Instrument check first.** The N-column refit must reproduce the published v11 headline
   to six decimals before anything built on top of it is trusted. Phase 10b did this and it
   is what makes its numbers comparable.
2. **Add-ablation** on the identical `cv_final_fold` split (train 2018–2023, eval 2024),
   using `evaluate.py`'s own `_fit`/`_score`, not a reimplementation.
3. **Delta against that family's own 5-reseed floor** — `2*sqrt(2)*sd` from
   `ml/src/attribution.py::refit_noise_floor`. Never against a floor computed under the
   paired-t protocol in `intervals.py`; they are not interchangeable.
4. **Permutation-null arm.** Row-shuffle the new columns in train and eval so capacity is
   preserved and signal destroyed, then report capacity and information separately. Phase 10a
   found a group whose total cleared while neither half did; without this arm that would have
   shipped as a clean win.
5. **Forward-window audit** for anything label-adjacent, and the leakage checks named per
   tier above.
6. **Pre-register the arms before running them.** `ml_research_program.md` §5 documents an
   uncorrected multiplicity problem across 22 checkpoints. Adding four more tiers of tests
   without pre-registration makes that problem worse, and pre-registration costs nothing.

---

## 8. Recommended order

1. ~~**Tier 2 leakage check** (hours).~~ **Done 2026-09-08 — and it reached forward.** The
   bucket is a fixed `FLOOR(lap/5)*5` block; mean forward reach 1.877 laps, entirely inside the
   label's own *t+1…t+5* window, with the driver's own future laps in their own baseline on
   95.55% of block-position-0 rows. Barred as constructed. Per this list's own contingency, that
   changes the ordering: **`02g` (the trailing-window rebuild) now comes before Tier 2's
   ablation**, and `02c` depends on it. See §3.
2. **Tier 1, qualifying** (~1 day). Cleanest join in the document, zero leakage treatment,
   and it tests §4's "no remaining data source" conclusion directly. Expect cliff and stint
   life to move, not the trio.
3. **Tier 2, corner inputs** (~2–3 days). Highest ceiling, because it is the only lap-varying
   candidate and therefore the only one that can reach the degradation trio's 99%.
4. **Tier 3, SC hazard** (~1 day), with the expanding-window rebuild, aimed at stint life —
   and at §1a's capping assumption.
5. **Raise `tyre_allocations` as an ingestion item**, separately from all of the above.

---

## 9. What this document is not

* **Not a record of work done.** Nothing has been built, joined, ablated or shipped. Every
  number is a row count or a column list read from `data/dev.duckdb` on 2026-09-07,
  or a figure quoted from an existing artefact with its source named.
* **Not a claim that any candidate works.** No candidate here has been through the gate in
  §7. The document's claim is narrower: these are different channels, the admission rule has
  never been pointed at them, and three of them are one join away.
* **Not a reopening of anything closed.** FP1/2/3 (§4 of the research program), weather/air
  density, and the Phase 9 telemetry aggregates stay closed. §2 argues that §4's *conclusion*
  over-generalised to qualifying; it does not argue that §4 was wrong about FP.
* **Not independent of `ml_research_program.md` §3.** If the ceiling work lands and shows the
  degradation trio near a trustworthy empirical floor, Tier 2 is noise-chasing and this whole
  document reduces to Tier 1 and Tier 3. **§3 still prices this.**
