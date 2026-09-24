# 06c Completion Checklist

**Rewritten 2026-09-20** after `00d` landed. The previous version signed off a draft built on the
pre-fix index and is superseded. That draft was lost with its temp scratchpad and was rewritten from
the repo artefacts rather than recovered, which `00d` required anyway.

---

## Deliverables

### 1. The post — `06c_blog_post.md` (in the repo, not a scratchpad)

Title: *"Does Verstappen actually brake later? Yes — and finding out cost us our leaderboard"*

- The sign defect and how it was caught, from two independent directions
- The two candidate explanations, both named, both resolved
- Verstappen's braking across seven seasons and four teammates, in seconds and in metres
- Verstappen's full 2024 phase split against Pérez
- The Norris re-read: 1st → 4th, and why the traction claim survives and sharpens
- What the leaderboard actually measures, and why Gasly tops 2024
- Construction, caveats, and what would change our mind

### 2. `06c_findings_summary.md` — rewritten, all numbers post-fix

### 3. `06c_stats.json` — regenerated from the rebuilt mart plus the race-clustered figures

### 4. `06c_analysis.py` — the original pre-fix loader, left as-is

Superseded by the queries recorded in the findings summary; kept for provenance only. **Its outputs
are pre-fix. Do not re-quote them.**

---

## Definition of done — `work/06-publication.md:568-570`

| Requirement | Status | Where |
| :--- | :--- | :--- |
| Post drafted with the phase split | Met | Phase table up front; splits for VER, NOR and GAS |
| Cell counts and SEs shown | Met | Mart SEs with cell counts; race-clustered SEs with race counts |
| Teammate-relative baseline stated plainly | Met | Dedicated section; antisymmetry demonstrated numerically |
| VER framed as an open question, two explanations named | **Adapted — see below** | Both named and resolved |

**The one deliberate departure.** The spec asked for the anomaly "as an open question with the two
candidate explanations named". `00d` closed the question before the post was written. Staging a
question whose answer is known would be dishonest, so the post names both explanations, reports
which was confirmed, and reports the independent falsification of the other. The requirement's
purpose — do not publish a bug as a finding — is met more fully than the literal wording would have.

---

## What changed against the pre-fix draft

| Claim in the old draft | Status now |
| :--- | :--- |
| "VER braking +0.0745 s, worse than PER" | **Inverted.** −0.0745 s, and better |
| "Contradicts public perception of VER as a braking specialist" | **Reversed.** It confirms it |
| "NOR leads the 2024 field at −3.17" | **False.** 4th at −1.69; GAS leads at −3.76 |
| "Norris's 2024 edge was traction, not braking" | **Survives, sharpened.** Exit z −2.19 is the largest phase term in 2024, and he braked *earlier* than PIA in 18 of 24 races |
| "Perfect sign symmetry suggests a systematic baseline effect" | **Restated.** Real, but it is the arithmetic of a two-driver LORO baseline, not evidence of a bug |
| Two explanations posed, unresolved | **Resolved.** 1 confirmed; 2 independently falsified |

---

## Added in the rewrite, beyond what the spec asked for

1. **Race-clustered standard errors.** The mart SE is `STDDEV(cells)/SQRT(N cells)` and treats ~280
   corner-cells as independent when they nest inside ~22 races. Every load-bearing claim in the post
   is restated at race level, where the unit of observation is defensible.
2. **A sign test.** 97 of 119 races, p ≈ 2 × 10⁻¹². Robust to the SE question entirely.
3. **A metres conversion.** +5.6 m ±1.3 pooled — the fan-legible version of the headline.
4. **Explanation 2 falsified rather than dropped.** Its own named falsification (VER against
   non-Pérez teammates) was run: the pattern holds against Albon and Gasly/Albon, absent only
   against Ricciardo.
5. **The antisymmetry verified numerically**, including why five 2024 teams deviate from it (a third
   driver shifts the LORO baseline without clearing the cell floor).

---

## Verification performed

- Every number quoted in the post re-read from the post-`00d` parquets, not from the old stats file.
- The 2024 table checked against the identity `corner_skill_index = braking_z + mid_z + exit_z`;
  max absolute deviation **0.0**.
- Race-clustered figures computed from `int_corner_skill_residuals` and `int_corner_metrics` on
  `data/dev.duckdb` (rebuilt post-fix).
- Population confirmed: 141 driver-seasons, 139 scored, the two misses being NOR 2019 and SAI 2019 at
  `exit_cells_n = 21`.

---

## Not done, deliberately

- **Not published.** Publication is **D15**.
- **No commit.** Per standing instruction, commits are the user's call.
- **`06c_analysis.py` not re-run or rewritten.** Its numbers are pre-fix and it is marked as such.
- **No app or warehouse change.** `00d` already established the app needs no code change, and a
  `make app-data` before publish regenerates the stale `_manifest.json` version hash.
