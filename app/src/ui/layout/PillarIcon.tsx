// Monochrome line icons for the sidebar pillars, keyed by pillar id. Stroke-based,
// inherit currentColor so they pick up the active/muted nav colour-no emoji, no
// colour glyphs, one consistent visual language across the whole nav.
type IconProps = { className?: string }

const base = {
  width: 16,
  height: 16,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.75,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
}

const ICONS: Record<string, (p: IconProps) => JSX.Element> = {
  // Home-hexagon (matches the OTP mark)
  home: (p) => (
    <svg {...base} {...p}><path d="M12 3l7 4v8l-7 4-7-4V7z" /></svg>
  ),
  // Races-stopwatch / lap timer
  races: (p) => (
    <svg {...base} {...p}><circle cx="12" cy="13" r="7" /><path d="M12 13V9M12 2h0M9 2h6" /></svg>
  ),
  // Ghost Car-dashed silhouette car outline (counterfactual)
  'ghost-car': (p) => (
    <svg {...base} {...p} strokeDasharray="3 2.5"><path d="M3 15l2-5a3 3 0 0 1 3-2h8a3 3 0 0 1 3 2l2 5v3H3z" /><circle cx="8" cy="18" r="1.4" strokeDasharray="0" /><circle cx="16" cy="18" r="1.4" strokeDasharray="0" /></svg>
  ),
  // Lap Decomposition-stacked layers (additive identity)
  'lap-decomposition': (p) => (
    <svg {...base} {...p}><path d="M12 3l8 4-8 4-8-4z" /><path d="M4 12l8 4 8-4M4 16l8 4 8-4" /></svg>
  ),
  // Tyre & Strategy-tyre (ring)
  'tyre-strategy': (p) => (
    <svg {...base} {...p}><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="4" /></svg>
  ),
  // Aero & Conditions-airflow lines
  aero: (p) => (
    <svg {...base} {...p}><path d="M3 8h13a3 3 0 1 0-3-3M3 12h16a3 3 0 1 1-3 3M3 16h10a2.5 2.5 0 1 1-2.5 2.5" /></svg>
  ),
  // Race Craft-crossed flags / duel
  'race-craft': (p) => (
    <svg {...base} {...p}><path d="M5 3v18M5 4h9l-2 3 2 3H5M19 21V8M19 9h-6" /></svg>
  ),
  // Drivers-helmet
  drivers: (p) => (
    <svg {...base} {...p}><path d="M4 13a8 8 0 0 1 16 0v1H4z" /><path d="M4 14h16a2 2 0 0 1-2 2H9a5 5 0 0 1-5-2z" /><path d="M9 9h7" /></svg>
  ),
  // Constructors-factory / structure grid
  constructors: (p) => (
    <svg {...base} {...p}><rect x="3" y="9" width="18" height="12" rx="1" /><path d="M3 9l5-3v3M8 9l5-3v3M3 13h18M9 13v8M15 13v8" /></svg>
  ),
  // Energy & Telemetry-signal pulse
  energy: (p) => (
    <svg {...base} {...p}><path d="M3 12h4l2-6 4 14 2.5-8H21" /></svg>
  ),
  // The Machine (ML)-circuit node
  ml: (p) => (
    <svg {...base} {...p}><rect x="8" y="8" width="8" height="8" rx="1" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5.5 5.5l2 2M16.5 16.5l2 2M18.5 5.5l-2 2M7.5 16.5l-2 2" /></svg>
  ),
  // Query Lab-terminal prompt
  query: (p) => (
    <svg {...base} {...p}><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M7 9l3 3-3 3M13 15h4" /></svg>
  ),
  // Data Quality-shield check
  'data-quality': (p) => (
    <svg {...base} {...p}><path d="M12 3l7 3v5c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z" /><path d="M9 12l2 2 4-4" /></svg>
  ),
}

export default function PillarIcon({ id, className }: { id: string; className?: string }) {
  const Icon = ICONS[id]
  if (!Icon) return null
  return <Icon className={className} />
}
