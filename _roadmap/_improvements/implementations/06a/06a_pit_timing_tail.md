# The pit call that costs a team a second doesn't make headlines. The one that costs 15 does.

*Status: DRAFT — analysis verified 2026-09-20, not yet published. Publish/order decision is
`D15`, tracked in `_improvements/status/build-log.json`.*

Every strategy inquest after a race focuses on one pit stop — the one that went wrong. That's
the wrong frame. Across seven seasons and 7,129 race stints (2018–2024), the average pit call
is close to perfect. The story isn't the average. It's the tail.

## The headline: most stops are fine, and then there's a cliff

We took every stint in the dataset and asked a narrow question: given what the tyre was doing,
when *should* this car have pitted, and how many seconds did the team actually lose by pitting
when they did? That's not "was this the right race strategy" — it's narrower and more
answerable: "was this the right lap to come in, given the tyre alone?" More on that distinction
below, because it matters for how to read every number here.

The distribution:

- **Median cost: 0.12 seconds.** Half of all stints are within a tenth of a second of the
  tyre-optimal lap.
- **47% of stints score exactly zero.** But that number is doing two different jobs at once —
  42% of all stints never pit again for the rest of the race, so there's no decision left to
  grade (that's a structural zero, not a good call). Strip those out and **5.4% of all stints
  pitted and landed on the exact optimal lap.**
- **Mean cost: 5.33 seconds** — four and a half times the median. That gap between the median
  and the mean *is* the finding: a few stints are losing a lot of time, and they're dragging the
  average up while telling you nothing about the typical stop.
- **The worst 10% of stints account for 61% of all the time lost to pit timing across the
  entire dataset.** One decile carries almost two-thirds of the total damage.

That's the number to take away: pit-timing losses aren't spread evenly across a season. They're
concentrated in a small number of specific, identifiable calls — the ones where a team
overshot a tyre by five or six laps, or pitted early into a phantom threat that didn't
materialize. Chasing "our average pit loss" is chasing noise. Chasing "how often do we land in
the bad 10%" is chasing something real.

| Percentile | Seconds lost |
| :--- | ---: |
| 50th (median) | 0.1 |
| 90th | 17.0 |
| 95th | 23.7 |
| 99th | 59.0 |
| Worst stint in 7 years | 240.7 |

## By constructor — who's in the tail more often

Restricted to constructors with more than 150 qualifying stints (some of these are the same
outfit under a different name across the rebrand years — noted below), ranked by mean seconds
lost per stint:

| Constructor | n | Mean cost (s) | Seasons |
| :--- | ---: | ---: | :--- |
| Ferrari | 701 | 4.24 | 2018–2024 |
| Red Bull Racing | 733 | 4.62 | 2018–2024 |
| Renault | 250 | 4.62 | 2018–2020 |
| Aston Martin | 453 | 4.74 | 2021–2024 |
| Alpine | 425 | 5.26 | 2021–2024 |
| Racing Point | 212 | 5.41 | 2018–2020 |
| AlphaTauri | 413 | 5.50 | 2020–2023 |
| Haas | 705 | 5.56 | 2018–2024 |
| Williams | 715 | 5.59 | 2018–2024 |
| McLaren | 718 | 5.69 | 2018–2024 |
| Mercedes | 758 | 5.83 | 2018–2024 |
| Alfa Romeo | 219 | 6.17 | 2022–2023 |
| Alfa Romeo Racing | 291 | 6.45 | 2019–2021 |
| Toro Rosso | 175 | 7.26 | 2018–2019 |

A few honest notes on reading this table:

- **This is a mean over a right-skewed distribution**, exactly like the field-wide number above.
  A team's position here can be moved a lot by a handful of bad stops, not by a systematically
  worse process. We're showing it because "who's best" is the question people actually want
  answered, not because the mean is the statistically cleanest way to answer it — the field-wide
  distribution above is.
- **The gap between best and worst here (Ferrari 4.24 s vs. Toro Rosso 7.26 s) is about 3
  seconds a stop.** Over a season with roughly two stops a race, that's single-digit seconds of
  championship position — real, but not the multi-second strategic disasters that make
  highlight reels. Those live in the tail, not in the team-average gap.
- **Team names span rebrands.** Racing Point became Aston Martin in 2021; Renault became Alpine;
  Toro Rosso became AlphaTauri (which later became RB, not shown here — under 150 stints in the
  window). We kept them as separate rows rather than merging by "lineage," because the personnel
  and car underneath changed too.
- We also computed a harsher, alternative version of this number — "if this had been the team's
  last stop of the race, not just the next one" — and it doesn't reorder this table materially.
  It's a robustness check, not a different finding.

## Why this isn't "which team is bad at strategy"

Here's the part that matters more than the ranking: **this number measures the pit call against
the tyre, not against the race.**

The model behind these numbers looks at how a tyre was degrading and asks: given only that,
what's the lap that minimizes total time lost? It has no idea whether a safety car was coming,
whether a rival just pitted and opened an undercut window, or whether track position was worth
protecting at the cost of a slightly worn tyre. It is, deliberately, a narrower question than
"did the team win the race with this strategy."

That distinction cuts both ways, and it's the reason this number is actually useful to a fan
rather than just another team-bashing stat:

- **A team that scores well here and still gets criticized in the paddock afterward is not
  necessarily making a modeling error — it's making a *judgment call* the tyre model can't see.**
  Reacting to a rival's undercut, or covering a safety-car risk, can be the *correct* strategic
  decision while still costing time against the tyre-only optimum. That's not a mistake; that's
  a trade-off the model doesn't get to weigh in on.
- **A team that scores badly here has left time on the table that no amount of race-craft
  explains** — the tyre alone says they were several laps past where the tyre wanted to come in,
  independent of what anyone else on track was doing.

That's two different failure modes that get flattened into one "bad pit call" story in most
race commentary. This number lets you tell them apart.

## What this number can and can't tell you

Three caveats, stated plainly because they change what you can claim with this data:

1. **No track position or undercut modeling.** The tyre-optimal lap and the strategically-optimal
   lap are different questions, and this only answers the first one. A stop that "cost" seconds
   against the tyre model may have gained track position that was worth more.
2. **Safety cars and virtual safety cars aren't a decision input.** The model doesn't know a
   caution period is coming and can't credit a team for correctly gambling on one (or debit them
   for missing one). Every SC-timed "free" stop in this dataset is scored purely against the
   tyre, which will make some genuinely smart calls look average and some genuinely lucky ones
   look smart.
3. **"Optimal" means the minimum of a modeled cost curve, not a physical fact.** The optimal lap
   is whichever lap comes out lowest when you run a tyre-degradation model plus a pit-lane-loss
   estimate forward from every candidate lap and take the best one. It inherits every assumption
   in that model. If the tyre model is wrong in a particular way, "optimal" is wrong in the same
   way, consistently, for every team — which is fine for *comparing* teams against each other,
   and a real limitation if you want to read too much into an individual number.

## Where this came from

Measured from `int_pit_strategy_value` in the warehouse, rebuilt fresh from the current model
code on 2026-09-20 (all 162 dbt tests passing). The reproducible query is in
`query.sql` next to this file.

Worth flagging for anyone digging into the history here: **two earlier passes at this same
analysis produced two different, both now-outdated, sets of numbers** — one from before a
safety-car data join-key fix (2026-09-11), one from after that fix but before a tyre wear-model
correction (2026-09-17) that changed the shape of the cost surface these numbers are computed
from. Neither is wrong in the sense of being computed incorrectly — they're measuring the same
thing, correctly, against a warehouse that has since been corrected twice. The numbers above are
current as of the date on this draft; if this post sits unpublished for a while, it's worth a
quick re-run of `query.sql` before it goes out, the same way this draft caught the last two
drifts.
