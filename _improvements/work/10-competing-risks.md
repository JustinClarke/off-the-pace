# 10 — Competing risks in the stint-life target

**Group:** 10 · **Depends on:** `10a` before `10b` before `10c` · **Shares its label with `02d`**

Opened 2026-09-07 out of research round R1. The strongest finding of that round, and the only one
where a settled statistical framework maps onto a **measured** defect in a shipped model.

Full evidence: [`../research/R3-competing-risks.md`](../research/R3-competing-risks.md).
Do not re-derive it.

**The claim in one line.** `schema.py` frames remaining stint life as single-event right-censored
survival. But "uncensored" is not one event — a stint ends for several reasons, and only one of
them is a statement about the tyre.

**Verified.** Of 5,360 uncensored stints, **1,543 (28.8%) end under safety car, VSC or red flag.**
They run **11.14 / 17.04 / 5.34 laps** respectively against green's **19.44**. Present in every
season (19.2–38.9% non-green). The AFT fit is therefore a mixture of a tyre-wear process and an
exogenous-interruption process, with a circuit- and season-varying mixture weight.

**Corrected by `10a`:** 325 of those 5,360 are not stints at all but 2018 laps FastF1 never
assigned a stint number, and 127 of them are non-green. On real stints the share is **1,416 /
5,037 = 28.1%**, and 2018 drops from 26.0% to 17.4%. The claim stands; the 2018 row did not.
See `10a`'s correction table below.

**Corroboration, Assumed rather than Verified.** In `ml/model_card.yml`'s `dual_importance`,
`age_in_stint` is in **neither** top-5 for `stint_life_regressor`, while the two models predicting
pace and cliff state both carry it prominently. What sits at the top instead is `fuel_mass_kg` and
`lap_number` — near-collinear, i.e. the **race clock**. That is the fingerprint a mixture of
tyre-limit and deployment-timing events predicts. Importance rankings are not causal and
`lap_number` correlates with tyre age by construction; carry both caveats whenever it is quoted.

**And the input is not the problem.** `age_in_stint` is FastF1's `TyreLife` passed through
untouched, 0.21% missing, and every within-stint step is exactly +1 across 154,378 transitions.
See [`../notes/tyre-life-provenance.md`](../notes/tyre-life-provenance.md). This is a **target**
problem. Nobody should re-open the data question.

---

## 10a — The end-regime label — **LANDED 2026-09-08**

**Objective.** One column: why did this stint end?

**Method.** Classify each stint's final lap from `int_stint_geometry`'s `is_red_flag_lap` /
`is_safety_car_lap` / `is_vsc_lap`, crossed with `is_censored_stint`, into
{green-pit, sc-pit, vsc-pit, red, race-end, retirement}. Precedence must be declared, not
inherited from whatever order the CASE happens to be written in — red before SC before VSC is what
the R3 measurement used.

**`02d` needs the same label.** Build it once, use it twice; sequence the two together.

**Acceptance.** The label exists at stint grain, its precedence rule is written down, and its
distribution reproduces R3's table.

**Definition of done.** A later reader can tell, for any stint, why it ended and how confidently.

### What landed

`transform/models/intermediate/int_stint_end_regime.sql`, one row per `stint_id`, 8,333 rows.
`fct_stint_features` now carries `end_regime`, `stint_end_cause` and `end_cause_confidence`
alongside `is_censored_stint`, so `10b` is a change to label construction in `ml/src` and nothing
else. Guarded by 19 schema tests on the model and 5 on the mart's passthrough columns, plus
`transform/tests/assert_stint_end_cause_partition.sql`, which re-derives the label independently
of the model's own CTEs — a different route to the final lap, the censoring window and the
running-at-the-flag test rebuilt from staging — so it fails on drift rather than moving with it.

**Two facets, not one, and they are not redundant.**

- `end_regime` ∈ {green, safety_car, vsc, red_flag} — the track regime in force on the stint's
  final lap, emitted for **every** stint including censored ones. Crossed with
  `is_censored_stint` it reproduces R3's 2×4 table exactly, cell for cell, counts and mean
  lengths both.
- `stint_end_cause` — the six-class answer, which folds the regime into the censoring split.

Splitting them is what lets the cause label do the honest thing on a censored stint without
losing the measurement R3 rests on.

### The precedence rule, as declared

1. **Censoring outranks regime.** A censored stint is the driver's last of the race, so it did not
   end in a tyre change whatever was flying at the time; its causes are `race_end` and
   `retirement`. The regime is still recorded in `end_regime`, so nothing is lost. The 2021
   Belgian GP — stopped and abandoned under red flag, 20 drivers classified after 3 laps — comes
   out `race_end` with `end_regime = 'red_flag'`, which is the true pair of facts. This is what
   makes the taxonomy's own shape work: four uncensored causes, two censored ones, six.
2. **Within an uncensored stint, severity decides:** `red_flag` > `safety_car` > `vsc` > green.
   Not academic — `TrackStatus` is a concatenated digit string, and **346 final laps carry more
   than one code**: 276 red+SC, 53 SC+VSC, 17 red+VSC. Reorder the CASE and those 276 change
   class with nothing else failing, which is what the singular test exists to catch.
3. **Within a censored stint, the classified result decides.** Running at the flag →
   `race_end`, else `retirement`. The test is on `status` ('Finished', '+N Lap(s)', 'Lapped'),
   not on `is_classified`: 23 'Retired' rows *are* classified because the driver covered 90% of
   the distance, and they stopped. Disqualification is the one status that hides the answer — a
   post-race ruling, not a reason a stint ended, landing on drivers who ran to the flag and on
   drivers who did not — so it is resolved on distance instead, and marked `inferred`.

### How confidently — `end_cause_confidence`

| value | n | what it means |
| :--- | ---: | :--- |
| `observed` | 7,593 | every input read, nothing chosen |
| `inferred` | 415 | severity precedence had to choose (346), the pit marker is missing on an uncensored stint (328, overlapping), or disqualification hid the answer |
| `unassigned_stint` | 325 | not a stint — see below. `stint_end_cause` is NULL here |

### Correction to R3's numbers — the artefact stints

**Verified.** 325 of the 8,333 "stints" are built from the 343 laps FastF1 never assigned a stint
number, all in 2018, mean length 1.06 laps. `fct_stint_features` already sorted them below every
real stint so they come out *uncensored*, and R3 counted them: **127 of them are non-green**.
They are not stints and their ending has no cause, so `stint_end_cause` is NULL on them and they
are excluded from any share.

That moves two of R3's numbers and leaves the finding standing:

| | R3, as written | corrected | note |
| :--- | :--- | :--- | :--- |
| non-green share of uncensored | 1,543 / 5,360 = **28.8%** | 1,416 / 5,037 = **28.1%** | headline barely moves |
| 2018 non-green share | 818 stints, **26.0%** | 495 stints, **17.4%** | entirely artefact |
| 2018 mean length, green | 16.6 | **24.0** | 1-lap artefacts were dragging it |
| 2018 mean length, non-green | 6.9 | **15.5** | same |

No other season contains an unassigned-stint row, so 2019–2024 are unchanged and 2018 stops being
the outlier it appeared to be. R3's headline claim — that the AFT fit is a mixture of a tyre-wear
process and an exogenous-interruption process, present in every season — survives intact.

### Deviations from this doc, logged

- **The label is not built inside `fct_stint_features`.** The method above said "crossed with
  `fct_stint_features.is_censored_stint`". Instead `int_stint_end_regime` **owns**
  `is_censored_stint` — the definition moved down out of the mart, which now reads it back — and
  the mart's output is bit-identical on that column (8,333/8,333 against an independent
  recomputation; 2,973 censored, unchanged). "Build it once, use it twice" applied to the
  censoring window too, rather than leaving `02d` a second copy to drift from. This doc's method
  paragraph is corrected above.
- **Two extra columns beyond the six-class label**: `end_regime` (so R3's table stays
  reproducible) and `end_cause_confidence` (the "how confidently" the definition of done asks
  for). Plus provenance — `end_lap_id`, `end_lap_number`, `end_lap_in_stint`,
  `is_multi_regime_end`, `ended_on_pit_lap`, `was_running_at_flag`.
- **The family is `strategy`, not a new `survival` family.** `transform_docs_facts.py` fixes the
  intermediate vocabulary at five families, and `int_sc_hazard_history` — the model `02d` rebuilds
  — already sits in `strategy`.

### What `10b` reads

`stint_end_cause = 'green_pit'` is the tyre-limit set: 3,621 stints, mean 20.44 laps. Everything
else uncensored — `sc_pit` (806, 12.48), `vsc_pit` (223, 18.47), `red` (387, 5.34) — is what
`10b` recodes to censored.

---

## 10b — The cause-specific arm

**Objective.** Test whether separating the causes buys anything, cheaply, before anything
expensive is built.

**Method.** Keep `survival:aft`. Refit with **non-green endings treated as censored** — the
interval label already supports it; this is a change to label construction, not to the model
class. That fit estimates the *tyre-limit* distribution, which is the quantity the app's gauge
claims to show. Compare against the incumbent under
[`../foundations/gates.md`](../foundations/gates.md), delta against the family's **own** reseed
floor.

**This is a genuine test, both ways.** If the recoded fit does not move NLL beyond the floor, the
reframing closes on a measurement and `10c` never runs.

**Declare the e-value construction before running** (`09b`).

**Acceptance.** Gate steps 1–3 run in full; the delta is quoted with its floor ratio.

**Definition of done.** A written verdict: does splitting the causes move the family, or not.

---

## 10c — Evaluation that fits the framing

**Objective.** Stop quoting AFT NLL on a mixture as though it were a headline.

**Method.** Cause-specific IPCW-Brier and time-dependent AUC, plus a calibration check
(D-calibration, or the 2025 A-calibration variant which handles censoring less conservatively).

**And state the dependent-censoring caveat rather than assuming it away.** SC arrival correlates
with race state, which correlates with tyre state, so censoring is **not** independent — under
which IPCW-weighted Brier and the concordance index are themselves biased. The literature's
recommended treatment is a copula-based sensitivity analysis: bracket it across a band of
dependence strengths rather than claiming to have fixed it. That is the same bracketing house
style `ceiling.py` already uses for its oracle.

**Acceptance.** Cause-specific metrics reported with the dependence band, never as a point.

**Definition of done.** The stint-life headline says which cause it is about.

---

## The product question this does not settle

From the app's point of view the pit wall's decision *is* arguably the thing to predict — a user
reading "remaining stint life: 11 laps" may want the realised answer, deployments included. That
is a genuine product call and it is the user's, not a statistical one.

It does not rescue the incumbent, because the incumbent answers **neither** question cleanly. It
answers the marginal mixture: a tyre limit contaminated by a deployment process it cannot see
coming, and a deployment process degraded by tyre variation. Splitting the causes lets the app
choose — and lets it show both. `int_sc_hazard_history` is exactly the term that recombines them.
