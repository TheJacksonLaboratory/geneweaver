// Legacy GeneWeaver UI lint config.
//
// Same tooling as geneweaver-ui: ESLint 9 flat config + eslint-config-prettier +
// Prettier (see .prettierrc). geneweaver-ui additionally layers @nx/eslint-plugin,
// angular-eslint and typescript-eslint on top — those do NOT apply here because legacy
// has no Nx workspace, no Angular and no TypeScript (it is plain ES5/ES6 jQuery JS),
// so we use the @eslint/js recommended base instead. Same tools, same Prettier rules.

const js = require('@eslint/js');
const prettier = require('eslint-config-prettier');

module.exports = [
  {
    // Vendored third-party libraries intermixed with first-party JS in src/static/js/
    // (jQuery + plugins, DataTables, d3, dynatree, cytoscape) — never lint these.
    ignores: [
      'src/static/js/cytoscape/**',
      'src/static/js/dynatree-1.2.8/**',
      'src/static/js/jquery*.js',
      'src/static/js/dataTables.*.js',
      'src/static/js/d3.*.js',
      '**/*.min.js',
    ],
  },
  js.configs.recommended,
  prettier,
  {
    files: ['**/*.js'],
    languageOptions: {
      ecmaVersion: 2021,
      sourceType: 'script',
      globals: {
        // Browser environment
        window: 'readonly',
        document: 'readonly',
        navigator: 'readonly',
        console: 'readonly',
        alert: 'readonly',
        location: 'readonly',
        setTimeout: 'readonly',
        setInterval: 'readonly',
        clearTimeout: 'readonly',
        clearInterval: 'readonly',
        // Libraries the legacy UI relies on as globals
        $: 'readonly',
        jQuery: 'readonly',
        d3: 'readonly',
      },
    },
    rules: {},
  },
];
