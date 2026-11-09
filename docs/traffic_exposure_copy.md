# Traffic exposure: draft user-facing copy (NOT WIRED)

Status: draft for review. Not linked from `docs.json`, not imported by any page or component. Source models:
`transform/models/intermediate/int_lap_physical_ahead.py`, `int_traffic_exposure_driver_race.sql`,
`int_traffic_exposure_race.sql`. Wording rule: measurement only. Nothing here may say or imply that traffic,
dirty air or a car's wake made any lap slow, or put a time cost on following.

## Constants (wording lives here, in one place)

```ts
// Copy these strings verbatim; do not paraphrase them in components.
export const TRAFFIC_BETA_LABEL =
  'BETA: estimated time spent close behind another car, from timing data. Shows where traffic happened, not why a lap was slow.'

export const TRAFFIC_DISCLAIMER =
  'These figures are approximate estimates based on timing and position data.'
```

## Page copy

**Title:** Time close behind

**Intro.** How long each driver spent within one second of the car directly ahead on track, lap by lap. The car
ahead is worked out from each car's position on track, not from the broadcast "driver ahead" field.

**What is measured**
- **Time close behind:** seconds spent less than 1 second behind a car on the same lap.
- **Bunching share:** the share of measured laps on which the driver was, at some point, within 1 second of
  the car ahead.
- **Laps we could not measure cleanly:** laps with a lapped car close by, laps where two cars ahead were too
  close together to tell apart, side-by-side moments, lap 1, and laps with missing position data. These are
  counted and shown separately. They are never counted as clear air and never counted as following.
- Safety-car, virtual-safety-car and red-flag laps are left out of close-behind time, because the field bunches
  there by rule.

**What this cannot tell you**
- It does not say whether being close behind made a driver faster or slower. It shows where traffic happened,
  not what it did to lap times.
- It is not a time loss and is not an estimate of "dirty air". No such figure is shown.
- A high share does not mean a driver was held up, and a low share does not mean a driver had a clear race.
- Who the car ahead is can be misread for a moment, mostly around lapped and overlapping cars. In a typical
  race this happens on about 3 in 1,000 position readings, and on up to about 2 in 100 in the worst race
  checked.
- Lap 1 is not measured: the order of a bunched field at the start cannot be resolved reliably.

**Disclaimer (one line, always shown):** These figures are approximate estimates based on timing and position data.

## BETA label: component design (for review, not built)

Text: `TRAFFIC_BETA_LABEL` above, verbatim.

- **Form:** full-width banner directly under the page title, above any chart or table. Not a tooltip, not a
  footnote. A compact pill variant ("BETA") may repeat on cards, but the full banner text must appear once.
- **F1 styling:** left accent bar 4 px in the existing F1 red token `rgb(var(--color-accent))` (225 6 0);
  "BETA" set as an uppercase, bold, letter-spaced (0.12em) chip, white text on the accent red; the rest of
  the sentence in the body text colour at normal weight, at least the page body size (no small print).
  Subtle tinted background `rgb(var(--color-accent) / 0.08)`. Works in light and dark themes because it uses
  the existing token.
- **Motion:** one pulse on mount (opacity/scale of the BETA chip, ~600 ms, `repeat: 0`), then static. No
  looping, no flashing. With `prefers-reduced-motion: reduce` there is no animation at all (use
  framer-motion's `useReducedMotion()`, as `src/routes/home/HeroTrace.tsx` already does).
- **Accessibility:** `role="note"`, text is real text (not an image), contrast of white on 225 6 0 is above
  4.5:1 for bold text at body size.

Sketch (not added to `app/`):

```tsx
import { motion, useReducedMotion } from 'framer-motion'
import { TRAFFIC_BETA_LABEL } from './copy'

export function TrafficBetaBanner() {
  const reduce = useReducedMotion()
  const [chip, ...rest] = TRAFFIC_BETA_LABEL.split(': ')
  return (
    <div role="note"
      className="flex items-start gap-3 border-l-4 border-[rgb(var(--color-accent))]
                 bg-[rgb(var(--color-accent)/0.08)] px-4 py-3 text-base">
      <motion.span
        className="rounded-sm bg-[rgb(var(--color-accent))] px-2 py-0.5 text-sm font-bold uppercase
                   tracking-[0.12em] text-white"
        initial={reduce ? false : { scale: 1, opacity: 0.6 }}
        animate={reduce ? undefined : { scale: [1, 1.08, 1], opacity: [0.6, 1, 1] }}
        transition={reduce ? undefined : { duration: 0.6, repeat: 0, ease: 'easeOut' }}
      >
        {chip}
      </motion.span>
      <span>{rest.join(': ')}</span>
    </div>
  )
}
```

## Words not to use on this page

"cost", "penalty", "time lost", "held up", "dirty air effect", "wake effect", "because of traffic",
"slowed by". Any sentence linking close-behind time to a lap time or result needs a validated measure that
does not exist (decision D1, experiment 13).
