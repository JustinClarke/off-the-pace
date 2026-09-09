# 07 — Causal pit timing: the safety car as a natural experiment

**Group:** 07 · **Depends on:** `00b` (landed) · **Cost:** hours → 1–2w
**Parallel to the ML ladder.** Uses the warehouse, not the feature contract.

The highest-value research direction in the programme, and it exists because of a number
measured on 2026-09-07 while closing `00b`.

## The problem this solves

`int_pit_strategy_value` is honest about its own limit — its header says *"counterfactual cost
calculation, not causal inference"*. It scores the actual pit lap against a modelled tyre
optimum. That is a **descriptive** gap, and it cannot separate two very different worlds:

- late pitting *caused* the lost time, or
- the car was already struggling, which is *why* it was still out there.

Teams do not pit at random. Every naive comparison of early vs late pitting is confounded by
the state that produced the decision. This is the reason `06a` can publish a distribution but
not a claim about what teams *should* do.

## The identification

**Verified 2026-09-07 (`00b`).** 26.87% of uncensored stint ends (a real pit decision,
n=5,360) fall on a lap flagged `is_safety_car_lap` or `is_vsc_lap`, against 6.49% of censored
stints. Present in all seven seasons, 21–36%.

A safety car is deployed because **another driver** crashed or stopped. Conditional on a given
car's own tyre state, its arrival is close to exogenous — it assigns an earlier pit than the
team planned. That is an instrument for pit timing, and the first stage is large.

## Threats to identification — name them before running anything

Not incidental. Each needs a stated treatment or the design is decorative.

1. **SCs are not unconditionally random.** They cluster on street circuits, in rain, and on
   lap 1. Condition on circuit, era and `rainfall_flag` (`int_track_evolution`) at minimum.
2. **Common shock.** Under an SC the whole field pits, and the pit-lane time loss itself
   falls. So the treatment bundles "pitted earlier" with "pitted cheaply". Separating them is
   the core design problem, not a caveat to mention at the end.
3. **The excluded restriction is the weak point.** An SC affects the outcome through channels
   other than pit timing — field compression, position changes, tyre temperature on the
   restart. State plainly which outcome the exclusion is defensible for. It is far more
   defensible for a *pace/degradation* outcome than for finishing position.
4. **Censoring.** 46.2% of stint-life rows are right-censored. The estimand must be defined
   on stints that had a real decision, per `00b`'s censoring split.

## 07a — Feasibility, before any estimator

**Objective.** Establish whether the first stage survives the conditioning, before a week is
spent on the design.

**Method.** Read-only. Count matched pairs: same circuit, same era, similar tyre age and
similar pre-SC degradation state, one arm SC-assigned and one not. Report how many survive,
and how thin the thinnest identifying cell is — the same shape of go/no-go `03a` runs for the
mover panel.

**Definition of done.** A matched-pair count with the conditioning set stated; a go/no-go on
`07b`; and if no-go, the reason recorded so it is not re-proposed.

## 07b — The estimator

**Blocked on `07a`.** Design written only once the first stage is known to survive. Pre-register
the arms per [`../foundations/gates.md`](../foundations/gates.md) step 6 before running them —
this item is exactly the kind of flexible design that multiplicity punishes.

**Definition of done.** An effect with an interval, the exclusion restriction argued for the
specific outcome chosen, all four threats above addressed in the write-up, and a stated
falsification test.
