// AX-10: validate tool-call arguments against the generated tool schemas (worker/src/generated/tools.ts,
// built from tools.template.json + the exported catalogue). A hand-written interpreter for the subset
// those schemas use: type, required, properties, enum, maxItems, maximum, items. Unknown top-level
// keys are refused, so an argument no schema names (such as an internal row cap) can never reach a tool.

export interface ToolDef {
  type: 'function'
  function: { name: string; description?: string; parameters: Schema }
}

export interface Schema {
  type?: string
  properties?: Record<string, Schema>
  required?: string[]
  enum?: unknown[]
  items?: Schema
  maxItems?: number
  maximum?: number
  [k: string]: unknown
}

export interface ArgError {
  reason: string
  allowed?: unknown
}

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v)

function typeOk(type: string | undefined, v: unknown): boolean {
  switch (type) {
    case undefined: return true
    case 'object': return isObj(v)
    case 'array': return Array.isArray(v)
    case 'string': return typeof v === 'string'
    case 'integer': return typeof v === 'number' && Number.isInteger(v)
    case 'number': return typeof v === 'number' && Number.isFinite(v)
    case 'boolean': return typeof v === 'boolean'
    default: return true
  }
}

function check(schema: Schema, v: unknown, path: string, topLevel: boolean): ArgError | null {
  if (!typeOk(schema.type, v)) return { reason: `${path} must be ${schema.type}` }
  if (schema.enum && !schema.enum.includes(v)) return { reason: `${path} is not an allowed value`, allowed: schema.enum }
  if (typeof v === 'number' && typeof schema.maximum === 'number' && v > schema.maximum) {
    return { reason: `${path} must be at most ${schema.maximum}` }
  }
  if (Array.isArray(v)) {
    if (typeof schema.maxItems === 'number' && v.length > schema.maxItems) return { reason: `${path} has more than ${schema.maxItems} items` }
    if (schema.items) {
      for (let i = 0; i < v.length; i++) {
        const e = check(schema.items, v[i], `${path}[${i}]`, false)
        if (e) return e
      }
    }
  }
  if (isObj(v) && schema.properties) {
    for (const r of schema.required ?? []) if (v[r] === undefined) return { reason: `${path}.${r} is required`, allowed: Object.keys(schema.properties) }
    for (const [k, val] of Object.entries(v)) {
      const sub = schema.properties[k]
      if (!sub) {
        // Nested objects are lenient (e.g. scope items); the top level is strict.
        if (topLevel) return { reason: `${path}.${k} is not an argument of this tool`, allowed: Object.keys(schema.properties) }
        continue
      }
      if (val === undefined) continue
      const e = check(sub, val, `${path}.${k}`, false)
      if (e) return e
    }
  }
  return null
}

/** null when the arguments satisfy the tool's schema. */
export function validateArgs(def: ToolDef, args: unknown): ArgError | null {
  const params = def.function.parameters
  if (!isObj(args)) return { reason: 'arguments must be a JSON object' }
  if ((args as Record<string, unknown>).__unparsable) return { reason: 'arguments were not valid JSON' }
  return check(params, args, 'arguments', true)
}
