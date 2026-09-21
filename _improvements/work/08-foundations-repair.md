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

> **STALE AS OF `08m` (2026-09-16) — every pinball number below is on the OLD target.**
> `08m` fixed how `int_compound_cliff_predicted.sql` consumes `compound_cliff_severity` and
> dropped the unfitted `0.002*age^2` term, then rebuilt the warehouse.
> `next_5_lap_cumulative_jump_s` is now **a different quantity**: its mean moved
> −1.8793 s → −0.3946 s, and `is_training_eligible` moved 82,470 → 81,619 rows. The absolute
> pinball losses, baselines and reseed floors in this section are therefore **not comparable to
> anything measured after that rebuild**, and the add-ablation *deltas* are not directly
> comparable either — both arms would have to be re-run on the rebuilt target. They were **not**
> re-measured by `08m`, which re-measured only the two acceptance numbers in its own RESULT.
> What is NOT invalidated: these deltas remain valid *relative to each other*, because every arm
> in the comparison was scored on the same (old) target. The leakage/forward-window rulings and
> the qualitative conclusions stand; only the numbers are on a superseded quantity.
>
> **SUPERSEDED FOR FAMILY T (2026-09-17).** Family T's gate has been **re-run on the `v12`/`08m`
> substrate** — see [`08e` — family T re-read](#08e--family-t-re-read-on-the-v1208m-substrate-2026-09-17)
> at the end of the `08e`/`08f` gate sections. All five targets clear their own floor on the
> rebuilt target, information-attributed, with the instrument check passing exactly against the
> published `v12` headline. Quote **that** table, not this one. The stale banner still governs
> `08f`, which was not re-read.



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

> **STALE AS OF `08m` (2026-09-16) — every pinball number below is on the OLD target.**
> `08m` fixed how `int_compound_cliff_predicted.sql` consumes `compound_cliff_severity` and
> dropped the unfitted `0.002*age^2` term, then rebuilt the warehouse.
> `next_5_lap_cumulative_jump_s` is now **a different quantity**: its mean moved
> −1.8793 s → −0.3946 s, and `is_training_eligible` moved 82,470 → 81,619 rows. The absolute
> pinball losses, baselines and reseed floors in this section are therefore **not comparable to
> anything measured after that rebuild**, and the add-ablation *deltas* are not directly
> comparable either — both arms would have to be re-run on the rebuilt target. They were **not**
> re-measured by `08m`, which re-measured only the two acceptance numbers in its own RESULT.
> What is NOT invalidated: these deltas remain valid *relative to each other*, because every arm
> in the comparison was scored on the same (old) target. The leakage/forward-window rulings and
> the qualitative conclusions stand; only the numbers are on a superseded quantity.
>
> **RE-READ COMPLETE, both halves (2026-09-17).** This banner still applies to every number
> *below*, which is left as history. The current numbers are in two new sections near the end of
> this item (after the `08e` re-read): `` `08f-2` — closed by measurement, not re-gated`` and
> `` `08f-1` — gate RESULT, isolated, on the v12/08m substrate``. `08f` stays `GATED`.



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

> **Correction (2026-09-17), from the 08f-1 gate.** `evaluate.py:613` (`_row_weights`) supplies
> `survival_weight` only as the **training** weight passed to `_fit` — `EvalSplit` carries `w_tr`
> only, no `w_ev`, and `_score`'s quantile branch calls `T._headline(spec, y_true, pred)` with no
> `meta` at all, so `pinball_loss` is unweighted at eval time (`grep -n "pinball_loss(" ml/src/*.py`
> shows exactly two call sites, both unweighted). So the channel this paragraph describes as
> "reaches both the fit and the metric" is, in the code as it stands today, **fit-only** — the
> metric reads eval-season information only insofar as a differently-weighted fit predicts
> differently on it, not through any direct reweighting of the eval loss. Whether this was accurate
> when written and changed in a later refactor, or was already the fit-only shape and mischaracterised
> here, was not traced — flagged as a correction either way, per BUILD-ORDER.md's deviation rule. It
> does not change the defect (a 2018 row's training weight is still partly estimated from 2024 data
> pre-08f-1) or the fix; it narrows how that defect reaches the headline. See the 08f-1 gate result
> below.

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

### `08e` — family T re-read on the `v12`/`08m` substrate (2026-09-17)

**Why this section exists.** The table above is on the target `08m` superseded, and the banner at
the head of `08e` says so. Decision `D3` ("Land `08e` + `08f`?") is explicitly waiting on those
deltas being **re-read**, not re-argued. This is the re-read: gate steps 1–4 and 7, re-run for
family T alone, on the warehouse as it stands today.

**One line of the Status paragraph above has itself gone stale and is left standing as history:**
`ml/artefacts/evaluation_metrics.json` no longer holds the v11 numbers. `08n` regenerated it, and
it is `v12` — which is what makes the instrument check below possible at all.

**What was NOT re-run, and why that is not a gap.** `08e`'s materiality half — the BLOCK vs
TRAILING correlation contrast, the position-matched swing table, the two sign inversions — was not
re-measured. `08m` moved the *label*; it did not touch the *leak*. The construction argument
(`baseline_cutoff_lap` is a deterministic function of the stint-life label's own numerator) and the
forward-reach census are both properties of the pre-rebuild SQL, which no longer exists. The
leakage ruling stands on its own evidence and does not depend on any number in this section.

**Design, and the one deliberate difference from the 2026-09-09 run.**

    baseline A  = the 32-column contract MINUS family T   (28 columns)
    arm    A+T  = the full 32-column contract

The 2026-09-09 run used a joint baseline excluding family T *and* family C
(`cliff_candidate_flag`), so one reference served both `08e` and `08f`. **`08j` has since pruned
`cliff_candidate_flag` from the contract outright** (ruled dead on both substrates by `08g`), so
"contract minus T" **is** the direct analogue of that run's `A`, and no family C arm exists to run.
The contract is 32 columns here rather than 33 for exactly that reason.

**Instrument check (gate step 1) — passes on all five, exactly.** The full-contract refit
reproduces the published `v12` headline on every target, to well inside six decimal places:
0.4764640778 / 0.9823587336 / 0.5128462338 / 0.3524660979 / 1.9913358779. The harness has not
moved, so every delta below is measured against a faithful reproduction of what is published.

**Family T on the rebuilt target — clears on all five, and it is information every time.**
`cv_final_fold`, train 2018–2023, eval 2024, through `evaluate.py`'s own `_fit`/`_predict_index`/
`_score`. Floors are 5 seed-only refits via `attribution.py::refit_noise_floor`, computed on **both**
arms, with every ratio quoted against the **larger** of the two — the conservative call, and the one
the 2026-09-09 run made.

| target | metric | A (28 cols) | A+T (32) | delta | ×floor | capacity | information | ×floor | E |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `degradation_regressor_p10` | pinball | 0.5429193 | 0.4764641 | **+0.0664552** | 9.95× | −0.0031177 (−0.47×) | +0.0695730 | **10.42×** | 35.91 |
| `degradation_regressor_p50` | pinball | 1.0499831 | 0.9823587 | **+0.0676244** | 6.06× | −0.0028325 (−0.25×) | +0.0704569 | **6.32×** | 35.46 |
| `degradation_regressor_p90` | pinball | 0.5440975 | 0.5128462 | **+0.0312513** | 3.39× | −0.0036515 (−0.40×) | +0.0349028 | **3.79×** | 31.16 |
| `cliff_classifier` | macro F1 | 0.3357970 | 0.3524661 | **+0.0166691** | 3.84× | +0.0018800 (+0.43×) | +0.0147892 | **3.41×** | 30.03 |
| `stint_life_regressor` | AFT nloglik | 2.0186246 | 1.9913359 | **+0.0272887** | 4.46× | +0.0028524 (+0.47×) | +0.0244363 | **4.00×** | 33.36 |

Deltas are oriented so **positive is improvement on every metric**. Five for five over their own
floors, and on every one of them the **information** term is larger than the total while the
**capacity** term sits inside the floor (|0.25×| to |0.47×|). On the three quantile targets capacity
is *negative* — four shuffled columns measurably hurt — so the family's whole contribution, and
slightly more, is its alignment with the label.

**NONE of these numbers may be subtracted from the 2026-09-09 table.** Both runs score a different
quantity; that is the entire reason this section exists. Two qualitative changes are worth naming
as **separate measurements read side by side**, never as a delta:

- p90 was the narrow case before (1.07× total, carried by a 1.35× information term). On the
  rebuilt target it is **not narrow** — 3.39× total, 3.79× information.
- p10's capacity term was the recorded anomaly before (+1.06× its own floor; shuffled columns
  hurt p10 enough to matter). On the rebuilt target p10's capacity is **−0.47×, inside the floor**.

**Gate step 7 — e-values, and the multiplicity reading.** Construction B (paired safe-t), n = 5
seeds, g = 1, declared on the **information** contrast (real vs its own per-seed shuffle) — the null
step 4 isolates, with capacity as a nuisance. The Monte Carlo validity check `e_value_construction.md`
§4 requires was run at four sigmas: mean `E` = 1.0016 / 0.9992 / 1.0108 / 1.0014 (±0.010), so the
construction is a valid e-value at this n. Max attainable `E` at n = 5, g = 1 is **36.0**, and four
of the five sit within 15% of that ceiling.

Within **this item's declared family of five**, e-BH at α = 0.05 rejects **all five** (sorted `E`
35.91 / 35.46 / 33.36 / 31.16 / 30.03 against thresholds `m/(αk)` = 100 / 50 / 33.33 / 25 / 20;
k\* = 5). **Stated with its limit:** that is a within-item count. The campaign-level family is
larger and `04a` owns enumerating it, and because the threshold scales with family size while this
construction caps at `E` = 36, these five cannot carry an arbitrarily large campaign family on their
own. The within-item result is reported as what it is and handed to `04a`.

**The negative controls, reported rather than rounded up.** Shuffle-vs-shuffle on family T, where H0
is true by construction: `E` = 0.493 / 0.458 / 1.220 / 1.097 — and **3.282 on p10**. Under H0 `E`
has mean 1 with a heavy right tail, so one control of five at 3.28 is unremarkable (it is nowhere
near the 20 that a rejection needs), but it is the largest control in the set and it sits on the
same target as the largest headline `E`, so it is recorded rather than omitted.

**Verified.**

- All five instrument checks against `ml/artefacts/evaluation_metrics.json` (`version: v12`).
- `features.py --check` on this substrate: `[forward-window audit] CLEAN`,
  `[aggregation-scope audit] CLEAN`, `[leakage guard] CLEAN (32 features)`, train rows **81,619** —
  i.e. `08m`'s row count, confirming the measurement is on the rebuilt target and not a stale build.
- `dbt test --select assert_no_future_leakage assert_stint_boundary_integrity` — **PASS, PASS** on
  the post-`08m` warehouse. The guard `08e` rewrote still holds after the target rebuild.
- **Zero `known_leak` entries remain anywhere in `transform/models/`**, and `int_lap_thermal_proxy`
  carries no `aggregation_scope_exemptions` block at all — the "no finding" branch of the definition
  of done, not the "accepted" one.
- `best_params` files are not version-keyed and are unmodified, so v11 and v12 refit from identical
  tuned params.

**Assumed.**

- `stint_life_regressor`'s arm is measured with the params `10d`/`10e` are expected to move (`02c`
  bars this family from its own arms for that reason). Its family-T result is reported because
  `08e`'s definition of done names three families; it should be re-read after `10e`, like every
  other stint-life number.
- `08n` verified `stint_life_regressor`'s target *values* are unchanged by `08m`, which would make
  its old and new family-T numbers nominally comparable — **the subtraction is still declined**,
  because its row set moved 121,193 → 119,822 via `anomaly_class` → `is_training_eligible`. That is
  population, not disagreement.
- That family T is still exactly these four columns was re-checked against the contract, not
  re-traced through the lineage; `int_lap_thermal_proxy`'s consumer set was last traced 2026-09-09.

**Gates run.** 1 (instrument check, all five), 2 (add-ablation, identical split), 3 (each arm's own
reseed floor, larger of the two quoted), 4 (permutation null, capacity and information separate),
5 (`features.py --check`, re-run this session), 7 (e-value declared before the arm ran, with its MC
validity check). Step 6 is satisfied by this section naming the design before the table.

**What this does and does not settle.** It settles that family T earns its place in the contract on
the target the warehouse actually computes today: the `08e` rebuild is not a degraded remnant of a
leaky feature, it is the largest single block in the contract on the degradation quantiles. It does
**not** re-price `08f`, whose deltas carry the same stale banner and whose family C column no longer
exists to ablate — `D3` bundles the two, and only the `08e` half is re-read here. Nothing was
committed and `build-log.json` was not touched.

**Artefact.** `ml/artefacts/08e_thermal_family_arms.json` — every fit's headline, per seed, so any
ratio or e-value above can be recomputed without refitting. Produced by
`scripts/arms_08e_thermal_family.py`.

---

### `08f-2` — closed by measurement, not re-gated (2026-09-17)

**Why this is closure, not a new gate run.** `08f-2`'s only live-feature path was
`cliff_candidate_flag`, already ruled dead on both substrates (`08g`, pruned by `08j`) — that
ablation target no longer exists. The 2026-09-17 probe asked the one question left: does `08f-2`
move the model's actual **targets**, since `driver_skill_residual_s` — barred as a feature input —
still feeds several of them (`next_5_lap_cumulative_jump_s`/`DEGRADATION_TARGET`,
`next_3_lap_cumulative_jump_s`, `drift_s_per_lap`, `laps_until_cliff_class`/`CLIFF_TARGET`).
Isolated-warehouse before/after diff, over the full 137,447-row population: `circuit_constructor_interaction_s`
changes on all 1,456 (race, constructor) cells (mean |Δ| 0.086s) and `driver_skill_residual_s` moves
1:1 on 99.8% of rows — but every target is unchanged to float noise (max |Δ| 1.8e-15 to 2.5e-14; 0
of 137,447 rows cross a `laps_until_cliff_class` boundary; 0 of 7,064 stints' `drift_s_per_lap`
moves). Proven algebraically, not just measured: the shift is an exact constant within every
`(race_year, race_id, constructor_id)` group (max within-group stddev 6.7e-16, machine-epsilon
scale), and every target checked is built from within-stint differences or a per-stint OLS slope,
so the constant cancels exactly. Full detail: `_improvements/eval/08f/README.md` and
`MEASUREMENTS.md`. **No add-ablation gate is meaningful for a change proven to touch zero live
features and zero targets** — that is the definition of done for this half, met by measurement
rather than by a floor ratio.

---

### `08f-1` — gate RESULT, isolated, on the v12/08m substrate (2026-09-17)

**Why this exists.** `08f-1` had never been gated alone. The one prior measurement touching it (the
2026-09-09 "gate step 1 re-baseline" above) reverted `08e` **and** both `08f` halves together in one
combined A/B — it cannot isolate `08f-1`'s own marginal effect, and it predates both `08j` (contract
33→32 features) and `08m`/`08n` (target rebuilt, v11→v12). This is that isolation, run fresh against
the current substrate.

**The commit, independently verified.** `git log --follow` on `fct_cliff_prediction_features.sql`'s
own history names `bbe3e48` (2026-09-09) as the commit introducing the season-lag rewrite; its
immediate predecessor `c7de693` is the pre-08f-1 content. `git diff c7de693 bbe3e48 -- <path>` shows
exactly that rewrite plus one unrelated bundled addition (`baseline_observations_n`, `08e`'s
companion column) — so the correct isolation is a hand revert of the three survival-weight CTEs
only, not `git show c7de693:<path>` wholesale. `bbe3e48` is also the commit that introduced `08f-2`
in the interaction model (see the correction above `08g`'s citation) — both halves of `08f` landed
in one squashed commit with an unrelated message.

**Because `survival_weight` is a sample weight, never a `FEATURE_COLUMNS` member, gates.md's
add/drop-a-column framework does not apply literally.** Translated: baseline arm `A` = uniform
weights (w=1, the zero point a weight-scheme ablation drops *to*); arm `BEFORE` = the season-pooled
IPW (pre-fix); arm `AFTER` = the season-lagged IPW (shipped). Full translation of all seven gate
steps, pre-registered before the arms ran, is in `scripts/gate_08f1_survival_weight.py`'s docstring
and `_improvements/eval/08f/README.md`.

**Headline: every one of the five deltas is inside its own reseed floor.**

| target | metric | AFTER (=published v12) | BEFORE (pooled) | delta | floor | ratio |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: |
| `degradation_regressor_p10` | pinball | 0.4764640778 | 0.4802231706 | +0.00375909 | 0.00763075 | 0.49× |
| `degradation_regressor_p50` | pinball | 0.9823587336 | 0.9840438286 | +0.00168510 | 0.01115092 | 0.15× |
| `degradation_regressor_p90` | pinball | 0.5128462338 | 0.5122840197 | −0.00056221 | 0.00839541 | −0.07× |
| `cliff_classifier` | macro F1 | 0.3524660979 | = AFTER, 0 by construction | 0.0 | n/a | n/a |
| `stint_life_regressor` | AFT nloglik | 1.9913358779 | = AFTER, 0 by construction | 0.0 | n/a | n/a |

AFTER's three quantile headlines reproduce `08e`'s own independent v12 re-read (`A+T` cell) to the
digits shown — a second, independently-built isolated warehouse reproducing the same numbers.
`cliff_classifier`/`stint_life_regressor` invariance is Verified two ways: code trace
(`train.py::_sample_weight` never reads `survival_weight` for these kinds) and a row-level warehouse
diff (0 of 32 `FEATURE_COLUMNS` differ, target columns differ by exactly 0.0, between the AFTER and
BEFORE snapshots).

**The weight vector moves substantially — this is not a null for lack of a real change.** 93.3% of
training rows (63,344/67,907) get a different `survival_weight`; mean shifts 1.711→1.970, max
per-row |Δ| 2.97. 08f-1 does exactly what it is meant to do to the training weights; that
substantial reweighting still does not move any of the three quantile headlines past noise on
`eval_season` 2024.

**Secondary finding, out of scope for 08f-1's own ruling, recorded because it fell out of the same
arms.** Both IPW schemes underperform *uniform* (no reweighting at all) on all three quantile heads
— AFTER is closer to uniform than BEFORE on p10/p50, marginally further on p90 — and on p10 the
permutation null's information term clears its floor as a real cost for **both** schemes alike
(AFTER −1.30×, BEFORE −1.06×). This says something about IPW reweighting as a mechanism, not about
the season-lag specifically (the sign and rough magnitude match whichever scheme is used), so it is
named here and not ruled on.

**Verdict.** `08f-1` is a real, substantial correctness fix (a 2018 row's training weight is no
longer partly estimated from 2024) whose effect on every headline metric this tree scores is not
distinguishable from refit noise, on the current substrate. Different from `08e` (a genuine,
floor-clearing win) and from the original combined step-1 finding (removing `08e`+`08f`'s
contamination cost headline performance, on the pre-08m target) — `08f-1` measured alone, on the
current target, costs nothing and wins nothing detectable. A clean null is the correct, complete
outcome of this gate, not a failure to run it.

**Gates run.** 1 (instrument check: published-v12 reproduction + row-level diff outside
`survival_weight`), 2 (the weight-scheme A/B), 3 (each arm's own 5-reseed floor, larger quoted), 4
(permutation null, translated to a weight-vector shuffle), 5 (`features.py --check`, this session —
unaffected, 32 features), 6 (design pre-registered in the script docstring before the arms ran), 7
(e-value on the information contrast, Construction B, with its MC validity check and negative
controls — largest E in the whole gate is a negative control, p50 shuffle-vs-shuffle at 8.76, out of
a max attainable 36.0). Full tables: `_improvements/eval/08f/MEASUREMENTS.md`. Artefact:
`_improvements/eval/08f/08f1_gate_arms.json` / `.log`, produced by
`scripts/gate_08f1_survival_weight.py`.

**Status.** Both `08f` halves are now complete on the v12/08m substrate. `08f` stays `GATED` (it
already was, from the 2026-09-09 run whose gates genuinely ran) — this re-read replaces the stale
numbers rather than changing the stage. Landing remains bundled with `08e` under decision `D3`,
which is not decided here.

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

### `08d` — BUILT 2026-09-10 on user-supplied data, and NOT sourced

**Status: `BUILDING`, deliberately not `LANDED`.** The table is in the warehouse and every
mechanical clause of the definition of done is met. The **acceptance** clause is not: "each row
traceable to a cited Pirelli source… no row's value was produced by asking a model to fill in the
pattern." That clause is unmet and the item stays open until it is.

**What is in the warehouse.** `transform/seeds/tyre_allocations.csv`, 128 rows — one per race,
wide (`race_year, circuit_key, hard_code, medium_code, soft_code, source_url`).
`stg_tyre_allocations` unpivots it to 384 rows at (race, label) grain. 16 dbt tests pass.
**All 127 mart races in 2019–2024 match**, so the join is total, not partial. The 128th row is
`(2021, belgian_grand_prix)` — the rain-shortened race, present in `int_stint_geometry`
(race `2021_12`, 60 laps) but absent from the mart.

It does the job the item exists for: 2024 `SOFT` resolves to **C3** at Bahrain, Silverstone,
Zandvoort, Suzuka, Qatar and Barcelona but **C4** at Spa and Shanghai — the relativity that
`compound_label` alone cannot express.

**Provenance — the reason this is not `LANDED`.** The data is **user-supplied and self-verified**,
accepted on the user's explicit instruction to unblock downstream work. It was **not** obtained by
the sourcing method this spec requires. Measured, not asserted: **only 47 of the 128 `source_url`
values resolve; 81 return 404** against the live press site, which no longer serves its pre-2025
archive. A URL in that column is an *attribution*, not evidence.

Three prior revisions of this table were rejected before this one, and the audit trail matters
because it shows what the checks caught:

- **Rev 1** asserted Monaco/Singapore/Baku/Montreal 2025 on C6 — the exact fabrication this spec
  already names as previously rejected — and carried **zero** citations across ~30 venues.
- **Rev 2** added citations but 59% were unusable: all 21 of 2019 cited a *search results page*
  (fetched and confirmed to name no compounds at all); all 17 of 2020 cited a 404; all 22 of 2021
  cited a **pre-season nomination list** which — fetched and read — contains the originally
  scheduled 23 rounds including four that were cancelled, omits Styria, Turkey and Qatar (three
  rows citing it), and gives Austria C2/C3/C4 against the row's claimed C3/C4/C5. It also used
  nine keys absent from the warehouse (`sao_paulo_grand_prix` for `são_paulo_grand_prix`,
  `mexican_grand_prix` for `mexico_city_grand_prix` from 2021 on).
- **Rev 3** (the one that landed) fixed every key and switched to per-race previews. One compound
  value changed silently between rev 2 and rev 3 — **2024 Monza C3/C4/C5 → C2/C3/C4** — in the
  eval season, and that change is **unresolved**: it was not checked at source before the build
  was stopped.

**Three rows verified at source, and they held.** Worth recording because two were flags raised
against the data that turned out to be wrong:

- **2022 Australia C2/C3/C5** — the preview states *"the P Zero White hard is the C2 compound"* …
  *"it's the softest C5 compound as the P Zero Red soft."* The non-consecutive C4 skip is real.
- **2022 Emilia-Romagna** — cited to a URL slugged `2022-italian-grand-prix---preview`, which
  looked like a mis-citation and is not: Pirelli's own slug is wrong, the page is the Imola
  preview, and it states C2/C3/C4 for Emilia-Romagna.
- **2024 Americas** — Austin C2/C3/C4, Mexico City C3/C4/C5, São Paulo C3/C4/C5, all confirmed.

**What must happen before this can be `LANDED`.** Re-source 2019–2022 from an archival route
(FIA event documents are the obvious candidate — regulator-issued, per-event, and they cover the
span); resolve the 2024 Monza discrepancy; then either replace the values or confirm them and
record which. Until then **nothing measured against this table may be quoted as a claim** — that
is [`../foundations/epistemics.md`](../foundations/epistemics.md)'s line, and a table whose
provenance is "accepted to keep moving" sits on the wrong side of it.

**Warehouse state.** `dbt seed --full-refresh` + `dbt run` on the one model + 16 tests, all green.
A full `dbt build` was started and **interrupted at model 215 of 723** at the user's request. No
damage: the mart anchors are unchanged — `fct_cliff_prediction_features` 137,447 rows, 121,193
training-eligible, `push_residual` coverage 98.275%, all three matching the `08e`/`08f` baselines
exactly. **A full `dbt build` should still be run before any measurement is taken.** Nothing
committed.

A stale `tyre_allocations` table from an earlier agent run was found in `dev.duckdb` carrying a
5-column `season` schema, which dbt was silently inheriting as the seed's column spec; it was
dropped via `--full-refresh`. It could not have pre-existed this session — the stub had no
`ref()`.

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

### 08g — RESULT 2026-09-09: `cliff_candidate_flag` is dead, not damaged

**Method, and a change from step 1's own.** Step 1 reverted `08e`/`08f` in place on
`data/dev.duckdb` itself and restored it from backups afterward. Here the BEFORE substrate was
built into an **isolated warehouse copy** instead: a `gate_before` dbt target
(`data/gate_before.duckdb`, added to `transform/profiles/profiles.yml` for the duration of this
session and removed afterward) built from the same bronze source files dev uses — sources are
`external_location` parquet paths, independent of which `.duckdb` file a target materialises into,
so a full `dbt seed && dbt run --target gate_before` reproduces dev's lineage from scratch without
ever opening dev.duckdb for write. `int_lap_thermal_proxy.sql` and
`int_circuit_x_constructor_interaction.sql` were reverted wholesale to their pre-`08e`/pre-`08f-2`
content (`git show c7c8509:<path>`, each confirmed a clean, self-contained diff against HEAD before
reverting).

> **Correction (2026-09-17), per BUILD-ORDER.md's deviation rule.** `c7c8509` is correct for
> `int_lap_thermal_proxy.sql` (08e) but **wrong** for isolating `int_circuit_x_constructor_interaction.sql`
> (08f-2) **alone**: `git log --follow` on that file shows `c7c8509` predates an unrelated later fix
> to the same file (pooling on the physical `circuit_id` rather than the event-slug `circuit_key`),
> so reverting to it for an 08f-2-only isolation would silently revert that too. The commit that
> actually introduced 08f-2's point-in-time rewrite in this file is `bbe3e48` (2026-09-09, despite an
> unrelated commit message); its immediate predecessor in the file's own history, `e5bcd35`, is the
> correct pre-08f-2 content — confirmed with `git diff e5bcd35 bbe3e48 -- <path>` showing exactly the
> `GROUP BY` → window-function rewrite and nothing else. This note does not re-litigate 08g's own
> ruling below (out of scope for this correction, and 08g is terminal) — it flags only that `c7c8509`
> is the wrong citation for anyone who needs to isolate 08f-2 **by itself** in this file, which
> nobody had needed to do until the 2026-09-17 probe — see `_improvements/eval/08f/README.md` and
> `scripts/measure_08f2_label_impact.py`. `bbe3e48` also turns out to be the same commit that
> introduced `08f-1`'s season-lag rewrite in `fct_cliff_prediction_features.sql` (see `08f`'s own
> section below) — both halves of `08f` landed in one squashed commit with an unrelated message.

`fct_cliff_prediction_features.sql` and its mart `schema.yml` contract entry were
hand-edited to remove only the `08e` companion column and un-lag the `08f-1` survival curve, because
the file also carries three unrelated rebuilds from the same squashed commit (the Phase 10a
proximity block, the cliff-bucket forward-scan fix, the multi-horizon target rework) that had to
stay. Built once with the unedited (AFTER) tree first as a pipeline sanity check — row count
137,447 both sides, zero-row diff on every family-relevant column against dev.duckdb, the sole
exception being `next_5_lap_cumulative_jump_s` at max abs diff 8.17e-14, the same
non-associative-float-under-threading noise step 1 already named. Then rebuilt with the BEFORE
edits in place. `dev.duckdb`'s mtime was checked before and after (unchanged; no dbt process ran
against `--target dev` at any point) and its training-eligible push_residual coverage re-verified
at 98.275% afterward, confirming it never left the AFTER state. The working tree was restored via
`git checkout HEAD --` on the four touched files immediately after the BEFORE build succeeded, and
`data/gate_before.duckdb` plus the profile block were deleted once the probe finished reading it —
nothing from this session persists on disk. **This method is available to `08h`/`08i` too** and is
cheaper to reason about than step 1's in-place revert: dev.duckdb is categorically never at risk,
so there is no restore step to get wrong.

**Instrument check passes on both targets, to better than 1e-6.** Arm `A` (contract minus both
families) on the BEFORE substrate: `cliff_classifier` 0.3567747940075294 against the AFTER run's
0.3567748 (|Δ| 6.0e-9); `stint_life_regressor` 2.022446495893194 against 2.0224465 (|Δ| 4.1e-9).
Nothing outside the two families moved. As an unplanned second instrument check, the quantile
trio's native BEFORE cell (BEFORE columns, BEFORE weights) and native AFTER cell were also refit
independently here and reproduce the already-published v11 and re-baseline numbers to
1.5e-8 / 4.2e-10 or better on all three heads (table below) — the harness is confirmed stable
across a third, independently-built copy of the warehouse.

**Family T (the four thermal columns, `08e`) on the BEFORE substrate — still clears, at roughly
half the AFTER-substrate size.** Add-delta against arm `A`, x-floor against
`max(floor(A), floor(full))`:

| target | add-delta (BEFORE) | x-floor | information | x-floor | AFTER-substrate add-delta (gate steps 2-4) |
| :--- | ---: | ---: | ---: | ---: | ---: |
| `cliff_classifier` (macro F1) | **+0.0230359** | 4.38x | +0.0264612 | 5.03x CLEARS | +0.0141401 (2.41x) |
| `stint_life_regressor` (AFT nloglik) | **−0.0735218** | 9.53x | −0.0702188 | 9.10x CLEARS | −0.0336961 (4.37x) |

Both clear on the BEFORE substrate too, so family T was never *only* a leakage artifact — but its
own marginal contribution is **roughly halved** by the `08e`/`08f-2` rebuild on both targets (macro
F1: 4.38x → 2.41x; AFT nloglik: 9.53x → 4.37x). That is consistent with, and adds a second
instrument to, `08e`'s own materiality finding that the contaminated baseline inflated
`push_residual`'s apparent relationship with the label: part of what family T was "worth" before the
rebuild was the leak itself, and the rebuild removed that part while leaving a real, smaller signal
behind.

**Family C (`cliff_candidate_flag`, the only column the `08f-2` chain reaches) is inside its floor
on the BEFORE substrate too, on both totals and information:**

| target | add-delta (BEFORE) | x-floor | information | x-floor |
| :--- | ---: | ---: | ---: | ---: |
| `cliff_classifier` | −0.0005112 | 0.10x | −0.0033409 | 0.64x |
| `stint_life_regressor` | −0.0014948 | 0.19x | −0.0000307 | 0.004x |

**Ruling: DEAD, not damaged.** `cliff_candidate_flag` does not clear its floor before the `08f-2`
rebuild any more than after it — the column has carried nothing since it was written, and `08f-2`'s
zeroing of 2018's `circuit_constructor_interaction_s` is not what emptied it, because there was
nothing to empty. This resolves the fork `08g` exists to resolve: `08j` runs the **prune arm**, not
a threshold reconstruction.

**Additivity check.** `A + (A+T − A) + (A+C − A)` against the measured `full` arm: cliff
0.3792996 implied vs 0.3802680 actual, residual +0.0009685 (0.28x `full`'s own floor); stint life
1.9474299 implied vs 1.9487233 actual, residual +0.0012934 (0.46x `full`'s own floor). Both
residuals are inside `full`'s own reseed floor, so `T` and `C` combine ~additively on the BEFORE
substrate — consistent with `C` carrying nothing: a dead column has little room to interact with a
live one.

**The quantile trio's weight channel is separated from its column channel.** `08f-1` moves the IPW
`survival_weight`, invisible to any column ablation, so arm `A` is not the right instrument here;
instead this runs the full 2×2 (BEFORE/AFTER columns) × (BEFORE/AFTER weights), aligned by
`lap_id` (row sets verified identical between the BEFORE and AFTER builds on all three heads — the
degradation target depends only on `driver_skill_residual_s` and `drift_s_per_lap`, neither of
which either family touches). Two of the four cells reproduce already-published numbers (validation
column) and the other two are new:

| target | BEFORE cols / BEFORE w | AFTER cols / AFTER w | AFTER cols / BEFORE w | BEFORE cols / AFTER w | column channel | weight channel |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| p10 pinball | 0.5187980 | 0.5353710 | 0.5314593 | 0.5186341 | +0.0146991 (89%) | +0.0018739 (11%) |
| p50 pinball | 1.0163386 | 1.0407823 | 1.0275016 | 1.0199334 | +0.0160059 (65%) | +0.0084378 (35%) |
| p90 pinball | 0.5600310 | 0.5660356 | 0.5690087 | 0.5545901 | +0.0102116 (170%) | −0.0042070 (−70%) |

(column channel = mean of the two same-weight cross-differences; weight channel = mean of the two
same-column cross-differences; the two sum to the total AFTER−BEFORE delta exactly, by
construction, on all three heads — 0.0165730 / 0.0244437 / 0.0060046, matching gate step 1.) The
column rebuild (`08e` + `08f-2` together — this design cannot separate them further) accounts for
most or all of the regression on every head. The weight channel (`08f-1` alone) moves the same
direction as the total on p10/p50 but **the opposite direction on p90** — season-lagging the IPW
curve would, on its own, have been a small p90 *improvement* (−0.0042070); it is the column changes
that cost more than the total and the weight channel claws a third of it back.

**Verified.** All headline figures above via `evaluate.py`'s own `_fit`/`_score`/`_predict_index`
and `attribution.py::refit_noise_floor` (5 reseeds, `RANDOM_STATE`..`RANDOM_STATE+4`), on
`cv_final_fold`, exactly as gates.md steps 1-3 specify. Permutation-null: gates.md step 4, one row
permutation per family per split (train and eval shuffled independently), applied jointly across a
family's columns so its own cross-column correlation survives and only row alignment to the label is
destroyed. Row-set identity between the BEFORE and AFTER builds for the quantile trio (68,574
train / 13,896 eval both sides) and the resulting `y` alignment (max abs diff 2.5e-14 train, 6.8e-14
eval — float noise, not a mismatch).

**Assumed.** The floor denominator convention (`max(floor(A), floor(full))`, shared across both
families) is this session's reading of the AFTER-substrate note's "x-floor against the larger of
the full and baseline 5-reseed floor" — the alternative reading (a separate `floor(A+T)` /
`floor(A+C)` denominator per family) was not what was used; both `A+T`'s and `A+C`'s own floors were
computed anyway (0.0050677 / 0.0042533 cliff, 0.0024979 / 0.0104361 life) and are smaller than
`floor(A)` on three of four, so this choice is conservative (produces smaller x-floor ratios,
never larger) rather than favourable to CLEARS. The permutation-null's random seeds (`RANDOM_STATE`,
`RANDOM_STATE+1` for train; `+100`, `+101` for eval, one pair per family) are a single draw each, not
resampled — gates.md step 4 does not call for repetition, and none of the four totals/information
readings sit close enough to their floor to be seed-sensitive at the level this decomposition
reports to.

**Gates run.** Steps 1-4 for both families on the BEFORE substrate, step 1's instrument check
additionally cross-validated on the quantile trio. Step 5 not re-run (unchanged since gate steps
2-4; nothing in this session touches the feature contract). Step 6 satisfied in advance — the four
arms, the permutation-null, and the weight/column split were all named in the `08g` spec before this
session ran them.

---

## 08h — `baseline_observations_n` as a feature: the add-ablation `08e` deferred

> **RE-MEASURED ON THE `v12`/`08m` SUBSTRATE (2026-09-17), and RULED. The column is measured
> and REJECTED — it is not in `FEATURE_COLUMNS` and the contract stays at 32 columns.** The
> stale-target banner that used to sit here is gone because the arms were re-run on the rebuilt
> target, not because it stopped applying: the `2026-09-09` numbers were on the pre-`08m`
> quantity and are **superseded**. See the RESULT at the end of this section.

<!-- superseded banner, kept for the record:
> **STALE AS OF `08m` (2026-09-16) — every pinball number below is on the OLD target.**
> `08m` fixed how `int_compound_cliff_predicted.sql` consumes `compound_cliff_severity` and
> dropped the unfitted `0.002*age^2` term, then rebuilt the warehouse.
> `next_5_lap_cumulative_jump_s` is now **a different quantity**: its mean moved
> −1.8793 s → −0.3946 s, and `is_training_eligible` moved 82,470 → 81,619 rows. The absolute
> pinball losses, baselines and reseed floors in this section are therefore **not comparable to
> anything measured after that rebuild**, and the add-ablation *deltas* are not directly
> comparable either — both arms would have to be re-run on the rebuilt target. They were **not**
> re-measured by `08m`, which re-measured only the two acceptance numbers in its own RESULT.
> What is NOT invalidated: these deltas remain valid *relative to each other*, because every arm
> in the comparison was scored on the same (old) target. The leakage/forward-window rulings and
> the qualitative conclusions stand; only the numbers are on a superseded quantity.
-->

**Objective.** `08e` shipped `baseline_observations_n` into the enforced mart contract and
deliberately kept it out of `FEATURE_COLUMNS`, on the stated ground that putting it in `X` is an
add-ablation someone has to gate. Run that gate.

**Why it is the first thing to try.** The trailing rebuild replaced one baseline of uniform
provenance with baselines of wildly varying evidence: the column runs 0–75 with a mean of 12.5
over the 137,447 mart rows, so a lap-3 row's baseline rests on two prior laps and a lap-30 row's on
twenty. The model currently cannot tell those apart, and the difference is exactly the uncertainty
the rebuild introduced. This is the cheapest candidate for recovering part of what step 1 priced,
and unlike a new sensor it costs no new ingestion.

**It is not free, and the hazard is named in `08e`.** The NULLs are deterministic on
count-of-valid-prior-laps, which is **not a contract axis** — `02a`'s declarability argument does
not carry over. Shipping the count so a consumer can condition on the missingness is one thing;
putting it in `X` makes the model's behaviour depend on an axis nothing declares. That is the
trade this item has to price, not assume.

> **Two corrections to this spec, found before the arms ran (2026-09-17).**
>
> 1. **The contract is 32 columns, not 33.** "33 → 34" below predates `08j` (which pruned
>    `cliff_candidate_flag`) and `08k` (which rebuilt the artefacts against the resulting
>    32-feature contract). The arms actually run are **32 → 33**. The ordering note's premise is
>    unaffected — see below.
> 2. **`baseline_observations_n` has no NULLs.** It is non-NULL on all 137,447 mart rows; it is
>    `0`, not NULL, where there is no evidence. The NULLs that are deterministic on it are
>    `push_residual`'s and the three other thermal columns'. Verified: `push_residual` is NULL on
>    **100.0%** of rows where the count is `0`, in both train and eval. (The implication runs one
>    way only — 2.3% of train rows with a non-zero count also have a NULL `push_residual`,
>    because the *current* lap can be invalid too. `marts/schema.yml`'s "NULL exactly where it is
>    0" is therefore slightly overstated.) This does not soften the hazard, which is about the
>    **axis**, not about a NULL pattern.

**Method.** Add-ablation on `cv_final_fold`, 33 columns → 34, through `evaluate.py`'s own
`_fit`/`_score`, against each family's own 5-reseed floor, with the permutation-null arm — the same
three arms `08e`/`08f` just went through. Also run it as a **pair** with `push_residual`: a count of
evidence is only meaningful beside the estimate it qualifies, so a joint arm distinguishes "the
model wants the uncertainty" from "the model wants another counter" (`attribution.py`'s
counter-like channel note is the relevant prior — prefix means of counters are rank-equivalent to
the counter).

**Ordering — this must run AFTER `08g`.** It changes the feature contract, and `08g`'s instrument
check is that arm `A` (contract minus both families) returns bit-identical to 0.3567748 and
2.0224465. A 34-column contract makes arm `A` a different arm and voids that check.

> **Satisfied, and moot in the end.** `08g` is `CLOSED`. And because this item **rejects** the
> column, the contract never moved: `08g`'s arm `A` is still the arm it was. Nothing downstream
> of `08g` needs re-running on account of `08h`.

**Definition of done.** The column is either in `FEATURE_COLUMNS` with a delta that cleared its
floor and was attributed to information by the permutation-null, or it is recorded as measured and
rejected with the number, and the declarability hazard is ruled on either way.

### `08h` — RESULT 2026-09-17: measured and **REJECTED** on the `v12`/`08m` substrate. No family clears its own floor (best **0.98×**, `p50`), no family clears on information, and the pair arm with `push_residual` shows no synergy above a floor anywhere. The declarability hazard is **declined**, and the measurement makes that an easy call rather than a close one.

Full tables in [`../eval/08h/MEASUREMENTS.md`](../eval/08h/MEASUREMENTS.md); artefact at
`ml/artefacts/08h_baseline_observations_n_arms.json`.

**Gate steps 2–3 — add-ablation (32 → 33) against each family's own 5-reseed floor.** Positive
delta means improvement on every metric; floor quoted against the larger of the baseline-arm and
add-arm floor, the `08g` convention.

| family | metric | baseline (32) | add (33) | delta | floor | x-floor | clears |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | :---: |
| `degradation_regressor_p10` | pinball | 0.476464 | 0.474687 | +0.001777 | 0.006343 | **0.28×** | NO |
| `degradation_regressor_p50` | pinball | 0.982359 | 0.971406 | +0.010953 | 0.011151 | **0.98×** | NO |
| `degradation_regressor_p90` | pinball | 0.512846 | 0.508681 | +0.004165 | 0.008395 | **0.50×** | NO |
| `cliff_classifier` | macro F1 | 0.352466 | 0.355676 | +0.003209 | 0.005083 | **0.63×** | NO |
| `stint_life_regressor` | AFT nloglik | 1.991336 | 1.991175 | +0.000161 | 0.006113 | **0.03×** | NO |

Every delta points the right way — the column is not harmful on the headline, it is just smaller
than the noise the refit already carries. `p50` misses by one part in fifty, which is exactly the
case the floor exists to refuse.

**Gate step 4 — permutation null.** Capacity (`shuffled − baseline`) and information
(`real − shuffled`), shuffled in train *and* eval:

| family | capacity | x-floor | information | x-floor | info clears | E(info) |
| :--- | ---: | ---: | ---: | ---: | :---: | ---: |
| `degradation_regressor_p10` | +0.001331 | 0.21× | +0.000446 | **0.07×** | NO | 0.549 |
| `degradation_regressor_p50` | +0.005601 | 0.50× | +0.005352 | **0.48×** | NO | **6.729** |
| `degradation_regressor_p90` | +0.001224 | 0.15× | +0.002941 | **0.35×** | NO | 0.412 |
| `cliff_classifier` | −0.001302 | −0.26× | +0.004511 | **0.89×** | NO | 0.851 |
| `stint_life_regressor` | +0.002477 | 0.41× | **−0.002316** | **−0.38×** | NO | 2.414 (dir −) |

On `p10`/`p50` capacity is as large as information — a third column of anything gives the booster
room. On `stint_life_regressor` the headline gain is **entirely** capacity and the information
term is negative; both are inside the floor, so it is a direction rather than a finding, but it is
the opposite direction from the one that would justify the column.

**The pair arm with `push_residual` — and the reference arm that makes it readable.** A joint
shuffle of `{baseline_observations_n, push_residual}` destroys `push_residual` too, and that is an
already-gated column carrying real signal, so the joint arm's size is mostly its. `push_residual`
shuffled **alone**, on the same permutation streams, is the missing comparator:

| family | info(cand) | info(`push_residual`) | sum | info(pair) | synergy | x-floor | E(pair) | E(`push_res`) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `degradation_regressor_p10` | +0.000787 | +0.050047 | +0.050834 | +0.050961 | +0.000126 | 0.02× | 35.67 | **34.70** |
| `degradation_regressor_p50` | +0.006960 | +0.055799 | +0.062759 | +0.068317 | +0.005558 | 0.50× | 33.49 | **34.77** |
| `degradation_regressor_p90` | +0.000270 | +0.006865 | +0.007135 | +0.014007 | +0.006872 | 0.82× | 12.07 | **6.44** |
| `cliff_classifier` | +0.001968 | −0.001106 | +0.000862 | +0.001694 | +0.000831 | 0.16× | 0.72 | **0.47** |
| `stint_life_regressor` | −0.000945 | +0.000894 | −0.000051 | −0.000802 | −0.000751 | −0.12× | 0.45 | **0.48** |

E(pair) 35.67 against E(`push_residual` alone) 34.70 on `p10`: **the pair arm is
`push_residual`.** On `p50` the pair is weaker than `push_residual` alone. **Synergy clears no
floor on any family** (largest `p90`, 0.82×), so the count is not functioning as the uncertainty
that qualifies the estimate — whatever it carries is a separate, additive channel. That is the
leaf doc's question answered, and answered against the column.

> **This overturns a first pass at this item run earlier the same day**, which compared E(pair)
> against E(candidate) (35.67 vs 0.549) and called the column a "correlation artifact" exploiting
> its correlation with `push_residual` on 3 of 5 families. Two checks kill that reading: the two
> columns' rank correlation is **+0.07**, so there is almost nothing to exploit; and the synergy
> is **positive** on four of five families, which is complementarity — the opposite of the
> redundancy the artifact story needs. The bottom line (REJECT) is unchanged; the reason is not,
> and the reason is what a later session would have inherited. That pass also recorded gate
> step 1 as "not applicable" and scored the item against invented "≥3 of 5 families" criteria
> that appear nowhere in [`../foundations/gates.md`](../foundations/gates.md).

**"Another counter", asked directly.** `attribution.py`'s `RANK_DEGENERATE_RHO = 0.99` is the
prior: above it a tree sees the same feature, because XGBoost splits on global thresholds and a
monotone relabelling induces the same partitions. Max abs Spearman against any contract column, on
the eval split: **+0.9745** (quantile trio), **+0.9789** (cliff), **+0.9801** (stint life), all
against `lap_in_stint`; next is `age_in_stint` at +0.964–0.970, everything else below +0.63. So it
sits **just under** the threshold — not formally degenerate, which is what makes the null a real
measurement rather than a foregone one: a distinguishable signal was available and did not amount
to anything.

**Declarability — the ruling, and a correction to how the hazard was written.**
`baseline_observations_n` has **no NULLs** (137,447/137,447 non-NULL; it is `0`, not NULL, where
there is no evidence). The NULLs deterministic on it are `push_residual`'s and the three other
thermal columns' — verified, `push_residual` is NULL on **100.0%** of rows where the count is 0,
in both train and eval. That does not soften the hazard, which was never about a NULL pattern but
about the **axis**.

Ruling: **DECLINED.** The trade has a measurable shape now. `lap_in_stint − baseline_observations_n`
is the count of invalidated prior laps: it is 2 on 64.37% of training-eligible rows (the
structural out-lap case) and **≥ 3 on 34.50%** — so about a third of rows carry something
`lap_in_stint` does not, and that something is "how disrupted was this stint", i.e. the safety-car
and pit-disruption channel. **The declarable part of the column (ρ ≈ 0.97 with `lap_in_stint`) is
redundant, and the non-redundant part is the undeclared axis itself.** There is no split that
gives the model the uncertainty without the undeclared axis. A large gain might have been worth
that; the gain is 0 of 5 above the floor. Declined on the numbers, not deferred a third time.

**Acceptance.** The column does **not** enter `FEATURE_COLUMNS`. The contract stays at **32**
columns on `v12`; no warehouse model, no model artefact and no line of `ml/src/schema.py` changes.
It stays in the mart, which is what `08e` shipped it for — `08e`'s call to ship it and not feature
it is now measured rather than assumed. The rejection is pinned by
`ml/tests/test_features.py::test_baseline_observations_n_is_never_a_feature`, so re-adding it
requires re-running this gate rather than an edit.

**Verified.** Gate step 1 — the 32-column baseline reproduces the published `v12` headline to
`0.00e+00` on all five families. The whole suite was run twice from independent invocations and
every per-seed score matched bit-for-bit. Row alignment of the candidate column verified
independently of the fit, via a relation the SQL contract guarantees and a shuffle would break:
`push_residual` NULL on 100.0% of count-0 rows in both splits (a misaligned column would show
~2%). All headline figures via `evaluate.py`'s own `_fit`/`_score`/`_predict_index` and
`attribution.py::refit_noise_floor`, 5 reseeds (`RANDOM_STATE`..`RANDOM_STATE+4`), on
`cv_final_fold`. E-value validity checked at four sigmas (mean `E` 0.999–1.011). Negative control
(shuffle vs shuffle, H0 true by construction) returns `E` = 0.42–1.71 on the five families.

**Assumed.** That the synergy contrast
`info(pair) − info(cand) − info(push_residual)` is a fair read of interaction. It is a
permutation-null difference, not a variance decomposition, and the three arms share one
permutation draw per seed (common random numbers) to keep the contrast low-variance — so the sign
is trustworthy and the magnitude is indicative. Nothing in the ruling turns on its magnitude:
every synergy is inside its floor. Also assumed, as in `08g`, the `max(floor(baseline), floor(add))`
denominator convention; the per-arm floors are both recorded in the artefact.

**Gates run.** Steps 1 (instrument check — run, and it passes, contrary to the first pass's "not
applicable"), 2 (add-ablation, identical split, all five families), 3 (each family's own 5-reseed
floor), 4 (permutation null, train and eval, with a negative control and a `push_residual`
reference arm), 7 (e-value construction declared in advance, validity-checked, all five reported
including `E < 1`, and counted in the campaign family). Step 5 not applicable — the candidate is
an existing mart column already covered by `assert_no_future_leakage`, and the contract did not
move. Step 6 satisfied — the three arms and the `push_residual` pair were named in this spec
before any of them ran; the reference arm is an addition that makes the pre-registered pair arm
interpretable, not a new hypothesis.

---

## 08i — The `min_observations` floor: the trade `08e` priced and did not take

> **STALE AS OF `08m` (2026-09-16) — every pinball number below is on the OLD target.**
> `08m` fixed how `int_compound_cliff_predicted.sql` consumes `compound_cliff_severity` and
> dropped the unfitted `0.002*age^2` term, then rebuilt the warehouse.
> `next_5_lap_cumulative_jump_s` is now **a different quantity**: its mean moved
> −1.8793 s → −0.3946 s, and `is_training_eligible` moved 82,470 → 81,619 rows. The absolute
> pinball losses, baselines and reseed floors in this section are therefore **not comparable to
> anything measured after that rebuild**, and the add-ablation *deltas* are not directly
> comparable either — both arms would have to be re-run on the rebuilt target. They were **not**
> re-measured by `08m`, which re-measured only the two acceptance numbers in its own RESULT.
> What is NOT invalidated: these deltas remain valid *relative to each other*, because every arm
> in the comparison was scored on the same (old) target. The leakage/forward-window rulings and
> the qualitative conclusions stand; only the numbers are on a superseded quantity.

> **SUPERSEDED, 2026-09-18.** The banner above applies to the *spec* text below and to the
> 2026-09-10 session's claims. It does **not** apply to the **`08i` — RESULT 2026-09-18** section
> at the end of this item: that was measured on the current v12/`08m` substrate, and its step-1a
> instrument check reproduces the published v12 headline on all five families to `0.00e+00`.
> Read the RESULT, not the objective — the objective's premise is wrong (see the pre-registration).



**Objective.** `08e`'s rebuild took `min_observations=1`. Floors of 2/3/5 were priced at the same
time — they buy more degradation signal for **3.49 / 8.82 / 19.09pp** of coverage — and that trade
was explicitly not taken because it had not been through the gate. Take it through the gate.

**Why it is worth revisiting now rather than then.** When the floor was chosen, nothing was known
about what the rebuilt thermal block was worth. Gate steps 2–4 now say it is worth **8.98× its own
floor on p50**, the largest single block in the contract on that family. A column that valuable
changes the arithmetic of trading rows for signal per row: at floor 1 the opening laps of every
stint carry a baseline built on one observation, which is the noisiest possible estimate of the
quantity the whole block rests on.

**Method.** Rebuild `int_lap_thermal_proxy` at floors 2 and 3 (5 is priced at 19.09pp and is almost
certainly too expensive to be worth a build), and run each as a full gate step 1–4 against the
current substrate as the BEFORE arm. Floor 5 only if 3 is still improving. The macro already takes
`min_observations`, so each arm is a parameter change rather than a rewrite.

**The measurement that decides it is not the headline alone.** Coverage loss falls entirely on
early-stint rows, which are over-represented in the cliff classifier's positive class. Report the
delta per family *and* the change in eval-row count per family, because a headline that improves by
deleting the hard rows is not an improvement.

**Ordering — after `08g`.** It moves `push_residual` itself, so it moves the substrate every number
recorded in this document is measured against.

**Definition of done.** A floor is chosen with the gate behind it, the rejected floors are recorded
with their numbers, and if floor 1 survives it survives as a measured result rather than as the
value that happened to be built first.

---

### 08i pre-registration (gate step 6) — written 2026-09-17, before any arm was run

**Correction to this item's own premise, found before the arms were written.** The objective above
says "`08e`'s rebuild took `min_observations=1`". **That has not been true since 2026-09-10.** A
prior `08i` session set `int_lap_thermal_proxy.sql` to `min_observations=2` and it rode into git
inside `c49473a` ("Add campaign-level multiple comparison audit and analysis scripts"), a commit
whose message does not mention it. `08m` then rebuilt the warehouse on 2026-09-16, so **the live
v12 substrate is floor 2, not floor 1** — every v12 number in this tree, including `08h`'s and
`08n`'s shipped artefacts, was measured on a floor-2 thermal block. The BEFORE arm here is
therefore floor 2, and "revert to floor 1" is a live option rather than the status quo.

That prior session's result is also **not carried forward**, for two independent reasons: it was
measured on the pre-`08m` target (this section's STALE banner), and its headline claim — floors 2
and 3 give "IDENTICAL headline results ... across all five families" — is a claim this
re-measurement has to reproduce or retract, because two floors that differ on 6,414 eligible rows
producing bit-identical headlines in five families is the signature of an arm that never varied.

**Arms.** Four: `min_observations` ∈ {1, 2, 3, 5}. Floor 5 is run rather than assumed too
expensive, because the whole point of the item is that the trade was priced and not taken.

**What varies and what does not.** Only the four `thermal` columns — `push_residual`,
`cumulative_push_load_surface`, `cumulative_push_load_bulk`, `surface_bulk_ratio`. The contract
stays 32 columns wide at every floor and **the row set is identical at every floor**:
`is_training_eligible` is `age_in_stint > 3 AND anomaly_class NOT IN ('mistake','conditions')`,
which does not reference the thermal block, so raising the floor turns values into NaN and never
deletes a row. The leaf doc's "a headline that improves by deleting the hard rows" hazard is
therefore **structurally absent here**, and the eval-row count is reported per family per floor to
show it rather than to assert it.

**Declared consequence:** the cross-floor contrast is **capacity-neutral by construction** — same
column count, same rows, same split — so a cross-floor delta cannot be a capacity artefact. Step 4
is still run, because "not capacity" is not the same as "not noise".

**Instrument (step 1), two parts, both required before any arm is read.**

1. `E._fit`/`_score` on `cv_final_fold` must reproduce the published **v12** headline in
   `ml/artefacts/evaluation_metrics.json` for all five families.
2. A floor-parameterised replica of `int_lap_thermal_proxy`'s window logic, run read-only against
   the warehouse, must reproduce the **built** floor-2 columns bit-for-bit on all 137,447 mart
   rows — NULL pattern included. Floors 1/3/5 are then that same query with one integer changed,
   which is what makes them comparable to the built arm rather than to a reimplementation.

**Steps 2–4, per family, per floor.** Add-ablation on `cv_final_fold` (train 2018–2023, eval 2024)
through `evaluate.py`'s own `_fit`/`_score`; each floor arm gets its own 5-reseed floor from
`attribution.py::refit_noise_floor`, and every cross-floor delta is quoted against the **larger**
of the two arms' floors; permutation null row-shuffles the four thermal columns **jointly** in
train and eval, giving `capacity = shuffled − baseline` and `information = real − shuffled` within
each floor.

**One extra control, declared here.** `shuffled(F) − shuffled(2)` isolates the cost of the extra
missingness *with the signal already destroyed*. If a floor's headline moves but its shuffled arm
moves by the same amount, the floor changed the NaN density and not the information.

**Step 7, declared before running.** Null = the within-floor information contrast (real vs its own
row-shuffle), not floor-vs-floor — capacity is a nuisance parameter. Construction **B (paired
safe-t)** from `reference/e_value_construction.md`, `n = 5` seeds
(`RANDOM_STATE + 0..4`, `RANDOM_STATE = 20260528`), `g = 1.0` (a one-sd effect, as in `02c` and
`08h`). Reported for every arm including `E < 1`, and a second e-value is declared on the
**cross-floor** paired contrast `headline(F, seed s) − headline(2, seed s)` — that is the shipping
question, and it is declared now so it cannot be selected afterwards. Direction is carried beside
each `E`, never folded into it.

**Decision rule, fixed in advance.** Ship the floor whose cross-floor delta against floor 2 clears
the larger of the two reseed floors, in the direction of improvement, on a majority of the five
families, with no family moved against by more than its own floor. If no floor clears anywhere,
the ruling is that the floor does not matter at this substrate and the cheapest-coverage option
(floor 1) is preferred on coverage grounds alone — stated as a coverage argument, not as a
signal win.

---

### 08i — RESULT 2026-09-18 (gate steps 1–7 on the v12/`08m` substrate)

**Artefacts.** `ml/artefacts/08i_min_observations_floor_arms.json` and its `.log`; the arms script
is `scripts/arms_08i_min_observations_floor.py`. 240 refits, all through `evaluate.py`'s own
`_fit`/`_score`/`_predict_index`. Nothing written to `ml/models/`, to
`ml/artefacts/evaluation_metrics.json`, to the warehouse or to git.

#### The one-line answer

**The trade does not exist.** `08e` priced floors above 1 as buying degradation signal for
coverage. Measured through the gate, **floors 3 and 5 cost coverage *and* signal** — they are
dominated on both axes, and they clear their own floor *in the wrong direction* on three of the
five families. **Floor 1 is the best-performing floor**, and the floor the warehouse is actually
built at — **floor 2** — is beaten by floor 1 on all three degradation heads.

#### Step 1 — instrument, both halves

| family | published v12 | floor-2 arm | abs diff |
| :--- | ---: | ---: | ---: |
| `degradation_regressor_p10` | 0.4764640778 | 0.4764640778 | `0.00e+00` |
| `degradation_regressor_p50` | 0.9823587336 | 0.9823587336 | `0.00e+00` |
| `degradation_regressor_p90` | 0.5128462338 | 0.5128462338 | `0.00e+00` |
| `cliff_classifier` | 0.3524660979 | 0.3524660979 | `0.00e+00` |
| `stint_life_regressor` | 1.9913358779 | 1.9913358779 | `0.00e+00` |

Exact, not merely inside 1e-6. And the floor-parameterised replica reproduces the **built**
thermal block bit-for-bit — `push_residual`, both loads and `surface_bulk_ratio`, 137,447/137,447
rows each, NULL counts identical (14,017 / 14,017 / 14,017 / 27,287). Per family the floor-2
splice is *identical* to the split it replaces, train and eval, on all four columns. Floors 1/3/5
are that same query with one integer changed.

#### Coverage, on the training-eligible panel

| floor | coverage | thermal-NaN rows | pp vs floor 1 | pp vs floor 2 (built) |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 98.20% | 2,156 / 119,822 | — | +2.15 |
| **2 (built)** | **96.05%** | 4,727 / 119,822 | −2.15 | — |
| 3 | 90.70% | 11,141 / 119,822 | −7.50 | −5.35 |
| 5 | 80.35% | 23,549 / 119,822 | −17.85 | −15.71 |

These are **not** `08e`'s 1.41 / 3.49 / 8.82 / 19.09pp. `08e` measured against the old block
median on the pre-`08m` mart; this is the eligible panel on the v12 substrate. Different
population — reported, not diffed.

#### Headline per floor (bold = best in family)

| family | metric | floor 1 | floor 2 (built) | floor 3 | floor 5 |
| :--- | :--- | ---: | ---: | ---: | ---: |
| p10 | pinball ↓ | **0.4753878** | 0.4764641 | 0.4873281 | 0.5008968 |
| p50 | pinball ↓ | **0.9684060** | 0.9823587 | 0.9821650 | 0.9874394 |
| p90 | pinball ↓ | **0.5072930** | 0.5128462 | 0.5249556 | 0.5274265 |
| cliff | macro F1 ↑ | 0.3509052 | **0.3524661** | 0.3474381 | 0.3454120 |
| life | AFT nloglik ↓ | 1.9926008 | 1.9913359 | **1.9880619** | 1.9909305 |

**All three degradation heads prefer floor 1.** Cliff prefers floor 2 and stint-life floor 3, both
by less than their own floor (below).

#### Steps 2–4 — the gate table, every floor against the built substrate

Delta is signed so **positive = improvement** on every metric. Floor is `2*sqrt(2)*sd` over 5
reseeds, quoted against the **larger** of the two arms' floors (`08g`'s convention). The
missingness-only control is `shuffled(F) − shuffled(2)`: both sides row-shuffled, so only NaN
density differs.

| family | floor | delta vs built | floor | ×floor | missingness-only control | E (cross-floor) | verdict |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| p10 | 1 | +0.0010763 | 0.0066994 | +0.16× | +0.0021707 (+0.32×) | 4.63 ↑ | inside |
| p10 | 3 | −0.0108640 | 0.0051848 | **−2.10×** | +0.0012840 (+0.25×) | 29.5 ↓ | **CLEARS AGAINST** |
| p10 | 5 | −0.0244327 | 0.0106539 | **−2.29×** | +0.0018590 (+0.17×) | 28.5 ↓ | **CLEARS AGAINST** |
| p50 | 1 | +0.0139527 | 0.0111509 | **+1.25×** | +0.0021132 (+0.19×) | 13.5 ↑ | **CLEARS** |
| p50 | 3 | +0.0001937 | 0.0111509 | +0.02× | −0.0016318 (−0.15×) | 0.495 ↓ | inside |
| p50 | 5 | −0.0050807 | 0.0111509 | −0.46× | +0.0034435 (+0.31×) | 4.64 ↓ | inside |
| p90 | 1 | +0.0055532 | 0.0146013 | +0.38× | +0.0020495 (+0.14×) | 0.413 ↓ | inside |
| p90 | 3 | −0.0121094 | 0.0083954 | **−1.44×** | +0.0021644 (+0.26×) | 21.4 ↓ | **CLEARS AGAINST** |
| p90 | 5 | −0.0145802 | 0.0092795 | **−1.57×** | −0.0008123 (−0.09×) | 30.8 ↓ | **CLEARS AGAINST** |
| cliff | 1 | −0.0015609 | 0.0043397 | −0.36× | −0.0003929 (−0.09×) | 0.527 ↓ | inside |
| cliff | 3 | −0.0050280 | 0.0045279 | **−1.11×** | −0.0005838 (−0.13×) | 3.23 ↓ | **CLEARS AGAINST** |
| cliff | 5 | −0.0070541 | 0.0070406 | **−1.00×** | −0.0021774 (−0.31×) | 6.00 ↓ | **AGAINST, at the floor** |
| life | 1 | −0.0012650 | 0.0068296 | −0.19× | +0.0011063 (+0.16×) | 0.430 ↓ | inside |
| life | 3 | +0.0032740 | 0.0061134 | +0.54× | +0.0023664 (+0.39×) | 1.02 ↑ | inside |
| life | 5 | +0.0004054 | 0.0090994 | +0.04× | −0.0013209 (−0.15×) | 0.502 ↑ | inside |

`cliff`/floor 5 is −1.0019× its own floor. Recorded as marginal rather than rounded either way.

**Every missingness-only control is small** (|0.09×| to |0.39×|, all inside their floors). The
damage at floors 3 and 5 is therefore **destroyed information, not NaN density** — which is the
specific thing this control was declared to separate.

#### Step 4 — how much information the thermal block carries *at* each floor

`information = real − shuffled`, within each floor. Eval rows are constant across floors by
construction; the NaN column is what actually varies.

| family | floor 1 | floor 2 | floor 3 | floor 5 |
| :--- | ---: | ---: | ---: | ---: |
| p10 | +0.0684786 | +0.0695730 | +0.0574250 | +0.0432813 |
| p50 | **+0.0822964** | +0.0704569 | +0.0722824 | +0.0619327 |
| p90 | **+0.0384065** | +0.0349027 | +0.0206290 | +0.0211348 |
| cliff | +0.0136212 | +0.0147892 | +0.0103450 | +0.0099124 |
| life | +0.0220650 | +0.0244363 | +0.0253439 | **+0.0261626** |
| **sum** (indicative only) | **0.2249** | 0.2142 | 0.1859 | 0.1624 |

Every arm's information clears its own floor (+1.41× to +50.86×) with `E` between 18.5 and 35.9 —
**the thermal block carries real information at every floor**, consistent with `08e`'s finding
that family T is the largest single block in the contract. What the floor changes is *how much*.
The sum is across different metrics and is indicative, not a statistic; the per-family columns are
the evidence. Read either way, **more floor means less information**, with `stint_life_regressor`
the single exception — it is the one family where a higher floor genuinely carries more, and its
headline delta still never clears.

Eval-row counts, the leaf doc's stated worry: **13,712 / 13,712 / 18,866 / 19,973 — identical at
every floor**, because `is_training_eligible` never references the thermal block.

#### Where the coverage actually goes

The leaf doc's hazard — "coverage loss falls entirely on early-stint rows, over-represented in the
cliff classifier's positive class" — is **confirmed, and it gets worse with the floor**. The
`0_to_2` class is 10.05% of eligible rows. Its share of the NaN rows and its within-class blind
rate:

| floor | `0_to_2` share of all NaN rows | over-representation | blind rate *within* `0_to_2` |
| ---: | ---: | ---: | ---: |
| 1 | 60.3% | 6.0× | 10.48% |
| 2 | 31.6% | 3.1× | 12.13% |
| 3 | 19.2% | 1.9× | 17.44% |
| 5 | 13.6% | 1.4× | **26.13%** |

The *concentration* falls as the floor rises only because everything else starts going blind too.
The number that matters — how much of the hardest class the model has no thermal reading for —
rises monotonically, and at floor 5 it is **a quarter of the positive class**. That is the
mechanism behind cliff's −1.11× and −1.00×.

#### Ruling

1. **Floors 3 and 5 are rejected with the gate behind them.** Dominated on both axes: they cost
   5.35pp and 15.71pp of coverage *and* clear against on p10, p90 and cliff. `08e`'s "floors above
   1 buy a little more degradation signal" is **false on this substrate** — they sell it. Do not
   re-open without new evidence named in the reason.
2. **Floor 1 is recommended over the built floor 2**, on: all three degradation heads prefer it;
   p50 — the headline degradation model, and the family the thermal block is worth most to —
   clears at **+1.25×** with `E = 13.46` in the improvement direction; no family is moved against
   by more than its own floor (worst is cliff at −0.36×); it carries the most information on 2 of
   5 families and the most in total; and it buys **+2.15pp** of coverage while cutting the blind
   rate on the hardest cliff class from 12.13% to 10.48%.
3. **Stated honestly: this is a preference, not a majority CLEAR.** The pre-registered rule above
   asked for a clear on a *majority* of the five families. Floor 1 clears on **one**. The rule's
   two branches — "clears on a majority" and "clears nowhere" — did not anticipate this case, and
   that gap is recorded rather than resolved by re-reading the rule after seeing the data. What
   the evidence supports is: floor 1 ≥ floor 2 everywhere that matters, strictly better on the
   degradation trio, and cheaper in coverage. What it does not support is calling that a gate pass
   on its own terms.
4. **Floor 1 survives as a measured result.** The leaf doc's definition of done asked that if
   floor 1 survives, it survive as a measurement rather than as the value that happened to be
   built first. It did not even have that status going in — it had been silently replaced by
   floor 2 — and it now has the measurement.

#### Two defects in the tree this item found, both still live

- **`transform/tests/assert_no_future_leakage.sql`** hard-codes `>= 2` in its independent
  re-derivation of the baseline ("Apply the same min_observations=2 floor the model uses"). It is
  a second copy of the parameter, and it must move with any floor change or it fires spuriously.
- **`transform/models/intermediate/schema.yml`** still documents **floor 1** for
  `stint_baseline_pace` — "NULL until *one* valid prior lap exists … Costs 1.41pp of
  training-eligible coverage" — while the SQL runs floor 2 at a measured 3.95pp. The 2026-09-10
  session changed the parameter and the inline SQL comment but not the column's own description.

#### Step 7 bookkeeping for the campaign family

**15 declared cross-floor hypotheses** (5 families × 3 non-reference floors) plus 20 within-floor
information arms, every `E` reported above including those below 1. Construction B (paired
safe-t), `n = 5`, `g = 1.0`, validity checked at four σ (mean `E` = 1.0016 / 0.9992 / 1.0108 /
1.0014, max attainable 36.0). These belong in `04c`'s campaign-level e-BH; **they have not been
counted there yet**, and no claim above is adjusted for multiplicity.

#### What this does NOT establish

- It does not re-price the thermal block itself. Arm-vs-arm only; `08e`'s family-T numbers are
  not re-measured here.
- It does not test floor 4, or a floor that varies by stint length or by `baseline_observations_n`.
  The four priced floors are the four that were priced.
- Landing floor 1 requires a warehouse rebuild and a retrain/re-export of all five artefacts —
  a cost this measurement does not pay and does not authorise. Raised as **D10**.

---

## 08j — Rule on `cliff_candidate_flag`: prune it or rebuild its threshold

**Objective.** Act on whatever `08g` rules. Gate steps 2–4 found the column carries no information
in any of the five families; `08g` says whether it ever did.

**The two branches, and they are not the same work.**

- **Dead** (inside floor on both substrates) → prune arm. Drop it from `FEATURE_COLUMNS` and
  measure: on p10 its capacity term was **+0.0096350**, so removing it may be a small *gain* rather
  than a neutral tidy-up. A prune is a contract change and gets the same three arms as an addition.
- **Damaged** (cleared before, does not now) → the flag is not the problem, the threshold is.
  `int_lap_anomaly_flags` fires on a MAD/z-score calibrated against a `driver_skill_residual_s`
  whose level moved when `08f-2` landed, and 2018 is the acute case: its
  `circuit_constructor_interaction_s` is identically 0, so the constructor-circuit effect now
  arrives in front of a threshold that was never calibrated to receive it. Recalibrate per season,
  or per (season, constructor), and re-gate.

**Do not run the prune arm before `08g`.** It is answerable now, but its answer does not tell you
which branch you are on — a column that is merely broken measures identically to one that is dead,
and pruning a repairable feature is the expensive mistake of the two.

**Definition of done.** `cliff_candidate_flag` is either out of the contract with the prune arm's
numbers behind the removal, or still in it with a rebuilt threshold that clears its floor — and the
`cliff_prior` group's description in `schema.py` says which happened, so the next reader meets the
result where the column is defined.

---

## 08k — Rebuild the model artefacts against the post-08j 32-feature contract

**Objective.** Make the shipped artefacts agree with the contract `08j` landed. Right now they do
not, and the disagreement is on a surface the browser reads.

**What happened.** `08j` pruned `cliff_candidate_flag` and landed the contract change in
`schema.py` — `FEATURE_GROUPS["cliff_prior"]` went from five members to four and
`BOOLEAN_COLUMNS` lost the column, taking the contract from **33 to 32**. The models,
manifests and ONNX exports under `ml/models/` were never rebuilt, so every one of them still
declares 33.

**Why this is not only a test-suite problem.** The manifest is what the browser builds its
feature vector from. A manifest declaring a feature the booster no longer takes is a shipped
inconsistency, and it is being caught here only because the contract test happens to assert it:

> `manifest declares a 33-feature input; stint_life_regressor at 'v11' takes 32.`

**Blast radius — 21 failures across 5 modules**, all the same root cause:

| module | failures |
| :--- | ---: |
| `test_onnx_parity.py` | 5 |
| `test_evaluate.py` | 9 |
| `test_manifest_contract.py` | 2 |
| `test_predict.py` | 3 (errors) |
| `test_attribution.py` | 1 |

**Method.** Retrain every affected target against the 32-feature contract, re-export the ONNX
artefacts and regenerate the manifests. No modelling decisions live here — this is the mechanical
completion of a change that already has its ruling in `08j`. If any target cannot be reproduced,
that is a finding and belongs in the log rather than in a workaround.

**Acceptance.** `python -m pytest ml/tests -q` is green.

**Definition of done.** No artefact under `ml/models/` declares a feature the contract does not
carry, and the suite passes without a skip or an xfail standing in for the drift.

**This gates [`10d`](10-competing-risks.md).** The calibration fix means retraining and
re-exporting `stint_life_regressor`; that cannot be validated while ONNX parity and the manifest
contract are already red for an unrelated reason.

## 08l — The seed compound curve that defines the degradation target

**CORRECTION, 2026-09-16 (this item's own RESULT below).** The premise below — that
`compound_cliff_params` is "hand-written" and its coefficients are "placeholder values" — is
**stale, not current**. `git log` shows the seed was rewritten from a real fit
(`transform/tasks/coefficients/fit_compound_cliff.py` + `survival.py`, KM survival + wind-controlled
OLS on `normalized_pace_s`) on 2026-07-30 and again on 2026-09-08/09, **before** this item was even
opened by `11b`'s 2026-09-16 session; `dev.duckdb`'s built `compound_cliff_params` table matches the
2026-09-08 seed CSV exactly (`fit_date`, `fit_source` columns checked directly). 337 of 438 rows carry
`fit_source = cox_km_survival`, 77 `cross_season_fallback`, 24 `compound_class_default`. The
`int_compound_cliff_predicted.sql` header comment quoted two paragraphs below was last touched
2026-09-07, one day *before* that refit landed, and nobody updated it afterward — it describes a
state the warehouse was in only briefly. **The −1.88 s/5-lap bias this item exists to quantify
survives an already-applied, legitimate, non-circular refit.** See the RESULT section at the end of
this item for why, and for the ruling that follows from it.

**Objective.** `compound_cliff_params` is a 438-row seed, fitted (see correction above, not
hand-written). It is not only the running cost of the pit-strategy surface — it is subtracted before
the ML target is formed, so the degradation trio is trained to predict **the seed's error**.
Establish how much of the tree's measured signal is that error, and rule on whether the seed is
refit.

**How it was found.** `11b` (2026-09-16) went looking for the DP's running cost and found no model
prediction in it at all. Tracing back:

```
compound_cliff_params (seed, 438 rows)
  └→ dim_compounds_season            -- "All β coefficients sourced from dim_compounds_season
       └→ int_compound_cliff_predicted      (placeholder values)" — the SQL's own header, line 4
            │                                [STALE as of 2026-09-16 — see correction above; the
            │                                 seed was refit 2026-07-30/09-08, before this comment
            │                                 was last touched (2026-09-07) and before this item
            │                                 was opened]
            └→ int_lap_residual_decomposed  -- subtracts it to form driver_skill_residual_s
                 └→ fct_cliff_prediction_features.next_5_lap_cumulative_jump_s  ← THE ML TARGET
```

**The size of it.** `next_5_lap_cumulative_jump_s` means **−1.88 s** per 5-lap window over the
95,346 non-null rows of `fct_cliff_prediction_features` (`11b` measured −2.163 s on its own
82,470-row panel — different population, same sign and order). A target whose mean is
systematically negative is a target whose baseline over-charges: roughly **0.14 s/lap** of the
signal the degradation models carry is spent undoing the seed rather than predicting tyre wear.

**Why this is foundations and not a group-11 footnote.** It moves the *definition* of the target,
not a feature. Every degradation number in the tree — `02`'s feature arms, `08e`/`08f`/`08i`'s
gated deltas, `10`'s stint-life work, `11a`'s coverage table — is measured against this curve. If
the seed is wrong, those numbers are not wrong *relative to each other*, but none of them means
what its name says. That is precisely the class this group exists to catch: *anything that changes
what you would measure goes before the measurements.*

**The trap, and the reason this item is `fable-5.1` rather than `opus-5`.** The obvious refit is
circular and will return a plausible number. `driver_skill_residual_s` is formed by subtracting the
seeded curve from `pace_delta_s`; fitting the curve to minimise a criterion computed on that
residual is fitting it to its own leftovers, and the degenerate solution is available. The
identification argument — what independent quantity the refit is anchored to, and why that anchor
is not itself downstream of the seed — is the hard part of this item and the part whose failure
mode is a number that looks fine. Derive it before fitting anything.

**Method.**
1. **Quantify first, refit second.** Decompose the target into (seed bias) + (residual wear signal)
   and report what fraction of each model's measured skill is attributable to each. This is worth
   having even if the refit is then declined.
2. **State the anchor.** Name the observable the refit identifies against, and show it is not
   formed by subtracting the seed. Write this before fitting.
3. **Refit `compound_cliff_params` against observed wear**, per compound-season.
4. **Price the blast radius.** Rebuild the target and report which published deltas in `02`, `08`,
   `10` and `11` move, by how much, and whether any change sign.

**Interactions.** `08d` (real Pirelli C1–C5 identity per race, `MEASURED`, hand-sourced and not
independently sourced) is what a per-compound refit would ideally key on — read its caveats before
relying on it. `D9` (should `int_pit_strategy_cost_curve` consume `mart_degradation_predictions`)
is deliberately sequenced *after* this item, because the +3.59 s/stint that motivates it is
measured against the unrefit seed.

**Acceptance.** The seed-bias fraction of the degradation target is reported with an interval,
race-clustered. If a refit is taken, the identification anchor is written down and argued before
any fit, and the blast-radius table is produced.

**Definition of done.** A ruling: refit, or keep the seed with its bias documented as a known
property of the target. Either way the tree stops describing `next_5_lap_cumulative_jump_s` as tyre
degradation without qualification.

**Raised by** [`11b`](11-parallel-surfaces.md).

### `08l` — RESULT 2026-09-16: the seed is already fit and independently anchored; the bias survives anyway because the SQL formula, not the seed, misuses one of its own fitted parameters. Ruling: keep the seed, decline the refit, fix the formula (flagged, not made).

**0. The premise correction, restated precisely.** `compound_cliff_params` is not hand-written.
`transform/tasks/coefficients/fit_compound_cliff.py` (driven by `survival.py`) fits it per
`(circuit_key, compound_code, season)` from real stint data, and the fit is **already anchored to an
observable independent of the seed** — see §2. `dev.duckdb`'s built table matches the 2026-09-08
seed CSV row-for-row (`fit_date`, `fit_source` verified directly against the warehouse, not just the
CSV on disk). The tree-wide description of this seed as "hand-written placeholder values" (this leaf
doc, the `08l` build-log note, and `11b`'s 2026-09-16 history entry) is corrected by this result.

**1. Quantify — the seed-bias fraction of the target, race-clustered.** `next_5_lap_cumulative_jump_s
= Σ_{i=1..5}[driver_skill_residual(t+i) − driver_skill_residual(t)] − 15·drift(t)`, and
`driver_skill_residual = pace_delta − fuel − compound − rubber − ambient − constructor − dirty_air`.
Because every term except `compound` cancels out of this decomposition at the *target's own
definition*, the target splits exactly into

```
target(t) = seed_bias(t) + rest(t)
seed_bias(t) = −Σ_{i=1..5}[expected_compound_pace_s(t+i) − expected_compound_pace_s(t)]
rest(t)      = target(t) − seed_bias(t)
```

computed by self-joining `fct_cliff_prediction_features` to itself at lap offsets +1..+5 within each
stint via the identical `LEAD(...) OVER (PARTITION BY stint_id ORDER BY lap_in_stint)` window the
mart's own target uses (so the row set and gap-handling are exactly the mart's, not a
reimplementation). On the 95,346 non-null rows:

| | mean | race-clustered 95% CI (147 races, 2000 resamples, `intervals.py::cluster_bootstrap`) |
| :--- | ---: | :--- |
| `target` (reproduces the prior reads) | **−1.8793 s** | [−2.1163, −1.6499] |
| `seed_bias` | **−3.5853 s** | [−3.7792, −3.3957] |
| `rest` | **+1.7059 s** | [1.5772, 1.8335] |
| `seed_bias / target` | **1.9077×** | [1.7638, 2.0825] |

On the 82,470 training-eligible rows the models actually train on: target −2.1633 s, seed_bias
−3.7970 s, rest +1.6337 s, fraction **1.7552×**, race-clustered CI **[1.6378, 1.8984]**.

**The seed doesn't just bias the target — it inverts its sign.** `seed_bias` is *larger in magnitude*
than `target` and carries the *same* sign, which forces `rest` — the target with the compound seed's
own forward contribution held out — to carry the **opposite** sign, and a materially different
magnitude. Read literally: net of what the compound curve itself assumes, lap-relative pace *rises*
by about +1.7 s over a 5-lap window (real degradation, positive, plausible in size), and it is the
seed's own assumed forward wear (≈3.6–3.8 s over the same window, ≈0.72 s/lap) that drags the
published target negative. **ACCEPTANCE is met**: the seed-bias fraction is reported with a
race-clustered interval, on both the full non-null population and the training-eligible subset.

**2. State the anchor.** `fit_compound_cliff.py` fits on `normalized_pace_s`
(`int_lap_normalized_pace`, dirty-air-corrected raw driven pace), not on `driver_skill_residual_s`.
Traced its full dependency chain (`int_lap_air_state`, `stg_laps`, `int_lap_fuel_state`,
`int_field_pace_curve`, `int_event_corrections`, `int_track_evolution`) — **none of it references
`compound_cliff_params`, `dim_compounds_season`, `int_compound_cliff_predicted` or
`int_lap_residual_decomposed`.** This is a legitimate, non-circular anchor: cliff onset by
Kaplan-Meier survival (correcting for the fact that most stints are right-censored — drivers pit
*before* the cliff, precisely to avoid it), wear gradient by wind-controlled OLS on fresh-tyre,
pre-cliff, uncensored laps, cliff severity by a pre/post window pace difference on uncensored stints
only. **This anchor was already applied**, twice (2026-07-30, 2026-09-08) — so §1's bias is not
evidence of an un-anchored seed; it is evidence that anchoring the seed did not fix it.

**3. Why the already-anchored fit didn't fix it — decomposed, not asserted.** `expected_compound_pace_s
= grip_peak + LEAST(wear_gradient·age + 0.002·age² + severity·laps_past_cliff, 10.0) + 0.005·ambient_temp_delta`
(`int_compound_cliff_predicted.sql:133–170`). `grip_peak`, `wear_gradient`, `severity` are constant
within a stint (same `circuit×compound×season` cell throughout), so they cancel from `seed_bias`'s
forward difference and only the age-varying terms carry it. Reconstructing `seed_bias` from its four
additive pieces (unbounded, then checked against the actual `LEAST(...,10)`-bounded column — the two
diverge by >0.01 s on 7.59% of rows, i.e. the bound is genuinely binding in the tail but is not the
main story):

| piece | mean contribution to `seed_bias` | share |
| :--- | ---: | ---: |
| fitted `wear_gradient·age` (linear) | −1.0819 s | 20.7% |
| **hardcoded** `0.002·age²` (never fit — a literal constant in the SQL, same everywhere) | −0.9900 s | 18.9% |
| fitted `severity·laps_past_cliff` | **−3.1569 s** | **60.4%** |
| hardcoded `0.005·ambient_temp_delta` | ≈0 | ≈0% |
| **sum (unbounded reconstruction)** | **−5.2288 s** | 100% |

**Only ~21% of the bias is the correctly-scaled, correctly-anchored linear wear term.** ~79% is
either a formula constant that was never fit against anything (`0.002·age²`, identical across every
circuit/compound/season) or the dominant term, `severity·laps_past_cliff` — and that one is a **units
bug, not a seed-value problem**. `survival.py::estimate_cliff_severity`'s own docstring: *"seconds of
pace loss at onset + 5 laps post-cliff"* — it is fit as `post.mean() − pre.mean()` over two ~5-lap
windows, i.e. a **level shift**, median 0.77 s across the 438-row seed (min 0.19, capped at the
fitter's own 1.5 s winsorisation ceiling). `int_compound_cliff_predicted.sql`'s inline comment then
calls this same number *"the empirically fitted average **s/lap rate** of post-cliff degradation"*
and multiplies it by `laps_past_cliff` **uncapped** — which reaches 48 in the observed data (19.4% of
rows are past onset at all; median `laps_past_cliff` among those is 6, p75 is 12). A quantity fit as
a total shift over roughly 5 laps is being charged again for every one of up to 48 laps past onset.
**The SQL model's own comments already half-document this failure mode** — lines 146–162 of the same
file record that, pre-bound, this exact formula emitted up to 93.5 s/lap and that the `LEAST(...,10)`
clip was added specifically because "an over-large wear term over-explains the lap and *depresses*
the residual." The clip caps the extreme tail; it does not touch the median-case overcharge
quantified above, which lives comfortably inside it.

**This is not local to the ML target.** `transform/models/intermediate/int_pit_strategy_cost_curve.sql`
(lines 189–194) **independently reimplements the identical formula** —
`wear_gradient·age + 0.002·age² + severity·GREATEST(age−onset,0)` — as the running cost for `11b`'s
DP. `11b`'s own finding — "the seed over-charges degradation by ~0.14 s/lap," the input to the
deferred `D9` decision — is the same bug, measured from a different lineage path.

> **ORCHESTRATION CORRECTION, 2026-09-16 (review of this item's own run).** The paragraph above
> originally said the cost curve applies the formula *"without the `LEAST(...,10)` clip"* and called
> the second path *uncapped* and *worse*. **That is wrong.** `int_pit_strategy_cost_curve.sql:189–194`
> applies `LEAST(…, {{ var('compound_wear_max_s_per_lap', 10.0) }})` — the *same shared bound*, on the
> same three terms. The "extrapolated to age 80 it reaches 136 s/lap" line quoted as evidence is from
> the comment **explaining why the cap is there**, and that same comment block states explicitly that
> `int_compound_cliff_predicted` "now applies the identical `LEAST()` to the identical three terms, so
> capping here alone no longer leaves the source curve unbounded." The two lineage paths are
> **equivalent**, not one-worse-than-the-other. The ruling is unaffected — the severity units misuse is
> real and present in both, and a 10 s/lap cap does not repair a per-lap/level-shift unit error — but
> any `08m` scoped from this result should treat the second path as a duplicate of the same bug, not
> as a more severe variant.

**4. Ruling: decline the seed refit; keep the seed; flag the formula fix.** Re-running
`fit_compound_cliff.py` (item `08l`'s literal step 3) can only move the ~21% of the bias carried by
the linear `wear_gradient·age` term — the anchor is legitimate and was already applied there. It
cannot touch the ~79% majority, because that majority is generated by how
`int_compound_cliff_predicted.sql` (and, identically, `int_pit_strategy_cost_curve.sql`) **consumes** the
seed's parameters, not by the parameters' values. Refitting the seed harder against a formula that
misreads one of its own outputs relocates where the optimiser compensates for a bug it cannot see; it
does not remove the bug. So: **the seed stays as-is.** Its bias is documented here — §1's numbers —
as a known, quantified property of `next_5_lap_cumulative_jump_s` (and of `int_pit_strategy_cost_curve`'s
running cost). This satisfies the definition of done's second branch: *"keep the seed with its bias
documented as a known property of the target."*

**Flagged for a human, not made (HARD CONSTRAINT: no dbt model write from this item).** The actual
fix is a `int_compound_cliff_predicted.sql` (and `int_pit_strategy_cost_curve.sql`) change, not a
seed change: (a) re-derive `compound_cliff_severity`'s consumption as a genuine per-lap slope over
`laps_past_cliff` (e.g. refit it as a regression coefficient on laps-past-onset in the post-cliff
region, the same way `wear_gradient` is already a slope) instead of a single ~5-lap window level
difference multiplied by an uncapped lap count — or, more conservatively, cap `laps_past_cliff`'s
multiplier or apply decay past some horizon; and (b) either fit the `0.002` quadratic coefficient
from data (it is currently identical across all 438 seed rows, contradicting the SQL comment's own
"rubber accumulation" framing, which should vary by compound) or drop it if unsupported once (a) is
fixed. This is a dbt model change and a re-derived seed-consumption rule — exactly the kind of
production-artefact write this item's constraints bar it from making. Recommended as a new,
well-scoped follow-on item (candidate id `08m`) rather than opened here, since opening a new tree item
is an orchestration-level call, not this item's to make.

**5. The "worth having even if the refit is declined" extra: how much of the trio's *measured skill*
is the seed's own arithmetic.** Built a zero-fit "seed-echo" predictor — `seed_bias(t)` plus one
constant (the `alpha`-quantile of `rest` on the training fold only, so nothing eval-side leaks in) —
and scored it with `train.py::pinball_loss` on the **exact same `cv_final_fold` eval split**
`evaluate.py::_evaluation_split` builds (season 2024 holdout, `n_train=68,574` / `n_eval=13,896`,
matching `model_card.yml`'s `n_train_rows=82,470` exactly). `seed_bias(t)` is not a leak: a real
model has `age_in_stint`, `compound`, `circuit_key`, `season` (hence every compound-curve parameter)
and `expected_compound_pace_s` itself at prediction time, and `age` increments by exactly 1 lap on
every row this target is defined for by construction — so extrapolating the seed's own known formula
5 laps forward is pure arithmetic on already-available inputs, not a forecast.

| model | `baseline_headline` | `eval_headline` (v11, `model_card.yml`) | trivial seed-echo | skill gain, full | skill gain, trivial | **fraction of skill from the seed-echo** |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| `degradation_regressor_p10` | 1.46443 | 0.53202 | 0.63828 | 0.93241 | 0.82615 | **88.6%** |
| `degradation_regressor_p50` | 2.17766 | 1.04679 | 1.13022 | 1.13087 | 1.04744 | **92.6%** |
| `degradation_regressor_p90` | 0.89080 | 0.57851 | 0.61292 | 0.31229 | 0.27788 | **89.0%** |

**Only 7–11% of the trio's entire published margin over the non-leakage baseline is anything beyond
reconstructing the compound seed's own deterministic forward arithmetic.** This is a materially
larger and more consequential number than §1's mean-bias finding, and it holds regardless of whether
the seed's mean is biased: it is a statement about how much of every "beats baseline" claim for this
family is redundant with a feature (`expected_compound_pace_s` / the `compound` group) the trio
already has, not new information the boosted trees found. It is reported here as the requested extra
("worth having even if the refit is declined") rather than folded into the ACCEPTANCE interval, which
is specifically about the target's own mean.

**6. Blast radius — what this changes and does not, since no refit was taken.** No new target was
built, so there is no rebuild-and-diff table against `02`/`08`/`10`/`11`'s published deltas in the
form the spec's step 4 describes; declining the refit removes that action's object. What is delivered
instead:

- **Directly implicated** (measured against `next_5_lap_cumulative_jump_s` / `degradation_regressor`
  p10/p50/p90, or against `dim_compounds_season` as a running cost): `11a` (the Mondrian band is p10/p90
  of this exact target), `11b` (already self-documented, corroborated and sharpened by §3 above), and
  the `degradation_regressor`-family arms inside `08e`/`08f`/`08h`/`08i` and `02b`/`02c`/`02d`/`02g`
  (per their own leaf-doc framing of a family ablation across degradation/cliff/life — **not**
  individually re-verified per item this session; **ASSUMED**, not verified). None of these numbers
  are *wrong relative to each other* — every add-ablation compares two arms on the identical,
  unchanged target — but §5 means their absolute "beats baseline" framing substantially overstates
  how much of that margin is new signal versus seed-echo, for the `degradation_regressor` heads
  specifically.
- **Partially implicated, not quantified (flagged risk, ASSUMED).** `cliff_classifier`'s label
  (`laps_until_cliff_class`) is also downstream of `driver_skill_residual_s`, via a threshold-crossing
  forward scan rather than the fixed 5-lap sum — a related but structurally different exposure to the
  same seed. Not quantified here; time-boxed out of scope for this item.
- **Not implicated — verified.** Group `10` (`10a`–`10e`, `stint_life_regressor`). Traced
  `STINT_LIFE_TARGET = stint_length_laps − lap_in_stint`, sourced from `int_stint_geometry` /
  `fct_stint_features`; no dependency on `driver_skill_residual_s` or the compound seed anywhere in
  its construction.

**Verified.** The seed's current `fit_date`/`fit_source` provenance, both in the seed CSV and in
`dev.duckdb`'s built table (queried directly, not assumed from the CSV on disk); the git history
placing the 2026-07-30 and 2026-09-08/09 refits before this item's 2026-09-16 opening and before the
SQL header comment's last edit (2026-09-07); `normalized_pace_s`'s full upstream dependency chain
carries no reference to the compound/residual lineage; the target's mean reproduces the prior session's
number to full precision (−1.8793 s); the seed-bias/rest decomposition's arithmetic identity (the four
reconstructed pieces sum exactly to the reconstructed `seed_bias`, and the reconstructed value matches
the mart-column value to within the measured 7.59%-of-rows bound-clipping); the exact formulas in both
`int_compound_cliff_predicted.sql` and `int_pit_strategy_cost_curve.sql` (same hockey-stick, same
severity misuse, and — per the orchestration correction above — the same shared `LEAST(…,10)` bound,
not one bounded and one not); the `severity`/`laps_past_cliff` distributions behind the
units-mismatch argument; the model-skill decomposition against `model_card.yml`'s own published
`eval_headline`/`baseline_headline` numbers, on the identical split `evaluate.py::_evaluation_split`
constructs (not reimplemented).

**Assumed.** Which specific published deltas inside `08e`/`08f`/`08h`/`08i` and
`02b`/`02c`/`02d`/`02g` are `degradation_regressor`-family (inferred from their leaf-doc framing, not
individually re-opened and re-read this session); `cliff_classifier`'s degree of exposure to the same
mechanism (flagged, not measured); that the recommended formula fix (§4) would remove the bulk of the
bias without introducing a new one — a natural conjecture from the diagnosis, not tested, since testing
it means making the dbt change this item is barred from making.

**Gates run.** None of the six standing-gate steps apply in their literal sense — this item changes
no feature contract, fits no model, and admits no new arm to the campaign; it is a decomposition and
identification-anchor argument on the existing target and formula. In their place: the target-mean
reproduction to the previously-published precision, and the exact-sum reconciliation of the component
decomposition, serve as this item's arithmetic-fidelity check.

---

## 08m — The severity units bug: fix how the SQL consumes the seed it was given

**Opened 2026-09-16** by the orchestrating session, out of [`08l`](#08l--the-seed-compound-curve-that-defines-the-degradation-target)'s
ruling. `08l` declined the seed refit and flagged this fix rather than making it (its own hard
constraints barred a dbt model write). This item is that write, plus the re-measurement it forces.

**Objective.** `compound_cliff_severity` is **fitted as a level shift** —
`survival.py::estimate_cliff_severity`, own docstring: *"seconds of pace loss at onset + 5 laps
post-cliff"*, computed as `post.mean() − pre.mean()` over two ~5-lap windows, median ~~0.77~~
**0.85** s across the 438-row seed *(**CORRECTED by this item's RESULT**: 0.77 s is the median of
the HARD rows only; the whole-seed median is 0.8500, mean 0.8996. Inherited from `08l`.)*. It is
**consumed as a per-lap rate**: `int_compound_cliff_predicted.sql:133–170`
multiplies it by `laps_past_cliff`, which reaches 48 in the observed data. That single term is
**60.4%** of the seed's contribution to the ML target. A second term, `0.002·age²`, is a literal
constant in the SQL that was never fitted against anything, and carries a further **18.9%**. Fix
both, and re-measure everything that was measured against the old target.

**Why it is worth the blast radius.** `08l` measured what the current formula costs: a zero-fit
predictor that re-emits the seed's own arithmetic plus a constant captures **88.6% / 92.6% / 89.0%**
of `degradation_regressor` p10/p50/p90's entire published skill margin over baseline. Only 7–11% of
the trio's "beats baseline" claim is signal the models learned. And the seed's forward contribution
(−3.59 s) exceeds the target's own mean (−1.88 s) with the same sign, so the published target's
**sign is an artefact**: net of the seed, lap-relative pace over a 5-lap window *rises* by +1.71 s.

**The sites.** ~~All four~~ **CORRECTED by this item's RESULT: there are SIX, and one of the four
listed here was not needed.** Sites 5 and 6 — `fct_ghost_car_pace.sql`'s `cliff_interaction_s` and
`int_constructor_deg_sensitivity.sql`'s `severity_used` — consume the same number under the same
per-lap reading and appear in neither `08l`'s diagnosis nor this table. Site 4 (`survival.py`) was
**not** touched, because the shape ruling came back (A). Neither site 5 nor 6 is in
`fct_cliff_prediction_features`' 40-model upstream closure, so neither could contaminate this item's
acceptance measurement. See the RESULT's own site table for what was done at each.

The four originally listed, which do consume the same three terms:

| site | what it does | note |
| :--- | :--- | :--- |
| `int_compound_cliff_predicted.sql:133–170` | `expected_compound_pace_s` — the term subtracted into `driver_skill_residual_s` | the ML target's lineage |
| `int_compound_cliff_predicted.sql` (`expected_degradation_rate_s_per_lap`) | first derivative — adds bare `severity` as a rate | same bug, derivative form |
| `int_pit_strategy_cost_curve.sql:189–194` | the DP's running cost | **a duplicate of the same bug, not a worse one** — it applies the *identical* shared `LEAST(…, 10.0)` bound; `08l`'s claim that this path is unbounded was wrong and is corrected in its RESULT |
| `survival.py::estimate_cliff_severity` | produces the number | only if the fix is (B) below |

**Method.**
1. **Rule on the fix's shape before writing SQL.** Two candidates, and they are not equivalent:
   **(A)** keep the seed as-is and correct the *consumption* — `severity` applied once as a step at
   onset, with post-cliff slope carried by a term that is actually fitted as a slope; or **(B)**
   refit `compound_cliff_severity` in `survival.py` as a genuine per-lap post-cliff gradient and
   leave the SQL's shape alone. State which, and why, before touching either file. (B) changes the
   seed's meaning and therefore `dim_compounds_season`'s contract; (A) does not.
2. **Fit the quadratic, or drop it.** `0.002·age²` is hardcoded and identical across every
   circuit/compound/season. Either fit it per cell off the same anchor the rest of the seed uses
   (`normalized_pace_s` — `08l` §2 established it is not downstream of the seed), or remove it and
   say what the linear term absorbs.
3. **Apply the fix at every site in the table above**, including the derivative column and the
   cost-curve duplicate. A fix at one site and not the others re-creates the split lineage.
4. **Rebuild and re-decompose.** Re-run `08l`'s exact decomposition against the rebuilt target and
   report the new `seed_bias` / `rest` / fraction with the same race-clustered interval. **This is
   ~~the acceptance test**: the fraction must move toward 1.0 or the fix did not do what it
   claims.~~ **CORRECTED by this item's RESULT — this acceptance test is ill-posed and is not a
   valid criterion.** `seed_bias / target` carries the target's own mean in its denominator, and a
   successful fix drives that denominator toward zero; the ratio therefore diverges *precisely*
   when the fix works, and cannot distinguish success from failure in the regime it was written to
   test. It came back **3.4518×** [2.7323, 4.5800] — further from 1.0 — while both un-normalised
   quantities moved sharply in the intended direction (`seed_bias` −3.5853 → −1.3620 s; target
   −1.8793 → −0.3946 s). The load-bearing acceptance test is step 5's seed-echo share, which is
   scale-free by construction.
5. **Re-run `08l`'s seed-echo probe on the rebuilt target.** If a zero-fit seed-echo predictor still
   captures ~90% of the trio's margin, the bias was relocated, not removed — say so.
6. **Retrain and re-price the blast radius**: the degradation trio, `cliff_classifier`
   (`laps_until_cliff_class` is a threshold scan over the same residual — `08l` flagged it as
   exposed and explicitly did not quantify it), and the published deltas in `02`, `08e`/`08f`/`08h`/`08i`
   and `11a`.

**THE TRAP — read this before reporting any improvement.** After step 4 **the target is a different
quantity**, so *pinball losses before and after are not comparable*, and neither are any of the
tree's published deltas. A retrained model scoring 0.9 against the new target has not beaten the
1.047 in `model_card.yml`. Anything claiming improvement must be a comparison **at fixed target** —
model vs. its own baseline on the same target, or the seed-echo share from step 5, which is
scale-free by construction. `foundations/epistemics.md`'s hard line applies with full force here.
The failure mode of this item is a report of a large improvement that is a change of units.

**Interactions.** `D9` (should `int_pit_strategy_cost_curve` consume `mart_degradation_predictions`)
should be decided **after** this lands — its motivating +3.59 s/stint is measured through the buggy
term and is expected to move. `D3` (land `08e`+`08f`) is measured against the old target; if it has
not landed before this item, its deltas need re-reading afterward. `08d`'s hand-sourced Pirelli
identity is what a per-cell refit would key on — read its caveats.

**Acceptance.** The rebuilt target's `seed_bias / target` fraction, race-clustered, reported
alongside `08l`'s 1.9077× [1.7638, 2.0825]; the step-5 seed-echo share on the rebuilt target
alongside `08l`'s 88.6/92.6/89.0%; and a table of which published numbers in `02`/`08`/`11a` are now
stale, with the ones re-measured this session marked as such.

**Definition of done.** The four sites are consistent, the fix's shape is argued in writing before
it was applied, the rebuilt target is decomposed and the seed-echo share re-measured, and every
number the fix invalidated is either re-measured or explicitly marked stale in its own leaf doc.

**Raised by** [`08l`](#08l--the-seed-compound-curve-that-defines-the-degradation-target).

### `08m` — RULING ON THE FIX SHAPE, written 2026-09-16 before any SQL was edited

**Ruling: (A) — keep the seed, correct the consumption.** `compound_cliff_severity`'s 438 fitted
values are not touched, `dim_compounds_season`'s contract is unchanged, and `survival.py` is not
edited. Five reasons, in descending weight:

1. **`compound_cliff_severity` is itself a published ML feature**, not only a curve parameter —
   `ml/src/schema.py:124`, `ml/src/attribution.py:107`, `ml/model_card.yml:43` (and again at :78, in
   the `compound` ablation group). Option (B) changes its units from seconds to seconds-per-lap
   *without changing its name*. That is a feature-contract change: it silently re-defines a column
   the 32-feature contract, the ablation groups and the model card all name, and it would need the
   full six-step gate plus a model-card relabel to be legitimate. (A) leaves every value and every
   meaning intact.
2. **The estimator cannot identify what (B) needs.** A genuine per-lap post-cliff gradient must be
   fit on the post-onset region, which is short (`laps_past_cliff > 0` on 19.4% of rows; median 6
   among those) and *selection-biased in the direction that matters*: drivers pit to escape the
   cliff, so the stints that run deep past onset are disproportionately the ones where the cliff did
   not bite. Kaplan-Meier handles exactly this censoring for **onset**; nothing in `survival.py`
   handles it for a post-cliff **slope**. (B) would therefore replace a units bug with a
   downward-biased new estimate — a plausible-looking number, which `foundations/epistemics.md`
   names as the failure mode to avoid inventing mid-item.
3. **(B) also has a double-counting trap of its own.** The SQL adds `wear_gradient*age` *and* the
   severity term, so a severity refit as the *total* post-cliff slope would double-charge the linear
   wear it already contains; it would have to be fit as the *excess* slope. That is a second
   derivation with its own identification argument, for the smaller of the two available gains.
4. **`08l` already ruled "keep the seed".** (A) is consistent with that ruling; (B) reverses it
   without any new evidence about the seed's *values* — and 08l's evidence was that the values are
   fine and the formula is not.
5. **Six consumers, one contract.** `dim_compounds_season` is read by
   `int_compound_cliff_predicted`, `int_pit_strategy_cost_curve`, `int_constructor_deg_sensitivity`,
   `fct_ghost_car_pace`, `fct_ghost_race_finish` and `fct_cliff_prediction_features`. (B) changes
   what the column means for all six at once; (A) changes only how each one consumes it, site by
   site, reviewably.

**What the estimator actually licenses.** `survival.py::estimate_cliff_severity` computes
`post.mean() − pre.mean()` with `pre = age ∈ [onset−5, onset−1]` (5 laps, centroid `onset−3.0`) and
`post = age ∈ [onset, onset+5]` (6 laps, centroid `onset+2.5`). So the measured number is **the
total pace change across the onset between two window centroids 5.5 laps apart**. Three consequences:

- It is a **magnitude over ~5.5 laps**, not a rate. Charging it once per lap for up to 48 laps is
  the bug.
- It is **agnostic between a step and a ramp** inside that window — a two-window mean difference
  cannot distinguish them — so either is within the estimator's resolution, and neither may be
  extrapolated past `onset+5`, where the fitter measured nothing at all.
- **~48.7% of it is ordinary wear, not cliff.** The formula already contains `wear_gradient*age`,
  which rises by `5.5 × wear_gradient` across the very same centroid separation. Mean
  `5.5 × wear_gradient` is 0.4385 s against mean severity 0.8996 s. The cliff-attributable **excess**
  is `GREATEST(severity − 5.5·wear_gradient, 0)`, mean 0.4829 s; it floors at zero on 41 of 438 cells
  (9.4%), where the measured "cliff" is no worse than the compound's own linear wear continuing.

**The replacement term — a moment-matched saturating ramp.**

```
excess   = GREATEST(severity − W·wear_gradient, 0)        W = 5.5  (pre+post centroid separation)
plateau  = (W / P) · excess = 2.2 · excess                P = 2.5  (post-window centroid past onset)
term(k)  = plateau · LEAST(k, W) / W                      k = laps_past_cliff
```

Ramps linearly from 0 at onset to `plateau` at `onset+5.5`, then holds flat. The `W/P` gain is not a
fudge: it is what makes the *fixed* curve reproduce the fitter's own measurement exactly — the model's
predicted pace change from `onset−3.0` to `onset+2.5` is `W·wear_gradient + plateau·(P/W)`, which
equals `severity` by construction. So the seed's number is consumed in the units it was measured in,
over the horizon it was measured over, and not again. Chosen over a pure step because it is
continuous at onset (the derivative column and the residual both consume this curve) and because it
moment-matches; a step would have required its own `6/5` occupancy correction for the `age = onset`
lap, where `laps_past_cliff = 0`.

Sanity check, median cell (`wear_gradient` 0.070, `severity` 0.850): plateau **1.023 s**. The
cost-curve model's own comment states "real cliff falloff is 1-3 s/lap". The fix lands at the bottom
of the range the codebase already believed; the formula it replaces charged **40.8 s** at
`laps_past_cliff = 48`.

**The quadratic: dropped, not fitted.** `0.002·age²` is removed at every site. Why dropped rather
than fitted per cell: (i) it has no provenance anywhere — one literal constant, identical across all
438 circuit×compound×season cells, which directly contradicts the "rubber accumulation" mechanism its
own comment claims (that would vary by compound and circuit); (ii) **the linear term already absorbs
it** — `survival.py::_fit_wear_slope_with_wind` fits `pace ~ [1, age, wind]`, with **no quadratic in
the design matrix**, by OLS over the pre-cliff region, so the fitted slope already absorbs, in a
least-squares sense, whatever average curvature exists over the window it was fit on; adding a second
curvature term on top of a slope that already absorbed it is double-counting by construction, exactly
as with severity; (iii) fitting it per cell would require a new seed column and therefore (B)'s
contract change, for the smaller of the two terms. At age 30 the dropped term was charging 1.8 s, at
age 50 4.5 s, identically for a HARD and a HYPERSOFT tyre.

**The sites — the spec's table said four; there are six.** Corrected in the spec block above.
Sites 5 and 6 were not in `08l`'s diagnosis or in this item's opening scope; both consume the same
number under the same per-lap reading, and `fct_cliff_prediction_features`' 40-model upstream closure
contains **neither** (verified via `dbt ls --select +fct_cliff_prediction_features`), so fixing them
cannot contaminate this item's acceptance measurement.

### `08m` — RESULT 2026-09-16: the fix landed at five of six sites and the target was rebuilt. The scale-free acceptance test passes decisively — the zero-fit seed-echo share falls 88.6/92.6/89.0% → 39.7/49.9/23.5%, so the bias was **removed, not relocated**. The spec's *other* acceptance test failed, because that test is ill-posed: it divides by the very quantity a successful fix drives to zero.

**Read this first — the two acceptance tests disagree, and one of them is broken.** The
pre-registered `seed_bias / target` ratio moved **away** from 1.0 (1.9077× → 3.4518×). Taken at face
value that reads as a failed item. It is not, and the reason is not a judgement call: the ratio's
denominator is the target's own mean, which the fix drives toward zero, so the statistic diverges
exactly when the fix succeeds. Both un-normalised quantities moved hard in the intended direction,
and the scale-free test the spec itself called "scale-free by construction" moved from ~90% to
24–50%. The spec block above is corrected accordingly. The ratio is reported in full below anyway,
because suppressing a pre-registered number that came back wrong is the failure this tree exists to
prevent.

#### 1. The shape ruling: **(A)**, argued in writing before any SQL was edited

See the RULING section immediately above, written and committed to the doc before the first edit.
In one line: `compound_cliff_severity` is itself a **published ML feature** (`ml/src/schema.py:124`,
`ml/src/attribution.py:107`, `ml/model_card.yml:43` and `:78`), so **(B)** would have silently
re-defined a contract column's units without changing its name; and the post-cliff region **(B)**
would have to fit on is short and censored in the one direction that biases it (drivers pit to
escape the cliff, so deep-past-onset stints are selected for cliffs that did not bite — KM handles
exactly this for *onset*, and nothing in `survival.py` handles it for a *slope*). The seed's 438
values, `dim_compounds_season`'s contract and `survival.py` are all untouched.

**The replacement term**, defined once in the new `transform/macros/compound_cliff_wear.sql`:

```
excess  = GREATEST(severity − W·wear_gradient, 0)     W = 5.5   (pre+post centroid separation)
plateau = (W/P)·excess = 2.2·excess                   P = 2.5   (post-window centroid past onset)
term(k) = plateau · LEAST(k, W)/W                     k = laps_past_cliff
```

Two corrections, both forced by what the estimator actually measures (`pre = age ∈ [onset−5,
onset−1]`, centroid `onset−3.0`; `post = age ∈ [onset, onset+5]`, centroid `onset+2.5`):
**de-double-counting** — the curve already charges `wear_gradient·age`, which rises by
`5.5·wear_gradient` across that same separation, so **48.7%** of the measured severity (mean 0.4385 s
of 0.8996 s) was ordinary wear being charged twice; and **moment-matching, then saturation** — the
`W/P` gain makes the corrected curve reproduce the fitter's own two-window difference *exactly*, and
past `onset+5.5` the curve holds flat because the fitter measured nothing there. The `0.002·age²`
quadratic is **dropped** at every site: never fitted, identical across all 438 cells, and already
absorbed by the linear term, since `survival.py::_fit_wear_slope_with_wind` fits `pace ~ [1, age,
wind]` with **no quadratic in its design matrix**.

Median cell (`wear_gradient` 0.070, `severity` 0.850): the severity term at `laps_past_cliff = 48`
goes from **40.8 s** to a **1.023 s** plateau — which sits at the bottom of the "real cliff falloff
is 1–3 s/lap" range `int_pit_strategy_cost_curve.sql`'s own comment already asserted. The excess
floors at zero on **41 of 438 cells (9.4%)**, where the measured "cliff" is no worse than the
compound's linear wear continuing.

#### 2. The sites — six, not the four the spec listed

| # | site | in the spec's table? | what was done |
| :--- | :--- | :--- | :--- |
| 1 | `int_compound_cliff_predicted.sql` → `compound_wear_s` / `expected_compound_pace_s` | yes | **FIXED** via macro. The ML target's lineage. |
| 2 | `int_compound_cliff_predicted.sql` → `expected_degradation_rate_s_per_lap` | yes | **FIXED** via macro — and it carried a **third defect `08l` never reported**: it added the full `compound_cliff_severity` on *every* lap with **no hinge at all**, so a fresh tyre on lap 1 was charged the whole cliff severity as its current degradation rate. It is now the actual derivative of the curve above. This column is a published ML feature. |
| 3 | `int_pit_strategy_cost_curve.sql:189–194` | yes | **FIXED** via the same macro. Confirmed a duplicate, not a worse variant — the orchestration correction to `08l` was right. |
| 4 | `survival.py::estimate_cliff_severity` | yes | **NOT TOUCHED** — correct under ruling (A); the spec made it conditional on (B). |
| 5 | `fct_ghost_car_pace.sql:211` `cliff_interaction_s` | **no** | **FIXED** via macro. Required exposing `compound_wear_gradient` from site 1 (additive; no contract is enforced on that model). Its ±2.0 s guardrail clip is kept but is now near-inert: `ramp() ∈ [0,1]`, so the term is bounded by the plateau instead of growing with age. The clip's stated justification cited "severity up to ~3.3 s/lap"; the seed's severity max is **1.5** (the fitter winsorises), so that figure was stale as well as mis-united. |
| 6 | `int_constructor_deg_sensitivity.sql:380` `severity_used` | **no** | **DELIBERATELY NOT FIXED, and marked in the code.** It uses severity as an s/lap² *divisor*. The correct replacement is `plateau/5.5`, median **~0.17** against severity's **~0.85** — so the `GREATEST(…, 0.30)` floor on that same line, calibrated to the old scale and currently almost never binding, would bind on nearly every cell and clamp `cliff_onset_shift_laps` for the whole field. Swapping the numerator without re-deriving that floor would replace a units bug with a saturated constant. Re-deriving it is a measurement with its own acceptance test, not a line edit. **Carried to the handoff as a candidate item.** |

The arithmetic now lives in **one** macro, so sites 1/2/3/5 cannot drift apart — which is
`macros/README.md`'s own stated reason for the macro directory, and the exact failure that produced
this bug.

#### 3. ACCEPTANCE 1 — the decomposition, `08l`'s method unchanged

Same script, same `LEAD(...) OVER (PARTITION BY stint_id ORDER BY lap_in_stint)` window, same
`intervals.py::cluster_bootstrap` (147 races, 2000 resamples, seed 0). **Instrument check:** run
against the pre-fix warehouse it reproduced `08l` to six decimals on every figure *including both CI
bounds*, so the two columns below are the same instrument.

| | `08l` (old target) | `08m` (rebuilt target) | move |
| :--- | ---: | ---: | :--- |
| `target` mean | −1.8793 s | **−0.3946 s** | **79% closer to zero** |
| `seed_bias` mean | −3.5853 s | **−1.3620 s** | **62% smaller** |
| `rest` mean | +1.7059 s | +0.9674 s | — |
| `seed_bias / target` | 1.9077× [1.7638, 2.0825] | **3.4518× [2.7323, 4.5800]** | **away from 1.0** |
| training-eligible fraction | 1.7552× [1.6378, 1.8984] | 2.9909× [2.4377, 3.8260] | away from 1.0 |
| training-eligible rows | 82,470 | **81,619** | −851 |

**The ratio failed and the criterion was wrong.** `target = seed_bias + rest`, so the ratio is
`seed_bias / (seed_bias + rest)` — unbounded as the denominator passes through zero. The fix shrank
the numerator by 62% and the denominator by 79%, which is success on both, and the ratio rose anyway.
It cannot be used as a pass/fail test in this regime and should not have been pre-registered as one.

**What genuinely survives from `08l`'s qualitative finding:** `|seed_bias|` still exceeds `|target|`
with the same sign, so `rest` still carries the **opposite** sign (+0.967 against a target of
−0.395). The seed's forward contribution still determines the target's sign. **The bias is
substantially reduced, not eliminated** — and what remains is now mostly legitimate:

| post-fix `seed_bias` component | mean | share |
| :--- | ---: | ---: |
| fitted `wear_gradient·age` (legitimate, unchanged by this item) | −1.0819 s | **79.4%** |
| cliff ramp + temperature | −0.2801 s | 20.6% |

That **inverts `08l`'s attribution**. Before: only ~21% of the bias was the correctly-scaled fitted
term and ~79% was the two unfounded terms. After: **79.4% is the fitted linear term** and the two
unfounded terms are gone. The `−1.0819 s` matches `08l`'s independently-measured figure for that
term exactly, which is a clean cross-check that the fix left the legitimate term alone.

#### 4. ACCEPTANCE 2 — the seed-echo share, at **fixed target**. This is the load-bearing test.

`08l` compared its trivial predictor against `model_card.yml`'s *published* headline. That is a
different instrument (a fully-tuned production pipeline) from an in-memory refit, so this item ran
the identical probe against **both** warehouses — the scratchpad rollback copy (old target) and the
rebuilt one — through the production path only (`F.load_features` → `E._evaluation_split` →
`E.baseline_predictions` → `E._fit` → `E._score`), writing nothing.

**Instrument check (gate step 1):** on the old warehouse the in-memory refit reproduced
`model_card.yml`'s published `eval_headline` and `baseline_headline` to five decimals
(0.53202 / 1.04679 / 0.57851 and 1.46443 / 2.17766 / 0.89080) and `08l`'s trivial-predictor scores
exactly. The harness did not move.

| | old target (n_tr 68,574 / n_ev 13,896) | rebuilt target (n_tr 67,907 / n_ev 13,712) |
| :--- | :--- | :--- |
| | baseline / model / seed-echo → **share** | baseline / model / seed-echo → **share** |
| `p10` | 1.46443 / 0.53202 / 0.63828 → **88.60%** | 0.73368 / 0.47646 / 0.63159 → **39.69%** |
| `p50` | 2.17766 / 1.04679 / 1.13022 → **92.62%** | 1.26289 / 0.98236 / 1.12291 → **49.90%** |
| `p90` | 0.89080 / 0.57851 / 0.61292 → **88.98%** | 0.64268 / 0.51285 / 0.61212 → **23.54%** |

**The bias was removed, not relocated.** A zero-fit predictor that re-emits the seed's own forward
arithmetic plus one train-fold constant used to account for **88.6–92.6%** of the trio's entire
margin over its non-leakage baseline; it now accounts for **23.5–49.9%**. The share is scale-free —
every term in it is scored on one common target — so this comparison is legitimate across the
rebuild in a way that no loss comparison is. On the rebuilt target the models are doing **2–4×
more of their own work**.

**Caveat, stated rather than buried:** the rebuilt-target models were refit with the **published v11
hyperparameters** (`_params_for(target, 'v11')`), not re-searched against the new target. A
re-tuned model would score better, which would push the seed-echo share **lower** still — so
23.5–49.9% is a conservative (high) estimate of the remaining share.

#### 5. THE TRAP — the comparison this result does **not** make

`model_card.yml`'s 1.04679 (p50) and this item's 0.98236 are **not comparable and are not compared
here.** They are losses on two different quantities: the target's mean moved −1.8793 → −0.3946 s and
its population moved 82,470 → 81,619 rows. A smaller pinball loss against a target with a smaller
spread is arithmetic, not skill. **No claim of model improvement is made by this item.** The only
performance claims made are (i) model-vs-its-own-baseline *within* each column of the table above,
and (ii) the seed-echo share, which is a ratio of differences on one target. Every pre-existing
number in the tree measured against `next_5_lap_cumulative_jump_s` is now on a superseded quantity;
see §7.

#### 6. Blast radius — `cliff_classifier` quantified, which `08l` flagged and explicitly did not measure

Old vs new labels joined on `lap_id` across both warehouses:

- **14,833 of 137,447 labels changed class — 10.79%.**
- The majority class shrank and real cliff classes grew: `none_in_stint` **69.3% → 63.6%**,
  `6_plus` **11.1% → 15.5%**, `3_to_5` 8.6% → 9.2%, `0_to_2` 11.1% → 11.7%.
- Direction confirms the mechanism: the over-charged curve was **depressing the forward residual and
  erasing cliff crossings into the majority class**, exactly as `int_compound_cliff_predicted.sql`'s
  own bound-comment described for the 93.5 s/lap tail. `08l` listed this exposure as ASSUMED; it is
  now **measured**, and it is material.
- `is_training_eligible`: 1,747 rows lost, 376 gained, **net −1,371** (82,470 → 81,619). This makes
  `model_card.yml`'s `n_training_rows: 82470` stale.

#### 7. Which published numbers are now stale, and which were re-measured

| where | what | status |
| :--- | :--- | :--- |
| `08l` §1 / §3 / §5 | seed-bias decomposition, four-piece attribution, seed-echo share | **RE-MEASURED this session** — §3 and §4 above |
| `cliff_classifier` exposure (`08l` §6, ASSUMED) | degree of exposure | **RE-MEASURED this session** — §6 above |
| `08e`, `08f`, `08h`, `08i` | every pinball/baseline/reseed-floor number | **STALE** — banners added to each section in this doc. Not re-measured. Deltas remain valid *relative to each other* (both arms shared the old target); the leakage rulings stand. |
| `02` (`02b`/`02c`/`02d`/`02g`) | Phase 10a p50 pinball, the target-mean population tables | **STALE** — banner added to `02-feature-expansion.md`. Not re-measured. `02a`'s leakage ruling and the admission rule are unaffected. |
| `11a` | band, coverage table, the n = 82,470 population | **STALE** — banner added to `11-parallel-surfaces.md`. The negative recommendation survives (it rests on variants' relative out-of-sample behaviour); its "mostly a measurement artefact" diagnosis should be re-checked, since this item removed a real systematic distortion from the band it was recalibrating. |
| `11b` / `D9` | the +3.59 s/stint that motivates `D9` | **STALE** — it rides on the buggy term through `int_pit_strategy_cost_curve`, which this item changed. `D9` should be decided after re-measuring it. Not re-measured. |
| `10a`–`10e` (`stint_life_regressor`) | — | **NOT AFFECTED** — `08l` verified the target is `stint_length_laps − lap_in_stint`, with no dependency on the seed. Re-confirmed: group 10's models are not in this item's rebuild set. |
| `ml/models/*`, `ml/model_card.yml`, `data/marts/mart_degradation_predictions.parquet` | all five production artefacts | **STALE AND UNTOUCHED — BARRED.** See §8. |

#### 8. The production artefacts, which this item was barred from rebuilding

Every published artefact is now **inconsistent with the warehouse**: the v11 boosters were trained
on the old target, and `mart_degradation_predictions.parquet` holds predictions of a quantity the
warehouse no longer computes. This item retrained **only in memory**, wrote nothing to `ml/models/`,
and left `model_card.yml` alone, per its constraints. The published artefacts therefore remain
self-consistent with the published *contract*, which is the correct state until a human decides to
relabel them. **Carried to the handoff as a candidate follow-on item** (`08k` did exactly this job
after `08j`, and is the model for it): retrain and re-export all five targets against the rebuilt
target, regenerate `model_card.yml` (including `n_training_rows` 82,470 → 81,619), re-run
`scripts/gen_ml_reference.py`, and re-version — with the explicit note that the new headline numbers
are **not** comparable to v11's and must not be presented as an improvement over them.

#### 9. A pre-existing test failure this item exposed but did not cause

`ml/tests/test_features.py::test_aggregation_survey_still_names_the_outstanding_instance` fails
(198 passed, 1 failed). **Not caused by this item** — it touches neither `int_sc_hazard_history.sql`
nor `ml/tests/`. The test asserts the aggregation survey *still* reports
`int_sc_hazard_history` as "pools every ingested season", i.e. it asserts `02d`'s defect is still
outstanding. That model's own header records it was rebuilt as a season-lagged point-in-time rate on
**2026-09-11** (`02d`), and its file mtime confirms it. `transform/target/` is gitignored, and the
manifest on disk predated that rebuild — so the stale manifest had been masking the stale test until
this item's `dbt run` regenerated it. **Left unfixed deliberately**: updating an assertion about
another item's defect belongs to `02d`, not here. Flagged in the handoff.

##### §9 addendum — re-verified 2026-09-18, and a *second* failure that is a false positive

A later session re-opened this item (the pointer was still on `08m`), found the work already
complete and committed at `fb546b4`, and re-ran the checks rather than redoing them. Nothing in the
item was changed. What the re-run established:

- **The fix is live in the warehouse and reproduces §3.** `fct_cliff_prediction_features`:
  `AVG(next_5_lap_cumulative_jump_s) = −0.394565` over 95,346 non-null rows and **81,619**
  `is_training_eligible` rows — §3's `−0.3946` and `81,619` to the digits reported. `dbt test
  --select int_compound_cliff_predicted+ int_pit_strategy_cost_curve+` — **225/225 pass**, matching
  §10 exactly. All five fixed sites still call the macro and site 6 still carries its declined-and-
  marked comment; `transform/` is clean against `HEAD`.
- **`pytest ml/tests` now reports 199 passed, 1 failed** — the count moved only because an
  uncommitted `08h` test (`test_baseline_observations_n_is_never_a_feature`) was added since. The one
  failure is still §9's, still `02d`'s to fix.
- **The trap.** On a stale `transform/target/`,
  `test_features.py::test_no_undeclared_aggregation_scope` *also* fails, naming
  `fct_cliff_prediction_features` GROUP BY `(compound)` and `(compound, lap_in_stint)` as undeclared
  and its two `race_year` exemptions as stale. **This is a false positive and the source is
  correct**: the committed model groups by `race_year, compound` and `d.race_year, d.compound,
  d.lap_in_stint` (lines 181/191, identical at `HEAD` and in the working tree), which is exactly what
  the exemptions declare. `audit_aggregation_scope` reads *compiled* SQL out of the gitignored
  `transform/target/`, and `features.py::_model_sql` falls back to the on-disk compiled file when the
  manifest carries no `compiled_code` — which is the state a `dbt test`/`dbt parse` manifest leaves
  behind. The compiled artefact on disk predated the season-lagging, so the audit was grading last
  week's SQL. **`dbt compile` clears it**, and it did: 199 passed, 1 failed. Anyone who meets this
  failure should regenerate `transform/target/` *before* touching the model or deleting an exemption
  — the cheap "fix" here is to delete two correct declarations and re-open a real leak. This is the
  same gitignored-artefact failure mode as §9 itself, pointing the other way: §9 was a stale artefact
  *masking* a true failure, this is a stale artefact *manufacturing* a false one.

#### 10. What was run

`dbt run --select int_compound_cliff_predicted+ int_pit_strategy_cost_curve+` — **20/20 models
built**, `data/dev.duckdb` mutated. `dbt test` on the same selection — **225/225 pass**, including
`assert_compound_wear_bounded` and `assert_cliff_seed_severity_bounded`. Full `dbt compile` clean.
`pytest ml/tests` — 198 pass, 1 pre-existing failure (§9). Rollback point: `data/dev.duckdb` was
1.4 GB (under the 5 GB threshold), so it was **copied to the scratchpad before the first `dbt run`**
and both acceptance probes were run against that copy to produce the "old" columns above.

**Verified.** The ruling's premises: `compound_cliff_severity` appears in `ml/src/schema.py:124`,
`ml/src/attribution.py:107`, `ml/model_card.yml:43`/`:78`; `_fit_wear_slope_with_wind`'s design
matrix is `[1, age, wind]` with no quadratic; `estimate_cliff_severity`'s two windows and their
centroids. The seed's own statistics (n=438, severity median 0.8500 / mean 0.8996 / max 1.50, 22
rows at the winsorisation ceiling; mean `5.5·wear_gradient` 0.4385; excess floors on 41 cells).
The pre-fix decomposition reproducing `08l` to six decimals including both CI bounds. The in-memory
refit reproducing `model_card.yml`'s published headline and baseline to five decimals on the old
warehouse. Both acceptance measurements on the rebuilt target. The post-fix four-way attribution,
whose linear term matches `08l`'s independent figure exactly. The `cliff_classifier` label movement
and `is_training_eligible` deltas, joined `lap_id`-to-`lap_id` across the two warehouses. That
`fct_cliff_prediction_features`' upstream closure is 40 models and contains none of
ghost/constructor/pit-strategy (`dbt ls`). The compiled SQL at every fixed site. That
`int_sc_hazard_history.sql` is not among this session's modified files (`git status`).

**Assumed.** That the six sites are *all* the sites — found by grepping `compound_cliff_severity`
across `*.sql`/`*.py`/`*.yml`, so a consumer that reads the column under an alias or via `SELECT *`
would not have been caught. That the `W = 5.5` / `P = 2.5` centroids are the *effective* ones — they
are exact for a stint with every lap present in both windows, and censoring or missing laps would
shift them slightly per cell; not re-derived per cell from the fitter's own row sets. That dropping
the quadratic is better than fitting it — argued from the design matrix, not tested against a fitted
alternative. That the rebuilt-target models would rank the same way after a hyperparameter
re-search (they were refit with v11 params). That the `08e`/`08f`/`08h`/`08i`/`02` deltas remain
valid relative to each other — inherited from their shared-target construction, not re-run.
Site 6's floor-binding argument (median ~0.17 vs a 0.30 floor) is computed from the seed, not from
a trial rebuild of `int_constructor_deg_sensitivity`.

**Gates run.** Step 1 (instrument check) — **run, and it is the reason the old/new comparison is
admissible**: the probe reproduced `08l` to six decimals and `model_card.yml` to five. Step 2
(add-ablation on the identical split) — **not applicable**: this item adds no feature and admits no
arm; it changes an existing column's definition. Steps 3, 4, 6, 7 (reseed floor, permutation null,
pre-registration, e-value) — **not run**; no arm was admitted to the campaign family and no delta is
claimed against a floor. Step 5 (forward-window audit) — **not run as a fresh audit**, but the fix
is itself the repair of a forward-facing defect, and `dbt test`'s 225 invariants (which include the
bound assertions on this exact curve) passed. **This item is therefore `MEASURED`, not `GATED`.**

---

## 08n — Rebuild the shipped artefacts against the fixed target

**Opened 2026-09-16** by the orchestrating session, out of [`08m`](#08m--the-severity-units-bug-fix-how-the-sql-consumes-the-seed)'s
ruling. `08m` was barred from writing production artefacts; this is that write. It is the same job
[`08k`](#08k--rebuild-the-model-artefacts-against-the-post-08j-32-feature-contract) did after `08j`
— mechanical completion of a change whose ruling is already made — with one decision in it and one
way to get it badly wrong.

**Objective.** `ml/models/*`, `ml/model_card.yml`, `app/public/models/*` and
`data/marts/mart_degradation_predictions.parquet` currently predict a quantity the warehouse no
longer computes. `08m` changed how `expected_compound_pace_s` is formed, so
`next_5_lap_cumulative_jump_s` — the degradation trio's target — and `laps_until_cliff_class` —
`cliff_classifier`'s label, 10.79% of which changed class — are both different quantities than the
shipped artefacts were fitted to. Retrain, re-export, regenerate, re-evaluate.

**THE TRAP, and the reason this item exists as its own item rather than a step inside `08m`.** The
rebuilt model card's numbers are **not comparable to v11's**, and the temptation to present them as
an improvement will be strong because they will look like one. `v11`'s `eval_headline` for
`degradation_regressor_p50` is 1.04679 **against the old target**; a rebuilt p50 scoring ~0.98 has
not improved on it, because the two numbers measure different quantities on different row sets
(`n_train_rows` also moves 82,470 → 81,619). The only admissible statements are at fixed target:
model vs its own baseline on the rebuilt target, and the seed-echo share `08m` reports
(39.69 / 49.90 / 23.54%). **Any sentence of the form "the fix improved the model" is wrong** unless
it names the fixed-target comparison it rests on. `foundations/epistemics.md`'s hard line applies.

**The one decision: does this ship as `v11` or as a new version?** Argue it in writing before
rebuilding. `MODEL_VERSION_DEFAULT` is `"v11"` (`ml/src/schema.py:361`) and 11 artefacts under
`ml/models/` carry that tag. Overwriting `v11` in place makes the published `v11` label ambiguous —
the same name for artefacts fitted to two different targets, with `model_card.yml`'s old numbers
already quoted elsewhere in this tree. Cutting `v12` keeps the history readable but touches
`app/public/models/` naming and interacts with `D2` (production still serves `v6`). State which,
and why, before any retrain.

**Scope — deliberately closed, so this stays mechanical.**
- **No hyperparameter re-tuning.** Reuse the `v11` hyperparameters. `08m` showed re-tuning would
  push the seed-echo share lower, which makes the un-tuned result the conservative one; a re-tune is
  its own item with its own acceptance test.
- **No modelling decisions.** If a target no longer beats its baseline on the rebuilt target, that
  is a **finding for the log and a candidate item** — not something to repair here by tuning,
  reweighting, or changing the baseline.
- ~~`stint_life_regressor` is **not** implicated (`08l` verified its target is built from
  `int_stint_geometry`, not the residual) — but it shares the manifest and the contract, so confirm
  rather than assume its artefacts are still valid.~~ **CORRECTED by this item's RESULT §4: it IS
  implicated, on two counts, and its `v11` artefacts were NOT still valid.** `08l`'s ruling holds
  for the target's *values* only (verified again here: `remaining_stint_life_laps` is synthesised in
  `features.py:165` as `clip(stint_length_laps − lap_in_stint, 0, None)`, neither input downstream
  of the seed). But (i) two of its 32 **inputs** — `expected_compound_pace_s` and
  `expected_degradation_rate_s_per_lap`, both in `FEATURE_GROUPS["cliff_prior"]` — were rewritten by
  `08m`, and (ii) its **row set** moved 121,193 → 119,822, because `features.py:124` filters every
  target by `is_training_eligible`, which is built from `anomaly_class`, which is computed from
  `driver_skill_residual_s`. It was retrained with the rest, and it is the one target whose
  `v11`/`v12` headlines are comparable in kind. The instruction to "confirm rather than assume" was
  the right instruction and is what caught this.

**Method.** Retrain the affected targets ~~(the degradation trio and `cliff_classifier`)~~ — **CORRECTED
by this item's RESULT: all FIVE, `stint_life_regressor` included, for the two reasons in the
corrected scope bullet above; and the manifest names one version for all five, so a partial rebuild
could not have satisfied `test_manifest_version_has_a_complete_artefact_set` anyway** — at the chosen
version tag, re-export ONNX, regenerate the manifests and `model_card.yml`, re-run the evaluation
report, regenerate `data/marts/mart_degradation_predictions.parquet` (`python -m ml.src.predict`),
and sync the browser-read copies under `app/public/models/`. Back up every artefact to the session
scratchpad before overwriting it. `08k`'s history entry records the verification steps that caught
drift last time — sha256 of each `.bst`/`.onnx` against what `manifest.json` declares, and a
byte-for-content diff of the `app/public/models/` copies against `ml/models/`; repeat both.

**Acceptance.** `python -m pytest ml/tests -q` is green apart from
`test_aggregation_survey_still_names_the_outstanding_instance`, which is a **known pre-existing
failure belonging to `02d`** (it asserts a defect `02d` fixed on 2026-09-11; a stale dbt manifest
masked it until `08m`'s rebuild) — do not repair it here and do not let it be quietly absorbed into
this item's result. Every artefact's declared feature count and sha256 matches its manifest. The
model card's new numbers are reported **with an explicit statement that they are not comparable to
v11's**, and each target's beats-baseline verdict is stated on the rebuilt target.

**Definition of done.** No artefact predicts the superseded target; the version decision is argued
in writing; the card carries its non-comparability statement; and nothing in this item's write-up
claims an improvement over `v11`.

**Raised by** [`08m`](#08m--the-severity-units-bug-fix-how-the-sql-consumes-the-seed).

### `08n` — THE VERSION RULING, written 2026-09-16 before any retrain was run

**Ruling: cut `v12`. Do not overwrite `v11` in place.** `MODEL_VERSION_DEFAULT` moves `"v11"` →
`"v12"`; the eleven `v11` artefacts under `ml/models/` are left on disk untouched. Five reasons, in
descending weight.

1. **The codebase already has this policy written down, in the guard built for exactly this
   failure.** `ml/src/train.py::_guard_target_change`'s docstring: refitting across a target change
   would overwrite *"the ones ONNX-exported into `app/public/models/` and the rollback point for
   everything after them — with models of a DIFFERENT QUANTITY under the same name, the same
   artefact path and an unchanged manifest. Nothing downstream would notice."* Its remedy, in its
   own words: *"Use a new `--version` for the new target (and promote it deliberately)."* That is
   this item, verbatim. Shipping `v11` in place is the thing the guard exists to refuse.
2. **The guard cannot fire here, which strengthens the case rather than weakening it.** It compares
   the training log's `target_column` against `spec.source_column` — both are the *string*
   `next_5_lap_cumulative_jump_s` before and after `08m`, because `08m` changed the column's
   **definition** upstream in SQL, not its name. Verified: the latest `v11` logs record
   `target_column: next_5_lap_cumulative_jump_s` (trio) and `laps_until_cliff_class`
   (`cliff_classifier`), so `_guard_target_change` returns at its `existing == spec.source_column`
   early-out and prints nothing. The fingerprint warning is unreachable on this path — it is gated
   behind `target_column is None`. **So the automatic protection against precisely this mistake is
   blind to a definitional change under a stable column name**, and the only thing standing between
   this item and the failure the guard describes is the version decision being made deliberately.
   (Recorded as a finding; see the RESULT.)
3. **Direct precedent in this project, and it went the other way once already.**
   `MODEL_VERSION_DEFAULT`'s own lineage note on `v10`: *"It is the first version fitted against the
   two target/label changes that were already live in the mart SQL … Both were already the code's
   truth under the stale `v6` label; v10 is the first artefact set that actually reflects them."*
   The tree has already been bitten by one label spanning two target definitions, and the recorded
   fix was to cut a new version. Repeating the mistake under a different number is not an option
   this item gets to take quietly.
4. **`v11`'s numbers are load-bearing citations all over this tree.** `model_card.yml`'s
   1.04679/0.53202/0.57851, `D3`'s decision text, the STALE banners `08m` just added to
   `08e`/`08f`/`08h`/`08i`/`02`/`11a`, and `docs/reference/ml/degradation-model.mdx` all quote `v11`
   figures. Overwrite `v11` and every one of those citations silently points at a label whose
   artefacts no longer produce those numbers — the citations become unfalsifiable rather than
   merely stale. Cut `v12` and each stale citation stays attached to a label that still means what
   it meant when the citation was written, which is what makes the staleness *checkable*.
5. **Rollback, and `D2`.** `v11` is the current rollback floor. Overwriting it destroys the only
   artefact set on disk fitted to the old target, so there would be nothing to roll back *to* and
   nothing to diff against. And `D2` — production still serves `v6` — is a decision whose own text
   turns on "production is serving a DIFFERENT TARGET from what the card documents". `v12` makes
   that conversation tractable (`v6` → `v12`, with `v11` intact in between); an in-place `v11`
   rewrite makes it unanswerable.

**The argument against, stated and weighed rather than skipped.** `08k` (2026-09-10) rebuilt the
`v11` artefacts **in place** after `08j`, so there is an in-place precedent eleven days old, and
`v11` has never actually reached production (`D2`), so its label is arguably not yet externally
load-bearing. Both are real and neither survives the distinction the codebase itself draws: `08j`
changed the **feature contract** (33 → 32), and a model refitted on a different feature set is
still predicting the same quantity, so the card's numbers stay comparable *in kind*. `08m` changed
the **target**. `_guard_target_change` guards the target and not the feature set — that asymmetry is
the project's own line, deliberately drawn, and it puts `08k` on the legitimate side of it and an
in-place rebuild here on the wrong side. The cost of `v12` is churn (`app/public/models/` filenames,
one retained-version tuple in `test_onnx_parity.py`, regenerated docs), and churn is the cheaper
error.

**What `v12` means, so the label is not itself ambiguous.** `v12` = `v11`'s 32-feature contract and
`v11`'s hyperparameters, refitted against the post-`08m` warehouse. Nothing else moves: no
re-tuning, no contract change, no split change. `v11` → `v12` is attributable to `08m`'s change of
the compound wear curve and to nothing else — the same "hold everything else fixed" property the
`v10` → `v11` note claims for itself, and the property that makes the label mean something.

**Two consequences of the target change that the version bump does NOT resolve, flagged here so
they are not read as resolved:** the `v11` and `v12` headline numbers are *not comparable* for the
degradation trio and `cliff_classifier` (different quantity, different row set), and no amount of
version hygiene makes them comparable. And `stint_life_regressor` is a *third* case, neither
"unaffected" nor "target changed" — see the RESULT.

### `08n` — RESULT 2026-09-16: shipped as **`v12`**; all five targets beat their own baseline on the rebuilt target, all five significantly. **No comparison with `v11` is made, and none is available for four of the five targets.**

**The headline is a version, not a number.** `MODEL_VERSION_DEFAULT` is `"v12"`, all five targets are
refitted at `v11`'s hyperparameters against the post-`08m` warehouse, every shipped surface is
rebuilt and consistent, and `v11` is retained intact on disk as the rollback floor. The ruling that
got there is the section immediately above, written before the first booster was trained.

#### 1. What was run, in order

`train --all --tuned` (exit 0, all five) → `evaluate --all` (exit 0) → `predict` → `export_onnx --all`
→ `card --write` → `gen_ml_reference.py` → `make app-models`. Then the card was regenerated a second
time after `card.py` gained its non-comparability limitation, and the app sync, both verification
checks and the full suite were re-run against that final state — `08k`'s drift lesson, applied.

#### 2. BEATS-BASELINE, ON THE REBUILT TARGET. This is the only performance table in this item.

Each model against **its own baseline in the same run, on the same target**. `eval_season` 2024,
`cv_final_fold`, from `ml/artefacts/evaluation_metrics.json`.

| target | metric | model | its baseline | margin | beats | significant |
| :--- | :--- | ---: | ---: | ---: | :--- | :--- |
| `degradation_regressor_p10` | pinball | 0.47646 | 0.73368 | 0.25722 | **yes** | yes |
| `degradation_regressor_p50` | pinball | 0.98236 | 1.26289 | 0.28053 | **yes** | yes |
| `degradation_regressor_p90` | pinball | 0.51285 | 0.64268 | 0.12983 | **yes** | yes |
| `cliff_classifier` | macro-F1 | 0.35247 | 0.20667 | 0.14580 | **yes** | yes |
| `stint_life_regressor` | AFT NLL | 1.99134 | 2.18868 | 0.19735 | **yes** | yes |

`all_models_beat_baseline: true`, `all_claims_significant: true`, `claims_inside_noise: []`.
**No target regressed against its own baseline**, so the spec's "a target that no longer beats its
baseline is a finding" branch did not fire and nothing was tuned, reweighted or re-based.

**Instrument check, and it is a strong one.** The trio's production numbers reproduce `08m`'s
in-memory probe **to five decimals on all six cells** (model 0.47646 / 0.98236 / 0.51285, baseline
0.73368 / 1.26289 / 0.64268). `08m` ran that probe through the production functions in memory
against a rebuilt warehouse; this item ran the real pipeline and wrote artefacts. They agree
exactly, so `08m`'s seed-echo shares (**39.69 / 49.90 / 23.54%**, down from 88.6 / 92.6 / 89.0%)
carry over to the shipped `v12` artefacts without re-measurement.

#### 3. THE TRAP — the comparison this item does **not** make

`v11`'s headlines were measured against the **superseded** target. They are recorded here only to be
ruled out as a baseline:

| | v11 (OLD target) | v12 (rebuilt target) |
| :--- | :--- | :--- |
| `p50` model | 1.04679 | 0.98236 |
| `p50` **baseline** | 2.17766 | **1.26289** |
| trio `n_train` | 82,470 | 81,619 |
| trio `n_eval` | 13,896 | 13,712 |

**`v12`'s p50 has not beaten `v11`'s.** The target's mean moved −1.8793 → −0.3946 s and its spread
collapsed with it — which is why the *baseline* fell 2.17766 → 1.26289, a 42% drop on a predictor
that learns nothing at all. A pinball loss measured against a narrower target is a smaller number
for arithmetic reasons. **No improvement-over-v11 claim is made anywhere in this item**, and the
model card now carries the same statement as its first limitation, so the claim cannot be made
downstream from the card either.

#### 4. `stint_life_regressor` — the spec said "not implicated". It is a THIRD case, and the spec block is corrected above.

The spec (and `08l`) treated it as unaffected because its target is not built from the residual.
That is true of the **target** and false of the **model**, on two independent counts, both traced
this session rather than inherited:

1. **Two of its 32 inputs changed meaning.** `FEATURE_GROUPS["cliff_prior"]` contains
   `expected_compound_pace_s` and `expected_degradation_rate_s_per_lap` — both rewritten by `08m`
   (the second one had `08m`'s third defect, no hinge at all). Every target reads the same
   32-column contract, so `stint_life_regressor`'s `v11` booster was fitted on input values the
   warehouse no longer computes. Its artefacts were **not** still valid.
2. **Its row set moved, 121,193 → 119,822 (−1,371).** Fully traced:
   `features.py:124` filters every target by `is_training_eligible`;
   `fct_cliff_prediction_features.sql:749-754` defines that as
   `age_in_stint > 3 AND anomaly_class NOT IN ('mistake','conditions')`; and `anomaly_class`
   (`int_lap_anomaly_flags.sql:245`) is computed from `driver_skill_residual_s` via `mad_score`,
   `trailing_median_s` and `cliff_onset_passed`. `08m` changed what is subtracted into that
   residual, so it changed which laps count as anomalies, and therefore the training population of
   **all five** targets. This also reconciles `08m`'s note, which reports "net −1,371" beside
   "82,470 → 81,619" (−851): both are right and they are **different populations** — −1,371 is the
   `is_training_eligible` flag count (121,193 → 119,822, which is `stint_life_regressor`'s
   population), −851 is the trio's, which additionally requires a non-null target.

**What its target genuinely is, verified not assumed:** `remaining_stint_life_laps` is synthesised in
`ml/src/features.py:165` as `clip(stint_length_laps − lap_in_stint, 0, None)`. Neither input is
downstream of the compound wear curve, so the target's **values** are unchanged. `08l`'s ruling
holds for the quantity; it did not hold for the model.

**So `stint_life_regressor` is the one target where a before/after statement is admissible in kind** —
same target quantity, both sides scored on it — and it should be read with the caveat that the row
set is *near*-fixed rather than fixed:

| | v11 | v12 |
| :--- | ---: | ---: |
| AFT NLL | 1.98784 | 1.99134 |
| baseline | 2.18689 | 2.18868 |
| **margin over baseline** | **0.19905** | **0.19735** |
| `n_eval` | 20,272 | 19,973 |

Its skill is **materially unchanged** (margin 0.199 → 0.197 on a ~1.5% smaller eval set). Stated
plainly: `08m`'s repair neither helped nor hurt this model, which is the expected result for a model
whose target never moved. This is *not* evidence about the other four, whose targets did.

#### 5. FINDING (no item opened, per scope): `_guard_target_change` cannot see a definition change

`ml/src/train.py::_guard_target_change` exists precisely to refuse "models of a DIFFERENT QUANTITY
under the same name". **It did not fire, and could not have.** It compares the training log's
`target_column` **string** against `spec.source_column`; `08m` changed the column's *definition* in
SQL and left its *name* alone, so the comparison passes and the function returns at its
`existing == spec.source_column` early-out. The fingerprint check that would have caught it — and
the fingerprint **did** move, `0e8700ec…` → `7852405c…` — is unreachable on this path, because it is
gated behind `target_column is None` (the pre-Phase-7 logs that do not name a column at all).

So a retrain-in-place across this change would have been **silent**: no error, no warning, correct
input width, passing parity, and a manifest that still looked right. The only thing that prevented
it was a human-made version ruling. **The guard's protection is nominal, not actual, for any change
that redefines a column without renaming it** — and `08m`-style SQL repairs are exactly that shape.
A candidate fix is named in the handoff (a target *fingerprint* stored in the training log and
compared, so a name collision cannot hide a definition change); the item is **not** opened here,
because opening items is the orchestrating session's call.

#### 6. Artefacts rebuilt, and the two verification checks

`ml/models/`: five `.bst` + five `.onnx` at `v12`, `manifest.json` (5 models, **32 features**,
`version=v12`), `model_card.json`, `encoders.json`. `ml/model_card.yml` at `v12` with
`n_training_rows` **81,619** (`08m` flagged 82,470 as stale; it is now correct) and `feature_count`
32. `data/marts/mart_degradation_predictions.parquet` regenerated — 137,447 rows,
`in_envelope=119,822`, `crossing=0.08%`, `version=v12`. `docs/reference/ml/degradation-model.mdx`
regenerated; `gen_ml_reference.py --check` passes. `app/public/models/` holds the five `v12` ONNX
plus manifest/encoders/card, with the `v11` ONNX removed by `make app-models`'s own `rm -f`.

- **CHECK 1 (sha256 + declared width vs manifest):** all 10 artefacts match the sha256
  `manifest.json` declares, and all five boosters report **32** features against the manifest's
  declared 32. `n_features`, `shape[1]`, `len(feature_order)` and `len(S.FEATURE_COLUMNS)` all 32.
- **CHECK 2 (app copies vs `ml/models/`):** all five ONNX identical by sha256; `manifest.json`,
  `model_card.json`, `encoders.json` JSON-equal; **no non-`v12` ONNX left** in `app/public/models/`.

Both checks were run twice — once after the first sync, and again after the card was regenerated —
and pass in both states.

**The contract did not move.** 32 features before and after; `v11` → `v12` is `08m`'s warehouse
change and nothing else. ONNX parity passed on all five at export (`abs` ≤ 1.7e-4, `rel` ≤ 1.6e-4,
within `atol`/`rtol` 1e-5 combined).

#### 7. Test suite

`python -m pytest ml/tests -q` → **198 passed, 1 failed**, both runs. The single failure is
`test_features.py::test_aggregation_survey_still_names_the_outstanding_instance` — **the known
pre-existing failure belonging to `02d`**, unchanged in count and identity from what `08m` reported
before this item started. It asserts `int_sc_hazard_history` *still* pools every ingested season,
i.e. it asserts the presence of a defect `02d` fixed on 2026-09-11; a stale dbt manifest masked it
until `08m`'s rebuild. **Not repaired here, not absorbed into this item's result, and still open
against `02d`.** This session modified neither `int_sc_hazard_history.sql` nor
`ml/tests/test_features.py` (`git status`).

One test file *was* touched, deliberately and not to make anything pass:
`ml/tests/test_onnx_parity.py`'s retained-version tuple gains `"v11"`, following that file's own
standing comment that the tuple "must keep naming every retained version" — when
`MODEL_VERSION_DEFAULT` last moved, `v5` fell out of it and the rollback target silently stopped
being parity-tested. `v11` is now the rollback floor and is fitted to the pre-`08m` target, so it is
the one version that most needs to stay in that tuple. The parity target itself is unchanged: the
tuple is tried in order and `MODEL_VERSION_DEFAULT` (`v12`) is still first.

#### 8. Scope held

No hyperparameter re-tuning — every target refitted from its own unchanged
`ml/models/<target>_best_params.json`, which is what `--tuned` resolves. No modelling decisions: no
target needed one, since none regressed against its baseline. No feature-contract change. Nothing
committed; `git` state untouched apart from working-tree file contents.

**Backups** (every artefact this item was authorised to overwrite, taken before the first write):
`<session scratchpad>/backup-08n/` — `ml_models/` (the eleven `v11` artefacts, `manifest.json`,
`model_card.json`, `encoders.json`, all five `*_best_params.json`, and the full `training_logs/`),
`app_public_models/`, `data_marts/mart_degradation_predictions.parquet`,
`ml_artefacts/evaluation_metrics.json`, `model_card.yml`, `degradation-model.mdx`, `schema.py.orig`.
123 MB. Note that `v11`'s `.bst`/`.onnx` also remain in `ml/models/` — the backup is belt-and-braces,
not the only copy.

---

## 08o — Drop the IPW survival sample weight from the degradation quantile heads

**Raised 2026-09-19** by the build-order restructure, off a finding `08f-1` recorded and explicitly
declined to rule on: *"Not gated here — recorded because it fell out of the same arms"*
([`../eval/08f/MEASUREMENTS.md`](../eval/08f/MEASUREMENTS.md), section "Uniform-weight comparison").

**What is shipped today.** `ml/src/train.py:175-176`:

```python
if spec.kind == "quantile" and meta is not None and "survival_weight" in meta.columns:
    return meta["survival_weight"].to_numpy(dtype=np.float32)
```

Every degradation quantile head is fitted under IPW survival weights. The docstring's stated reason
is *"so early-pitted (degraded) stints are not under-counted at high `lap_in_stint`"* — a
plausible-sounding correction that has never been tested against **not doing it at all**.

**What `08f-1` measured, by accident.** Its baseline arm `A` was uniform weights (`w = 1`), because a
weight-scheme ablation has to drop *to* something:

| head | uniform `A` | shipped v12 | AFTER − A | `08f-1` floor | ×floor |
| :--- | ---: | ---: | ---: | ---: | ---: |
| p10 | 0.4711254463 | 0.4764640778 | −0.00533863 | 0.00763075 | 0.70× |
| p50 | 0.9817102187 | 0.9823587336 | −0.00064851 | 0.01115092 | 0.06× |
| p90 | 0.5093926910 | 0.5128462338 | −0.00345354 | 0.00839541 | 0.41× |

**Uniform is better on all three heads. Every one of those deltas is inside its own reseed floor.**
Both halves of that sentence are load-bearing and neither may be dropped when this item is quoted.

**The one thing that does clear a floor** is the permutation-null information term on p10: the real
weight vector costs **−0.00990506, −1.30× the floor**, against the same weight *values* randomly
reassigned across training rows — and the pre-`08f-1` scheme shows the same sign at −1.06×. So the
cost belongs to IPW reweighting as a mechanism, not to the season-lag. p10's capacity term (0.60×)
and p90's (≈ −1.0× on both schemes) also sit at or near their floors, which `08f-1` reads as
*"reweighting by itself, independent of alignment, measurably moves p10 and p90."*

> **This item may well close as a null, and that is a complete outcome.** The honest prior is a
> consistent three-for-three direction and one floor-clearing information cost, not a demonstrated
> headline win. Do not write it up as a free win; `08f-1`'s own clean null is the precedent for how
> to record it if it comes back that way.

### Method

**Arms.** `A` = uniform (`w = 1`), `B` = shipped IPW, `P` = permutation null (the weight vector
shuffled across training rows, so the weight *distribution* is preserved and only the row alignment
is destroyed — `08f-1`'s translation of gate step 4 for a weight scheme, reused unchanged).
Degradation trio only. `cliff_classifier` uses balanced class weights and
`stint_life_regressor` deliberately takes `None` (`train.py::_sample_weight`), so neither is touched
and both are asserted invariant by code trace rather than re-run.

**Pre-register before anything refits** (gates.md step 6), in the script docstring, as
`scripts/gate_08f1_survival_weight.py` did: the three arms, the families, the floors, the expected
direction, and the e-value construction.

**e-values under the post-`09c` construction.** `09c`'s non-retroactivity rule cuts *for* this item:
its arms are declared **after** that landing, so Construction B at n = 10, g = 1 applies
(`E_max` = 11^4.5 = 48,558.70) instead of the n = 5 ceiling of 36 that makes `02b`'s and `02c`'s
gate-7 non-rejection categorical. `09c` also flags the unresolved cost — 20 refits per arm, and an
open question about whether gate step 3's 5-reseed floor study has to move to 10 seeds with it.
Decide that here, in writing, before running, and record which way.

**The eval side is a separate statement and must be made, not assumed.** `evaluate.py:613`
(`_row_weights`) supplies `survival_weight` only as the **training** weight; the 2026-09-17
correction above establishes that `pinball_loss` is unweighted at eval time and names the two call
sites. So dropping the training weight does not silently move the metric — say so with the trace.

### Acceptance

- Gate 1 reproduces the published v12 headline on all three heads before any arm runs.
- All three arms scored through `evaluate.py`'s own `_fit`/`_score`, nothing reimplemented.
- Negative control reported whatever it comes out as, and every E reported including `E < 1`.
- Nothing written to `ml/models/`, `ml/artefacts/`, the warehouse or git.

### Definition of done

1. A written ruling on whether the IPW sample weight should be dropped from the quantile heads,
   with the deltas quoted against their own floors and the permutation-null split reported beside
   them — **not** a headline delta alone, because the headline deltas are inside noise and the
   information term is not.
2. The eval-side question answered explicitly: dropping the training weight does or does not move
   the scoring path, traced to the call sites.
3. The landing cost priced: it changes what three of five production models are fitted on, so it is
   a retrain and re-export of the trio plus a version bump on `08n`'s own argument. The ruling must
   say whether it should ride along with the `D10`/`D12` bundle (both of which already require a
   retrain) or go alone — that is a recommendation to the user, not a decision this item takes.
   **`D16` (raised 2026-09-20) is where that recommendation lands**: it asks whether `08o`, `08q`,
   `08i` (`D10`) and `02b` (`D12`) should land as one `v12 → v13` rebuild. Two facts for the pricing,
   both traced from source 2026-09-20: this item's own footprint is **three of five**, because
   `train.py::_sample_weight` returns `survival_weight` only when `spec.kind == "quantile"`; and the
   *version* is set-wide regardless, because `S.MODEL_VERSION_DEFAULT` is a single constant
   (`schema.py:361`) and `predict.py:43-76` loads **all five** artefacts at one version.
4. `survival_weight` stays in `IDENTIFIER_COLUMNS` and barred from `FEATURE_COLUMNS` under every
   outcome; the feature contract does not move.
5. If the answer is "no detectable difference", the item **closes** on that, with the numbers, and
   `train.py`'s docstring is corrected to say the correction is untested-no-longer rather than
   silently keeping a rationale the measurement does not support.

**Cost:** 0.5 – 1 day. **Model:** `opus-5` — the judgment call is open (the evidence is inside noise
with one floor-clearing counter-signal) and the outcome changes what three shipped models are fitted
on.

---

## 08p — `int_stint_geometry` still hardcodes `compound_code` to NULL

**Raised 2026-09-19** by the build-order restructure.
`transform/models/intermediate/int_stint_geometry.sql:67-69`:

```sql
-- compound_code (C1–C5) is circuit-specific; populated once
-- stg_tyre_allocations is ingested
CAST(NULL AS VARCHAR) AS compound_code,
```

**`stg_tyre_allocations` has been ingested since 2026-09-10.** `08d` is `LANDED`:
`transform/seeds/tyre_allocations.csv` holds 128 rows (one per race, wide —
`race_year, circuit_key, hard_code, medium_code, soft_code, source_url`), `stg_tyre_allocations`
unpivots them to 384 rows at `(race_year, circuit_key, compound_label)` grain, 16 dbt tests pass, and
all 127 mart races in 2019–2024 join. So the comment names a precondition that has been satisfied for
nine days, and the column is still a typed NULL every downstream consumer inherits.

**Why group 08 and not group 02.** This is a transform-layer correctness fix in the same compound
lineage as `08a` (the 2018 compound backfill) and `08d` (the seed itself). Filing it under 02 would
frame it as feature expansion, which is the one thing it must not do on its own authority.

### The constraint that makes this a ruling rather than a wiring job

`08d`'s own record contains two statements in tension, and this item has to say which governs a
column that would sit in the **feature lineage** rather than in a side table:

- **2026-09-10** — *"accept current table as NON-QUOTABLE convenience for internal use, allowing
  measurement to proceed without citing these rows as claims (`epistemics.md` line)… Until proper
  sourcing, nothing measured against this table may be quoted as a claim."* Taken on a measurement:
  **only 47 of 128 `source_url` values resolve; 81 return 404** against a press site that no longer
  serves its pre-2025 archive. `stg_tyre_allocations.sql`'s own header still carries this warning.
- **2026-09-17** — *"user confirms full correctness of 128-row mapping table across 2019–2024.
  Landed as is."*

A user attestation is evidence under this repo's rules; a dead URL is not evidence either way. But
"non-quotable convenience" and "in the lineage of a published feature" are not compatible states, and
[`../foundations/epistemics.md`](../foundations/epistemics.md) is where that is settled — not here,
and not by whoever writes the `JOIN`.

**Second constraint, measured not guessed.** The seed starts at **2019**, because Pirelli's relative
hard/medium/soft labelling starts at 2019 and `08d`'s acceptance clause puts 2018's
HYPERSOFT/SUPERSOFT/ULTRASOFT out of scope (they are already `dim_compounds_season`'s own
`compound_code`). So `compound_code` is NULL for **all of 2018** under every possible ruling — a
season-shaped missingness pattern, which is exactly the shape `02b` measured as *not* label-neutral
for the qualifying columns (2018 carried 51% of all NULLs on 12.5% of rows; NULL rows averaged
−1.7831 s of 5-lap jump against −2.1715 s for present rows). That has to be declared, not `COALESCE`d
away.

### Method

1. Rule the provenance question first, in writing, before touching SQL — the pattern `08m` set.
2. If admitted: join `stg_tyre_allocations` on `(race_year, circuit_key, compound_label)` in
   `int_stint_geometry`, replacing the NULL cast; `schema.yml` gains a `compound_code` column block
   stating the 2019 start, the 2018 NULL rule and the provenance caveat verbatim; a dbt test pins the
   2018-is-NULL rule so it cannot be silently back-filled later.
3. If not admitted: **delete the column and the comment.** A typed NULL that promises a future
   population, with no item behind it, is the same defect in a different shape.
4. Report row-level coverage after the change: how many `int_stint_geometry` rows resolve a
   `compound_code`, by season, and which `compound_label` values fail to join.

### Scope guard

**Land the column mart-only at most. `FEATURE_COLUMNS` is not touched by this item.** Whether
`compound_code` should become a 33rd feature — it would be a third `CATEGORICAL_COLUMNS` member, and
unlike `compound` an ordinal encoding of C1…C5 is at least *physically* ordered — is a separate
ablation under group 02's admission rule. Named here so it does not happen by accident.

And leave the negative outcome genuinely open: `dim_compounds_season` already sidesteps the
relativity problem by keying on `circuit_key × compound_code × season`, which is exactly why `08d`
says *"this item is not a repair; it's new information."* It is entirely possible that wiring the
column buys nothing any consumer needs and the right answer is (3).

### Definition of done

1. A written ruling on whether a table `08d` declared non-quotable may sit in the feature lineage,
   citing `epistemics.md`, and naming which of the two 2026-09-1x statements governs.
2. Either the column is populated with its coverage reported per season and its 2018 NULL rule
   tested and documented in `schema.yml`, **or** the column and its comment are deleted — no third
   state where the comment survives the decision.
3. `python3 -m ml.src.features --check` clean and the contract unmoved at 32 columns, whichever
   branch is taken.
4. `dbt run` + `dbt test` green on the touched models, with the counts quoted.

**Cost:** 0.5 – 1 day. **Model:** `opus-5` — it rules on whether a provenance-flagged table may enter
the lineage of a published feature, which is an epistemics call, not a wiring task.

---

## 08q — `theta_air` is a `COALESCE` default, not an estimate

**Raised 2026-09-20** by the fan-value reprioritisation. This is the follow-up `06b` proposed and
never created — `06b` called it `08l`, that id has since been used for the seed compound curve, so
it is created here as `08q`. The 2026-09-19 history entry lists it under `assumed` as *"a live,
unscheduled finding"*. It is now scheduled.

### The defect, re-traced from source 2026-09-20

Not taken from `06b`'s write-up — re-read line by line, because the whole item turns on it.

1. [`int_lap_air_state.sql:144-152`](../../transform/models/intermediate/int_lap_air_state.sql)
   builds `dirty_air_share_lap` as
   `MAX(CASE WHEN sector = 2 AND sector_air_state = 'dirty_air' THEN 1.0 ELSE 0.0 END)`.
   **One bit per lap** — there is one S2 per lap, and the code comment says so.
2. [`int_dirty_air_tax_component.sql:82`](../../transform/models/intermediate/int_dirty_air_tax_component.sql)
   lags it into `dirty_air_share_lag1`, which is therefore also one bit.
3. `:160-162` filters `calibration_panel` to `WHERE dirty_air_share_lag1 > 0` — leaving a regressor
   **constant at 1.0**.
4. `:168-177` is

   ```sql
   COALESCE(
       COVAR_POP(partial_residual_s, dirty_air_share_lag1)
       / NULLIF(VAR_POP(dirty_air_share_lag1), 0),
       0.5
   ) AS theta_air
   ```

   Zero variance → `NULLIF` returns NULL → the `COALESCE` falls through to the literal **0.5**.

`theta_air` is not a fitted slope. It is a default that has never once been overwritten by data.

### Why it is a fan-facing defect, not only a modelling one

[`app/src/features/dirty-air-cost/queries.ts:34-36`](../../app/src/features/dirty-air-cost/queries.ts)
selects `MAX(d.cumulative_dirty_air_tax_race_s)`, `AVG(d.dirty_air_tax_s)` and a count of laps where
`dirty_air_tax_s > 0` straight out of `int_dirty_air_tax_component`, and ranks drivers by the total.

With θ at 0.5 and the treatment one bit, `dirty_air_tax_s` is **exactly 0.5 on every dirty-air lap
and 0.0 otherwise**. So the page's "dirty air cost" is `0.5 × (a lap count)`, presented as measured
seconds. **The leaderboard is a lap counter with a unit attached.**

`06b` measured what the number should be — per-season θ, F2 (stint FE + tyre-age bins,
race-clustered):

| 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| +0.396 | +0.151 | +0.170 | +0.083 | +0.011 | +0.045 | −0.036 |

**0.5 sits outside the 95% CI in six of the seven seasons.** This is the same shape as `00d` — a
live public page built on a number this tree has already proved wrong — except that until now
nothing was tracking it.

### Why it is not cheap, said up front

`06b`'s **decision was to keep the global θ in production**, and the reason is structural rather
than timid. `int_lap_residual_decomposed` subtracts `dirty_air_tax_s` when forming
`driver_skill_residual_s`, and `fct_cliff_prediction_features` builds the regression target as a
lead-difference of that column. **The tax is inside the label.**

`06b` priced the footprint: a ±0.5 s step on **14.3% of panel laps**, against a training-label sd of
**0.988 s** and a median absolute value of **0.363 s** — half a standard deviation on one lap in
seven.

So re-estimating θ rewrites the target for all five families: a full gate ladder plus a v12 → v13
bump, on the same argument `08n` made. It collides with three things already on the board:

- **`D10`** — a floor-1 revert retrains all five artefacts anyway.
- **`D12`** — a `FEATURE_COLUMNS` bump retrains at least the classifier.
- **`08o`** — drops the IPW weight from the degradation trio.

**This leaf doc must say whether `08q` rides that bundle or goes alone**, the same clause `08o`
carries. Four items now want one version bump; deciding that once is cheaper than four times.

> **`D16` is where that answer lands — raised 2026-09-20 by the clubbing pass.** It asks exactly
> that question for all four (`08i`/`D10`, `02b`/`D12`, `08o`, `08q`) and it blocks nothing. Two
> corrections to the pricing above, both traced from source that day. (1) **This item's footprint is
> four of five, not five.** `grep -rn theta_air transform/models` returns
> `int_dirty_air_tax_component.sql` and nothing else, so θ moves `dirty_air_tax_s` →
> `driver_skill_residual_s` → `DEGRADATION_TARGET` and `CLIFF_TARGET`, while `STINT_LIFE_TARGET` is
> synthesised in `ml/src/features.py` from `stint_length_laps − lap_in_stint` and carries no
> dirty-air term. No `FEATURE_COLUMNS` entry moves either: `dirty_air_share_lap` and
> `dirty_air_thermal_load_surface`/`_bulk` come from `int_lap_air_state`, which never reads θ. (2)
> **The fifth artefact is re-cut anyway**, by the version convention rather than by a changed fit —
> `S.MODEL_VERSION_DEFAULT` is one constant (`schema.py:361`) and `predict.py:43-76` loads all five
> boosters at it, so a `v13` exists only once all five `.bst` files exist at `v13`.

### Two things `06b` says this item must not repeat

- **A binary regressor filtered to its treated arm identifies nothing.** Removing the
  `dirty_air_share_lag1 > 0` filter from `calibration_panel` is the minimum, not the fix.
- **`dirty_air_share_lap` is a one-bit, S2-only measure.** The natural repair is a **dose-response
  on the gap**, not a better-fitted constant. The gap is available: `int_lap_air_state` already
  computes `min_gap_s` and `dirty_air_intensity` off the same sectors, and
  [`stg_telemetry_position.sql:65`](../../transform/models/staging/stg_telemetry_position.sql)
  carries `distance_to_ahead_m` per sample.

### Method

1. Write the identification argument **first**, before touching SQL — the pattern `08m` and `00d`
   set. State what the treatment variable is, why it identifies θ, and what the estimand means when
   the treatment is a dose rather than a bit.
2. Pre-register per `gates.md` step 6 before any refit, including the global-vs-per-season choice.
3. Run the full gate ladder, because the label moves. Gate 1 reproduction is the rebuilt panel
   against `int_dirty_air_tax_component`'s **123,993 rows** and per-season treatment mean to 1e-9 —
   `06b` already did this once and it passed.
4. Price the landing explicitly: which artefacts, which published figures move, and whether it
   bundles with `D10` / `D12` / `08o`.
5. Re-check the app page against whatever ships, per `00d`'s last DoD clause.

### The negative outcome must stay open

`06b`'s per-season fit puts θ at **+0.011 to −0.036** across 2022–2024, and its lead placebo **fails
on 2021–2024**, which `06b` published as *"no detectable directional cost"*. If the estimated θ is
indistinguishable from zero on recent seasons, the right answer may be that the dirty-air-cost page
**should not show a per-driver seconds total for those seasons at all**. Ruling on that is part of
this item. Do not assume the fix is simply a better number.

### Definition of done

1. A written identification argument and a pre-registration, both before any refit.
2. θ estimated rather than defaulted, with the global-vs-per-season choice made on the evidence and
   the dose-vs-bit treatment ruled on explicitly.
3. The label footprint re-measured on the v12 substrate — `06b`'s 14.3% / 0.988 s figures are
   pre-`08m` and must not be re-quoted without re-measuring.
4. A written statement of whether `08q` rides the `D10` / `D12` / `08o` version bump or goes alone.
5. A written ruling on what `app/src/features/dirty-air-cost` should show, including the option that
   it shows nothing for the seasons where θ is indistinguishable from zero.

**Cost:** 1 – 2 days **for the estimation and the ruling** — *not* for the landing, which is a
target rebuild plus a retrain and re-export of all five artefacts and is the same cost `D10` is
being weighed against. **Model:** `opus-5` — it rules on an identification strategy and moves the
ML target, which is the definition of the default.
