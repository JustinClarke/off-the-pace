// AX-01 test fixtures: ten valid cards covering every label, status and interval kind family,
// and a factory for building the bad ones. Values are illustrative, not quoted from data.
import type { Card } from './card.types'

export function makeCard(over: Partial<Card> = {}): Card {
  return {
    id: 'era_rating.season:2024:LEC',
    kind: 'era_rating.season',
    metric: 'era_adjusted_rating',
    label: 'modelled',
    value: -0.142,
    unit: 's',
    display: '-0.14 s',
    unavailable_reason: null,
    n: { count: 24, unit: 'races' },
    interval: { low: -0.231, high: -0.053, level: 0.95, kind: 'ci_normal_95', source_columns: ['era_adjusted_rating_ci_low_s', 'era_adjusted_rating_ci_high_s'] },
    scope: { season: 2024, race_id: null, driver_id: 'LEC', constructor_id: 'ferrari', circuit_id: null, compound: null, stint_id: null, lap: null },
    source: { mart: 'int_era_normalized_driver_rating', columns: ['era_adjusted_rating'], feature: 'era-ratings-timeline', query: 'era-ratings-timeline.all', transform: 'era-ratings-timeline/transform.ts#transform' },
    versions: { data_version: '30f91247d7cb651e', label_version: 'v16', model_version: null, card_schema: '1', registry: 'abc123' },
    page: { route: '/drivers/era-ratings', params: { season: 2024 }, docs_slug: 'era-ratings-timeline' },
    caveats: [],
    sample: 'na',
    grade: null,
    status: 'active',
    held_reason: null,
    policy_fields: {},
    ...over,
  }
}

const scope0 = makeCard().scope

export const validCards: Card[] = [
  // 1. modelled, normal-approximation CI
  makeCard(),
  // 2. modelled, lap noise band, race-lost style id with a variant
  makeCard({
    id: 'race_lost.component:2024_8:LEC:compound',
    kind: 'race_lost.component',
    metric: 'compound_component_s_total',
    value: -3.412,
    display: '-3.4 s',
    n: { count: 51, unit: 'laps' },
    interval: { low: -3.9, high: -2.9, level: 0.95, kind: 'lap_noise_band', source_columns: ['ci_low', 'ci_high'] },
    scope: { ...scope0, season: 2024, race_id: '2024_8', circuit_id: 'monaco' },
    page: { route: '/lap-decomposition/race-lost', params: { race: '2024_8', driver: 'LEC' }, docs_slug: 'race-lost' },
    caveats: ['THIN_SAMPLE'],
  }),
  // 3. measured count, no interval
  makeCard({
    id: 'race_control.caution_laps:2024_8',
    kind: 'race_control.caution_laps',
    metric: 'caution_laps',
    label: 'measured',
    value: 6,
    unit: 'laps',
    display: '6 laps',
    n: { count: 78, unit: 'laps' },
    interval: null,
    scope: { ...scope0, driver_id: null, constructor_id: null, race_id: '2024_8' },
    page: { route: '/race-craft/race-control', params: { season: 2024, race_id: '2024_8' }, docs_slug: 'race-control' },
  }),
  // 4. computed with an explicit 'none' interval
  makeCard({
    id: 'field_pace.lap:2024_8:30',
    kind: 'field_pace.lap',
    metric: 'field_pace_smoothed_s',
    label: 'computed',
    value: 75.912,
    display: '75.91 s',
    n: { count: 14, unit: 'cells' },
    interval: { low: null, high: null, level: null, kind: 'none', source_columns: [] },
    scope: { ...scope0, driver_id: null, constructor_id: null, race_id: '2024_8', lap: 30 },
  }),
  // 5. experimental with a bootstrap CI
  makeCard({
    id: 'experimental.metric:2024:VER',
    kind: 'experimental.metric',
    metric: 'some_experimental_s',
    label: 'experimental',
    value: 0.31,
    interval: { low: 0.1, high: 0.52, level: 0.9, kind: 'ci_bootstrap', source_columns: ['lo', 'hi'] },
    scope: { ...scope0, driver_id: 'VER', constructor_id: 'red_bull' },
  }),
  // 6. unavailable with a reason, n = 0
  makeCard({
    id: 'era_rating.season:2018:XXX',
    label: 'unavailable',
    value: null,
    display: null,
    unavailable_reason: 'no paired teammate lap this season',
    n: { count: 0, unit: 'races' },
    interval: null,
    scope: { ...scope0, season: 2018, driver_id: 'XXX' },
  }),
  // 7. held pit-strategy card
  makeCard({
    id: 'pit_strategy.optimal_lap:2024_8:LEC:1',
    kind: 'pit_strategy.optimal_lap',
    metric: 'optimal_pit_lap_in_stint',
    label: 'modelled',
    value: null,
    display: null,
    unit: 'lap',
    n: { count: 0, unit: 'stints' },
    interval: null,
    scope: { ...scope0, race_id: '2024_8', stint_id: '2024_8_LEC_1' },
    status: 'held',
    held_reason: 'PIT_CALL_REPRODUCTION_RATE: the pit optimum has not been checked against real calls',
    page: { route: '/tyre-strategy/pit-gantt', params: { season: 2024, race_id: '2024_8' }, docs_slug: 'pit-strategy' },
  }),
  // 8. ML-style card: prediction band, holdout sample, policy fields
  makeCard({
    id: 'degradation.p50:2024_8:LEC:20',
    kind: 'degradation.p50',
    metric: 'pred_p50_s',
    value: 0.84,
    interval: { low: 0.4, high: 1.3, level: 0.8, kind: 'pred_band_p10_p90', source_columns: ['pred_p10_s', 'pred_p90_s'] },
    sample: 'holdout',
    versions: { data_version: 'd1', label_version: 'v16', model_version: 'm7', card_schema: '1', registry: 'r' },
    policy_fields: { is_in_envelope: true, calibration_flag: null },
  }),
  // 9. se_1 interval, graded, string value, no page link
  makeCard({
    id: 'corner_skill.braking:2024:HAM',
    kind: 'corner_skill.braking',
    metric: 'braking_skill_s',
    value: 0.05,
    interval: { low: 0.02, high: 0.08, level: null, kind: 'se_1', source_columns: ['braking_skill_se_s'] },
    n: { count: 120, unit: 'cells' },
    grade: 'B',
    page: null,
    policy_fields: { trust_label: 'ok', car_term_source: 'estimated', beats_baseline_significant: true },
  }),
  // 10. withdrawn measured card with a boolean value and an order-statistic CI
  makeCard({
    id: 'race_rating.race:2024_8:LEC',
    kind: 'race_rating.race',
    metric: 'rating_s',
    label: 'measured',
    value: true,
    unit: null,
    display: 'yes',
    n: { count: 33, unit: 'laps' },
    interval: { low: -0.3, high: -0.1, level: 0.95, kind: 'ci_order_stat_median', source_columns: ['ci_low', 'ci_high'] },
    status: 'withdrawn',
  }),
]

/** Ten bad cards, with the interval kind the registry would pass for the relabel case. */
export const badCards: { name: string; card: unknown; expectedIntervalKind?: string }[] = (() => {
  const noN = { ...makeCard() } as Record<string, unknown>
  delete noN.n
  return [
    { name: 'no n', card: noN },
    { name: 'modelled with no interval', card: makeCard({ interval: null }) },
    {
      name: 'experimental with kind none',
      card: makeCard({ label: 'experimental', interval: { low: null, high: null, level: null, kind: 'none', source_columns: [] } }),
    },
    {
      name: 'unavailable with a value',
      card: makeCard({ label: 'unavailable', value: 0, unavailable_reason: 'no data', n: { count: 0, unit: 'races' }, interval: null }),
    },
    {
      name: 'held with a value',
      card: makeCard({ status: 'held', value: 12, held_reason: 'PIT_CALL_REPRODUCTION_RATE', n: { count: 0, unit: 'stints' }, interval: null }),
    },
    {
      name: 'unavailable with no reason',
      card: makeCard({ label: 'unavailable', value: null, unavailable_reason: null, n: { count: 0, unit: 'races' }, interval: null }),
    },
    { name: 'n.unit outside the enum', card: makeCard({ n: { count: 24, unit: 'seasons' as never } }) },
    { name: 'label outside the vocabulary', card: makeCard({ label: 'estimated' as never }) },
    { name: 'relabelled interval kind', card: makeCard(), expectedIntervalKind: 'ci_bayes' },
    {
      name: 'low above high',
      card: makeCard({ interval: { low: 0.2, high: -0.2, level: 0.95, kind: 'ci_normal_95', source_columns: [] } }),
    },
  ]
})()
