# F1 said the 2022 cars would be easier to follow. Following did get cheaper — but it started getting cheaper in 2019

*Dirty-air cost per season, 2018–2024. Analysis run 2026-09-15; post revised 2026-09-22 after the
production fix this analysis triggered landed.*

The 2022 regulations were sold on one promise: cars would be able to follow each other. In this
data the cost of following did fall, by about two thirds since 2018. But it was already falling
before the new cars arrived, and when we test the same pre/post comparison at every *other* season
boundary, it fires at all of them. A step-change test that detects a step wherever you put it is
detecting a trend.

---

## The number nobody has: what following costs, per season

θ is the average lap time, in seconds, that a car loses on a lap **because it was in dirty air on
the previous lap of the same stint**. Positive means following costs time.

| Season | n (laps) | G (races) | **θ (s/lap)** | 95% CI |
| :--- | ---: | ---: | ---: | :--- |
| 2018 | 14,850 | 20 | **+0.396** | [+0.217, +0.575] |
| 2019 | 17,982 | 21 | **+0.151** | [+0.004, +0.298] |
| 2020 | 14,122 | 17 | **+0.170** | [+0.052, +0.288] |
| 2021 | 19,198 | 21 | +0.083 | [−0.030, +0.196] |
| 2022 | 16,864 | 22 | +0.011 | [−0.130, +0.151] |
| 2023 | 19,261 | 22 | +0.045 | [−0.050, +0.139] |
| 2024 | 21,528 | 24 | −0.036 | [−0.175, +0.103] |

Four tenths of a second a lap in 2018. Indistinguishable from zero from 2021 onwards, and the 2024
point estimate is marginally negative. Confidence intervals are clustered on race, because traffic
is a race-level state rather than a lap-level coin flip, and there are only 17–24 races in a
season. Those intervals are wide. That width is the honest width.

**The shape is not an artefact of the fixed effects we chose.** We ran the same seven fits at four
levels of absorption, from a pooled OLS with nothing absorbed to the strictest version, and every
rung tells the same story:

| Rung | What it absorbs | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| F0 | nothing (pooled OLS) | 0.418 | 0.292 | 0.250 | −0.034 | 0.065 | 0.106 | −0.011 |
| F1 | driver × race | 0.343 | 0.180 | 0.079 | −0.032 | −0.105 | −0.003 | −0.114 |
| **F2** | **stint + tyre-age bin (headline)** | **0.396** | **0.151** | **0.170** | **0.083** | **0.011** | **0.045** | **−0.036** |
| F3 | F2, minus laps near an SC/VSC/red flag/pit | 0.327 | 0.090 | 0.120 | 0.062 | −0.061 | −0.011 | −0.070 |

Large in 2018, gone by 2022, on every rung.

## How it is identified, in one paragraph

The outcome is a lap's pace against the field's smoothed pace on that lap of that race, with the
fuel-burn component removed. The treatment is the **previous** lap's air state, which is what keeps
the causal arrow pointing the right way: slow cars do end up following more, but last lap's
position cannot have been caused by this lap's time. The headline fit absorbs **stint** fixed
effects — so every comparison is the same driver, in the same car, in the same race, on the same
set of tyres — plus six tyre-age bins (laps 1–5, 6–10, 11–15, 16–20, 21–25, 26+), because within a
stint both tyre age and the chance of being caught rise together, and without the bins degradation
loads onto the treatment. Errors are clustered on race.

**The treatment is one bit per lap.** A lap counts as "following" if the median gap to the car
ahead through sector 2 was under 1.5 seconds. That is the whole measurement. There is no
dose-response in gap here, and nothing in this post can be read as "x seconds per car length".

## Why you should believe the falsification more than the result

Run the comparison everyone would run — average θ before 2022 against average θ from 2022 — and it
comes back exactly as a regulation story would want:

- θ(2018–2021) = **+0.185** [+0.115, +0.255], n = 66,152 over 79 races
- θ(2022–2024) = **+0.004** [−0.066, +0.075], n = 57,653 over 68 races
- **Δ = −0.219 [−0.331, −0.106], p = 0.0002**

Clean, significant, correctly signed. It is also worthless on its own, and here is why. We refit
the identical interaction with a **fake** era boundary at every season:

| Boundary | Δ | 95% CI | p |
| :--- | ---: | :--- | ---: |
| ≥ 2019 | −0.359 | [−0.542, −0.176] | 0.0002 |
| ≥ 2020 | −0.238 | [−0.369, −0.106] | 0.0005 |
| ≥ 2021 | −0.224 | [−0.341, −0.108] | 0.0002 |
| **≥ 2022 (the real one)** | **−0.219** | **[−0.331, −0.106]** | **0.0002** |
| ≥ 2023 | −0.192 | [−0.312, −0.073] | 0.0018 |
| ≥ 2024 | −0.234 | [−0.409, −0.059] | 0.0091 |

Every boundary "works", and the real one is the second-weakest of the six. Two more cuts point the
same way. A plain linear season trend fits the data: **dθ/dseason = −0.0667 [−0.0963, −0.0371]**,
p < 0.0001. And the era contrast leans heavily on a season four years before the treatment —
**dropping 2018 shrinks Δ from −0.219 to −0.163** [−0.277, −0.049]; dropping 2018 and 2019 leaves
−0.154 [−0.282, −0.025].

**The measured claim.** The cost of following in this data fell by roughly two thirds between 2018
and 2024. The decline is gradual and it pre-dates the 2022 regulations, so the regulations cannot
be given credit for it on this evidence.

That is the opposite of what we expected to find, and it is the part worth publishing. The naive
test passes. The falsification kills it.

## The corner split: the mechanism test, and what it can't do

If the 2022 cars genuinely reduced wake sensitivity, the effect should be aerodynamic, and
downforce scales with the square of speed. So a real aero improvement should show up **in fast
corners and not in slow ones**. We declared that prediction before fitting.

We classify every (race, corner) cell by its field-median apex speed — slow under 125 km/h, medium
125–199, fast 200 and above — and measure the apex-speed deficit a driver carries on a lap after
following, against the same driver, at the same corner, in the same race, on a lap after clean air.

| Class | n (pre / 2022+) | θ pre-2022 | θ 2022+ | as % of apex speed | Δ | 95% CI |
| :--- | ---: | ---: | ---: | :--- | ---: | :--- |
| Slow (< 125 km/h) | 235,038 / 208,696 | +0.0308 | +0.0342 | 0.86% → 0.95% | −0.0001 | [−0.0107, +0.0105] |
| Medium (125–199) | 159,595 / 116,407 | +0.0308 | +0.0311 | 0.86% → 0.86% | −0.0023 | [−0.0184, +0.0138] |
| Fast (≥ 200 km/h) | 29,960 / 28,912 | +0.0226 | +0.0140 | 0.63% → 0.39% | −0.0114 | [−0.0316, +0.0089] |

**The point estimates land in exactly the predicted order.** The fall is concentrated in fast
corners, where downforce matters most, and is literally zero in slow corners. **And not one of the
three changes is distinguishable from zero.**

It is worth being specific about how underpowered this is rather than waving at it. Read against
the pre-2022 level it is measured from, the fast-corner interval runs from **eliminating that
deficit outright to making it 40% worse**. Its half-width is 1.8 times its own point estimate. To
resolve a change of the size we actually estimate, we would need roughly **3.2 times as many
fast-corner observations** as seven seasons of this calendar provide — fast corners are about 15%
of corner-rows, and that is where the precision went. This test is consistent with the aero
mechanism and nowhere near able to confirm it.

A phase decomposition, run after the fact, points the same way without adding power: following
makes a driver get on the brakes **earlier** in every class and both eras, and most of all in fast
corners (−0.059 pre, −0.053 from 2022). That is the textbook downforce mechanism. Two robustness
cuts — classifying corners by within-race speed tercile instead of absolute thresholds, and
restricting to the 23 tracks that appear in both eras — leave the ordering intact.

## The half that is precise, and it is the strange half

The change in cornering is unmeasurable. The **level** is not:

> **Following still costs about 0.9% of apex speed in a slow corner in 2024, exactly as it did in
> 2018.** Season by season, the slow-corner deficit runs 0.027 / 0.036 / 0.031 / 0.029 / 0.038 /
> 0.025 / 0.039, and every season's confidence interval excludes zero.

So: **the lap-level cost of following collapsed, and the cornering deficit did not move at all.**
Whatever made following cheaper over a full lap did not make the car grip better in the corner.
That is a genuinely odd pair of findings to hold at once, and we are publishing it as a pair rather
than picking the half that tells a cleaner story.

## What would change this result

Three things, named in advance:

1. **Per-corner gap exposure instead of a lap-level bit.** The treatment here is one binary per lap
   from one sector. A measure of actual exposure per corner would be a different, better instrument
   and could move every number above.
2. **A dose-response in gap rather than a 1.5-second threshold.** Everything here is the cost of a
   lap *classified* as following. A model in the gap itself would say whether the cost is smooth,
   and whether the decline is a decline in the cost of proximity or a change in how often cars are
   genuinely close.
3. **The same fit on a season this analysis has never seen.** 2025 onwards is the obvious test. If
   the trend is real and continues, θ stays at or below zero; if 2018–2024 was a fitted artefact of
   this population, it will not.

## Caveats, in the post and not in a reply

**2022 is a bundle, not an aero experiment.** The regulations arrived together with 18-inch tyres,
a minimum-weight rise of roughly 46 kg, and porpoising. Nothing in this analysis separates them.
The corner-class split is the only thing here that moves toward mechanism, and it is underpowered
to get there.

**The treatment is one bit per lap**, from a single sector-2 median gap crossing 1.5 seconds. No
dose-response. Nothing here is "x seconds per car length".

**The baseline is only mostly clean air.** The field-pace baseline is restricted to laps whose
dominant air state across the three sectors is free air or tow. But "following" is scored on sector
2 alone, so a lap can be treated on sector 2 and still be dominated by clean air overall:
**48.1% of treated laps enter the baseline anyway**, and **65.1% of treated laps carry a
non-dirty-air dominant state**. The measured level of θ is therefore a lower bound. The second
share is flat across seasons (63.1–66.1%), which is the argument for the season *contrast*
surviving it. The first is not: it drifts from 50.0% in 2018 to 40.9% in 2024, so the baseline is
cleaner in the later seasons than in the earlier ones. Both figures are reported rather than
corrected for.

**The baseline is a 5-lap centred rolling mean.** Field pace at lap *t* is averaged over laps *t*−2
to *t*+2, so the baseline is not a strictly backward-looking object. The treatment is lagged, so
the future is not inside the treatment — but the level of the outcome is not a real-time quantity.

**The 2021–2024 estimates failed their own placebo test.** We pre-declared one: refit with the
*next* lap's air state in place of the previous lap's. Dirty air is persistent, so a non-zero lead
coefficient is expected; the design fails if the lead is not materially smaller than the lag.
Lag / lead by season: 2018 **0.365 / 0.132**, 2019 0.134 / 0.099, 2020 **0.162 / 0.040**, 2021
0.068 / 0.073, 2022 −0.006 / 0.113, 2023 0.039 / 0.040, 2024 −0.044 / 0.042. The design holds for
2018 and 2020, is marginal for 2019, and **fails for 2021 through 2024**, where lag and lead are
the same size and both near zero. Those four seasons are reported as **no detectable directional
cost**, which is what their intervals say anyway — not as measured costs of following. The placebo
does not rescue a hidden late-era effect either; it says there is nothing there to certify in
either direction.

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

Our own table says 0.5 sits inside only 2018's confidence interval, and outside it in six seasons
of seven.

That defect is now fixed. The calibration panel keeps both arms, the coefficient is estimated
rather than defaulted, and the warehouse currently applies a fitted **0.131 s/lap** — about a
quarter of the constant it replaced. It is still a single global number: the
per-season fits in this post are **published, not shipped**, deliberately. The dirty-air tax sits
inside the label that several of our models are trained against, so making θ vary by season
rewrites the training target for the whole programme and is a change that has to go through the
full gate rather than ride along with a blog post.

Which is the honest summary of this item: the headline finding is that the 2022 regulations cannot
be credited with a decline that started in 2019, and the most useful finding is that we had been
quoting a number nobody ever fitted.

---

### Provenance

Panel: 123,993 laps, 2018–2024, from the production dirty-air calibration population — verified to
reproduce the shipped table's row count exactly and its per-season treatment mean to 1e-9 before
any coefficient was fitted. 93 fits in
[`06b_dirty_air_per_season.json`](06b_dirty_air_per_season.json), diagnostics in
[`06b_diagnostics.json`](06b_diagnostics.json), reproducible from `d0`–`d3` in this directory.
Fixed-effect absorption was cross-checked against a hand-written alternating-projection demeaning
and agrees to 1.6e-13.

The estimand, population, estimator ladder, era contrast, corner classes and both falsification
tests were **pre-registered before any coefficient existed**; the pre-registration is in
[`../../work/06-publication.md`](../../work/06-publication.md). Two deviations are logged there:
untreated laps were kept in the calibration sample (the whole point), and the headline corner
outcome is the mid-corner phase rather than the three-phase total, because the total sums a term
whose sign convention runs the other way.

**Status: written, not published.** Publishing is the user's call.
