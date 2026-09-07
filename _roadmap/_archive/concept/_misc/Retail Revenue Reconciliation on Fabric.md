# Retail Revenue Reconciliation on Fabric — DP-700 Portfolio Project

> **Purpose:** A single, tightly-scoped project that doubles as DP-700 (Microsoft Fabric
> Data Engineer Associate) exam prep and closes the one real gap in the Off The Pace
> portfolio — everything to date is local (DuckDB / DuckDB-Wasm / Firebase); this puts
> dbt on a **cloud warehouse** with **real orchestration**.
>
> **Failure mode to guard against:** grandiose scope (see `Neuro-Symbolic Data Plane.md`).
> This plan is deliberately small. Ship the MVP, write an honest README, move on.

---

## Cert decision: DP-700 (not Databricks — for now)

- **DP-700 compounds; Databricks restarts.** Existing production Microsoft Fabric experience
  (VNS) + PL-300 incoming + DP-700 = one legible story: *"Microsoft Fabric data engineer."*
  Databricks ignores that edge and drops you into a pool with real Spark production experience.
- **Market fit.** UAE enterprise / Big 4 / banks are Microsoft-heavy. DP-700 keyword-matches
  the thickest demand. Databricks is thinner/more competitive here (mostly Abu Dhabi / G42).
- **Speed.** Faster to a *coherent* candidate because it sits on skills already in hand.
- **Sequence:** DP-700 now → get employed → Databricks as the level-up on someone else's payroll.

---

## Core idea

Messy multi-source retail sales data (POS exports + an ERP/ledger feed + refunds) that
**don't tie out** — and a pipeline that ingests, reconciles, and **fails the build** if the
books don't balance.

**Why retail (not pure finance):** authentic to the VNS story (retail / F&B / e-commerce
clients), maps to the biggest UAE retail employers (Majid Al Futtaim, Landmark), and keeps the
mathematical-invariant flavour that is the Off The Pace signature move. Interview line:
*"I did this reconciliation for retail clients at VNS — so I built the cloud-native, tested version."*

> Swap-in: re-skin as bank/finance double-entry (`∑debits − ∑credits = 0`) if specifically
> targeting DIFC / banks. Same architecture, different employer base.

---

## Stack — each layer is a DP-700 objective AND a resume keyword

| Layer | Tool | DP-700 domain | Why it impresses |
|---|---|---|---|
| Ingest | Fabric Data Pipeline + a PySpark notebook pulling messy POS/ERP CSVs into a Lakehouse | Ingest & transform | Orchestrated + idempotent, not a laptop notebook |
| Transform | **dbt (dbt-fabric adapter)** on a Fabric Warehouse | Transform | dbt-on-Fabric = modern-stack cred + enterprise cred in one |
| Contract | Invariant `gross_sales − refunds − discounts = net_revenue`, and net_revenue ties to the ledger, enforced as a **dbt test that fails the build** | Monitor & manage | The Off The Pace "CI-enforced invariant", now on cloud |
| Orchestrate | Fabric pipeline on a schedule, incremental load | Implement & manage pipelines | Runs on its own, handles late-arriving refunds |
| Serve | Power BI Direct Lake semantic model with a reconciliation-status KPI | (ties in PL-300) | Closes the loop to a stakeholder-facing output |
| CI/CD | GitHub Actions: `dbt build` against Fabric on every PR | Secure & monitor | The line that makes an engineer nod |

**Neutralises the "Fabric isn't real engineering" snobbery:** dbt + CI is the spine; Fabric is
the deployment surface.

---

## MVP definition (the whole project)

One messy source → Lakehouse → dbt on Fabric Warehouse → one failing-then-passing
reconciliation invariant → one Power BI page → green CI. **That's it.**

### Anti-scope-creep guardrails — do NOT add:
- ❌ ML / an agent / LLM anything
- ❌ a second domain
- ❌ real-time streaming
- ❌ a custom frontend
- ❌ "mathematically proven / cannot fail" language anywhere

The README must be the **opposite** of the Neuro-Symbolic tone: measured, bounded, true.
> *"Reconciles 50k POS rows against the ledger; build fails on any imbalance > AED 0.01"*
> beats any superlative — knowing the limits is the seniority signal.

---

## 4-week timeline (part-time, alongside the channel/outreach work)

- **Week 1 — Ingest.** Provision Fabric trial. Build ingest pipeline + Lakehouse (DP-700:
  ingest). Study the matching exam module the same evening. *Don't touch dbt yet.*
- **Week 2 — Transform + invariant.** Wire dbt-fabric, port a reconciliation model, make the
  invariant test **fail** on bad data, then fix the model so it passes (DP-700: transform/monitor).
- **Week 3 — Orchestrate + serve + CI.** Schedule + incrementalize the pipeline, add GitHub
  Actions CI, Power BI Direct Lake page (DP-700: orchestrate/secure + PL-300). Practice exam.
- **Week 4 — Ship + certify.** Honest README + 90-second Loom. **Sit DP-700.** Update resume +
  LinkedIn.

> The cert/project is the background process; the recruiter outreach + one-lane resume is what
> actually produces interviews. Run them in parallel.

---

## Deliverables

**Resume bullet (analytics-engineer lane):**
> Built a cloud-native retail revenue reconciliation pipeline on Microsoft Fabric — PySpark
> ingestion into a Lakehouse, dbt-on-Fabric Warehouse transforms, and a CI-enforced double-entry
> invariant (`gross − refunds − discounts = net`) that fails the build on any imbalance — served
> to a Power BI Direct Lake model. *Microsoft Fabric, dbt, PySpark, Power BI, GitHub Actions.*

**LinkedIn / DM one-liner:**
> Microsoft Fabric data engineer (DP-700, PL-300) — dbt, cloud reconciliation pipelines,
> CI-tested data contracts. Dubai, family visa, available now.

---

## Why this is the right project

- **Closes the one real gap** — dbt on a real cloud warehouse with real orchestration.
- **Reuses proven strengths** — dbt, invariant-as-test, CI gating (ports Off The Pace rigour onto cloud infra).
- **Reinforces three credentials at once** — DP-700 (the build), PL-300 (the Power BI layer), dbt (the spine).
- **Authentic interview narrative** — bridges directly to VNS retail reconciliation experience.

---

## Next step

Repo skeleton: folder layout, dbt-fabric `profiles.yml`, the reconciliation model + the failing
test, and the GitHub Actions workflow — so Week 1 starts from a running scaffold, not a blank page.
