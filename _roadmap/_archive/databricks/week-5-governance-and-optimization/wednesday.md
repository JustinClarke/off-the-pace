# Week 5 · Wednesday — Govern gold + cluster the big marts

⏱️ **~3 hrs** · 90% build · **Build day** 🔨
🎯 **One-liner:** organise the rebuild cleanly under Unity Catalog and make the biggest marts measurably
faster with OPTIMIZE + Liquid Clustering.

> ▶️ **Start here (first 15 min):** pick the single biggest mart (`fct_lap_residuals` or
> `fct_telemetry_deltas`), note its current `numFiles` (`DESCRIBE DETAIL`) and time one representative
> query. That's your "before" — you'll beat it by lunch.

---

## 🎯 If you only do one thing today
`OPTIMIZE` + `CLUSTER BY` **one** big mart and capture a **before/after** file-count and query-time
comparison. That measured win is the day's deliverable (and a great portfolio screenshot).

## Parts (tick as you go)

### ⬜ Part 1 — Govern the gold schema · ~1 hr  *(build, timeboxed)*
- [ ] Confirm the clean UC layout: `otp_spark.{bronze,staging,silver,gold}`.
- [ ] Apply the Monday/Tuesday governance for real on `gold`: `GRANT SELECT` to the read-only group +
      one **row filter** + one **column mask**. Keep it tight — demo, not a project.

### ⬜ Part 2 — Optimize the big marts · ~1.25 hrs  *(build)*
For `fct_lap_residuals`, `fct_telemetry_deltas`, `mart_degradation_history_envelope`:
- [ ] `OPTIMIZE` (compaction) → `CLUSTER BY` the columns you join/filter on most (`race_id`, `driver_id`).
- [ ] Compare **file counts + a representative query's runtime** in the Spark UI, before vs after.

### ⬜ Part 3 — Note the ZORDER framing · ~30 min  *(production engineering)*
- [ ] In notes: where `ZORDER` *would* have been the pre-2025 answer, and why Liquid Clustering replaces it.
      The exam may phrase the same question either way — be ready for both.

## 🐍 You already know this
Clustering is just **co-locating rows you query together** so Spark reads fewer files — the same instinct
behind a database index, but layout-based. You already know *which* columns you filter on (you wrote every
query); that knowledge *is* the clustering decision.

## 📚 Resources
- None. Tables + Spark UI open, docs closed.

## 🏁 Done when
- [ ] Gold governed (grant + row filter + column mask).
- [ ] ≥1 big mart shows a real before/after improvement (fewer files and/or faster query).

## 🅿️ Park it
**Tomorrow is the fun one** — the float-drift detective story, the headline learning artefact of the whole
rebuild. Bring your best focus. Note which mart had the widest shuffle (a good candidate to investigate).

## Notes & gotchas
-
