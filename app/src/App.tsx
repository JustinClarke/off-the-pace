// Browser router definition lazy-loads all route components; root layout wraps the data layout.
import { lazy, Suspense } from 'react'
import { createBrowserRouter } from 'react-router-dom'
import Root from './routes/_root'
import DataLayout from './routes/_data'
import Home from './routes/home'
import Spinner from './ui/feedback/Spinner'

function Loading() {
  return (
    <div className="flex items-center justify-center h-64 gap-3 text-muted text-sm">
      <Spinner />
    </div>
  )
}

function lazyRoute(factory: () => Promise<{ default: React.ComponentType }>) {
  const C = lazy(factory)
  return (
    <Suspense fallback={<Loading />}>
      <C />
    </Suspense>
  )
}

function Stub({ title }: { title: string }) {
  return (
    <div className="max-w-4xl mx-auto px-6 py-10">
      <h1 className="text-2xl font-bold tracking-tight mb-2">{title}</h1>
      <p className="text-muted text-sm">Feature coming soon.</p>
    </div>
  )
}

export const router = createBrowserRouter([
  {
    element: <Root />,
    children: [
      { path: '/', element: <Home /> },
      // Roadmap needs no data engine-keep it out of DataLayout so it renders instantly.
      { path: '/roadmap', element: lazyRoute(() => import('./routes/roadmap')) },
      {
        element: <DataLayout />,
        children: [
          // Races
          { path: '/races', element: <Stub title="Races" /> },
          { path: '/races/:raceId', element: lazyRoute(() => import('./routes/races/story')) },

          // Ghost Car
          { path: '/ghost-car', element: lazyRoute(() => import('./routes/ghost-car/index')) },
          { path: '/ghost-car/standings', element: lazyRoute(() => import('./features/ghost-race-standings')) },
          { path: '/ghost-car/lap-chart', element: lazyRoute(() => import('./routes/ghost-car/lap-chart')) },
          { path: '/ghost-car/championship', element: lazyRoute(() => import('./routes/ghost-car/championship')) },
          { path: '/ghost-car/hidden', element: lazyRoute(() => import('./routes/ghost-car/hidden-performance')) },

          // Lap Decomposition
          { path: '/lap-decomposition', element: lazyRoute(() => import('./routes/lap-decomposition/index')) },
          { path: '/lap-decomposition/waterfall', element: lazyRoute(() => import('./features/lap-waterfall')) },
          { path: '/lap-decomposition/race-lost', element: lazyRoute(() => import('./routes/lap-decomposition/race-lost')) },
          { path: '/lap-decomposition/sectors', element: lazyRoute(() => import('./routes/deep-dives/sector-decomposition')) },

          // Tyre & Strategy
          { path: '/tyre-strategy', element: lazyRoute(() => import('./routes/tyre-strategy/index')) },
          { path: '/tyre-strategy/survival', element: lazyRoute(() => import('./features/tyre-cliff-survival')) },
          { path: '/tyre-strategy/degradation', element: lazyRoute(() => import('./routes/tyre-strategy/degradation')) },
          { path: '/tyre-strategy/pit-gantt', element: lazyRoute(() => import('./features/pit-strategy')) },
          { path: '/tyre-strategy/recovery', element: lazyRoute(() => import('./features/tyre-recovery-forecast')) },
          { path: '/tyre-strategy/party-mode', element: lazyRoute(() => import('./features/party-mode')) },

          // Aero & Conditions (canonical paths; old /aerodynamics/* paths kept below as aliases)
          { path: '/aero', element: lazyRoute(() => import('./routes/aerodynamics/index')) },
          { path: '/aero/dirty-air', element: lazyRoute(() => import('./routes/aerodynamics/dirty-air')) },
          { path: '/aero/lap-map', element: lazyRoute(() => import('./routes/aerodynamics/lap-map')) },
          { path: '/aero/wind-altitude', element: <Stub title="Wind & Altitude" /> },
          { path: '/aero/track-evolution', element: lazyRoute(() => import('./features/track-evolution')) },
          { path: '/aero/field-pace', element: lazyRoute(() => import('./features/field-pace-curve')) },
          // Legacy aliases
          { path: '/aerodynamics', element: lazyRoute(() => import('./routes/aerodynamics/index')) },
          { path: '/aerodynamics/dirty-air', element: lazyRoute(() => import('./routes/aerodynamics/dirty-air')) },
          { path: '/aerodynamics/lap-map', element: lazyRoute(() => import('./routes/aerodynamics/lap-map')) },

          // Race Craft
          { path: '/race-craft', element: <Stub title="Race Craft" /> },
          { path: '/race-craft/overtakes', element: lazyRoute(() => import('./routes/race-craft/overtakes')) },
          { path: '/race-craft/stewarding', element: lazyRoute(() => import('./routes/race-craft/stewarding')) },
          { path: '/race-craft/drs', element: lazyRoute(() => import('./routes/race-craft/drs')) },
          { path: '/race-craft/pass-location', element: lazyRoute(() => import('./routes/race-craft/pass-location')) },
          { path: '/race-craft/race-control', element: lazyRoute(() => import('./routes/race-craft/race-control')) },

          // Drivers
          { path: '/drivers', element: lazyRoute(() => import('./routes/drivers/index')) },
          { path: '/drivers/ratings-timeline', element: lazyRoute(() => import('./features/era-ratings-timeline')) },
          { path: '/drivers/consistency', element: lazyRoute(() => import('./features/driver-consistency')) },
          { path: '/drivers/quali-vs-race', element: lazyRoute(() => import('./routes/drivers/quali-vs-race')) },
          { path: '/drivers/circuit-affinity', element: lazyRoute(() => import('./routes/drivers/circuit-affinity')) },
          { path: '/drivers/era-translator', element: lazyRoute(() => import('./routes/drivers/era-translator')) },
          { path: '/drivers/wet-race', element: lazyRoute(() => import('./routes/drivers/wet-race')) },
          { path: '/drivers/workload', element: lazyRoute(() => import('./routes/drivers/workload')) },
          { path: '/drivers/synthetic-teammate', element: lazyRoute(() => import('./features/synthetic-teammate')) },
          { path: '/drivers/dna-clusters', element: lazyRoute(() => import('./routes/drivers/dna-clusters')) },
          { path: '/drivers/career-twin', element: lazyRoute(() => import('./routes/drivers/career-twin')) },
          { path: '/drivers/corner-skill', element: lazyRoute(() => import('./features/corner-phase-skill')) },
          { path: '/drivers/racing-line', element: lazyRoute(() => import('./routes/drivers/racing-line')) },

          // Constructors
          { path: '/constructors', element: lazyRoute(() => import('./routes/constructors/index')) },
          { path: '/constructors/structural', element: lazyRoute(() => import('./routes/constructors/structural-pace')) },
          { path: '/constructors/circuits', element: lazyRoute(() => import('./routes/constructors/circuit-interaction')) },

          // Energy & Telemetry (deep-dives telemetry migrated here)
          { path: '/energy', element: <Stub title="Energy & Telemetry" /> },
          { path: '/energy/telemetry-fingerprint', element: lazyRoute(() => import('./routes/deep-dives/telemetry-fingerprint')) },
          { path: '/energy/management-map', element: lazyRoute(() => import('./routes/energy/management-map')) },
          { path: '/energy/ers-short-shift', element: lazyRoute(() => import('./routes/energy/ers-short-shift')) },
          { path: '/energy/corner-taxonomy', element: lazyRoute(() => import('./routes/energy/corner-taxonomy')) },
          // Legacy deep-dives alias
          { path: '/deep-dives', element: lazyRoute(() => import('./routes/deep-dives/index')) },
          { path: '/deep-dives/sectors', element: lazyRoute(() => import('./routes/deep-dives/sector-decomposition')) },
          { path: '/deep-dives/telemetry', element: lazyRoute(() => import('./routes/deep-dives/telemetry-fingerprint')) },

          // The Machine (ML)
          { path: '/ml', element: lazyRoute(() => import('./routes/ml/index')) },
          { path: '/ml/blind-test', element: lazyRoute(() => import('./features/blind-test-scoreboard')) },
          { path: '/ml/simulator', element: lazyRoute(() => import('./features/degradation-simulator')) },
          { path: '/ml/metrics', element: lazyRoute(() => import('./features/model-metrics')) },
          { path: '/ml/edge-cases', element: lazyRoute(() => import('./routes/ml/edge-cases')) },

          // Query Lab
          { path: '/query', element: lazyRoute(() => import('./routes/query')) },

          // Data Quality
          { path: '/data-quality', element: lazyRoute(() => import('./features/data-quality-audit')) },
        ],
      },
    ],
  },
])
