import { Waterfall } from '../../ui/charts'
import type { WaterfallResult } from './transform'

interface Props {
  results: WaterfallResult[]
  selectedDriver: string | null
}

export default function LapWaterfallChart({ results, selectedDriver }: Props) {
  const result = selectedDriver
    ? results.find(r => r.driverId === selectedDriver) ?? results[0]
    : results[0]

  if (!result) return null

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between text-xs text-muted">
        <span>
          {result.driverId} · {result.raceId} · {result.nLaps} clean laps averaged
        </span>
        <span className="font-mono">mean Δ vs base pace (s)</span>
      </div>
      <Waterfall
        bars={result.bars}
        closureGap={result.closureGap}
        yLabel="mean Δ (s)"
      />
    </div>
  )
}
