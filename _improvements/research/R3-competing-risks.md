# R3 — Survival: the stint-life target is a competing-risks problem, and is not modelled as one

**Track:** T3 · **Prices:** `02d`, `05a`, and the `stint_life_regressor` family generally
**Status:** DRAFTED, reconciled against `data/dev.duckdb` on 2026-09-07 ·
**partially corrected 2026-09-08 by `10a`**

> **Correction, `10a`, 2026-09-08.** The measurement below counts 325 rows that are not stints:
> 2018 laps FastF1 never assigned a stint number, mean length 1.06 laps, which
> `fct_stint_features` sorts below every real stint and so reports as *uncensored*. **127 of them
> are non-green.** On real stints only, the headline is **1,416 / 5,037 = 28.1%** rather than
> 1,543 / 5,360 = 28.8%, and the 2018 row of the season table below is wrong in three of its four
> cells: **495 stints, 17.4% non-green, mean 24.0 laps green / 15.5 non-green** against the 818 /
> 26.0% / 16.6 / 6.9 printed here. No other season contains such a row, so 2019–2024 stand as
> written. The 2×4 decomposition immediately below is reproduced cell-for-cell by
> `int_stint_end_regime` and is correct *as a decomposition* — it is the shares derived from it
> that needed the artefact rows removed. The finding is unaffected: 2018 simply stops being the
> season where non-green endings ran four times shorter than green ones.
> Detail in [`../work/10-competing-risks.md`](../work/10-competing-risks.md).

This is the strongest finding of the round, because it is the only one where a well-established
statistical framework maps onto a **measured** defect in a shipped model rather than onto a
hypothetical one.

---

## The claim

`schema.py` frames remaining stint life as a single-event, right-censored survival problem:
`survival:aft` over `[y+1, y+1]` (uncensored) or `[y+1, +inf)` (censored), where "censored"
means `is_censored_stint` — the stint ended at the flag or at retirement.

That framing has exactly one failure mode in mind: *the stint didn't finish, so the observed
life is a lower bound*. It is correct as far as it goes.

**What it misses is that "uncensored" is not one event.** A stint that ends in a pit stop ends
for one of several reasons, and only one of them is a statement about the tyre.

---

## The measurement

Read-only against `data/dev.duckdb`, joining `fct_stint_features` to the final lap of each
stint in `int_stint_geometry` and classifying the regime in force on that lap.

**Verified — the end-regime decomposition (n = 8,333 stints, 2018–2024):**

| censored | end regime | n | mean stint length (laps) |
| :--- | :--- | ---: | ---: |
| False | green | 3,817 | 19.44 |
| False | **safety car** | **913** | **11.14** |
| False | **red flag** | **387** | **5.34** |
| False | **VSC** | **243** | **17.04** |
| True | green | 2,754 | 25.28 |
| True | safety car | 129 | 10.78 |
| True | VSC | 55 | 18.80 |
| True | red flag | 35 | 2.31 |

**1,543 of the 5,360 uncensored stints — 28.8% — end under a deployment or a red flag** (1,416 of
5,037, 28.1%, once `10a`'s 325 unassigned-lap rows are removed — see the correction above). The
model is told each of those is a completed tyre life. It is not: it is the moment the pit wall
was handed a free stop.

The effect size is not marginal. Green-ended stints run **19.44** laps; SC-ended ones **11.14**;
red-flag-ended ones **5.34**. The AFT fit is therefore fitting a mixture whose components differ
by roughly a factor of two — and, in the red-flag case, by nearly a factor of four.

**Verified — this is present in every season** (uncensored stints only; the 2018 row is corrected
by `10a` to 495 / 17.4% / 24.0 / 15.5):

| season | n | % non-green end | mean length, green | mean length, non-green |
| ---: | ---: | ---: | ---: | ---: |
| 2018 | 818 | 26.0% | 16.6 | 6.9 |
| 2019 | 647 | 19.2% | 20.5 | 13.4 |
| 2020 | 594 | 38.9% | 20.8 | 12.6 |
| 2021 | 795 | 34.3% | 22.5 | 7.3 |
| 2022 | 770 | 29.9% | 18.6 | 14.4 |
| 2023 | 912 | 30.9% | 18.8 | 10.0 |
| 2024 | 824 | 23.1% | 19.5 | 11.5 |

So it is not a 2020-and-2021 pandemic-calendar artefact, and it does not wash out post-2022.

### Corroboration from an artefact that already existed

**Assumed (importance rankings are not causal), but it is the fingerprint this hypothesis
predicts.** `ml/model_card.yml`'s `dual_importance` block, read 2026-09-07:

| model | `age_in_stint` in SHAP top-5? | in permutation top-5? | top two features (both methods) |
| :--- | :---: | :---: | :--- |
| `degradation_regressor_p50` | yes | yes | `compound_cliff_onset_laps`, `push_residual` |
| `cliff_classifier` | yes (#2) | no | `fuel_mass_kg` / `compound_cliff_onset_laps` |
| **`stint_life_regressor`** | **no** | **no** | **`fuel_mass_kg`, `lap_number`** |

The model whose entire job is remaining tyre life has **tyre age in neither top-5**, while the two
models that predict pace and cliff state both carry it prominently. What sits at the top instead
is `fuel_mass_kg` and `lap_number` — and fuel burns off near-linearly with laps, so those are one
signal, the **race clock**, counted twice.

A model fitted on a mixture of tyre-limit and deployment-timing events should look exactly like
this: pit windows and safety cars are functions of race lap, tyre wear is a function of tyre age,
and the mixture pulls the fit toward the clock.

**Three reasons this is corroboration and not proof**, all of which must be carried if it is
quoted: importance rankings are not causal; `lap_number` and `age_in_stint` are correlated by
construction (a set fitted on lap 20 has age ≈ lap − 20) so credit slides between them; and
`fuel_mass_kg` is near-collinear with `lap_number`. The card itself already flags this model's
SHAP/permutation disagreement as *"likely correlated features or leakage pressure"* — it noticed
the anomaly and attributed it to correlation.

**Assumed** — that the loss currently attributable to these stints is material in NLL terms.
The share and the length gap are measured; their contribution to the 1.9520 headline is not.
That is the arithmetic `02d` needs and nobody has run it.

---

## Why this matters more than it looks

`reference/ml_research_program.md` §1a already walks up to this and stops one step short. It
measures the SC share of stint endings (26.87% of uncensored, on a different flag definition),
correctly refuses to convert it into an NLL cap, and records the cap as OPEN. That was the right
call under a single-event framing, because under a single-event framing there is nothing to do
with the number except turn it into a cap.

Under a competing-risks framing there is something to do with it: **model it.**

The distinction is standard and its consequences are well understood
([review, Austin/Fine and successors](https://arxiv.org/pdf/2212.05157)):

- **Cause-specific hazard** — "given the tyre is still on, what is the rate of ending *for
  reason k*?" This is what a strategist actually wants: the tyre-limit hazard with the
  deployment hazard held separate.
- **Subdistribution hazard (Fine–Gray)** — what you need if the quantity of interest is the
  cumulative incidence of a specific cause in the presence of the others.

The current AFT model estimates neither. It estimates the marginal distribution of "lap at which
this stint stopped, whatever the reason", which is a mixture of a tyre-wear process and an
exogenous-interruption process, weighted by a circuit- and season-varying mixture parameter.

**And it is worse than a mixture, because the censoring is dependent.** A stint that ends under
SC ends early *because* an SC arrived, and SC arrival is correlated with race state, which is
correlated with tyre state (traffic, incidents, late-race). Under dependent censoring the
standard evaluation machinery — IPCW-weighted Brier, the concordance index — is itself biased,
not just the fit ([Overcoming Dependent Censoring in the Evaluation of Survival Models,
2025](https://arxiv.org/pdf/2502.19460)). The recommended treatment there is a **copula-based
sensitivity analysis**: don't claim to fix it, bracket it, and report metrics across a band of
dependence strengths. That is exactly the house style `ceiling.py` already uses for the oracle.

---

## What the literature offers, ranked by fit to this repo

**1. Discrete-time competing-risks hazard. Cheapest, and it fits the grain the warehouse already
has.** The data is lap-grain. A discrete-time hazard model asks, per lap: does the stint end this
lap, and by which cause? That turns survival into a multinomial classification over
{continues, ends-green, ends-SC/VSC, ends-red, ends-retirement} at lap grain — which is a model
family this repo already ships, tunes and exports. It handles censoring natively (censored rows
simply stop contributing), it gives a per-lap hazard that the app can render directly, and
Schmid & Berger's discrete-time framing is the standard reference. **It also unifies with the
cliff classifier**, which is already a lap-grain multiclass model over a horizon label.

**2. Cause-specific AFT / two-model split.** Keep `survival:aft`, fit it twice — once treating
non-green endings as *censored* (giving the tyre-limit distribution, which is the quantity the
gauge claims to show), once on the deployment process. Minimal code change: the interval label
already supports it, it is one column in the label construction. This is the cheapest possible
test of whether the reframing buys anything, and it is a genuine one — if the tyre-limit fit
under the recoded label does not move NLL beyond the family's reseed floor, the reframing is
closed on a measurement.

**3. Neural / monotonic competing-risks models.** [Neural Fine-Gray](https://arxiv.org/abs/2305.06703)
uses constrained monotonic networks so each cause's survival function is exactly monotone and the
likelihood is maximised exactly; [copula-based deep competing risks](https://onlinelibrary.wiley.com/doi/10.1002/sam.70051)
(2025) learns the dependence between causes rather than assuming independence. **Not recommended
first** — they cost the ONNX export path, the parity gate and `behaviour_audit`, which
`work/05` correctly names as a real cost rather than a footnote.

**4. Evaluation, which has to change regardless of which of the above is chosen.** AFT NLL on a
mixture is not a meaningful headline. The competing-risks equivalents are cause-specific
IPCW-Brier and time-dependent AUC, plus a calibration check — **D-calibration**, a Pearson
goodness-of-fit on transformed survival times, or the 2025
[A-calibration](https://link.springer.com/article/10.1186/s12874-025-02671-6) variant that
handles censoring less conservatively.

---

## The honest counter-argument

The pit wall's decision *is* the thing being predicted, from the app's point of view. A user
looking at "remaining stint life: 11 laps" arguably wants the realised answer, deployments
included, not a counterfactual tyre-limit answer.

That is a genuine product question and it is the user's call, not a statistical one. But it does
not rescue the current model, because **the current model answers neither question cleanly.** It
answers "the marginal mixture", which is the tyre limit contaminated by a deployment process it
cannot see coming, and a deployment process degraded by tyre variation. Splitting the causes lets
the app choose — and lets it show both, which is a better surface than either.

`int_sc_hazard_history` is exactly the term needed to recombine them: cause-specific tyre hazard
× circuit deployment hazard → the realised distribution. That table already exists and currently
feeds nothing.

## Proposed promotion into `status/build-log.json`

One item in group 05 or a new group, at `SPEC`, depending on `02d` (which needs the same
end-regime label built properly and season-lagged):

> Recode the stint-life label by end cause; fit the cause-specific arm with non-green endings
> treated as censored; compare against the incumbent under `foundations/gates.md` with the
> family's own reseed floor. Report cause-specific IPCW-Brier and a calibration check alongside
> AFT NLL, and state the dependent-censoring caveat rather than assuming it away.

Cost: days, not weeks, for arm 2. The label is one CASE expression over columns that exist.
