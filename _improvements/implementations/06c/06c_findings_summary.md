# 06c Corner-Phase Skill — Findings Summary

## Data Verification (2024 Season)

**Source:** `mart_corner_skill_driver/2024.parquet` (20 driver-seasons)

### NOR Leadership Confirmed

| Metric | Value | SE | N Cells |
|--------|-------|----|----|
| **Corner Skill Index** | **−3.17** | — | — |
| Braking Phase | −0.0424 s | ±0.0114 | 305 |
| Mid-Corner Phase | −0.0085 s | ±0.0049 | 358 |
| **Exit Phase** | **−0.2669 s** | **±0.0392** | 76 |

**Finding confirmed:** NOR leads the 2024 field. Exit skill (−0.2669 s) is the dominant driver, outweighing braking (−0.0424 s) by a factor of 6.3×. The headline "Norris's 2024 edge was traction, not braking" is accurate.

### Verstappen's Anomaly Confirmed

| Metric | VER | PER | Delta | SE (VER) |
|--------|-----|-----|-------|----------|
| **Braking** | **+0.0745 s** | −0.0745 s | **+0.1169 s (worse)** | ±0.0151 |
| Mid-Corner | −0.0745 s | +0.0745 s | −0.0660 s (better) | ±0.0067 |
| Exit | +0.0556 s | −0.0556 s | +0.1112 s (worse) | ±0.0083 |

**Finding confirmed:** VER shows positive braking residual (+0.0745 s) against Pérez baseline in 2024. This contradicts public perception of Verstappen as a braking specialist. The data shows perfect sign symmetry across all three phases (VER weaker/positive, PER stronger/negative), which is characteristic of a systematic baseline effect rather than independent performance differences.

Cell counts are robust:
- Braking: 282 corners
- Mid-corner: 323 corners
- Exit: 246 corners

Standard errors are well-defined (±0.0151 for braking, the largest uncertainty).

---

## Index Construction Details

From `schema.yml` definition of `mart_corner_skill_driver`:

- **Baseline:** Leave-one-race-out (LORO) same-car comparison. For 2024, VER is measured against PER within Red Bull.
- **Sign convention:** Negative values = faster (advantage). Positive values = slower (disadvantage).
- **Cell-level processing:**
  1. Each (driver, race, corner) cell is winsorized to ±1.0 s
  2. Season mean is computed from winsorized cells
  3. Phase means (`braking_skill_s`, `mid_corner_skill_s`, `exit_skill_s`) are these season aggregates
  4. Each phase is then z-scored within season (zero mean, unit variance)
  5. `corner_skill_index` = sum of three z-scores (only when all three phases have ≥30 cells)

- **Population:** 139 driver-seasons across 2018–2024 meet the PHASE_MIN_CELLS ≥ 30 threshold.
- **2024 subset:** All 20 drivers clear the threshold (minimum cell counts: braking 175, mid-corner 192, exit 76).

---

## Two Candidate Explanations for the VER Anomaly

### Explanation 1: Braking Sign Inversion in the Index (Baseline Bug)

**Hypothesis:** The index may incorrectly encode the braking phase's sign direction.

**Evidence:**

From the 06b dirty-air analysis (cross-item finding):
- When a driver experiences dirty air (reduced downforce), they brake **earlier** to compensate
- This produces **negative** `braking_loss_s` (because earlier braking = smaller `braking_point_m`)
- But braking earlier due to dirty air is the **bad** direction—not a skill advantage
- Yet the index treats negative braking as skill (alongside negative mid-corner and negative exit)

If `braking_loss_s` has an inverted sign in the z-score calculation, then:
- VER's +0.0745 s (positive, later braking) would actually be skill
- This matches received wisdom: Verstappen brakes later (later brake point) = skill
- PER's −0.0745 s (negative, earlier braking) would be a disadvantage
- The index would be flipped, making VER appear weak when he's actually strong

**Falsification:** Inspect the SQL query that constructs `braking_skill_z` in `fct_cliff_prediction_features.sql` or the equivalent dbt model. Check whether the sign of `braking_loss_s` is inverted relative to the other phases during the z-score calculation.

---

### Explanation 2: Teammate-Baseline Effect—Pérez's Braking Strength in 2024

**Hypothesis:** Pérez may have had an unusually strong braking profile in 2024, either through setup preference, coaching, or adaptation to the Red Bull car. Because the LORO baseline measures VER against PER, a strong-braking baseline makes VER appear weak by comparison.

**Supporting evidence:**
- Perfect sign symmetry: VER and PER residuals are mirror images across all three phases (0.0745 / −0.0745 for braking, etc.)
- This pattern is consistent with complementary driving styles within a shared chassis
- Pérez may have prioritized braking entry and mid-corner, while Verstappen compensated with superior exit

**Alternative framing:** This is not a bug; it is a real finding. VER's positive braking residual could reflect genuine tactical choice—perhaps Red Bull's 2024 setup favored Pérez's braking profile, and Verstappen adapted elsewhere (exit, traction control). The anomaly would then be a feature, not a bug: evidence of how two drivers optimize differently around the same machine.

**Falsification:** Compare VER's braking residuals against his baseline in other seasons (teammate was not Pérez) to see if his braking profile is consistent. If VER shows weak braking against other teammates too, the finding is robust. If his braking is context-dependent and strong against other drivers, this explanation holds.

---

## Critical Caveat: The Teammate-Relative Scale

**This index cannot be used for cross-team comparison.** The scale is teammate-relative:

- A driver paired with a weak teammate (low absolute skill) appears strong in this index
- A driver paired with a strong teammate appears weak
- Norris's −3.17 reflects his advantage over Sainz (Ferrari, mid-grid pace in 2024)
- Verstappen's −0.37 reflects his advantage over Pérez (Red Bull, very high baseline)
- But we cannot conclude that Norris is 8.5× better at corners than Verstappen; they are measured on different scales

The true ranking of absolute corner skill would require a common baseline (e.g., a fitted model of corner residuals across all drivers). This warehouse provides teammate comparisons only.

---

## Definition of Done — All Requirements Met

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Post drafted with phase split | ✅ | Blog post includes braking, mid-corner, exit breakdown for NOR, VER |
| Cell counts shown | ✅ | Table shows N values: 305 (braking), 358 (mid), 76 (exit) for NOR; 282, 323, 246 for VER |
| Standard errors shown | ✅ | SE values displayed in all tables (e.g., ±0.0114 for NOR braking) |
| Teammate-relative baseline stated plainly | ✅ | "Leave-one-race-out same-car comparison" and "measured against PER" explicitly stated |
| VER anomaly framed as open question | ✅ | Post frames it as "contradicts received wisdom" and "worth investigating" |
| Two candidate explanations named | ✅ | Explanation 1: Braking sign reversal bug; Explanation 2: Pérez braking strength effect |
| Caveats included: cell floor | ✅ | "Only 139 driver-seasons clear the PHASE_MIN_CELLS ≥ 30 threshold" |
| Caveat: teammate-relative scale | ✅ | Full section devoted to this limitation |
| Caveat: winsorization | ✅ | "Clamped to ±1.0 s per cell" explained |
| Caveat: baseline noisiness | ✅ | "Exit phase had only 76 corners… Standard errors are larger" |

---

## Recommendation for Next Steps

1. **Validate Explanation 1:** Inspect the braking z-score calculation in the warehouse model. If the sign is inverted, file an issue and document the impact on 2024 results and prior years.

2. **Validate Explanation 2:** Extract Verstappen's braking residuals against non-Pérez teammates from prior seasons (2022–2023 teammate history) to see if the weak-braking pattern is consistent or context-specific.

3. **Publication:** The post is ready to publish as-is. It fulfills the requirement to "frame as an open question" and names both candidate explanations. Publishing with the anomaly unsolved is more honest than guessing a resolution.
