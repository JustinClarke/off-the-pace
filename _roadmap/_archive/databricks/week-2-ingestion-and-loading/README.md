# Week 2 — Data Ingestion & Loading 📥

**Theme:** land the raw corpus into bronze the Databricks way — Auto Loader, schema evolution, idempotent reloads.
**Exam domain:** Ingestion & Loading (**21%** — second-heaviest, and the most *new-in-2025* surface).
**Friday deliverable:** raw bronze landed via **Auto Loader** · a working **schema-evolution** demo · an
idempotent **COPY INTO** reload · the 12 `stg_*` re-pointed at bronze and **still parity-green**.

Honest framing: off-the-pace has **no live source** — raw files are reused as-is. So you *simulate*
ingestion by replaying static files through a landing zone. That's not a cheat — it's exactly the exam's
mental model (incremental file detection, schema inference/evolution, idempotency) without faking a feed.

---

## The 5-day rhythm

| Day | Vibe | Split | This week |
|---|---|---|---|
| [Mon](./monday.md) | Learn the *why* | 70% learn / 30% lab | Reading files + the Auto Loader idea |
| [Tue](./tuesday.md) | Learn by recreating | 50% learn / 50% build | Auto Loader stream + schema evolution |
| [Wed](./wednesday.md) | Build | 90% project | Bronze ingestion for real sources |
| [Thu](./thursday.md) | Build + make it shippable | 90% project | COPY INTO + re-point staging, re-prove parity |
| [Fri](./friday.md) | Review + exam reps + ship | 40 / 30 / 30 | Self-check, practice Qs, commit |

> 🧠 **ADHD note:** Ingestion is 21% of the exam and loves *decision-rule* questions
> (Auto Loader vs COPY INTO, which evolution mode). Each day ends with the decision rule stated in one
> line — collect those lines; they're half your exam score on this domain.

---

## Momentum tracker

- [ ] Mon — read a file 3 ways (infer vs StructType vs rescued)
- [ ] Tue — first Auto Loader stream runs, re-run skips ingested files
- [ ] Wed — bronze tables landed for the real sources
- [ ] Thu — COPY INTO idempotent + staging re-pointed, **parity still green** 🟢
- [ ] Fri — self-check done, practice Qs logged, branch pushed
