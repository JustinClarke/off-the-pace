// AX-14: the chart card, loaded when an answer actually carries a chart (recharts stays out of the drawer's first load).
import { createElement, lazy, Suspense } from 'react'

const Lazy = lazy(() => import('../charts/ChartCard'))

export function ChartCard({ chartId }: { chartId: string }) {
  return createElement(Suspense, { fallback: null }, createElement(Lazy, { chartId }))
}
