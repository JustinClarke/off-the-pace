# 06 — Publication track

**Group:** 06 · **Depends on:** nothing · ***parallel*** — neither blocks nor is blocked by 01–05

Findings written for an external audience. The programme's other items ask "how good are our
models"; this one asks "what can this warehouse say that a team cannot say for itself".

## Positioning, which determines what is worth writing

A team has deep telemetry on its own two cars and only **public data on the other eighteen** —
the same data this warehouse holds. So competitor-facing findings are where a public-data
project is near the frontier, and own-model accuracy metrics are where it is hopelessly behind.

What travels: **a number, the identification strategy behind it, the error bar, and one
sentence on what would falsify it.** What does not: driver rankings without uncertainty, and
"my model achieved X".

Every item below must ship with its limitations stated in the post itself, not in a reply.

---

## 06a — The pit-timing tail

**Objective.** Publish the distribution, not the average.

**Verified 2026-09-07** from `int_pit_strategy_value` (7,129 stints): **median opportunity cost
0.0 s, mean 10.15 s.** Teams hit the tyre-optimal pit lap most of the time; all the lost time
sits in a tail. By constructor (n > 150), mean seconds lost per stint: Ferrari 7.32, Red Bull
9.00, Alpine 9.09, Aston Martin 9.93, Haas 10.05, Renault 10.11, McLaren 10.15, Racing Point
10.30, Alfa Romeo 10.37, Mercedes 10.62, AlphaTauri 10.79, Toro Rosso 12.36, Williams 12.53,
Alfa Romeo Racing 12.71.

**The finding is the nuance, not the ranking.** `int_pit_strategy_value` scores the pit lap
against the **tyre** optimum — its own header says "counterfactual cost calculation, not causal
inference". So a team that scores well here and is still criticised publicly is not making
tyre-modelling errors; it is making race-context errors — reacting to rivals, safety-car calls.
**That separates two failure modes that outside commentary conflates**, and it is the reason a
strategist would read it.

**Required caveats in the post.** No track-position or undercut dynamics; SC/VSC not modelled
as a decision input; the optimum is an argmin over a modelled cost surface, so it inherits that
model's assumptions.

**Definition of done.** Post drafted with the distribution as the headline, the tyre-vs-context
distinction stated, per-constructor n shown, and the caveats above in the body.

---

## 06b — Dirty air per season · the 2022 regulation question

**Objective.** Convert an assumption into a measurement.

**Verified 2026-09-07.** `int_dirty_air_tax_component` calibrates a **single global θ_air** and
applies `dirty_air_tax_s = CLAMP(θ_air × dirty_air_share_lag1, 0, 5.0)`. Output confirms it:
the tax at a given following intensity is identical in 2018 and 2024. **The model currently
assumes the cost of following never changed**, so as built it cannot answer the question at
all.

Also verified, and interesting on its own: mean following intensity rose from 0.197 (2018) to
0.237 (2024). Cars spend *more* of each lap in dirty air now, not less.

**Method.** Refit θ per season, keeping the existing lagged identification (prior-lap position
→ current-lap cost) that the model already uses to keep the causal arrow the right way round.
Then per era × corner-type using `dim_corners`, since the heterogeneity is the real finding —
the regulations were sold as a uniform improvement.

**Required caveat.** 2022 bundles the aero change with 18-inch tyres and porpoising. The
defensible claim is about the **bundle**; corner-geometry heterogeneity is what moves it toward
mechanism.

**Definition of done.** Per-season θ with confidence intervals; the corner-type breakdown; the
bundled-treatment caveat stated in the post; and the warehouse model either updated or a
written decision to keep the global θ in production and publish the per-season fit separately.

---

## 06c — Corner-phase skill

**Objective.** Publish the phase decomposition, and publish the anomaly.

**Verified 2026-09-07** from `mart_corner_skill_driver` (139 driver-seasons with a populated
index). 2024 leader **NOR at index −3.22, and it is nearly all exit** (exit −0.275 s vs braking
−0.041 s). "Norris's 2024 edge was traction, not braking" is specific and checkable.

**The anomaly, which is the more valuable half.** VER shows braking **+0.076 (weak)** and
mid-corner −0.078 (strong), against near-universal received wisdom about his braking. The
baseline is leave-one-race-out over same-car drivers, so for 2024 it is measured against PER.
**Post it as an open question, not a finding** — it is either something real or a baseline bug,
and working that out in public is worth more than another leaderboard.

**Required caveats.** The index is a sum of z-scores over winsorized (driver, race, corner)
cells with a `PHASE_MIN_CELLS = 30` floor; only 139 driver-seasons clear it; and the baseline
is teammate-relative, so a driver with a weak teammate and a driver with a strong one are not
on the same scale.

**Definition of done.** Post drafted with the phase split, the cell counts and SEs shown, the
teammate-relative baseline stated plainly, and the VER anomaly framed as an open question with
the two candidate explanations named.
