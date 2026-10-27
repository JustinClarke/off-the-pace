# Grain review: seconds, metres, or both (2026-10-23)

Read-only review for the DA-02 owner decision. Nothing was run against a warehouse. Sources: `wi/DA-design-note.md`, `wi/DA-02-tables.md`, `wi/DA-03-identification.md`, `wi/DA-05-label-and-app.md`, `status/build-log.json`, and DA-01 evidence (`_evidence/DA-01-2026-10-23/NOTE.md` section 3, `results/04_incumbent_ff_distance_over_speed.csv`, `results/03_driverahead_vs_crossing_order.csv`).

## 0. What the choice actually is

Micro-sectors are slices of track position (`relative_distance`) under either option, and the outcome y stays in seconds either way. The only thing that changes is the **exposure**: are the gap bands in β(g) defined by the time gap (s) or by the distance gap (m)? The micro-sector count (10-20) is a separate decision that is also owed at this gate.

## 1. Analysis

**What each grain assumes.**
- **Seconds:** g_i is the difference in time to reach the same track point. This is what the timing feed measures, what DA-01 checked (median absolute error 0.053-0.078 s against sector-line times), and what the 3 s rules (DD5, the reference band) are written in. It assumes the time gap is the right summary of how much wake the car meets.
- **Metres:** the distance between the cars at the same instant. At a fixed time gap the metre gap stretches on straights and shrinks in slow corners (1 s is about 80 m at 290 km/h and about 25 m at 90 km/h). Turning metres into a time-like quantity assumes both cars travel at the same speed. Physically, the wake is a structure in space, so metres is a fair candidate for the aero mechanism. That is the best case for it.
- **Measured problem with metres as it stands:** FastF1 distance divided by speed agrees with timing under 1 s (median -0.011 s) but is biased at 1-2 s (-0.13 s) and above 2 s (-1.04 s). `distance_to_ahead_m` itself was never checked against timing (design note section 8). It is also tied to FastF1 `DriverAhead`, which follows race order and names a different car from the crossing logic on 4% of same-lap bins and almost all lapped-car bins.

**Forking paths.** Yes, this is a real risk. Two grains × two eras × three placebos is enough choice to find a passing combination. The rule that removes the risk: **seconds is primary; the gate, the DD4 wording and every number shown to users come from seconds only.** Metres can be a pre-registered sensitivity check that **cannot rescue a failed seconds result**. If seconds fails a gate, the project stops or reports the failure, whatever metres shows. If seconds passes and metres disagrees, that is reported as a caveat, never as a reason to switch grains.

**What the pre-registration (DA-03 hash) must name, if both are carried:**
1. Seconds is primary, and the no-rescue rule above, in words.
2. Metres band edges, fixed before anyone looks at curves. There are no natural edges. One option is to map each seconds edge (0.5/1/1.5/2/3 s) through the median green speed per era, but era-specific edges are themselves a choice and must be fixed in advance.
3. A metres reference band (the counterpart of >3 s).
4. The same valid sample set for both. Validity, the lapped-car 3 s rule (DD5), and the 20% unknown rule are decided in seconds. Metres only re-bins those samples.
5. The same car ahead for both: metres computed in-house from the same pair as g_i (difference in track distance at the same instant), not FastF1's `distance_to_ahead_m`.
6. What "agree" means (for example, the sign and monotone shape of β, and the <1 s band within the primary CI), plus the wording used when the two disagree.

## 2. Identification

- **Placebos.** P1 (car behind) carries over unchanged. P2 needs its own metres reference band (item 3 above). **P3 is entangled under metres.** Metre bands line up with local speed: a car at a constant 1 s gap moves from a "far" metres band on a straight to a "near" one in a slow corner. P3 splits by corner class, so under metres the band and the mechanism split move together. P3 should be gated on seconds only and reported descriptively for metres.
- **Era split.** Fitting each era separately absorbs the level difference in speed within each era. The stop rule "sign flips between eras", however, compares β across eras. In metres, that comparison mixes changes in the wake (the 2022 ground-effect rules aimed to reduce it) with changes in corner and straight speed between eras. So the metres version cannot test era stability cleanly. Seconds is closer to like-for-like. DA-01 also found era-specific timestamp noise (0.053-0.061 s in 2018-21, 0.067-0.078 s in 2022-25), which affects both grains, and metres adds the speed-conversion error on top.
- **Net effect:** carrying both grains changes the placebos (P2 needs a new band; P3 is seconds-only) and weakens the era test for metres. It does not change the seconds design.

## 3. Label and app

- **Label and ML feature.** Under path A (DD2 recommendation) the label is unchanged either way. Under path B there can be only one tax in the label. Any ML feature built on it uses one grain, fixed in the feature contract. A toggle cannot change either one without a label version or a new feature arm.
- **The number users see.** A toggle shows two "dirty-air cost" numbers for the same lap. They will differ, most on high-speed laps, and users will pick whichever suits their argument. That is forking paths moved into the app. It also conflicts with DD4: the wording ("causal" or "adjusted traffic cost") is earned by the seconds result passing P1-P3. Metres would not have passed the same gates (P3 is not testable on it as primary), so it cannot carry the same wording, and labelling one toggle position differently from the other is confusing.
- **Can it be done without touching the label or the feature contract?** Yes, technically: under path A, a display-only second column (for example `dirty_air_cost_dynamic_m_s`) beside `dirty_air_cost_dynamic_s`, read only by the replay. **Cost:** a second published column at sample, micro-sector, sector and lap grain, plus a toggle on the replay page, copy for both states, page summaries and assistant docs (the docs-drift check), and a test that the label never reads the metres column. That is roughly 1-2 weeks on top of DA-05's 3 weeks. If the metres sensitivity fails, the toggle has nothing honest to show.
- **A cheaper alternative:** show the metres result once, as a sensitivity chart on the methods or docs page, not as a toggle.

## 4. Cost against the estimates (DA-02 3-4 wk, DA-03 4-6 wk; the brief's "2-3 wk" is DA-01)

| Option | DA-02 | DA-03 | DA-05 |
|---|---|---|---|
| (a) seconds only; metres logged | +0-2 days: one metres-band column and one descriptive curve, no test beyond NULL handling | +1-2 days: one unregistered refit, logged | 0 |
| (b) both carried; seconds primary; metres pre-registered | +1-1.5 wk: in-house metres gap on the same pair; metres band columns at sample and micro-sector grain; tests (same valid set as seconds, NULL only when seconds is NULL, band edges fixed); validation of metres against the timing lines (reuse DA-01 query 04) | +1 wk: second fit per era, P1/P2 on metres, agreement report, pre-registration items 1-6 | 0 |
| (c) (b) plus app toggle | as (b) | as (b) | +1-2 wk (section 3) |

For (b), the main extra row volume is extra columns on the roughly 68M-row sample table, not a new table. The ROUND and total-order rules for byte stability apply to the new columns too.

## 5. Recommendation

**(b), with a precondition:** carry both through DA-02 and DA-03, seconds primary, metres pre-registered as a sensitivity check under the no-rescue rule. Gate P3 and the era test on seconds only. Add a DA-02 step that checks the in-house metres gap against the timing lines. If it fails the same threshold as seconds (median under 0.1 s below 2 s), drop to (a) automatically, and pre-register that fallback. **No toggle (not (c)).** If the owner wants metres visible, show it as a single sensitivity chart on the methods page.

**Strongest reason against (b):** if metres disagrees with seconds, the disagreement cannot be read cleanly, because measurement bias (DA-01: -0.13 s at 1-2 s), speed confounding, and a real spatial-wake effect all predict the same pattern. So (b) spends about 2 weeks on a check that, by construction, can only lower confidence and cannot change the result. (a) would get most of the reassurance for a few days.

## Owner decision

1. (a) or (b) for the analysis. Either way, seconds is primary and metres can never rescue a failed seconds result.
2. Whether metres is ever shown to users: no, a methods-page chart, or a toggle (c).
3. The micro-sector count (10-20), owed at the same gate.
