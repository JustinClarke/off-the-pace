# Next step after WC-01: replay dashboard now, or the method checks first? (2026-10-27)

**Recommendation: run WC-02 first, starting with check 1 (does the derived gap agree with the timing feed). Then build the WC-07 replay at the same time as the WC-03 pre-registration is written, not before WC-02.** A rough replay of two or three races is fine as a WC-02 debugging aid. It is not the owner-facing dashboard.

This memo does not claim the method works. Nothing has been fitted or validated.

## Why not WC-07 first

- **The replay's main number is not checked yet.** WC-07 shows the gap to the car ahead in seconds and metres. WC-02 check 1 is the test of that gap against S1, S2 and the finish line. It takes 1-2 weeks. Until it passes, the dashboard would show a precise-looking number nobody has checked. Measurement-only output avoids the risks of a loss estimate (sign, attribution, selection). It can still be plainly wrong: wrong car ahead, timing offsets, the approximate marshal sectors.
- **The problems found so far came from counts, not from looking.** The 743 "kept → excluded" passes were reconciled from counts. 560 came from a YELLOW and CLEAR logged in the same second (2023 Bahrain), and 136 + 19 from missing or late CLEAR messages. A replay would make that kind of fault visible faster. But WC-02 runs per-race checks that find it reliably, which a person scrolling does not.
- **An owner-facing page that looks finished invites the next step.** Once it exists, adding a loss scale feels small. That is WC-08, and it stays gated on WC-03 and WC-04.

## Why WC-07 soon after, not much later

- It costs little (an estimated 1-2 weeks on the existing pass table) and needs nothing from WC-03 to WC-05.
- It is the clearest way for the owner to check three open issues by eye before the pre-registration locks:
  1. **Neighbouring-corner overlap.** 47% of kept braking-corner passes start inside the previous corner's window.
  2. **Flat-out corners and the tow.** 515,750 kept passes; 301,107 follow within 3 s; 19,955 have DRS open in the segment. Nothing separates tow from wake loss (W5).
  3. **Reference coverage.** Only 48.9% of kept passes have a measured reference, and 31.7% of stints have no measured pass. This is where selection bias would come from.

## What would falsify the approach (and where it is tested)

- The derived gap disagrees with timing (median absolute error over 0.1 s) in many races: WC-02 check 1.
- Segment time and minimum speed rank passes differently: WC-02 check 3.
- The car-ahead-pits contrast does not match, or shows a pre-trend: WC-02 builds the event set, WC-04 reads it.
- Estimates move between ±2 and ±6-lap reference windows (baseline drift): WC-04.
- The physics sign fails: fast-corner loss below slow-corner loss in dirty air, or a flat curve that never flattens above about 3 s. This is only interpretable once flat-out passes are kept out or split (W5).
- Too few passes are measured where traffic matters, so the measured losses cannot speak for the midfield trains.

## Not yet

- No loss scale, delta or curve on any page (WC-08 waits on WC-03 and WC-04).
- No fit or gate before the pre-registration is committed and hashed (W1).
- No pooling of flat-out passes into the dirty-air curve without a pre-registered split. A candidate test, **TS-1 tow/wake split**, has no threshold set yet. It would use three upstream measures, none of them taken from the outcome window:
  - DRS open in the gap window or the segment (telemetry DRS code 10/12/14);
  - the change in gap across the approach window (closing or not);
  - the follower's entry speed at the segment start against its own clean reference entry speed.
  The pre-registration names the cut-offs, or keeps `fixed_before_apex` out of the curve.
- No live ingest (DD-WC3 open). No bronze rewrite for marshal sectors without an owner yes (W6).
