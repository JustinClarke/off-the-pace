# WC-03 pre-registration, amendment A2: a fifth, report-only pass class, `no_reference`

**Status: DRAFT. Not committed, not hashed. Decision recorded 2026-10-28 (see "Decision record" at the end): decided by the owner, delegated to the Opus session on 2026-10-28; not the owner's personal signature.** The owner chose this option (B: register `no_reference` as a fifth class). This file amends `wi/WC-03-preregistration-DRAFT.md` (signed 2026-10-28, SHA-256 `518c3348a619ebf6a964486bbe6313dcdc86c64ae05ca3daed8db202d9653a63`, commit `839e0f4`). The registered text is **not edited**: this file is read beside it (and beside amendment A1), and where they differ this file governs once it is committed and its SHA-256 is recorded on WC-03 in `status/build-log.json`.

**When it was made, stated plainly.** This amendment was drafted on 2026-10-28 (local machine clock, 18:06 +04:00; some earlier build-log entries carry 2026-10-29 stamps), **after** the synthetic G1 (i) test was seen to fail under the registered race-level bootstrap (amendment A1), and after the code review that raised it (review item Q5, build-log entry 2026-10-29T01:00). **No real-data result has been seen:** nothing has been fitted, scored or gated on the pass table, the warehouse or the bronze files, no pass has been classified on real data, no class count exists, and G2 and G3 have not been run. It is a pre-result amendment in the sense of §0. It was not written blind to the synthetic results; those results concern the bootstrap, not the class rule, and nothing in them depends on this change. Whether that calls for any label beyond this paragraph is for the owner to rule.

**Nothing else changes.** No threshold, margin, season split, bin, trim, fit set, curve, contest rule or verdict rule changes. The §6 fit sets are untouched, so no pass enters or leaves the main curve or a class curve because of this amendment.

---

## The change

Sections affected: **§5, row "Pass class"**; **§12a, G1 (vi)**; **§12b, "Counts"**.

A following pass that is not racecraft, whose car-ahead time is known, but which has **no measured own reference** gets a fifth class, `no_reference`, checked after `no_leader_time` and before `held_up`. It is **report-only**: it never enters any fit, because every §6 fit set (main curve and class curves) requires `ref_status = measured`.

## The reason: the registered four-class rule cannot classify these passes

§5 says every following pass gets exactly one class, and G1 (vi) tests that. But the registered tests for (3) `held_up` and (4) `dirty_air` both compare the car ahead's time with `ref_time_s` + 2 × reference spread. Where the driver has no measured reference (`ref_status` ≠ `measured`; the builder's reference rule needs at least 2 clean own passes within ±4 laps, same stint and compound), `ref_time_s` and the reference spread are missing, so neither comparison holds. Such a pass is not racecraft and has a car-ahead time, so under the registered text it falls into **no class**, and the "exactly one" promise of §5 and G1 (vi) is broken for it. WC-01 records 1,117,322 of 2,188,484 kept passes with no measured reference (§2a), so this is not an edge case in the count, although only following passes are classed.

The two other ways to close the gap were: put these passes in `dirty_air` by default (option A), which would mislabel passes whose class cannot be judged and inflate the dirty-air count; or leave them unclassified and weaken G1 (vi) to "at most one" (option C), which hides them. The owner chose B: name them, count them, keep them out of every fit.

Its place in the order (after `no_leader_time`, before `held_up`) changes the class of no pass that the registered rule could classify: a pass reaching step (3) under the registered rule already had a measured reference, and those passes still go to `held_up` or `dirty_air` exactly as before.

## Exact new text

**§5, row "Pass class"** — replace the whole row with:

> | Pass class (every following pass gets exactly one) **(C6, boundary changed: N3; fifth class: amendment A2)** | Checked in this order: racecraft; then, if the car ahead's time is unknown, "no leader time"; then, if the driver has no measured reference of their own, "no reference"; then held up if the car ahead was clearly slower than this driver's normal; otherwise dirty air. No gap, no overlap. "No reference" is counted and reported only. | Priority: (1) `racecraft`; (2) `no_leader_time` if the car ahead's time is missing; (3) `no_reference` if `ref_time_s` or the reference spread is missing (that is, `ref_status` ≠ `measured`); (4) `held_up` if car ahead's time > `ref_time_s` + 2 × reference spread; (5) `dirty_air` if car ahead's time ≤ `ref_time_s` + 2 × reference spread. Class does not decide membership of the main (contest) curve; §6 does, and every §6 fit set requires `ref_status = measured`, so a (3) `no_reference` pass never enters the main curve or any class curve. Only (4) and (5) have class curves. |

(Note on the replaced sentence: the registered row said "All four go into the contest curve". That was always subject to the §6 fit set; under this amendment it reads: (1), (2), (4) and (5) enter the main curve when the pass is in the §6 fit set; (3) never can.)

**§12a, G1 (vi)** — replace the clause "(vi) the class rule puts every following pass in exactly one class;" with:

> (vi) the class rule puts every following pass in exactly one of five classes (`racecraft`, `no_leader_time`, `no_reference`, `held_up`, `dirty_air`; §5, amendment A2), and no `no_reference` pass is in any §6 fit set;

**§12b, bullet "Counts"** — replace with:

> - Counts: passes per class, bin, season and race; `no_reference` passes per season and corner class, with their share of following braking passes (amendment A2; report-only, never in a fit); `no_car_ahead` passes (per season, class, and for the race leader); every §8a drop by reason; unjoined laps; `flat_unknown` and `flat_now_unknown` laps.

Unchanged: §4a, §4b, §6 (fit sets, class curves, estimator), §7, §8, §9, §10, §11, the rest of §12a and §12b.

## What follows, stated so it is not decided silently

- **Class curves (§6) and P2 (§10)** are fitted on `held_up` and `dirty_air` passes in the fit set, as registered. Before this amendment a no-reference pass could not reach either (no class, and outside the fit set); after it, it still cannot. P2 is unchanged.
- **Under-attack difference (§12b)** uses the main fit set, which has no `no_reference` pass. Unchanged.
- **Coverage per team (§5)** is unchanged: it is the share of following braking passes with a measured reference, over all following braking passes. The `no_reference` count is not its exact complement, because a racecraft or `no_leader_time` pass without a reference keeps its earlier class.
- **Code.** `transform/tasks/wake_calibration/estimator.py` already implements this order (`PASS_CLASSES`, `pass_class`), and `tests/test_estimator.py` already tests it (`test_g1_vi_*`, `test_no_reference_passes_never_enter_a_fit`). Both are uncommitted; no code changes with this amendment.

## Decision record

**Decided 2026-10-28. Decided by the owner, delegated to the Opus session on 2026-10-28; not the owner's personal signature.**

- **Option B is adopted:** `no_reference` is registered as a fifth, report-only pass class, checked after `no_leader_time` and before `held_up`, as written in "Exact new text" above (§5 "Pass class" row, §12a G1 (vi), §12b "Counts"). Options A (default to `dirty_air`) and C (leave unclassified, weaken G1 (vi)) are not adopted.
- A `no_reference` pass never enters any §6 fit set, main curve or class curve.
- No threshold, fit set, contest rule, verdict rule or other registered text changes with this decision.

## After the decision is recorded

1. Commit this file alone.
2. `shasum -a 256 _roadmap/_wake-calibration/wi/WC-03-amendment-A2-no-reference-class.md`; record the digest and commit on WC-03 in `status/build-log.json`.
3. Nothing is fitted or classified on real data before step 2 (BUILD-ORDER rule 4).
