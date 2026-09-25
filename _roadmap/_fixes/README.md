# _fixes — reverified fix plan for the transform forensic audit, and the board that runs it

**What this is.** `_roadmap/_improvements/reference/transform_forensic_audit*.md` (3 rounds, run
2026-09-24) found 49 defects (F1–F49) in the transform/ML pipeline and the fan-facing app. This
folder is that audit **independently reverified against the live tree**, extended with the
findings it missed (F50–F55), and turned into work items with a board that executes them.

## Layout

```
_fixes/
├── README.md               this file: what it is, how to run it, how it was reverified
├── status/                 execution state — start here to run anything
│   ├── board.py            renderer + validator (never writes to the log)
│   ├── build-log.json      AUTHORITATIVE state: items, stages, open decisions, handoff history
│   └── BUILD-ORDER.md      the rules, and the generated, ordered task list
├── wi/                     one doc per work item: method, acceptance, tests, definition of done
└── reference/              static evidence, not state
    ├── finding-verdicts.md one row per finding (F1–F55): reverification verdict, severity, its WI
    └── new-findings.md     F50–F55, written up in the audit's own format
```

Same mechanism as [`../_improvements/status/`](../_improvements/status/BUILD-ORDER.md) — a JSON log,
a read-only board, a generated task list — adapted for fixes. `status/BUILD-ORDER.md` lists what
differs and why.

## Running it

```bash
python3 _roadmap/_fixes/status/board.py            # every item, its stage, what it waits on, open rulings, next command
python3 _roadmap/_fixes/status/board.py --check    # invariants; run after any edit to build-log.json
```

Say `proceed` and the orchestrating session spawns an agent, at the model the log names, on the
pointer item; it reviews the result before touching the log. Five items wait on a ruling of yours
(the `FD*` decisions in the board's output) — those are asked first, in plain language.

**State lives in `status/build-log.json` and nowhere else.** This README, the `wi/` docs and
`reference/` describe the defects and the fixes; none of them records whether a fix has been
done. If one of them ever seems to say so, it is stale — the log wins.

## Work items

One doc per work item in [`wi/`](wi/). Three are executed as two board items each, where part of the
doc is waiting on a ruling and part is not (why: `status/BUILD-ORDER.md`). There is no WI-06 or
WI-10: the numbering is the audit's own, kept so cross-references to it stay valid.

| Doc | Board item(s) | Group | Findings |
| :-- | :-- | :-- | :-- |
| [WI-01](wi/WI-01-label-spine.md) | `WI-01` | 08 foundations | F1, F5, F22, F23, F35, F38, F42, F48 (θ), **F51** |
| [WI-02](wi/WI-02-compound-seed-provenance.md) | `WI-02a`, `WI-02b` | 08 foundations | F41, F7, F39 · F2, F9 |
| [WI-03](wi/WI-03-holdout-policy.md) | `WI-03` | 12 season coverage | F4 |
| [WI-04](wi/WI-04-browser-inference-contract.md) | `WI-04` | 06 publication / app | F3 |
| [WI-05](wi/WI-05-season-onboarding.md) | `WI-05` | 12 season coverage | F6, F8, F21, F24, F25, F26, F32, F33, **F52** |
| [WI-07](wi/WI-07-guard-repairs.md) | `WI-07` | 09 scoring instruments | F11, F34, **F53**, **F54**(*) |
| [WI-08](wi/WI-08-qualifying-chain.md) | `WI-08` | 02 feature expansion | F10 |
| [WI-09](wi/WI-09-cleanup-bundle.md) | `WI-09` | 08 foundations (low) | F12, F13, F14, F17, F18, F19, F20, **F54** |
| [WI-11](wi/WI-11-fan-page-truth-pass.md) | `WI-11` | 06 publication | F15, F16, F27, F29, F30, F36, F37 |
| [WI-12](wi/WI-12-06b-remeasure.md) | `WI-12` | 06 publication | (references F23, F48) |
| [WI-13](wi/WI-13-pit-strategy.md) | `WI-13` | 07 causal pit timing | F31 |
| [WI-14](wi/WI-14-rating-chain.md) | `WI-14a`, `WI-14b` | 06 publication | F50, F28, F46 · F40, F44, F45 |
| [WI-15](wi/WI-15-traffic-thermal-feature-semantics.md) | `WI-15a`, `WI-15b` | 02 feature expansion | F43, F48 (coding) · F47, F49 |

(*) F54 is written up once, in `WI-09` next to F17 (same file, same defect class); `WI-07`
cross-references it.

The group ids are the `_improvements` groups these fixes belong to, so a fix can still be
cross-referenced against that tree. The evidence standard (Definitely wrong / Probably wrong /
Requires investigation), the "how I could be wrong" discipline and the **T1–T39** test ids are
inherited from the audit as-is — reinventing labels would only add translation risk. Cite
findings by their original id (F1–F49) or the new ones (F50–F55) everywhere else in the tree.

## Reverification method

1. Re-ran the audit's own reproducibility harness, `verify_findings.py`, read-only against the live
   `data/dev.duckdb`. It had a path bug (`_db.py` resolved `REPO` one directory short of the real
   repo root — see F53 in [`wi/WI-07-guard-repairs.md`](wi/WI-07-guard-repairs.md)) which was
   patched in a scratch copy, not in the tracked artefact. **Result: 51/51 mechanical checks still
   PRESENT**, magnitudes matching the written reports almost exactly (a handful of counts moved by
   single digits, consistent with the dev build advancing slightly, not with the defects going
   away). Nothing in the three reports is stale on the facts.
2. Beyond that, five independent read-only reviews — one per finding cluster, each starting cold with
   no access to the audit's own conclusions beyond the report text — re-read the cited source
   directly, re-derived several of the algebraic/mechanism claims by hand instead of trusting the
   audit's probes, and judged whether severity, "ML impact," and the recommended fix are proportionate,
   overblown, or understated. Every finding got one of: **CONFIRMED-AS-STATED**, **ARGUABLE**
   (mechanism holds, some part of the characterization is debatable), or **UNDERSTATED**. None came
   back OVERBLOWN, INVALID, or STALE-OR-FIXED. Verdicts: [`reference/finding-verdicts.md`](reference/finding-verdicts.md).
3. The same reviews surfaced five issues not in F1–F49, numbered **F50–F54** to keep them out of the
   audit's own range while staying cross-referenceable; the WI-05 build later found a sixth, **F55**.
   Write-ups:
   [`reference/new-findings.md`](reference/new-findings.md).

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

## Sequencing — the reasoning behind the board's dependencies

The dependency graph itself is in `status/build-log.json` (`depends_on`); this is why it looks the
way it does.

**`WI-01` is the pacing item.** F1, F22, F23, F35, F38, F42 and the θ part of F48 all touch the same
question — *what does the residual's field base already contain, and what should still be subtracted
from it?* — and must ship as one label version bump, not four, because fixing F1 alone already moves
θ (F23) by 2.7×, and F22/F38 are the same defect class (a component inside the base, subtracted
again) applied to different components. θ must be re-estimated exactly once, **after** F48's
feature-coding fix — which is why `WI-01` depends on `WI-15a` (the traffic half of WI-15; the thermal
half does not feed θ). It also waits on two rulings, `FD1` and `FD2`.

**`WI-02`'s refit needs `WI-02a` first.** A "point-in-time" seed is only honest if a cell labelled
"fitted" really was; F41's per-parameter provenance is what makes that checkable. The refit also
waits on `WI-05`, whose bronze QA fixes the stint boundaries the seed's fits consume (F24/F25 are
wrong in 3+ races), and on `FD3`. `WI-08` shares that seed and waits for the refit.

**`WI-11` waits on `WI-05`** only for F27, which needs F26's wet-flag fix; if `WI-05` slips, split F27
off rather than idling the other six.

Everything else — `WI-03`, `WI-04`, `WI-07`, `WI-09`, `WI-13`, `WI-14a`, `WI-15a`, `WI-15b` — can
proceed independently and in parallel. `WI-04` is the one with a deadline: it has to land before the
v14 manifest is published to the CDN.
