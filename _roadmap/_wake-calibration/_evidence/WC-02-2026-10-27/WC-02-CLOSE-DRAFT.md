# WC-02 closing draft: results and rulings needed

Draft for owner review. Not committed, not recorded in the build log. Numbers were re-read from the CSVs in this folder on 2026-10-28. No fit, coefficient, loss curve or gate result was computed. No number from the archived dirty-air method (DA-03) is used.

## Check 1: timing agreement, per race

- Method used by the WC-01 builder (line found from track position, C3). Source: `salvage_per_race.csv`.
- 168 of 169 races have a median absolute pair error at or under 0.1 s. Median per-race error across races is about 0.045 s.
- The one race over 0.1 s is 2024 Las Vegas (0.116 s). The feed's own sector times disagree there. Recorded as a flagged race, not dropped.
- The first check (line placed by lap distance) flagged 34 races. That flag came from the locator, not the feed (`SALVAGE-timing.md`).
- Races dropping out at the 0.1 s bar: 1 (2024 Las Vegas). **Owner needs to see this.** It is the only race that fails under the method the pass table uses.

Ruling needed: DD-WC11 (keep all 34 flagged races). Recommendation: retire the 34-race flag as a locator artefact and keep all races, with 2024 Las Vegas marked as a feed-inconsistent race.

## Check 2: car-ahead-pits event set

- The 1,124 figure is not reproducible under a stated definition. It comes from a script with no window and no stop-level count (`RECONCILE-1124.md`).
- Under the restated definition in `check2_summary_by_season.csv` and `check2_events_with_pit_windows.csv`:
  - 2,551 candidate follower-laps; 1,970 where the follower stays out across L-2 to L+2.
  - 1,669 distinct car-ahead pit stops behind those 1,970 events (one count per stop).
  - 246 of the 1,970 pair cars on different lap numbers.
  - 530 events have readings on both sides of the window; they hold 512 distinct stops.
- Per-season stays-out counts run from 180 (2020) to 287 (2025).

Rulings needed:
- DD-WC9: retire 1,124 and use the restated definition. Recommendation: yes.
- DD-WC10: drop the 246 different-lap events. Recommendation: yes.

## Check 3: minimum-speed agreement

- Per corner class (`check3_by_class.csv`), Spearman between time and minus minimum speed: fast -0.64, medium -0.59, slow -0.47. Sign agreement 76%, 74%, 68%.
- Recorded as an observation only, with no pass mark.

Ruling needed: DD-WC12. Recommendation: yes, observation only.

## Other ruling needed

- DD-WC13: no-loss check moved to the 2-3 s band. Recommendation: yes; above 3 s the check holds by construction.

## What closing WC-02 still needs

1. Owner rulings on DD-WC9, DD-WC10, DD-WC11, DD-WC12 and DD-WC13.
2. Owner sight of the races that drop out (2024 Las Vegas, and the 34-race flag reversal).
3. A results file in this folder with the same numbers, once the rulings are in.

Separately, G3 (WC-03 prereg §12a) is blocked by BUILD-ORDER rule 4 until the prereg is committed alone. That is independent of WC-02 closing.
