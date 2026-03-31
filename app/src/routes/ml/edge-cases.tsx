export default function Page() {
  return (
    <div className="max-w-4xl mx-auto px-6 py-10">
      <h1 className="text-2xl font-bold tracking-tight mb-3">Degradation Edge Cases</h1>
      <p className="text-sm text-muted mb-3">
        This view requires <code className="font-mono text-xs bg-surface px-1 py-0.5 rounded">mart_degradation_predictions</code> the
        offline ML scoring mart which is not included in the current public data export.
      </p>
      <p className="text-sm text-muted">
        When available, this page will highlight race stints where the tyre degradation model's
        predicted cliff timing diverged most from observed pace surfacing edge cases used to
        improve model calibration and identify circuits where the compound priors are least reliable.
      </p>
    </div>
  )
}
