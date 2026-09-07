# Macro Shock Lab — Project Plan

> **Does the claimed effect survive an honest identification strategy?**

A browser-native tool that turns a policy shock ("what if the BoE hikes 25bps") into a
properly identified impulse response — with real confidence bands, not a confident
single line — and, as a labeled side-by-side, shows what a black-box neural net would
have told you instead. The gap between the two *is* the point.

---

## 1. The thesis

Most "what if the Fed/BoE does X" content on the internet shows a single, falsely
precise prediction line. That's not because the economics is that clean — it's because
nobody shows their identification assumptions or their uncertainty.

This project does the opposite: pick a real monetary policy shock, state the
identification assumption explicitly, estimate a proper impulse response with
bootstrapped confidence bands, and put a naive neural net's confident point-estimate
right next to it. The takeaway: **more model capacity doesn't fix an identification
problem.** That's the whole pitch, in one chart.

---

## 2. Why this project (and not the neural-net-only version)

The tempting version of this project trains a "physics-informed" neural net with an
accounting-identity loss term (`Y = C + I + G + NX`) and calls it done. Two problems:

1. **The identity isn't a law.** `Y = C + I + G + NX` is true by definition of how GDP
   is measured — enforcing it keeps your bookkeeping consistent, it doesn't make your
   predictions causally correct.
2. **It skips the actual hard problem.** The reason "does raising rates lower GDP" is
   hard isn't arithmetic — it's that central banks set rates *in response to* expected
   inflation and growth. A naive regression is contaminated by reverse causality
   (endogeneity). Solving that is what an identification strategy is *for*, and no
   amount of loss-function cleverness substitutes for one.

So: build the identified econometric model as the primary, rigorous artifact. Keep the
neural net — but demoted to an explicit, labeled foil that demonstrates why
identification beats capacity.

**Bonus:** because the primary model (SVAR / Local Projections) is linear, impulse
responses scale linearly with shock size. That means the "instant slider" demo needs
*no* ONNX/PyTorch inference at run time — just `response = coefficient × shock_size`,
computed client-side in JS or a DuckDB query. Simpler to build, genuinely deterministic,
and honest about uncertainty.

---

## 3. Architecture

```
┌────────────────────── Offline (one-time / periodic) ──────────────────────┐
│                                                                            │
│  FRED / DBnomics / BoE ──► Nightly GitHub Actions ──► Clean Parquet       │
│  (FEDFUNDS, CPI, GDP,           (seasonal adjustment,                     │
│   BoE Bank Rate, ONS data)       HP/Hamilton filter)                      │
│                                        │                                  │
│                                        ▼                                  │
│                          ┌─────────────────────────┐                     │
│                          │  Identified SVAR /       │                     │
│                          │  Local Projections       │  ← stated           │
│                          │  (Python/statsmodels)    │    identification   │
│                          └────────────┬────────────┘    assumption        │
│                                       │                                    │
│                          ┌────────────┴────────────┐                     │
│                          ▼                          ▼                     │
│              IRF coefficients +          Naive neural net                 │
│              bootstrapped CIs            (labeled "no identification,     │
│              (static JSON/Parquet)        for contrast only")            │
│                          │                          │                     │
└──────────────────────────┼──────────────────────────┼─────────────────────┘
                           │                          │
┌──────────────────────────▼──────────────────────────▼─────────────────────┐
│                     Browser (React + DuckDB-Wasm, zero backend)          │
│                                                                            │
│  Slider: shock size ──► linear scaling of precomputed IRF ──► chart      │
│  (works with zero setup, no API key required)                            │
│                                                                            │
│  Optional: "type your hypothesis" ──► LLM parses to shock params         │
│  (clearly labeled as calling out to an edge endpoint — not client-side,  │
│   requires user's own API key, gated behind a toggle, not the default)   │
└────────────────────────────────────────────────────────────────────────────┘
```

**Key correction from the earlier draft:** the LLM call is a real network round-trip to
remote infrastructure. It is not client-side compute and shouldn't be diagrammed as such.
Label it honestly. Sliders must work with zero setup on first load — gating the whole
demo behind "bring your own API key" kills a cold LinkedIn visitor before they see
anything.

---

## 4. The identification strategy (pick one to start)

Simplest defensible option for a v1, in order of effort:

1. **Recursive / Cholesky ordering** on a small VAR (e.g., `[GDP, CPI, Bank Rate]`,
   ordered so that Bank Rate reacts contemporaneously to GDP/CPI but GDP/CPI only react
   to Bank Rate with a lag). Standard, well-documented, easy to defend, easy to caveat.
2. **Local Projections (Jordà 2005)** as a robustness check — one OLS regression per
   horizon, less parametric than a VAR, easier to explain, naturally supports
   heteroskedasticity-robust or bootstrapped confidence bands.
3. **Stretch: narrative or high-frequency shocks** (Romer-Romer style, or identifying
   the shock component of a rate move around the announcement window) if time allows —
   this is the "gold standard" but meaningfully more data-engineering-heavy.

Whichever is chosen, **state the assumption on the page, not just in the README** —
mirrors the "explicit limitations section" habit from Off The Pace.

---

## 5. Data pipeline

| Source | Series | Purpose |
|---|---|---|
| FRED | `FEDFUNDS`, `GDPC1`, `CPIAUCSNS`, `PCOILWTICO` | US baseline system |
| Bank of England | Bank Rate, MPC decision dates | UK primary shock series |
| ONS / DBnomics | UK CPI, UK GDP, UK unemployment | UK response variables |
| DBnomics | ECB deposit rate, OECD composites | Cross-country comparison |

- Nightly (or weekly — no need for nightly precision on macro series) GitHub Actions
  pull → clean → seasonally adjust (HP or Hamilton filter via `statsmodels.tsa.filters`)
  → write compressed Parquet to the static asset repo.
- Re-estimate the SVAR/LP coefficients on a slower cadence (e.g., after each new BoE
  print) rather than per-request — these are stable structural estimates, not
  live-serving predictions.

---

## 6. UK-specific hook: the July 30 BoE decision

The next Bank of England MPC decision, with a full Monetary Policy Report, is
**30 July 2026**. Live context as of writing: the last vote was 7–2 to hold at 3.75%,
with two members dissenting in favor of a hike to 4.00%, against services inflation
running at 3.7% (above the 2% target). This is a genuine, current, undecided question —
not a settled backdrop.

**Suggested cadence:**
1. Publish the tool with the identified UK impulse response *before* 30 July, including
   the model's confidence band for a hold vs. a 25bp hike scenario.
2. Short follow-up post after the decision: did the realized data fall inside the
   band? Was the neural net foil more or less wrong than the identified model?

This mirrors a predict-then-grade structure — a real deadline, not a static demo,
and directly reuses the "measure against a baseline, don't trust the demo" instinct
already established across the portfolio.

---

## 7. Build order

1. **Data pipeline** — FRED + BoE + ONS ingestion, cleaning, seasonal adjustment,
   Parquet export. Manually verify a handful of known historical values.
2. **Identified model v1** — small Cholesky-ordered VAR on UK data (Bank Rate, CPI,
   GDP). Compute IRFs + bootstrapped confidence bands offline. Sanity-check signs
   against known macro theory (a rate hike should, with a lag, dampen inflation and
   growth — if it doesn't, something's wrong before anything ships).
3. **Frontend v1** — static chart of the precomputed IRF with a shock-size slider doing
   linear scaling client-side. No backend, no API key required to see it work.
4. **Neural net foil** — small PyTorch net with the accounting-identity soft
   constraint, exported to ONNX, shown side-by-side with a clear label explaining what
   it does and doesn't prove.
5. **Local Projections robustness check** — second identification method, shown as a
   toggle ("VAR vs. Local Projections") to demonstrate the result isn't an artifact of
   one specific method.
6. **Optional: NL hypothesis parser** — LLM-backed, gated behind an explicit toggle and
   the user's own key, clearly diagrammed as a network call rather than "client-side."
7. **Publish before 30 July** — write up the identification assumption, the limitations,
   and the prediction. Post. Follow up after the decision.

---

## 8. What this demonstrates (for interviews / the README)

- Real causal-inference discipline: a stated identification assumption, not just a
  regression.
- Honest uncertainty: confidence bands, not a single confident line.
- A clear, defensible reason for *not* over-trusting a flashier ML approach — using the
  neural net as a labeled contrast rather than pretending it's the main result.
- A genuinely client-side, zero-cost architecture, with an honest line drawn around
  what actually is and isn't running in the browser.
- Direct overlap with Macroeconomic Policy and Data Analysis and Econometric Methods —
  built *before* the coursework, so the coursework sharpens it rather than starting it
  from zero.

---

## 9. Explicit non-goals (v1)

- No claim of forecasting real-world outcomes precisely — this is a shock-response
  estimation tool, not a prediction market.
- No production-grade multi-country DSGE model — three or four well-chosen series,
  done rigorously, beats twenty series done shallowly.
- No pretending the neural net foil is state-of-the-art economics ML — it's a teaching
  contrast, and the README should say so plainly.
