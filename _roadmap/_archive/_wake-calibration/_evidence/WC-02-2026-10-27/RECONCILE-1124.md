# Where 1,124 comes from, and why our WC-02 count differs

Run date 2026-10-27. Reconciliation only. Scratch only: nothing written to data/dev.duckdb, data/ci.duckdb or data/bronze (bronze lap files were read, not changed). No fit, coefficient, loss curve or gate was computed. No number from the archived dirty-air method (DA-03) was used. Nothing committed. Scripts (not in repo): /private/tmp/claude-501/-Users-justin-github-off-the-pace/b032368a-69cb-47e7-b591-7234689fb01e/scratchpad/rec/rec.py and ov.py.

## 1. Where the figure is written

The 1,124 is not in any committed document as a derived result. The WC design note says its sources are a research recommendation and a decision memo "written in a session scratchpad, not in the repo". The figure first appears in the research recommendation, section 1 ("Feasibility counts from the lap files"):

  /private/tmp/claude-501/-Users-justin-github-off-the-pace/ee218c22-feb2-4bd5-b674-56820a262446/scratchpad/research/traffic-loss-recommendation.md (line 24)

Its text: "Car ahead pits while the follower is within 1.5 s and stays out: 1,124 events (83 in 2018 up to 192 in 2024)", under a heading that says the gap is "the difference of lap-end timing-line crossings to the car one place ahead, green laps, no pit laps". The same session's decision memo (decision-memo.md) quotes a different number, 157, which is a subset of those events that fall inside stints with no clean lap. It is not a competing total.

The count was produced by a short script in the same folder (research/feasibility.py). No pre-registration or design note defines it more precisely than that script. WC-02 and the design note then repeated the figure as a target.

## 2. The source definition in plain English

Read from the script (the prose summary is looser than the code in two places, noted below):

- Data: the bronze lap files only (one row per driver per lap), all 8 seasons 2018-2025, every race that has a lap file (173). The pass table, corner segments and telemetry are not involved. The jolpica pit-stop table is not used; a pit stop is a lap with a pit-in time recorded.
- Car ahead: the car listed one place ahead (race position minus one) on the same lap number, using the race position recorded at the end of that lap.
- Gap: follower's lap-end timing-line time minus that car's lap-end timing-line time on the same lap number. Within 1.5 s means that single lap-end gap is under 1.5 s. It is one number per lap at the finish line, not an approach gap before a corner.
- Pit-stop of the car ahead: that car has a pit-in time on that lap (its in-lap).
- Green: the follower's own lap has a flag string of exactly "1" (all clear). The car ahead's lap is not checked.
- Lap 1 and 2 are dropped (laps from 3 up).
- Stays out: the only test in the code is that the follower has no pit-in time on that same lap. The code comment says "this lap and next", but next lap is not tested, and a pit-out lap for the follower is not excluded. The prose says "no pit laps", which the code does not do either.
- No window of 2 laps either side is applied. The "2 laps either side" idea belongs to the later use of the events, not to the count.

## 3. Definitions tried (lap files; events by season 2018 ... 2025)

Order of seasons: 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025.

| Variant | Total | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
| :-- | --: | --: | --: | --: | --: | --: | --: | --: | --: |
| A. Source definition exactly as the script has it | **1,124** | **83** | 113 | 105 | 124 | 156 | 176 | **192** | 175 |
| A with gap strictly above 0 as well | 1,124 | 83 | 113 | 105 | 124 | 156 | 176 | 192 | 175 |
| No green-lap requirement | 1,275 | 109 | 131 | 125 | 137 | 181 | 190 | 204 | 198 |
| Also drop follower pit-out laps | 1,072 | 81 | 110 | 104 | 114 | 146 | 164 | 184 | 169 |
| Also drop pit-out for the follower and the car ahead | 1,070 | 80 | 110 | 104 | 114 | 146 | 164 | 183 | 169 |
| Laps from 2 up instead of 3 | 1,131 | 83 | 113 | 107 | 125 | 156 | 178 | 193 | 176 |
| Car ahead's lap must also be green | 1,120 | 83 | 112 | 105 | 124 | 154 | 176 | 192 | 174 |
| Gap 1.5 s or under (not strictly under) | 1,125 | 84 | 113 | 105 | 124 | 156 | 176 | 192 | 175 |
| Follower no pit in or out within 1 lap either side | 929 | 75 | 94 | 98 | 99 | 118 | 141 | 160 | 144 |
| Follower no pit in or out within 2 laps either side | 843 | 71 | 84 | 89 | 87 | 102 | 129 | 143 | 138 |
| Same, 2 laps either side, any flag status | 948 | 91 | 95 | 101 | 97 | 121 | 137 | 153 | 153 |
| Follower does not pit in on this lap or the next only | 1,026 | 77 | 103 | 102 | 115 | 137 | 159 | 178 | 155 |

## 4. Result

Variant A reproduces 1,124 exactly, and the per-season counts match the quoted ends exactly (83 in 2018, 192 in 2024). Every other variant misses the total, so A is the definition behind the figure. Full season series for A: 83, 113, 105, 124, 156, 176, 192, 175 (2025 is 175, below 2024, consistent with "up to 192 in 2024").

Important reading of this: the 1,124 does not satisfy the stays-out wording in the WC-02 spec. Under the source definition "stays out" only means the follower did not pit in on that one lap. If the follower must also have no pit in or out for 2 laps either side (what WC-02 needs to read segment deltas on both sides), the same lap-end method gives 843.

## 5. Why our WC-02 numbers differ (2,551 candidates; 1,970 stayed out)

The two counts are different things, not one count done well and one done badly.

- Source: one event per follower lap, tested at the finish line, car ahead = the car one place ahead in the race order at the end of the lap.
- Ours: events built from the WC-01 pass table, where the car ahead is by order at a corner (apex order), the gap is the approach gap before a corner, and the candidate is kept if the gap was within 1.5 s at any corner of the lap (the minimum over corners). A single lap can qualify through several corners and several follower laps are found around a leader's pit-in lap.
- Only 143 of our 2,551 events (follower, race, lap) are also among the 1,124; 93 of those have the same car as the leader. 981 of the 1,124 are not in our set.
- Where they split: for our 2,551 events, the follower's lap-end gap to the car one place ahead is 1.5 s or more in 1,578 of them (plus 116 with no lap-file row, 370 on a non-green lap). In 1,996 of them the follower actually finishes the lap ahead of our pitting car on the line by 1.5 s or more, i.e. the pitting car has already fallen behind at the line (it is in the pit lane). In the source definition the pitting car must still be listed one place ahead at the end of its in-lap. Our method catches the follower while the car ahead is still on track; the source catches laps where the pitting car is still ahead at the line, which is a narrower, different set.
- Our stays-out test is stricter (no pit in or out for the follower in laps L-2 to L+2) and gives 1,970 of 2,551. The source test is looser.
- Races: ours uses the 169 WC-01 races; the source used all 173 lap-file races (WC-01 skipped 4: 2018 Australia and Bahrain, 2020 Sakhir and Tuscan).

I did not make our set conform to the source, and did not try to explain every individual event.

## 6. Options for the owner (no choice made here)

1. Keep the spec's event definition (approach gap, apex order, 2 laps either side, stays out). Then 1,124 is not the right target; our stayed-out count is 1,970 (198, 275, 180, 227, 266, 253, 284, 287 by season), of which 530 have measured deltas on both sides. Restate the target in the spec.
2. Adopt the source definition (lap-end gap, one place ahead, follower not pit-in on that lap). It reproduces 1,124, but it does not guarantee the follower stays out for the 2 laps either side that the deltas need; the 2-laps-either-side version of it is 843.
3. Use the source definition for a headline count and the pass-table definition for the event set that WC-04 and WC-05 read, and say so in the spec so the two numbers are never compared.

A further caution for the spec wording: the 157 "events in no-clean stints" in the decision memo and WC-05 comes from the source definition (variant A), not from our event set.
