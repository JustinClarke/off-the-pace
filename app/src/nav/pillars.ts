export interface Pillar {
  id: string
  label: string
  icon: string
  path: string
  description: string
  featureFlag?: string
}

export const pillars: Pillar[] = [
  {
    id: 'home',
    label: 'Home',
    icon: '⬡',
    path: '/',
    description: 'Project overview and navigation',
  },
  {
    id: 'races',
    label: 'Races',
    icon: '⏱',
    path: '/races',
    description: 'Race lifecycle deep dive causal leaderboard to ghost-car sandbox',
  },
  {
    id: 'ghost-car',
    label: 'Ghost Car',
    icon: '👻',
    path: '/ghost-car',
    description: 'Counterfactual standings, lap charts, and championship re-runs',
  },
  {
    id: 'lap-decomposition',
    label: 'Lap Decomposition',
    icon: '⧉',
    path: '/lap-decomposition',
    description: 'Seven-term additive identity enforced by CI on every lap',
  },
  {
    id: 'tyre-strategy',
    label: 'Tyre & Strategy',
    icon: '◎',
    path: '/tyre-strategy',
    description: 'Degradation, cliff survival, pit strategy, and recovery',
  },
  {
    id: 'aero',
    label: 'Aero & Conditions',
    icon: '≋',
    path: '/aero',
    description: 'Dirty air cost, track evolution, wind, altitude, field pace',
  },
  {
    id: 'race-craft',
    label: 'Race Craft',
    icon: '⚔',
    path: '/race-craft',
    description: 'Overtakes, DRS dependency, stewarding, pass-location heatmap',
  },
  {
    id: 'drivers',
    label: 'Drivers',
    icon: '◈',
    path: '/drivers',
    description: 'Era-adjusted ratings, consistency, archetypes, circuit affinity',
  },
  {
    id: 'constructors',
    label: 'Constructors',
    icon: '⊞',
    path: '/constructors',
    description: 'Structural pace and circuit interaction matrices',
  },
  {
    id: 'energy',
    label: 'Energy & Telemetry',
    icon: '⚡',
    path: '/energy',
    description: 'ERS deployment, coast tax, telemetry fingerprints, corner taxonomy',
  },
  {
    id: 'ml',
    label: 'The Machine',
    icon: '◇',
    path: '/ml',
    description: 'Degradation prediction: blind-test scoreboard, live simulator, model metrics',
  },
  {
    id: 'query',
    label: 'Query Lab',
    icon: '⌗',
    path: '/query',
    description: 'DuckDB-Wasm SQL over all registered marts',
    featureFlag: 'queryLab',
  },
  {
    id: 'data-quality',
    label: 'Data Quality',
    icon: '✦',
    path: '/data-quality',
    description: 'Anomaly audit and coverage stats the DE view',
  },
]
