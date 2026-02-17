// The slider/select panel that drives the simulator. Emits a new SimulatorInputs on every change;
// the page re-scores via the ONNX layer. The "load a real stint" preset is handled by the page and
// surfaced here as a selector plus a reset-to-defaults affordance.

import { useMemo, useState } from 'react'
import {
  SLIDERS, COMPOUND_OPTIONS, AIR_STATE_OPTIONS, CONSTRUCTOR_OPTIONS,
  compoundConstants,
} from './inputs'
import type { SimulatorInputs } from './inputs'
import type { StintOption } from './queries'

interface Props {
  inputs: SimulatorInputs
  onChange: (next: SimulatorInputs) => void
  stintOptions: StintOption[]
  selectedStintId: string | null
  onSelectStint: (stintId: string | null) => void
  onReset: () => void
}

const AIR_STATE_LABELS: Record<string, string> = {
  free_air: 'Free air', dirty_air: 'Dirty air', drs_train: 'DRS train', tow_zone: 'Tow zone',
}

const SELECT_CLS = `
  bg-[rgb(var(--color-bg))] border border-[rgb(var(--color-border))] rounded
  px-2 py-1.5 text-sm text-[rgb(var(--color-text))]
  focus:outline-none focus:ring-1 focus:ring-[rgb(var(--color-accent))]
  disabled:opacity-40 cursor-pointer
`.trim()

export default function SimulatorControls({
  inputs, onChange, stintOptions, selectedStintId, onSelectStint, onReset,
}: Props) {
  const set = (patch: Partial<SimulatorInputs>) => onChange({ ...inputs, ...patch })

  // Cascading preset state: GP → driver → stint number
  const [selectedRaceId, setSelectedRaceId] = useState<string>('')
  const [selectedDriverId, setSelectedDriverId] = useState<string>('')

  const gpOptions = useMemo(() => {
    const seen = new Set<string>()
    const out: { value: string; label: string }[] = []
    for (const s of stintOptions) {
      if (!seen.has(s.race_id)) {
        seen.add(s.race_id)
        out.push({ value: s.race_id, label: s.circuit_name })
      }
    }
    return out
  }, [stintOptions])

  const driverOptions = useMemo(() => {
    if (!selectedRaceId) return []
    const seen = new Set<string>()
    const out: { value: string; label: string }[] = []
    for (const s of stintOptions) {
      if (s.race_id === selectedRaceId && !seen.has(s.driver_id)) {
        seen.add(s.driver_id)
        out.push({ value: s.driver_id, label: s.driver_id })
      }
    }
    return out
  }, [stintOptions, selectedRaceId])

  const stintNumberOptions = useMemo(() => {
    if (!selectedRaceId || !selectedDriverId) return []
    return stintOptions
      .filter(s => s.race_id === selectedRaceId && s.driver_id === selectedDriverId)
      .map(s => ({
        value: s.stint_id,
        label: `Stint ${s.stint_number} · ${s.compound} · ${s.stint_length} laps`,
      }))
  }, [stintOptions, selectedRaceId, selectedDriverId])

  const handleGpChange = (raceId: string) => {
    setSelectedRaceId(raceId)
    setSelectedDriverId('')
    onSelectStint(null)
  }

  const handleDriverChange = (driverId: string) => {
    setSelectedDriverId(driverId)
    onSelectStint(null)
    // Auto-select if only one stint for this driver
    const options = stintOptions.filter(s => s.race_id === selectedRaceId && s.driver_id === driverId)
    if (options.length === 1) onSelectStint(options[0].stint_id)
  }

  const handleStintChange = (stintId: string) => {
    onSelectStint(stintId || null)
  }

  const handleReset = () => {
    setSelectedRaceId('')
    setSelectedDriverId('')
    onReset()
  }

  return (
    <div className="flex flex-col gap-5 border border-[rgb(var(--color-border))] rounded-lg p-5 bg-white/[0.02]">
      {/* Cascading preset selectors */}
      <div className="flex flex-col gap-2">
        <label className="text-xs font-semibold uppercase tracking-wide text-muted">Load a real stint</label>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          <select
            className={SELECT_CLS + ' w-full'}
            value={selectedRaceId}
            onChange={e => handleGpChange(e.target.value)}
          >
            <option value="">— Grand Prix —</option>
            {gpOptions.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>

          <select
            className={SELECT_CLS + ' w-full'}
            value={selectedDriverId}
            onChange={e => handleDriverChange(e.target.value)}
            disabled={!selectedRaceId}
          >
            <option value="">— Driver —</option>
            {driverOptions.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>

          <select
            className={SELECT_CLS + ' w-full'}
            value={selectedStintId ?? ''}
            onChange={e => handleStintChange(e.target.value)}
            disabled={!selectedDriverId || stintNumberOptions.length === 0}
          >
            <option value="">— Stint —</option>
            {stintNumberOptions.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>

        <div className="flex items-center justify-between">
          {selectedStintId && (
            <p className="text-xs text-muted/70">Sliders show the loaded stint drag any to run a what-if.</p>
          )}
          <button
            onClick={handleReset}
            className="ml-auto text-xs px-3 py-1 rounded border border-[rgb(var(--color-border))] text-muted hover:text-[rgb(var(--color-text))] hover:border-[rgb(var(--color-accent))] transition-colors"
          >
            Reset
          </button>
        </div>
      </div>

      {/* Compound + categoricals */}
      <div className="grid grid-cols-2 gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted">Compound</label>
          <select
            className={SELECT_CLS + ' w-full'}
            value={inputs.constants.compound}
            onChange={e => set({ constants: compoundConstants(e.target.value) })}
          >
            {COMPOUND_OPTIONS.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted">Constructor</label>
          <select
            className={SELECT_CLS + ' w-full'}
            value={inputs.constructor_id}
            onChange={e => set({ constructor_id: e.target.value })}
          >
            {CONSTRUCTOR_OPTIONS.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted">Air state</label>
          <select
            className={SELECT_CLS + ' w-full'}
            value={inputs.air_state_dominant}
            onChange={e => set({ air_state_dominant: e.target.value })}
          >
            {AIR_STATE_OPTIONS.map(a => <option key={a} value={a}>{AIR_STATE_LABELS[a]}</option>)}
          </select>
        </div>
        <div className="flex flex-col gap-1 justify-end">
          <label className="flex items-center gap-2 text-sm cursor-pointer py-1.5">
            <input
              type="checkbox"
              checked={inputs.is_rain_lap}
              onChange={e => set({ is_rain_lap: e.target.checked })}
            />
            <span className="text-muted">Rain lap</span>
          </label>
        </div>
      </div>

      {/* Numeric sliders */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-5 gap-y-3">
        {SLIDERS.map(s => {
          const value = inputs[s.key] as number
          return (
            <div key={s.key} className="flex flex-col gap-1">
              <div className="flex items-baseline justify-between">
                <label className="text-xs text-muted">{s.label}</label>
                <span className="text-xs font-mono text-[rgb(var(--color-text))]">
                  {s.step < 1 ? value.toFixed(2) : value}{s.unit ? ` ${s.unit}` : ''}
                </span>
              </div>
              <input
                type="range"
                min={s.min}
                max={s.max}
                step={s.step}
                value={value}
                onChange={e => set({ [s.key]: Number(e.target.value) } as Partial<SimulatorInputs>)}
                className="w-full accent-[rgb(var(--color-accent))]"
              />
            </div>
          )
        })}
      </div>
    </div>
  )
}
