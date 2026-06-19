// Constructor and compound color lookups; maps canonical keys to design-token hex values.
import { tokens } from '../ui/tokens'

type ConstructorKey = keyof typeof tokens.color.constructor
type TyreKey = keyof typeof tokens.color.tyre

export function constructorColor(id: string): string {
  const key = id.toLowerCase().replace(/\s+/g, '_') as ConstructorKey
  return tokens.color.constructor[key] ?? tokens.color.base
}

export function compoundColor(compound: string): string {
  const key = compound.toLowerCase() as TyreKey
  return tokens.color.tyre[key] ?? tokens.color.base
}

export function buildGradient(from: string, to: string, direction = '135deg'): string {
  return `linear-gradient(${direction}, ${from}, ${to})`
}
