import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  { ignores: ['dist', 'src/data/schemas'] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
      // The `cond ? params.set(k, v) : params.delete(k)` idiom in the URL-state
      // setters is an intentional side-effecting ternary, not a dead expression.
      '@typescript-eslint/no-unused-expressions': ['error', { allowShortCircuit: true, allowTernary: true }],
    },
  },
  // Chart-primitive import gate (AD-14): primitives must stay generic  
  // they may not reach into features/ or data/schemas/.
  {
    files: ['src/ui/charts/**/*.{ts,tsx}'],
    rules: {
      // Recharts' <Tooltip content> render-prop is typed as `any` upstream (the props
      // shape is internal and varies with the chart's data generics). The chart
      // primitives only use `any` for that render-prop boundary.
      '@typescript-eslint/no-explicit-any': 'off',
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['*features*', '*data/schemas*'],
              message: 'ui/charts/ must not import from features/ or data/schemas/. Keep chart primitives generic.',
            },
          ],
        },
      ],
    },
  }
)
