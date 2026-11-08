import type { QueryResult } from '../queryBuilder/types'

export const fakeResult = (id: string, rows: QueryResult['rows']): QueryResult => ({
  status: 'ok', view: 'qv_laps', filters_applied: [], grain: 'g', aggregate: { fn: 'median', col: 'lap_time_s' },
  group_by: [], rows, row_count: rows.length, rows_shown: rows.length, rows_dropped: 0, label: 'computed_not_card', notes: [], result_id: id,
})

