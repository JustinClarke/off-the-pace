# Career Project Shortlist — UK Job Market

> Candidate portfolio projects that pair the econ MSc (causal inference + policy + data)
> with the CS/engineering background (Off The Pace). Goal: one shipped project that shows
> **stated identification + honest uncertainty + production shipping** on a problem UK
> employers actually care about.

Degree modules these must map onto: Microeconomic Analysis with Data Applications ·
Data Analytics & ML for Economics · International Financial Markets · Macroeconomic
Policy & Data Analysis · Econometric Methods & Dissertation · Data & Policy Analysis
for Sustainable Development.

**Decision (2026-07-05): Project 1 (Energy) chosen for build.**
Detailed plan: [energy-price-cap-lab-plan.md](./energy-price-cap-lab-plan.md)

---

## 1. Energy Price Cap Lab ⭐ CHOSEN

- **Question:** When the Ofgem price cap jumps, how much do GB households actually cut
  gas/electricity consumption — and what would a different cap have done?
- **Identification:** Event study / interrupted time series at cap-reset dates (the cap
  changes discretely on known dates by known amounts, via a published mechanical
  formula). Weather-normalized daily demand. *Note: this is a temporal discontinuity —
  an event study, not a classic RDD; earlier framing of "RDD on the cap" was loose.*
- **Data:** All free and immediate — National Gas daily LDZ demand, NESO half-hourly
  electricity demand, Ofgem cap workbooks, Met Office temperature series. No scraping,
  no accreditation, no ToS risk.
- **Degree fit:** Sustainable Development + Micro + Econometrics.
- **Who hires for this:** Octopus/OVO/Centrica data teams, energy trading, Ofgem/DESNZ,
  climate fintech, think tanks (Resolution, IFS, NESTA), tech econ teams.
- **Why chosen:** Cleanest identification of the four, fastest path to shipped v1
  (public daily data), biggest employer surface, and the price cap is a permanently
  topical UK policy instrument.

## 2. Housing Supply Response to Planning Reform

- **Question:** Do planning liberalizations actually increase housing supply, and where
  would similar reforms bite hardest?
- **Identification:** Staggered diff-in-diff / synthetic control across local
  authorities; event studies around reform dates.
- **Data risk (the reason this lost):** ONS/EPC/planning data is public but messy and
  lagged; portal listing data (Rightmove/Zoopla) is **not** freely scrapable (ToS),
  and council planning records often need FOI. Data acquisition could eat half the
  project. Modern staggered-DiD estimators (Callaway–Sant'Anna etc.) also raise the
  econometric bar.
- **Degree fit:** Micro + Econometrics.
- **Who hires:** PropTech, mortgage fintech, every policy institution, consultancies.
- **Verdict:** Strongest policy topic, weakest data access. Good dissertation
  candidate later; wrong choice for a ship-in-weeks portfolio piece.

## 3. Transport Mode Shift after ULEZ Expansion

- **Question:** How did London's ULEZ expansion change travel behaviour, emissions,
  and who bore the cost?
- **Identification:** Genuinely spatial — boundary discontinuity designs (this one
  *is* RDD-shaped) + DiD around expansion dates.
- **Data:** TfL open data, DfT counts, air-quality sensors (all public, decent).
- **Degree fit:** Sustainable Development + Micro.
- **Who hires:** Mobility tech, TfL/DfT, tech econ teams, environmental consultancies.
- **Verdict:** Solid runner-up. Loses to energy on national relevance and on the
  cleanliness of the price variation (ULEZ effects entangle charge, signage,
  scrappage schemes, and publicity).

## 4. Macro Shock Lab (existing plan)

- Plan: [_misc/macro-shock-lab-plan.md](./_misc/macro-shock-lab-plan.md)
- **Question:** Does a BoE rate shock's estimated effect survive an honest
  identification strategy (SVAR / local projections vs a neural-net foil)?
- **Verdict:** Intellectually the sharpest thesis ("identification beats capacity"),
  but macro is the *worst* fit for early-career hiring (dominated by experienced
  central-bank economists), the July 30 predict-then-grade hook can't actually be
  graded on IRF timescales, and known small-VAR pathologies (price puzzle) risk the
  headline chart. Keep as a second project or BoE-application special; don't lead
  with it.

---

## Target-role mapping

| Target | Best evidence | Notes |
|---|---|---|
| Fintech / trading (research-eng hybrid) | Energy (1) | Real market, causal rigor, shipped tool |
| BoE / FCA / Treasury / Ofgem | Energy (1) or Macro (4) | Energy doubles as an Ofgem-relevant artifact |
| Tech econ teams (pricing, marketplaces) | Energy (1) or ULEZ (3) | "Identify cause/effect in messy observational data" |
| Think tanks / policy research | Any of 1–3 | Research quality > tool, but the tool differentiates |
| Pure SWE roles | Off The Pace | These projects don't replace it; they complement it |

## Common bar for whichever ships

1. Identification assumption stated **on the page**, not just the README.
2. Confidence bands, never a single confident line.
3. Zero-setup demo: a cold visitor sees a working chart with no API key.
4. A limitations section written before the results section.
5. Reuse the Off The Pace static stack (Parquet on CDN + DuckDB-Wasm + precomputed
   coefficients) — proven, zero-cost, and tells one continuous story.

---
---

# Data Engineering / Science Project Shortlist

> Candidate portfolio projects that fill gaps Off The Pace **doesn't** cover:
> streaming, cloud warehouses, orchestration, data quality/observability, and
> serving layers. Goal: one shipped project that demonstrates production data
> engineering skills beyond the batch/DuckDB/dbt surface already proven.

**Off The Pace already covers:** ingestion, dbt transforms, DuckDB, CI-enforced
invariants, ML (XGBoost → ONNX), browser-native serving, IaC (Terraform),
GitHub Actions CI/CD.

**Gaps to fill:**

| Gap | Why it matters | OTP status |
|---|---|---|
| Real-time / streaming | #1 thing interviewers test separately | 100% batch |
| Cloud warehouse at scale | Snowflake/BigQuery/Fabric experience | Local DuckDB only |
| Orchestration | Airflow/Dagster/Prefect | dbt via Make/CI, no scheduler |
| Data quality / observability | Schema contracts, monitoring | One dbt macro |
| Reverse ETL / serving layer | Data products feeding other systems | Browser Parquet only |

---

## 5. Schema Drift Detector & Contract Enforcer ⭐ RECOMMENDED

- **Problem:** Upstream data sources silently change schemas — columns renamed,
  types changed, new nullable fields appear. Pipelines break at 3am. Great
  Expectations checks *values*; Soda checks *freshness/volume*; Monte Carlo is
  enterprise-only. Nobody does **structural schema diffing against a declared
  contract** as a standalone OSS tool.
- **How it helps Off The Pace directly:** FastF1 and OpenF1 are external APIs
  that OTP doesn't control. FOM alters live timing feeds frequently. A schema
  change that renames `car_data.Speed` to `car_data.speed` silently breaks the
  5 XGBoost models (42 features) — either crashing the ONNX runtime or producing
  garbage predictions. dbt tests run *after* ingestion; this catches drift
  *before* it enters the warehouse.
- **Integration point:** Sits between the ingestion scripts and bronze Parquet:
  `Ingestion → Bronze Parquet → [Schema Drift Detector] → dbt pipeline`
- **Stack:** Python CLI + GitHub Action. Polls source schemas (APIs, Parquet
  headers, DB catalogs), diffs against a registered JSON Schema contract,
  blocks or alerts on violations. Ships as `pip install schema-sentinel` or
  similar.
- **Portfolio signal:** Data contracts, schema evolution, observability — hot
  topic, no good OSS exists for this specific problem.
- **Effort:** 1–2 weeks for a shippable v1.
- **Resume line:** *"Built an open-source schema contract enforcer that detects
  structural drift in upstream sources before it reaches the warehouse —
  protecting 5 downstream ML models from silent breakage."*
- **Ties the portfolio together:** OTP enforces invariants on transforms (the
  additive identity). This enforces contracts on *ingestion boundaries* — the
  part you don't control. Same philosophy, new domain.

---

## 6. Live Venue Capacity Intelligence (Kappa Architecture)

- **Concept:** A real-time spatial occupancy engine for Dubai mid-market venues.
  Ingests Wi-Fi probe logs, smart parking induction loops, and municipal transit
  tap webhooks via Redpanda/Kafka → Flink/Materialize for CEP → sub-500ms
  sliding-window occupancy analytics → staffing alerts dashboard.
- **Stack:** Redpanda, Apache Flink / Materialize SQL, DuckDB (historical OLAP),
  PostgreSQL + webhooks (real-time), React dashboard.
- **Market thesis:** Legacy venue analytics requires $50k+ hardware cameras.
  Government projects (Dubai Pulse) operate at macro urban-planning level,
  locked away from SMB operators. This is a pure-software layer on existing
  enterprise Wi-Fi infrastructure (Cisco Meraki/Aruba).
- **Portfolio signal:** Streaming, real-time aggregation, exactly-once semantics,
  Kappa architecture — the exact gap OTP doesn't cover.

### Honest viability assessment

> **Verdict: Legitimate product idea. Terrible portfolio project. Premature
> startup pitch.**

**What's real:**
- The market gap is real — mid-market Dubai venues genuinely lack affordable,
  real-time occupancy analytics.
- The architecture (Kappa, Redpanda, Flink) is technically sound and would
  demonstrate streaming skills impressively.
- Dubai's commercial real estate operators (MAF, Emaar) do over-staff based on
  gut feeling.

**What's not real (yet):**

1. **You have zero access to any of the three data streams.** Wi-Fi probe logs
   require a partnership with the venue's network vendor (Meraki dashboard API
   needs admin credentials). Parking induction loop data is proprietary to the
   parking operator (Parkin/Emaar). RTA transit tap webhooks don't exist as a
   public API — Dubai Pulse's open data is batched CSV dumps, not streaming
   webhooks. The entire architecture diagram assumes data access you don't have.

2. **Synthetic data doesn't prove anything.** You can build a beautiful Flink
   pipeline on fake sensor data, but no interviewer, VC, or customer will care.
   The hard part of this project isn't the Flink SQL — it's getting the data
   agreements signed. A portfolio project with simulated data proves you can
   write Flink DDL, which any tutorial also proves.

3. **The VC pitch is premature.** The manifesto reads well but requires:
   regulatory clarity on Wi-Fi probe privacy (UAE PDPL), a venue partner willing
   to pilot, and proof the Wi-Fi probe → occupancy correlation is actually
   accurate (it's notoriously noisy — MAC randomization on iOS/Android has
   degraded probe-based counting significantly since 2020).

4. **Scope is a startup, not a project.** This is a 6–12 month venture with
   business development, data partnerships, and regulatory work. Framing it as
   a portfolio project misrepresents what it takes to make it real.

**If you still want to do it:** Park it as a startup concept with its own repo.
Don't put it in the Off The Pace portfolio. Build the Schema Drift Detector
first (ships in weeks, integrates with OTP, demonstrates the same streaming
awareness without requiring data access you don't have), then revisit this
when you have a venue partner willing to share Wi-Fi logs.

---

## 7. Cost-Aware Query Planner / Warehouse Spend Auditor

- **Problem:** Data teams run BigQuery/Snowflake and have no idea which queries,
  dbt models, or dashboards cost the most. The cloud console shows total spend
  but not "this one model costs $47/day because of a fan-out join."
- **Stack:** Pull query logs from `INFORMATION_SCHEMA.JOBS` (BigQuery) or
  `QUERY_HISTORY` (Snowflake) → model cost attribution per dbt model/dashboard
  → surface top money-burning queries with suggested rewrites.
- **Portfolio signal:** Cloud warehouse internals, cost optimization, query
  profiling — stuff senior data engineers do daily.
- **Blocker:** Requires an active BigQuery/Snowflake account with real query
  volume to be credible. Can't demo on an empty warehouse. Also overlaps with
  emerging tools (SELECT.dev for Snowflake, BigQuery slot estimator).
- **Verdict:** Good idea, wrong timing. Build this when you're employed and have
  access to a real warehouse with real spend.

---

## Data engineering target-role mapping

| Target | Best evidence | Notes |
|---|---|---|
| Data engineer (mid-level) | Schema Drift (5) + OTP | Contracts + streaming awareness + dbt mastery |
| Analytics engineer | OTP + Schema Drift (5) | dbt spine + quality enforcement |
| ML engineer / MLOps | OTP (ML layer) + Schema Drift (5) | Model protection from upstream drift |
| Streaming / real-time roles | Venue Intelligence (6) | Only if built with real data, not synthetic |
| Senior / staff DE | Cost Auditor (7) | Requires real warehouse access |

## Recommended build order

1. **Schema Drift Detector (5)** — ships in 1–2 weeks, integrates with OTP,
   fills the data quality gap, OSS-releasable, interview-ready.
2. **Energy Price Cap Lab (1)** — already chosen, ships the econ/policy story.
3. **Venue Intelligence (6)** — only after securing a data partner; park as a
   concept until then.
4. **Cost Auditor (7)** — build on an employer's warehouse, not your own dime.
