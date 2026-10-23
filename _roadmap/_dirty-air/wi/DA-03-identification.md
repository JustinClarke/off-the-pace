# DA-03 - Identification

**Model (design note, section 3).** Micro-sector time minus the field median (same race, lap, micro-sector), regressed on entry-gap bands with driver-lap fixed effects, the car ahead's own residual time, a tyre-age term, and a traffic control. Standard errors clustered by race. Only the entry gap is used; the exit gap is an outcome.

**Pre-registration.** Commit the hash of the pre-registration before the fit. It names the placebos and the gate below.

**Placebos.**
- P1: the car behind within 1 s should give about 0. Rules out a general close-racing effect; does not rule out a confound specific to the car ahead.
- P2: effect is about 0 above 3 s and shrinks with the gap. Rules out a level shift not tied to the gap.
- P3: mechanism. Loss in high-speed corners, gain on straights from tow.
- Lead window: not a clean placebo, because losing time opens the gap mechanically. It must be 0 or below only.

**Gate to continue.** Beta at under 1 s has a CI excluding 0. P1 below beta/3 with a CI including 0. P2 and P3 pass.

**Stop if.** P1 is about beta, or the sign flips between eras.

**Owner decision at this gate.** Wording: "causal" or "adjusted traffic cost" (DD4).

**Not ruled out by this design.** Pair-local shocks race control did not flag; deliberate tyre saving while following; selection into who follows whom.
