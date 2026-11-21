import { SurvivalCurve } from '../../ui/charts'
import { compoundColor } from '../../ui/compound'
import type { SurvivalTransformResult } from './transform'
import { CLIFF_ESTIMATE_LABEL, formatOnsetRange } from '../shared/cliffEstimate'

interface Props {
  result: SurvivalTransformResult
}

export default function TyreCliffSurvivalChart({ result }: Props) {
  const {
    kmCurve,
    stintObservations,
    cliffOnset,
    fitDate,
    dataWindow,
    nStints,
  } = result

  return (
    <SurvivalCurve
      kmCurve={kmCurve}
      stintObservations={stintObservations}
      cliffOnsetLap={cliffOnset?.kind === 'measured' ? cliffOnset.lap : undefined}
      cliffOnsetEstimate={cliffOnset?.kind === 'estimate'
        ? {
            range: cliffOnset.range,
            text: cliffOnset.range ? `${formatOnsetRange(cliffOnset.range)}, ${CLIFF_ESTIMATE_LABEL}` : CLIFF_ESTIMATE_LABEL,
          }
        : undefined}
      fitDate={fitDate ?? undefined}
      dataWindow={dataWindow ?? undefined}
      nStints={nStints ?? undefined}
      height={420}
      curveColor={compoundColor(result.compound)}
    />
  )
}
