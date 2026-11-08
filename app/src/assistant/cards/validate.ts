// AX-01 card validator. It interprets card.schema.json directly (no copy of the rules lives
// here), using the small JSON Schema subset below, then adds the checks a schema cannot say:
// interval low <= high, id starts with kind, and the registry's interval kind (AX-04 passes
// expectedIntervalKind so a relabelled interval kind is an error).
//
// Decision (AX-01 finding 2): hand-written interpreter, no ajv. app/package.json has no schema
// validator; the only ajv in node_modules is eslint's ajv 6, which has no 2020-12 support.
// validate.test.ts fails if the schema starts using a keyword this file does not implement.
import schemaJson from './card.schema.json'
import type { Card } from './card.types'

export type { Card }

export interface ValidationResult {
  ok: boolean
  errors: string[]
}

export interface ValidateOptions {
  /** The interval kind the registry entry declares. A card whose interval.kind differs fails. */
  expectedIntervalKind?: string
}

type Schema = {
  type?: string | string[]
  enum?: unknown[]
  const?: unknown
  pattern?: string
  minLength?: number
  minimum?: number
  maximum?: number
  required?: string[]
  properties?: Record<string, Schema>
  additionalProperties?: boolean | Schema
  items?: Schema
  if?: Schema
  then?: Schema
  not?: Schema
  anyOf?: Schema[]
  allOf?: Schema[]
  [annotation: string]: unknown
}

/** Keywords the interpreter evaluates. Annotation keywords are ignored. */
export const SUPPORTED_KEYWORDS = [
  'type', 'enum', 'const', 'pattern', 'minLength', 'minimum', 'maximum', 'required',
  'properties', 'additionalProperties', 'items', 'if', 'then', 'not', 'anyOf', 'allOf',
] as const
export const ANNOTATION_KEYWORDS = ['$schema', '$id', '$comment', 'title', 'description'] as const

export const cardSchema = schemaJson as unknown as Schema

function typeOf(v: unknown): string {
  if (v === null) return 'null'
  if (Array.isArray(v)) return 'array'
  if (typeof v === 'number') return Number.isInteger(v) ? 'integer' : 'number'
  return typeof v
}

function typeMatches(v: unknown, t: string): boolean {
  const actual = typeOf(v)
  if (t === 'number') return actual === 'number' || actual === 'integer'
  return actual === t
}

function check(s: Schema, v: unknown, path: string, errors: string[]): void {
  const at = path || '(card)'
  if (s.type !== undefined) {
    const ts = Array.isArray(s.type) ? s.type : [s.type]
    if (!ts.some((t) => typeMatches(v, t))) {
      errors.push(`${at}: expected ${ts.join(' or ')}, got ${typeOf(v)}`)
      return
    }
  }
  if (s.const !== undefined && v !== s.const) errors.push(`${at}: must be ${JSON.stringify(s.const)}`)
  if (s.enum && !s.enum.includes(v)) errors.push(`${at}: ${JSON.stringify(v)} is not one of ${JSON.stringify(s.enum)}`)
  if (typeof v === 'string') {
    if (s.pattern !== undefined && !new RegExp(s.pattern, 'u').test(v)) errors.push(`${at}: does not match ${s.pattern}`)
    if (s.minLength !== undefined && v.length < s.minLength) errors.push(`${at}: shorter than ${s.minLength}`)
  }
  if (typeof v === 'number') {
    if (s.minimum !== undefined && v < s.minimum) errors.push(`${at}: below ${s.minimum}`)
    if (s.maximum !== undefined && v > s.maximum) errors.push(`${at}: above ${s.maximum}`)
  }
  if (Array.isArray(v) && s.items) v.forEach((item, i) => check(s.items as Schema, item, `${path}[${i}]`, errors))
  if (v !== null && typeof v === 'object' && !Array.isArray(v)) {
    const obj = v as Record<string, unknown>
    for (const k of s.required ?? []) if (!(k in obj)) errors.push(`${path ? path + '.' : ''}${k}: required`)
    for (const [k, child] of Object.entries(obj)) {
      const p = path ? `${path}.${k}` : k
      const ps = s.properties?.[k]
      if (ps) check(ps, child, p, errors)
      else if (s.additionalProperties === false) {
        if (s.properties) errors.push(`${p}: unknown field`)
      } else if (s.additionalProperties && typeof s.additionalProperties === 'object') {
        check(s.additionalProperties, child, p, errors)
      }
    }
  }
  if (s.not) {
    const sub: string[] = []
    check(s.not, v, path, sub)
    if (sub.length === 0) errors.push(`${at}: must not match ${JSON.stringify(s.not)}`)
  }
  if (s.anyOf) {
    const branches = s.anyOf.map((b) => {
      const sub: string[] = []
      check(b, v, path, sub)
      return sub
    })
    if (!branches.some((b) => b.length === 0)) errors.push(`${at}: matches none of: ${branches.map((b) => b.join('; ')).join(' | ')}`)
  }
  for (const sub of s.allOf ?? []) check(sub, v, path, errors)
  if (s.if) {
    const cond: string[] = []
    check(s.if, v, path, cond)
    if (cond.length === 0 && s.then) {
      const sub: string[] = []
      check(s.then, v, path, sub)
      const why = typeof s.$comment === 'string' ? ` (${s.$comment})` : ''
      for (const e of sub) errors.push(`${e}${why}`)
    }
  }
}

/** Validate one card against card.schema.json plus the semantic checks. */
export function validateCard(card: unknown, opts: ValidateOptions = {}): ValidationResult {
  const errors: string[] = []
  check(cardSchema, card, '', errors)
  if (card !== null && typeof card === 'object' && !Array.isArray(card)) {
    const c = card as Partial<Card>
    if (typeof c.id === 'string' && typeof c.kind === 'string' && !c.id.startsWith(`${c.kind}:`)) {
      errors.push(`id: must start with kind "${c.kind}:"`)
    }
    const iv = c.interval
    if (iv && typeof iv === 'object') {
      if (typeof iv.low === 'number' && typeof iv.high === 'number' && iv.low > iv.high) {
        errors.push(`interval: low ${iv.low} is above high ${iv.high}`)
      }
      if (opts.expectedIntervalKind !== undefined && iv.kind !== opts.expectedIntervalKind) {
        errors.push(`interval.kind: "${iv.kind}" differs from the registry's "${opts.expectedIntervalKind}" (relabelled interval kind)`)
      }
    } else if (opts.expectedIntervalKind !== undefined && opts.expectedIntervalKind !== 'none' && c.status === 'active' && c.label !== 'unavailable') {
      errors.push(`interval: null, but the registry declares "${opts.expectedIntervalKind}"`)
    }
    if (typeof c.value === 'number' && !Number.isFinite(c.value)) errors.push('value: must be finite')
  }
  return { ok: errors.length === 0, errors }
}

/** Every keyword used anywhere in a schema, for the supported-keyword guard test. */
export function keywordsUsed(s: unknown, out = new Set<string>()): Set<string> {
  if (s === null || typeof s !== 'object') return out
  if (Array.isArray(s)) {
    for (const x of s) keywordsUsed(x, out)
    return out
  }
  for (const [k, v] of Object.entries(s as Record<string, unknown>)) {
    out.add(k)
    if (k === 'properties') for (const child of Object.values(v as Record<string, unknown>)) keywordsUsed(child, out)
    else if (k !== 'enum' && k !== 'const' && k !== 'required') keywordsUsed(v, out)
  }
  return out
}
