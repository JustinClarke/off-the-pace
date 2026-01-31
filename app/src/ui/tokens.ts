// Design tokens constructor/compound hex colours and any other hardcoded visual constants.
export const tokens = {
  color: {
    fuel: '#60a5fa',
    compound: '#4ade80',
    dirty_air: '#f97316',
    traffic: '#a78bfa',
    tyre_cliff: '#fb7185',
    driver_skill: '#34d399',
    pitstop: '#fbbf24',
    base: '#94a3b8',

    constructor: {
      red_bull: '#3671c6',
      ferrari: '#e8002d',
      mercedes: '#27f4d2',
      mclaren: '#ff8000',
      aston_martin: '#358c75',
      alpine: '#ff87bc',
      williams: '#64c4ff',
      rb: '#6692ff',
      kick_sauber: '#52e252',
      haas: '#b6babd',
    },

    tyre: {
      soft: '#e8002d',
      medium: '#ffd700',
      hard: '#f0f0f0',
      intermediate: '#39b54a',
      wet: '#0067ff',
      // 2018–2019 era compound names
      supersoft: '#c0000a',
      ultrasoft: '#9b59b6',
      hypersoft: '#ff80c7',
    },
  },

  spacing: {
    xs: '4px',
    sm: '8px',
    md: '16px',
    lg: '24px',
    xl: '32px',
    '2xl': '48px',
  },

  fontSize: {
    xs: '0.75rem',
    sm: '0.875rem',
    base: '1rem',
    lg: '1.125rem',
    xl: '1.25rem',
    '2xl': '1.5rem',
    '3xl': '1.875rem',
  },
} as const
