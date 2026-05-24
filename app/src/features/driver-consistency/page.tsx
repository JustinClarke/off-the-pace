import FeaturePage from '../../ui/layout/FeaturePage'
import DriverConsistencyChart from './DriverConsistencyChart'
import { methodologyContent, methodologyHref } from './methodology'
import { useQuery } from '../../data/hooks/useQuery'
import { useFilters } from '../../state/FilterContext'
import { transform, toCsvRows } from './transform'
import './queries' // side-effect: registers the named query in the registry
import type { DriverConsistencyRow } from './queries'

export default function DriverConsistencyPage() {
  const { season } = useFilters()
  const { data, isLoading, error } = useQuery<DriverConsistencyRow[]>(
    'driver-consistency.season',
    { season }
  )

  const result = data ? transform(data) : null

  return (
    <FeaturePage
      title="Driver Consistency"
      hook="How reliably does each driver extract the same pace the car is capable of? Lap-to-lap residual variance after removing car, tyre, dirty air, and conditions reveals whether a driver is dependably fast or brilliantly erratic."
      badges={[
        {
          label: 'What It Means',
          content: 'Who can you trust to deliver in qualifying conditions when it actually matters? Low variance with a negative mean is the gold standard.',
        },
        {
          label: 'Why It Matters',
          content: 'Driver skill residuals are estimated via the seven-term additive identity a CI-enforced causal decomposition, not correlation. The methodology drawer links to the full reference.',
        },
        {
          label: "How It's Calculated",
          content: 'Source: fct_driver_skill_features. Clean-lap filter applied (≥10 laps, no anomaly flags). Residuals are OLS skill proxies from the decomposition pipeline.',
        },
      ]}
      methodology={methodologyContent}
      methodologyHref={methodologyHref}
      provenance={{ dataWindow: '2018–2024', nObs: result?.points.length }}
      csvRows={result ? toCsvRows(result) : undefined}
      csvFilename={`driver-consistency-${season}.csv`}
      isLoading={isLoading}
      error={error}
      isEmpty={result?.points.length === 0}
    >
      {result && <DriverConsistencyChart result={result} />}
    </FeaturePage>
  )
}
