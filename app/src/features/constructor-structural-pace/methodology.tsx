import { CANONICAL_DOCS_BASE } from '../../config'

export const methodologyHref = `${CANONICAL_DOCS_BASE}/app/constructor-structural-pace`

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
      In the per-race view the CI reflects estimation uncertainty: teams with few clean
      teammate-pair observations have wider intervals. The per-race view shows a single-round estimate and its 95% CI
      (±1.96 × SE).
    </p>
    <p className="mt-2">
      <strong>Season view.</strong> The season number is the plain average of the team's race
      estimates, over the k races that have one (the Races column; Obs counts only those races).
      The interval treats the season's races as a sample of circuits and weekends. The
      standard error is √(max(s², mean se²) / k): the larger of the race-to-race spread
      (s², the sample variance of the race estimates) and the per-race estimation error
      (mean se²). The 95% CI is the average ± t × SE, with the t quantile for k − 1
      degrees of freedom. With fewer than 3 races there is no season interval and the
      cells show a dash. Why the larger of the two: the race estimates scatter about ten
      times more than their own SEs allow, so an interval built from estimation error alone
      was too narrow (in a split-half check it covered about half of what it should). Some
      of that scatter is real weekend-specific car pace; the rest may be per-race SEs that
      ignore lap-to-lap correlation. The plain average stays the point, so the number you
      see is still the simple mean of the races. The per-race view is unchanged: one
      round's estimate and its ±1.96 × SE interval.
    </p>
    <p className="mt-2">
      Race pace and qualifying pace are estimated separately because tyre management strategies
      in races decorrelate from single-lap qualifying performance.
    </p>
  </>
)
