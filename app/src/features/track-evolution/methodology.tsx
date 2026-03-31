export const methodologyContent = (
  <>
    <p>
      Track evolution decomposes the lap-time baseline into two time-varying components:
      rubber buildup and ambient conditions. Both are extracted from the seven-term
      additive decomposition run over clean laps.
    </p>
    <ul className="list-disc pl-4 mt-3 space-y-1">
      <li><strong>Rubber component</strong>: how much the track surface improves (becomes
        faster) as rubber is laid over the race distance. Derived from
        <code> rubber_component_s</code> positive means the track is slower early, then
        rubbering in reduces the positive offset over laps.</li>
      <li><strong>Ambient component</strong>: temperature and humidity drift over the
        race window, extracted as a separate time-varying offset. Usually small but
        can be significant in night races or sessions with changing cloud cover.</li>
      <li><strong>Rainfall</strong>: laps tagged with the rainfall flag are highlighted.
        Track state index resets substantially after rain.</li>
    </ul>
    <p className="mt-3 text-muted/70">
      Source: <code>int_track_evolution</code>. Single race view.
    </p>
  </>
)

export const methodologyHref = 'https://offthepace.mintlify.app/reference/models/int/int_track_evolution'
