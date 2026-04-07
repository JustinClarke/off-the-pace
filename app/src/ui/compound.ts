import { tokens } from './tokens'

/** Returns the hex colour for a tyre compound name (case-insensitive). */
export function compoundColor(name: string): string {
  const normalized = name.toLowerCase()
  if (normalized in tokens.color.tyre) {
    return tokens.color.tyre[normalized as keyof typeof tokens.color.tyre]
  }
  return tokens.color.base
}

/** Returns a Tailwind-compatible CSS class for compound badge backgrounds. */
export function compoundBadgeClass(name: string): string {
  const normalized = name.toLowerCase()
  switch (normalized) {
    case 'soft':
    case 'supersoft':
    case 'ultrasoft':
    case 'hypersoft':
      return 'bg-[#e8002d] text-white'
    case 'medium':
      return 'bg-[#ffd700] text-black'
    case 'hard':
      return 'bg-[#f0f0f0] text-black'
    case 'intermediate':
      return 'bg-[#39b54a] text-white'
    case 'wet':
      return 'bg-[#0067ff] text-white'
    default:
      return 'bg-border text-white'
  }
}

/** Returns the hex colour for a constructor ID. */
export function constructorColor(id: string): string {
  const normalized = id.toLowerCase().replace(/[^a-z0-9]/g, '_')
  
  if (normalized in tokens.color.constructor) {
    return tokens.color.constructor[normalized as keyof typeof tokens.color.constructor]
  }

  // Handle prefix and alias mappings for database names
  if (normalized.startsWith('red_bull')) return tokens.color.constructor.red_bull
  if (normalized.startsWith('haas')) return tokens.color.constructor.haas
  if (normalized.startsWith('alfa_romeo') || normalized.startsWith('alpha_romeo') || normalized.startsWith('sauber')) {
    return tokens.color.constructor.kick_sauber
  }
  if (normalized.startsWith('alphatauri') || normalized.startsWith('toro_rosso')) {
    return tokens.color.constructor.rb
  }
  if (normalized.startsWith('racing_point') || normalized.startsWith('force_india')) {
    return tokens.color.constructor.aston_martin
  }
  if (normalized.startsWith('renault')) return tokens.color.constructor.alpine

  return tokens.color.base
}
