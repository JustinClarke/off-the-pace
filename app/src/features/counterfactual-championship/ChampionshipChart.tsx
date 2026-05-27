import RankedTable from '../../ui/charts/RankedTable'
import type { ChampionshipEntry } from './transform'

const fmtDelta = (d: number) => (d > 0 ? `+${d}` : String(d))

function DeltaCell({ v }: { v: number }) {
  const cls = v > 0 ? 'text-emerald-400' : v < 0 ? 'text-red-400' : 'text-muted'
  return <span className={cls}>{fmtDelta(v)}</span>
}

function RankMoveCell({ ghost, actual }: { ghost: number; actual: number }) {
  const move = actual - ghost
  if (move === 0) return <span className="text-muted"> </span>
  const cls = move > 0 ? 'text-emerald-400' : 'text-red-400'
  return <span className={cls}>{move > 0 ? `+${move}` : move}</span>
}

export default function ChampionshipChart({
  data,
  coverageWarning,
}: {
  data: ChampionshipEntry[]
  coverageWarning: boolean
}) {
  return (
    <div className="flex flex-col gap-4">
      {coverageWarning && (
        <p className="text-xs text-amber-400/80 bg-amber-500/10 border border-amber-500/20 rounded px-3 py-2">
          Coverage warning: fewer than 15 races qualify with recombination_confidence &ge; 0.3.
          Season-level aggregation may be unreliable.
        </p>
      )}
      <RankedTable
        rows={data as unknown as Record<string, unknown>[]}
        initialRows={25}
        columns={[
          { key: 'ghostRank', header: 'Ghost P', align: 'right', render: v => `P${v}` },
          { key: 'driver', header: 'Driver', align: 'left' },
          { key: 'ghostPoints', header: 'Ghost Pts', align: 'right' },
          { key: 'actualPoints', header: 'Actual Pts', align: 'right' },
          {
            key: 'delta',
            header: 'Pts Δ',
            align: 'right',
            render: v => <DeltaCell v={v as number} />,
          },
          {
            key: 'ghostRank',
            header: 'Rank move',
            align: 'right',
            render: (v, row) => (
              <RankMoveCell
                ghost={v as number}
                actual={(row as unknown as ChampionshipEntry).actualRank}
              />
            ),
          },
          {
            key: 'avgConfidence',
            header: 'Avg conf',
            align: 'right',
            render: v => `${((v as number) * 100).toFixed(0)}%`,
          },
        ]}
      />
    </div>
  )
}
