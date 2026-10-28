# Wake calibration: the single best move now (2026-10-27)

Advice only. Nothing was built, fitted, gated or committed for this note. The warehouse, bronze, the build log and the build order were not touched. One read-only count was made from the existing car-ahead-pits event list in this folder (how many distinct pit stops it holds, and how many events pair cars on different lap numbers). No loss, curve or coefficient was looked at.

Read for this note: the earlier advice note (BEST-PLAY), the timing salvage and its pre-declared corrections, the 1,124 reconciliation, the WC-02 provenance and summaries, all work items and the design note, and the build log.

---

## The move, in one line

**Write the pre-registration now, as a draft for your sign-off, with the finished measurement checks folded into it. Run nothing until you have signed it and it has been committed on its own.**

The earlier note said the same thing but made it wait for the timing salvage. The salvage has now reported, so that wait is over. Where I disagree with the earlier note is on *what the pre-registration must say*, mainly about how the final verdict is scored (section 4).

---

## (a) The next concrete step and what it produces

One document, with two parts.

**Part 1: closing the measurement checks (one page, numbers already exist).**
- **Timing.** When each timing line is found from the car's position on the track (which is how the pass table actually measures gaps), our gaps agree with the official timing within 0.1 s in 168 of 169 races. The typical error is about 0.045 s, a bit higher since 2022 (about 0.05 s). The 34-race flag came from the way the first check found the lines, not from the data. The one race that still fails, 2024 Las Vegas, fails because the timing feed contradicts itself there. All 34 races stay in, as you ruled. The stated risk becomes "one race with an inconsistent feed, and about 0.05 s of gap noise everywhere".
- **Car-ahead-pits events.** The 1,124 is retired. We restate the event set in our own definition (see decision 4 below).
- **Minimum speed.** Recorded as an observation: good agreement in fast and medium corners, weaker in slow corners and getting weaker over the years. No pass mark.

**Part 2: the pre-registration itself.** It fixes, before anyone has looked at a single loss value:
- the question, and the bar for replacing the flat penalty (decision 1);
- which season is held back, and what it is scored against (decision 2 and section 4);
- the role of 2026 and the checks it gets (decision 3);
- the car-ahead-pits event definition, its comparison group and how it is read (decision 4);
- what the headline covers (decision 5);
- the smaller fixes: how a lap total is added up without counting overlapping stretches of track twice; the "no loss at large gaps" check moved to the 2-3 s band, because above 3 s it is true by construction; fast flat-out corners kept out of the first curve; a statement that gaps closer than about 0.2-0.3 s are smeared by the timing noise, so the very close end of the curve will read flatter than it really is.

What you get: a document you can approve or change line by line. Once approved, it is committed alone and its fingerprint recorded. From then on, thresholds cannot follow the data.

---

## (b) What you must decide first, with my recommended answer

**1. The bar for replacing the flat penalty.**
Recommend: **replace it only if all three hold on the held-out season:**
- the measured cost explains lap times better than the flat penalty, and the improvement is clearly above zero once race-to-race chance is allowed for (the interval is fixed in advance);
- it is **not worse** on the laps of drivers who had no clean reference (the long trains), scored separately;
- the basic physics checks pass: close to no loss in the 2-3 s band, and more loss in fast corners than slow ones.

If only the first holds, **keep the flat penalty and show the new number beside it** for the drivers where it is measured. If the first fails, keep the flat penalty and stop; the product items do not start. Say this in advance so that a "nearly" result cannot be argued up.

**2. The held-out season.**
Recommend: **yes to 2025, fitted on 2022-2024**, as proposed. It tests forwards in time, which is how the number will be used. 2025 also has the lowest share of clean references (43%), so it is a hard test, which is what we want. Hold out 2021 (fitted on 2018-2020) for the older cars too, but **let the verdict rest on 2025**; 2021 is reported, not decisive. State openly that the flat penalty was fitted on data that included 2025, so the contest slightly favours the flat penalty.

**3. Is 2026 only a check?**
Recommend: **yes. 2026 is a check that the measuring still works, plus a first 2026-only curve marked as exploratory. It gives no verdict.** With no DRS and new cars, a curve from earlier years is expected to be wrong in 2026 for physical reasons, so a failure would tell us nothing and a pass would tell us little. The 2026 checks are: gaps agree with the timing (same method as the salvage); share of clean references; little loss in the 2-3 s band; more loss in fast corners than slow; the car-ahead-pits contrast within 2026. All of these are written into the pre-registration before 2026 is ingested.

**4. The event definition, with a comparison group.**
Recommend: **yes to our own definition, with these rules, all fixed in advance:**
- "Close" is measured on the **two laps before** the car ahead's pit-entry lap, never on the entry lap itself. On that lap the car ahead is slowing for the pit lane, so being "close" partly means the car ahead backed off.
- **Count each pit stop once.** The current list of 1,970 events holds only 1,669 distinct stops, and the 530 with readings on both sides hold 512 distinct stops. Counting several follower laps per stop overstates how much evidence we have.
- **Drop events where the two cars are on different lap numbers.** That is 246 of the 1,970 events (about 12%). These are most likely lapped cars or lap-labelling problems (the salvage found some races where lap start times are a second or two off). Neither is the situation we are trying to measure.
- **The follower's clean reference must come from outside the event window.** Otherwise the laps after the stop serve as their own yardstick and show almost zero loss by construction.
- **Comparison group:** followers at the same gap at the same stage of the race whose car ahead does not pit. Their before-and-after change is subtracted.
- **Read it as a ceiling, not a match.** After the car ahead pits, the follower often pushes to gain time on the stop. That makes the jump bigger than the real traffic cost, and the comparison group cannot remove it. So the check is one-sided: the curve's loss at the pre-stop gap should **not exceed** the adjusted jump. The earlier note asked for the two to "match"; for this reason I disagree.
- **Expect far fewer events**, likely a few hundred stops or fewer. Fix a minimum in advance (I suggest 200 distinct stops). Below that, the check is reported as descriptive only.

**5. Does the headline cover only the half of the field with a clean reference?**
Recommend: **no, and here I disagree with the earlier note.** The curve can only be *fitted* on passes with a clean reference. But once fitted, it needs only the gap and the corner type, so it can be **applied to every lap with a valid gap**, trains included. The held-out contest should be scored on all of 2025's laps that have a valid gap, and reported twice: laps with a clean reference, and laps without. That turns the biggest weakness, the missing half, into something we measure rather than something we only warn about. Reported loss sizes per driver or team still carry the coverage share, and the "modelled" tier (WC-05) still waits for the verdict.

**6. A working 2026 data login.**
Recommend: **check it now.** The earlier research found that the archived 2026 data asks for an F1 TV login, and without the car traces there are no corner passes at all. A one-race fetch tells us only whether the data can be reached, not what it shows, so it can happen before the sign-off. If there is no login, 2026 shrinks to timing-only counts, and the pre-registration should say so rather than promise 2026 checks we cannot run.

---

## (c) What should wait, and why

- **Any fit, curve or loss plot,** until the pre-registration is signed and committed. Nobody has yet looked at loss against gap; keep it that way. This includes the replay view, which correctly shows no loss values.
- **Ingesting 2026 beyond the one-race access test,** until the pre-registration is committed. The 2026 checks are pre-registered, so the data should not be seen before them.
- **The modelled tier, the app pages and the loss scale on the replay** (WC-05, WC-06, WC-08), until you have read the held-out verdict. If the measured cost does not beat the flat penalty, that is roughly 8-10 weeks of product work you will not need.
- **More replay-view work** (WC-07). It is useful for checking a few races by eye, but it produces no part of the answer. Now that the timing check has effectively passed, it may become owner-facing under its own rule, but it should not take time away from the pre-registration.
- **The live data licence and any re-ingest of bronze.** Already ruled; nothing here changes that.
- **Chasing the last timing questions** (which feed field is wrong in general, why noise is higher since 2022). They are worth a line in the stated risks, not a work item. They move the gap by hundredths of a second.

---

## (d) The main risk of a misleading result, and how this step guards against it

**The risk.** The curve is learned only from drivers who regularly got clean air, because only they have a clean reference. Those are not the drivers stuck in long midfield trains, where the cost is largest, and the clean-reference share is falling year by year (53% in 2018, 43% in 2025). If we also score the curve only on those same drivers, every check shares the same blind spot. The curve could look tidy, pass the physics checks and beat the flat penalty, and then be rolled out to every driver while understating what the trains actually cost. The car-ahead-pits check does not catch this: it has the same selection, and the push after a stop biases it the other way. The two errors can cancel and look like agreement.

A second, smaller way to get a flattering result: adding up corner losses into a lap total counts overlapping stretches of track twice (47% of braking-corner passes start inside the previous corner's window). That would inflate the curve's lap total in exactly the contest against the flat penalty.

**How the next step guards against it.**
1. **The verdict is scored on the whole field.** The held-out contest covers every 2025 lap with a valid gap, and the result for drivers without a clean reference is reported separately and must not be worse (decisions 1 and 5).
2. **A neutral yardstick.** Both numbers are scored against the same lap-time baseline the flat penalty was itself fitted with (each stint's own level plus tyre age), with neither number refitted on 2025. Do not score against the existing lap-time model's errors, because that model is trained on a label that already contains the flat penalty.
3. **The pit check is built so it cannot flatter the curve.** It uses one event per stop, a reference from outside the window, a comparison group, and a one-sided reading (decision 4).
4. **A rule for adding up laps that counts nothing twice,** fixed before the fit.
5. **All of this is fixed in writing before anyone sees a loss value.** That is the only reliable defence against choosing, after the fact, whichever version looks best.

---

## Where this note departs from the earlier one

- The wait for the salvage is over (168 of 169 races agree), so the pre-registration can be written now.
- **Headline coverage:** the earlier note would report the measured half with a coverage share. I recommend scoring the verdict on the whole field, split into the two halves, because the curve can be applied where it cannot be fitted.
- **Pit-event check:** read it as a one-sided ceiling, not a match; count stops, not follower laps; drop pairs on different lap numbers. The earlier note did not raise the double-counting of stops or the lap-number mismatches.
- **The yardstick for the contest** has to be named, and it must not be the lap-time model's errors.
- I agree with the earlier note on: 2025 as the held-out season; 2026 as a check of the method only; measuring "close" before the pit-entry lap; the 2-3 s band; the lap-total overlap; keeping product work behind the verdict.
