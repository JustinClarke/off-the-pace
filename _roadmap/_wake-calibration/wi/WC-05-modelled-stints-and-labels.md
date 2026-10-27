# WC-05 - Phase 4: modelled-stint calibration and the labels

**Status: not started, not registered.** Depends on WC-04. Waits on DD-WC2 (owner confirms the disclaimer wording). The modelled-reference rules and the checks below go into a pre-registration before anything is fitted. Design: [`WC-design-note.md`](WC-design-note.md).

**Goal.** Give a modelled reference to stints with no clean lap, check it, and assign every stint and pass one label: measured, modelled or unavailable.

**The stints this is for (corrected count).** **16.7% of stints (1,177) have no clean lap.** About **86%** of those can be filled from another stint of the same driver or the teammate. About **2% of all stints (162)** are **unavailable**. Count-only, lap-end gap, whole stint; the per-corner ±4-lap measure will give a somewhat lower measured share.

**Inputs.** WC-01 pass table, WC-03 curve, WC-02 car-ahead-pits events.

**Sources for a modelled reference (same car, same race; source stored per stint).**
- `own_other_stint`: the driver's own clean passes in another stint, with a compound offset and a tyre-age trend.
- `teammate`: the teammate's clean passes on the same compound, with a driver offset from laps where both were clean.

Neither exists: the stint is **unavailable**. It is not filled from the pooled curve or from the archived dirty-air method. The pooled curve is used only for season and team aggregates, with the coverage share printed.

**Checks (reported, not shown to users).**
- The **157** car-ahead-pits events inside no-clean stints: does the modelled loss before the stop match the measured jump after it?
- The minimum-speed gradient: is the modelled loss at least as large as this lower bound?
- If modelled values consistently fall short of either, the modelled tier is withdrawn and those stints become unavailable.

**Labels.** measured (number with interval); modelled (wider interval, marked "modelled", with the disclaimer); unavailable ("—" with the reason, never 0).

**Disclaimer for modelled stints** (pending DD-WC2; use exactly):

> Normalised from other compounds, based on stints from other drivers or the general performance of the tyres after removing other factors.

**Done when.** Each stint and pass carries a label and, for modelled, its source; both checks are in `_evidence/WC-05-<date>/`; the owner has confirmed the disclaimer (DD-WC2).

**Risks.**
- Selection: a high modelled share for midfield teams; measured losses smaller than modelled at the same gap.
- The compound offset and local tyre and fuel trend are estimated within one race, so modelled intervals must be wider.
