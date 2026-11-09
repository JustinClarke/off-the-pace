# WC-02 results: measurement checks

Written for: the owner, reviewing whether the measurements are good enough to pre-register against.

Scope: the three WC-02 checks, with the rulings DD-WC9 to DD-WC13 applied (recorded in the build log, 2026-10-28). No fit, coefficient, loss curve or gate result is computed here. No number from the archived dirty-air method (DA-03) is used. Sources are the CSVs and notes in this folder.

## Check 1: timing agreement, per race

- Gaps from the WC-01 builder's method (timing line found from track position, C3) agree with the official timing within 0.1 s in **168 of 169 races**. Median per-race error is about 0.045 s.
- **2024 Las Vegas** is over the bar, at 0.116 s. The timing feed's own sector times disagree there. It stays in the set with a feed-inconsistency flag (DD-WC11).
- The first check's 34-race flag came from how it placed the timing lines (lap distance drifts by about 9 m per lap). It is a locator artefact, not a feed problem (`SALVAGE-timing.md`). None of the 34 is dropped.
- Source: `salvage_per_race.csv`.

## Check 2: car-ahead-pits event set

- The 1,124 figure cannot be reproduced under a stated definition (`RECONCILE-1124.md`). It is retired (DD-WC9).
- Restated definition: the follower stays out across laps L-2 to L+2 of the car ahead's pit-entry lap L, and each stop counts once.

| | Count |
| :-- | --: |
| Candidate follower-laps | 2,551 |
| Stays out across the window | 1,970 |
| Distinct car-ahead pit stops behind those events | 1,669 |
| Events where the two cars are on different lap numbers (dropped, DD-WC10) | 246 |
| Events with readings on both sides of the window | 530 (512 distinct stops) |

- Stays-out events by season run from 180 (2020) to 287 (2025).
- Source: `check2_summary_by_season.csv`, `check2_events_with_pit_windows.csv`.

## Check 3: minimum-speed agreement

- Spearman correlation between time and minus minimum speed, per corner class:

| Corner class | Spearman | Sign agreement |
| :-- | --: | --: |
| Fast | -0.64 | 76% |
| Medium | -0.59 | 74% |
| Slow | -0.47 | 68% |

- Recorded as an observation only, with no pass mark (DD-WC12).
- Source: `check3_by_class.csv`.

## Rulings applied

- DD-WC9: 1,124 retired; restated definition used.
- DD-WC10: 246 different-lap events dropped.
- DD-WC11: all races kept; 2024 Las Vegas flagged.
- DD-WC12: minimum speed as observation only.
- DD-WC13: no-loss check moved to the 2-3 s band (above 3 s it holds by construction). This is a rule for the pre-registration, not a result here.

## Open before WC-02 can close

- Owner sight of this file and of the 2024 Las Vegas flag.
- WC-02 is then closed in the build log. Closing it does not start G3, which still waits on the prereg commit question.
