# R6 — The external field, the causal layer, and the decision layer nobody has assembled

**Track:** T7 + T9 · **Prices:** `03c`, `07a`, `07b`, `06`, and the app
**Status:** DRAFTED

---

## Part 1 — Where this project actually stands against the published field

Three recent papers are the closest published work to what this repo does. Read together they
say something useful: **the protocol here is ahead of the field; the model class is behind it;
and the scale is unmatched.**

### The direct competitor, and why its headline number should not worry anyone

[Data-driven pit stop decision support for Formula 1 using deep learning models
(Frontiers in AI, 2025)](https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2025.1673148/full)
is the nearest thing to a peer-reviewed version of this project's problem: FastF1, **2020–2024,
99,928 laps**, binary "does this lap contain a pit stop", five deep architectures, Bi-LSTM
winning with **ROC-AUC 0.988**, precision 0.77 / recall 0.86.

That number is not comparable to anything here, for reasons this repo's own `gates.md` would
catch immediately:

- **The model is bidirectional.** A Bi-LSTM over a 10-lap window processes the sequence in both
  directions, so the representation of lap *t* is built partly from laps *t+1 … t+9*. On a
  forecasting problem that is forward-window leakage of exactly the shape `audit_forward_window`
  exists to bar — and it is the architectural choice the paper credits for winning.
- **SMOTE is applied to a temporally split problem**, rebalancing 3,131 positives up to 88,299
  synthetic ones before training. Synthetic minority rows interpolate between real rows that may
  straddle the split.
- **ROC-AUC on a 3.5%-positive problem is the wrong summary**, and the paper does report AUC-PR
  alongside it, but leads with the 0.988.
- **No censoring, no competing risks.** The paper explicitly does not discuss retirements or
  non-standard pit counts. [R3](R3-competing-risks.md) shows that is a 28.8% problem.

The paper's own stated limitations are honest and worth quoting for the record: regulatory churn,
and *"reliance on public data ... lack access to proprietary team telemetry (tire temperature,
brake wear, fuel load)"* — which is `reference/ml_research_program.md` §2's external wall,
independently arrived at.

**The competitive read:** on evaluation discipline — season-grouped CV, per-family reseed noise
floors, permutation-null capacity/information arms, an SQL-AST leakage auditor, a hard
Verified/Assumed line — this project is not behind the published field. It is comfortably ahead
of it. That is worth knowing before spending anything to catch up.

### The paper that shows what the wall costs

[Explainable Time Series Prediction of Tyre Energy in Formula One Race Strategy
(SAC 2025)](https://arxiv.org/abs/2501.04067), by Todd, Jiang, Russo, Winkler, Sale, McMillan and
Rago, forecasts **tyre energy** — the energy applied to each tyre, from which degradation is
computed — using **Mercedes-AMG PETRONAS' own historic telemetry**, comparing deep models against
XGBoost with feature-importance and counterfactual explanations.

This is the target this project cannot have. Tyre energy is not in the public feed. It is the
concrete instance of §2's wall, and it confirms the wall is real rather than an excuse. It also
says something about the model class: with the *right target*, XGBoost was competitive with deep
models — so the incumbent class is not the thing holding this project back either.

### The paper this project should have written, at 1/1000th of the data

[A State-Space Approach to Modeling Tire Degradation in Formula 1 Racing
(arXiv 2512.00640)](https://arxiv.org/abs/2512.00640) is the most important find of this round.

It proposes a **Bayesian state-space model** in which tyre degradation is a **latent process
observed indirectly through lap times**: a state equation carrying degradation across laps with
**pit stops as state resets**, and an observation equation modelling lap time as a function of
**fuel mass** and latent tyre condition. Extensions cover compound-specific degradation rates,
time-varying dynamics, and a **skewed-t** observation distribution for asymmetric driver errors.
It beats an ARIMA(2,1,2) baseline, with the skewed-t specification strongest.

Three things follow.

1. **The method is validated and the scale is not.** The case study is **one driver in one race** —
   Hamilton, 2025 Austrian GP — from FastF1. The paper's own stated limitation is that it needs
   generalising to multi-race, multi-driver analyses. This repo has **137,447 laps, 8,333 stints,
   7 seasons, 36 circuits**, with fuel state (`int_lap_fuel_state`), stint geometry, compound
   parameters and pit-loss all already modelled. The generalisation the paper asks for is a
   warehouse query away from being feasible here and nowhere else in public.
2. **Its distributional choice independently corroborates a measurement made here.** The paper
   reaches for a skewed t; [R2](R2-model-family.md) measures the target at skewness **−0.829**
   and excess kurtosis **5.218**. Two routes, same conclusion.
3. **It is the honest form of the physics ambition.** §2 rules out physics *validation* and is
   right to. A latent state-space model is not a claim to have measured tyre temperature — it is
   an explicit statement that the state is unobserved and inferred, with the inference's
   uncertainty carried through. That is the mechanistically honest version of the `thermal`
   feature group, which `schema.py` already describes as an inference of exactly this kind.

**And a latent per-stint tyre state is a feature.** Fit the SSM, extract the filtered state, and
it enters the feature contract as a column like any other, testable under `gates.md` unchanged.
That makes this a Tier-2 cost, not a rewrite.

---

## Part 2 — The causal layer

### `03c` — AKM two-way fixed effects is correctly specified, with one caveat to write down

`work/03` already names the right estimator:
[Kline, Saggio & Sølvsten (2020), *Leave-Out Estimation of Variance
Components*](https://eml.berkeley.edu/~pkline/papers/KSS2020.pdf), which gives
heteroscedasticity-robust variance components and corrects the **limited mobility bias** that
plagues naive AKM when few units move between groups. `03a`'s "confirm the connected set
survives" is the right prerequisite. Nothing in the current literature displaces this choice.

Two additions:

- **The bias is severe exactly where this panel is thin.** Limited mobility bias grows as the
  number of movers falls relative to the model's dimensionality. With ~20 drivers and ~10
  constructors per season, the mover count is small in absolute terms. `03a` should report the
  **leave-one-out connected set size**, not just the connected set — the KSS correction is only
  defined on the former, and the `VarianceComponentsHDFE` package computes both.
- **An AKM variance decomposition is not a causal statement.** It decomposes variance under an
  exogenous-mobility assumption — drivers move between teams for reasons uncorrelated with the
  match effect. In F1 that assumption is obviously strained: good drivers move to good cars
  *because* they are good. Report it as a decomposition, with the assumption stated, not as
  "how much is the driver."

### `07` — the SC natural experiment is an IV problem, and DML is the estimator for it

`work/07` frames a safety-car instrument for pit timing and correctly insists the exclusion
restriction be argued **per outcome**. That is the hard part and it is scoped right.

What the modern literature adds is the *estimation* half. With a 33-dimensional conditioning set,
a hand-specified first stage is the weak point. **Double/debiased machine learning**
(Chernozhukov et al.) uses flexible learners for both nuisance functions — treatment and outcome —
with **Neyman orthogonality** and **cross-fitting** so that the ML fits' regularisation bias does
not contaminate the structural parameter. `DoubleML` and `EconML` both implement the IV variants
directly, and [recent work extends it to heterogeneous effects with efficient
instruments](https://arxiv.org/pdf/2503.03530).

The heterogeneity question — "does an early stop under SC pay differently for a front-running car
than a midfield one?" — is a **CATE** problem, and the causal forest is the standard tool. One
caution worth pre-registering: [How Do Applied Researchers Use the Causal Forest? A Methodological
Review (International Statistical Review, 2025)](https://onlinelibrary.wiley.com/doi/full/10.1111/insr.12610)
finds systematic misuse in applied work — chiefly reading CATE estimates as discoveries without
the honest-splitting and calibration tests GRF provides. Run `test_calibration` and report it.

**What is *not* the right tool:** modern staggered-adoption difference-in-differences
(Callaway–Sant'Anna, Sun–Abraham, de Chaisemartin–D'Haultfœuille). Those exist to fix a bias in
two-way FE under *staggered treatment timing with heterogeneous effects*. A safety car is not a
staggered adoption — units are not absorbed into treatment permanently. That literature is worth
knowing about for `03c`'s two-way FE, where the critique does partly bite, but it does not apply
to `07`.

---

## Part 3 — The decision layer this repo has 80% built and never assembled

This is the largest unclaimed value in the round, and it needs no new mathematics.

The warehouse already holds:

| table | rows | what it is |
| :--- | ---: | :--- |
| `int_pit_strategy_cost_curve` | 386,036 | cost of stopping at each lap |
| `int_pit_strategy_value` | 7,129 | realised strategy value per stint |
| `int_pit_loss_circuit` | — | empirical pit loss per venue |
| `int_sc_hazard_history` | 36 | per-lap SC/VSC hazard per circuit, EB-shrunk — **`schema.py` notes it is "exported for downstream consumers (unconsumed today)"** |
| the five ML models | — | degradation quantiles, cliff class, stint life |

Those are, precisely, the transition costs, the stochastic event process and the state dynamics of
a **stochastic dynamic program over pit timing**. The published formulation exists and is not
exotic:

- [On the optimization of pit stop strategies via dynamic programming
  (CEJOR, 2022)](https://link.springer.com/article/10.1007/s10100-022-00806-4), Carrasco Heine &
  Thraves — a DP over which laps to stop and which compounds to fit, minimising total race time,
  extended to a **stochastic DP incorporating yellow flags and rain**. That extension is exactly
  what `int_sc_hazard_history` is shaped to feed; its own header says it exists *"so a Monte Carlo
  race simulator could draw an interruption on each simulated lap."*
- [Optimizing pit stop strategies in Formula 1 with dynamic programming and game theory
  (EJOR, 2024)](https://www.sciencedirect.com/science/article/abs/pii/S0377221724005484) — the
  competitive extension, as a zero-sum feedback Stackelberg game.
- Heilmeier et al.'s race simulation and "virtual strategy engineer" line is the applied
  precedent; [Explainable Reinforcement Learning for Formula One Race
  Strategy](https://arxiv.org/pdf/2501.04068) (2025) is the RL variant.

**Why this matters beyond being a nice feature.** A DP is the thing that converts a predictive
distribution into a decision, and it changes what the models are *scored on*. Right now a
degradation quantile is scored by pinball loss, which is a statistician's question. Under a DP,
the same model is scored by **the expected race time of the policy it induces** — and that is a
metric a strategist can read, that the app can render, and that finally gives the p10 and p90 arms
a job. It also gives the whole programme a decision-relevant denominator to sit alongside
`ceiling.py`'s statistical one: the gap between the DP's policy under the model and under an
oracle is a headroom estimate **in seconds of race time**, which is the only unit anyone outside
this repo cares about.

**Cost:** the DP itself is a few hundred lines over tables that exist. The hard parts — the cost
curve, the hazard, the degradation forecast — are done. This is assembly, not research.

---

## Ranked recommendations from this track

1. **Assemble the stochastic DP.** Highest value-per-day in the round. Uses only existing tables,
   converts the model outputs into a decision surface, and yields a headroom metric in seconds.
2. **Fit the state-space model at scale.** The published method is a single-race case study; this
   is the only public dataset that can generalise it. Serves `06` (publication) directly, and the
   filtered latent state drops into the feature contract as a testable column.
3. **`07a` as specified, with DML as the estimator** and cross-fitting rather than a hand-specified
   first stage.
4. **`03a` reports the leave-one-out connected set**, and `03c` labels its output a decomposition
   under exogenous mobility rather than a causal driver share.
