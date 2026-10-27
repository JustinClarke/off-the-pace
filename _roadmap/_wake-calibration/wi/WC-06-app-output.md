# WC-06 - Phase 5: app output

**Status: not started, not registered.** Depends on WC-05. Waits on DD-WC2 (disclaimer wording). Design: [`WC-design-note.md`](WC-design-note.md).

**Goal.** Show the traffic cost in the app with its label on every number.

**Inputs.** WC-05 labelled passes and stints; the existing `app/src/features/dirty-air-cost/` and `app/src/features/dirty-air-lap-map/` pages; the marts that feed them.

**What the app shows.**
- Per driver: a race and stint total, split into dirty air, held up, racecraft and tow/DRS; a per-lap bar; a corner heat strip.
- **measured**: number with interval. **modelled**: wider interval, hatched or greyed, marked "modelled", with the disclaimer. **unavailable**: "—" with the reason, never 0.
- **Totals show the modelled share**, for example "3.4 s (28% modelled)". Unavailable laps are left out of totals and counted.
- No number from the archived dirty-air method (DA-03) appears anywhere.

**Disclaimer on every modelled value** (pending DD-WC2; use exactly):

> Normalised from other compounds, based on stints from other drivers or the general performance of the tyres after removing other factors.

**Stint coverage the UI must handle.** 16.7% of stints (1,177) have no clean lap; about 86% of those are modelled from another stint of the same driver or the teammate; about 2% of all stints (162) are unavailable.

**Done when.** App tests are green; the owner reviews the label and disclaimer on screen; nothing ships without the owner's yes. Whether this replaces or sits beside the existing 0.331 × share tax is an owner call at this gate, and a label change goes through the ML retrain plan.

**Risks.**
- Readers take a modelled number for a measurement: the label, hatch and disclaimer must be on every modelled value, including totals.
- A driver whose stint switches label shows a jump from the method, not the race; show the label per stint.
