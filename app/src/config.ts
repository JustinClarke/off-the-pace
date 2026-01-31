// Static app configuration and feature flags; imported by components that need site metadata or conditional features.
export const APP_CONFIG = {
  title: 'Off The Pace',
  description: 'F1 causal lap time decomposition and performance analysis',
  githubUrl: 'https://github.com/JustinClarke/off-the-pace',
  docsUrl: '/docs',
  domain: 'offthepace.dev',
} as const

export const FEATURE_FLAGS = {
  mlPillar: true,
  queryLab: true,
  recruiterDrawer: true,
} as const
