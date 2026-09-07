# Week 5 · Monday — Unity Catalog + book the exam 📅

⏱️ **~2.5 hrs** · 70% learn / 30% lab · **Domain:** Governance (15%)
🎯 **One-liner:** learn the UC object model + access control, and **lock in your exam date**.

> ▶️ **Start here (first 15 min):** open the **readiness gate** in the [week README](./README.md). If
> you're at ~75–80% on the Academy practice exam, **book the exam now** for end of Week 6. Date locked =
> brain calm. Do this *before* studying — it's the highest-leverage 15 minutes of the week.

---

## 🎯 If you only do one thing today
**Book the exam** (per the gate). Everything else today is learning you can finish in the buffer; the
booking is the one thing only Monday-you can set in motion.

## Parts (tick as you go)

### ⬜ Part 0 — Book it · ~15 min  *(logistics)*
- [ ] Confirm practice-exam score vs the gate → book for end of Week 6 (or +1–2 weeks if under). 📅

### ⬜ Part 1 — UC object model & access control · ~50 min  *(learn)*
- [ ] Docs: **"What is Unity Catalog?"**, **"Manage privileges in Unity Catalog"**, **"Capture and view data lineage"**.
- [ ] Notes: the **three-level namespace** `catalog.schema.table`; the privilege chain an analyst needs to
      `SELECT` a gold table (`USE CATALOG` → `USE SCHEMA` → `SELECT`); managed vs external in UC terms.

### ⬜ Part 2 — Grants + lineage lab · ~40 min  *(lab)*
- [ ] `GRANT SELECT` on the `gold` schema to a second read-only principal/group — model "analysts read
      gold, engineers write silver."
- [ ] Open the **lineage graph** for `fct_lap_residuals`; confirm it traces back through `int_*` to bronze.

## 🐍 You already know this
Privileges here are just **SQL `GRANT`/`REVOKE`** — same verbs you know from Postgres. The new idea is the
**extra namespace level** (you must be granted `USE` on the catalog *and* schema before `SELECT` on the
table matters — privileges chain top-down). Lineage is auto-captured; you just read the graph.

## 📚 Resources (pick ONE)
- Academy → Data Engineering path → "Data Governance with Unity Catalog" module.

## 🏁 Done when
- [ ] **Exam booked** (or consciously deferred per the gate). 📅
- [ ] `GRANT` applied to a second principal; lineage graph viewed.

## 🅿️ Park it
Tomorrow: row filters/column masks + the optimization toolkit (OPTIMIZE, Liquid Clustering). Timebox the
governance demos — they're "show + explain," not a big build.

## Notes & gotchas
-
