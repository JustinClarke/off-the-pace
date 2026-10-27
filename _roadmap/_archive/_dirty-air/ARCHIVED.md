# ARCHIVED 2026-10-27 - the dirty-air micro-sector method

**This plan is closed.** The owner decided on 2026-10-27 to archive the old dirty-air method. Nothing here is run, extended or maintained, and no number from it is used in the product, as a fallback or otherwise. Work on traffic cost continues in [`../_wake-calibration/`](../_wake-calibration/README.md).

## Why

- **DA-03 failed its registered checks.** P1, P2 and P3 failed pooled and in both eras (2018-21 and 2022-25). P3 was reversed: slow corners lost more than fast ones, which points to blocking rather than aerodynamics. The failed checks concentrate in exactly the midfield trains a traffic cost is meant to describe.
- **A failed primary result cannot be rescued.** That is the registered rule. Showing the old numbers for some stints would be a rescue by the back door.
- **DA-03F asked the right question with the wrong tool.** The new method answers "is the slow-corner loss blocking?" directly, by splitting held up from dirty air. DA-03F was withdrawn while it was still a draft, so withdrawing it costs nothing under the rules.

## Where the DA-03 record lives (kept in full, frozen)

| What | Where |
| :-- | :-- |
| Registered pre-registration | [`wi/DA-03-preregistration.md`](wi/DA-03-preregistration.md), committed alone in `08b6410` |
| Lock (the registered file's SHA-256) | `prereg_sha256` on item DA-02P in [`status/build-log.json`](status/build-log.json) |
| Fit output | [`_evidence/DA-03-2026-10-27/`](_evidence/DA-03-2026-10-27/) (`fit.json`, `fit.log`, copied unchanged from the session scratchpad; see `PROVENANCE.txt`) |
| Verdict and failed checks | history entry dated `2026-10-27T10:28:00+04:00` in the log; item DA-03 (`stage` CLOSED, `outcome` FAIL (registered)) |
| Estimator | `transform/tasks/coefficients/fit_dirty_air_microsector.py`, frozen as it stands: not rerun, re-specified or extended |

## DA-03F

Withdrawn before registration: never registered, hashed, run or committed. Kept for the record at [`wi/archive/DA-03-followup-slow-corner-draft.md`](wi/archive/DA-03-followup-slow-corner-draft.md), unchanged. It is in the log as DA-03F, `outcome` WITHDRAWN, so nobody later takes it for a hypothesis still waiting to run.

## State of the log

Every item is terminal. DA-01 stays LANDED. DA-03 is CLOSED as a registered FAIL; DA-03F CLOSED as WITHDRAWN; DA-02, DA-02P, DA-04 and DA-05 CLOSED as ARCHIVED (none marked LANDED). DD2 (path A or B) is MOOT. The pointer is null. `python3 _roadmap/_dirty-air/status/board.py --check` still runs and passes.
