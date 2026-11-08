export interface ProvenanceMeta {
  fitDate?: string
  dataWindow?: string
  nObs?: number
  modelVersion?: string
  datasetFingerprint?: string
  /** Data build id (manifest version); rendered as data:<first 8> */
  dataVersion?: string
  /** Label version from the data manifest (TX-05), e.g. "v16"; rendered as "label v16" */
  labelVersion?: string
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
  if (meta.dataVersion) parts.push(`data:${meta.dataVersion.slice(0, 8)}`)
  if (meta.labelVersion) parts.push(`label ${meta.labelVersion}`)
  if (!parts.length) return null

  return (
    <p className="text-xs text-muted/60 font-mono">
      {parts.join(' · ')}
    </p>
  )
}
