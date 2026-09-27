# F1 said the 2022 cars would be easier to follow. Following did get cheaper, but it started before 2022, it never got cheap, and in 2025 it went back up

*Dirty-air cost per season, 2018–2025. Analysis run 2026-09-15, post revised 2026-09-22.
**Re-measured 2026-09-27 on a corrected baseline, which changed the late-season result.** See
"What changed since the first version" below.*

The 2022 regulations were sold on one promise: cars would be able to follow each other. In this
data the cost of following roughly halved between 2018 and 2022–2024. But it was already falling
before the new cars arrived, and when we test the same pre/post comparison at every *other* season
boundary, it fires at all of them. It never fell anywhere near zero. And in 2025, the season we
named in advance as the test of all this, it went back up.

---

## The number nobody has: what following costs, per season

θ is the average lap time, in seconds, that a car loses on a lap **because it was in dirty air on
the previous lap of the same stint**. Positive means following costs time.

| Season | n (laps) | G (races) | **θ (s/lap)** | 95% CI |
| :--- | ---: | ---: | ---: | :--- |
| 2018 | 15,600 | 20 | **+0.511** | [+0.375, +0.647] |
| 2019 | 18,539 | 21 | **+0.435** | [+0.296, +0.573] |
| 2020 | 13,131 | 17 | **+0.297** | [+0.208, +0.386] |
| 2021 | 17,872 | 20 | **+0.347** | [+0.264, +0.431] |
| 2022 | 14,609 | 20 | **+0.275** | [+0.213, +0.337] |
| 2023 | 18,864 | 22 | **+0.194** | [+0.113, +0.274] |
| 2024 | 20,450 | 23 | **+0.271** | [+0.183, +0.359] |
| 2025 | 19,614 | 23 | **+0.382** | [+0.255, +0.509] |

Half a second a lap in 2018. About a quarter of a second in 2022–2024, and every season's interval
is clear of zero. Then 0.38 in 2025. Confidence intervals are clustered on race, because traffic is
a race-level state rather than a lap-level coin flip, and there are only 17–23 races in a season.
That width is the honest width.

**The shape is not an artefact of the fixed effects we chose.** We ran the same fits at four levels
of absorption, from a pooled OLS with nothing absorbed to the strictest version:

| Rung | What it absorbs | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| F0 | nothing (pooled OLS) | 0.720 | 0.644 | 0.581 | 0.373 | 0.455 | 0.346 | 0.416 | 0.603 |
| F1 | driver × race | 0.600 | 0.560 | 0.428 | 0.399 | 0.304 | 0.277 | 0.283 | 0.418 |
| **F2** | **stint + tyre-age bin (headline)** | **0.511** | **0.435** | **0.297** | **0.347** | **0.275** | **0.194** | **0.271** | **0.382** |
| F3 | F2, minus laps near an SC/VSC/red flag/pit | 0.505 | 0.466 | 0.296 | 0.349 | 0.250 | 0.207 | 0.279 | 0.391 |

Every rung puts 2018 highest, 2023 lowest and 2025 back above 2022–2024. No rung, in any season,
has an interval that reaches zero.

## How it is identified, in one paragraph

The outcome is a lap's pace against the field's smoothed pace on that lap of that race, with the
fuel-burn component and the lap's own modelled tyre cost removed, **on laps where the field's pace
was actually measured**. The treatment is the **previous** lap's air state, which is what keeps the
causal arrow pointing the right way: slow cars do end up following more, but last lap's position
cannot have been caused by this lap's time. The headline fit absorbs **stint** fixed effects — so
every comparison is the same driver, in the same car, in the same race, on the same set of tyres —
plus six tyre-age bins (laps 1–5, 6–10, 11–15, 16–20, 21–25, 26+), because within a stint both tyre
age and the chance of being caught rise together, and without the bins degradation loads onto the
treatment. Errors are clustered on race.

**The treatment is one bit per lap.** A lap counts as "following" if the median gap to the car
ahead through sector 2 (the middle third of the lap) was under 1.5 seconds, whatever DRS was doing.
That is the whole measurement. There is no dose-response in gap here, and nothing in this post can
be read as "x seconds per car length".

## Why you should believe the falsification more than the result

Run the comparison everyone would run — average θ before 2022 against average θ from 2022, over
the 2018–2024 window this analysis pre-registered — and it comes back exactly as a regulation story
would want:

- θ(2018–2021) = **+0.396** [+0.339, +0.454], n = 65,142 over 78 races
- θ(2022–2024) = **+0.245** [+0.200, +0.291], n = 53,923 over 65 races
- **Δ = −0.241 [−0.326, −0.156], p < 0.0001**

Clean, significant, correctly signed. It is also worthless on its own, and here is why. We refit
the identical interaction with a **fake** era boundary at every season:

| Boundary | Δ | 95% CI | p |
| :--- | ---: | :--- | ---: |
| ≥ 2019 | −0.303 | [−0.450, −0.157] | 0.0001 |
| ≥ 2020 | −0.274 | [−0.393, −0.155] | < 0.0001 |
| ≥ 2021 | −0.218 | [−0.319, −0.117] | < 0.0001 |
| **≥ 2022 (the real one)** | **−0.241** | **[−0.326, −0.156]** | **< 0.0001** |
| ≥ 2023 | −0.223 | [−0.309, −0.137] | < 0.0001 |
| ≥ 2024 | −0.151 | [−0.249, −0.053] | 0.0028 |

Every boundary "works", and the real one sits in the middle of the pack. Two more cuts point the
same way. A plain linear season trend fits 2018–2024: **dθ/dseason = −0.065 [−0.088, −0.043]**,
p < 0.0001. And the era contrast leans on seasons well before the treatment: **dropping 2018
shrinks Δ from −0.241 to −0.195** [−0.287, −0.104]; dropping 2018 and 2019 leaves −0.152
[−0.241, −0.063].

**The measured claim.** The cost of following in this data roughly halved between 2018 and
2022–2024. The decline is gradual and it pre-dates the 2022 regulations, so the regulations cannot
be given credit for it on this evidence. And it did not go away: following still cost about a
quarter of a second a lap in 2022–2024.

## The test we named in advance, and what it did

The first version of this post ended with the test that would break it: the same fit on a season
the analysis had never seen. "If the trend is real and continues, θ stays at or below zero."

On the corrected baseline, the 2018–2024 trend predicts about **+0.07** for 2025. The fit gives
**+0.38** [+0.26, +0.51], the highest value since 2019, with the prediction far outside its
interval. Adding 2025 to the window halves the trend (−0.040 a season), and a pre/post split at
2024 or 2025 no longer finds anything.

So "a steady decline" is not the right description any more. The data shows a fall from 2018 to
2023 and then a rebound in 2025, the last season of the 2022 rules. Nothing in this analysis says
why.

## How much of it is caused by following: the placebo

We pre-declared one placebo: refit with the **next** lap's air state alongside the previous lap's.
Dirty air is persistent, so a non-zero lead coefficient is expected; the design is in trouble if the
lead is not materially smaller than the lag.

| Season | lag | lead | lag ÷ lead | lag − lead | 95% CI |
| :--- | ---: | ---: | ---: | ---: | :--- |
| 2018 | 0.432 | 0.244 | 1.8× | +0.188 | [+0.093, +0.283] |
| 2019 | 0.379 | 0.205 | 1.8× | +0.174 | [+0.063, +0.285] |
| 2020 | 0.241 | 0.188 | 1.3× | +0.053 | [−0.012, +0.117] |
| 2021 | 0.290 | 0.182 | 1.6× | +0.108 | [+0.020, +0.196] |
| 2022 | 0.236 | 0.155 | 1.5× | +0.080 | [+0.004, +0.157] |
| 2023 | 0.172 | 0.077 | 2.2× | +0.095 | [+0.026, +0.164] |
| 2024 | 0.223 | 0.164 | 1.4× | +0.059 | [−0.035, +0.153] |
| 2025 | 0.310 | 0.208 | 1.5× | +0.101 | [+0.019, +0.183] |

Two things are true at once. **The next lap's air state predicts this lap's pace in every season**
(lead +0.08 to +0.24), so some of every number above is a car being stuck in a traffic state, not
the cost of the previous lap's wake. **But the lag beats the lead in every season**, by 1.3 to 2.2
times, and the difference, which is the part the design can call directional, is clear of zero in
six of eight seasons, including 2021, 2022 and 2023. Pooled over 2018–2025 that directional part is
about **0.11 s a lap**, roughly a third of the headline number.

So read the per-season θ as the lap-time cost *associated with* having followed on the previous
lap, of which a fifth to a half is directional by this test. It is not a clean causal cost of
following in any season. It is not "no detectable directional cost" in 2021–2024 either, which is
what the first version of this post said.

## The corner split: the mechanism test, and what it can't do

If the 2022 cars genuinely reduced wake sensitivity, the effect should be aerodynamic, and
downforce scales with the square of speed. So a real aero improvement should show up **in fast
corners and not in slow ones**. We declared that prediction before fitting.

We classify every (race, corner) cell by its field-median apex speed — slow under 125 km/h, medium
125–199, fast 200 and above — and measure the apex-speed deficit a driver carries on a lap after
following, against the same driver, at the same corner, in the same race, on a lap after clean air.
2018–2024, as pre-registered:

| Class | n (pre / 2022+) | θ pre-2022 | θ 2022+ | as % of apex speed | Δ | 95% CI |
| :--- | ---: | ---: | ---: | :--- | ---: | :--- |
| Slow (< 125 km/h) | 236,279 / 198,677 | +0.0450 | +0.0556 | 1.25% → 1.54% | +0.0067 | [−0.0033, +0.0166] |
| Medium (125–199) | 161,415 / 110,903 | +0.0518 | +0.0484 | 1.44% → 1.35% | −0.0071 | [−0.0179, +0.0037] |
| Fast (≥ 200 km/h) | 29,646 / 28,512 | +0.0401 | +0.0294 | 1.11% → 0.82% | −0.0119 | [−0.0316, +0.0077] |

**The point estimates land in the predicted order.** The fall is concentrated in fast corners,
where downforce matters most, and there is no fall at all in slow corners. **And not one of the
three changes is distinguishable from zero.**

How underpowered: read against the pre-2022 level, the fast-corner interval runs from **removing
four-fifths of that deficit to making it a fifth worse**. Its half-width is 1.65 times its own point
estimate. To resolve a change of the size we estimate, we would need roughly **2.7 times as many
fast-corner observations** as seven seasons of this calendar provide; fast corners are under 8%
of corner-rows (the first version said 15%, which was the share of corners, not of rows). This test is consistent with the aero mechanism and nowhere near able to confirm it.

One more result, reported because it was the pre-registered outcome. The corner *total* (braking
plus mid-corner plus exit) shows a fast-corner change that does clear zero: −0.053
[−0.102, −0.003]. It cannot be read as "less time lost in fast corners", because the braking term
in that total runs the opposite sign to the other two (a larger value means braking later, which is
faster). That is why the apex deficit is the headline. It is one of three tests, at p ≈ 0.04.

## The half that is precise, and it is the strange half

The change in cornering is unmeasurable. The **level** is not:

> **Following cost about 1.0% of apex speed in a slow corner in 2018, and about 1.6% in 2024.**
> Season by season, the slow-corner deficit runs 0.038 / 0.045 / 0.048 / 0.050 / 0.054 / 0.053 /
> 0.059, and every season's confidence interval excludes zero.

So: **the lap-level cost of following halved, and the cornering deficit did not shrink. If anything
it grew.** Whatever made following cheaper over a full lap did not make the car grip better in the
corner. That is a genuinely odd pair of findings to hold at once, and we are publishing it as a pair
rather than picking the half that tells a cleaner story.

## What changed since the first version

The first version of this post (2026-09-15, revised 2026-09-22) reported θ falling from +0.40 in
2018 to −0.04 in 2024, "indistinguishable from zero from 2021 onwards", with a placebo failure in
2021–2024 read as "no detectable directional cost". Most of that late-era zero was not in the cars.
It was in our baseline.

About 7% of the laps in that panel had no measured field pace. The pipeline filled the gap by
treating each such lap as exactly on the field's pace, which left it with a residual of about
−1.4 s (just the fuel correction). Those invented laps were also disproportionately "following" laps
(39% against 22% overall). Together that pulled every season's estimate toward zero. Removing them
raises every season by 0.10 to 0.22, with three of the four largest moves in 2021, 2022 and 2024.
Two further corrections moved the numbers again, by less. Laps where a car sat under a second behind
with DRS open had been coded as clean air. And the field baseline now removes each car's tyre cost
the same way it removes fuel.

This version measures only laps with a real baseline. The ladder, the placebo, the era tests and
the corner split were re-run on the same pre-registered design. Nothing about the design changed,
and the first version's panel, run through the same code, reproduces the first version's table
exactly.

**What survived:** the decline pre-dates 2022, the placebo boundaries fire everywhere, the
regulations cannot be credited, the corner ordering matches the aero mechanism without the power to
confirm it, and the cornering deficit did not fall. **What did not:** "two thirds", "gone by 2022",
"no detectable directional cost 2021–2024", "exactly as it did in 2018" for slow corners, and the
steady trend, which 2025 broke.

## What would change this result

1. **Per-corner gap exposure instead of a lap-level bit.** The treatment here is one binary per lap
   from one sector. A measure of actual exposure per corner would be a different, better instrument
   and could move every number above.
2. **A dose-response in gap rather than a 1.5-second threshold.** Everything here is the cost of a
   lap *classified* as following. A model in the gap itself would say whether the cost is smooth,
   and whether the decline is a decline in the cost of proximity or a change in how often cars are
   genuinely close. It is also the most direct way to separate the directional cost from the
   persistent-traffic part the placebo finds.
3. **Another season this analysis has never seen.** 2025 was the named test, and it broke the
   trend. 2026, the first season of new regulations, is the next one.

## Caveats, in the post and not in a reply

**2022 is a bundle, not an aero experiment.** The regulations arrived together with 18-inch tyres,
a minimum-weight rise of roughly 46 kg, and porpoising. Nothing in this analysis separates them.
The corner-class split is the only thing here that moves toward mechanism, and it is underpowered
to get there.

**The treatment is one bit per lap**, from a single sector-2 median gap crossing 1.5 seconds. No
dose-response. Nothing here is "x seconds per car length".

**The placebo is not clean in any season.** The next lap's air state carries weight everywhere, so
every θ above includes some persistent-traffic association. The directional part is detectable in
six of eight seasons, not all of them (2020 and 2024 are the exceptions).

**The baseline is only mostly clean air.** The field-pace baseline is restricted to laps whose
dominant air state across the three sectors is free air or tow. But "following" is scored on sector
2 alone, so **36.2% of treated laps pass that clean-air filter anyway**, and **63.8% of treated laps
carry a non-dirty-air dominant state**. The second share is flat across seasons (62.1–64.5%). The
first is not: it drifts from 42.8% in 2018 to 29.9% in 2025, so the baseline is cleaner in the
later seasons than in the earlier ones. Both figures are reported rather than corrected for.

**The tyre cost in the outcome is modelled.** The outcome subtracts the lap's modelled tyre cost.
The headline spec barely depends on it: without that term, the pooled 2018–2025 estimate is 0.312
instead of 0.331.

**The baseline is a 5-lap centred rolling mean.** Field pace at lap *t* is averaged over laps *t*−2
to *t*+2, so the baseline is not a strictly backward-looking object. The treatment is lagged, so
the future is not inside the treatment — but the level of the outcome is not a real-time quantity.

**Season boundaries are not clean experiments.** Calendars change, tyre compounds change annually,
and 2020 was a 17-race season run largely without crowds on a rearranged calendar. The per-season
θs absorb all of that.

## Postscript: what this measurement did to our own warehouse

The reason this analysis existed at all is that the model could not answer the question. The
production dirty-air tax applied a single global coefficient, `dirty_air_tax_s = θ × (was the
previous lap in dirty air)`, with the same θ in 2018 and 2024 — so as built it *assumed* the cost
of following had never changed.

Then the instrument check found something worse than a modelling assumption. The treatment column
is binary, and the calibration query filtered it to the treated arm before fitting. A binary
regressor restricted to its treated arm is a **constant**: the variance is exactly zero, the slope
is undefined, and the SQL's own fallback default fired. **The shipped 0.5 s/lap dirty-air tax had
never been estimated from data.** It was a hard-coded prior, charged to every following car, in
every season, since 2018.

That defect was fixed first: the calibration panel kept both arms and the warehouse fitted
**0.131 s/lap**. But that fit was calibrated on the same invented-baseline laps described above. With
them removed and tyre cost handled like fuel, the warehouse now fits **0.503 s/lap**, pooled across
every season with nothing absorbed. By coincidence that is almost exactly the hard-coded 0.5 it
replaced, and the per-season fits here put it outside the interval in five of eight seasons
(2020–2024).

It is also higher than this post's own within-stint estimate over the same seasons (**0.331**),
because slower cars follow more often and a pooled slope bills some of their pace as dirty air.
So the warehouse now carries **0.331**: the within-stint estimate replaced the pooled one in the
training label, frozen as a declared value rather than re-fitted on every build. That change
rewrites the training target, so the models still have to be retrained and gated on it before
anything they produce moves. The per-season fits in this post stay **published, not shipped**:
the label carries one coefficient for every season. The app's dirty-air leaderboard still shows
figures from an earlier coefficient until the models are retrained and re-exported.

The honest summary of this item has not changed: the regulations cannot be credited with a decline
that started years before them. The most useful finding is still that we had been quoting a number
nobody ever fitted. The second most useful is that a filled-in baseline had been telling us the
cost of following had vanished, when it had only halved.

---

### Provenance

This version: 138,970 laps, 2018–2025, the production dirty-air calibration panel on the corrected
label. The rebuilt panel reproduces the shipped panel's row count and its fitted coefficient to
3e-15 before any other fit. Scripts, panels and every fit (224 entries) are in
[`_roadmap/_fixes/_evidence/wi-12-2026-09-27/`](../../../_fixes/_evidence/wi-12-2026-09-27/), and the
re-measure is written up in
[`_roadmap/_fixes/wi/WI-12-06b-remeasure.md`](../../../_fixes/wi/WI-12-06b-remeasure.md). The first
version's panel ([`panel_06b_lap.parquet`](panel_06b_lap.parquet)), run through the same code,
reproduces the first version's table, era contrast, trend and placebo boundaries exactly. Its 93
fits remain in [`06b_dirty_air_per_season.json`](06b_dirty_air_per_season.json) and
[`06b_diagnostics.json`](06b_diagnostics.json), reproducible from `d0`–`d3` in this directory.

The estimand, population, estimator ladder, era contrast, corner classes and both falsification
tests were **pre-registered before any coefficient existed**; the pre-registration is in
[`../../work/06-publication.md`](../../work/06-publication.md) and did not change for this
re-measure. Two deviations are logged there: untreated laps were kept in the calibration sample
(the whole point), and the headline corner outcome is the mid-corner phase rather than the
three-phase total, because the total sums a term whose sign convention runs the other way.

**Status: written, not published.** Publishing is the user's call.
