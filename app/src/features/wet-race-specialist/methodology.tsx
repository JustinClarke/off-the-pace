import { CANONICAL_DOCS_BASE } from '../../config'

export const methodologyContent = (
  <>
    <p>
      Wet-race skill is measured by comparing a driver's race skill residual on
      wet-flagged races against their dry-race baseline, across their full
      2018–2024 career.
    </p>
    <ul className="list-disc pl-4 mt-3 space-y-1">
      <li><strong>Wet advantage</strong>: wet skill residual minus dry skill residual.
        Positive = the driver is faster (relative to the field model) in wet conditions
        than their dry-race baseline. Shrunk toward zero by sample size (k=6 prior)
        so low-n drivers appear closer to neutral.</li>
      <li><strong>Wet flag</strong>: <code>race_wet_flag</code> from
        <code> fct_driver_skill_features</code>. Flags a race where weather
        significantly affected conditions during the timed stint window.</li>
      <li><strong>Eligibility</strong>: at least 4 wet races and 5 dry races with ≥5
        clean laps each. Drivers with fewer observations are excluded.</li>
    </ul>
    <p className="mt-3">
      The skill residual already accounts for car pace, tyre compound, fuel load,
      and ambient conditions so the wet advantage reflects genuine driver
      adaptability rather than the car's wet-weather setup.
    </p>
    <p className="mt-3 text-muted/70">
      Source: <code>fct_driver_skill_features</code>. Career aggregation (2018–2024).
    </p>
  </>
)

export const methodologyHref = `${CANONICAL_DOCS_BASE}/app/wet-race-specialist`
