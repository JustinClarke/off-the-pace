// The control panel that drives the simulator, organised into two explicit modes so each user job
// gets an uncluttered view:
//   • Replay load a real stint (GP → driver → stint) and watch what actually happened. No
//                sliders: a pristine stint scores its real per-lap telemetry, and editing any lever
//                would silently drop to the synthetic sweep, so we don't expose them here.
//   • Scenario build a hypothetical from the headline levers (compound, stint length, fuel,
//                dirty-air), with the finer conditions behind an Advanced drawer.
// Circuit + era are shared context above the tabs (they anchor the absolute lap time in both modes).
// The current-lap playhead is NOT here it's a scrubber on the chart (it isn't a model feature).

import { useMemo, useState } from 'react'
import {
  PRIMARY_SLIDERS, ADVANCED_SLIDERS, COMPOUND_OPTIONS, AIR_STATE_OPTIONS, CONSTRUCTOR_OPTIONS,
  compoundConstants,
} from './inputs'

import type { SimulatorInputs, SliderSpec } from './inputs'
import type { StintOption, CircuitOption } from './queries'

export type SimulatorMode = 'replay' | 'scenario'

interface Props {
  inputs: SimulatorInputs
  onChange: (next: SimulatorInputs) => void
  mode: SimulatorMode
  onModeChange: (mode: SimulatorMode) => void
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

// One labelled range row, used for both the primary levers and the advanced drawer.
function Slider({ spec, value, onChange }: { spec: SliderSpec; value: number; onChange: (v: number) => void }) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between gap-2">
        <label className="text-[11px] text-muted">{spec.label}</label>
        <span className="rounded bg-white/[0.05] px-1.5 py-0.5 font-mono text-[11px] tabular-nums text-[rgb(var(--color-text))]">
          {spec.step < 1 ? value.toFixed(2) : value}{spec.unit ? ` ${spec.unit}` : ''}
        </span>
      </div>
      <input
        type="range"
        min={spec.min}
        max={spec.max}
        step={spec.step}
        value={value}
        onChange={e => onChange(Number(e.target.value))}
        className="w-full cursor-pointer accent-[rgb(var(--color-accent))]"
      />
    </div>
  )
}

export default function SimulatorControls({
  inputs, onChange, mode, onModeChange, stintOptions, selectedStintId, onSelectStint, onReset,
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

  const loadedStint = useMemo(
    () => stintOptions.find(s => s.stint_id === selectedStintId) ?? null,
    [stintOptions, selectedStintId],
  )

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

      {/* Mode switch: Replay (load real data) vs Scenario (build a what-if). Reset is global. */}
      <div className="flex items-center justify-between gap-2">
        <div role="tablist" aria-label="Simulator mode" className="inline-flex rounded-lg border border-border bg-[rgb(var(--color-bg))] p-0.5">
          {(['replay', 'scenario'] as const).map(m => (
            <button
              key={m}
              role="tab"
              aria-selected={mode === m}
              onClick={() => onModeChange(m)}
              className={[
                'rounded-md px-3 py-1 text-xs font-medium capitalize transition-colors',
                mode === m
                  ? 'bg-[rgb(var(--color-accent)/0.15)] text-[rgb(var(--color-text))]'
                  : 'text-muted hover:text-[rgb(var(--color-text))]',
              ].join(' ')}
            >
              {m}
            </button>
          ))}
        </div>
        <button
          onClick={handleReset}
          className="shrink-0 rounded border border-border px-3 py-1 text-xs text-muted transition-colors hover:border-[rgb(var(--color-accent))] hover:text-[rgb(var(--color-text))]"
        >
          Reset
        </button>
      </div>

      {mode === 'replay' ? (
        // ── Replay: pick a real stint, then read what happened. No sliders (see file header). ──
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

          {loadedStint ? (
            <div className="flex flex-col gap-2.5 rounded-lg border border-border bg-white/[0.02] p-3">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-[11px] text-muted">
                <span className="font-medium text-[rgb(var(--color-text))]">{loadedStint.driver_id}</span>
                <span>{loadedStint.compound}</span>
                <span>{loadedStint.stint_length} laps</span>
                <span>{inputs.fuel_mass_kg.toFixed(0)} kg start</span>
              </div>
              <p className="text-[11px] leading-snug text-muted/70">
                Scoring this stint's real per-lap telemetry. Scrub the current lap on the chart.
              </p>
              <button
                onClick={() => onModeChange('scenario')}
                className="self-start rounded border border-border px-2.5 py-1 text-xs text-muted transition-colors hover:border-[rgb(var(--color-accent))] hover:text-[rgb(var(--color-text))]"
              >
                Tweak this stint in Scenario →
              </button>
            </div>
          ) : (
            <p className="text-[11px] leading-snug text-muted/70">
              Pick a Grand Prix, driver and stint to replay it. Switch to Scenario to build a hypothetical instead.
            </p>
          )}
        </Section>
      ) : (
        // ── Scenario: the headline levers, with finer conditions tucked behind Advanced. ──
        <Section label="Build a scenario">
          {loadedStint && (
            <p className="text-[11px] leading-snug text-muted/70">
              Starting from {loadedStint.driver_id}'s real stint edit any lever to go hypothetical.
            </p>
          )}
          <Field label="Compound">
            <div className="relative">
              <select
                className={SELECT_CLS + ` w-full`}
                value={inputs.constants.compound}
                onChange={e => set({ constants: compoundConstants(e.target.value) })}
              >
                {COMPOUND_OPTIONS.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
          </Field>

          {PRIMARY_SLIDERS.map(s => (
            <Slider
              key={s.key}
              spec={s}
              value={inputs[s.key] as number}
              onChange={v => set({ [s.key]: v } as Partial<SimulatorInputs>)}
            />
          ))}

          <details className="group flex flex-col gap-2.5">
            <summary className="flex cursor-pointer list-none items-center gap-1.5 text-[11px] font-medium text-muted transition-colors hover:text-[rgb(var(--color-text))]">
              <span className="transition-transform group-open:rotate-90" aria-hidden>▸</span>
              Advanced conditions
            </summary>
            <div className="mt-2.5 flex flex-col gap-3 border-l border-border pl-3">
              <Field label="Constructor">
                <div className="relative">
                  <select
                    className={SELECT_CLS + ` w-full`}
                    value={inputs.constructor_id}
                    onChange={e => set({ constructor_id: e.target.value })}
                  >
                    {CONSTRUCTOR_OPTIONS.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
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
              {ADVANCED_SLIDERS.map(s => (
                <Slider
                  key={s.key}
                  spec={s}
                  value={inputs[s.key] as number}
                  onChange={v => set({ [s.key]: v } as Partial<SimulatorInputs>)}
                />
              ))}
              <label className="flex cursor-pointer items-center gap-2 py-0.5 text-sm">
                <input
                  type="checkbox"
                  className="accent-[rgb(var(--color-accent))]"
                  checked={inputs.is_rain_lap}
                  onChange={e => set({ is_rain_lap: e.target.checked })}
                />
                <span className="text-muted">Rain lap</span>
              </label>
            </div>
          </details>
        </Section>
      )}
    </div>
  )
}
