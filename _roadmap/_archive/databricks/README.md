# Databricks Data Engineer Associate — 6-Week Learning Plan

> **Goal:** pass the **Databricks Certified Data Engineer Associate** exam, and reinforce
> the skills by rebuilding the off-the-pace transform layer from scratch on Databricks
> (Lakehouse + Delta + Lakeflow). Same app layer, brand-new marts.
>
> This folder is the **week-by-week execution** of the design/contract doc
> [`../_wip/SPARK_REBUILD_PLAN.md`](../_wip/SPARK_REBUILD_PLAN.md). That doc owns the
> "what & why" (the app/ML contract, the parity gate, the non-goals). These files own
> the "learn it → build it" schedule.

---

## How this plan is structured

Every concept follows the same three-part rhythm:

| Part | What it means |
|---|---|
| 🎯 **Learning outcome** | The exam-relevant capability. "By the end I can…" — written so you can test yourself against it. |
| 📚 **Learn it** | Watch + read. Specific Academy courses, docs pages, and videos. Do this *before* touching the project. |
| 🔨 **Build it** | Apply it immediately by building a real slice of the off-the-pace rebuild. Concrete tables/files named. |

The loop is deliberate: **learn the abstraction → cement it by shipping a real artefact** you
already understand from the dbt-duckdb version. You're not learning Spark on toy data — you're
re-deriving a system you designed, which is the fastest way to make the concepts stick for the exam.

---

## The exam (source of truth)

- **Cert page:** <https://www.databricks.com/learn/certification/data-engineer-associate>
- **Exam Guide PDF (read this first, it is authoritative — version July 25 2025):**
  <https://www.databricks.com/sites/default/files/2025-11/databricks-certified-data-engineer-associate-exam-guide-july-25-2025-04.pdf>
- **Format:** 45 multiple-choice questions, 90 minutes, no notes, proctored online. Pass mark ~70%.
- **Cost:** USD $200 (one free retake is *not* included — budget for a possible resit).
- **2025 emphasis (new vs older dumps):** Lakeflow Declarative Pipelines (the rebrand of DLT),
  Auto Loader, Unity Catalog, Delta Sharing / Lakehouse Federation, Databricks Asset Bundles (DAB),
  **Liquid Clustering** (now preferred over `ZORDER`), and more **scenario-based** questions.
  ⚠️ Ignore pre-2025 dumps that test the old "Workflows/DLT" naming and SQL warehouse trivia.

### Domain weights → week map

| Domain | Weight | Covered in |
|---|---|---|
| Data Transformation & Modeling | 22% | **Week 3** (+ Week 1 Delta foundations) |
| Data Ingestion & Loading | 21% | **Week 2** |
| Working with Lakeflow Jobs / pipelines | 16% | **Week 4** |
| Governance & Security (Unity Catalog) | 15% | **Week 5** |
| Implementing CI/CD | 10% | **Week 6** |
| Troubleshooting, Monitoring & Optimization | 10% | **Week 5** |
| Databricks Intelligence Platform basics | 6% | **Week 1** |

---

## The environment: Databricks Free Edition

Use **Databricks Free Edition** (it replaced Community Edition, which is being retired). It is
serverless-only and quota-limited but ships the exact features the exam tests — **Unity Catalog,
Lakeflow Declarative Pipelines, Jobs, Auto Loader, MLflow** — so you can practise every domain
for free.

- **Sign up:** <https://docs.databricks.com/aws/en/getting-started/free-edition>
- No cluster management (serverless), so you can ignore the old "cluster sizing" UI trivia and
  focus on query plans / partitions in the Spark UI.
- **Caveat for this project:** the ~6 GB bronze corpus is large for Free Edition quotas. Land a
  **subset of seasons** (e.g. 2023–2024) into a Volume for day-to-day build/iteration, and keep the
  full-corpus parity run for a single end-of-project batch. See Week 1, Build step 2.

> If Free Edition quotas become a wall, the fallback is **local single-node Spark**
> (`pip install pyspark`, `spark-submit`) for Transformation/Modeling practice — but you lose
> Lakeflow Jobs, Unity Catalog, and DAB, which are 41% of the exam. Prefer Free Edition.

---

## The build contract (do not break it)

The whole rebuild is safe because the **app and ML layers never change**. They read parquet from
four exported paths. As long as Spark writes the same paths / table names / column types, nothing
downstream needs to know it switched engines. Full detail in
[`SPARK_REBUILD_PLAN.md` §1](../_wip/SPARK_REBUILD_PLAN.md).

```
data/dimensions/     ← dim_*   (4 reference models)
data/facts/          ← fct_*   (7 marts)
data/intermediates/  ← int_*   (exported subset of 34)
data/marts/          ← mart_*  (2 marts) + dim_events
```

**60 models total:** 12 staging · 4 reference · 34 intermediate · 10 marts.
Every "Build it" step ports a named slice of these. The full inventory lives in each week file.

---

## Calendar (suggested — adjust to your pace)

| Week | Dates (w/c Mon) | Theme | Exam domains | Build milestone |
|---|---|---|---|---|
| [1](./week-1-platform-and-delta-foundations/) | Jun 30 – Jul 6 | Platform + Delta Lake foundations | Platform 6%, Delta basics | Workspace live; 12 `stg_*` ported; parity harness proven |
| [2](./week-2-ingestion-and-loading/) | Jul 7 – Jul 13 | Ingestion & Loading | Ingestion 21% | Bronze via Auto Loader; schema-evolution demo |
| [3](./week-3-transformation-and-modeling/) | Jul 14 – Jul 20 | Transformation & Modeling | Transform 22% | 4 `dim_*` + 34 `int_*` + 10 marts in Spark |
| [4](./week-4-lakeflow-pipelines-and-jobs/) | Jul 21 – Jul 27 | Lakeflow pipelines + Jobs | Lakeflow 16% | Medallion DLT pipeline; 7-stage Job DAG |
| [5](./week-5-governance-and-optimization/) | Jul 28 – Aug 3 | Governance + Optimization | UC 15%, Troubleshoot 10% | UC grants/row-filters; OPTIMIZE+Liquid Clustering; drift incident replay |
| [6](./week-6-cicd-parity-and-exam/) | Aug 4 – Aug 10 | CI/CD + parity + exam | CI/CD 10% + full review | DAB deploy; full 60-model parity gate; **sit the exam** |

Each week is a **folder** with one `README.md` (week overview + momentum tracker) and five day files
(`monday.md` … `friday.md`). The day file is the unit of work — open today's, follow the parts, stop at "Done when."

**Target exam date:** end of Week 6 (≈ Aug 11–14 2026), booked at the start of Week 5 so it's locked in.

---

## Weekly operating rhythm (the same five days, every week)

The theme changes weekly; **the rhythm never does**. Consistency is the point — same shape every week so
you build momentum instead of re-learning how to study. Each day file follows this:

| Day | Goal | Split |
|---|---|---|
| **Monday** | Learn the *why* | 70% learn / 30% small lab |
| **Tuesday** | Learn by recreating | 50% learn / 50% build |
| **Wednesday** | Build Off The Pace | 90% project |
| **Thursday** | Build + make it shippable | 90% project |
| **Friday** | Review + exam reps + ship | 40% review / 30% practice Qs / 30% cleanup |

**Sat** = buffer/spillover (Week 3's 48 models *will* use it — that's expected). **Sun** = rest.

Every Friday you should be able to point at something tangible and say *"this is now part of the rebuilt
platform"* — and you'll have drilled real exam questions on that week's domain while it's fresh.

### 🧠 How to use this if your brain is like mine (ADHD-friendly by design)

Every day file has the same five anchors so you never face a blank page:

- **▶️ Start here (first 15 min)** — a tiny, concrete task to beat activation energy. Just do that one thing; momentum follows.
- **🎯 If you only do one thing today** — the minimum-viable day for low-fuel days. Doing only this still counts as a win.
- **Timeboxed parts with checkboxes** — small dopamine hits, and a guard against rabbit-holing. *Pick ONE resource per part; don't binge the docs.*
- **🏁 Done when** — a clean *stop* signal so work doesn't sprawl into the evening.
- **🅿️ Park it** — one line to tomorrow-you, so context-switching doesn't lose your place.

Permission slip: you do **not** need to read every doc or finish every model on time. Parity-clean and
exam-ready are the only real targets. Falling behind → port one representative model per cluster and move on.

### Practice questions (the #1 predictor of passing — don't skip Fridays)

Use the **Databricks Academy practice exam** (free, official) + one third-party bank, but always reconcile
answers against the official Exam Guide PDF — third-party banks lag the July 2025 update. For every wrong
answer, write one line on *why* Databricks wanted the right one; the distractor pattern is the real lesson.

### 🚦 Readiness gate (book to a score, not a date)

Book the exam in **Week 5 (Monday)** for end of Week 6 — **only if** you're hitting **≥75–80% on the
official Academy practice exam**. Below that? Book it 1–2 weeks later and protect the buffer. A locked date
gives the final week a real deadline; a *premature* date just adds dread. You can always sit it sooner.

---

## Progress tracker

> Per repo convention, status lives **in these plan docs**, not in auto-memory. Update this table
> as you go.

| Week | Learn ✅ | Build ✅ | Self-check score | Notes |
|---|---|---|---|---|
| 1 | ☐ | ☐ | | |
| 2 | ☐ | ☐ | | |
| 3 | ☐ | ☐ | | |
| 4 | ☐ | ☐ | | |
| 5 | ☐ | ☐ | | |
| 6 | ☐ | ☐ | | |
| **Exam** | | | **booked: ☐  passed: ☐** | |

---

## Anchor resources (referenced throughout)

- **Databricks Academy** (official, free self-paced): <https://www.databricks.com/learn/training/home>
  → take the **"Data Engineer Learning Plan" / "Data Engineering with Databricks"** path. Its modules
  line up almost 1:1 with these six weeks.
- **Official docs:** <https://docs.databricks.com> — navigate by topic name (deep links rot across
  the aws/azure/gcp variants; each week names the *page title* to search).
- **Databricks YouTube:** <https://www.youtube.com/@Databricks> — plus search
  *"Databricks Certified Data Engineer Associate full course"* for several free 3–8 h walkthroughs
  (pick one published **after Aug 2025** so it covers Lakeflow/DAB).
- **Exam Guide PDF** (linked above) — re-read the relevant domain section every Saturday.
