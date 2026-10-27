# WC-03 - Phase 2: estimator

**Status: not started, not registered.** Depends on WC-02. **No pre-registration exists yet.** One must be written, approved by the owner, committed alone, and its SHA-256 recorded on this item before anything is fitted. Design: [`WC-design-note.md`](WC-design-note.md).

**Goal.** Turn per-pass losses into a loss-versus-gap curve and a per-pass class.

**Inputs.** The WC-01 pass table and the WC-02 race flags.

**Method.**
- Per pass: loss = observed - own reference.
- **Classes** for each following pass (approach gap under 2.5 s):
  - **held up**: leader slower than the follower's reference by more than 2× its MAD;
  - **dirty air**: leader at or faster than the follower's reference;
  - **racecraft**: a pass or position change within 3 segments, or a sharp lateral change;
  - **under attack**: a car behind within 1 s (a separate flag).
- **Curve:** monotone (non-increasing) loss against approach gap, **per corner class and era**, partially pooled across segments and circuits; race-level cluster bootstrap for intervals.
- Corners only for the dirty-air number; straights and DRS zones are a separate "tow + DRS" number.

**Done when.** The pre-registration is committed and hashed first; the estimator passes synthetic tests; it is run once on a scratch copy against the registered text; the result is read by the owner before anything else.

**Risks.**
- Held up versus dirty air misclassified; tyre saving while following. Shows as slow-corner dirty-air loss as large as fast-corner loss, or a non-zero under-attack effect.
- Era change (2022 ground effect, 2025 cars, 2026 no DRS): fit per era; refit for 2026.
