export interface ProvenanceMeta {
  fitDate?: string
  dataWindow?: string
  nObs?: number
  modelVersion?: string
  datasetFingerprint?: string
}

interface ProvenanceProps {
  meta: ProvenanceMeta
}

export default function Provenance({ meta }: ProvenanceProps) {
  const parts: string[] = []
  if (meta.fitDate) parts.push(`fit ${meta.fitDate}`)
  if (meta.dataWindow) parts.push(meta.dataWindow)
  if (meta.nObs !== undefined) parts.push(`n=${meta.nObs.toLocaleString()}`)
  if (meta.modelVersion) parts.push(`v${meta.modelVersion}`)
  if (meta.datasetFingerprint) parts.push(`sha:${meta.datasetFingerprint.slice(0, 8)}`)
  if (!parts.length) return null

  return (
    <p className="text-xs text-muted/60 font-mono">
      {parts.join(' · ')}
    </p>
  )
}
