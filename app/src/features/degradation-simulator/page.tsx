// Feature 16-Degradation Simulator. The ONNX layer's anchor feature: the trained tyre models
// scored live in the browser as the user dials a stint. Inputs flow slider -> buildStintRows ->
// predictLaps (onnxruntime-web) -> transform -> fan + cliff bars + life gauge. A preset loads a
// real stint from the warehouse and overlays its observed next-lap jump against the prediction.

import { useEffect, useMemo, useState } from 'react'
import FeaturePage from '../../ui/layout/FeaturePage'
import DegradationSimulatorChart from './DegradationSimulatorChart'
import SimulatorControls from './SimulatorControls'
import { methodologyContent, methodologyHref } from './methodology'
import { useQuery } from '../../data/hooks/useQuery'
import { useFilters } from '../../state/FilterContext'
import { predictLaps } from '../../ml'
import type { LapPrediction } from '../../ml'
import { buildStintRows, DEFAULT_INPUTS } from './inputs'
import type { SimulatorInputs } from './inputs'
import { transform, toCsvRows, inputsFromStint, observedJumps } from './transform'
import './queries' // side-effect: register the preset queries
import type { StintOption, StintFeatureRow } from './queries'

export default function DegradationSimulatorPage() {
  const { season } = useFilters()
  const [inputs, setInputs] = useState<SimulatorInputs>(DEFAULT_INPUTS)
  const [selectedStintId, setSelectedStintId] = useState<string | null>(null)

  // ONNX scoring state (async; re-runs whenever the swept rows change).
  const [predictions, setPredictions] = useState<LapPrediction[]>([])
  const [scoring, setScoring] = useState(true)
  const [scoreError, setScoreError] = useState<Error | null>(null)

  // Preset: the pickable stints for the active season, and the chosen stint's rows.
  const { data: stintOptions } = useQuery<StintOption[]>('degradation-simulator.stint-options', { season })
  const { data: stintRows } = useQuery<StintFeatureRow[]>(
    'degradation-simulator.stint-rows',
    { season, stintId: selectedStintId },
    { enabled: selectedStintId !== null },
  )

  // When a stint loads (or changes), seed the inputs from it so sliders show a real baseline.
  useEffect(() => {
    if (selectedStintId && stintRows && stintRows.length) {
      const derived = inputsFromStint(stintRows)
      if (derived) setInputs(derived)
    }
  }, [selectedStintId, stintRows])

  // Observed overlay only applies while a stint is loaded AND the swept length matches it
  // (once the user perturbs stint_length the observed series no longer aligns lap-for-lap).
  const actuals = useMemo(() => {
    if (!selectedStintId || !stintRows) return []
    const obs = observedJumps(stintRows)
    return obs.length === inputs.stint_length ? obs : []
  }, [selectedStintId, stintRows, inputs.stint_length])

  // Re-score whenever the swept rows change.
  const rows = useMemo(() => buildStintRows(inputs), [inputs])
  useEffect(() => {
    let cancelled = false
    setScoring(true)
    setScoreError(null)
    predictLaps(rows)
      .then(preds => { if (!cancelled) { setPredictions(preds); setScoring(false) } })
      .catch(err => { if (!cancelled) { setScoreError(err instanceof Error ? err : new Error(String(err))); setScoring(false) } })
    return () => { cancelled = true }
  }, [rows])

  const result = useMemo(
    () => transform(predictions, inputs.current_lap, actuals),
    [predictions, inputs.current_lap, actuals],
  )

  const onSelectStint = (id: string | null) => {
    setSelectedStintId(id)
    if (id === null) setInputs(DEFAULT_INPUTS)
  }
  const onReset = () => { setSelectedStintId(null); setInputs(DEFAULT_INPUTS) }

  return (
    <FeaturePage
      title="Degradation Simulator"
      hook="The trained tyre-degradation models, running live in your browser. Dial a stint compound, fuel, dirty air, conditions and watch the predicted next-lap pace loss, cliff risk, and remaining tyre life update in real time via onnxruntime-web."
      badges={[
        {
          label: 'What It Means',
          content: 'Ask the model a what-if: how fast does this tyre fall off, and when does it cliff? Move a slider and the five XGBoost models re-score the whole stint instantly no server, all in the browser.',
        },
        {
          label: 'Why It Matters',
          content: 'This is the difference between a static dashboard and a model you can interrogate. Browser inference matches the trained boosters to 1e-5; the encoders, feature order, and post-processing are read from the manifest, never hard-coded.',
        },
        {
          label: "How It's Calculated",
          content: 'A 38-feature float32 vector per lap feeds three quantile regressors (p10/p50/p90 jump), a 4-class cliff classifier, and a stint-life regressor. Slider ranges are the p5-p95 of fct_cliff_prediction_features (2018-2024).',
        },
      ]}
      methodology={methodologyContent}
      methodologyHref={methodologyHref}
      provenance={{
        modelVersion: '1',
        datasetFingerprint: '3aff4559',
        dataWindow: 'ONNX parity 1.05e-5 (max abs) vs trained boosters',
      }}
      csvRows={result.fan.length ? toCsvRows(result) : undefined}
      csvFilename={`degradation-simulator-${inputs.constants.compound.toLowerCase()}.csv`}
      isLoading={scoring && predictions.length === 0}
      error={scoreError}
      isEmpty={false}
    >
      <div className="flex flex-col gap-6">
        <SimulatorControls
          inputs={inputs}
          onChange={setInputs}
          stintOptions={stintOptions ?? []}
          selectedStintId={selectedStintId}
          onSelectStint={onSelectStint}
          onReset={onReset}
        />
        <DegradationSimulatorChart result={result} />
      </div>
    </FeaturePage>
  )
}
