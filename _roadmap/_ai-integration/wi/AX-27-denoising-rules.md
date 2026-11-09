# AX-27 — Denoising rules for any future lap-time measure (constraint, not a build)

**Rule set** (from the owner's notes, to apply to any lap-time measure of traffic or dirty air):
- compare each driver with their own clean laps, not the field;
- remove fuel and tyre trends, with stint and driver fixed effects;
- exclude safety car, pit, lapped and overlapping cases;
- use the car-ahead field only where validated, and not on lapped or overlapping laps;
- pool across races and seasons, and report intervals, not a single number.

**Status:** a constraint. No feature depends on it yet. The separability audit (experiment 14) tests whether these rules can separate the factors. Its verdict gates any publication of a traffic-cost interval.
**Done when:** the rules are in the owner's docs and any future lap-time measure cites them. No publication before the audit verdict is in.
