# B1 ruling 1 (racecraft free passes out of step 1): what it does to every registered count floor

**Analysis only, structure columns only.** Written 2026-10-30. No outcome column was read (`seg_time_s`, `min_speed_kph`, `exit_speed_kph`, `seg_start_t`, `seg_end_t`, coast, throttle, `LapTime` were not opened). Nothing was fitted. `data/dev.duckdb` was not opened. No threshold, floor or gate is proposed for change: the registration (`wi/WC-10-discovery-preregistration-DRAFT.md`, commit `6fd0330`) is read as it stands (BUILD-ORDER rule 4).

## Plain-English summary (read this first)

- **What changed.** Ruling 1 says a "free" pass that happened while positions were changing nearby (racecraft) can no longer be used to set a driver's free-air baseline. That removes 11,950 of 172,413 free passes (6.9 %). Fewer baseline passes means some following passes lose their baseline, some lose their "free pass on both sides" bracket, and some lose the free running at other corners that the held-up / dirty-air class needs.
- **Does any floor that was met become not met?** **No.** Every floor that was met before the drop is still met after it, in every class. Every floor that was already missed before the drop is still missed. The drop shrinks counts by roughly 4-13 %, not by enough to cross a line.
- **Where it hurts most.** The S2 bracketed check (the one that compares passes with a free pass on both sides against the rest). Slow corners lose 13 % of their bracketed near-band passes (947 to 822), medium loses 10 % (1,025 to 924). Both are still above the 500 needed for AGREE, with room to spare (the outcome trim would have to remove 39 % of slow and 46 % of medium bracketed passes to cross it; the trims are wide incident trims, so that is not expected). Fast was already below 500 (420) and goes to 387: it still cannot AGREE, exactly as the registration already says, and that does not block DESIGN A.
- **The one thing that got closer to the edge: S2-aero.** Its count is the smaller of the fast and slow **dirty-air** bracketed counts. Before outcomes we can only count the passes whose class is knowable (an upper bound): fast 306 before, 282 after. S2-aero can only say DISAGREE if at least 100 of those turn out dirty air, so now at least 35.5 % of them must be dirty air (32.7 % before). If fewer are, S2-aero is forced to INCONCLUSIVE. Under the registration that does **not** block DESIGN A or aero: aero is still proposed, with the weakness printed. It was never able to reach AGREE (below 500 before and after).
- **Things the drop does not touch.** The data gate (it hashes file bytes, it counts no passes), the lap arm behind F1 (its free laps already exclude any lap with a racecraft pass), the 43-race / 24-circuit bootstrap list (fixed literals), and the stint close-share tiers.
- **Worst honest outcome.** The drop does not by itself force any verdict. What it does is make every interval a little wider (about 3-7 % more noise from 6-13 % fewer passes) and the S2 equivalence test a little harder to pass. If, on the real data, medium or slow S2-pace comes out INCONCLUSIVE, the registered table says DESIGN A is blocked; then FALLBACK (lap level, pace only) if F1 passes, else NEITHER. That path existed before the drop; the drop makes it somewhat more likely, by an amount that only SG7 (the synthetic S2 power check, rerun after the amendment on the new structure) can measure. If SG7 then fails, the registered ladder applies (±8-lap window, then a 0.030 s pace floor, then "S2 unpowered"), each step a pre-result amendment.

## Headline per gate

| Gate / floor (registration §) | Floor | Before drop | After drop | Status |
|---|---|---|---|---|
| Data gate (§16) | 4 byte digests | no pass count | no pass count | **Met, unaffected** |
| S1 (§11): β_near and β_far must exist per class | no count floor; bins must be non-empty | near 4,475 / 11,374 / 10,806; far 6,013 / 17,963 / 16,791 | near 4,263 / 10,808 / 10,207; far 5,828 / 17,392 / 16,205 | **Met** (37 / 43 / 43 races, unchanged) |
| S2-pace AGREE floor (§11) | ≥ 500 bracketed near-band entering | 420 / 1,025 / 947 | 387 / 924 / 822 | Fast **not met** (already not met before); medium, slow **met** |
| S2-pace DISAGREE floor (§11) | ≥ 100 | 420 / 1,025 / 947 | 387 / 924 / 822 | **Met** in every class |
| S2 cell floor (§11) | bracketed passes in a cell with < 20 one-sided are dropped | 1 thin cell per class; 4 / 5 / 5 bracketed dropped | same cell; 3 / 2 / 2 dropped | **Unchanged** (no new thin cell) |
| S2-aero AGREE floor (§11) | ≥ 500 (min of fast, slow dirty-air) | ≤ 306 (upper bound) | ≤ 282 (upper bound) | **Not met** (already not met before) |
| S2-aero DISAGREE floor (§11) | ≥ 100 | ≤ 306 | ≤ 282 | **At risk** (needs ≥ 35.5 % of fast class-known passes to be dirty air; was 32.7 %) |
| S3 population (§11) | groups with ≥ 3 free passes spanning ≥ 8 tyre-age laps, ≥ 1 near-band pass | 2,467 / 5,916 / 5,604 passes in 813 / 2,061 / 1,861 groups | 2,308 / 5,523 / 5,170 passes in 774 / 1,919 / 1,723 groups | **Met** |
| F1 (§11) | lap arm support ≥ 3 free laps; S3 medium, slow | lap arm counts unchanged by construction | unchanged; S3 medium, slow met | **Met** (lap arm unaffected) |
| Support (§6a) | ≥ 2 free passes per group | 150,500 supported following | 144,123 | Floor applies per group; 543 groups fall below it (amendment B1 §C) |
| φ support (§6c) | ≥ 3 distinct other free drivers, W ≤ 2 | 12,131 supported following φ-unsupported | 12,367 | Per-pass floor; 236 more passes fail it |
| θ thin cells (§6d) | ≥ 3 distinct free drivers per (race, compound, class) | 47 of 329 thin | 46 of 328 thin + 1 cell left with no free pass (47 thin or empty) | **Unchanged in effect** |
| Pass class (§6h) | N_F ≥ 2, N_L ≥ 2, leader eligible, φ̃ ok | known 4,080 / 11,450 / 11,041 | known 3,711 / 10,603 / 10,162 | Per-pass floor; more `unknown` (see table 5) |

Counts are fast / medium / slow. "Entering" means supported, not racecraft, φ-supported. **Every "after" count is an upper bound on the run-time count**: they are taken before the §6f (i) free-pass trim and the §6f (ii) following-pass trim, which need outcomes and can only remove more.

---

## 1. How the counts were made

- Script: `b1_support_impact.py` (session scratch, sha256 `938ad3454cac88201239b86ff8250de4b4748adccb31f45917f398ccc8bdd39f`), output `b1_support_impact_out.txt` (sha256 `9cf46b901de63f3b53ba8c1bdb10c9e93fc9a4c473b0aff465fae325f6f2ea3a`). Thin-cell check `b1_theta_check.py` (sha256 `77f74bb310f93cac2de1ec16342d7f7e42fa59bc9d781868a5b62944121192cc`), output sha256 `b548964ad8663c0ae3341375e319866efe3fbe3543f79848e73a3c1ea1db20c2`. All in `/private/tmp/claude-501/-Users-justin-github-off-the-pace/885ba8d8-f683-485f-bcf1-ec11563a5da3/scratchpad/`. If they are to be kept as evidence, the owner copies them into `counts_d/scripts/` (BUILD-ORDER rule 8).
- Columns read: pass table `season`, `race_id`, `race`, `driver`, `lap`, `stint`, `compound`, `tyre_life`, `corner_id`, `corner_number`, `corner_class`, `segment_basis`, `leader`, `leader_lap`, `gap_s`, `clear_ahead`, `behind_1s`, `tag`, `reason`; sidecar `prev_lap_gap_s`, `prev_lap_clear_ahead`, `prev_lap_reason` (structure, as d05). A grep of both scripts finds no outcome-column name outside the docstring.
- Eligibility, free / following / near / far, groups, ±5 local bracket, φ windows (n_W distinct other drivers, W = 0, 1, 2), 15 S2 cells (gap change in the B-iv order × stint close-share tier with the top tiers merged), cross-fitted class availability and the S3 population follow §5, §6a-§6d, §6h, §8a, §8d, §11 and the d05 / d06 scripts.
- "Before" = all free passes in step 1 (the registered §3 item 8 structure). "After" = racecraft free passes removed from step 1, and from everything counted from that set (support, bracket, φ n_W, θ driver counts, N_F / N_L, S3), as ruling 1 says.
- **Reproduction check (before):** supported following 150,500; φ-unsupported 12,131; bracketed near band, racecraft out, φ ok 424 / 1,030 / 952; one-sided 4,051 / 10,344 / 9,854; thin θ cells 47 of 329 (40 with one driver), 1,539 free / 2,376 following passes in them. All equal d03 / d05. The after-drop supported following total (144,123) equals amendment B1 §C.
- **One deliberate difference from d05:** the class-known count here also requires the **leader's** φ̃ to be supported (§6h last condition), which d05 did not check. So "before" is 4,080 / 11,450 / 11,041, not d05's 4,124 / 11,576 / 11,131.
- **Not counted here** (needs an outcome or a fit): §6f trims; σ̂_k; the ᾱ "no comparison group left" case of ruling 2; the held-up / dirty-air split; undefined bootstrap draws (ruling 4).

## 2. S1: passes entering β per class and bin (supported, not racecraft, φ-supported; before trim ii)

| Bin (s) | Fast before | Fast after | Medium before | Medium after | Slow before | Slow after |
|---|---|---|---|---|---|---|
| 0-0.3 (no decision) | 420 | 388 | 1,032 | 939 | 958 | 877 |
| 0.3-0.5 | 1,232 | 1,134 | 3,245 | 2,992 | 3,095 | 2,894 |
| **0.5-0.75 (near)** | 2,389 | 2,274 | 6,220 | 5,882 | 5,818 | 5,487 |
| **0.75-1.0 (near)** | 2,086 | 1,989 | 5,154 | 4,926 | 4,988 | 4,720 |
| 1.0-1.5 | 3,337 | 3,210 | 9,394 | 9,019 | 8,876 | 8,467 |
| 1.5-2.0 | 3,803 | 3,659 | 10,511 | 10,055 | 9,798 | 9,306 |
| **2.0-2.5 (far)** | 3,150 | 3,038 | 9,492 | 9,139 | 8,957 | 8,605 |
| **2.5-3.0 (far)** | 2,863 | 2,790 | 8,471 | 8,253 | 7,834 | 7,600 |
| Near band total | 4,475 | 4,263 (−4.7 %) | 11,374 | 10,808 (−5.0 %) | 10,806 | 10,207 (−5.5 %) |
| Far band total | 6,013 | 5,828 (−3.1 %) | 17,963 | 17,392 (−3.2 %) | 16,791 | 16,205 (−3.5 %) |
| Races with a near-band pass | 37 | 37 | 43 | 43 | 43 | 43 |

S1 has no count floor. It needs β_near and β_far to exist in the full fit and in every bootstrap draw (ruling 4). With thousands of passes per bin spread over 37-43 races, an empty near or far bin in a draw is not a realistic risk. **Met.** The cost is precision only: about 5 % fewer near-band passes, so the interval is about 2-3 % wider.

## 3. S2-pace: bracketed near band and the 15 cells

Bracketed near-band passes (local ±5, not racecraft, φ-supported) and one-sided near-band passes, per class:

| | Fast before | Fast after | Medium before | Medium after | Slow before | Slow after |
|---|---|---|---|---|---|---|
| Bracketed near band | 424 | 390 | 1,030 | 926 | 952 | 824 |
| … dropped for a thin cell (< 20 one-sided) | 4 | 3 | 5 | 2 | 5 | 2 |
| **Bracketed entering β^brk (the S2 count)** | **420** | **387** (−7.9 %) | **1,025** | **924** (−9.9 %) | **947** | **822** (−13.2 %) |
| One-sided near band | 4,051 | 3,873 | 10,344 | 9,882 | 9,854 | 9,383 |
| AGREE floor 500 | not met | not met | met | met | met | met |
| DISAGREE floor 100 | met | met | met | met | met | met |
| Headroom above 500 after drop | n/a | n/a | | 424 (46 % of 924) | | 322 (39 % of 822) |

The bracketed set loses more than the one-sided set (−9 to −13 % against −4 to −5 %). That is expected: a racecraft free pass is by definition near a position change, so it tends to sit right next to a following spell, which is where it was serving as one end of a bracket.

**The 15 cells.** Bracketed (b) and one-sided (o) near-band counts, before → after. "thin" = fewer than 20 one-sided, so its bracketed passes are dropped (§11).

| Gap change | Tier | Fast b | Fast o | Medium b | Medium o | Slow b | Slow o |
|---|---|---|---|---|---|---|---|
| arrived from free | < 0.20 | 109 → 105 | 64 → 68 | 234 → 219 | 125 → 137 | 207 → 193 | 125 → 134 |
| arrived from free | 0.20-0.50 | 27 → 22 | 41 → 42 | 54 → 46 | 87 → 89 | 42 → 31 | 72 → 77 |
| arrived from free | ≥ 0.50 | 4 → 3 | **13 → 13 thin** | 5 → 2 | **16 → 16 thin** | 5 → 2 | **17 → 14 thin** |
| shrinking | < 0.20 | 101 → 91 | 386 → 391 | 345 → 307 | 1,037 → 1,045 | 308 → 271 | 937 → 954 |
| shrinking | 0.20-0.50 | 62 → 57 | 791 → 761 | 138 → 119 | 1,983 → 1,917 | 157 → 129 | 1,769 → 1,701 |
| shrinking | ≥ 0.50 | 5 → 5 | 305 → 269 | 11 → 10 | 786 → 707 | 6 → 4 | 874 → 785 |
| steady | < 0.20 | 14 → 14 | 86 → 85 | 32 → 30 | 282 → 279 | 24 → 20 | 314 → 314 |
| steady | 0.20-0.50 | 34 → 32 | 585 → 567 | 55 → 52 | 1,443 → 1,412 | 51 → 46 | 1,229 → 1,182 |
| steady | ≥ 0.50 | 3 → 3 | 312 → 294 | 5 → 5 | 949 → 854 | 4 → 3 | 1,154 → 1,057 |
| growing | < 0.20 | 20 → 16 | 135 → 137 | 48 → 41 | 290 → 296 | 48 → 44 | 315 → 312 |
| growing | 0.20-0.50 | 28 → 26 | 575 → 545 | 47 → 43 | 1,444 → 1,381 | 58 → 49 | 1,326 → 1,257 |
| growing | ≥ 0.50 | 1 → 1 | 356 → 325 | 9 → 9 | 932 → 829 | 12 → 6 | 986 → 908 |
| unknown | < 0.20 | 13 → 12 | 152 → 149 | 33 → 30 | 363 → 358 | 22 → 20 | 253 → 250 |
| unknown | 0.20-0.50 | 3 → 3 | 201 → 183 | 11 → 10 | 454 → 427 | 8 → 6 | 358 → 333 |
| unknown | ≥ 0.50 | 0 → 0 | 49 → 44 | 3 → 3 | 153 → 135 | 0 → 0 | 125 → 105 |

- The thin cell is the same one in every class, before and after (arrived from free × tier ≥ 0.50). No other cell comes near 20 one-sided passes (the next smallest is fast "arrived from free, 0.20-0.50" at 42). **The cell floor is unchanged.**
- The two cells that carry most of the bracketed weight (arrived from free and shrinking, tier < 0.20) keep 64-137 and 271-1,045 passes. A one-sided cell has no "undefined" risk in the full sample; in a bootstrap draw a cell that falls below 20 one-sided passes drops its bracketed passes (that is the registered cell rule, not an undefined draw).
- One-sided counts in the "arrived from free" cells **rise** slightly after the drop (for example medium < 0.20: 125 → 137): passes that lost a bracket end move from bracketed to one-sided.

## 4. S2-aero: the dirty-air bracketed count (upper bound)

The S2-aero count is the smaller of the fast and slow **dirty-air** bracketed near-band counts after trims. Dirty air versus held up needs a fitted Δ̂, so it cannot be counted from structure. What can be counted is the set whose class is knowable (§6h: N_F ≥ 2, N_L ≥ 2, leader eligible, own and leader φ̃ supported), in non-thin cells. Dirty air is a subset, so this is an upper bound.

| | Before | After |
|---|---|---|
| Fast bracketed near, class knowable, in S2 cells | 306 | 282 |
| Medium (reported, not in A) | 847 | 738 |
| Slow | 809 | 699 |
| **Upper bound on the S2-aero count (min of fast, slow)** | **306** | **282** |
| AGREE floor 500 | not met | not met |
| DISAGREE floor 100 needs a fast dirty-air share of at least | 32.7 % | **35.5 %** |

**Status: AGREE impossible (as before). DISAGREE possible only if at least 100 of the ≤ 282 fast class-knowable bracketed passes are dirty air after trims.** If they are not, S2-aero is INCONCLUSIVE by the floor, whatever the interval says. Under §11 that does not block DESIGN A or aero: aero is proposed with the weakness printed. It does mean S2-aero can no longer catch a real one-sided / bracketed disagreement in aero in that case. The share is not known before outcomes, so this is "at risk", not "not met".

## 5. Pass class (held up / dirty air / unknown): structure availability

Supported close, not racecraft passes whose cross-fitted class is knowable:

| | Fast | Medium | Slow |
|---|---|---|---|
| Before | 4,080 of 7,249 (56.3 %) | 11,450 of 18,305 (62.6 %) | 11,041 of 17,441 (63.3 %) |
| After | 3,711 of 6,943 (53.4 %) | 10,603 of 17,349 (61.1 %) | 10,162 of 16,534 (61.5 %) |

There is no class-level count floor in §6h; N_F ≥ 2 and N_L ≥ 2 are per-pass floors, and a pass that fails them is `unknown`. The share of `unknown` rises by 1.5-3 points. Two knock-on effects, both registered behaviour, not new rules: fewer passes in the aero contrast, and more laps whose S_aero is "—" ("car-ahead level unknown" when more than half of the lap's fast and medium following corners are `unknown`, §13 item 7). Single-braking-corner classes (fast 15 of 37 races, medium 2 / 43, slow 2 / 43) are structure of corners, not of free passes, and do not change. Ruling 2's skipped corners are not counted here.

## 6. S3 population and F1

| | Fast before | Fast after | Medium before | Medium after | Slow before | Slow after |
|---|---|---|---|---|---|---|
| Near-band passes in the S3 population | 2,467 | 2,308 (−6.4 %) | 5,916 | 5,523 (−6.6 %) | 5,604 | 5,170 (−7.7 %) |
| Groups | 813 | 774 | 2,061 | 1,919 | 1,861 | 1,723 |

(The registered §3 item 8 figure 3,218 / 8,016 / 7,497 is before racecraft and φ drops; the "before" here removes racecraft and φ-unsupported near-band passes, as §11 defines the population.) S3 has no count floor: B_k needs at least one near-band pass per class, and there are thousands. **Met.** Precision: about 7 % fewer passes and groups, so the iid se of B_k rises by about 3-4 % (from about 0.003 / 0.002 / 0.002 s on the d06 basis). The S3 tolerance floor (0.010 s) is three to five of those standard errors, so this barely moves S3's chance of passing.

**F1.** The lap arm's scored lap already excludes any lap with a racecraft pass (§9a), so a free lap never contains a racecraft free pass and ruling 1 changes no lap-arm count (d07: 23,663 scored, 9,504 free, 5,401 supported following, 1,087 supported near band; lap-arm support ≥ 3 free laps unaffected). F1's second leg is corner-level S3 in medium and slow, met above. **Met.**

## 7. Support, φ and θ (per-pass and per-cell floors)

| | Before | After | Change |
|---|---|---|---|
| Supported following (group ≥ 2 free), all | 150,500 (23,008 / 65,511 / 61,981) | 144,123 (22,157 / 62,745 / 59,221) | −6,377 |
| … not racecraft | 133,818 (21,048 / 57,971 / 54,799) | 128,453 (20,286 / 55,658 / 52,509) | −5,365 (as amendment B1 §C) |
| Supported following, φ-unsupported | 12,131 (1,957 / 5,113 / 5,061) | 12,367 (2,040 / 5,144 / 5,183) | +236 |
| Entering β, all bins | 123,123 (19,280 / 53,519 / 50,324) | 117,643 (18,482 / 51,205 / 47,956) | −5,480 (−4.5 %) |
| θ cells with free passes / thin (< 3 drivers) | 329 / 47 (13 / 16 / 18) | 328 / 46 (13 / 16 / 17) | one slow cell loses all its free passes (thin or empty: 47 both) |
| Free / following passes in thin cells | 1,539 / 2,376 | 1,405 / 2,337 | |
| Reference compound changes, of 123 (race, class) | | 2 | |

These floors are per group, per pass or per cell. None has a pass/fail at run level. Passes that fail them are dropped and counted (§6a, §6c) or take the reference curve (§6d), which is registered behaviour.

## 8. What the registration says happens where a floor is not met

| Where | Registered consequence | Does the drop change whether it happens? |
|---|---|---|
| Fast S2-pace below 500 | Cannot be AGREE. Prints "fast-corner bracketed check inconclusive"; **does not block DESIGN A** (§11). DISAGREE (≥ 100, interval wholly outside ±T) still blocks. | No: below 500 before (420) and after (387); still ≥ 100. |
| S2-aero below 500 | Cannot be AGREE. INCONCLUSIVE: aero proposed with the weakness printed (§11). DISAGREE: aero "—". | No for AGREE. For DISAGREE, the drop raises the dirty-air share needed from 32.7 % to 35.5 % of the fast class-knowable passes. |
| S2-aero below 100 (if dirty air < 35.5 %) | Forced INCONCLUSIVE; non-blocking; aero proposed with the weakness. | **Possibly**: this is the one floor the drop moves closer. |
| Medium or slow S2-pace INCONCLUSIVE (interval too wide or straddling ±T, or undefined draws, ruling 4) | **Blocks DESIGN A.** Then FALLBACK (lap level, pace only, aero "—") if F1 passes, else NEITHER (no pace level, aero "—"; the owner decides whether WC-10 continues). | Floors still met; the drop only lowers power (−10 % / −13 % bracketed passes). SG7 measures this on the new structure. |
| SG7 fails on the new structure (S2 can't reach AGREE in medium and slow in ≥ 80 % of no-drift simulations) | Fixed ladder (§17): ±8-lap window, then 0.030 s pace floor, then "S2 unpowered" (S2 leaves the go/no-go table); each a pre-result amendment committed alone. | Not computable from structure; SG7 must be rerun anyway after the amendment (§0a). |
| A per-pass floor (support, φ, N_F / N_L) | Pass dropped and counted, or class `unknown`. | More passes affected, as counted above. |
| Data gate check fails | `FAILED_RESTARTABLE`, nothing read. | No: the gate hashes bytes and counts no passes. |

**Worst honest outcome attributable to the drop:** no floor flips. Medium and slow S2-pace keep their 500-pass AGREE floor with 39-46 % headroom; fast S2-pace and S2-aero were already below 500 and stay there; S1, S3 and F1 have no binding count floor and keep thousands of passes. The real cost is power: about 5 % fewer near-band passes overall and 10-13 % fewer bracketed ones in medium and slow, which makes an INCONCLUSIVE S2-pace in medium or slow (and so FALLBACK or NEITHER) somewhat more likely, and makes a forced-INCONCLUSIVE S2-aero (below 100 dirty-air bracketed fast passes) a live possibility. The size of the first risk is SG7's job, on the post-amendment structure.
