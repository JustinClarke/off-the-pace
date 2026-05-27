// Feature 16 Degradation Simulator. The headline is an absolute lap time built from three
// additive pieces: a per-circuit/era/compound fresh-tyre anchor + a deterministic fuel term +
// the isotonic-fitted observed tyre degradation × a physics modulation factor M (dirty-air bump
// + compound-window temp penalty). The monotone fit guarantees old rubber only adds time; M is
// constant across the stint so monotonicity is preserved at all slider positions. The ONNX models
// (jump fan, cliff risk, remaining life) are unchanged. The Fuel slider moves the curve only via
// the deterministic term; dirty-air and temp move it modestly by design (~0.1–0.3s).

import { useEffect, useMemo, useRef, useState } from 'react'
import FeaturePage from '../../ui/layout/FeaturePage'
import DegradationSimulatorChart from './DegradationSimulatorChart'
import SimulatorControls from './SimulatorControls'
import { methodologyContent, methodologyHref } from './methodology'
import { useQuery } from '../../data/hooks/useQuery'
import { useFilters } from '../../state/FilterContext'
import { loadManifest } from '../../data/manifest'
import { predictLaps } from '../../ml'
import type { LapPrediction, FeatureRow } from '../../ml'
import { buildStintRows, DEFAULT_INPUTS } from './inputs'
import type { SimulatorInputs } from './inputs'
import { transform, toCsvRows, inputsFromStint, observedJumps } from './transform'
import type { RecomposeOptions } from './transform'
import './queries' // side-effect: register the preset + circuit queries
import type {
  StintOption, StintFeatureRow, CircuitOption, CircuitCompoundConstants, HistoryEnvelopeRow,
} from './queries'

// The slider state that actually shapes the scored sweep everything except current_lap, which
// only moves the gauge/cliff marker (transform reads it) and is not a model feature. Used to tell
// a pristine loaded stint from a perturbed one so we know whether to score real rows.
const sweepKey = (i: SimulatorInputs) => JSON.stringify({ ...i, current_lap: 0 })

const num = (v: unknown, d: number) => {
  if (v === null || v === undefined) return d
  const n = Number(v)
  return Number.isFinite(n) ? n : d
}

export default function DegradationSimulatorPage() {
  const { season } = useFilters()
  const [inputs, setInputs] = useState<SimulatorInputs>(DEFAULT_INPUTS)
  const [selectedStintId, setSelectedStintId] = useState<string | null>(null)
  const [circuitId, setCircuitId] = useState<string | null>(null)
  const [era, setEra] = useState<string>('post2022')
  const [eraBoundary, setEraBoundary] = useState<number>(2022)
  useEffect(() => {
    loadManifest().then(m => {
      if (m.stats?.era_boundary) setEraBoundary(m.stats.era_boundary)
    }).catch(() => {})
  }, [])

  // ONNX scoring state (async; re-runs whenever the swept rows change).
  const [predictions, setPredictions] = useState<LapPrediction[]>([])
  const [scoring, setScoring] = useState(true)
  const [scoreError, setScoreError] = useState<Error | null>(null)

  // Circuit catalogue + the chosen circuit's compound constants and historical envelope.
  const { data: circuitOptions } = useQuery<CircuitOption[]>('degradation-simulator.circuit-options', {})
  const compound = inputs.constants.compound
  const { data: circuitConst } = useQuery<CircuitCompoundConstants[]>(
    'degradation-simulator.circuit-compound-constants',
    { circuitId, compound, era },
    { enabled: circuitId !== null },
  )
  const { data: history } = useQuery<HistoryEnvelopeRow[]>(
    'degradation-simulator.history-envelope',
    { circuitId, era, compound },
    { enabled: circuitId !== null },
  )

  // Preset: the pickable stints for the active season, and the chosen stint's rows.
  const { data: stintOptions } = useQuery<StintOption[]>('degradation-simulator.stint-options', { season })
  const { data: stintRows } = useQuery<StintFeatureRow[]>(
    'degradation-simulator.stint-rows',
    { season, stintId: selectedStintId },
    { enabled: selectedStintId !== null },
  )

  // Default the circuit picker to the first circuit so the absolute recomposition is live on first
  // paint (the picker is always available, per spec). Skipped once a stint sets the circuit.
  useEffect(() => {
    if (circuitId === null && circuitOptions && circuitOptions.length && !selectedStintId) {
      setCircuitId(circuitOptions[0].circuit_id)
    }
  }, [circuitOptions, circuitId, selectedStintId])

  // When a stint loads (or changes), seed the inputs from it AND point the circuit/era at its venue
  // so the historical envelope and anchor match the loaded stint.
  useEffect(() => {
    if (selectedStintId && stintRows && stintRows.length) {
      const derived = inputsFromStint(stintRows)
      if (derived) setInputs(derived)
      const opt = stintOptions?.find(s => s.stint_id === selectedStintId)
      if (opt?.circuit_id) {
        setCircuitId(opt.circuit_id)
        setEra(opt.season >= eraBoundary ? 'post2022' : 'pre2022')
      }
    }
  }, [selectedStintId, stintRows, stintOptions, eraBoundary])

  // Merge the chosen circuit's fitted compound constants + circuit physics into the inputs. Guarded
  // by a signature so user slider edits to other fields aren't clobbered and we don't loop.
  const appliedSig = useRef('')
  useEffect(() => {
    if (!circuitId || !circuitConst || !circuitConst.length) return
    const sig = `${circuitId}|${era}|${compound}`
    if (appliedSig.current === sig) return
    appliedSig.current = sig
    const c = circuitConst[0]
    const opt = circuitOptions?.find(o => o.circuit_id === circuitId)
    setInputs(prev => ({
      ...prev,
      circuit_id: circuitId,
      circuit_name: opt?.circuit_name ?? '',
      era,
      weight_penalty_factor: num(c.weight_penalty_factor, prev.weight_penalty_factor),
      fuel_consumption_rate_kg_per_lap: num(c.fuel_consumption_rate_kg_per_lap, prev.fuel_consumption_rate_kg_per_lap),
      track_energy_index: num(c.track_energy_index, prev.track_energy_index),
      circuit_abrasiveness_index: num(c.abrasiveness_index, prev.circuit_abrasiveness_index),
      constants: {
        ...prev.constants,
        compound,
        compound_grip_peak: num(c.compound_grip_peak, prev.constants.compound_grip_peak),
        compound_wear_gradient: num(c.compound_wear_gradient, prev.constants.compound_wear_gradient),
        compound_optimal_temp_low: num(c.compound_optimal_temp_low, prev.constants.compound_optimal_temp_low),
        compound_optimal_temp_high: num(c.compound_optimal_temp_high, prev.constants.compound_optimal_temp_high),
        compound_cliff_onset_laps: num(c.compound_cliff_onset_laps, prev.constants.compound_cliff_onset_laps),
        compound_cliff_severity: num(c.compound_cliff_severity, prev.constants.compound_cliff_severity),
      },
    }))
  }, [circuitId, era, compound, circuitConst, circuitOptions])

  // Observed overlay only applies while a stint is loaded AND the swept length matches it.
  const actuals = useMemo(() => {
    if (!selectedStintId || !stintRows) return []
    const obs = observedJumps(stintRows)
    return obs.length === inputs.stint_length ? obs : []
  }, [selectedStintId, stintRows, inputs.stint_length])

  // Re-score whenever the swept rows change. A pristine loaded stint scores its real per-lap rows
  // (full 41-wide v3 vector with telemetry); perturbing any composition slider drops to the
  // synthetic sweep (those laps are hypothetical, so the 11 telemetry cols pass as NaN).
  const rows = useMemo<FeatureRow[]>(() => {
    if (selectedStintId && stintRows && stintRows.length) {
      const baseline = inputsFromStint(stintRows)
      if (baseline && sweepKey(inputs) === sweepKey(baseline)) {
        return stintRows as unknown as FeatureRow[]
      }
    }
    return buildStintRows(inputs)
  }, [selectedStintId, stintRows, inputs])
  useEffect(() => {
    let cancelled = false
    setScoring(true)
    setScoreError(null)
    predictLaps(rows)
      .then(preds => { if (!cancelled) { setPredictions(preds); setScoring(false) } })
      .catch(err => { if (!cancelled) { setScoreError(err instanceof Error ? err : new Error(String(err))); setScoring(false) } })
    return () => { cancelled = true }
  }, [rows])

  // The recomposition options: historical anchor + deterministic fuel + isotonic envelope + modulation.
  const recompose = useMemo<RecomposeOptions | undefined>(() => {
    if (!history || !history.length) return undefined
    const hist: HistoryEnvelopeRow[] = history.map(h => ({
      lap_in_stint: num(h.lap_in_stint, 0),
      n_observations: num(h.n_observations, 0),
      ref_green_pace_s: num(h.ref_green_pace_s, 0),
      obs_fuel_removed_pace_p10_s: num(h.obs_fuel_removed_pace_p10_s, 0),
      obs_fuel_removed_pace_p50_s: num(h.obs_fuel_removed_pace_p50_s, 0),
      obs_fuel_removed_pace_p90_s: num(h.obs_fuel_removed_pace_p90_s, 0),
      obs_deg_from_fresh_p10_s: num(h.obs_deg_from_fresh_p10_s, 0),
      obs_deg_from_fresh_p50_s: num(h.obs_deg_from_fresh_p50_s, 0),
      obs_deg_from_fresh_p90_s: num(h.obs_deg_from_fresh_p90_s, 0),
      obs_deg_from_fresh_p10_mono_s: h.obs_deg_from_fresh_p10_mono_s != null ? num(h.obs_deg_from_fresh_p10_mono_s, 0) : null,
      obs_deg_from_fresh_p50_mono_s: h.obs_deg_from_fresh_p50_mono_s != null ? num(h.obs_deg_from_fresh_p50_mono_s, 0) : null,
      obs_deg_from_fresh_p90_mono_s: h.obs_deg_from_fresh_p90_mono_s != null ? num(h.obs_deg_from_fresh_p90_mono_s, 0) : null,
      dirty_air_deg_mult: num(h.dirty_air_deg_mult, 1.0),
      temp_headroom_c: num(h.temp_headroom_c, 8.0),
      temp_penalty_s_per_deg: num(h.temp_penalty_s_per_deg, 0.01),
    }))
    return {
      refGreenPaceS: hist[0].ref_green_pace_s,
      fuelStartKg: inputs.fuel_mass_kg,
      fuelConsumptionRateKgPerLap: inputs.fuel_consumption_rate_kg_per_lap,
      weightPenaltyFactor: inputs.weight_penalty_factor,
      history: hist,
      dirtyAirShare: inputs.dirty_air_share_lap,
      ambientTempDelta: inputs.ambient_temp_delta,
      analyticalDegRatePerLap: inputs.constants.expected_degradation_rate_s_per_lap,
    }
  }, [history, inputs.fuel_mass_kg, inputs.fuel_consumption_rate_kg_per_lap, inputs.weight_penalty_factor,
      inputs.dirty_air_share_lap, inputs.ambient_temp_delta, inputs.constants.expected_degradation_rate_s_per_lap])

  const result = useMemo(
    () => transform(predictions, inputs.current_lap, actuals, recompose),
    [predictions, inputs.current_lap, actuals, recompose],
  )

  const onSelectStint = (id: string | null) => {
    setSelectedStintId(id)
    if (id === null) setInputs(DEFAULT_INPUTS)
  }
  const onReset = () => {
    setSelectedStintId(null)
    setInputs(DEFAULT_INPUTS)
    appliedSig.current = ''
    if (circuitOptions && circuitOptions.length) setCircuitId(circuitOptions[0].circuit_id)
  }

  const onSelectCircuit = (id: string | null) => {
    appliedSig.current = ''
    setCircuitId(id)
  }
  const onSelectEra = (e: string) => {
    appliedSig.current = ''
    setEra(e)
  }

  return (
    <FeaturePage
      wide
      title="Degradation Simulator"
      hook="The trained tyre-degradation models, running live in your browser anchored to observed reality. Pick a circuit and era, dial fuel, compound, dirty air and conditions, and watch the projected lap time, tyre degradation, cliff risk, and remaining tyre life update instantly via onnxruntime-web."
      badges={[
        {
          label: 'What It Means',
          content: 'The headline is the observed tyre degradation for this circuit, era and compound monotone-fitted so old rubber only ever adds time scaled by your dirty-air and temperature conditions, then anchored to the historical fresh-tyre pace with the deterministic fuel term on top.',
        },
        {
          label: 'Why It Matters',
          content: 'The raw observed median is non-monotone (survivorship bias collapses the late-stint tail), and ONNX jump-integration was a category error. The isotonic fit (MAE ≤ 0.5s vs raw data) corrects both and stays faithful to what actually happened. The dirty-air and temp sliders move it modestly by design (~0.1–0.3s) because that is what the data supports.',
        },
        {
          label: "How It's Calculated",
          content: 'net(k) = ref_green_pace + weight_penalty × fuel(k) + isotonic_p50(k) × M, where M = clamp(1 + air_bump·𝟙[dirty_air] + temp_penalty·max(0, ΔT−headroom), 1.0, 1.5). The ONNX models (fan / cliff risk / remaining life) are unchanged; the headline no longer integrates their jumps.',
        },
      ]}
      methodology={methodologyContent}
      methodologyHref={methodologyHref}
      provenance={{
        modelVersion: '3',
        datasetFingerprint: 'b8a37b7c',
        dataWindow: 'ONNX parity 7.6e-6 (max abs) vs trained boosters',
      }}
      csvRows={result.fan.length ? toCsvRows(result) : undefined}
      csvFilename={`degradation-simulator-${inputs.constants.compound.toLowerCase()}.csv`}
      isLoading={scoring && predictions.length === 0}
      error={scoreError}
      isEmpty={false}
    >
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start">
        <div className="lg:sticky lg:top-4 lg:w-[330px] lg:shrink-0">
          <SimulatorControls
            inputs={inputs}
            onChange={setInputs}
            stintOptions={stintOptions ?? []}
            selectedStintId={selectedStintId}
            onSelectStint={onSelectStint}
            onReset={onReset}
            circuitOptions={circuitOptions ?? []}
            circuitId={circuitId}
            era={era}
            onSelectCircuit={onSelectCircuit}
            onSelectEra={onSelectEra}
          />
        </div>
        <div className="min-w-0 flex-1">
          <DegradationSimulatorChart result={result} />
        </div>
      </div>
    </FeaturePage>
  )
}
