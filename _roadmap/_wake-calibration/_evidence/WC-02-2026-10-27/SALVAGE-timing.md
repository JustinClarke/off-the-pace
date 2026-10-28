# WC-02 check 1 salvage: why telemetry and the timing feed disagree

Run 2026-10-27, scratch only. No fit, coefficient, loss curve or gate result. No archived dirty-air (DA-03) number.
Commands and hashes: `PROVENANCE-additions.txt`. Corrections were declared in advance in `SALVAGE-predeclared.txt`,
which also records two amendments. Amendment 2 is post-hoc.
Threshold unchanged: a race is flagged when its pooled median absolute pair gap error is over 0.1 s.

## Finding in one paragraph

Most of the 34-race flag came from the way check 1 located the lines, not from the timing feed and not from the
WC-01 builder's gaps. Check 1 placed each timing line at a fixed distance into the lap. That distance comes from
integrating the car's speed from the lap start, and it drifts by about 9 m from car to car and lap to lap (median
spread of the lap's integrated length, up to 21 m). The drift grows with distance into the lap, which is why S2
was worse than S1. It is also worse on long laps such as Baku, Spa and Las Vegas, and in the 34 flagged races
(lap-length spread 12.1 m against 9.4 m overall). When the line is located by the car's position on the track
instead, either directly (C2) or the way the builder does it (C3: from the corner apex found by position, plus a
fixed distance), the disagreement falls to about 0.045 s per race. With either locator, 168 of 169 races agree.
The one race that still fails, 2024 Las Vegas, fails because of the feed's own sector times.

## Numbers (command 3 = salvage.py, command 4 = analyse.py, command 5 = feedcheck.py)

| | check 1 (lap distance) | C2 position | C3 builder-style |
|---|---|---|---|
| median per-race error, all 169 races | 0.0756 s | 0.0451 s | 0.0451 s |
| median per-race error, the 34 flagged | 0.1187 s | 0.0536 s | 0.0500 s |
| worst race | 0.2674 s (2021 Belgium) | 0.1010 s (2024 Las Vegas) | 0.1164 s (2024 Las Vegas) |
| races over 0.1 s | 34 | 1 | 1 |

Source: `salvage_per_race.csv` (command 4). The check 1 column is the earlier `check1_pooled_per_race.csv`.
C2 and C3 are scored on the same 288,806 pairs.

- **The dependence on the line is gone.** Check 1's locator (C0), on the S1 and S2 crossings all four methods locate: S1
  0.058 s, S2 0.098 s (median over races). C2: S1 0.044, S2 0.045, finish 0.043 (command 4).
- **The finish-line "-0.085 s constant" is an artefact, not a timing offset.** Every lap's telemetry starts and ends
  exactly at the feed's lap start and lap end times (checked: difference 0.000 s on every lap, 2023 Azerbaijan and
  2018 Austria, inline command 6). Placing the finish at the median lap length therefore always lands slightly early
  (median -0.0847 s, range -0.24 to -0.04). It also cannot place cars whose lap integrates shorter, which is why check 1 had few
  finish pairs. Located by position, the finish constant is 0.000 s (largest 0.020 s).
- **Rescaling each lap to the median length (C1) also works on S1 and S2** (0.0426 s median), which confirms the
  drift is roughly proportional. It is not admissible, because it uses each lap's feed-defined length. At the finish line
  it is circular (error exactly 0).
- **What remains.** A per-race constant per line is about 0.5% of the variance; it cancels in gaps. A per-car constant
  is about 13% (median). Sampling: pairs where a car's samples are more than 0.3 s apart at the line have a median
  error of 0.06 s, against 0.035 to 0.039 s otherwise (about 6% of pairs). Close pairs are slightly worse (0.048 s under 0.5 s apart, against
  0.034 s at 2 to 3 s). Since 2022 the error has been higher (median 0.05 s, against 0.02 to 0.03 s in 2018-2021); the cause is not settled.

## Races that still need a note

- **2024 Las Vegas: still over 0.1 s (C2 0.101, C3 0.116).** At S1 and S2 each car carries its own constant offset
  against the feed, from -0.30 to +0.23 s, roughly the same at both lines and steady from lap to lap (spread 0.02 to 0.06 s).
  At the finish it agrees (0.057 / 0.066 s). In this race the feed disagrees with itself. Its recorded S1 clock time
  differs from lap start plus the S1 sector duration by a per-driver constant of 0 to 0.52 s, and those constants
  roughly mirror the telemetry offsets. Two independent telemetry locators agree with each other and with the
  finish line, so the fault is most likely in the feed's S1/S2 clock times, not in the telemetry. **Post-hoc only:**
  scoring against feed times rebuilt from the sector durations brings 2024 Las Vegas to 0.066 / 0.081 s. The same
  rule breaks 2018 Azerbaijan (0.117 / 0.147 s) and makes 101 of 169 races worse, so it is not a usable general
  correction and was rejected (command 5, `salvage_feed_rebuilt_per_race.csv`).
- **2021 Belgium agrees (0.055 / 0.073 s), but on only 45 pairs.** The race ran a few laps behind the safety car.
  Agreement there is thin evidence.
- **2018 Azerbaijan (C3 0.094) and 2023 Las Vegas (C3 0.089)** pass, but close to the line.
- **2022 Japan**: C1 could not be computed (the race's median lap length came out empty), so the four-method S1/S2
  comparison is blank. C2 and C3 agree (0.052 / 0.050 s).

## What this means for the pass table

The builder's gap uses the C3 construction: the apex located by position, plus distance offsets of a few hundred
metres. So check 1's flag measured a weakness in check 1, not in the pass table. Against the feed, the builder's way
of measuring agrees in 168 of 169 races. Nothing in the builder needs changing for this. Keeping all 34 races, as the owner ruled, stands. The
stated risk can be narrowed: 2024 Las Vegas, where the feed's sector clock times are internally inconsistent, and
the residual gap noise of about 0.045 s median (0.05 s since 2022).

## Choices made by looking at the data (risk for the owner)

1. The mechanism (lap-distance drift) and the C0-C3 candidates were written down after seeing check 1's per-race
   table, which already showed S2 worse than S1. They were fixed before any corrected number was computed.
2. Amendment 1 came after a 3-race test run (2018 Austria, 2021 Belgium, 2023 Azerbaijan). It dropped C1 and C0 at
   the finish from the verdict because they are circular. No threshold or parameter changed.
3. Choosing C3 as "the builder-faithful view" rests on reading the builder's code, not on the results.
4. The feed-rebuild idea (Amendment 2) was chosen after seeing 2024 Las Vegas. It is reported only as a diagnostic and
   is not used.
5. C2 and C3 still use the feed once per race per line, to place the line, exactly as check 1 did. The agreement
   they show is agreement on gaps, not an independent absolute timing.

## Not settled

- Which feed field is wrong in general. In most races the recorded clock times agree with telemetry and the
  "lap start + duration" reconstruction does not, but in 2024 Las Vegas it is the other way round. A third timing
  source would be needed.
- Why the error is higher since 2022.
- Some races' lap start times sit far from the recorded S1 clock time minus the S1 duration (for example 2023 Dutch,
  median 2.15 s). Telemetry laps are cut at those lap start times, so a pass close to the start/finish line could carry the wrong lap
  number there. This does not move a position-anchored gap, but it was not checked against lap labels.
