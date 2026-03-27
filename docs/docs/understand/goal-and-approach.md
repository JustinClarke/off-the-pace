---
sidebar_position: 1
title: Goal & Approach
---

# Goal & Approach

## The question

When a car is off the pace, there are at least seven possible reasons: fuel load, tyre degradation, dirty air from a car ahead, safety car interference, weather, the car's structural pace relative to the field, and driver execution. In practice, commentary collapses all of these into "pace" or "strategy" without attribution.

Off The Pace exists to answer the attribution question precisely: **what fraction of a car's pace deficit on any given lap is explained by each named cause?**

## Why decomposition

The fundamental problem is that lap time is a single number that conflates everything. A driver who looks slow on lap 40 might be managing a tyre cliff, running in dirty air, or running heavy fuel, any of which would make a fast driver look slow. A driver who looks fast might be underweight and on fresh rubber.

The only way to extract a meaningful driver signal is to remove the physics first. Decomposition subtracts each measurable component (fuel, tyre age, air gap, and weather) and treats the residual as the driver's contribution. The residual is defined as a closure: whatever is left after accounting for everything else.

This is not a new idea in causal inference. It is how you separate signal from confounders when you cannot run a controlled experiment.

## What "additive" means

The decomposition is additive by design:

> `lap_time = baseline + tyre_deg + fuel_load + traffic + safety_car + weather + residual`

Each term has physical units (seconds). Positive = slower. Negative = faster. The terms sum to zero relative to the field baseline on every lap. This additivity is what makes the attribution interpretable: if `traffic = +0.4s` on lap 32, the car lost 400ms to dirty air that lap.

## The enforced invariant

Additivity is enforced in CI by `assert_additive_identity`. If the terms on any lap don't sum to zero within floating-point tolerance, the build fails. This is the most important engineering choice in the project; it makes the identity a contract, not an aspiration.

## What the project is not

This is not a lap time prediction model. It does not predict what lap time a driver *will* run. It attributes what lap time a driver *did* run to its components.

The ML component will predict tyre cliff onset and degradation rate (inputs to the decomposition), not lap times directly.
