# 08 — Foundations repair

**Group:** 08 · **Depends on:** nothing · **Prices:** every measurement taken after it

Opened 2026-09-07 out of research round R1. The programme was about to spend a fortnight
measuring (`04`, `01a`, `01b`) on a substrate with two defects nobody had found. Fix the
substrate first: **anything that changes what you would measure goes before the measurements.**

Evidence: [`../research/R7-data-quality-and-shipped-surface.md`](../research/R7-data-quality-and-shipped-surface.md)
and [`../research/R5-representation-and-transform.md`](../research/R5-representation-and-transform.md)
Part 2. Do not re-derive them.

---

## 08a — Backfill the 2018 compound dimension

**Objective.** Repair the `compound` feature group for 2018.

**The defect, verified.** `dim_compounds_season` carries five `compound_code` values — HARD (117),
MEDIUM (131), SOFT (130), INTERMEDIATE (16), WET (9). It has **no rows** for SUPERSOFT, ULTRASOFT
or HYPERSOFT, the pre-2019 naming. So **7,622 training rows (6.30%), every one of them 2018**,
carry NULL for all six compound physical parameters.

**Why it is first.** `compound_cliff_onset_laps` is the **#1 feature** on
`degradation_regressor_p50` by both SHAP and permutation (`ml/model_card.yml`, `dual_importance`).
The most important feature in the headline model is absent for an entire season's soft-compound
running, and absent **non-randomly** — by season and compound together. `01a`'s season arm starts
at 2018–19, so its first data point is currently measured on a crippled base.

**Method.** Either fit the six parameters for the three 2018 compounds the way the existing rows
were fitted (`dim_compounds_season` carries `fit_date`, `data_window` and `notes` — follow them),
or map SUPERSOFT / ULTRASOFT / HYPERSOFT onto their C-number equivalents and inherit. **State
which, and why, in the model's `notes` column** — an inherited parameter and a fitted one are not
the same evidence.

**Acceptance.** `compound_grip_peak` NULL rate on training-eligible rows falls from 6.30% to ~0,
and the 2018 rows carry parameters whose provenance is recorded.

**Definition of done.** The null sweep is re-run and reported; the history entry states whether
the parameters were fitted or inherited, and no downstream contract changed.

---

## 08b — Extend `audit_forward_window` to aggregation scope

**Objective.** Close the class of leakage the auditor cannot currently see.

**The gap, verified.** `ml/src/features.py::audit_forward_window` is sound on what it checks —
`_expr_is_forward_looking` catches `LEAD()` and `FOLLOWING` frames, `_self_join_inequality` catches
row-ordering self-joins, and unparsed models become violations rather than silent passes. But
**both of the programme's known leakage suspects have none of those shapes**:

| model | construct | detected? |
| :--- | :--- | :---: |
| `int_corner_skill_residuals` | `FLOOR(lap_number/5.0)*5.0 AS lap_window`, then `GROUP BY` | **no** |
| `int_sc_hazard_history` | `GROUP BY race_year, race_id` → one row per `circuit_slug`, all seasons pooled | **no** |

Neither uses a window function at all. The forward reach lives in the **scope of a `GROUP BY`**,
which the walker never inspects. That is a class, not two instances — every `int_*` model
computing a rate, median or baseline by `GROUP BY` is in it.

**Method.** Walk `exp.Group` for every model feeding `FEATURE_COLUMNS`. Require the grouping key
set to either (a) include a time key at or below the label's grain, or (b) be declared exempt in
that model's `schema.yml` with a written reason. Exemptions are data, not comments — the checker
reads them.

**Why early rather than late.** If it finds more leaks, the feature contract moves and everything
downstream re-runs. Finding them before `01b` is cheaper than finding them after.

**Acceptance.** The extended audit runs over the live manifest, its findings are enumerated, and
every finding is either fixed or exempted with a reason. A finding that is neither fails the build.

**Definition of done.** `make ml-features` fails on an undeclared aggregation scope; the two known
instances are among the findings; the count of newly-found instances is reported plainly, including
if it is zero.

### Corrections to this spec, made while building it (2026-09-09)

**"A time key at or below the label's grain" was too loose to implement, and is now precise.**
The label grain is `lap_id` — `fct_cliff_prediction_features` is one row per valid race lap. A key
set passes iff it confines a group to **at most one lap**: it holds `lap_id`, or a race key
alongside a lap ordinal, or `stint_id` alongside a lap ordinal. Extra keys only ever shrink a
group, so the test is monotone. Two sub-rulings the wording did not anticipate:

- `race_id` pins a race **without** a season key beside it. Verified, not assumed: it is globally
  unique across the ingested seasons — 147 distinct ids in `fct_lap_residuals`, 149 in
  `int_stint_geometry` and `fct_stint_features`, **zero reused across seasons in any of the
  three**. Without this the audit reports a false positive on `int_lap_telemetry_aggregates`.
- `circuit_id` / `circuit_key` / `circuit_slug` / `track_id` are **not** race keys even beside a
  season key. 2020 ran two races at the Red Bull Ring and two at Silverstone, so (season, venue)
  does not identify a race.

**The two known instances are in the survey, not in the gate — and that is the correct scope.**
Neither `int_corner_skill_residuals` nor `int_sc_hazard_history` is in the mart's lineage today;
nothing reads them, so nothing can leak through them yet. Enforcing over every `int_*`/`stg_*`
model to reach them would have forced **56 declarations that assert nothing anyone has to honour**,
and an exemption file that is mostly noise is worse than no exemption file. So the audit is the
gate over the mart's lineage, and `survey_aggregation_scope()` is a report-only second pass over
the `int_*`/`stg_*` models outside it. Both known instances appear there, by name, with the right
severity — `int_sc_hazard_history`'s `GROUP BY circuit_slug` as *pools every ingested season*, which
is exactly `02d`'s defect. When `02c` and `02d` wire those models into a feature they enter the
gate's scope **automatically**, and the build stops until someone rules on them. The instrument's
own falsification lives in `test_features.py` instead: four synthetic-SQL tests that reproduce both
shapes, plus a negative control and the aliased-bucket hole.

**Scope is the whole model lineage, not the models on a feature's definition chain.** Resolving a
feature to the models that build it means following the definition chain, and that chain stops at
the first computed expression — `int_field_pace_curve` feeds `push_residual` by subtraction and
would drop out of scope. Over-approximating costs a few declarations; under-approximating costs the
guard.

### What it found

**31 aggregation scopes in the lineage; 17 do not pin a lap.** All 17 are now declared in
`schema.yml` under `meta.aggregation_scope_exemptions` — 16 entries, because `int_track_evolution`
repeats one key set. Each carries `keys`, a `status` and a written `reason`; a `known_leak` also
carries `fixed_by`. The checker refuses a blank reason, an unknown status, a `known_leak` with
nothing scheduled, and an exemption that no longer matches any aggregation in its model.

**Five are real leaks.** They are the two shapes [`../foundations/gates.md`](../foundations/gates.md)
step 5 names, found inside the live 33-feature contract:

| model | scope | reaches | item |
| :--- | :--- | :--- | :--- |
| `int_lap_thermal_proxy` | `stint_id` | `push_residual` + 3 | `08e` |
| `fct_cliff_prediction_features` | `compound` | `survival_weight` | `08f` |
| `fct_cliff_prediction_features` | `compound, lap_in_stint` | `survival_weight` | `08f` |
| `int_circuit_x_constructor_interaction` | `circuit_id, constructor_id` | `cliff_candidate_flag` | `08f` |
| `int_circuit_x_constructor_interaction` | `race_year, constructor_id` | `cliff_candidate_flag` | `08f` |

**Twelve are accepted, and eleven of those are one decision.** See the next section.

### The race-scoped spine — a method finding, not a defect list

Eleven of the seventeen findings are instances of a single design decision: **this warehouse
decomposes a completed race.** `int_field_pace_curve`'s 107% filter, `int_event_corrections`' race
fastest lap, `int_constructor_structural_pace`'s per-race coefficient and its race-mean re-centring,
`int_track_evolution`'s four race-level baselines — each is race-scoped because the quantity it
computes is only defined over a whole race. None of them crosses the season split, so none
contaminates a CV fold, and each is accepted on those grounds.

**The price is worth stating in one place rather than eleven.** Everything downstream of
`driver_skill_residual_s` — which is the whole residual spine, and through
`int_lap_anomaly_flags` reaches the feature `cliff_candidate_flag` — is **not point-in-time correct
for live mid-race prediction**. It is correct for post-hoc race analysis, which is what the app
does. That is a defensible position, but it had never been written down, and it is now the thing to
re-read before anyone proposes a live prediction surface.

Two of the eleven are narrower than the rest and are recorded as such: `int_lap_fuel_state`'s
`MAX(lap_number)` stands for the **scheduled** race distance, a pre-race known the warehouse has no
column for — adding one to `dim_events` would remove that exemption outright; and
`int_field_pace_curve`'s race-scoping is confined to the eligibility threshold, since the pace curve
itself groups `(race_year, race_id, lap_number)` and pins a lap.

The remaining accepted finding is `int_lap_anomaly_flags`' `(race_year, race_id, driver_id)`
z-score, which is diagnostic: `cliff_candidate_flag` uses the **trailing** window
(`w.lap_number BETWEEN r.lap_number - 6 AND r.lap_number`) and the mart never reads the z-score
columns.

---

## 08e — The thermal-proxy stint baseline reaches forward

**Objective.** `push_residual` and the three features built on it are measured against a baseline
computed from laps that had not yet run, in a window whose width is set by the stint-life label.
Rebuild the baseline so it is available at the lap it scores.

**The defect, verified (2026-09-09, by `08b`'s new audit).**
`int_lap_thermal_proxy.stint_baseline_agg` is
`MEDIAN(lap_time_s) FILTER (WHERE lap_in_stint <= baseline_cutoff_lap AND is_valid_lap) GROUP BY stint_id`,
with `baseline_cutoff_lap = GREATEST(CEIL(stint_length_actual * 0.60), 3)`. Two reaches:

1. **The median pools laps 1..cutoff**, so any lap before the cutoff is scored against laps from
   its own future. **55.92% of the 137,447 mart rows**, mean reach **4.65 laps**, max 45. By
   position in stint: lap 2 is 100% of rows at a mean of 11.83 laps, lap 5 is 94.5% at 9.37, lap 10
   is 76.7% at 5.57. `DEGRADATION_TARGET` is `next_5_lap_cumulative_jump_s`, so the mean reach sits
   **inside the label's own window** — the same thing that decided `02a`.
2. **The cutoff is a function of the label.** `stint_length_actual` is identical to
   `fct_stint_features.stint_length_laps` — measured, **8,333 of 8,333 stints, r = 1.0** — which is
   the numerator of `remaining_stint_life_laps`. For the stint-life family the baseline window's
   *width* is set by the target.

**Reaches four features:** `push_residual`, `cumulative_push_load_surface`,
`cumulative_push_load_bulk`, `surface_bulk_ratio`.

**Why nothing caught it.** `transform/tests/assert_no_future_leakage.sql` re-derives the two EWMAs
over `push_residual` with backward `LAG`s and asserts they match. It never checks `push_residual`
itself. Its own comment calls it "the definitive future-leakage guard" — it validated the window
and was blind to the aggregation that built the window's input. That is `08b`'s premise, in the
one place it costs the most.

**Method.** Rebuild `stint_baseline_pace` as a trailing or expanding median over laps strictly
before the lap being scored, with a minimum-observation floor for the opening laps, and drop
`stint_length_actual` from the cutoff entirely. `02g` is rebuilding the corner field median to the
same shape — write the trailing-median pattern once as a dbt macro (R5's recommendation 2) and call
it from both, so the third instance is a call rather than a rediscovery.

**Materiality is not measured, and must be before the rebuild is priced.** `02a`'s ruling is the
template: isolate `delta = block − trailing`, correlate it with the label, and use a zero-reach
position as the control. The construction alone is enough to bar it from a *claim*; it is not
enough to predict what the rebuild costs.

**Acceptance.** `int_lap_thermal_proxy` has no `GROUP BY` that fails `audit_aggregation_scope`, or
has one whose exemption is `accepted` rather than `known_leak`; the four features are re-measured
against their own reseed floor through [`../foundations/gates.md`](../foundations/gates.md);
`assert_no_future_leakage` is extended to check `push_residual` itself, not only the EWMA over it.

**Definition of done.** The `known_leak` entry in `transform/models/intermediate/schema.yml` is
gone, replaced by either no finding or an `accepted` one, and the delta on all three families is
reported whichever way it goes.

### `08e` materiality — MEASURED 2026-09-09, and it is not the cheap case

`02a`'s template, run against `data/dev.duckdb` read-only. Two arms rebuilt from identical
source with identical formulae, differing only in the baseline window: **BLOCK** (production —
`MEDIAN(lap_time_s) FILTER (lap_in_stint <= cutoff AND is_valid_lap) GROUP BY stint_id`) and
**TRAILING** (expanding median over valid laps *strictly before* the scored lap, same stint).

**Instrument check first.** The probe's BLOCK arm reproduces `int_lap_thermal_proxy` exactly —
`stint_baseline_pace` and `push_residual` both bit-for-bit on **162,729 of 162,729 rows**,
max abs diff 0.0. Everything below is measured against a faithful rebuild, not an approximation.

**Verified — defect 2 is exact, not approximate.** The baseline window's width is a deterministic
function of the stint-life label's own numerator:
`baseline_cutoff_lap == GREATEST(CEIL(stint_length_laps * 0.60), 3)` on **121,193 of 121,193**
training-eligible mart rows, and `corr(baseline_cutoff_lap, remaining_stint_life_laps) = +0.5644`.
This is stronger than `08b` recorded: not merely that `stint_length_actual` equals
`stint_length_laps`, but that the cutoff is re-derivable from the mart's own label column.

**Verified — the contamination carries label signal in all three families.** Isolating
`delta = BLOCK − TRAILING` and correlating with the label, with the zero-forward-reach position
(`lap_in_stint >= baseline_cutoff_lap`) as the control. Race-clustered bootstrap, 2,000 resamples,
n = 109,904 training-eligible rows with both arms defined:

| target | arm | n | corr(delta, y) | 95% CI |
| :--- | :--- | ---: | ---: | :--- |
| `next_5_lap_cumulative_jump_s` | contaminated | 47,797 | **−0.0501** | [−0.0845, −0.0055] |
| | control | 25,542 | +0.0561 | [+0.0284, +0.0873] |
| | **paired difference** | | **−0.1062** | [−0.1540, −0.0554], one-sided *p* = 0.000 |
| `remaining_stint_life_laps` | contaminated | 52,922 | **−0.1551** | [−0.2498, −0.0704] |
| | control | 56,982 | −0.0848 | [−0.1218, −0.0500] |
| | **paired difference** | | −0.0703 | [−0.1807, +0.0303], one-sided *p* = 0.082 |
| `laps_until_cliff_class` (P(0–2)) | contaminated | 52,915 | +0.0218 | [−0.0030, +0.0464] |
| | control | 50,521 | +0.0034 | [−0.0156, +0.0212] |
| | **paired difference** | | +0.0184 | [−0.0161, +0.0546], one-sided *p* = 0.147 |

`laps_until_cliff_class` is a 4-way categorical, so it is encoded as the two binaries the
classifier is actually asked — P(cliff in 0–2 laps), shown, and P(cliff at all in stint),
which behaves the same way (−0.0239, *p* = 0.212).

**That table has `02a`'s weakness and it is fixed below.** The control sits at a different stint
position from the contaminated arm by construction, so early/late-stint effects are confounded
with contamination. `02a` noted this and let the ruling rest elsewhere. Here it can be removed:
at a **fixed `lap_in_stint`**, contamination status depends only on the stint's own cutoff — i.e.
its length — so both arms coexist at the same position. Matching on `lap_in_stint` (21 strata,
laps 6–26, ≥300 rows on both sides, n = 85,693) and comparing the BLOCK→TRAILING **swing** in the
feature's own correlation with the label:

| target | swing, contaminated | swing, control | matched difference | 95% CI | one-sided *p* |
| :--- | ---: | ---: | ---: | :--- | ---: |
| `next_5_lap_cumulative_jump_s` | −0.0317 | +0.0033 | **−0.0350** | [−0.0633, −0.0073] | 0.010 |
| `laps_until_cliff_class` (P(0–2)) | −0.0316 | +0.0042 | **−0.0357** | [−0.0518, −0.0230] | 0.000 |
| `remaining_stint_life_laps` | +0.1310 | +0.0255 | **+0.1055** | [+0.0361, +0.1776] | 0.001 |

**All three clear once the control is matched, including the cliff family, which did not clear
unmatched.** The control's own swing is small but non-zero (+0.003 to +0.026) — expected, because
BLOCK and TRAILING differ even at zero forward reach (BLOCK is laps 1..cutoff, TRAILING is laps
1..t−1, a superset). The matched difference subtracts exactly that.

**Verified — the contamination inverts the feature's sign, twice, independently.** This is the
finding that separates `08e` from `02a`.

| population | n | corr(`push_residual`, y) BLOCK | TRAILING |
| :--- | ---: | ---: | ---: |
| `remaining_stint_life_laps`, contaminated rows | 52,922 | **−0.1231** [−0.1504, −0.0943] | **+0.0315** [−0.0231, +0.0897] |
| `remaining_stint_life_laps`, control rows | 56,982 | +0.0945 [+0.0580, +0.1373] | +0.1251 [+0.0914, +0.1639] |
| `next_5_lap_cumulative_jump_s`, `lap_in_stint <= 4` | 7,701 | **−0.1191** | **+0.1197** |
| `next_5_lap_cumulative_jump_s`, `lap_in_stint >= 5` | 113,492 | +0.1984 | +0.2490 |

Under production the feature's relationship to the label **reverses sign across the leak
boundary** — negative where the baseline reaches forward, positive where it does not. Under the
rebuild both regions agree in sign. The swing on contaminated rows is +0.1546 [+0.0800, +0.2268],
five times the control's +0.0305 [+0.0217, +0.0392]. The mechanism is defect 2: a longer stint
buys a later cutoff, which moves the baseline, and stint length *is* the label.

**`02a` found contamination behaving as noise. This is not that.** There the trailing arm's
marginal correlation was equal or slightly higher and the ruling was "nothing is lost by removing
it, which is the cheap case". Here the production feature is not a noisier version of the correct
one — in the region where the reach is largest it points the other way.

**Verified — the rebuild is cheap, and cheaper than `02a`'s was.** Minimum-observation floor
priced over all 121,193 training-eligible rows (BLOCK coverage 99.69%):

| floor | coverage | vs BLOCK | corr(pr, deg) | corr(pr, cliff) | corr(pr, life) |
| ---: | ---: | ---: | ---: | ---: | ---: |
| BLOCK | 99.69% | — | +0.0867 | −0.0239 | −0.1041 |
| **n ≥ 1** | **98.28%** | **−1.41pp** | **+0.2031** | **+0.0354** | **+0.0738** |
| n ≥ 2 | 96.20% | −3.49pp | +0.2324 | +0.0373 | +0.0702 |
| n ≥ 3 | 90.87% | −8.82pp | +0.2519 | +0.0315 | +0.0627 |
| n ≥ 5 | 80.60% | −19.09pp | +0.2539 | +0.0288 | +0.0652 |

**Recommend floor n ≥ 1**: it costs 1.41pp of coverage and *raises* marginal correlation on all
three targets against production. `02a`'s rebuild cost −2.22pp; this one costs less. Floors above
1 buy a little more degradation signal for several points of coverage — a trade worth re-testing
through the gate, not settling here.

**The coverage loss is NOT as declarable as `02a`'s, and that is the one open hazard.** 2,018
rows: 41.8% at `lap_in_stint` 2, 16.7% at 4, 14.4% at 5, with a tail to lap 15. The cause is that
lap 1 of a stint is an out-lap with `is_valid_lap = FALSE`, so lap 2's only predecessor
contributes no observation. `02a` could call its NULLs declarable because they were deterministic
on `lap_number`, already in the contract via `age_in_stint`. **These are deterministic on the
count of valid prior laps in the stint, which is not a contract axis** and which rises with SC and
pit disruption — plausibly correlated with the outcome. §3's warning applies. **Carry the
observation count as a companion column** so the model can condition on the thing the NULL is
deterministic on; do not assume `age_in_stint` covers it.

**Protocol note.** Every figure above is a correlation contrast under a race-clustered bootstrap —
`02a`'s instrument, and the same one in both arms. **No model was fit**, so neither
`intervals.py::paired_t` nor `attribution.py::refit_noise_floor` is in play and nothing here may
be diffed against a floor ratio or a CV p-value
([`../foundations/epistemics.md`](../foundations/epistemics.md)).

**Population anchoring.** `corr(push_residual_block, next_5_lap_cumulative_jump_s)` is +0.0867
pooled over all training-eligible rows but +0.2373 over the subset where both arms are defined.
That gap is population, not disagreement — the excluded rows are `lap_in_stint <= 4`, which are
also the highest-reach rows. Do not diff a pooled figure here against a subset figure.

**Ruling. Barred as constructed, and the bar is firmer than `02a`'s.** `02a` rested on the
deterministic construction because its materiality half was suggestive; `08e`'s materiality half
is decisive on its own — three families, position-matched, two independent sign inversions. The
four features must not be quoted, ablated or shipped in their current form.

**Assumed, and not measured here.** The delta-defined arm excludes `lap_in_stint <= 4`, where
TRAILING has no window: **83.5%** of contaminated training-eligible rows are kept, and the dropped
ones carry *higher* mean forward reach (9.84 vs 7.34 laps). **Every materiality number above is
therefore a floor, measured on the low-reach half of the contamination.** No claim is made about
what the headline scores do — that needs the rebuild and the gate, not a correlation.

**Method**, inlined so it is re-derivable rather than quoted — the probe scripts were scratchpad
and are gone. Run from `transform/`; `stg_laps` is a parquet-backed view with paths relative to it,
and the warehouse is opened `read_only=True`.

```sql
-- Both arms, from the same source int_lap_thermal_proxy builds from.
CREATE OR REPLACE TEMP VIEW combined AS
SELECT g.stint_id, g.lap_id, g.race_year, g.race_id, g.driver_id,
       g.lap_number, g.lap_in_stint, g.stint_length_actual, g.is_valid_lap, l.lap_time_s,
       GREATEST(CEIL(g.stint_length_actual * 0.60), 3) AS baseline_cutoff_lap
FROM int_stint_geometry g INNER JOIN stg_laps l ON g.lap_id = l.lap_id;

-- ARM A: production block median, one value per stint (reproduces the model exactly)
CREATE OR REPLACE TEMP VIEW block_arm AS
SELECT stint_id,
       MEDIAN(lap_time_s) FILTER (WHERE lap_in_stint <= baseline_cutoff_lap AND is_valid_lap)
         AS block_baseline
FROM combined GROUP BY stint_id;

-- ARM B: expanding median over valid laps STRICTLY BEFORE the scored lap.
-- n_prior is the minimum-observation floor knob priced in the table above.
CREATE OR REPLACE TEMP VIEW trail_arm AS
SELECT lap_id, stint_id, lap_in_stint,
       MEDIAN(CASE WHEN is_valid_lap THEN lap_time_s END) OVER w AS trail_baseline,
       COUNT(CASE WHEN is_valid_lap THEN lap_time_s END) OVER w AS n_prior
FROM combined
WINDOW w AS (PARTITION BY stint_id ORDER BY lap_in_stint
             ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING);

CREATE OR REPLACE TEMP VIEW arms AS
SELECT c.*, b.block_baseline, t.trail_baseline, t.n_prior,
       b.block_baseline - t.trail_baseline AS delta,
       GREATEST(c.baseline_cutoff_lap - c.lap_in_stint, 0) AS forward_reach_laps,
       (c.lap_in_stint < c.baseline_cutoff_lap) AS is_contaminated
FROM combined c JOIN block_arm b USING (stint_id) LEFT JOIN trail_arm t USING (lap_id);
```

The instrument check is `arms` joined back to `int_lap_thermal_proxy` on `lap_id`, asserting
`stint_baseline_pace` and `push_residual` are `NOT DISTINCT FROM` the rebuilt values. The analysis
frame joins `arms` to `fct_cliff_prediction_features` on `lap_id` and `fct_stint_features` on
`stint_id`, filtered to `is_training_eligible`, with `remaining_stint_life_laps` synthesised the way
`features.py:143` does it (`GREATEST(stint_length_laps − lap_in_stint, 0)`) and
`laps_until_cliff_class` encoded as the two binaries named above.
`push_residual` per arm is `baseline − lap_time_s`.

**The two statistics.** *Delta table*: `corr(BLOCK − TRAILING, y)` within each arm, arms split on
`is_contaminated`. *Matched table*: within each `lap_in_stint` stratum holding ≥300 rows on both
sides, the **swing** `corr(pr_trail, y) − corr(pr_block, y)` computed separately for contaminated
and control rows, then averaged across strata weighted by `min(n_contaminated, n_control)` — the
matchable mass at that position. Both CIs are race-clustered bootstraps (resample `race_id` with
replacement; 2,000 resamples for the delta and sign-flip tables, 1,000 for the matched table),
with the one-sided *p* taken as the share of resamples on the null side of zero.

---

### `08e` rebuild — BUILT 2026-09-09, green, and NOT yet gated

**What is in the warehouse.** `int_lap_thermal_proxy.stint_baseline_pace` is now
`trailing_median('lap_time_s', ['stint_id'], ['lap_in_stint'], min_observations=1,
valid_condition='is_valid_lap')` — an expanding median over the stint's valid laps strictly before
the scored lap. `stint_length_actual` is gone from the model entirely, so the second reach (the
label-derived window width) is gone by construction rather than by measurement.

**The instrument check on the rebuild.** The dbt model reproduces the priced probe exactly, which
is what makes the materiality numbers above apply to the thing that shipped rather than to a
prototype of it. Over the 121,193 training-eligible mart rows, measured against `dev.duckdb`:

| | production (BLOCK) | rebuilt (TRAILING) | priced in the probe |
| :--- | ---: | ---: | ---: |
| `push_residual` coverage | 99.688% | 98.275% | 99.69% → 98.28% |
| `corr` with `next_5_lap_cumulative_jump_s` | +0.0867 | +0.2031 | +0.0867 → +0.2031 |
| `corr` with `remaining_stint_life_laps` | −0.1041 | +0.0738 | −0.1041 → +0.0738 |
| `corr` with P(cliff 0–2), non-NULL class only | −0.0239 | +0.0354 | −0.0239 → +0.0354 |

The lost rows are the priced ones: 2,018 of them, 41.8% at `lap_in_stint` 2.

**Four decisions the build made, and why.**

1. **Expanding, not trailing-N.** A stint is ~20 laps, so the window is local by construction, and
   capping it would let the baseline drift with the degradation it is supposed to measure. This is
   the opposite call from `02g`, where trailing-5 is right because the pool is the whole field
   across a race — the macro takes `lookback` for exactly this reason.
2. **Floor of 1.** What was priced. Floors of 2/3/5 buy more degradation signal for
   3.49/8.82/19.09pp of coverage; that trade has not been through the gate and was not taken here.
3. **`baseline_observations_n` ships, and is NOT a feature.** It is in the mart and in the enforced
   contract, and it is deliberately absent from `ml/src/schema.py`'s `FEATURE_COLUMNS`. Putting it
   in `X` is an add-ablation someone has to gate; shipping it so a consumer can condition on the
   missingness is not. The declarability hazard is unchanged by this build — it is made visible,
   not closed.
4. **A NULL residual on the CURRENT lap makes both loads NULL; a NULL residual on a PRIOR lap
   contributes 0.** `GREATEST(NULL, 0)` is `0` in DuckDB, so without an explicit `CASE` the loads
   would have read "no thermal load" on a lap whose load is simply unknown. The prior-lap
   convention is the one the window already used for laps before the stint began.

**`assert_no_future_leakage` now checks the baseline, and it is a real check.** It re-derives the
baseline by **self-join on strictly-prior laps** — deliberately not with the macro the model uses,
so the test is an independent construction rather than a restatement of the model's own window,
and it uses `FILTER` in a plain `GROUP BY`, which is legal exactly where the `FILTER` inside a
windowed ordered-set aggregate is not. Verified to fire: against the old block-median definition it
returns **145,934 of 162,729 rows**; against the rebuild, **0**. It also asserts the floor rule
(`baseline_observations_n` matches, and the baseline is NULL exactly where it is 0) and the
residual identity.

Two collateral fixes the rebuild forced, both of which were tests that would otherwise have gone
quiet rather than failed:

- `assert_stint_boundary_integrity` anchored on `lap_in_stint = 1`, where `push_residual` is now
  always NULL — the comparison would have passed on a NULL rather than checking anything. It now
  anchors on the stint's **first scored lap**, which is the same boundary and is still a real
  identity, because every lagged term there is either outside the partition or NULL.
- The two EWMA checks in `assert_no_future_leakage` compared with `ABS(actual − expected)`, which
  is NULL — and so not a failure — wherever the model is now NULL. They carry the model's NULL rule
  into `expected` and compare with `IS DISTINCT FROM`.

**Status: `BUILDING`, not `GATED` and not `LANDED`.** `dbt run` is green on all 72 models,
`dbt test` green on all 622, the CI fixture build green on 705, and
`ml/src/features.py --check` reports **both audits CLEAN with zero declared `known_leak`s** for the
first time. None of that is the gate. Steps 2–4 of [`../foundations/gates.md`](../foundations/gates.md)
— add-ablation on `cv_final_fold`, the family's own reseed floor, the permutation-null arm — have
not been run, so **no claim about the headline exists yet**, and nothing is committed.

---

---

## 08f — Cross-season pooled statistics in the feature lineage

**Objective.** Three aggregations in the lineage pool every ingested season into one statistic, so a
2018 training row's value is estimated partly from the 2024 evaluation season. Season-lag them, or
rule the pooling acceptable with a measurement rather than an assumption.

**The defect, verified (2026-09-09, by `08b`'s new audit).** Two independent instances:

**08f-1 — the survival IPW curve.** `fct_cliff_prediction_features` builds
`P(stint reaches lap_in_stint | compound)` from `total_per_compound` (`GROUP BY compound`) and
`stints_reaching` (`GROUP BY compound, lap_in_stint`), neither of which carries a season key.
`survival_weight` is not a feature and never enters `X`, but `train.py:175` uses it as the XGBoost
sample weight for the quantile regressors and `evaluate.py:613` uses it again to weight the scores.
So eval-season information reaches both the fit and the metric, through the weights rather than
through a column.

**08f-2 — the circuit × constructor interaction.** `int_circuit_x_constructor_interaction`
shrinks a constructor's per-circuit deviation over all seasons at once (`GROUP BY constructor_id,
circuit_id`), and separately averages over a whole season (`GROUP BY race_year, constructor_id`).
Measured: **522 cells, mean 2.79 seasons pooled**, and **57.4% of pre-2024 panel rows sit in a cell
that also holds a 2024 observation**, each season carrying mean weight 0.35 in the shrunk mean.
This one reaches a live feature, and the chain is traced:
`circuit_constructor_interaction_s` → `constructor_component_s`
(`int_lap_residual_decomposed:224`) → `driver_skill_residual_s` (`:299-314`) →
`int_lap_anomaly_flags` → **`cliff_candidate_flag`**.

**Method.** For 08f-1, rebuild the survival curve as a season-lagged expanding estimate — the same
shape `02d` needs for `int_sc_hazard_history`, and a third caller for `08e`'s macro. For 08f-2,
either season-lag the shrinkage or restrict the panel to seasons at or before the row's own.
Re-run the affected families through the gate afterwards; the weights change, so the headline
moves and every delta measured against the old headline stops being comparable
([`../foundations/gates.md`](../foundations/gates.md) step 1).

**Ordering.** 08f-2 before 08f-1: it reaches a feature, 08f-1 reaches only the weights.

**Acceptance.** No `known_leak` entry with `fixed_by: 08f` remains in either `schema.yml`, and the
instrument check (gate step 1) is re-run and reported, because the headline itself moves.

**Definition of done.** The three aggregations either carry a season key or are `accepted` with a
measurement behind the acceptance, and the re-measured headline is recorded as the new baseline
with the old one named beside it.

---

### `08f` rebuild — BUILT 2026-09-09, both instances, green and NOT yet gated

**08f-2 (first, because it reaches a live feature).** `int_circuit_x_constructor_interaction` has
no `GROUP BY` left. Both aggregations are point-in-time windows:

- `constructor_season_avg` → expanding mean over the constructor's races **strictly before this
  one, within the season**. NULL at the season's first race, which is the honest answer: there is
  no season level to deviate from yet.
- `circuit_constructor_agg` → expanding count/mean/stddev over that (constructor, circuit)
  pairing's **prior visits**, ordered by `(race_year, round_n)`.

`pace_circuit_deviation_s` is deliberately **NULL, not `COALESCE(..., 0.0)`**, where there is no
season-to-date average. Coalescing would have made the deviation the constructor's *raw pace* and
fed that whole level into the circuit pool as if it were a circuit effect.

The ordering key needed care: `race_id` is `'YYYY_R'` **as a string**, so it sorts `2023_10` before
`2023_2`. Ordering a point-in-time window on it directly would have silently scrambled the time
axis — the exact failure the item exists to fix, reintroduced by the fix. `round_n` is
`CAST(SPLIT_PART(race_id, '_', 2) AS INTEGER)`; verified over the warehouse that every `race_id`
matches `^[0-9]{4}_[0-9]+$` and that `(race_year, round_n)` identifies all 147 races.

Grain is unchanged (1,456 rows, PK unique). **The consequence to state plainly:** 2018 is the first
ingested season, so no 2018 row has a prior visit and `circuit_constructor_interaction_s` is now
**identically 0 across the whole of 2018** (197 rows), against a mean absolute value of ~0.08–0.11s
in later seasons. That is correct — the old value for 2018 was estimated from 2019–2024 — but it
means an entire training season loses this feature's variation, and that is a change the gate has
to price, not a cosmetic one.

**08f-1.** The survival curve in `fct_cliff_prediction_features` is cumulated over seasons
**strictly before** the row's own, numerator and denominator lagged **together** — lagging one
alone stops the ratio being a probability. 2018 has no prior season, so its `survival_prob` is NULL
and the existing `COALESCE` gives those rows a weight of **1.0** (unweighted), which is the honest
estimate when there is no prior curve and is the same fallback the model already applied to an
unmatched cell.

**The exemptions.** `int_circuit_x_constructor_interaction`'s two `known_leak` entries are
**deleted** — there is no `GROUP BY` left for them to describe, and the auditor's stale-exemption
check would have failed on them. The mart's two are **re-declared as `accepted`** on keys that now
carry a season (`[race_year, compound]` and `[race_year, compound, lap_in_stint]`): the per-season
counts still do not pin a lap, but the only thing that reads them is a window cumulating strictly
prior seasons, so no row is ever weighted by a count drawn from its own season.

**What the CI fixtures do and do not cover.** The fixture warehouse holds three seasons (2020,
2023, 2024), so the season-lag is genuinely exercised — only 30 of 2,562 rows sit at the unity
weight. The 705-test CI build is green.

---


### `08e` + `08f` — gate step 1, run as a re-baseline (2026-09-09)

Step 1 says the refit must reproduce the published v11 headline to six decimal places. Here the
substrate moved **on purpose**, so reproduction is not the test — the test is whether anything
*else* moved. Run as a true A/B on one warehouse, both arms through `evaluate.py`'s own
`run()`/`_fit`/`_score` with `ARTEFACTS_DIR` redirected to scratch, so nothing in `ml/models/` or
`ml/artefacts/` was written and **no retrain was needed**: `evaluate.run()` refits from
`{target}_best_params.json` and never loads a shipped booster.

**The instrument check passes, and it is what closes the confound.** With `08e` and `08f` reverted
in place and the two subtrees rebuilt, all five headlines come back **identical to the published
v11 artefact to better than 1e-9**:

| target | metric | published v11 | BEFORE arm | AFTER arm | A − B |
| :--- | :--- | ---: | ---: | ---: | ---: |
| `degradation_regressor_p10` | pinball | 0.5187980 | 0.5187980 | 0.5353710 | **+0.0165730** |
| `degradation_regressor_p50` | pinball | 1.0163386 | 1.0163386 | 1.0407823 | **+0.0244437** |
| `degradation_regressor_p90` | pinball | 0.5600310 | 0.5600310 | 0.5660356 | **+0.0060047** |
| `cliff_classifier` | macro F1 | 0.3802680 | 0.3802680 | 0.3704769 | **−0.0097912** |
| `stint_life_regressor` | AFT nloglik | 1.9487233 | 1.9487233 | 1.9900697 | **+0.0413464** |

Pinball and AFT nloglik are lower-is-better, macro F1 higher-is-better, so **every one of the five
moves the wrong way.** Removing the leakage costs headline performance — which is what removing
label information from features is supposed to look like. Part of what v11 published was bought
with the contamination `08e` and `08f` describe.

**Why this is attributable to `08e` + `08f` and not to the rest of the working tree.** The session
opened worried that the rebuilt warehouse also carried `10a`'s stint-end-regime model, an
841-line `compound_cliff_params.csv` refit and edits to `fct_stint_features.sql`. All three are
ruled out, by measurement rather than by argument:

- The BEFORE arm reproduces published v11 **exactly on five independent metrics**. Had any other
  pending change moved a feature in this mart's lineage, it could not.
- The seed refit is **not in the warehouse**: `dbt run` does not seed, and the `compound_cliff_params`
  table in `dev.duckdb` still differs from the CSV on disk (same 438×17 shape, different values).
- `fct_cliff_prediction_features` does not `ref` `fct_stint_features` or `int_stint_end_regime` —
  checked against its ref list. They reach `features.py` only as the stint-life label and the
  censoring flag, and both are provably unmoved: `n_eval_rows` and the constant-predictor
  `baseline_headline` are **bit-identical** across both arms on all five targets (13,896 / 19,145 /
  20,272 rows; 1.464425 / 2.177660 / 0.890801 / 0.218654 / 2.186889).

That last row is also the protocol anchoring [`../foundations/epistemics.md`](../foundations/epistemics.md)
asks for: the population, the split and the labels did not move, so the two headlines are
comparable and the only thing that changed is feature values.

**What this is NOT.** These deltas have **not** been compared to anything. Gate steps 2–4 have not
been run: no add-ablation isolating the four thermal columns from the circuit-interaction chain, no
`attribution.py::refit_noise_floor` reseed floor for any family, no permutation-null arm. So no
number here may be called significant, and none of them may be quoted as "clears" or "inside" a
floor — a delta without its family's floor is exactly the quotation
[`epistemics.md`](../foundations/epistemics.md) exists to forbid. **The direction is established;
the magnitude is not yet interpretable.**

**The AFTER arm was measured twice, and the dev build is reproducible.** The `ci` profile pins
both dbt's `threads` and DuckDB's internal `settings.threads` to 1, with a comment explaining that
non-associative float aggregation reorders across intra-query threads and drifts `fct_*` output;
the `dev` profile every ML measurement is taken on runs `threads: 4` with no such setting. That
asymmetry was checked rather than assumed: the AFTER evaluation was re-run against a second,
independent full `dbt run` of the same SQL, and all five headlines came back **bit-identical**
(0.535371003 / 1.040782333 / 0.566035645 / 0.370476863 / 1.990069681, zero difference). So the
asymmetry is real in the profile and carries no observed cost at the headline. Recorded as an
untested asymmetry, not a finding.

---

### `08e` + `08f` — gate steps 2–4, and the two families separated (2026-09-09)

Step 1 established the direction and refused to interpret the magnitude. Steps 2–4 make it
interpretable. All three arms run on the **rebuilt (AFTER) substrate only**, on `cv_final_fold`
(train 2018–2023, eval 2024), through `evaluate.py`'s own `_fit`/`_score` — no reimplementation,
nothing written to `ml/models/`, `ml/artefacts/`, the warehouse or git.

**The two families, fixed by lineage rather than by taste.**

| family | columns | why exactly these |
| :--- | :--- | :--- |
| **T — `08e`** | `push_residual`, `cumulative_push_load_surface`, `cumulative_push_load_bulk`, `surface_bulk_ratio` | The only contract columns fed by `int_lap_thermal_proxy`. Checked, not assumed: its only three consumers are this mart, `fct_stint_features` and `int_tyre_surface_vs_bulk_decoupling`, and `dirty_air_thermal_load_*` come from `int_lap_air_state`, which does **not** `ref` it. |
| **C — `08f-2`** | `cliff_candidate_flag` | `int_circuit_x_constructor_interaction` reaches the contract through exactly one path: `int_lap_residual_decomposed` → `int_lap_anomaly_flags`. Its other consumer in the mart is the C1 detrending, which differences a stint-constant shift straight back out — which is why step 1 found the labels bit-identical. |

**`08f-1` is in neither family, and that is a gap, not an omission.** It moves the IPW
`survival_weight`, which is not a column. No column ablation can see it, and it is live for the
quantile trio only (`_row_weights` returns weights for `kind == "quantile"` and `None` otherwise).

**Design.** One common baseline arm `A` = the 33-column contract minus T minus C, then `A+T`,
`A+C`, and the full 33. Each family's permutation-null arm has the **same columns** as its add
arm with the family block row-shuffled as a unit in train *and* eval — capacity and the family's
own joint distribution preserved exactly, only its alignment with the label destroyed — over
**3 draws**, because a single permutation is a point estimate. Floors are 5 seed-only refits via
`attribution.py::refit_noise_floor`, computed on both the full and the baseline arm; every ratio
below is quoted against the **larger** of the two, which is the conservative call.

**Family T — the rebuilt thermal block clears on all five, and it is information.**

| target | metric | A (no T, no C) | A+T | delta | ×floor | capacity | information | ×floor |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `degradation_regressor_p10` | pinball | 0.5829013 | 0.5298958 | **−0.0530055** | 4.21× | +0.0133784 | −0.0663839 | **5.27×** |
| `degradation_regressor_p50` | pinball | 1.1144292 | 1.0335762 | **−0.0808530** | 8.98× | −0.0019026 | −0.0789505 | **8.77×** |
| `degradation_regressor_p90` | pinball | 0.5918152 | 0.5747936 | **−0.0170216** | 1.07× | +0.0043156 | −0.0213373 | **1.35×** |
| `cliff_classifier` | macro F1 | 0.3567748 | 0.3709149 | **+0.0141401** | 2.41× | −0.0001629 | +0.0143030 | **2.43×** |
| `stint_life_regressor` | AFT nloglik | 2.0224465 | 1.9887504 | **−0.0336961** | 4.37× | −0.0033000 | −0.0302961 | **3.93×** |

Five for five, in the direction of improvement, with the permutation-null attributing the gain to
information rather than capacity every time. **This is the result that changes how step 1 reads.**
The rebuilt thermal columns are not a degraded remnant of a leaky feature: they are the largest
single block in the contract on the degradation median, worth 8.98× its floor. What step 1 priced
was the loss of the *contaminated* portion, not the loss of the family.

Two things recorded rather than rounded up. **p90's total is 1.07× — barely over**, and it is
carried by its information term (1.35×) rather than by the total; it clears, and it clears
narrowly. **p10's capacity term is +0.0133784, or 1.06× its own floor** — four shuffled columns
measurably *hurt* p10. The information term is 5× larger and oppositely signed so the family still
clears unambiguously, but the capacity term is not nil for p10 and is not reported as if it were.

**Family C — `cliff_candidate_flag` carries nothing, in any family.**

| target | A | A+C | delta | ×floor | capacity | information | ×floor |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `degradation_regressor_p10` | 0.5829013 | 0.5928065 | +0.0099053 | 0.79× | +0.0096350 | +0.0002702 | 0.02× |
| `degradation_regressor_p50` | 1.1144292 | 1.1116689 | −0.0027604 | 0.31× | −0.0027613 | +0.0000009 | **0.00×** |
| `degradation_regressor_p90` | 0.5918152 | 0.5933422 | +0.0015270 | 0.10× | −0.0003952 | +0.0019222 | 0.12× |
| `cliff_classifier` | 0.3567748 | 0.3576418 | +0.0008671 | 0.15× | +0.0008122 | +0.0000549 | 0.01× |
| `stint_life_regressor` | 2.0224465 | 2.0182955 | −0.0041510 | 0.54× | −0.0072889 | +0.0031380 | 0.41× |

Every total is inside its floor, and every information term is inside it by a wider margin — the
largest is 0.41× and on p50 it is 0.0000009, which is nil to seven decimal places. Whatever
`cliff_candidate_flag` moves, it moves as split capacity. The column is TRUE on **0.854% of the
137,447 mart rows**, so this is not a surprise; it is the first time it has been measured.

**What steps 2–4 do NOT establish, stated plainly.** They are run on the AFTER substrate only, so
they measure what each family is worth *now*. They do **not** decompose step 1's regression between
`08e` and `08f-2`. "C carries nothing now" and "C carried nothing before" are different claims, and
only the first is measured — a leak-removal that emptied the column would look exactly like this.

One piece of the decomposition does follow, and only for two of the five families. Arm `A` excludes
both T and C and takes no weights, so for `cliff_classifier` and `stint_life_regressor` it is
invariant across the two substrates (the quantile trio is not: `08f-1` moves their IPW weights).
Against that common reference, using step 1's BEFORE headlines:

| target | A | BEFORE joint T+C | AFTER joint T+C | change |
| :--- | ---: | ---: | ---: | ---: |
| `cliff_classifier` | 0.3567748 | +0.0234932 | +0.0137021 | −0.0097911 |
| `stint_life_regressor` | 2.0224465 | −0.0737232 | −0.0323768 | +0.0413464 |

So on the stint-life family the two columns-families jointly were worth 0.0737 of AFT nloglik
before and are worth 0.0324 after: **the rebuild removed 56% of their joint contribution.** The
split of that 56% between T and C is one measurement away — the same add-ablation on the BEFORE
substrate — and is not inferable from anything here.

**Gate steps 5 and 6.** Step 5 re-run this session rather than carried over: `features.py --check`
reports `[forward-window audit] CLEAN`, `[aggregation-scope audit] CLEAN`, `[leakage guard] CLEAN
(33 features)`, fingerprint `26345ce7…`. Step 6 was satisfied in advance — the step 1 section named
these three arms, by name, before they were run.

**Status.** All six gate steps are now run for `08e` and `08f`, so both move `BUILDING` → `GATED`.
`GATED` is "eligible to land", not landed: `ml/artefacts/evaluation_metrics.json` still holds the
v11 numbers and the warehouse still disagrees with it by design, and nothing is committed.

---

---

## 08c — Two silent assumptions, written down

**Objective.** Convert two undocumented properties into declared ones. Documentation-grade, hours.

**08c-1 — the lap-1 NULL tyre-life rows.** 343 of 162,729 `int_stint_geometry` rows have NULL
`age_in_stint` (0.21%), and **325 of them (94.8%) sit on lap 1 of a stint**. That is a pattern,
not scatter, and lap 1 of a stint is exactly where `starting_tyre_age_laps` is derived. Explain it
or bound it; do not assume it benign. See [`../notes/tyre-life-provenance.md`](../notes/tyre-life-provenance.md).

**08c-2 — `ahead_identity_stability` null semantics.** 31.0% NULL, stable at 28.6–32.2% in every
season. Only 1,449 of 36,044 nulls are "no car ahead"; the rest are the statistic being
**undefined**, not absent. Declare that in `schema.yml` so a later consumer does not read NULL as
zero.

**Acceptance.** Both are described in the relevant `schema.yml`, and 08c-1 carries either a cause
or a measured bound.

**Definition of done.** No consumer of either column has to guess what a NULL means.

---

## 08d — Real Pirelli C1–C5 compound identity per race (2019–present)

**Objective.** `compound_label` (HARD/MEDIUM/SOFT) has been relative since 2019 — Pirelli picks 3
of 5(+1) physical compounds per weekend and calls them hard/medium/soft for that race only, so
"SOFT" at one circuit is not the same rubber as "SOFT" at another. Nothing in this warehouse
currently records which C-number a label actually was. Land that mapping, sourced for real.

**Why 08a didn't need this and this item does anyway.** `dim_compounds_season`'s grain
(`circuit_key × compound_code × season`) already sidesteps the relativity problem for the fitted
physics parameters — it never pools "SOFT" across circuits, so it doesn't need to know the
C-number to be correct. This item is not a repair; it's new information — an absolute physical
scale that would let compound severity be compared *across* circuits/seasons on common ground,
and would let the fitted `compound_grip_peak`/`wear_gradient` ordering be sanity-checked against
Pirelli's own hardness ranking as an independent cross-check.

**On sourcing — read before starting.** Two LLM-generated attempts at this exact table were
rejected this session, both self-contradictory or fabricated: one had a "Supersoft" that its own
row list didn't contain, both invented a compound called "Ice Hard" (not a real Pirelli name, in
any season), and one asserted Monaco/Singapore 2025 raced on C6 when the sourced fact is that C6
was a limited *test* at Mexico City and Abu Dhabi in 2024, not a raced compound at those two
races in 2025. **Do not regenerate this table from a model's prior knowledge.** Every row must
trace to a specific Pirelli announcement.

**Method.** `transform/models/staging/stg_tyre_allocations.sql` already exists as an empty stub
with the target shape (`race_year, circuit_key, compound_code, compound_label,
allocated_sets_per_driver`) and a comment pointing at this exact gap — it just returns zero rows.
Source is `press.pirelli.com`'s per-round nomination posts, or a season-recap article that lists
every round in one place (denser, fewer pages to read). Read each source directly (WebFetch, not
recall), record the C-number → hard/medium/soft mapping per `(race_year, circuit_key)`, and cite
the source URL per season in the seed's provenance. `allocated_sets_per_driver` is FIA technical
allocation data, not something Pirelli's compound-choice announcements carry — expect to leave it
NULL, or drop the column, rather than inventing a number for it.

**Acceptance.** A seed lands with real rows for at least 2019–2024 (the 2018 legacy names are
already `dim_compounds_season`'s own `compound_code`, not in scope here), each row traceable to
a cited Pirelli source, `stg_tyre_allocations` no longer returns zero rows, and no row's value
was produced by asking a model to fill in the pattern.

**Definition of done.** `stg_tyre_allocations` is populated and tested (not_null on the four real
columns, accepted_values on compound_label); the history entry names the source article(s) used
per season.

---

## 08g — Decompose the `08e`/`08f` regression on the BEFORE substrate, and rule on `cliff_candidate_flag`

**Objective.** Gate steps 2–4 measured what each family is worth on the rebuilt substrate. They
did not, and could not, split step 1's regression between `08e` and `08f-2`. Run the identical
add-ablation on the BEFORE substrate so the split is measured rather than inferred, and use it to
rule on a column the AFTER arm found carries nothing.

**Why this is not bookkeeping.** `cliff_candidate_flag` is inside its floor on all five families
with an information term of 0.00–0.41× (largest 0.0031, and 0.0000009 on p50). Two readings, and
they fork:

- **It carried nothing before either** — then it is a dead column that has been in the contract
  since it was written, and the follow-up is a prune arm, not a repair.
- **It carried something before and the rebuild emptied it** — then `08f-2` destroyed a real
  feature, and the follow-up is a better construction (the MAD/z-score threshold in
  `int_lap_anomaly_flags` is calibrated against a `driver_skill_residual_s` whose level moved),
  not a prune.

Nothing in the AFTER arm distinguishes these, and the wrong choice is cheap to make and expensive
to keep.

**A live instance of the second reading, unattributed.** `cliff_candidate_flag` is TRUE on 1.835%
of 2018's rows against 0.470–1.258% for 2019–2024 (rows with `push_residual` non-NULL). 2018 is
exactly the season whose `circuit_constructor_interaction_s` the rebuild set identically to 0
across all 197 of its panel rows, so the constructor-circuit effect now flows into
`driver_skill_residual_s` and lands in front of a threshold calibrated without it. **That is a
mechanism, not a measurement** — 2019 sits at 1.258% with a full interaction value, so the
season-rate ordering does not by itself attribute anything. It is written down because it is the
first thing the BEFORE arm should check.

**Method.** Reproduce the step 1 A/B setup: revert `08e` and `08f` in place, rebuild the two
subtrees, and re-run the *same* four arms (`A`, `A+T`, `A+C`, full) plus both permutation-null
arms and both floors. `A` is the anchor — for `cliff_classifier` and `stint_life_regressor` it
takes no weights and excludes both families, so it must come back **bit-identical** to the AFTER
run's 0.3567748 / 2.0224465. That is this item's instrument check, and it is a real one: if `A`
moves, something outside the two families moved and the whole decomposition is void.

**The quantile trio needs a third arm.** `08f-1` moves the IPW `survival_weight`, which is not a
column, so `A` is *not* invariant for p10/p50/p90 and no column ablation can see it. Measure it
directly: the AFTER substrate's columns with the BEFORE weights, and the reverse. Without that arm
the trio's regression has three causes and two measurements.

**Acceptance.** The BEFORE-substrate add-ablation is reported in the same table shape as the AFTER
one, with `A` verified bit-identical on the two unweighted families; the T/C split of step 1's
regression is stated as a number for at least `cliff_classifier` and `stint_life_regressor`; and
`08f-1`'s weight channel is separated from the column channel for the quantile trio.

**Definition of done.** `cliff_candidate_flag` is ruled either **dead** (inside floor on both
substrates → opens a prune arm, which is itself an add-ablation someone gates) or **damaged**
(cleared its floor before, does not now → opens a reconstruction of the anomaly threshold), with
the number behind the ruling; and the working tree is restored to the AFTER substrate with
`dbt test` green, as step 1 restored it.
