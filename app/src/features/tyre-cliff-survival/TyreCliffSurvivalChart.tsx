import { SurvivalCurve } from '../../ui/charts'
import type { SurvivalTransformResult } from './transform'

interface Props {
  result: SurvivalTransformResult
}

export default function TyreCliffSurvivalChart({ result }: Props) {
  const {
    kmCurve,
    stintObservations,
    cliffOnsetLap,
    fitDate,
    dataWindow,
    nStints,
  } = result

  return (
    <SurvivalCurve
      kmCurve={kmCurve}
      stintObservations={stintObservations}
      cliffOnsetLap={cliffOnsetLap ?? undefined}
      fitDate={fitDate ?? undefined}
      dataWindow={dataWindow ?? undefined}
      nStints={nStints ?? undefined}
      height={420}
    />
  )
}
