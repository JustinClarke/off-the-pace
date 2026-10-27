# Wake calibration: design note (2026-10-27)

**Status: plan only. Nothing is registered, built, fitted or run.** No pre-registration exists yet; one is written and committed before anything is fitted (WC-03). Owner decisions DD-WC1 and DD-WC2 are open in [`../status/build-log.json`](../status/build-log.json).

Sources: the research recommendation ("Measuring time lost to traffic in F1", 2026-10-27, section 4) and the decision memo of the same date. Both were written in a session scratchpad, not in the repo.

**Replaces** the archived dirty-air method ([`../../_dirty-air/ARCHIVED.md`](../../_dirty-air/ARCHIVED.md)). No number from the old method (DA-03) is used here, as a fallback or otherwise.

## The idea

A driver's best evidence of what they would have done in clean air is **their own passes of the same corner, a few laps either side, when nobody was close**. Price each corner pass against that, attribute the excess using a gap measured *before* the corner, and keep "held up" separate from "dirty air".

## Method in brief

1. **Unit.** One driver passing one corner on one lap (a corner segment): braking point to 100 m after the apex, built once per circuit layout from `circuit_info` corners and median clean-air speed traces. About 12-20 per lap. Flat kinks merge with their straight. Classes by clean-air apex speed: slow (<120 km/h), medium, fast (>=200 km/h).
2. **Two independent outcomes**, each a delta to the driver's own reference: segment time from the driver's own trace only, and minimum speed in the segment (no timestamps).
3. **Reference.** Robust value of the driver's clean passes of that segment within ±4 laps, same stint, same compound. Clean = gap over 3 s ahead and no car within 1 s behind. No global tyre or fuel slope.
4. **Gap.** Time gap in seconds (follower's time at distance d minus the car ahead's at d), averaged **300 m to 50 m before the segment starts**, so no sample is shared with the outcome. Car ahead by on-track crossing order, not FastF1 DriverAhead.
5. **Exclusions.** SC, VSC, red, yellow-sector laps; lap 1 and the 2 laps after a restart; pit in/out laps for either car; wet laps; OffTrack samples. Lapped car ahead within 3 s = "lapped". Blue-flagged follower = "yielding", not loss.
6. **Classes.** Held up (leader slower than the follower's reference by more than 2× its MAD), dirty air (leader at or faster), racecraft (a pass or position change within 3 segments, or a sharp lateral change), under attack (car behind within 1 s, a separate flag). Straights and DRS zones are a separate "tow + DRS" number.
7. **Estimator.** Per pass loss = observed - reference. A monotone (non-increasing) loss-versus-gap curve per corner class and era, partially pooled across segments and circuits; race-level cluster bootstrap.
8. **Validation scorecard**, all reported: car-ahead-pits contrast, physics sign, flat curve above about 2.5-3 s, outcome agreement, gap check, held-out season against the current 0.331 × share rule, era split.

## Stints with no clean lap (corrected count)

**16.7% of stints (1,177) have no clean lap.** About **86%** of those can be filled from another stint of the same driver or from the teammate. About **2% of all stints (162)** are **unavailable**.

These are count-only figures from the bronze lap parquet (lap-end line gap, whole-stint window, stints of 8+ green laps, leaders counted as clean). The real test is per corner within ±4 laps, so the true measured share will be somewhat lower. Read them as orders of size. The earlier 21.5% figure counted leaders as not clean and is superseded.

## Labels

| Label | When | Shown as |
| :-- | :-- | :-- |
| **measured** | Own clean passes of the corner within ±4 laps, same stint and compound | Number with interval |
| **modelled** | No own clean reference; reference from the driver's other stint or the teammate, same race (source stored) | Wider interval, marked "modelled", hatched or greyed, with the disclaimer below |
| **unavailable** | Neither source exists, the gap is unknown, or the lap is excluded | "—" with the reason. Never 0 |

Totals add measured and modelled only with the modelled share printed beside them, for example "3.4 s (28% modelled)". Unavailable laps are left out of totals and counted, never treated as zero.

**Disclaimer for modelled stints** (wording pending owner confirmation, DD-WC2; use exactly):

> Normalised from other compounds, based on stints from other drivers or the general performance of the tyres after removing other factors.

## Top risks (from the research)

1. **Selection.** Drivers stuck in traffic have no clean reference, and that is where the loss is largest. Shows as a high modelled share for midfield teams, and measured losses smaller than modelled at the same gap.
2. **Held up versus dirty air**, and tyre saving while following. Shows as slow-corner "dirty air" as large as fast-corner, loss rising with time spent following, a non-zero under-attack effect, car-ahead-pits jumps bigger than the curve.
3. **Local baseline drift.** A tyre cliff, track evolution, or following bunched at one end of the stint biases the ±4-lap reference. Shows as a trend in clean-pass residuals inside the window, a pre-trend before car-ahead-pits events, estimates that move between ±2 and ±6 laps.

Also: live use depends on a paid OpenF1 feed (2023+, NC-SA licence); 2026 removes DRS, so the method must be refit then.
