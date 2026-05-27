export const methodologyContent = (
  <>
    <p>
      The Lap Air Map shows the aerodynamic environment each driver experienced lap by lap
      during a race: whether they were running in free air, stuck in dirty air, benefiting from
      a tow, or running in a DRS train.
    </p>
    <ul className="list-disc pl-4 mt-3 space-y-1">
      <li><strong>Dirty air</strong> (red): gap to car ahead &lt; 1.5s in the middle-third
        sector. The thermally-loaded air disrupts downforce and causes tyre overheating.</li>
      <li><strong>Tow zone</strong> (green): gap &lt; 1.0s on a straight sector, without active
        DRS. Slipstream benefit without full aerodynamic interference.</li>
      <li><strong>DRS train</strong> (amber): gap &lt; 1.0s with DRS active. Speed benefit but
        still constrained by car ahead.</li>
      <li><strong>Free air</strong> (grey): gap &gt; 2.0s or gap unavailable. Clean aerodynamic
        conditions; baseline.</li>
    </ul>
    <p className="mt-3">
      Drivers are sorted by total dirty-air laps in the race (most affected first).
      Lap numbers run left to right. Hover a cell for the thermal load index and closest
      gap reading.
    </p>
    <p className="mt-3 text-muted/70">
      Source: <code>int_lap_air_state</code>. Telemetry-derived gap estimates; missing telemetry
      laps show as free-air (grey).
    </p>
  </>
)

export const methodologyHref = 'https://offthepace.mintlify.app/reference/models/int/int_lap_air_state'
