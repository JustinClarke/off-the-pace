interface IdentityCheckProps {
  explained: number
  observed: number
  tolerance?: number
  label?: string
}

const TOLERANCE = 1e-4

export default function IdentityCheck({
  explained,
  observed,
  tolerance = TOLERANCE,
  label = 'closure',
}: IdentityCheckProps) {
  const error = Math.abs(explained-observed)
  const isValid = error <= tolerance

  return (
    <span
      title={`${label}: explained=${explained.toFixed(6)}, observed=${observed.toFixed(6)}, error=${error.toFixed(2e-6)}`}
      className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded font-medium ${
        isValid
          ? 'bg-green-500/10 text-green-400 border border-green-500/20'
          : 'bg-orange-500/10 text-orange-400 border border-orange-500/20'
      }`}
    >
      <span>{isValid ? '✓' : '⚠'}</span>
      {isValid ? 'Identity valid' : `Identity gap: ${error.toFixed(4)}`}
    </span>
  )
}
