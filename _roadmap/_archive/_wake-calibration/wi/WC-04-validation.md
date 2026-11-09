# WC-04 - Phase 3: validation on a held-out season

**Status: not started. Registered in the WC-03 pre-registration** ([`WC-03-preregistration-DRAFT.md`](WC-03-preregistration-DRAFT.md), SIGNED 2026-10-28). That document fixes the held-out season (2025), the win rule and every threshold (§0, §8-§12, §15). Depends on WC-03. Where this note and the registered text differ, the registered text governs. Design: [`WC-design-note.md`](WC-design-note.md).

_Note correction 2026-10-28: the status line read "not started, not registered". The pre-registration covers WC-04 (prereg §0 and the header: "This document covers the fit (WC-03) and the held-out verdict (WC-04)")._

**Goal.** Show the curve predicts traffic loss on a season it was not fitted on, and passes the physics checks.

**Inputs.** The WC-03 curve, fitted without the held-out season. The pit-stop events, rebuilt from the pass table under prereg §11 (the WC-02 list is not used as it stands, §2c).

**Scorecard (all reported, none rescues another).** The original list follows, each item with its correction. The registered scorecard is prereg §15, Tables 1 and 2.
1. ~~Car ahead pits: the follower's deltas 2 laps before and after match the curve at the pre-pit gap.~~ _Note correction: superseded (prereg §16). The "match" test is replaced by W1-W3 (§9). The pit-stop figure is reported only, never pass or fail (§11, Table 2)._
2. ~~Physics sign: fast-corner loss at least slow-corner loss inside "dirty air"; the straight tow is a gain.~~ _Note correction: dropped (prereg §16), because straights are not measured. The fast-versus-slow part survives only as P2 (§10): the dirty-air fast minus slow interval must not lie wholly below zero._
3. Clean reference band: the curve is flat above about 2.5-3 s. _Note correction: this is now P1 (prereg §10). The 2-3 s band must be within 25 % of the 0.5-1.0 s band, the near band must be above zero, and the interval of near − far must sit above zero (DD-WC13)._
4. Outcome agreement: minimum speed and segment time rank the same. _Note correction: an observation only, with no pass mark (DD-WC12; prereg §12b "Minimum-speed agreement per corner class (observation only, as ruled in WC-02)")._
5. Gap check per race (from WC-02).
6. Held-out season: summed lap loss predicts held-out lap residuals better than the current 0.331 × share rule. _Note correction: W1 (prereg §9) requires beating both the shipped flat penalty and flat-now by 0.5 % at the lower end of the 95 % interval, plus W2 on train laps._
7. Era split, and a note that 2026 is not covered. _(Older cars: their own curve, never decides the verdict, §3, §9. 2026: §13.)_

**Done when.** The scorecard is in `_evidence/WC-04-<date>/` and the owner has read it.

**Risks.**
- Local baseline drift biases the reference: check estimates with ±2 and ±6-lap windows.
- Selection: losses for drivers with a measured reference may be smaller than for those without.
