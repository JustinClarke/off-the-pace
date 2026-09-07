# Energy Price Cap Lab — Implementation Plan

> **When the price cap jumped 54%, how much did Britain actually cut back?**

A browser-native tool that estimates how GB household energy demand responds to Ofgem
price-cap changes — weather-adjusted, with a stated identification strategy and
bootstrapped confidence bands — and lets a visitor set a counterfactual cap level and
see the estimated consumption and spend response, with honest uncertainty.

Chosen over the other shortlist candidates on 2026-07-05 — see
[career-project-shortlist.md](./career-project-shortlist.md) for the comparison and
[_misc/macro-shock-lab-plan.md](./_misc/macro-shock-lab-plan.md) for the macro sibling
this plan deliberately borrows its structure from.

---

## 1. The thesis

Between 2021 and 2024 the UK ran an accidental natural experiment: retail energy prices
for ~28m households moved in **large, discrete, pre-announced steps** on known dates,
set by a **published mechanical formula** (the Ofgem default tariff cap), not by
household demand. April 2022 alone was a +54% jump (typical dual-fuel bill £1,277 →
£1,971). That is about as close to textbook exogenous price variation as observational
consumer data ever gets.

Most public commentary answered "how did households respond?" with anecdote or raw
year-on-year comparisons that are mostly weather. This project does it properly:
weather-normalize daily demand, estimate the demand break at each cap reset, state the
identification assumption on the page, and put confidence bands on everything —
including the counterfactual slider.

One number the tool should be able to defend in an interview: a short-run price
elasticity of household gas demand, estimated from cap-reset events, with a CI that
overlaps the literature range (roughly −0.1 to −0.35) — and a plain-English account of
why the Oct 2022 event is excluded from the headline (see §5).

---

## 2. Why this project (decision record)

Decisions made and why — so future-me doesn't relitigate them:

1. **Energy over housing.** Housing (planning reform) is the hotter policy topic but
   the data is the project: portal data isn't legally scrapable, council records need
   FOI, and staggered-DiD across authorities raises the econometric bar. Energy data
   is free, daily, national, and available *today* — the project is the econometrics,
   not the acquisition. Ships in weeks, not months.
2. **Event study, not "RDD".** The cap creates a *temporal* discontinuity — price
   jumps at known dates. There is no running variable, so this is an interrupted
   time series / event study, and the plan says so. (An earlier framing called this
   "RDD on price cap discontinuities"; that was loose and would get picked apart in
   an interview.)
3. **Aggregate public data, not household microdata.** Household-level smart-meter
   data (SERL) needs accreditation measured in months. Daily LDZ-level gas demand and
   half-hourly national electricity demand are public and dominated by household
   behaviour (gas NDM especially). Cost: estimates are aggregate elasticities, and
   the write-up must say "this is not a household-level claim" (ecological caveat).
4. **Weather normalization is first-class, not a control tossed in.** Temperature
   explains the overwhelming majority of daily gas-demand variance. Without a
   credible weather model the price estimates are noise. It gets its own pipeline
   stage, its own validation, and its own toggle in the UI (raw vs adjusted) so the
   visitor can *see* why it matters.
5. **Reuse the Off The Pace stack.** Offline Python → Parquet + coefficient JSON on a
   CDN → React + DuckDB-Wasm, zero backend. Proven in production, costs ~nothing, and
   the counterfactual slider is linear scaling of precomputed coefficients — the same
   "no runtime inference" trick as the macro plan. One continuous portfolio story.
6. **Bands everywhere.** Same house rule as the rest of the portfolio: no single
   confident lines. The slider renders a ribbon, not a curve.

---

## 3. Data pipeline

| Source | Series | Cadence / access | Purpose |
|---|---|---|---|
| National Gas (Data Item Explorer / MIPI API) | Daily gas demand by LDZ, split incl. **NDM** (non-daily-metered ≈ households + small business) | Daily, free, no key | Primary demand outcome (gas) |
| NESO data portal (formerly National Grid ESO) | Half-hourly GB electricity demand (historic demand data) | Half-hourly, free | Secondary outcome (electricity) |
| Ofgem | Default tariff cap levels + annex model workbooks (by region, fuel, payment method; incl. wholesale allowance) | Per cap period, free XLSX | Treatment variable: price series + the mechanical formula |
| Met Office HadCET | Daily mean Central England Temperature | Daily, free, long history | Heating-degree-day (HDD) weather normalization, national |
| HadUK-Grid or ERA5 | Regional daily temperature | Daily, free | Regional HDD (stretch: per-LDZ weather) |
| DESNZ | Subnational annual consumption; Energy Trends | Annual (lagged ~18–24 mo) / quarterly | Cross-sectional anchoring, sanity checks |
| ONS | CPIH energy indices; Living Costs & Food spend shares | Monthly / annual | Spend calculations for the counterfactual view |

Pipeline mechanics (mirrors Off The Pace conventions):

- **Weekly GitHub Actions job** (macro series don't need nightly): pull → validate →
  clean → write compressed Parquet + a small `events.json` (cap dates, levels, %
  changes by fuel/region/payment method) to the static asset bucket.
- **Manual verification gate before anything ships:** reproduce a handful of known
  values by hand — the Apr 2022 +54% cap change, published typical-consumption
  figures, a known cold-snap demand spike — the same "verify a handful of known
  historical values" habit as the macro plan.
- Model estimation runs **offline on demand** (re-run when a new cap period lands),
  not per-request. Outputs: coefficient JSON + bootstrap draws summarised to bands.

Key treatment-series detail: the cap varies by **region (14 zones), fuel, and payment
method** (direct debit / prepayment / standard credit). v1 uses the national
dual-fuel direct-debit series as the headline price; the regional and payment-method
splits are kept in the Parquet from day one so the equity stretch (§8) needs no
pipeline rework.

---

## 4. Identification strategy

Stated on the page, not just here:

> **Assumption:** conditional on weather (HDD, non-linear), seasonality, calendar
> effects, and a slow-moving trend, the *timing and size* of cap resets are unrelated
> to unobserved short-run demand shocks — because the cap is set by Ofgem's published
> formula from a wholesale-price observation window months earlier. Households can
> anticipate resets (they're announced ~1–2 months ahead), so we read responses as
> "response to the announced-and-arrived price", and test for pre-adjustment.

Estimation, in increasing order of sophistication (v1 = first two):

1. **Weather model first.** Daily NDM gas demand ~ smooth function of HDD (spline or
   piecewise-linear with a heating threshold), day-of-week, holidays, seasonal terms,
   trend. Fit on pre-crisis years; validate out-of-sample (this stage has its own
   sanity gate: R² on held-out pre-2021 winters should be very high, or stop).
2. **Event study on the residuals.** Step + short dynamic response (local-projections
   flavour: one regression per horizon in days/weeks) at each cap-reset date. Convert
   each event's demand break + known price change into an elasticity; pool across
   events with event fixed effects. **Block bootstrap** (serial correlation) for CIs.
3. **Robustness:** placebo dates (random non-reset days), gas-vs-electricity contrast
   (gas is more price-salient for heating), leave-one-event-out, and an
   anticipation window test (demand drift between announcement and effective date).

Sanity anchors before anything ships (the macro plan's "check signs" habit):
demand should *fall* when price rises; the pooled elasticity should land near the
literature's short-run range (≈ −0.1 to −0.35 for residential gas); weather-adjusted
winter-2022/23 savings should be in the ballpark of published estimates (~10–20%).
If any of these fail, the bug hunt starts in the weather model, not the event study.

---

## 5. Known confounders (limitations section, written first)

These go on the public methods page verbatim — writing them now, before results exist,
is the point:

- **Oct 2022 is contaminated.** The Energy Price Guarantee replaced the cap (£2,500
  typical vs £3,549 formula), £400 EBSS rebates paid Oct–Mar, plus a national
  "save energy" publicity wave. The headline pools the *clean* events and shows
  Oct 2022 separately, labeled.
- **Salience ≠ price.** Cap resets arrive with saturation media coverage; part of any
  response is attention, not price. The tool says "response to a cap event", and the
  elasticity is framed as an upper bound on the pure price response.
- **Anticipation.** Resets are announced weeks ahead → pre-adjustment shrinks the
  measured step. Tested explicitly (announcement-window drift), reported either way.
- **Income vs substitution.** A bill shock is also an income shock; aggregate data
  can't separate them. Stated, not solved.
- **Structural conservation.** Insulation retrofits and boiler replacement accumulate
  through the sample; handled as slow trend, acknowledged as imperfect.
- **Aggregation.** LDZ/national NDM demand ≠ households only, and aggregate
  elasticity ≠ any individual household's. No household-level claims.

---

## 6. Architecture

```
┌──────────────────────── Offline (weekly + on new cap period) ───────────────────────┐
│                                                                                      │
│  National Gas / NESO / Ofgem / Met Office ──► GitHub Actions (weekly)               │
│                                                    │  pull → validate → clean        │
│                                                    ▼                                 │
│                                        Parquet panel + events.json                   │
│                                                    │                                 │
│                                                    ▼                                 │
│                              ┌─────────────────────────────────┐                    │
│                              │ Weather model (spline HDD, held- │  ← own validation  │
│                              │ out validation) → residual series│    gate            │
│                              └───────────────┬─────────────────┘                    │
│                                              ▼                                       │
│                              ┌─────────────────────────────────┐                    │
│                              │ Event study / local projections  │  ← stated          │
│                              │ + block bootstrap (Python,       │    identification  │
│                              │ statsmodels)                     │    assumption      │
│                              └───────────────┬─────────────────┘                    │
│                                              ▼                                       │
│                    IRF/step coefficients + elasticities + CI bands                   │
│                    (static JSON) · daily panel (Parquet) ──► GCS CDN                 │
│                    (reuses Off The Pace publish/versioning pipeline)                 │
└──────────────────────────────────────┬───────────────────────────────────────────────┘
                                       │
┌──────────────────────────────────────▼───────────────────────────────────────────────┐
│                    Browser (React + Vite + DuckDB-Wasm, zero backend)                │
│                                                                                       │
│  DuckDB-Wasm reads Parquet from CDN ──► explore charts (fuel/region/event/raw-vs-    │
│  adjusted). Counterfactual slider ──► linear scaling of precomputed coefficients     │
│  client-side ──► response ribbon (band, not line). No API key, no runtime inference. │
└───────────────────────────────────────────────────────────────────────────────────────┘
```

Architecture decisions and why:

- **Zero backend.** Coefficients are small and linear in the shock size, so the
  slider is `response = coefficient × Δprice` in JS — deterministic, free, and
  honest about what runs where (the lesson carried over from the macro plan's LLM
  diagram correction).
- **DuckDB-Wasm for the panel, JSON for the model.** The daily multi-year, multi-LDZ
  panel is worth querying client-side (region/fuel/date slicing without a server);
  the *model* is deliberately not — it's precomputed so results are reproducible and
  the page can't silently re-estimate.
- **Reuse, don't rebuild.** CDN publish (versioned URLs to beat edge cache), CI
  gates, chart primitives, and the FeaturePage pattern all exist in Off The Pace.
  New repo, imported habits.
- **Weekly cadence, not nightly.** Demand data lags a day or two and cap periods
  change quarterly; nightly buys nothing.

---

## 7. User flow

Designed for the cold LinkedIn visitor first, the technical interviewer second:

1. **Hero (zero setup).** One chart, pre-loaded: daily weather-adjusted gas demand
   through 2021–2024 with cap-reset markers, the Apr-2022 event highlighted, and the
   headline finding in one sentence with its CI. Works instantly, no key, no picker.
2. **"Why weather-adjusted?" toggle.** Flip between raw and adjusted demand. The raw
   series is visibly all winter; the adjusted one shows the behavioural signal. This
   single interaction teaches the whole methodological point in five seconds.
3. **Explore.** Pickers: fuel (gas/electricity), event (each cap reset, with its
   announced-vs-effective dates and % price change), region (stretch). Each event
   view shows the local-projection response path with its band, plus the placebo
   distribution as context.
4. **Counterfactual slider.** "Set the cap yourself": drag the price change (within
   the observed support, hard-capped — the UI refuses to extrapolate beyond the
   largest observed shock and says why), see estimated consumption response and
   typical-household spend as ribbons. Clearly labeled linear extrapolation.
5. **Methods page.** The identification assumption verbatim, the §5 limitations
   verbatim, sanity anchors vs literature, and a link to the repo. The assumption is
   *on the page* — the standing house rule.
6. **Stretch — equity view.** Prepayment vs direct-debit cap series diverge; even a
   descriptive view (who faced what price when) is a strong sustainable-development
   talking point without extra identification claims.

---

## 8. Build order

1. **Pipeline + verification** (week 1) — National Gas + NESO + Ofgem + HadCET pulls,
   Parquet export, `events.json`, hand-check known values. *Gate: known values match.*
2. **Weather model** (week 1–2) — spline HDD fit, held-out validation on pre-crisis
   winters. *Gate: out-of-sample fit is excellent or stop and fix.*
3. **Event study v1** (week 2–3) — national gas, clean events only, block-bootstrap
   bands, pooled elasticity. *Gate: signs right, elasticity in literature range.*
4. **Frontend v1** (week 3–4) — hero + raw/adjusted toggle + event explorer +
   counterfactual slider on precomputed JSON. Zero setup on first load.
5. **Robustness + electricity** (week 4–5) — placebos, leave-one-out, anticipation
   test, electricity contrast, Oct-2022-labeled view.
6. **Methods page + write-up** (week 5) — assumption, limitations, anchors; publish;
   LinkedIn post structured as question → method → band → caveat.
7. **Stretch** — regional/LDZ heterogeneity, prepayment equity view, payment-method
   splits (data already in the Parquet from step 1 by design).

Effort estimate: ~4–6 weeks part-time. Steps 1–4 are the shippable core; nothing
after step 4 blocks publishing.

---

## 9. What this demonstrates (interview / README framing)

- **Causal-inference discipline:** exogenous-by-formula price variation, an explicit
  stated assumption, placebo and robustness checks — Econometric Methods applied,
  not recited.
- **Honest uncertainty:** bootstrap bands on every claim including the interactive
  counterfactual.
- **Domain judgment:** knowing Oct 2022 is contaminated and saying so up front is
  worth more than any point estimate.
- **Production shipping:** weekly automated pipeline, CDN-published Parquet, client-
  side analytical UI, zero marginal cost — the Off The Pace engineering story
  transplanted to a domain UK employers (energy retail, trading, Ofgem/DESNZ, climate
  fintech, think tanks) can evaluate directly.
- **Degree integration:** Sustainable Development (energy demand, equity),
  Microeconomics (elasticities), Econometrics (event study, bootstrap) — built before
  or alongside the coursework so the coursework sharpens it.

The one-sentence pitch: *"I weather-adjusted four years of national gas demand and
estimated how much Britain actually cut back at each price-cap jump — with a stated
identification assumption and confidence bands, in a zero-backend browser tool."*

---

## 10. Explicit non-goals (v1)

- **Not a bill forecaster or tariff-comparison site** — no future cap predictions.
- **No household-level claims** — aggregate elasticities only, ecological caveat
  stated on the page.
- **No smart-meter microdata** — SERL accreditation is a v2-if-ever.
- **No supplier-level or switching analysis** — different question, different data.
- **No extrapolation beyond observed shocks** — the slider is clamped to the support
  of the data, and the UI says so rather than silently obliging.
- **No causal claim for Oct 2022** — shown, labeled contaminated, excluded from the
  headline pooled estimate.
