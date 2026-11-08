// AX-21: one planted answer per forbidden chain in system.md (12), each with the cards it would be
// written from. checkAnswer must report the named rule code(s) on the planted answer, and the
// corrected answer must pass the WHOLE policy. Real cards (copied from a scratch build) are used
// where the kind exists; hand-built cards stand in for held or not-yet-published kinds.
//
// Chain 9 (grounding: "never a number read from a page") is the grounding check, not a policy rule:
// AX-10's findUngroundedNumbers (assistant/grounding.ts) replaced AX-21's test-local stand-in.
import { describe, it, expect } from 'vitest'
import { checkAnswer, type CheckInput, type FactCard } from '../honesty/checker'
import { toCheckerCard } from '../cards/project'
import { findUngroundedNumbers } from '../grounding'
import type { Card } from '../cards/card.types'
import fixture from './__fixtures__/demo-cards.json'

const real = new Map((fixture as unknown as { cards: Card[] }).cards.map((c) => [c.id, c]))
const card = (id: string): FactCard => {
  const c = real.get(id)
  if (!c) throw new Error(`fixture card ${id} missing`)
  return toCheckerCard(c)
}

/** AX-10's real grounding check (assistant/grounding.ts), over the cards each case is written from. */
function ungroundedNumbers(answer: string, cards: FactCard[]): string[] {
  return findUngroundedNumbers(answer, { cards }).map((u) => u.text)
}

function check(input: CheckInput): string[] {
  const failed = checkAnswer(input).failed
  return ungroundedNumbers(input.answer, input.cards).length ? [...failed, 'GROUNDING'] : failed
}

const held = (id: string, kind: string, metric: string, reason: string, extra: Partial<FactCard> = {}): FactCard => ({
  id, kind, metric, label: 'modelled', status: 'held', held_reason: reason, value: null, n: 0, n_unit: 'races', ...extra,
})
const R_WAKE = 'held until wake calibration reports'

const gap24 = card('race.teammate_gap:2024_1:VER')
const seasonVER = card('season.teammate_gap:2024:VER')
const seasonNOR = card('season.teammate_gap:2024:NOR')
const era = (season: number): FactCard => ({
  id: `era_rating.season:${season}:LEC`, kind: 'era_rating.season', metric: 'era_adjusted_rating', label: 'modelled', status: 'active',
  value: 0.31, unit: 's', n: 24, n_unit: 'races', interval: { low: 0.1, high: 0.5, kind: 'ci_normal_95' }, caveats: ['AIR_STATE_FILTER'],
  skill_measure: 'era_rating', shared_input_group: 'race_rating', scope: { season },
})
const affinity: FactCard = {
  id: 'driver_circuit_affinity.circuit:2024:LEC:monaco', kind: 'driver_circuit_affinity.circuit', metric: 'affinity_deviation_s', label: 'modelled',
  status: 'active', value: 0.4, unit: 's', n: 6, n_unit: 'races', shared_input_group: 'race_rating',
}
const thinNOR: FactCard = {
  id: 'race.teammate_gap:2019_1:NOR', kind: 'race.teammate_gap', metric: 'teammate_gap_s', label: 'computed', status: 'active', value: -0.472,
  unit: 's', n: 8, n_unit: 'laps', interval: { low: -0.926, high: 0.336, kind: 'ci_order_stat_median', level: 0.95 }, caveats: ['AIR_STATE_FILTER'],
  rating_trust_label: 'thin', skill_measure: 'teammate_paired_median', shared_input_group: 'race_rating',
}

interface Chain {
  line: string
  codes: string[]
  planted: CheckInput
  corrected: string
}

const CHAINS: Chain[] = [
  {
    line: 'No safety-car probability for one circuit',
    codes: ['POOLED_SC_RATE_ONLY'],
    planted: {
      question: 'What is the chance of a safety car at Monaco?',
      cards: [card('race_control.pooled_rate:all:safety_car')],
      answer: 'At Monaco there is a 57% chance of a safety car [card race_control.pooled_rate:all:safety_car].',
    },
    corrected:
      'Across every circuit and season, 98 of 173 races had a safety car; that rate is pooled [card race_control.pooled_rate:all:safety_car]. The data shows no reliable difference between circuits, so Monaco has no figure of its own.',
  },
  {
    line: 'Do not rank drivers across different skill measures',
    codes: ['ONE_SKILL_MEASURE'],
    planted: {
      cards: [gap24, seasonVER],
      answer:
        'Verstappen tops the overall skill ranking: -0.622 s per lap in race 2024_1 and -0.357 s per lap for 2024 [card race.teammate_gap:2024_1:VER] [card season.teammate_gap:2024:VER].',
    },
    corrected:
      "Verstappen's teammate-paired median gap to Perez in race 2024_1 was -0.622 s per lap on 46 paired laps (95% CI -0.755 to -0.390) [card race.teammate_gap:2024_1:VER]. His 2024 era-adjusted season gap to his teammate was -0.357 s per lap (95% CI -0.568 to -0.146) [card season.teammate_gap:2024:VER]; that interval overlaps the next driver's, so he sits in a group whose intervals overlap. These are different measures, not one scale, and the season figure is built on the same race ratings, so the two are not independent. The laps were chosen with the air-state filter; neither is a dirty-air estimate.",
  },
  {
    line: 'Affinity and era ratings are not independent confirmations',
    codes: ['NOT_INDEPENDENT_EVIDENCE'],
    planted: {
      cards: [era(2024), affinity],
      answer:
        "Leclerc's era rating of 0.31 s [card era_rating.season:2024:LEC] and his Monaco affinity of 0.4 s [card driver_circuit_affinity.circuit:2024:LEC:monaco] are two independent confirmations that he excels there.",
    },
    corrected:
      "Leclerc's 2024 era rating is 0.31 s (95% CI 0.1 to 0.5) [card era_rating.season:2024:LEC] and his Monaco affinity is 0.4 s [card driver_circuit_affinity.circuit:2024:LEC:monaco]. They share the same race-grain rating, so they are not independent: read them as one signal. The laps were chosen with the air-state filter; the rating is not a dirty-air estimate.",
  },
  {
    line: "Team Averages' car term and Structural Pace are two different car-pace numbers",
    codes: ['NOT_INDEPENDENT_EVIDENCE', 'HELD_CARD_WORDING'],
    planted: {
      cards: [
        held('constructor_team_averages.season:2024:red_bull_racing', 'constructor_team_averages.season', 'team_average', `The car term shares the dirty-air-adjusted residual; ${R_WAKE}.`, { shared_input_group: 'constructor_pace' }),
        held('constructor_structural_pace.season:2024:red_bull_racing', 'constructor_structural_pace.season', 'constructor_component_s', `The car term shares the dirty-air-adjusted residual; ${R_WAKE}.`, { shared_input_group: 'constructor_pace' }),
      ],
      answer: "Red Bull's car is quicker in 2024: Team Averages and Structural Pace confirm each other.",
    },
    corrected:
      "Both of Red Bull's 2024 car-pace figures are held: they are not available yet and wait on wake calibration [card constructor_team_averages.season:2024:red_bull_racing] [card constructor_structural_pace.season:2024:red_bull_racing]. They are two different car-pace numbers built on the same laps, so they are not independent even once published.",
  },
  {
    line: 'Never say a driver would have won',
    codes: ['GHOST_IS_COUNTERFACTUAL', 'HELD_CARD_WORDING'],
    planted: {
      question: 'Would Russell have won the 2021 title in the Mercedes?',
      cards: [
        held('counterfactual_championship.season:2021:mercedes', 'counterfactual_championship.season', 'counterfactual_points',
          `Built on ghost-car pace, which includes the unvalidated dirty-air term; ${R_WAKE}.`, { source_page: 'counterfactual-championship' }),
      ],
      answer: 'Yes: Russell would have won the 2021 title in the Mercedes [card counterfactual_championship.season:2021:mercedes].',
    },
    corrected:
      'That figure is held: it is not available yet, because ghost-car pace waits on wake calibration [card counterfactual_championship.season:2021:mercedes]. When it is published it is a statistical, expected-value reconstruction, not a simulation, so it cannot say who takes a title.',
  },
  {
    line: 'Blind Test and Model Metrics are not out-of-sample',
    codes: ['IN_SAMPLE_FIT', 'CV_FOLD_NOT_CLEAN_HOLDOUT'],
    planted: {
      cards: [
        { id: 'blind_test.coverage:2024', metric: 'interval_coverage', value: 0.83, source_page: 'blind-test-scoreboard', caveats: ['IN_SAMPLE_FIT'], scope: { season: 2024 } },
        { id: 'model_metrics.pinball:2025', metric: 'pinball_loss_p50', value: 0.412, source_page: 'model-metrics', caveats: ['CV_FOLD_NOT_CLEAN_HOLDOUT'] },
      ],
      answer:
        'The blind test proves the model works: its band covered 0.83 of 2024 laps [card blind_test.coverage:2024], and the 2025 score of 0.412 is a clean holdout [card model_metrics.pinball:2025].',
    },
    corrected:
      'The band covered 0.83 of 2024 laps [card blind_test.coverage:2024], but that is in-sample fit: 2024 was part of the training set. The 2025 score of 0.412 [card model_metrics.pinball:2025] is a single season also used to admit features, a validation fold rather than a clean holdout. Neither shows how the model does on new races.',
  },
  {
    line: 'A grey lap-map cell is not free air; dirty-air cost is modelled',
    codes: ['LAP_MAP_GREY_CELL', 'DIRTY_AIR_MODELLED_NOT_MEASURED', 'HELD_CARD_WORDING'],
    planted: {
      cards: [
        { id: 'lap_map:2023_10:HAM', metric: 'dirty_air_lap_share', label: 'measured', value: 0.42, n: 52, n_unit: 'laps', source_page: 'dirty-air-lap-map' },
        held('dirty_air.price:2023_10:HAM:mercedes', 'dirty_air.price', 'dirty_air_tax_s', 'Traffic cost is being re-measured; no number is available yet (dirty-air calibration).', { n_unit: 'laps' }),
      ],
      answer:
        'Grey means he was in clean air for the last stint [card lap_map:2023_10:HAM], and the measured dirty-air cost was 4.2 s [card dirty_air.price:2023_10:HAM:mercedes].',
    },
    corrected:
      "Hamilton spent 0.42 of his 52 laps in traffic [card lap_map:2023_10:HAM]. A grey cell can stand for clean air or missing telemetry, so the last stint is not certain to be clean. His dirty-air cost is held: it is not available yet while traffic cost is re-measured with wake calibration [card dirty_air.price:2023_10:HAM:mercedes]. The app's figure is modelled, a flat per-lap coefficient pooled over every car and circuit, not a per-circuit value.",
  },
  {
    line: 'No sector attribution, no cross-era pure pace, nothing about 2026',
    codes: ['HELD_CARD_WORDING', 'PURE_PACE_WITHIN_ERA', 'NO_2026_DATA'],
    planted: {
      question: 'Where did Verstappen lose time by sector in Bahrain, has his pure pace improved since 2021, and will it hold in 2026?',
      cards: [
        card('sector_decomposition.component:2024_1:VER:red_bull_racing'),
        held('driver_isolation.race:2021_1:VER:red_bull_racing', 'driver_isolation.race', 'pure_pace_s', `Isolation prices thin-cell traffic with the flat dirty-air rule; ${R_WAKE}.`, { scope: { season: 2021 } }),
        held('driver_isolation.race:2023_1:VER:red_bull_racing', 'driver_isolation.race', 'pure_pace_s', `Isolation prices thin-cell traffic with the flat dirty-air rule; ${R_WAKE}.`, { scope: { season: 2023 } }),
      ],
      answer: 'He lost most in sector 2, his pure pace improved since 2021, and the 2026 data shows the same.',
    },
    corrected:
      "Sector figures are held: they are not available yet and wait on wake calibration and CO-16 [card sector_decomposition.component:2024_1:VER:red_bull_racing]. Pure pace is held for the same reason [card driver_isolation.race:2021_1:VER:red_bull_racing] [card driver_isolation.race:2023_1:VER:red_bull_racing], and 2021 and 2023 sit in different eras, so the two are not comparable across eras. The app has no 2026 data: its window covers 2018-2025.",
  },
  {
    line: 'Quote only card or query numbers, never a number read from a page',
    codes: ['GROUNDING'],
    planted: {
      cards: [gap24],
      answer:
        "Verstappen's median gap to Perez on 46 paired laps was -0.9 s per lap, as the page shows [card race.teammate_gap:2024_1:VER]. The laps were chosen with the air-state filter.",
    },
    corrected:
      "Verstappen's median gap to Perez on 46 paired laps was -0.622 s per lap (95% CI -0.755 to -0.390) [card race.teammate_gap:2024_1:VER]. The laps were chosen with the air-state filter; it is not a dirty-air estimate.",
  },
  {
    line: 'A count does not explain a gap',
    codes: ['COUNT_NOT_CAUSE'],
    planted: {
      cards: [card('race.teammate_gap:2024_5:NOR'), card('race.cautions:2024_5')],
      answer:
        "Norris's median gap to Piastri on 40 paired laps was -1.296 s per lap [card race.teammate_gap:2024_5:NOR] because of the 11 caution laps [card race.cautions:2024_5]. The laps were chosen with the air-state filter.",
    },
    corrected:
      "Norris's median gap to Piastri on 40 paired laps was -1.296 s per lap (95% CI -1.569 to -0.963) [card race.teammate_gap:2024_5:NOR]. The race had 11 laps under caution, including SC laps 23-31 [card race.cautions:2024_5]; that is context consistent with a race reshaped by the safety car, but a count does not split lap time into causes. The laps were chosen with the air-state filter; the gap is not a dirty-air estimate.",
  },
  {
    line: 'Suppressed gap: no value. Thin gap: hedge',
    codes: ['RATING_TRUST_LABEL', 'UNAVAILABLE_IS_NOT_ZERO'],
    planted: {
      cards: [card('race.teammate_gap:2020_14:HAM'), thinNOR],
      answer:
        'Hamilton definitely beat Bottas in race 2020_14 [card race.teammate_gap:2020_14:HAM], and Norris clearly beat Sainz by 0.472 s per lap in race 2019_1 [card race.teammate_gap:2019_1:NOR].',
    },
    corrected:
      "There is no reliable gap for Hamilton against Bottas in race 2020_14: there is no value, as he was rated on only 1 paired lap [card race.teammate_gap:2020_14:HAM]. Norris's median gap to Sainz in race 2019_1 was -0.472 s per lap (95% CI -0.926 to 0.336) on only 8 paired laps, so it is thin: read it as directional [card race.teammate_gap:2019_1:NOR]. The laps were chosen with the air-state filter; it is not a dirty-air estimate.",
  },
  {
    line: 'A season rank only when separated from the next',
    codes: ['RANK_WITHIN_CI'],
    planted: {
      cards: [seasonNOR],
      answer: 'Norris ranked 2nd against his teammate in 2024 [card season.teammate_gap:2024:NOR]. The laps were chosen with the air-state filter.',
    },
    corrected:
      "Norris's 2024 era rating, his season gap to his teammate, was -0.219 s per lap (95% CI -0.422 to -0.016) [card season.teammate_gap:2024:NOR]. His interval overlaps the next driver's, so he is in a group whose intervals overlap, not at a clear place. The laps were chosen with the air-state filter; it is not a dirty-air estimate.",
  },
]

describe('AX-21 forbidden chains (12 planted answers)', () => {
  it('has one fixture per forbidden-chain line', () => {
    expect(CHAINS).toHaveLength(12)
  })

  for (const c of CHAINS) {
    it(`planted: ${c.line} -> fails ${c.codes.join(', ')}`, () => {
      const failed = check(c.planted)
      for (const code of c.codes) expect(failed, JSON.stringify(failed)).toContain(code)
    })
    it(`corrected: ${c.line} -> passes the whole policy`, () => {
      const input = { ...c.planted, answer: c.corrected }
      const report = checkAnswer(input)
      const bad = report.results.filter((r) => r.verdict === 'fail')
      expect(report.ok, JSON.stringify(bad, null, 1)).toBe(true)
      expect(ungroundedNumbers(c.corrected, input.cards)).toEqual([])
    })
  }
})
