# WC-03 pre-registration, amendment A1: circuit-then-race curve bootstrap

**Status: DRAFT. Not committed, not hashed. Item 1: decision recorded 2026-10-28 (see "Owner's decision" under item 1): decided by the owner, delegated to the Opus session on 2026-10-28; not the owner's personal signature.** Item 2 is **pending owner confirmation**. This file amends `wi/WC-03-preregistration-DRAFT.md` (signed 2026-10-28, SHA-256 `518c3348a619ebf6a964486bbe6313dcdc86c64ae05ca3daed8db202d9653a63`, commit `839e0f4`). The registered text is **not edited**: this file is read beside it, and where the two differ this file governs once it is committed and its SHA-256 is recorded on WC-03 in `status/build-log.json`.

**When it was made, stated plainly.** This amendment was drafted on 2026-10-28, **after** the synthetic G1 (i) test was seen to fail under the registered race-level bootstrap. No real data has been read for it: nothing has been fitted, scored or gated on the pass table, the warehouse or the bronze files, and G3 has not been run. It is a pre-result amendment in the sense of §0 (no curve, contest score, verdict or real-data gate result exists), but it was **not** written blind: the owner chose it knowing the synthetic numbers below. Whether that calls for any extra label beyond the disclosure in this paragraph is for the owner to rule.

**Nothing else changes.** B = 1,000 draws, seed 20261027 (numpy `default_rng`), 95 % percentile intervals (2.5th to 97.5th percentile), whole-chain refit in every draw (REML, then the non-increasing step), the G1 (i) bar (90 % of 200 simulations, each with 200 draws), and every threshold, margin, season split and decision rule in the registration are unchanged.

---

## Item 1. Curve bootstrap: resample circuits, then races (owner decision)

### The change

Sections affected: **§6 "Intervals"** and **§8c "Allowing for chance"** (with the matching row of the §0 table, "Chance"). The fit side of every bootstrap draw becomes a two-stage resample: circuits with replacement, then races with replacement within each drawn circuit. A circuit drawn twice enters the curve fit as two distinct circuit groups, and its corners as two distinct corner groups. The held-out (2025, and 2021 for the older cars) side is unchanged: races resampled with replacement, independently.

### The reason: G1 (i) failed under race-level resampling

G1 (i) (§12a) asks that the estimator's 95 % intervals cover the true curve in at least 90 % of 200 simulations, each with 200 draws. Coverage is read **per bin** (each of the 8 bins on its own; see "Clarifications" below).

The test simulates passes from the registered model itself (§6): corner loss = bin effect + circuit random effect + corner random effect, plus a race shock and noise. Design: 68 races on 23 circuits (each circuit hosting about 3 races, as 2022-2024 does), 8 corners per circuit, 30 passes per (race, corner); standard deviations circuit 0.05 s, corner 0.05 s, race 0.03 s, noise 0.15 s; true curve 0.30, 0.22, 0.16, 0.11, 0.07, 0.04, 0.02, 0.01 s.

Per-bin coverage, 200 simulations x 200 draws (synthetic data only):

| Design | Race-level (registered §8c) | Circuit-then-race (this amendment) |
|---|---|---|
| Registered model (circuit 0.05, corner 0.05, race 0.03) | 0.600, 0.645, 0.645, 0.635, 0.600, 0.595, 0.615, 0.610 (hits of 200: 120, 129, 129, 127, 120, 119, 123, 122). **Fails** the 90 % bar in every bin. | 0.945, 0.930, 0.940, 0.930, 0.910, 0.935, 0.915, 0.930 (hits of 200: 189, 186, 188, 186, 182, 187, 183, 186). Passes, every bin at or above 0.90; the lowest bin (1.0-1.5 s) is 0.910, one Monte Carlo standard error (about 0.021) above the bar. |
| Race shocks only (no circuit or corner effect) | 0.905 to 0.965 per bin, passes | 0.995, 0.985, 0.975, 0.975, 0.980, 0.975, 0.980, 0.985 (hits 199, 197, 195, 195, 196, 195, 196, 197); passes, conservative |

Circuit-then-race numbers are from the G1 test itself under the adopted code (`test_g1_i_interval_coverage_registered_model` and `..._race_shocks_only`, 2026-10-28 run, 93 passed). They equal the earlier scratch comparison bin for bin.

The race-level row for the registered model was re-run on 2026-10-28 through the estimator's own comparison path after the code change and reproduced the earlier numbers exactly.

Why race-level fails: the registered model has a random effect per circuit, and the 68 fit races sit on about 23 circuits. A race-level resample almost always keeps every circuit in the draw, so the draws do not reproduce the spread that the circuit effects put into the bin estimates; the intervals come out too narrow. Resampling circuits first carries that spread.

### Owner's decision

The owner decided on 2026-10-28, in session, to adopt circuit-then-race resampling for the curve bootstrap, to disclose it as this amendment, and to keep the 90 % bar and every threshold unchanged. (The preceding build-log entry is stamped 2026-10-29T01:00+04:00.)

**Decision record (item 1).** **Decided 2026-10-28. Decided by the owner, delegated to the Opus session on 2026-10-28; not the owner's personal signature.** The curve bootstrap on the fit side is the circuit-then-race bootstrap: circuits resampled with replacement, then each drawn circuit's races with replacement, a circuit drawn twice entering the fit as two separate circuit and corner groups; the held-out side stays race-level. The exact new text below for §0 "Chance", §6 "Intervals" and §8c is adopted as written. B = 1,000, seed 20261027, the 95 % percentile interval, the G1 (i) 90 % bar and every other threshold are unchanged. The decision date is 2026-10-28. This record covers item 1 only; item 2 and the "Clarifications" list below are not decided by it.

### Exact new text

**§0 table, row "Chance"** — replace the value cell with:

> circuit-then-race cluster bootstrap on the fit side (circuits resampled with replacement, then each drawn circuit's races; amendment A1), race-level on the held-out side; **1,000 draws, fixed**, seed 20261027, 95 % percentile intervals, no reruns

**§6, bullet "Intervals"** — replace with:

> - **Intervals:** cluster bootstrap (§8c), circuits then races (amendment A1). Each draw resamples the fit circuits with replacement, then each drawn circuit's fit races with replacement, and refits the whole chain, including the non-increasing step. A circuit drawn twice enters the fit as two separate circuit groups, and each of its corners as two separate corner groups.

**§8c, "Plain English"** — replace with:

> - Plain English: to see how much of a difference could be luck, the data are reshuffled 1,000 times. On the fit side, each reshuffle first draws circuits with replacement, then, for each drawn circuit, draws that circuit's races with replacement; a circuit drawn twice is treated as two different circuits. The held-out races are drawn with replacement, as races. Each reshuffle refits the curve and θ_now on the drawn fit races and rescores the drawn held-out races. The interval is the middle 95 % of the 1,000 results. The number 1,000 is fixed now; it is not reduced or increased after anything is seen, and the run is not repeated.

**§8c, "Formal", bullet "Method"** — replace with:

> - Method: nonparametric cluster bootstrap. **Fit side (amendment A1):** two stages. (1) The circuits of the fit races (the §6 circuit key) are resampled with replacement to their count. (2) For each drawn circuit, in draw order, that circuit's fit races are resampled with replacement to that circuit's own race count. A circuit drawn twice enters the curve fit as two distinct circuit random-effect groups, and each of its corners as two distinct corner random-effect groups; within one copy a race drawn twice counts twice (frequency weight) and stays in that copy's circuit and corner groups. **Held-out side (unchanged):** the held-out races (24) are resampled with replacement to their count, independently of the fit side. On either side a race drawn more than once counts each time, and its stints count as separate stints. The old flat penalty is not re-estimated in a draw (it is the shipped value); θ_now and the measured curve are, both on the same drawn fit races.
> - Draw order: one numpy `default_rng(20261027)`; per draw, first the circuits (`integers(0, n_circuits, n_circuits)` over the sorted circuit list), then each drawn circuit's races (`integers(0, m, m)` over that circuit's sorted race list), then the held-out races (`integers(0, n_held, n_held)` over the sorted held-out list).

**§8c, "Formal", bullet "Stated limitation"** — add one sentence at the end:

> On the fit side the effective number of clusters is the number of distinct circuits in 2022-2024 (about 23; 2018-2020 for the older cars), not 68 races, so the curve intervals rest on a small number of clusters too.

Unchanged in §8c: "Draws" (B = 1,000, seed 20261027, no fallback count), "Interval" (95 % percentile), "Minimum races" (G5).

**§12a G1 (i)** — text unchanged. Under this amendment G1 (i) is computed with the circuit-then-race bootstrap.

### What follows from item 1, stated so it is not decided silently

These are readings the code uses; the owner confirms them with this amendment or rules otherwise:

- **θ_now** is refitted in each draw on the same drawn fit races as the curve (the circuit-then-race multiset), each occurrence's stints separate. A circuit copy has no meaning for θ_now (no circuit term), so only the race multiplicities matter.
- **Same draws everywhere on the fit side:** the held-up and dirty-air class curves, the under-attack difference (§12b) and the ±2/±6 sensitivity runs use the same plan as the main curve. The under-attack difference is a plain pass mean, so only race multiplicities matter there too.
- **§11 pit-stop figure:** its "95 % race-bootstrap interval" on the adjusted jump is not changed by this amendment. Where the ratio needs curve draws (predicted drop), they come from the same plan.
- **The race-level resample** stays in the code only as a labelled comparison (`BOOTSTRAP_COMPARISON = "race"`), for synthetic side-by-side checks. It is never used for a reported interval.

---

## Item 2. A gap bin with no fit pass — **PENDING OWNER CONFIRMATION**

### The change

The registration does not say what happens when a gap bin has no fit pass in a corner class, in the point fit or in a bootstrap draw. The bin's fixed effect is then not identified. The code (review item Q6, 2026-10-29 log entry) handles it as below, fixed before any real run. Under item 1 a draw can drop whole circuits, so an empty bin in some draw is more likely than under race-level resampling; this makes the rule more important, not less.

### Exact new text (proposed)

**§6, new bullet after "Intervals":**

> - **Empty gap bin.** If, in a corner class, a gap bin has no fit pass, in the point fit or in any of the B draws, that bin is not estimated and nothing is patched: no bins are merged, no prior is used, and no draw is skipped or redrawn (B stays 1,000; a draw with an empty bin is recorded as empty). For the **main curve** this means **no verdict** (§9). For a **class curve** (held up, dirty air) that corner class is reported as "not estimable", with no estimate and no interval; the other corner classes stand. If the dirty-air curve is not estimable in the fast or slow class, P2 cannot be computed, so W3 cannot be assessed: **no verdict**.

**§9, verdict table, first row** — replace the left cell with:

> Any check in 12a fails, any minimum in 12a is not met, or the main curve has a gap bin with no fit pass in the point fit or in any bootstrap draw (§6)

**§12a, new item after G6:**

> - **G7 curve identified:** in every corner class, every gap bin of the main curve has at least one fit pass in the point fit and in each of the 1,000 draws. If not: no verdict, and the scorecard's first line says which corner class, which bins, and in how many draws.

### Open within item 2

- The P2 consequence (dirty-air curve not estimable in fast or slow → no verdict) is a proposal here; the code marks the class curve "not estimable" but does not yet wire it to P2 or W3 (P2 is WC-04 work).
- Whether this is G7 (a setup check) or a row of §9 only is the owner's choice; the wording above does both.

---

## Clarifications already in the code (for confirmation with this amendment)

Recorded in the 2026-10-28/29 build-log entries and in code comments; listed so the owner can confirm them in one place:

- G1 (i) coverage is read **per bin**: each of the 8 bins must reach 0.90 on its own.
- The §6 corner random effect is **nested** in the circuit (`circuit|corner_id`).
- The G1 (i) simulation design is the registered model's own (circuit and corner effects, race shock, about 3 races per circuit), as above.

## After the decision is recorded

1. Commit this file alone.
2. `shasum -a 256 _roadmap/_wake-calibration/wi/WC-03-amendment-A1-circuit-bootstrap.md`; record the digest and commit on WC-03 in `status/build-log.json`.
3. Nothing is fitted on real data before step 2 (BUILD-ORDER rule 4).
