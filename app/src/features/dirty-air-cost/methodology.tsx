import { CANONICAL_DOCS_BASE } from '../../config'
import { DD_WC2_DISCLAIMER, PLACEHOLDER_LINE } from './transform'

export const methodologyContent = (
  <>
    <p>
      The dirty air cost leaderboard shows a <strong>placeholder</strong> estimate of the time each
      driver lost to the wake of the car ahead in the selected race. Every value on the page is
      modelled, not measured.
    </p>
    <ul className="list-disc pl-4 mt-3 space-y-1">
      <li><strong>Assumed loss, per race</strong>: a fixed rule, not a fit. The race layout's
        braking corners are counted by apex speed as fast-corner equivalents (fast, 200 km/h or
        more, 1; medium 0.5; slow, under 120 km/h, 0.25; a kink taken flat 0.25). A lap of 8
        equivalents is assumed to cost 0.35 s for a full lap within 1 s with 2017-18 cars. That is
        multiplied by an assumed factor for the car generation: 2019-21 0.90, 2022 0.65 (the
        ground-effect rules were designed to make following easier), 2023 0.75, 2024-25 0.80. The
        result is kept between 0.15 s and 0.55 s and rounded to 0.01 s. A race with no corner data
        uses a circuit-class value (fast 0.45 s, medium 0.30 s, slow 0.20 s) times the same factor,
        and is marked FALLBACK. Corner counts come from the circuit layout, never from lap
        times.</li>
      <li><strong>Tyre factor (assumed)</strong>: each lap's race value is multiplied by a small
        factor for the lap's dry compound. From 2019 it uses Pirelli's C-number (C1 hardest to C6
        softest) against the race's medium compound: one step softer 1.10, two or more steps softer
        1.17, one step harder 0.96, two or more steps harder 0.93, the medium itself 1.00. Steps are
        counted in C-numbers, so a race whose three compounds skip a number follows the real gap.
        The factor is kept between 0.90 and 1.17. The nominations come from a table of
        Pirelli's choices checked against a published source for every race. In 2018 Pirelli used
        names, not C-numbers, so the race's three dry compounds are ranked by softness: softest 1.10,
        middle 1.00, hardest 0.96. A car in the wake slides more and runs hotter tyres, and a softer
        compound overheats sooner. This is a per-lap sensitivity, not tyre wear (wear builds over a
        stint and is not modelled). Intermediate and wet laps get 1.00, because the dry ranking does
        not extend to them.</li>
      <li><strong>Car factor</strong>: 1.00 for every team in every season (the neutral
        default). A team gets a different value only if a public, checkable source about its car
        concept supports one, and none does today. No team is assumed to suffer more or less in
        the wake.</li>
      <li>The per-lap value (race value x tyre x car) is kept between 0.15 s and 0.55 s. A lap with
        no recorded compound or team gets the neutral 1.00 and is flagged.</li>
      <li><strong>Measured exposure</strong>: the share of the lap spent within 1 s of the car
        ahead, plus half the share spent between 1 and 2 s (the loss tapers to nothing at 2 s).
        Gaps are crossing-time gaps: the difference between two cars passing the same point on
        track.</li>
      <li><strong>Per-lap cost</strong>: assumed loss times exposure. <strong>Total</strong> is the
        sum over laps with a value; <strong>Avg/Lap</strong> is the mean over those laps.</li>
      <li><strong>Unavailable</strong>: a lap with no measured gap, or a safety car, VSC or red
        flag lap, has no value and is shown as —, never 0. The leaderboard counts those laps
        and gives the reason.</li>
    </ul>
    <p className="mt-3">
      <strong>Reading the visuals</strong>: the bar chart shows each driver's total, labelled
      placeholder, modelled; a driver with no value shows — and the reason, never an empty bar of
      0. Select a driver to see the lap-by-lap build-up: the measured share of each lap within 1 s
      and between 1 and 2 s of the car ahead, above the assumed cost for that lap. Safety car and
      no-gap laps are hatched, never 0. The table below the charts has the same numbers: each row shows the total, average per lap and a modelled label, and opens (click, Enter or Space) to show the tyre and car factors, lap counts and unavailable reasons.
    </p>
    <p className="mt-3">
      Not included: being held up by a slower car, the tow gain on straights, DRS, and tyre
      wear. The car-generation and tyre factors are assumptions, not measurements. These values are not used to train any model; the
      machine-learning models see the measured gaps only.
    </p>
    <p className="mt-3">
      The total depends mostly on track position and car pace (how long the driver spent close
      behind another car), not on driver error. Read it as how much traffic shaped the race, and
      pair it with the lap air map to see when the driver was close behind another car.
    </p>
    <p className="mt-3 text-xs">{DD_WC2_DISCLAIMER}</p>
    <p className="mt-1 text-xs">{PLACEHOLDER_LINE}</p>
    <p className="mt-3 text-muted/70">
      Source: <code>int_lap_wake_placeholder_cost</code> and
      <code> int_wake_placeholder_race_loss</code> (rule in
      <code> seeds/wake_placeholder_rule.csv</code>; tyre and car factors in
      <code> seeds/wake_placeholder_c_number_factor.csv</code>,
      <code> seeds/wake_placeholder_tyre_allocation.csv</code>,
      <code> seeds/wake_placeholder_compound_factor.csv</code> and
      <code> seeds/wake_placeholder_constructor_factor.csv</code>). Single race view.
    </p>
  </>
)

export const methodologyHref = `${CANONICAL_DOCS_BASE}/app/dirty-air-cost`
