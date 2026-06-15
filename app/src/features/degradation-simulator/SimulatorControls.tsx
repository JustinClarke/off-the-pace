// The slider/select panel that drives the simulator. Emits a new SimulatorInputs on every change;
// the page re-scores via the ONNX layer. The "load a real stint" preset is handled by the page and
// surfaced here as a selector plus a reset-to-defaults affordance.

import { useMemo, useState } from 'react'
import {
  SLIDERS, COMPOUND_OPTIONS, AIR_STATE_OPTIONS, CONSTRUCTOR_OPTIONS,
  compoundConstants,
} from './inputs'
import type { SimulatorInputs } from './inputs'
import type { StintOption, CircuitOption } from './queries'

interface Props {
  inputs: SimulatorInputs
  onChange: (next: SimulatorInputs) => void
  stintOptions: StintOption[]
  selectedStintId: string | null
  onSelectStint: (stintId: string | null) => void
  onReset: () => void
  circuitOptions: CircuitOption[]
  circuitId: string | null
  era: string
  onSelectCircuit: (id: string | null) => void
  onSelectEra: (era: string) => void
}

const ERA_LABELS: Record<string, string> = {
  pre2022: 'Pre-2022 (last-gen aero)',
  post2022: '2022+ (ground-effect)',
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

// A titled block within the console: a small uppercase heading with a hairline rule, then content.
function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex items-center gap-2">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-muted">{label}</span>
        <span aria-hidden className="h-px flex-1 bg-border" />
      </div>
      {children}
    </div>
  )
}

// A labelled select/field stacked vertically (rail-friendly).
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-[11px] text-muted">{label}</label>
      {children}
    </div>
  )
}

export default function SimulatorControls({
  inputs, onChange, stintOptions, selectedStintId, onSelectStint, onReset,
  circuitOptions, circuitId, era, onSelectCircuit, onSelectEra,
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
    <div className="flex flex-col gap-5 rounded-xl border border-border bg-white/[0.02] p-4">
      <div className="flex items-center gap-2">
        <span aria-hidden className="h-3.5 w-[3px] rounded-full bg-[rgb(var(--color-accent))]" />
        <h2 className="text-xs font-semibold uppercase tracking-widest text-muted">Simulator inputs</h2>
      </div>

      {/* Circuit + era picker always available; anchors the absolute lap time + history envelope */}
      <Section label="Circuit & era">
        <select
          className={SELECT_CLS + ' w-full'}
          value={circuitId ?? ''}
          onChange={e => onSelectCircuit(e.target.value || null)}
        >
          <option value="">Generic circuit</option>
          {circuitOptions.map(o => (
            <option key={o.circuit_id} value={o.circuit_id}>{o.circuit_name}</option>
          ))}
        </select>
        <select
          className={SELECT_CLS + ' w-full'}
          value={era}
          onChange={e => onSelectEra(e.target.value)}
        >
          {Object.entries(ERA_LABELS).map(([v, l]) => (
            <option key={v} value={v}>{l}</option>
          ))}
        </select>
        {circuitId && (
          <p className="text-[11px] leading-snug text-muted/70">
            Anchored to historical fresh-tyre pace at {inputs.circuit_name || 'this circuit'} ·
            fuel {inputs.weight_penalty_factor.toFixed(3)} s/kg, burn{' '}
            {inputs.fuel_consumption_rate_kg_per_lap.toFixed(2)} kg/lap.
          </p>
        )}
      </Section>

      {/* Cascading preset selectors */}
      <Section label="Load a real stint">
        <select
          className={SELECT_CLS + ' w-full'}
          value={selectedRaceId}
          onChange={e => handleGpChange(e.target.value)}
        >
          <option value="">Grand Prix…</option>
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
          <option value="">Driver…</option>
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
          <option value="">Stint…</option>
          {stintNumberOptions.map(o => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <div className="flex items-center justify-between gap-2">
          {selectedStintId
            ? <p className="text-[11px] leading-snug text-muted/70">Sliders show the loaded stint drag any to run a what-if.</p>
            : <span />}
          <button
            onClick={handleReset}
            className="shrink-0 rounded border border-border px-3 py-1 text-xs text-muted transition-colors hover:border-[rgb(var(--color-accent))] hover:text-[rgb(var(--color-text))]"
          >
            Reset
          </button>
        </div>
      </Section>

      {/* Compound + categoricals */}
      <Section label="Tyre & car">
        <Field label="Compound">
          <select
            className={SELECT_CLS + ' w-full'}
            value={inputs.constants.compound}
            onChange={e => set({ constants: compoundConstants(e.target.value) })}
          >
            {COMPOUND_OPTIONS.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </Field>
        <Field label="Constructor">
          <select
            className={SELECT_CLS + ' w-full'}
            value={inputs.constructor_id}
            onChange={e => set({ constructor_id: e.target.value })}
          >
            {CONSTRUCTOR_OPTIONS.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </Field>
        <Field label="Air state">
          <select
            className={SELECT_CLS + ' w-full'}
            value={inputs.air_state_dominant}
            onChange={e => set({ air_state_dominant: e.target.value })}
          >
            {AIR_STATE_OPTIONS.map(a => <option key={a} value={a}>{AIR_STATE_LABELS[a]}</option>)}
          </select>
        </Field>
        <label className="flex cursor-pointer items-center gap-2 py-0.5 text-sm">
          <input
            type="checkbox"
            className="accent-[rgb(var(--color-accent))]"
            checked={inputs.is_rain_lap}
            onChange={e => set({ is_rain_lap: e.target.checked })}
          />
          <span className="text-muted">Rain lap</span>
        </label>
      </Section>

      {/* Numeric sliders */}
      <Section label="Stint & conditions">
        {SLIDERS.map(s => {
          const value = inputs[s.key] as number
          return (
            <div key={s.key} className="flex flex-col gap-1.5">
              <div className="flex items-baseline justify-between gap-2">
                <label className="text-[11px] text-muted">{s.label}</label>
                <span className="rounded bg-white/[0.05] px-1.5 py-0.5 font-mono text-[11px] tabular-nums text-[rgb(var(--color-text))]">
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
                className="w-full cursor-pointer accent-[rgb(var(--color-accent))]"
              />
            </div>
          )
        })}
      </Section>
    </div>
  )
}
