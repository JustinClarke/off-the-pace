import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';

const config: Config = {
  title: 'Off The Pace',
  tagline: 'Physics-informed F1 lap-time decomposition',
  favicon: 'img/favicon.svg',

  future: {
    v4: true,
  },

  url: 'https://off-the-pace.onrender.com',
  baseUrl: '/',
  trailingSlash: false,

  organizationName: 'justinclarke',
  projectName: 'off-the-pace',

  onBrokenLinks: 'throw',
  onBrokenAnchors: 'warn',
  markdown: {
    hooks: {
      onBrokenMarkdownLinks: 'warn',
    },
  },

  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  scripts: [
    {
      src: 'https://cloud.umami.is/script.js',
      defer: true,
      'data-website-id': '591c3025-6560-47b4-b7b0-16fa8c3f4c0b',
    },
  ],

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          editUrl: 'https://github.com/justinclarke/off-the-pace/tree/main/',
          routeBasePath: '/',
          remarkPlugins: [remarkMath],
          rehypePlugins: [rehypeKatex],
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    image: 'img/audif1.webp',
    colorMode: {
      respectPrefersColorScheme: true,
    },
    navbar: {
      title: 'Off The Pace',
      logo: {
        alt: 'Off The Pace',
        src: 'img/logo.svg',
      },
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'understandSidebar',
          position: 'left',
          label: 'Understand',
        },
        {
          type: 'docSidebar',
          sidebarId: 'dbtSidebar',
          position: 'left',
          label: 'DBT',
        },
        {
          type: 'docSidebar',
          sidebarId: 'mlSidebar',
          position: 'left',
          label: 'Machine Learning',
        },
        {
          type: 'docSidebar',
          sidebarId: 'findingsSidebar',
          position: 'left',
          label: 'Findings',
        },
        {
          type: 'docSidebar',
          sidebarId: 'referenceSidebar',
          position: 'left',
          label: 'Reference',
        },
        {
          href: 'pathname:///project-graph.html',
          position: 'left',
          label: 'Project Graph',
        },
        {
          href: 'https://github.com/justinclarke/off-the-pace',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Understand',
          items: [
            {label: 'Goal & Approach', to: '/understand/goal-and-approach'},
            {label: 'Seven-Term Identity', to: '/understand/seven-term-identity'},
            {label: 'Methodology', to: '/understand/methodology'},
            {label: 'Limitations', to: '/understand/limitations'},
          ],
        },
        {
          title: 'Findings',
          items: [
            {label: 'São Paulo 2021', to: '/attributed-findings/sao-paulo-2021'},
          ],
        },
        {
          title: 'Reference',
          items: [
            {label: 'dbt Models', to: '/reference/models'},
            {label: 'Schemas', to: '/reference/schemas'},
            {label: 'Glossary', to: '/reference/glossary'},
          ],
        },
        {
          title: 'More',
          items: [
            {
              label: 'GitHub',
              href: 'https://github.com/justinclarke/off-the-pace',
            },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} Justin Clarke. Code: AGPL-3.0. Docs: MIT.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
      additionalLanguages: ['python', 'bash', 'sql', 'json', 'yaml'],
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
