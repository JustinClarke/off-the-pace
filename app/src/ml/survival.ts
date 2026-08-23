// Browser side of the stint-life AFT contract. The mirror of ml/src/survival.py.
//
// The stint-life model is not a regressor: it is an accelerated-failure-time fit,
// because remaining stint life is right-censored on 46.2% of training rows (a
// driver's last stint of a race ends at the flag or at retirement, so the observed
// life is a lower bound). The ONNX graph emits a shifted log-scale margin, and
// turning that into laps is the app's job.
//
// Every constant is read from the manifest, never written here. `margin_offset`
// exists because onnxmltools has no case for survival:aft and would otherwise emit
// a logistic classifier graph; the export retags the objective to get a plain
// TreeEnsembleRegressor, which leaves a fixed offset that ml/src/export_onnx.py
// measures and proves constant before it ships.

import { SurvivalOutput } from './manifest'

/**
 * Inverse standard normal CDF (probit), Acklam's rational approximation.
 * Relative error < 1.15e-9 over the open interval, which is far tighter than the
 * 1e-5 parity gate this feeds. Used only for the p10/p90 band, never the median.
 */
export function probit(p: number): number {
  if (p <= 0 || p >= 1) throw new RangeError(`probit expects p in (0,1), got ${p}`)
  const a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
    1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
  const b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
    6.680131188771972e+01, -1.328068155288572e+01]
  const c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
    -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
  const d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
    3.754408661907416e+00]
  const pLow = 0.02425
  let q: number, r: number
  if (p < pLow) {
    q = Math.sqrt(-2 * Math.log(p))
    return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) /
           ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
  }
  if (p > 1 - pLow) {
    q = Math.sqrt(-2 * Math.log(1 - p))
    return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) /
            ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
  }
  q = p - 0.5
  r = q * q
  return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q /
         (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
}

/**
 * One graph output → remaining stint life in laps.
 * `q` omitted gives the median (the log-normal's 50th percentile is exp(mu));
 * otherwise the q-th percentile. Clipped at 0 -- negative remaining life is not
 * a thing, and predict.py clips identically.
 */
export function lapsFromMargin(raw: number, out: SurvivalOutput, q?: number): number {
  const shifted = raw + out.margin_offset + (q === undefined ? 0 : out.aft_scale * probit(q))
  return Math.max(0, Math.exp(shifted) - out.label_shift)
}

export interface StintLifeBand {
  /** AFT log-normal median, in laps. The headline. */
  median: number
  /** 10th percentile of the same fitted distribution. */
  p10: number
  /** 90th percentile of the same fitted distribution. */
  p90: number
}

/** Median plus the reported band, all from the single graph output. */
export function stintLifeBand(raw: number, out: SurvivalOutput): StintLifeBand {
  return {
    median: lapsFromMargin(raw, out),
    p10: lapsFromMargin(raw, out, out.quantiles.p10 ?? 0.1),
    p90: lapsFromMargin(raw, out, out.quantiles.p90 ?? 0.9),
  }
}
