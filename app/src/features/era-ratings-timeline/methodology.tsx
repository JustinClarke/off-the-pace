export const methodologyContent = (
  <>
    <p>
      Each line tracks a driver's era-adjusted pace rating across seasons, expressed
      in seconds relative to the field average after normalising for the 2022
      regulation change. Negative = faster than the era-normalised field average.
    </p>
    <ul className="list-disc pl-4 mt-3 space-y-1">
      <li>
        <strong>Bayesian shrinkage:</strong> per-season residuals are shrunk toward the
        season league average. Drivers with fewer races have wider CIs and estimates
        pulled closer to zero-the uncertainty is honest, not hidden.
      </li>
      <li>
        <strong>Era calibration:</strong> the 2022 ground-effect regulation change
        shifted raw lap-time residuals. The offset is estimated from 20 "bridge
        drivers"-drivers with ≥8 clean-race seasons on both sides of the boundary -
        and applied to all pre-2022 seasons. Bridge drivers are shown as solid lines;
        non-bridge drivers as dashed.
      </li>
      <li>
        <strong>95% CI ribbon:</strong> propagates both the per-season shrinkage
        standard error and (for pre-2022) the era-offset estimation uncertainty.
      </li>
    </ul>
    <p className="mt-3 text-muted/70">
      Source: <code>int_era_normalized_driver_rating</code> via{' '}
      <code>int_driver_season_ratings</code>. Clean-lap filter applied upstream.
    </p>
  </>
)

export const methodologyHref =
  'https://off-the-pace.onrender.com/reference/models/int/int_era_normalized_driver_rating'
