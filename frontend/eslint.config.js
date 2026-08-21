import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'

// eslint-plugin-react is absent on purpose: its latest release declares no
// support for ESLint 10, and pinning a pre-release to get it back is worse
// than doing without. The rule it is most missed for is react/jsx-key, so
// tests/setup.js fails any test that logs a React warning instead.
export default [
  { ignores: ['dist/**', 'coverage/**'] },
  js.configs.recommended,
  {
    files: ['**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 2023,
      globals: { ...globals.browser, ...globals.node },
      parserOptions: { ecmaFeatures: { jsx: true }, sourceType: 'module' },
    },
    plugins: { 'react-hooks': reactHooks },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
    },
  },
  {
    files: ['tests/**/*.{js,jsx}'],
    languageOptions: { globals: { ...globals.vitest } },
  },
]
