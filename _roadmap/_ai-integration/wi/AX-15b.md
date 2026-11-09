# AX-15b — Make the dirty-air-dependent cards live once wake calibration is settled and the label is re-sealed if it moves

**Group:** 5 held classes · **Depends on:** `AX-15a` · **Model / cost:** `opus-5`, 2-3d · **Unblocks:** `AX-16`
**Blocker:** `XW` (external, not an owner call): wake calibration reaches WC-06 (app output) with its labels. WC-10e is still blocked on amendment B2 and DD-WC23, so this is weeks away. **Post-v1:** nothing in the v1 launch (AX-19, AX-20) waits on this item.
**HD2 is re-ruled at that gate.** It was ruled C on 2026-11-07 ("undecided; revisit when wake calibration reports"). At the gate the owner picks:
- **A, sits beside the flat tax:** only the dirty-air price stays held.
- **B, replaces it:** the driver-skill residual moves.

**The label may move.** Under B, every rating, ghost-car and constructor number is rebuilt on a new transform label version, sealed the way CO-33 sealed v16. No card from the v16 build survives the flip.

Content carried from the old AX-15 (lift procedure and builders); the held stubs are AX-15a.

**Sources:**
- AX-15a's `_evidence/ax-15a/classes.md` and stub registry, and AX-07's lineage (`_evidence/ax-07-lineage/`).
- `_roadmap/_archive/_wake-calibration/wi/WC-05-*.md` and `WC-06-app-output.md`, as landed.
- TX-05's `mart_build_provenance`, `policy.json` (`VALIDATION_GRADE_BELOW_PASS`, `PURE_PACE_WITHIN_ERA`), and design 2.3-2.4.

---

## What lifts the hold

- **HD2 = A.** The owner records the ruling. Build the T\* values on the current label, then flip `HELD_CLASSES` to drop `T*`. Price kinds stay held.
- **HD2 = B.** All of these first:
  1. XW resolved, with WC-05 and WC-06 landed.
  2. A new label version sealed, with `label_version` bumped in TX-05's vars alongside `label_stability_baseline.csv`.
  3. The byte-oracle baselines re-taken by the owner.
  4. Data re-exported under the HD12 process (the owner's yes).

  Then build and flip.
- **Dirty-air price kinds** go live only through AX-16, never through this item.

## Method

1. Read HD2's new ruling, AX-15a's class list and WC-05/06 as landed. **Re-run AX-07a's column lineage on the new build:** WC may redefine the exposure classification (AX-05.md:16), so a source that was T can become T\*, or the reverse. Record every change.
2. For each T\* kind, replace the stub builder with the real `cards.ts`. That is `enumerate`, plus `build` through the feature's own `queries.ts` and `transform()` run headless (AX-04), plus `pageParams`, the interval and `n` mapping, and `caveatRules`, per design 2.4.
3. **Intervals.** Take them from the mart (`se_1`, `ci_bootstrap`, `ci_normal_95`, or `ci_order_stat_median` for the race rating if it was ever T\*). Otherwise refuse the card with a reason; never invent an interval. Note: design-ai-access.md:190 calls the rating-mart CI a `lap_noise_band`, which is stale after TX-01.
4. **Policy hooks.**
   - Isolation cards carry `grade` from the trust label, so `VALIDATION_GRADE_BELOW_PASS` can fire.
   - Pure-pace cards carry the fit era, so `PURE_PACE_WITHIN_ERA` can fire.
   - Skill kinds carry `skill_measure` (AX-21 glossary).
5. **Versions.** Read every card's `versions.label_version` from `mart_build_provenance`, never hard-coded. A card whose label version differs from the manifest's provenance is refused.
6. **The flip.** `HELD_CLASSES` drops `T*`, and the manifest gets `classes_live:["T","T*"]` with price kinds still held. Update AX-21's playbook: held links become recipe links, the glossary statuses change, and `system.md` is regenerated. Re-run AX-13 on the affected groups. The full bar is re-run only if the owner asks.
7. **A new snapshot is a new AX-19 run.** The v1 `freeze.json` is never edited.

## Acceptance

- As in AX-07: every card has every field or is refused with a reason, `interval.kind` is never relabelled, and the cards match the page for 20 (driver, race) pairs across at least 3 seasons.
- **Before the flip.** The real values build in a test-only mode, and 100% of published T\* cards are still held. The switch is the only difference between the two states (a test runs both).
- **After the flip.** Every price kind is still held (AX-15a's deny-list test still passes), and every card's `label_version` equals the provenance. Under HD2-B it is no longer v16.
- `VALIDATION_GRADE_BELOW_PASS` and `PURE_PACE_WITHIN_ERA` fire on fixtures.
- No kind reads `flag_chance_lookup.json` (AD5) or a DA-03 number.
- On a scratch export, `export_app_data.py --check` is stable on re-run.

## Tests to add

`cards.<feature>.test.ts` for each T\* feature, `parity.t-star.test.ts`, `registry.flip.test.ts` (held, flipped, price kinds still held), `label-version.test.ts`, and AX-15a's deny-list test reused unchanged.

## Definition of done

The owner's HD2 re-ruling and the yes to flip are recorded in the log. The lineage changes and the lift steps taken are saved to `_evidence/ax-15b/`. The tests pass, and AX-21 and AX-13 are updated as in step 6. Do not commit.
