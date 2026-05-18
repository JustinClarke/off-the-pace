// SEO metadata helpers generates title and description strings for each route's <head> tags.
export interface PageMeta {
  title: string
  description: string
}

const BASE = 'Off The Pace'

export const pageMeta: Record<string, PageMeta> = {
  '/': { title: BASE, description: 'F1 causal lap time decomposition and performance analysis.' },
  '/ghost-car': { title: `Ghost Car · ${BASE}`, description: 'What would a reference constructor have scored with each driver?' },
  '/ghost-car/standings': { title: `Ghost Car Standings · ${BASE}`, description: 'Counterfactual race finish positions.' },
  '/ghost-car/lap-chart': { title: `Ghost Car Lap Chart · ${BASE}`, description: 'Lap-by-lap actual vs predicted pace.' },
  '/ghost-car/championship': { title: `Ghost Car Championship · ${BASE}`, description: 'Season-level counterfactual standings.' },
  '/ghost-car/hidden': { title: `Hidden Performance · ${BASE}`, description: 'Under-rewarded drives.' },
  '/lap-decomposition': { title: `Lap Decomposition · ${BASE}`, description: 'Seven-term lap time identity.' },
  '/lap-decomposition/waterfall': { title: `Waterfall · ${BASE}`, description: 'Seven-term lap time decomposition waterfall.' },
  '/lap-decomposition/race-lost': { title: `Race Lost · ${BASE}`, description: 'Six-bucket gap decomposition.' },
  '/tyre-strategy': { title: `Tyre Strategy · ${BASE}`, description: 'Degradation and survival modelling.' },
  '/tyre-strategy/survival': { title: `Survival Profile · ${BASE}`, description: 'Kaplan-Meier tyre cliff profiles.' },
  '/tyre-strategy/degradation': { title: `Degradation Timeline · ${BASE}`, description: 'Pace vs expected degradation.' },
  '/tyre-strategy/pit-gantt': { title: `Pit Gantt · ${BASE}`, description: 'Strategy Gantt and pit optimizer.' },
  '/aerodynamics': { title: `Aerodynamics · ${BASE}`, description: 'Dirty air and airflow analysis.' },
  '/aerodynamics/dirty-air': { title: `Dirty Air · ${BASE}`, description: 'Dirty air cost leaderboard.' },
  '/aerodynamics/lap-map': { title: `Lap Air Map · ${BASE}`, description: 'Per-lap air state timeline.' },
  '/drivers': { title: `Drivers · ${BASE}`, description: 'Era-adjusted driver ratings and analysis.' },
  '/constructors': { title: `Constructors · ${BASE}`, description: 'Structural pace and circuit interaction.' },
  '/deep-dives': { title: `Deep Dives · ${BASE}`, description: 'Sector and telemetry decomposition.' },
  '/query': { title: `Query Lab · ${BASE}`, description: 'DuckDB-Wasm SQL lab.' },
  '/ml': { title: `ML · ${BASE}`, description: 'Tyre degradation prediction model.' },
}

export function getPageMeta(pathname: string): PageMeta {
  return pageMeta[pathname] ?? { title: BASE, description: '' }
}
