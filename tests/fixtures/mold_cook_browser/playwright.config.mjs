import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: '.',
  timeout: 15_000,
  outputDir: process.env.PLAYWRIGHT_OUTPUT_DIR ?? 'test-results',
  reporter: [['line']],
  use: { browserName: 'chromium' },
});
