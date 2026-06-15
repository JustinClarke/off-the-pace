export const methodologyHref =
  'https://docs.offthepace.dev/reference/models/int/int_constructor_structural_pace'

export const methodologyContent = (
  <>
    <p>
      Constructor structural pace comes from <strong>int_constructor_structural_pace</strong> (race)
      and <strong>int_constructor_structural_pace_qualifying</strong>: a fixed-effects panel
      regression isolates each team's car contribution to lap time after controlling for driver
      skill, tyre state, fuel, and ambient conditions.
    </p>
    <p className="mt-2">
      Negative values mean the constructor's car is faster than the field average for that race.
      The CI reflects estimation uncertainty teams with few clean teammate-pair observations
      have wider intervals. Season view averages across all rounds; per-race view shows a
      single-round estimate.
    </p>
    <p className="mt-2">
      Race pace and qualifying pace are estimated separately because tyre management strategies
      in races decorrelate from single-lap qualifying performance.
    </p>
  </>
)
