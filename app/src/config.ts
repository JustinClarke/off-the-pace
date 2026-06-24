// Static app configuration and feature flags; imported by components that need site metadata or conditional features.
export const APP_CONFIG = {
  title: 'Off The Pace',
  description: 'F1 causal lap time decomposition and performance analysis',
  githubUrl: 'https://github.com/JustinClarke/off-the-pace',
  docsUrl: '/docs',
  domain: 'offthepace.dev',
} as const

// Canonical host for the published Mintlify documentation site. Every feature's
// `methodologyHref` is built as `${CANONICAL_DOCS_BASE}/app/<feature-dir>` so the
// host can never drift per-feature. Kept in sync with scripts/app_docs_audit.py.
export const CANONICAL_DOCS_BASE = 'https://offthepace.mintlify.app/'

export const FEATURE_FLAGS = {
  mlPillar: true,
  queryLab: true,
  recruiterDrawer: true,
} as const
