# WC-03 - Phase 2: estimator

**Status: pre-registration signed; estimator built on synthetic data only, uncommitted; nothing fitted on real data.** Depends on WC-02. The pre-registration is [`WC-03-preregistration-DRAFT.md`](WC-03-preregistration-DRAFT.md) (SIGNED 2026-10-28, SHA-256 `518c3348…`, commit `839e0f4`; see WC-03 in the build log). Amendment A1 ([`WC-03-amendment-A1-circuit-bootstrap.md`](WC-03-amendment-A1-circuit-bootstrap.md)) is a draft: not yet committed or hashed. Where this note and the registered text differ, the registered text governs. Design: [`WC-design-note.md`](WC-design-note.md).

_Note correction 2026-10-28: the status line read "not started, not registered … No pre-registration exists yet". That has been stale since the signature (prereg §0, §17b). Only the status changed; the registered meaning is unchanged._

**Goal.** Turn per-pass losses into a loss-versus-gap curve and a per-pass class.

**Inputs.** The WC-01 pass table and the WC-02 race flags.

**Method.**
- Per pass: loss = observed - own reference.
- **Classes** for each following pass (approach gap 0 to under 3.0 s; a negative gap is racecraft):
  - **held up**: the car ahead's time through the corner is above the follower's reference + 2 × reference spread;
  - **dirty air**: the car ahead's time is at or below the follower's reference + 2 × reference spread;
  - **racecraft**: a negative gap, or a change of car ahead at any braking corner within 3 corners either side (same or adjoining lap). No lateral rule;
  - **no leader time**: the car ahead's time is unknown (its own class);
  - **under attack**: a car behind within 1 s (a separate flag, not a class).
- **Curve:** non-increasing loss against approach gap in 8 gap bins, **per corner class and era**, with circuit and corner random effects (REML), then pool-adjacent-violators. Intervals: cluster bootstrap, 1,000 draws, seed 20261027.
  - Registered (§6, §8c): race-level resample.
  - Amendment A1 (owner decision 2026-10-28, draft, not committed): circuits first, then races within each drawn circuit. A1 governs only once it is committed and hashed.
- Braking corners only. Flat-out corners are out of the curve and the lap totals. No tow/wake split, and straights are not priced.

_Note corrections 2026-10-28 (registered text unchanged):_
- _Following was "approach gap under 2.5 s". It is now 0 ≤ gap < 3.0 s (prereg §5, choice C4)._
- _Racecraft said "or a sharp lateral change". The registered rule has no lateral rule, because the table has no lateral measure (prereg §5, choice C5)._
- _Held up / dirty air were "more than 2× its MAD" / "at or faster". They are now reference + 2 × spread on either side, with `no_leader_time` as its own class (prereg §5, C6/N3)._
- _The bootstrap was "race-level". It is race-level as registered (§6, §8c), changed to circuit-then-race by draft amendment A1._
- _"Straights and DRS zones are a separate 'tow + DRS' number" is replaced by prereg §4b (C1) and §16. Neither tow nor straights are measured here._

**Done when.** The pre-registration is committed and hashed first; the estimator passes synthetic tests; it is run once on a scratch copy against the registered text; the result is read by the owner before anything else.

**Risks.**
- Held up versus dirty air misclassified; tyre saving while following. Shows as slow-corner dirty-air loss as large as fast-corner loss, or a non-zero under-attack effect.
- Era change (2022 ground effect, 2025 cars, 2026 no DRS): fit per era; refit for 2026.
