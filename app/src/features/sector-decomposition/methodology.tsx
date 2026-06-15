export const methodologyContent = (
  <>
    <p>
      Sector Decomposition applies the lap-level residual decomposition identity to each of the
      three timing sectors separately, allocating physics components proportionally to sector
      time share.
    </p>
    <ul className="list-disc pl-4 mt-3 space-y-1">
      <li>
        <strong>Pace delta</strong>: the driver's average sector time minus the rolling 7-lap
        field median sector time for that sector and lap number.
      </li>
      <li>
        <strong>Skill residual</strong>: the portion of the pace delta not explained by the
        physics components (fuel load, tyres, ambient, constructor, dirty air). Isolates
        driving contribution within that sector.
      </li>
      <li>
        <strong>Total explained</strong>: the sum of the six physics components allocated to
        this sector. A large explained component means external factors dominated the delta
        rather than driving style.
      </li>
      <li>
        <strong>Consistency</strong>: within-race standard deviation of the skill residual for
        this driver–sector pair. Lower = more repeatable sector performance.
      </li>
    </ul>
    <p className="mt-3">
      All physics components are allocated proportionally using{' '}
      <code>sector_time / lap_time</code> as the allocation weight, which preserves the
      sector sum = lap total identity.
    </p>
    <p className="mt-3 text-muted/70">
      Source: <code>int_sector_residual_decomposed</code>. Single race view.
    </p>
  </>
)

export const methodologyHref = 'https://offthepace.mintlify.app/reference/models/int/int_sector_residual_decomposed'
