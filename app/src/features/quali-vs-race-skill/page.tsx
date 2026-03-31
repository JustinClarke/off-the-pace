import FeaturePage from '../../ui/layout/FeaturePage'
import QualiVsRaceChart from './QualiVsRaceChart'
import { methodologyContent, methodologyHref } from './methodology'
import { useQuery } from '../../data/hooks/useQuery'
import { useFilters } from '../../state/FilterContext'
import { transform, toCsvRows } from './transform'
import './queries'
import type { QualiVsRaceRow } from './queries'

export default function QualiVsRacePage() {
  const { season } = useFilters()
  const { data, isLoading, error } = useQuery<QualiVsRaceRow[]>(
    'quali-vs-race.season',
    { season }
  )

  const result = data ? transform(data) : null

  return (
    <FeaturePage
      title="Quali vs Race Skill"
      hook="Does a driver extract more from the car over a single lap or across a full race? Residual skill measured separately in qualifying and race sessions reveals whether a driver is a one-lap specialist or a race-craft expert."
      badges={[
        {
          label: 'What It Means',
          content: 'Both axes are residuals the pace a driver adds or loses beyond what the car, tyres, fuel, and conditions already explain. Negative = faster than expected. The diagonal marks equal skill across formats.',
        },
        {
          label: 'Why It Matters',
          content: 'Points left of the diagonal: the driver\'s qualifying residual is better (more negative) than their race residual. They excel under the pressure of a single flying lap.',
        },
        {
          label: "How It's Calculated",
          content: 'Points right of the diagonal: the driver builds pace over a stint, outperforming their qualifying residual across race distance. Tyre management and racecraft show up here.',
        },
      ]}
      methodology={methodologyContent}
      methodologyHref={methodologyHref}
      provenance={{ dataWindow: '2018–2024', nObs: result?.points.length }}
      csvRows={result ? toCsvRows(result) : undefined}
      csvFilename={`quali-vs-race-${season}.csv`}
      isLoading={isLoading}
      error={error}
      isEmpty={result?.points.length === 0}
    >
      {result && <QualiVsRaceChart result={result} />}
    </FeaturePage>
  )
}
