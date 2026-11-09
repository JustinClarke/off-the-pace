# Wake calibration: what we are trying to learn, and the best way to get there (2026-10-27)

Advice only. Nothing was built, fitted or run for this note; no gate or coefficient was computed; the warehouse, bronze, the build log and the build order were not touched. It reads the README, the design note, WC-01 to WC-09, the build order, the WC-01 and WC-02 evidence (including the 1,124 reconciliation), the research recommendation and decision memo the 1,124 came from, and the timing-salvage work that is still running in another session (its pre-declared corrections and the partial log, not a finished result).

Owner rulings taken as given: keep all 34 timing-disagreement races and state the risk; salvage timing where possible; 1,124 was a rough script number and we use our own event definition; minimum-speed agreement is an observation with no pass mark; 2026 will be ingested to see how the method performs; the live-data licence can wait; no re-ingest of bronze.

---

## 1. What we are actually trying to learn

Today the product charges every car a flat traffic tax of about a third of a second per lap, scaled by how much of the lap it spends close behind another car. That one number feeds the app pages and the label the lap-time model is trained on. The owner wants to know whether we can replace it with something true: **how much time a driver really loses in traffic, corner by corner, measured against that same driver's own clean pace a few laps either side, and split into "held up by a slower car" and "losing grip in the wake"**. The question underneath is simple: is there a real, measurable traffic cost that varies with the gap and the type of corner, and does it explain lap times better than the flat tax does?

**A useful answer looks like this:**

- A loss-versus-gap curve for slow, medium and fast corners, per car era, with honest error bars, that is close to zero at a three-second gap and grows as the gap closes, larger in fast corners than slow ones.
- A clear statement of how much of the field it speaks for. Right now only about half of the usable corner passes have a clean own reference, and the drivers stuck in long trains are mostly in the other half.
- A head-to-head on a season the curve never saw: does the measured cost explain that season's lap times better than the flat tax? A yes or no, with the margin.
- A short verdict the owner can act on: replace the flat tax, keep it, or keep it and show the new number beside it for the drivers where it is measured.

The 2026 season is a separate question: does the measuring machinery still work on cars with no DRS and new aero, and roughly what does the cost look like there? It is not a test of whether the 2018-2025 curve carries over (see section 3).

A useful answer is **not** a per-driver app number with labels and disclaimers. That is product work that should wait until the answer above says the number is worth showing.

---

## 2. Which remaining items are needed, and in what order

| Item | Needed for the answer? | Why |
|---|---|---|
| WC-02 measurement checks (finish it) | **Yes** | The timing salvage decides how much to trust the gap. The car-ahead-pits event set needs its target restated in our own definition. |
| WC-03 estimator, with its pre-registration | **Yes** | This is where the answer is produced. The pre-registration is the most important document left. |
| WC-04 validation on a held-out season | **Yes** | This is the head-to-head against the flat tax. Without it there is a curve but no verdict. |
| WC-09 ingest 2026 | **Yes, for the 2026 question only** | Cheap, but the 2026 data must not be looked at before the pre-registration is committed. |
| A "run the method on 2026" step | **Yes, and it does not exist yet** | WC-09 stops at counting rows with no fit, and WC-04 only notes that 2026 is not covered. The owner's stated aim of seeing how the method performs on 2026 has no item. It belongs in the pre-registration and as a new item after WC-04. |
| WC-07 replay dashboard | No (useful, not needed) | Good for eyeballing a few races and the pit events, but it produces no part of the answer. Keep it to a two-or-three-race debugging view at most, and do not let it delay the pre-registration. |
| WC-05 modelled stints and labels | No, not yet | It fills gaps for the product. It does not answer whether the cost is real. Its check also quotes 157 events from the old script definition, which no longer matches our event set. |
| WC-06 app output | No | Product. Decide after WC-04. |
| WC-08 loss scale on the replay | No | Product. Decide after WC-04 and WC-05. |

**Order:**

1. Close WC-02: let the salvage finish, write its result next to check 1, and restate check 2's target in our own definition (section 3 below says which one).
2. Write the pre-registration (WC-03) and get the owner's yes. It must cover the held-out season, the event definition, the 2026 plan and the fixes in section 3. Commit it alone and record its hash.
3. Ingest 2026 (WC-09), counts only, after step 2 is committed. A one-race probe that confirms 2026 telemetry can be fetched at all can run earlier, because it says nothing about the outcome.
4. Fit (WC-03), then validate (WC-04) on 2018-2025.
5. Run the pre-registered 2026 checks (new item).
6. Owner reads the scorecard and decides whether WC-05, WC-06, WC-07 and WC-08 go ahead at all.

This moves the product items behind a decision instead of treating them as the end of a fixed line. If the held-out test says the measured cost is no better than the flat tax, about 8-10 weeks of product work is saved.

---

## 3. Is the plan sound? Where it could mislead

The core idea is good: compare each driver with their own clean passes of the same corner, measure the gap before the corner, and keep the two outcomes separate. WC-01 was done carefully and WC-02 has already produced useful findings. **I disagree with four parts of the plan**, and one of them is the biggest risk.

### 3a. The biggest risk: the answer is measured on the drivers least in traffic, and the main check leans the other way

- **Selection.** Only 49% of usable corner passes have a clean own reference, and the share falls over time, from 53% in 2018 to 43% in 2025. The passes with no reference are the long midfield trains, which is where the cost is largest. So the curve is fitted mostly on drivers who regularly got clean air. It will tend to **understate** the cost for the drivers who matter most.
- **The car-ahead-pits check has the same selection.** Of 1,970 events where the follower stays out, only 530 have a measured reference on both sides. Those are again the followers who were not stuck.
- **The check has a confound of its own that pushes the other way.** When the car ahead pits, the follower is often told to push for the overcut. Their laps after the stop are faster because of effort, not only because the air is clean. That makes the before/after jump **bigger** than the true traffic cost.
- **It is partly circular.** For a follower stuck before the stop, the clean passes that make up their reference mostly come from the laps right after the stop, so the "after" laps are close to zero by construction.

Put together: the curve could be biased low and the main check biased high. They might agree by accident, or disagree for reasons unrelated to the curve, and either outcome would look like a clean result. **This is where a wrong answer is most likely to come from.**

**What to do (in the pre-registration, before any fit):**
- Build the reference for the pit-event check **only from laps outside the event window** (or from the earlier part of the stint), so the "after" laps cannot be their own reference.
- Add a **placebo set**: followers at the same gap at the same stage of the race whose car ahead does *not* pit. Subtract their before/after change. What remains is the effect of the car leaving, with tyre wear, fuel and general pushing netted out. The overcut push will not fully net out, so report it as a known upward bias.
- Report every headline twice, for the measured half and as a coverage share per team, and pre-register what result would count as the selection problem showing (for example, measured losses at a given gap clearly smaller than those in the pit-event set).

### 3b. Our own event definition: yes, but one change

I agree with dropping 1,124 as a target. It was a lap-end count from a short script and does not even guarantee the follower stays out. Our definition (gap measured before the corner, on-track order, follower stays out for two laps either side) is the right basis: 1,970 events, 530 with measured deltas on both sides. One change: today a lap qualifies if the follower is within 1.5 s at **any** corner of the car ahead's in-lap. On that lap the car ahead is slowing for the pit lane, so the "close" reading partly comes from the pitting car backing off. Define closeness on the **two laps before** the in-lap instead, and never use the in-lap itself in the contrast. Expect the count to fall. That is fine, because the count was never the point.

### 3c. 2026 as an out-of-sample test: sound as a method test, not sound as a test of the curve

2026 removes DRS and brings new cars and active aero. The design note already says the method has to be refit for 2026. A curve fitted on 2018-2025 is therefore *expected* to be wrong on 2026 for physical reasons. If it fails there, that tells us nothing about the method. If it passes, it is weak evidence. **Do not use 2026 as the held-out season for the curve.** Use it for what it is good at:

- **Method transfer.** Does the measuring machinery still work? That means gap agreement with timing, reference coverage, the physics checks (loss near zero at three seconds, more loss in fast corners), and the pit-event contrast **within 2026**. None of these needs a curve carried over from earlier years.
- **A first 2026 curve**, refit on 2026 alone, reported with the warning that it comes from roughly one season.
- The DRS-based split between tow and wake loss cannot work without DRS, so 2026 flat-out corners stay out.

For the curve itself, hold out a season **inside the current car era**. I recommend 2025: fit on 2022-2024 and test forwards in time, which is how the number would actually be used. Note that 2025 has the lowest reference coverage, which makes it a harder test, and that is no bad thing. Also note that the flat tax was fitted on 2018-2025 *including* 2025, so the comparison slightly favours the flat tax. That is acceptable, but say so.

Before relying on 2026 at all, confirm that 2026 **telemetry** can be fetched. The research found the FastF1 archive asks for an F1 TV login, and timing data without telemetry gives no corner passes at all.

### 3d. Two smaller things in the validation list that would mislead if left as written

- **"Flat above about 2.5-3 s" is partly true by construction.** Clean passes are defined as more than 3 s behind, and those passes *are* the reference, so the loss above 3 s is close to zero automatically. The check only means something in the 2-3 s band. Say so, or move the band.
- **Summing corner losses into a lap total double-counts.** 47% of braking-corner passes start inside the previous corner's window, so adding per-corner losses counts some stretches of track twice. That would inflate the lap total in exactly the head-to-head against the flat tax. The pre-registration must say how a lap total is formed (for example, only the non-overlapping part of each corner, or score the lap total directly) and what lap-time residual it is scored against.

### 3e. On the 34 timing-disagreement races

Keeping them is the right call, and the risk may turn out smaller than it looks. The timing check placed the timing line at a fixed distance into the lap. That is not how the pass table measures the gap: it measures each car's distance from its own corner apex. The salvage's pre-declared, builder-faithful method and its position-based method both bring the three test races (2021 Belgium, 2023 Azerbaijan, 2018 Austria) under the 0.1 s bar. The partial full run shows the same for the 2023 races logged so far, including Las Vegas, Dutch and Azerbaijan. That is **partial and unfinished**: wait for the full run. If it holds, the stated risk becomes "gap agrees with timing within 0.1 s in N of 169 races under the method the pass table actually uses", and the 34 is a statement about the old check, not about the data.

### 3f. Minimum-speed agreement (observation only)

The two outcomes agree reasonably well in fast and medium corners (rank correlation about 0.6) and less well in slow corners (about 0.47 overall, falling from 0.52 in 2018-2019 to 0.40 in 2025). No pass mark, as ruled. It is still worth knowing: in slow corners the time is decided by traction on exit, not minimum speed, and that is also where "held up" and "wake" are hardest to tell apart. Expect the slow-corner part of the answer to be the least reliable.

### 3g. Things in the plan I agree with

- Pre-register before fitting, and do not move thresholds afterwards.
- Keep flat-out corners out of the first wake-loss curve rather than invent a tow/wake split now (watch item W5).
- No number from the archived method, as a fallback or otherwise.

---

## 4. The single next step

**Write the WC-03 pre-registration as a draft for the owner, once the timing salvage reports.** No fit, no run: one document that fixes the question, the decision it feeds, the held-out season, our event definition with the placebo and the out-of-window reference, how a lap total is formed without double-counting, the selection reporting, and the 2026 plan (method transfer plus a refit, not a transfer test of the curve). Everything else in the order waits on it. It is also the step that prevents the plausible-but-wrong answer described in section 3a.

**What the owner needs to decide before it is written:**

1. **What the answer is for.** Is the bar "replace the flat tax if the measured cost beats it on the held-out season by a stated margin", or "show the measured cost beside the flat tax where it exists"? The pre-registration needs the bar in advance.
2. **The held-out season.** Recommended: 2025, fit on 2022-2024, with the older era handled the same way (for example, hold out 2021, fit on 2018-2020).
3. **2026's role.** Agree that 2026 tests whether the method still works and gets its own refit, not whether the old curve carries over.
4. **The event definition.** Agree to our own definition, with closeness measured on the two laps before the car ahead's in-lap, a placebo comparison, and a reference built outside the event window. Accept that the count will drop below 1,970.
5. **Measured-only headline.** Agree the first answer reports the measured half with coverage per team, and that the modelled tier (WC-05) and the product items wait for the verdict.
6. **2026 telemetry access.** Confirm the F1 TV login or another personal-use route is available, or accept that the 2026 part may be timing-only and much weaker.
