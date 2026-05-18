// Global filter bar season, driver, and race dropdowns that write to FilterContext; shown on data-layout routes.
import { useLocation } from 'react-router-dom'
import { useFilters } from '../../state/FilterContext'
import { SEASONS } from '../../data/constants'

// Routes where the season filter is irrelevant (they always show all seasons).
const NO_SEASON_FILTER = new Set(['/drivers/ratings-timeline'])

export default function FilterBar() {
  const { season, setSeason } = useFilters()
  const { pathname } = useLocation()
  const hideSeason = NO_SEASON_FILTER.has(pathname)

  if (hideSeason) return null

  return (
    <div className="flex items-center gap-4 px-4 py-2 border-b border-border bg-surface text-sm">
      <label className="flex items-center gap-2 text-muted">
        Season
        <select
          value={season}
          onChange={e => setSeason(Number(e.target.value))}
          className="bg-transparent border border-border rounded px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-[rgb(var(--color-accent))]"
        >
          {[...SEASONS].reverse().map(s => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </label>
    </div>
  )
}
