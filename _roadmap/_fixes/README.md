# _fixes — reverified fix plan for the transform forensic audit (F1–F49)

**What this is.** `_improvements/reference/transform_forensic_audit*.md` (3 rounds, run 2026-09-24)
found 49 defects in the transform/ML pipeline and the fan-facing app. This folder is that audit,
**independently reverified against the live tree today**, and turned into an actionable fix plan.

## Reverification method

1. Re-ran the audit's own reproducibility harness, `verify_findings.py`, read-only against the live
   `data/dev.duckdb`. It had a path bug (`_db.py` resolved `REPO` one directory short of the real
   repo root — see `WI-07-guard-repairs.md` item F53) which was patched in a scratch copy, not in the
   tracked artefact. **Result: 51/51 mechanical checks still PRESENT**, magnitudes matching the
   written reports almost exactly (a handful of counts moved by single digits, consistent with the
   dev build advancing slightly, not with the defects going away). Nothing in the three reports is
   stale on the facts.
2. Beyond that, five independent read-only reviews — one per finding cluster, each starting cold with
   no access to the audit's own conclusions beyond the report text — re-read the cited source
   directly, re-derived several of the algebraic/mechanism claims by hand instead of trusting the
   audit's probes, and judged whether severity, "ML impact," and the recommended fix are proportionate,
   overblown, or understated. Every finding got one of: **CONFIRMED-AS-STATED**, **ARGUABLE**
   (mechanism holds, some part of the characterization is debatable), or **UNDERSTATED**. None came
   back OVERBLOWN, INVALID, or STALE-OR-FIXED.
3. The same reviews surfaced five issues not in F1–F49. They're numbered **F50–F54** to keep them
   out of the audit's own numbering range while staying cross-referenceable. Full write-ups in
   [`NEW-FINDINGS.md`](NEW-FINDINGS.md).

## Overall verdict, reconfirmed

**Not overblown.** Every one of the 49 findings survived independent re-derivation from the current
source — none turned out to be a misreading, a stale citation, or a non-issue that the original audit
talked itself into. If anything the balance tips the other way:

- Several fan-page findings (**F15, F27, F29, F37**) and one guard finding (**F34**) are rated lower
  than the evidence supports once you weigh them against this product's stated priority (fan-value
  pages are not a footnote — see `_improvements` project memory, 2026-09-20 win-definition decision).
  F29 in particular is the model's own trust/credibility page and structurally flatters the model.
- **F2**'s "small honest-pipeline cost" framing is true for the trio (p50) and cliff targets but not
  for stint-life, whose arm-C cost (−0.0761 AFT NLL, ~3.8% relative) is an order of magnitude larger
  than the headlined 0.7%/0.0015 deltas — worth separating in the fix spec rather than one "cost is
  small" narrative, especially since stint-life is the family the 2026-09-10 gauge decision tunes
  against.
- The reverification pass found a genuinely new, high-severity defect three audit rounds read past:
  **F50**, the Synthetic Teammate page's own independent sign inversion (its "ahead"/"behind" verdict
  is backwards for essentially the whole page).

## How to navigate

- **`STATUS-BOARD.md`** — one row per finding (F1–F54): reverification verdict, severity call, which
  fix file it lives in.
- **`NEW-FINDINGS.md`** — F50–F54, full write-ups in the audit's own format (file:line, mechanism,
  severity, fix, "how I could be wrong").
- **`WI-*.md`** — one file per work item, grouped the way the audit's own §9/§10 proposed across all
  three rounds (merged, since round 3 extended round 1/2's WI-1, WI-2, WI-5, WI-7, WI-11, WI-12).
  Each carries the reverification verdict folded in, corrected file:line citations where they'd
  drifted by a few lines (comment churn since 2026-09-24, not substantive), and a concrete
  method/acceptance/test spec in the style of `_improvements/work/*.md`.

| File | Group (existing convention) | Findings |
| :-- | :-- | :-- |
| `WI-01-label-spine.md` | 08 foundations | F1, F5, F22, F23, F35, F38, F42, F48 (θ part), **F51** |
| `WI-02-compound-seed-provenance.md` | 08 foundations | F2, F7, F9, F39, F41 |
| `WI-03-holdout-policy.md` | 12 season coverage | F4 |
| `WI-04-browser-inference-contract.md` | 06 publication / app | F3 |
| `WI-05-season-onboarding.md` | 12 season coverage | F6, F8, F21, F24, F25, F26, F32, F33, **F52** |
| `WI-07-guard-repairs.md` | 09 scoring instruments | F11, F34, **F53**, **F54**(*) |
| `WI-08-qualifying-chain.md` | 02 feature expansion | F10 |
| `WI-09-cleanup-bundle.md` | 08 foundations (low) | F12, F13, F14, F17, F18, F19, F20, **F54** |
| `WI-11-fan-page-truth-pass.md` | 06 publication | F15, F16, F27, F29, F30, F36, F37 |
| `WI-12-06b-remeasure.md` | 06 publication | (references F23, F48) |
| `WI-13-pit-strategy.md` | 07 causal pit timing | F31 |
| `WI-14-rating-chain.md` | 06 publication | F28, F40, F44, F45, F46, **F50** |
| `WI-15-traffic-thermal-feature-semantics.md` | 02 feature expansion | F43, F47, F48 (feature side), F49 |

(*) F54 is written up once, in `WI-09-cleanup-bundle.md` next to F17 (same file, same defect class);
`WI-07` cross-references it.

## What's unchanged from the audit

The evidence standard (Definitely wrong / Probably wrong / Requires investigation), the "how I could
be wrong" discipline, and the **T1–T39** test IDs are inherited as-is — reinventing labels would only
add translation risk. Read the three original reports for full measurement detail; this folder is
the "what to do about it," not a replacement for "what's wrong." Cite findings by their original ID
(F1–F49) or the new ones (F50–F54) everywhere else in the tree (build-log.json, PRs, etc.).

## Sequencing (unchanged from round 3 §8, reconfirmed correct)

**WI-01 is the pacing item.** F1, F22, F23, F35, F38, F42 and the θ part of F48 all touch the same
question — *what does the residual's field base already contain, and what should still be subtracted
from it?* — and must ship as one label version bump, not four, because fixing F1 alone already moves
θ (F23) by 2.7×, and F22/F38 are the same defect class (a component inside the base, subtracted
again) applied to different components. **WI-02**'s point-in-time seed refit needs **F41**'s
per-parameter provenance fix landed first (otherwise a "lagged" seed can still silently carry a
same-race default with no way to tell), and benefits from **WI-05**'s bronze QA landing first too
(F2's fits consume the stint boundaries F24/F25 show are wrong in 3+ races). Nothing else blocks
anything else — **WI-03, WI-04, WI-07, WI-09, WI-11, WI-13, WI-14, WI-15** can proceed independently
and in parallel.
