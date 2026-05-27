import RankedTable from '../../ui/charts/RankedTable'
import type { LeaderboardResult, LeaderboardEntry } from './transform'
import { CONFIDENCE_FLOOR } from './transform'

interface Props {
  result: LeaderboardResult
}

function paceClass(s: unknown): string {
  const n = s as number
  if (n < -0.05) return 'text-emerald-400'
  if (n > 0.05) return 'text-rose-400'
  return 'text-muted'
}

function fmtSigned(s: unknown): string {
  const n = s as number
  const r = n.toFixed(2)
  return n > 0 ? `+${r}` : r
}

function confidenceBadge(conf: unknown): string {
  const c = conf as number
  if (c >= 0.5) return 'bg-emerald-500/10 text-emerald-400'
  if (c >= CONFIDENCE_FLOOR) return 'bg-amber-500/10 text-amber-400'
  return 'bg-rose-500/10 text-rose-400'
}

export default function GhostStandingsChart({ result }: Props) {
  if (!result.entries.length) return null

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xs font-mono text-muted uppercase tracking-wider">
          {result.circuitName}
        </span>
        <span className="text-xs text-muted/50">equal-car record · {result.eraLabel}</span>
      </div>
      <RankedTable<LeaderboardEntry>
        rows={result.entries}
        columns={[
          {
            key: 'rank',
            header: '#',
            align: 'right',
            render: v => <span className="font-semibold">{String(v)}</span>,
          },
          {
            key: 'driverId',
            header: 'Driver',
            align: 'left',
            render: v => <span className="font-medium tracking-wide">{String(v)}</span>,
          },
          {
            key: 'affinityS',
            header: 'Pace vs field',
            align: 'right',
            render: v => {
              const s = v as number
              return (
                <span
                  className={`font-mono ${paceClass(s)}`}
                  title="Car-removed pace at this circuit, shrunk toward the driver's era average. Negative = faster than the field."
                >
                  {fmtSigned(s)}s
                </span>
              )
            },
          },
          {
            key: 'gapToLeaderS',
            header: 'Gap',
            align: 'right',
            render: (v, row) => {
              const g = v as number
              if (row.rank === 1) return <span className="text-muted/40 text-xs"> </span>
              return <span className="font-mono text-muted">+{g.toFixed(2)}s</span>
            },
          },
          {
            key: 'ciLowS',
            header: '95% CI',
            align: 'right',
            render: (_v, row) => (
              <span
                className="font-mono text-xs text-muted/70"
                title="95% credible interval on the shrunk pace estimate (seconds)."
              >
                [{row.ciLowS.toFixed(2)}, {row.ciHighS.toFixed(2)}]
              </span>
            ),
          },
          {
            key: 'races',
            header: 'Races',
            align: 'right',
            render: (v, row) => (
              <span title={`${row.seasons} season${row.seasons === 1 ? '' : 's'} observed in this era`}>
                {String(v)}
              </span>
            ),
          },
          {
            key: 'confidence',
            header: 'Conf.',
            align: 'right',
            render: v => {
              const c = v as number
              return (
                <span
                  className={`text-xs px-1.5 py-0.5 rounded font-mono ${confidenceBadge(c)}`}
                  title={
                    c < CONFIDENCE_FLOOR
                      ? 'Prior-dominated: too few races to separate from this driver’s career average.'
                      : `Data fraction of the estimate (n / (n+5)). Higher = more races behind it.`
                  }
                >
                  {c.toFixed(2)}
                </span>
              )
            },
          },
        ]}
        initialRows={30}
      />
    </div>
  )
}
