// CSS variable accessors typed wrappers around --color-* custom properties; used in chart colour configs.
export const cssVar = {
  bg: 'rgb(var(--color-bg))',
  surface: 'rgb(var(--color-surface))',
  border: 'rgb(var(--color-border))',
  text: 'rgb(var(--color-text))',
  textMuted: 'rgb(var(--color-text-muted))',
  accent: 'rgb(var(--color-accent))',
  accentSubtle: 'rgb(var(--color-accent-subtle))',
} as const

export function cn(...classes: (string | undefined | null | false)[]): string {
  return classes.filter(Boolean).join(' ')
}
