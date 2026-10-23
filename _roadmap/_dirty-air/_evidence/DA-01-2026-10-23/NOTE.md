# DA-01 Phase 0 audit: evidence note (2026-10-23)

**All numbers are PROVISIONAL.** They come from stale dev (watch W1) and must be re-run after CO-17. See PROVENANCE.txt for how this run limited the exposure: it read only staging views over bronze and rebuilt the crossing-order table itself.

Coverage: 171 races, 2018-2025. 2018 has 19 races in telemetry; rounds 1 and 2 (Australia, Bahrain) are in laps and results but have no telemetry. There are 68.1M position samples and 58.9M green samples.

## Verdicts

| Gate / stop rule | Verdict | Numbers |
|---|---|---|
| Continue: >= 90% of green samples valid | **UNSETTLED** (depends on a definition) | FastF1 car ahead known: 94.1%. On-track car ahead known (crossing order): 99.98%. Design-note literal (any lapped car ahead is invalid): **88.6%**, and 85.4-88.4% per season in 2018-21. Lapped car ahead invalid only when within 3 s: **97.0%**. |
| Continue: median gap disagreement < 0.1 s for gaps < 2 s | **PASS** | Signed median +0.0011 s (<1 s) and +0.0005 s (1-2 s). Median absolute 0.067 s and 0.063 s. n = 66,237 and 66,765 pairs. |
| Stop: gap unreliable under 1 s | **Not triggered** (with a caveat) | The bias is zero at every sub-band. Per-pair noise: p90 absolute error 0.20 s; 85% of pairs land in the same beta band and 99.6% within one band. Under 0.25 s, 14.7% of pairs have the order flipped. |
| Stop: spacing differs by season in a way that cannot be corrected | **Not triggered** | There are three regimes (below). All can be corrected with the design's dt_i weight; under 0.25% of samples have dt > 1 s. |

**Overall: UNSETTLED.** Gate B and both stop rules are fine. Gate A passes or fails depending on whether a lapped car far up the road invalidates a sample. Recommendation: treat a lapped car ahead as invalid only when it is within the dirty-air range (3 s). Beyond 3 s the sample sits in the reference band whoever the car is. On that reading Gate A passes in every season (95.5-98.5%). This needs a ruling before DA-02.

## 1. Sample spacing (position channel, on track)

results/01_spacing_*.csv

| Seasons | Cadence | p10 / p50 / p90 (s) | Races |
|---|---|---|---|
| 2018-19 | fixed 0.30 s grid (97% exactly 0.30, 3% 0.20) | 0.30 / 0.30 / 0.30 | 19 + 21 |
| 2020-21 | fixed 0.22 s grid (95.5% 0.22, 4.5% 0.20) | 0.22 / 0.22 / 0.22 | 17 + 22 |
| 2022-25 | jittered, 0.06-0.5 s | 0.16 / 0.24 / 0.38 | 22 + 22 + 24 + 24 |

Every race in a season has the same per-race median, so the cadence is a property of the season and not of the race. The "0.30 s" figure in the design note holds only for 2018-19.

## 2. Green samples, car ahead, NULL distance

results/02_*.csv, 05_*.csv

- **Green definition used here.** A green sample has pos Status OnTrack, session track status '1' at that instant, lap >= 2, and is outside the driver's own pit window. The "2 laps after a restart" rule is not applied.
- **How many samples are green.** 81-90% of samples per season.
- **Missing track-status timeline in two 2018 races.** In 2018_3 (China) the timeline only starts around lap 30, and in 2018_11 (Germany) around lap 29. Samples with no known flag state are counted as not green (02b).
- **NULL distance.** `distance_to_ahead_m` is NULL on 5.08% of green samples (4.98-5.33% per season). Every NULL also has no DriverAhead.
- **Where NULLs fall.** 93.9% of leader samples have NULL distance, against 0.01% for P2+. The NULL is the race leader, not missing data.
- **Lapped car ahead on track.** For 11.7% of green bins the on-track car ahead is a lapped car: 14-15% in 2018-21 and 8-11% in 2022-25. Only 3.2% have that lapped car within 3 s.

## 3. Gap agreement with the timing feed

results/04_*.csv, 04b_*.csv

**Method.** The truth is the timing feed's sector-line session times (S1 and S2). The car ahead is the car that crossed the line just before. The estimate is the design's g_i: the time each car's position-channel relative_distance reaches that line's location (median per race), interpolated linearly, then differenced. 293,675 green pairs. S3 (the finish line) was left out because FastF1's lap slicing makes that comparison circular.

| Timing gap | n | Median diff | Median abs | p25 / p75 | p90 abs | p99 abs | abs > 0.1 s |
|---|---|---|---|---|---|---|---|
| < 1 s | 66,237 | +0.0011 | 0.0666 | -0.065 / +0.069 | 0.197 | 0.627 | 33.0% |
| 1-2 s | 66,765 | +0.0005 | 0.0629 | -0.062 / +0.064 | 0.185 | 0.533 | 30.5% |
| >= 2 s | 160,673 | -0.0003 | 0.0630 | -0.064 / +0.062 | 0.185 | 0.597 | 30.7% |

- **By era.** Median absolute error is 0.053-0.061 s in 2018-21 and 0.067-0.078 s in 2022-25. In 2022-25 it does not depend on the bracketing sample interval (04b_noise_by_era_and_bracket), which suggests noise in the timestamps themselves rather than interpolation error. Because the noise level differs by era, the attenuation of beta will also differ by era. Phase 2's era split covers this, but DA-03 should model the error.
- **By line.** S2 is noisier than S1 (0.08 vs 0.05 s median absolute).
- **Incumbent measure.** FastF1 distance divided by speed is close under 1 s (median -0.011 s) but biased at 1-2 s (-0.13 s) and above 2 s (-1.04 s).

## 4. Does DriverAhead include lapped cars?

**No.** DriverAhead follows race order (results/03_*.csv).

- **When the on-track car ahead is a lapped car,** DriverAhead names it in only 1.3% of green bins. It is NULL in 47% and names the race-order car further up the road in the rest.
- **For the leader,** DriverAhead is NULL (97.6% of leader samples are unresolved).
- **On the same lap,** it agrees with crossing order in 95.8% of bins.
- **Residual.** In 1.16% of named cases the named car is on a lower lap at that bin. About 38% of these are cars passed within the last 5 s (update lag). The rest are unresolved; they may be an artefact of the pit-window exclusion in this audit (03b).

**Consequence.** The design's crossing-order car ahead, not DriverAhead, has to identify lapped cars.

## 5. DRS code 8

**Reliable, including in 2018** (results/06_*.csv).

- **Presence.** Code 8 appears in every race that ran DRS. The four races without it (2021 Belgium, 2021 Turkey, 2022 Japan, 2024 Sao Paulo) also have no DRS openings: these are wet races, not data loss.
- **Openings follow an 8.** 98.6-99.6% of openings come straight after an 8 episode, in every season; 2018 is 99.5% (97.5-100% per race).
- **8s lead to an opening.** 77-85% of 8 episodes end in an opening; 2018 is the lowest at 77%.
- **Gap when 8 is showing at a timing line.** The median timing gap is 0.63-0.72 s, and the gap is under 1.2 s in 90% of 2018 cases and 93-99.5% in later seasons.
- **Openings on laps 1-2.** None in 2018-23. 3-5% in 2024-25, consistent with DRS being enabled one lap earlier from 2024. That rule date was not verified here.

## 6. Marshal sectors 2018-2020

**Available for 58 of 59 races** (results/07*.csv).

- **What the API returns.** The MultiViewer circuit API (FastF1's source for `get_circuit_info`) returns marshal sectors with x/y for every 2018-2020 race except the 2020 Sakhir GP (Outer Track), which has 0.
- **Caveat: a later year's layout for ten 2018 races.** For 10 of the 21 2018 races (AUS, BHR, AZE, ESP, MON, CAN, FRA, AUT, GBR, GER) the API serves the 2019 layout. The payload's `year` field says 2019 (07c).
- **Consistency with race control.** Race-control messages carry a sector number for every sector-scope message in 2018-2020, and that number never exceeds the served layout's sector count except at Sakhir 2020 (max 11, layout 0) (07e).
- **FastF1 path.** FastF1's own path failed on this machine: livetiming returned 401 for session info. Ingestion through FastF1 would hit the same wall unless the data is cached or access is restored.

## Unverified / not settled here

- Gate A's definition of "valid" (see above). Owner or orchestrator ruling.
- Whether 2019 marshal-sector layouts are correct for the ten 2018 races. Settle by comparing race-control sector yellows with the positions of slow cars in those races.
- The 1.16% of DriverAhead naming a lower-lap car (03b): partly lag, partly unexplained.
- Gap agreement is measured only at 2 points per lap (S1 and S2). Agreement at other track points is assumed, not shown.
- Whether the line location (median relative_distance per race) shifts with era or track changes. Spread is small (median p10-p90 width 0.002-0.003 of a lap).
- Position-row `speed_kph` native vs interpolated, and `telemetry.schema.json` coverage: not examined.
