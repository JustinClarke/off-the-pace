# WC-08 - Loss scale on the replay dashboard

**Status: not started, not registered.** Depends on WC-03 and WC-04 passing, on WC-05 (modelled references and labels; owner ruling 2026-10-27) and on WC-07. Design: [`WC-design-note.md`](WC-design-note.md).

**Goal.** Add the per-pass and per-lap traffic loss to the WC-07 replay, from the WC-03 curve that passed the WC-04 scorecard.

**Rules.**
- Nothing is shown before WC-04's scorecard is in `_evidence/WC-04-<date>/` and the owner has read it.
- Every value carries its label: measured, modelled or unavailable. Unavailable is "—" with the reason, never 0.
- Every modelled value carries the DD-WC2 disclaimer word for word: "Normalised from other compounds, based on stints from other drivers or the general performance of the tyres after removing other factors."
- Totals print the modelled share beside them.
- Flat-out corners (`segment_basis = fixed_before_apex`) show a loss only if the WC-03 pre-registration split tow from wake loss for them; otherwise they show "—" with that reason.
- No archived dirty-air (DA-03) number, as a fallback or otherwise.

**Done when.** The replay shows the labelled scale on the held-out season's races; a test shows every value has a label and every modelled value the disclaimer; the owner reviews.

**Risks.** Modelled values need WC-05, which is now a listed dependency (owner, 2026-10-27), so the scale is not shown until WC-05 has landed.
