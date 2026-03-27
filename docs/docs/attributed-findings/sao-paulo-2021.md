---
sidebar_position: 1
title: "São Paulo 2021: Was It the Driver or the Strategy?"
---

# São Paulo 2021: Was It the Driver or the Strategy?

On 14 November 2021, Lewis Hamilton started the Brazilian Grand Prix from tenth position a five-place grid penalty for an illegal rear wing had erased a sprint race victory. He won. The gap at the checkered flag to Max Verstappen was **10.5 seconds**.

The broadcast called it "brilliant driving." That is almost certainly true. But brilliant by how much? And how much of it was Mercedes handing Hamilton a structural advantage through a three-stop strategy?

Lap time alone cannot answer that question. This case study runs the 7-term decomposition on the race and finds a precise answer.

---

## The problem with lap time as a single number

Verstappen's lap times in the final stint looked nearly identical to Hamilton's, both running in the low 72s and low 73s. Commentary treated this as evidence of equal machinery and a racing contest decided by wheel-to-wheel skill.

The decomposition tells a richer story. That apparent equivalence was the **product of two opposing forces cancelling each other out**: Verstappen's tyres were aging faster (slowing him down), and Verstappen was pushing proportionally harder to compensate (speeding him up). Neither shows in the raw number.

The 7-term identity makes these forces visible by separating what the car produced from what the driver contributed:

> `lap_time = baseline + fuel_load + tyre_compound_age + tyre_rubber + dirty_air + ambient + constructor + driver_skill`

Each term is in seconds. Positive = slower than baseline. Negative = faster. The terms must sum to zero relative to field pace on every lap a contract enforced in CI by `assert_lap_7term_identity`. See the [seven-term identity reference](/understand/seven-term-identity) for the full formulation.

---

## The final stint: two drivers, two tyre ages

Hamilton pitted for the third time on lap 44. Verstappen had made his third stop on lap 41. That three-lap difference was small in the moment. By the end of the race, it was everything.

The table below shows selected laps from the final stint:

| Lap | Driver | Position | Tyre Age | Lap Time | Compound Penalty | Driver Skill | Dirty Air |
|-----|--------|----------|----------|----------|------------------|--------------|-----------|
| 45  | HAM    | P2       | 2        | 72.14 s  | +1.08 s          | −1.99 s      | 0.00 s    |
| 45  | VER    | P1       | 5        | 72.98 s  | +1.28 s          | −2.08 s      | 0.50 s    |
| 55  | HAM    | P2       | 12       | 72.56 s  | +1.87 s          | −2.57 s      | 0.50 s    |
| 55  | VER    | P1       | 15       | 72.49 s  | +2.19 s          | −2.69 s      | 0.00 s    |
| **59** | **HAM** | **P1** | **16** | **72.38 s** | **+2.30 s** | **−3.11 s** | **0.50 s** |
| **59** | **VER** | **P2** | **19** | **74.07 s** | **+2.66 s** | **−1.51 s** | **0.00 s** |
| 65  | HAM    | P1       | 22       | 72.95 s  | +5.46 s          | −5.44 s      | 0.00 s    |
| 65  | VER    | P2       | 25       | 73.66 s  | +8.30 s          | −7.79 s      | 0.00 s    |
| 71  | HAM    | P1       | 28       | 73.86 s  | +11.17 s         | −9.72 s      | 0.00 s    |
| 71  | VER    | P2       | 31       | 74.93 s  | +14.08 s         | −12.86 s     | 0.00 s    |

*Compound penalty = `compound_component_s` from `fct_lap_residuals`. Driver skill = `driver_skill_residual_s`. Positive = slower than field baseline. Negative = faster.*

Three things stand out immediately.

---

## Finding 1: The cars were equal when conditions were equal

At the start of the final stint (laps 45–50), Hamilton's average lap time was **72.36 s** and Verstappen's was **72.77 s** a 0.41 s gap that almost exactly matches the difference in their tyre ages (Hamilton age 2–7, Verstappen age 5–10). Adjust for the compound penalty difference and the two cars are running the same pace.

This matters. The race was not decided by constructor advantage. Red Bull and Mercedes had identical structural pace at Interlagos that day. Everything that followed was strategy and driver execution.

---

## Finding 2: Strategy created a 2.9-second tyre advantage

Compound penalty grows roughly linearly with tyre age once a set is past its initial window. By the final lap:

- **Hamilton**: compound penalty **+11.17 s** (28 laps on this set)
- **Verstappen**: compound penalty **+14.08 s** (31 laps on this set)
- **Structural delta**: **2.91 s** in Hamilton's favour

That 2.91 s was manufactured entirely by Mercedes' decision to make a third pit stop at lap 44 rather than running the tyres to the flag on a 36-lap stint. Hamilton gave up track position temporarily; the model shows exactly what he got back.

---

## Finding 3: The overtake was skill and strategy in roughly equal measure

Lap 59 is where Hamilton passed Verstappen for the lead and held it to the flag.

The decomposition of the 1.69 s lap time gap on that lap:

| Component | Value | Explanation |
|-----------|-------|-------------|
| Tyre age delta | +0.36 s | VER was 3 laps older on this set |
| Driver skill delta | +1.59 s | HAM residual −3.11 s; VER residual −1.51 s |
| Dirty air (HAM) | −0.50 s | Hamilton absorbed 0.5 s wake penalty in VER's slipstream |
| **Total explained** | **+1.45 s** | (remaining gap from ambient/rubber components) |
| **Actual gap** | **1.69 s** | |

Hamilton was penalised **0.5 s** that same lap for running in Verstappen's dirty air, and the model separates this out from the skill residual. Strip out the dirty air and Hamilton's net driving advantage was **1.59 s**, which combined with the **0.36 s** tyre edge made the pass stick.

Neither component alone was decisive. The strategy manufactured 0.36 s; the driver delivered 1.59 s.

---

## The dirty air penalty that never made the headlines

Here is a less-told part of the story. From the moment Hamilton rejoined the track in the final stint, he spent **13 of his first 14 racing laps** in Verstappen's wake, accumulating a **6.5 s dirty air penalty**.

![Component evolution: final stint](/img/case-studies/sao-paulo-2021/final-stint-components.png)

*Top panel: compound penalty growing with tyre age. Verstappen (red) degrading faster on a 31-lap set vs Hamilton (teal) on 28. Bottom panel: driver skill residual deepening as both drivers push harder to compensate. Vertical dashed line = lap 59 overtake.*

The model attributed those 6.5 s to dirty air rather than to Hamilton's pace. Without the decomposition, a commentator watching the lap times would see Hamilton running 72.5 s while stuck behind a 72.7 s Verstappen and conclude he was "conserving" or had "similar pace." The decomposition shows Hamilton was already being slowed: his car was capable of 72.0–72.1 s in clean air, as the laps 59–65 (after the pass) confirm.

---

## How the skill residuals grew

![Lap decomposition: key moments](/img/case-studies/sao-paulo-2021/lap-decomposition-bars.png)

*Faded bar = structural lap time (car + tyre age + fuel, no driver contribution). Solid bar = actual driven time. The number inside the faded bar shows the driver skill residual: how much faster the driver was than the car's structural prediction. Both drivers are outdriving their tyres, but by very different amounts as the stint progresses.*

The chart reveals something counterintuitive. By lap 65, Verstappen's tyre penalty was **+8.30 s** but his skill residual was **−7.79 s**: he was nearly fully compensating for degraded rubber through effort. Hamilton's tyre penalty was **+5.46 s** with a residual of **−5.44 s**, doing the same thing but starting from a fresher base.

By the final lap:
- Verstappen was outdriving his tyres by **12.86 s/lap** just to run 74.9 s
- Hamilton was outdriving his tyres by **9.72 s/lap** to run 73.9 s

Both numbers are extraordinary. A driver running 9–13 seconds faster than the model's structural prediction on a single lap is not conserving: that is the upper limit of what a human can extract from a degraded compound at racing speed.

From lap 59 to the flag (13 laps), Hamilton's cumulative time was **950.9 s** against Verstappen's **961.9 s**. The 11-second winning margin was entirely accumulated after the overtake.

---

## What this means

Three things the decomposition separates that commentary could not:

**1. Constructor pace was neutral.** Neither team had a structural speed advantage that day. Every second of margin was earned in the pits or on the wheel, not by the engineers who built the car.

**2. The strategy was the setup, not the win.** Mercedes' three-stop created a **2.91 s structural tyre advantage** by the final lap. That was a necessary condition for Hamilton's race. But on its own, a 0.36 s tyre delta on the pass lap was not enough. The driver closed the rest.

**3. Both drivers were at the limit.** Verstappen's −12.86 s skill residual on the final lap is not the signature of a driver who was beaten easily. It is the signature of a driver who was losing a structural battle he could not fully overcome, and trying everything to compensate. A different strategy call and that drive would have won the race.

---

## What comes next

This is the first attributed finding from the Off The Pace pipeline. The same decomposition runs across **168 races (2018–2024)** with 7 seasons of data. The questions it can answer at scale (which drivers consistently outperform their equipment, how teams' structural pace evolves across a season, which circuits amplify dirty air most) are the subject of the React application currently in development.

São Paulo 2021 was chosen as the first case study because it is a race where the outcome seems explicable by feel. The data shows the feel was right for the wrong reasons, and more precisely right than any broadcast account captured.

---

<details>
<summary>Technical sidebar: the 7-term identity</summary>

The decomposition identity (all terms in seconds, positive = slower than field baseline):

```
lap_time_s = field_pace_baseline
           + fuel_component_s          -- fuel mass × circuit weight penalty
           + compound_component_s      -- compound type + age degradation curve
           + rubber_component_s        -- surface rubber thermal hysteresis
           + ambient_component_s       -- air density, temperature delta
           + constructor_component_s   -- structural pace relative to field
           + dirty_air_tax_s           -- wake penalty from car ahead
           + driver_skill_residual_s   -- closure residual (what's left)
```

The identity is enforced lap-by-lap in CI by the `assert_lap_7term_identity` dbt test, which calls the `assert_additive_identity` macro:

```sql
-- transform/tests/assert_lap_7term_identity.sql
{{ assert_additive_identity(
     ref('int_lap_residual_decomposed'),
     'pace_delta_s',
     ['fuel_component_s', 'compound_component_s', 'rubber_component_s',
      'ambient_component_s', 'constructor_component_s', 'dirty_air_tax_s'],
     'driver_skill_residual_s',
     tolerance=0.0001
) }}
```

If any lap fails this test, the dbt build fails. This makes the identity a contract, not a post-hoc approximation. The São Paulo 2021 data passes with zero violations.

The `compound_component_s` term used in this case study combines the compound-type effect (Hard vs Medium baseline pace delta) with the age-degradation curve fitted per `(circuit, compound, season)` in `dim_compounds_season`. The dramatic growth from +1.08 s at age 2 to +14.08 s at age 31 reflects the expected degradation trajectory for a Hard compound at Interlagos in 2021, not a modelling artefact.

Full methodology: [Seven-Term Identity](/understand/seven-term-identity) · [Methodology](/understand/methodology)

Data source: [`fct_lap_residuals`](/reference/models/fct/fct_lap_residuals)

</details>
