export interface RouteConfig {
  path: string
  pillar: string
  featureId?: number
  label: string
  /** Features that don't yet render real data are hidden from nav and surfaced on /roadmap. */
  shipped?: boolean
}

export const routes: RouteConfig[] = [
  { path: '/', pillar: 'home', label: 'Home' },

  // Races (pillar retired from nav-only feature is unshipped; see /roadmap)
  { path: '/races', pillar: 'races', label: 'Races', shipped: false },
  { path: '/races/:raceId', pillar: 'races', featureId: 47, label: 'Race Story', shipped: false },

  // Ghost Car
  { path: '/ghost-car', pillar: 'ghost-car', label: 'Ghost Car' },
  { path: '/ghost-car/standings', pillar: 'ghost-car', featureId: 1, label: 'Standings' },
  { path: '/ghost-car/lap-chart', pillar: 'ghost-car', featureId: 2, label: 'Lap Chart', shipped: false },
  { path: '/ghost-car/championship', pillar: 'ghost-car', featureId: 21, label: 'Championship' },
  { path: '/ghost-car/hidden', pillar: 'ghost-car', featureId: 25, label: 'Hidden Performance' },

  // Lap Decomposition
  { path: '/lap-decomposition', pillar: 'lap-decomposition', label: 'Lap Decomposition' },
  { path: '/lap-decomposition/waterfall', pillar: 'lap-decomposition', featureId: 4, label: 'Waterfall' },
  { path: '/lap-decomposition/race-lost', pillar: 'lap-decomposition', featureId: 22, label: 'How the Race Was Lost' },
  { path: '/lap-decomposition/sectors', pillar: 'lap-decomposition', featureId: 18, label: 'Sector & Corner' },

  // Tyre & Strategy
  { path: '/tyre-strategy', pillar: 'tyre-strategy', label: 'Tyre & Strategy' },
  { path: '/tyre-strategy/survival', pillar: 'tyre-strategy', featureId: 5, label: 'Cliff Survival Profile' },
  { path: '/tyre-strategy/degradation', pillar: 'tyre-strategy', featureId: 10, label: 'Degradation Timeline' },
  { path: '/tyre-strategy/pit-gantt', pillar: 'tyre-strategy', featureId: 9, label: 'Pit Strategy Gantt' },
  { path: '/tyre-strategy/recovery', pillar: 'tyre-strategy', featureId: 40, label: 'Tyre Recovery Forecast' },
  { path: '/tyre-strategy/party-mode', pillar: 'tyre-strategy', featureId: 41, label: 'Party Mode' },

  // Aero & Conditions
  { path: '/aero', pillar: 'aero', label: 'Aero & Conditions' },
  { path: '/aero/dirty-air', pillar: 'aero', featureId: 6, label: 'Dirty Air Cost' },
  { path: '/aero/lap-map', pillar: 'aero', featureId: 13, label: 'Dirty Air Lap Map' },
  { path: '/aero/wind-altitude', pillar: 'aero', featureId: 33, label: 'Wind & Altitude', shipped: false },
  { path: '/aero/track-evolution', pillar: 'aero', featureId: 38, label: 'Track Evolution' },
  { path: '/aero/field-pace', pillar: 'aero', featureId: 39, label: 'Field Pace Curve' },

  // Race Craft (pillar retired from nav-all features unshipped; see /roadmap)
  { path: '/race-craft', pillar: 'race-craft', label: 'Race Craft', shipped: false },
  { path: '/race-craft/overtakes', pillar: 'race-craft', featureId: 29, label: 'Overtake Graph', shipped: false },
  { path: '/race-craft/stewarding', pillar: 'race-craft', featureId: 32, label: 'Penalty Impact', shipped: false },
  { path: '/race-craft/drs', pillar: 'race-craft', featureId: 35, label: 'DRS Dependency', shipped: false },
  { path: '/race-craft/pass-location', pillar: 'race-craft', featureId: 42, label: 'Pass-Location Heatmap', shipped: false },
  { path: '/race-craft/race-control', pillar: 'race-craft', featureId: 43, label: 'Race Control Timeline', shipped: false },

  // Drivers
  { path: '/drivers', pillar: 'drivers', label: 'Drivers' },
  { path: '/drivers/ratings-timeline', pillar: 'drivers', featureId: 3, label: 'Era Ratings Timeline' },
  { path: '/drivers/consistency', pillar: 'drivers', featureId: 14, label: 'Consistency' },
  { path: '/drivers/quali-vs-race', pillar: 'drivers', featureId: 8, label: 'Quali vs Race' },
  { path: '/drivers/circuit-affinity', pillar: 'drivers', featureId: 11, label: 'Circuit Affinity' },
  { path: '/drivers/era-translator', pillar: 'drivers', featureId: 24, label: 'Era Translator' },
  { path: '/drivers/wet-race', pillar: 'drivers', featureId: 26, label: 'Wet-Race Specialist' },
  { path: '/drivers/workload', pillar: 'drivers', featureId: 27, label: 'Workload Heatmap' },
  { path: '/drivers/synthetic-teammate', pillar: 'drivers', featureId: 37, label: 'Synthetic Teammate' },
  { path: '/drivers/dna-clusters', pillar: 'drivers', featureId: 23, label: 'Driver DNA Clusters', shipped: false },
  { path: '/drivers/career-twin', pillar: 'drivers', featureId: 28, label: 'Career Twin', shipped: false },
  { path: '/drivers/corner-skill', pillar: 'drivers', featureId: 30, label: 'Corner-Phase Skill' },
  { path: '/drivers/racing-line', pillar: 'drivers', featureId: 34, label: 'Racing Line Fidelity', shipped: false },

  // Constructors
  { path: '/constructors', pillar: 'constructors', label: 'Constructors' },
  { path: '/constructors/structural', pillar: 'constructors', featureId: 7, label: 'Structural Pace' },
  { path: '/constructors/circuits', pillar: 'constructors', featureId: 12, label: 'Circuit Interaction' },

  // Energy & Telemetry (pillar retired from nav-all features unshipped; see /roadmap)
  { path: '/energy', pillar: 'energy', label: 'Energy & Telemetry', shipped: false },
  { path: '/energy/telemetry-fingerprint', pillar: 'energy', featureId: 19, label: 'Telemetry Fingerprint', shipped: false },
  { path: '/energy/management-map', pillar: 'energy', featureId: 31, label: 'Energy-Management Map', shipped: false },
  { path: '/energy/ers-short-shift', pillar: 'energy', featureId: 36, label: 'ERS & Short-Shift', shipped: false },
  { path: '/energy/corner-taxonomy', pillar: 'energy', featureId: 45, label: 'Corner Taxonomy', shipped: false },

  // The Machine (ML)
  { path: '/ml', pillar: 'ml', label: 'The Machine' },
  { path: '/ml/blind-test', pillar: 'ml', featureId: 15, label: 'Blind-Test Scoreboard' },
  { path: '/ml/simulator', pillar: 'ml', featureId: 16, label: 'Degradation Simulator' },
  { path: '/ml/metrics', pillar: 'ml', featureId: 17, label: 'Model Metrics' },
  { path: '/ml/edge-cases', pillar: 'ml', featureId: 46, label: 'Edge Cases', shipped: false },

  // Query Lab
  { path: '/query', pillar: 'query', label: 'Query Lab' },

  // Data Quality
  { path: '/data-quality', pillar: 'data-quality', featureId: 44, label: 'Data Quality Audit' },

  // Roadmap (unshipped showcase)
  { path: '/roadmap', pillar: 'roadmap', label: 'Roadmap' },
]
