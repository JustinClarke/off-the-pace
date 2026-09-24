# 06c Corner-Phase Skill — Findings Summary

**Rewritten 2026-09-20, after `00d` landed.** Every number below is post-fix. The previous version
of this file carried pre-fix numbers and three statements that the sign correction inverted; it was
rewritten rather than re-signed, per `work/00-corrections.md` §`00d` ("What this means for `06c`").

**Source:** `mart_corner_skill_driver` rebuilt post-`00d`; parquets re-exported and verified.
Race-clustered figures computed for this item from `int_corner_skill_residuals` and
`int_corner_metrics` on `data/dev.duckdb`.

---

## What `00d` changed

`braking_loss_s` was `(own braking point − field median)`, so positive meant braking **later**, i.e.
faster. The other two phases are positive when **worse**. `corner_skill_index` summed all three
z-scores and ranked ascending, so one of three terms entered the shipped leaderboard inverted. Fixed
at the source in `int_corner_skill_residuals.sql`; all three phases now read "positive = seconds
lost".

Consequences for this item:

- Braking columns flip sign exactly. `corner_skill_index` moves by `−2 × (old braking z)`.
- SEs and all three cell counts are **invariant** to the flip.
- `corr(index before, index after) = +0.21`. 122 of 139 scored driver-seasons change rank; the
  season leader changes in six of seven seasons.

---

## Finding 1 — Verstappen brakes later than his teammate (was the "anomaly")

Post-fix, `braking_skill_s` negative = braking later = faster.

| Season | Teammate | `braking_skill_s` | SE | Braking cells | `corner_skill_index` | Rank |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: |
| 2018 | RIC | +0.0036 | ±0.0189 | 211 | +0.42 | 14 / 20 |
| 2019 | GAS / ALB | −0.0492 | ±0.0140 | 253 | −3.28 | **1 / 18** |
| 2020 | ALB | −0.1566 | ±0.0220 | 182 | −5.61 | **1 / 20** |
| 2021 | PER | −0.0770 | ±0.0148 | 241 | −3.09 | 2 / 20 |
| 2022 | PER | −0.0426 | ±0.0127 | 293 | −2.57 | 2 / 20 |
| 2023 | PER | −0.0403 | ±0.0152 | 273 | −2.10 | 4 / 21 |
| 2024 | PER | **−0.0745** | ±0.0151 | 282 | −2.96 | 2 / 20 |

Negative in six of seven seasons, against four distinct teammates. 2018 vs Ricciardo is the lone
exception and is indistinguishable from zero (t = 0.19 on the mart SE).

### Race-clustered cross-check (the mart SEs are optimistic)

The mart's SE is `STDDEV(cells)/SQRT(COUNT(cells))` over (driver, race, corner) cells
(`mart_corner_skill_driver.sql:238-243`). Cells nest inside races and are not independent, so that
SE understates uncertainty. Re-run with the race as the unit of observation:

| Season | Mean diff (s) | Race-clustered SE | t | Races VER braked later |
| :--- | ---: | ---: | ---: | :--- |
| 2018 | +0.0056 | ±0.0346 | 0.16 | 7 / 17 |
| 2019 | −0.0470 | ±0.0252 | −1.87 | 17 / 20 |
| 2020 | −0.2592 | ±0.1230 | −2.11 | 14 / 15 |
| 2021 | −0.0623 | ±0.0292 | −2.13 | 14 / 19 |
| 2022 | −0.0503 | ±0.0139 | −3.62 | 18 / 22 |
| 2023 | −0.0366 | ±0.0260 | −1.41 | 16 / 21 |
| 2024 | −0.0816 | ±0.0197 | −4.13 | 18 / 22 |
| **2019–2024 pooled** | **−0.0814** | **±0.0185** | **−4.39** | **97 / 119** |

Sign test on 97/119: p ≈ 2 × 10⁻¹². Individual seasons vary from convincing (2024, 2022) to
suggestive (2023); the pooled race-level result is what the claim should rest on.

**In metres** (`braking_point_m` differential, same race-clustered construction): pooled 2019–2024
**+5.6 m ±1.3** later on the brakes. Per season: 2018 +0.9 ±2.2, 2019 +3.2 ±1.9, 2020 +18.4 ±8.8,
2021 +5.2 ±1.9, 2022 +2.6 ±1.6, 2023 +2.1 ±1.8, 2024 +5.8 ±1.3.

### VER 2024 full phase split, race-clustered vs PER

| Phase | Mean diff (s) | Race-clustered SE | t | Races ahead |
| :--- | ---: | ---: | ---: | :--- |
| Braking | −0.0816 | ±0.0197 | −4.13 | 18 / 22 |
| **Mid-corner** | **−0.0795** | ±0.0126 | **−6.33** | **20 / 22** |
| Exit | +0.0483 | ±0.0124 | +3.90 | 5 / 22 |

Mid-corner is his largest and most consistent edge, not braking. He concedes on exit in 17 of 22
races.

---

## Finding 2 — the Norris leaderboard re-read

**NOR is no longer the 2024 leader.** He falls 1st → 4th (index −3.17 → −1.69). He led four seasons
pre-fix (2021, 2022, 2023, 2024) and leads none post-fix (ALO takes 2021–22, GAS takes 2023–24).

2024 top of table, ordered as the app orders it (`corner_skill_index ASC`):

| # | Driver | Team | Braking z | Mid z | Exit z | Index |
| ---: | :--- | :--- | ---: | ---: | ---: | ---: |
| 1 | GAS | Alpine | −2.18 | −1.15 | −0.43 | −3.76 |
| 2 | VER | Red Bull | −1.30 | −2.12 | +0.46 | −2.96 |
| 3 | ZHO | Kick Sauber | −0.80 | −1.15 | −0.27 | −2.22 |
| 4 | NOR | McLaren | +0.74 | −0.24 | **−2.19** | −1.69 |
| 5 | RUS | Mercedes | −0.89 | −0.16 | −0.36 | −1.41 |

Verified: `corner_skill_index` equals the sum of the three printed z-scores exactly on every row
(max abs deviation 0.0), which is the identity the app prints and the one fix option (b) would have
broken.

**The traction claim survives and sharpens.** NOR's exit z of −2.19 is the largest single phase term
anywhere in the 2024 table. Raw exit −0.2669 s ±0.0392 on 76 cells, 6.3× his braking term.

| NOR vs PIA, 2024 | Mean diff (s) | Race-clustered SE | t | Races ahead |
| :--- | ---: | ---: | ---: | :--- |
| Braking | **+0.0502** | ±0.0160 | +3.13 | **6 / 24** |
| Mid-corner | −0.0108 | ±0.0086 | −1.25 | 12 / 24 |
| Exit | −0.1930 | ±0.1056 | −1.83 | 12 / 14 |

Post-fix the honest statement is stronger than "traction, not braking": **Norris braked earlier than
Piastri in 18 of 24 shared races**, and his whole advantage was exit. The braking deficit is the most
statistically solid line in the McLaren comparison; the exit magnitude is the least (14 paired races,
SE ±0.1056), though the direction holds at 12 of 14.

---

## Finding 3 — the index is a pure teammate differential

With two drivers per car the LORO baseline **is** the other driver, so pairs are exactly
antisymmetric. Verified on 2024 by summing `braking_skill_s` within constructor: **0.00000** for
Aston Martin, Kick Sauber, McLaren, Mercedes and Red Bull. The five teams with a non-zero sum are
exactly those that ran a third driver in 2024 (Alpine −0.0015, Ferrari +0.0033, Haas −0.0048,
RB −0.0030, Williams −0.0102); the third driver shifts the LORO baseline without clearing the cell
floor to appear as a row.

So VER ±0.0745 against PER is **one number written twice**, not two findings. GAS topping 2024 means
he beat Ocon in all three phases by more than anyone beat their teammate:

| GAS vs OCO, 2024 | Mean diff (s) | Race-clustered SE | t | Races ahead |
| :--- | ---: | ---: | ---: | :--- |
| Braking | −0.1483 | ±0.0433 | −3.43 | 16 / 19 |
| Mid-corner | −0.0368 | ±0.0094 | −3.93 | 16 / 19 |
| Exit | −0.0550 | ±0.0122 | −4.51 | 16 / 19 |

**No cross-team comparison is available from this mart.** A common baseline would need a fitted
field-wide model, which is a different item.

---

## Index construction

1. Per-corner residuals vs a **backward-only trailing-5-lap** field median; NULL when
   `field_corner_sample_n < 5`, and lap 2 always NULL.
2. Sign convention post-`00d`, one rule for all three phases: **positive = seconds lost**.
   `braking_point_m` higher is faster → `(field − own)`; `v_min_kph` higher is faster →
   `(field − own)`; `throttle_point_m` higher is slower → `(own − field)`.
3. Each (driver, race, corner) cell is LORO-adjusted against the same-car baseline, then winsorized
   to ±1.0 s.
4. Season phase means = `AVG` of winsorized cells; SE = `STDDEV/SQRT(N)` over those cells.
5. Each phase z-scored within season; `corner_skill_index` = sum of the three, ranked ascending,
   scored only when every phase clears `PHASE_MIN_CELLS = 30`.

**Population:** 141 driver-seasons 2018–2024, **139 scored**. The two unscored are NOR 2019 and
SAI 2019, both on exit at 21 cells.

**The exit phase is the weakest measurement** — fewest cells, widest SEs, and the widest spread
between teams (2024: 76 cells for McLaren vs 262 for Kick Sauber).

---

## The two candidate explanations — resolved

**Explanation 1 — braking sign inverted in the index. CONFIRMED.** The falsification this file named
("inspect the SQL that constructs `braking_skill_z`") was run by the `00d` audit. It also named the
wrong model: the sign was set in `int_corner_skill_residuals.sql`, two models upstream of the
`fct_cliff_prediction_features.sql` this file pointed at.

**Explanation 2 — Pérez was genuinely a strong braker in 2024, making VER look weak. NOT NEEDED, and
independently falsified.** Its own named falsification (compare VER against non-Pérez teammates) was
run: the later-braking pattern holds against Albon (2020) and the Gasly/Albon pairing (2019), and is
absent only against Ricciardo (2018). The result was never about Pérez.

The "perfect sign symmetry" this file previously read as evidence of a systematic baseline effect was
real, but it is not evidence of a bug — it is the arithmetic of a two-driver LORO baseline (Finding 3).

**Corroboration from an independent direction.** `06b` reached the same sign defect from a treatment
whose physical direction is known a priori: dirty air produces negative `braking_loss_s` in every
corner class and both eras, and dirty air can only make a driver brake *earlier*.

---

## Definition of done

Per `work/06-publication.md:568-570`, against `06c_blog_post.md`:

| Requirement | Status |
| :--- | :--- |
| Phase split (braking / mid / exit) shown | Done — for VER, NOR and GAS, plus the 2024 table |
| Cell counts and SEs shown | Done — mart SEs with cell counts, plus race-clustered SEs with race counts |
| Teammate-relative baseline stated plainly | Done — its own section, with the antisymmetry demonstrated |
| VER framed with two candidate explanations named | Done — both named, both falsified, resolution stated |

Framing changed deliberately: the spec asked for the anomaly "as an open question". It is no longer
open, so the post reports the resolution instead of staging a question it knows the answer to.

**Not done, deliberately:** the post is drafted, not published. Publication is **D15**.
