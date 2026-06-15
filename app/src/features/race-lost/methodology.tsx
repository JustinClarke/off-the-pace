export const methodologyContent = (
  <>
    <p>
      "How the Race Was Lost" cumulates the per-lap decomposition identity across the entire race
      for a selected driver, turning average-per-lap components into total race contributions.
    </p>
    <p className="mt-3">
      For each component (fuel, tyres, ambient, constructor, dirty air, driver skill, track
      noise), the value shown is the <strong>sum across all classified laps</strong> laps under
      safety car, virtual safety car, and major outlier laps are excluded. The result answers:
      "across the full race, how many seconds did dirty air cost this driver vs the per-lap field
      median?"
    </p>
    <ul className="list-disc pl-4 mt-3 space-y-1">
      <li>Negative total = driver/car gained time from that factor vs field median</li>
      <li>Positive total = driver/car lost time from that factor</li>
      <li><strong>Driver Skill</strong>: the residual after removing all physics components pure driving contribution</li>
      <li><strong>Track Noise</strong>: unexplained lap-to-lap variation; informational, not additive to the identity</li>
    </ul>
    <p className="mt-3 text-muted/70">
      Source: <code>fct_lap_residuals</code>. Single race view.
    </p>
  </>
)

export const methodologyHref = 'https://offthepace.mintlify.app/decomposition/seven-term-identity'
