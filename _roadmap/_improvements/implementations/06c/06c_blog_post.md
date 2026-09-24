# Does Verstappen actually brake later? Yes — and finding out cost us our leaderboard

*Corner-phase skill, 2018–2024. Rewritten 2026-09-20 after a sign fix to the underlying index.*

Every F1 broadcast eventually reaches the same sentence: *nobody brakes later than Verstappen*. It
is the kind of claim that sounds unfalsifiable, gets repeated for a decade, and never gets a number
attached to it.

We attached a number to it, and the first answer came back backwards. Our corner-skill index said
Verstappen was the weakest braker at Red Bull. That result was wrong, and it was wrong because of
us, not because of him. This post is what the data says now that the defect is fixed, plus the
story of the defect — which turned out to be the more useful half.

---

## What we measure, in one paragraph

We split every corner a car takes into three phases and compare each one against the rest of the
field at that corner, on that lap:

| Phase | What it compares | Negative means |
| :--- | :--- | :--- |
| **Braking** | Where the driver first gets on the brakes | Braking **later** — time gained |
| **Mid-corner** | Minimum speed through the corner | Carrying **more** speed |
| **Exit** | Where the driver gets back on the throttle | On the power **earlier** |

All three are expressed in seconds, and all three follow one rule: **negative is faster, positive
is time lost**. Each driver's per-corner residual is then compared to their own teammate's, averaged
over the season, standardised within that season, and the three standardised phases are summed into
a `corner_skill_index` where lower is better.

That one rule in bold is the whole story of this post. Until two days ago, the braking phase did not
follow it.

---

## The defect

`braking_loss_s` was built as *(own braking point − field median)*. A driver's braking point is
measured as distance along the lap, so braking later gives you a **larger** number. Positive meant
later, which meant faster.

The other two phases were built the other way round, where positive meant slower. The index summed
all three and ranked ascending. So for seven seasons, our published leaderboard rewarded drivers for
**braking early**.

Two separate pieces of work walked into this from opposite directions:

1. **This one.** Verstappen kept coming out as a weak braker against Pérez, which contradicted
   roughly everything anyone has ever said about him. We wrote it up as an open question with two
   candidate explanations and declined to publish it as a finding.
2. **A dirty-air study running alongside it.** It found that following another car produces a
   negative `braking_loss_s` in every corner class and both aero eras. Dirty air removes downforce.
   Removing downforce can only make you brake *earlier*. A column where "earlier" came out negative
   and negative counted as skill could not be measuring skill.

The second route is the convincing one, because its direction is known from physics before you look
at the data. The fix went in at the source, so all three phases now share one convention, and a test
now pins the direction against the raw telemetry geometry so it cannot come back. That test, run
against the old code, fails on 98,769 of 98,769 eligible corner groups.

---

## The two explanations we named, and which one won

When we first wrote this up, we refused to call the Verstappen result a finding and instead named
two things it could be. For the record, both are listed here with what happened to them:

**Explanation 1 — the index has the braking sign inverted.** Falsification named at the time:
inspect the SQL that builds the braking z-score and check its sign against the other two phases.
**Confirmed.** That is exactly what had happened. (Our own note pointed at the wrong model to
inspect; the sign was set two models further upstream than we guessed.)

**Explanation 2 — Pérez was genuinely a strong braker in 2024, and the teammate baseline makes
Verstappen look weak by comparison.** Falsification named at the time: check Verstappen's braking
against teammates who are not Pérez. **Not needed, but we ran it anyway** — see the seven-season
table below. It does not hold: the pattern is the same against Albon and against Gasly, and it is
absent only against Ricciardo.

The anomaly did not survive. It dissolved in the direction of the received wisdom.

---

## So: does he brake later?

Yes, and it is not close.

Here is Verstappen's braking residual against whoever was in the other Red Bull, every season we can
measure. These come from the corrected index, one row per season:

| Season | Teammate | `braking_skill_s` | SE | Corner-cells | Reads as |
| :--- | :--- | ---: | ---: | ---: | :--- |
| 2018 | RIC | **+0.0036** | ±0.0189 | 211 | No difference detectable |
| 2019 | GAS / ALB | −0.0492 | ±0.0140 | 253 | Brakes later |
| 2020 | ALB | **−0.1566** | ±0.0220 | 182 | Brakes later, by a lot |
| 2021 | PER | −0.0770 | ±0.0148 | 241 | Brakes later |
| 2022 | PER | −0.0426 | ±0.0127 | 293 | Brakes later |
| 2023 | PER | −0.0403 | ±0.0152 | 273 | Brakes later |
| 2024 | PER | −0.0745 | ±0.0151 | 282 | Brakes later |

Six seasons out of seven, against four different teammates. The exception is 2018 against Daniel
Ricciardo, which is a pleasing result if you remember Ricciardo's reputation, and which is also
statistically indistinguishable from zero — we are not claiming Ricciardo out-braked him, only that
we cannot tell them apart.

### The honest version of those standard errors

The SEs above treat every corner-cell as an independent observation. They are not independent: a
driver's ~280 corner-cells in a season nest inside ~22 races, and everything about a race weekend
correlates within it. Quoting a t-statistic off those SEs would flatter the result.

So we re-ran the question at race level, which is both more honest and easier to picture. For each
race, take Verstappen's average braking residual minus his teammate's on the corners they both ran,
then treat each race as one observation:

| Season | Teammate | Mean diff (s) | Race-clustered SE | t | Races he braked later |
| :--- | :--- | ---: | ---: | ---: | :--- |
| 2018 | RIC | +0.0056 | ±0.0346 | 0.16 | 7 of 17 |
| 2019 | GAS / ALB | −0.0470 | ±0.0252 | −1.87 | 17 of 20 |
| 2020 | ALB | −0.2592 | ±0.1230 | −2.11 | 14 of 15 |
| 2021 | PER | −0.0623 | ±0.0292 | −2.13 | 14 of 19 |
| 2022 | PER | −0.0503 | ±0.0139 | −3.62 | 18 of 22 |
| 2023 | PER | −0.0366 | ±0.0260 | −1.41 | 16 of 21 |
| 2024 | PER | −0.0816 | ±0.0197 | −4.13 | 18 of 22 |
| **2019–2024 pooled** | | **−0.0814** | **±0.0185** | **−4.39** | **97 of 119** |

Individual seasons range from convincing to merely suggestive — 2023 on its own would not settle an
argument. The pooled result does. **In 97 of 119 races across six seasons, Verstappen braked later
on average than the other Red Bull.** Against a coin-flip null that is a sign test with a p-value of
about 2 × 10⁻¹², and it does not lean on the optimistic standard errors at all.

### In metres, for the pub argument

Seconds are the right unit for an index and the wrong unit for a conversation. The same comparison,
measured as raw distance along the lap:

| Season | Teammate | Metres later on the brakes | SE |
| :--- | :--- | ---: | ---: |
| 2018 | RIC | +0.9 | ±2.2 |
| 2019 | GAS / ALB | +3.2 | ±1.9 |
| 2020 | ALB | +18.4 | ±8.8 |
| 2021 | PER | +5.2 | ±1.9 |
| 2022 | PER | +2.6 | ±1.6 |
| 2023 | PER | +2.1 | ±1.8 |
| 2024 | PER | +5.8 | ±1.3 |
| **2019–2024 pooled** | | **+5.6** | **±1.3** |

**About five and a half metres.** That is roughly a car and a bit, averaged over every corner of
every race for six years. The 2020 number against Albon is the eye-catching one and also the least
trustworthy: 15 races, a standard error of nearly 9 metres, and a season in which the second Red
Bull was famously not a happy place.

Treat the metres as the intuitive number and the seconds as the fair one. Five metres at the end of
a 300 km/h straight is worth far less time than five metres into a hairpin, and only the seconds
version accounts for that.

---

## Verstappen's 2024, all three phases

Braking is the headline, but it is not where his biggest edge is. Against Pérez in 2024, race-clustered:

| Phase | Mean diff (s) | Race-clustered SE | t | Races ahead |
| :--- | ---: | ---: | ---: | :--- |
| Braking | −0.0816 | ±0.0197 | −4.13 | 18 of 22 |
| **Mid-corner** | **−0.0795** | **±0.0126** | **−6.33** | **20 of 22** |
| Exit | +0.0483 | ±0.0124 | +3.90 | 5 of 22 |

The mid-corner gap is the most consistent thing in the table — he carried more apex speed than Pérez
in 20 of 22 races. The exit row runs the other way, and that is not a rounding artefact:
**Verstappen gave time back getting on the power**, in 17 of 22 races, at a t of +3.90.

The composite picture, which no single clip on social media will ever show you: he arrives later,
carries more speed through the middle, and concedes a little on the way out. Whether that is a style
choice, a setup consequence, or the price of the first two is not something this measurement can
answer.

---

## The Norris re-read

Our previous draft said Norris topped the 2024 corner-skill index at −3.17, and that his edge was
traction rather than braking. The first half of that is now false and the second half is more true
than we realised.

The sign fix moved 122 of 139 scored driver-seasons in the rankings, and changed the leader in six of
seven seasons. Norris led four seasons before the fix and leads none after. In 2024 he drops from
1st to 4th:

| 2024 | Driver | Team | Braking z | Mid z | Exit z | **Index** |
| ---: | :--- | :--- | ---: | ---: | ---: | ---: |
| 1 | GAS | Alpine | −2.18 | −1.15 | −0.43 | **−3.76** |
| 2 | **VER** | Red Bull | −1.30 | −2.12 | +0.46 | **−2.96** |
| 3 | ZHO | Kick Sauber | −0.80 | −1.15 | −0.27 | −2.22 |
| 4 | **NOR** | McLaren | **+0.74** | −0.24 | **−2.19** | **−1.69** |
| 5 | RUS | Mercedes | −0.89 | −0.16 | −0.36 | −1.41 |
| … | | | | | | |
| 17 | PIA | McLaren | −0.74 | +0.24 | +2.19 | +1.69 |
| 19 | PER | Red Bull | +1.30 | +2.12 | −0.46 | +2.96 |
| 20 | OCO | Alpine | +2.15 | +1.13 | +0.43 | +3.71 |

Norris's exit z of −2.19 is the single largest phase term anywhere in the 2024 table. His raw exit
number is −0.2669 s against Piastri (±0.0392, 76 corner-cells) — more than six times his braking
term. So "Norris's 2024 edge was traction, not braking" survives, and sharpens into something more
specific:

| NOR vs PIA, 2024 | Mean diff (s) | Race-clustered SE | t | Races ahead |
| :--- | ---: | ---: | ---: | :--- |
| Braking | **+0.0502** | ±0.0160 | +3.13 | **6 of 24** |
| Mid-corner | −0.0108 | ±0.0086 | −1.25 | 12 of 24 |
| Exit | −0.1930 | ±0.1056 | −1.83 | 12 of 14 |

**Norris braked earlier than Piastri in 18 of their 24 shared races**, and that is the most
statistically solid line in the whole McLaren comparison. His advantage was entirely on corner exit,
and he paid for part of it on entry.

The exit figure carries the biggest health warning on this page. McLaren has the thinnest exit
sample in the 2024 field — 76 corner-cells against 246 for Red Bull, and only 14 races with usable
paired data. The magnitude is genuinely uncertain. The *direction* holds up better than the
magnitude: Norris was ahead on exit in 12 of those 14 races.

---

## What the leaderboard actually measures, and why Gasly is top of it

This is the caveat that matters most, and it is the one most likely to be stripped off if a single
row of this table ever gets screenshotted.

**Every number here is measured against the driver's own teammate.** The baseline for each driver is
the other person in the same car. With two drivers per team that makes the comparison exactly
symmetric: Verstappen's −0.0745 and Pérez's +0.0745 are not two findings, they are one number
written twice. You can see it in the table above — rows 2 and 19 are mirror images, as are 4 and 17.

So Pierre Gasly topping the 2024 index does not mean Gasly was the best corner driver in Formula 1
in 2024. It means **Gasly beat Ocon in all three phases by more than anyone else beat their
teammate**, which he did, convincingly:

| GAS vs OCO, 2024 | Mean diff (s) | Race-clustered SE | t | Races ahead |
| :--- | ---: | ---: | ---: | :--- |
| Braking | −0.1483 | ±0.0433 | −3.43 | 16 of 19 |
| Mid-corner | −0.0368 | ±0.0094 | −3.93 | 16 of 19 |
| Exit | −0.0550 | ±0.0122 | −4.51 | 16 of 19 |

A clean sweep of a teammate is what this index rewards. It is a real result about the Alpine garage
and it is not a claim about Gasly versus Verstappen, because those two numbers are measured against
different people. There is no common yardstick in this data. Building one is a different project.

The same caveat runs the other way. A driver stuck alongside a very strong teammate will look
mediocre here no matter how quick they are, and Verstappen sitting second rather than first is partly
a statement about Pérez.

---

## How it is built, and what we would still like to fix

**The sample.** 141 driver-seasons, 2018–2024. A phase scores only if it has at least 30
(driver, race, corner) cells behind it, and the index needs all three phases, so 139 of the 141
score. The two that miss are Norris and Sainz in 2019, both on exit data at 21 cells.

**Cell counts and errors.** Every number above is quoted with its cell count or race count. The
per-season standard errors in the first table are `STDDEV(cells)/√N` over corner-cells and are
optimistic for the clustering reason given earlier — that is why every claim we actually lean on is
stated at race level instead.

**Winsorization.** Each cell is clipped to ±1.0 s before averaging, so one anomalous corner cannot
carry a season. This does mean genuinely extreme single corners are pulled in.

**Field medians are backward-looking.** Each corner is compared to the field over the previous five
laps, never the current one or later ones. Lap 2 has no comparison set and returns nothing.

**The exit phase is the weak one.** It has the fewest cells across the board and the widest errors,
and the spread between teams is large — 76 cells for McLaren against 262 for Kick Sauber in 2024.
Any exit-based claim in this post is the least durable claim in it.

**What would change our mind on Verstappen.** A race-clustered pooled result that crossed zero, or a
teammate other than Ricciardo against whom the sign flipped. Neither is in the data we have. If
somebody finds a systematic reason a driver's telemetry reports a later first-brake sample without
them actually braking later, that would do it too — we looked and did not find one, but that is the
shape of the argument that would work.

---

## The part worth keeping

The Verstappen result is the headline, and it is a headline that says a thing everyone already
believed. That is a perfectly good outcome for a measurement — received wisdom is usually received
for a reason, and now there is a number on it: about five and a half metres, in 97 of 119 races.

But the more useful story is the one about us. We published a leaderboard that rewarded braking
early, and it survived because nobody on it ever looked obviously wrong enough to trigger an audit.
It took a driver whose reputation is so specific and so universally agreed that a single contrary
number felt worth stopping for, plus a completely unrelated study about following another car, to
catch it.

The lesson we are taking is not "check your signs". It is that the anomaly was the alarm working. If
we had trusted our own index over the received wisdom, we would have published a leaderboard that had
one of its three ingredients backwards, and we would still be publishing it.

---

### Provenance

Corrected index from `mart_corner_skill_driver`, rebuilt after the sign fix. Race-clustered figures
computed from `int_corner_skill_residuals` and `int_corner_metrics` for this post. Metres computed
from `braking_point_m`, a telemetry-derived distance along the lap at the first braking sample, so it
is an estimate at the resolution of the telemetry, not a surveyed brake-marker distance.

**Status: drafted, not published. Publication is decision D15.**
