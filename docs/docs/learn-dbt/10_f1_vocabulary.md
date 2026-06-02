---
sidebar_position: 11
title: "Part 10: F1 Vocabulary"
---

# Part 10: F1 vocabulary appendix

Every F1 term used in this guide, defined in one sentence.

---

## Tyres and compounds

**Compound**: the rubber formula for a tyre set; in F1 there are five: C1–C5 mapped to Soft/Medium/Hard (dry), Intermediate (light wet), and Wet (heavy wet).

**Tyre life / age in stint**: how many laps a set of tyres has been on the car; tyre performance degrades with age.

**Stint**: the sequence of consecutive laps a driver completes on a single set of tyres, from pit-out to pit-in.

**Cliff**: the point in a tyre's life where degradation accelerates sharply; a tyre losing 0.05 s/lap can suddenly start losing 0.3 s/lap when it "goes off the cliff."

**Degradation**: the pace loss a tyre accumulates over its life due to heat cycling, wear, and surface chemistry changes.

**Push**: driving at high effort (aggressive throttle, late braking), which heats the tyres faster and accelerates degradation.

**Lift-and-coast**: deliberately backing off the throttle before a braking zone to save fuel or tyres, sacrificing lap time for strategic purposes.

**Fuel saving**: driving at reduced effort to manage fuel consumption when the car is heavier than planned.

---

## Race control events

**Safety car (SC)**: a physical Mercedes-AMG car deployed on track during incidents; all drivers must slow to a delta time and cannot overtake.

**Virtual safety car (VSC)**: an electronic delta-time limit imposed without a physical car; drivers slow but not as severely as under a full SC.

**Red flag**: the race is suspended; all cars must slow and return to the pit lane or grid.

**Yellow flag**: a hazard is present in a sector; drivers must slow and cannot overtake in that sector.

**DRS (Drag Reduction System)**: a rear wing flap a driver can open when within 1 second of the car ahead at specific detection points; reduces drag and increases straight-line speed to facilitate overtaking.

**Restart**: the lap immediately after a SC period ends; pace returns to racing speed.

---

## Aerodynamics and car performance

**Downforce**: aerodynamic force pressing the car into the track; enables faster cornering but increases drag.

**Dirty air**: turbulent air created behind a car at speed; following drivers lose downforce and get increased front-tyre temperatures.

**Free air**: racing without another car close enough to cause aerodynamic interference.

**Tow zone**: being close enough to the car ahead (roughly 1–3 seconds) to benefit from the slipstream (reduced drag) without severe downforce loss.

**Constructor**: the F1 team that builds the car (e.g. Mercedes, Ferrari, Red Bull).

**Power unit (PU)**: the hybrid power system: internal combustion engine + energy recovery systems. Teams supply PUs to multiple constructors (e.g. Mercedes PU powers Mercedes, Aston Martin, McLaren).

**Aero**: shorthand for aerodynamic performance, usually in the context of corner speed (vs. straight-line power).

---

## Timing and analysis

**Lap time**: elapsed time for one full lap of the circuit.

**Sector time**: elapsed time for one of three sectors of the circuit; used to diagnose where a driver gains or loses time.

**Speed trap**: a fixed measurement point on a straight where the car's top speed is recorded.

**Trimmed mean**: the arithmetic mean after removing the top and bottom N% of values; more robust to outliers than a plain mean.

**MAD (Median Absolute Deviation)**: `median(|x-median(x)|)`; a robust measure of spread much less sensitive to outliers than standard deviation.

**Modified Z-score**: `0.6745 × (x-median) / MAD`; flags outliers in a robust way.

**Survival analysis**: statistical methods for analysing time-to-event data where some observations are censored (the event hasn't happened yet). Used here to estimate tyre cliff onset without being biased by voluntary early pits.

**Cox proportional hazards**: a semi-parametric survival model that estimates the effect of covariates on the hazard (instantaneous failure rate). Used in the compound cliff fitter to control for compound class, season, and circuit.

**ASOF join**: a join that returns the most recent matching row from one table before (or at) a given timestamp in another  used to match weather readings to lap timestamps.

---

**Continue to [Part 11  Next Steps](./11_where_next.md).**
