export default {
  displayName: 'geneweaver-ui',
  preset: './jest.preset.js',
  setupFilesAfterEnv: ['<rootDir>/src/test-setup.ts'],
  coverageDirectory: './coverage/geneweaver-ui',
  transform: {
    '^.+\\.(ts|mjs|js|html)$': [
      'jest-preset-angular',
      {
        tsconfig: '<rootDir>/tsconfig.spec.json',
        stringifyContentPathRegex: '\\.(html|svg)$',
      },
    ],
  },
  // D3 v7 and its three dependencies ship only ES modules, which Jest must transform; every
  // other package is left alone, as before.
  transformIgnorePatterns: [
    'node_modules/(?!(?:d3|d3-[^/]+|internmap|delaunator|robust-predicates)/|.*\\.mjs$)',
  ],
  snapshotSerializers: [
    'jest-preset-angular/build/serializers/no-ng-attributes',
    'jest-preset-angular/build/serializers/ng-snapshot',
    'jest-preset-angular/build/serializers/html-comment',
  ],
  testMatch: [
    '<rootDir>/src/**/__tests__/**/*.[jt]s?(x)',
    '<rootDir>/src/**/*(*.)@(spec|test).[jt]s?(x)',
  ],
  testEnvironment: "@happy-dom/jest-environment"
};
