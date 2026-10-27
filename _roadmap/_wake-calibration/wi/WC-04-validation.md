# WC-04 - Phase 3: validation on a held-out season

**Status: not started, not registered.** Depends on WC-03. The held-out season and every scorecard threshold are named in the pre-registration (WC-03) before any run. Design: [`WC-design-note.md`](WC-design-note.md).

**Goal.** Show the curve predicts traffic loss on a season it was not fitted on, and passes the physics checks.

**Inputs.** The WC-03 curve, fitted without the held-out season; the WC-02 car-ahead-pits event set.

**Scorecard (all reported, none rescues another).**
1. Car ahead pits: the follower's deltas 2 laps before and after match the curve at the pre-pit gap.
2. Physics sign: fast-corner loss at least slow-corner loss inside "dirty air"; the straight tow is a gain.
3. Clean reference band: the curve is flat above about 2.5-3 s.
4. Outcome agreement: minimum speed and segment time rank the same.
5. Gap check per race (from WC-02).
6. Held-out season: summed lap loss predicts held-out lap residuals better than the current 0.331 × share rule.
7. Era split, and a note that 2026 is not covered.

**Done when.** The scorecard is in `_evidence/WC-04-<date>/` and the owner has read it.

**Risks.**
- Local baseline drift biases the reference: check estimates with ±2 and ±6-lap windows.
- Selection: losses for drivers with a measured reference may be smaller than for those without.
