import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: '/Users/jadennation/DEV/01_active_projects/cyclops/apps/coordinator-web/e2e',
  use: {
    baseURL: 'http://127.0.0.1:4173',
    trace: 'on-first-retry',
  },
  webServer: {
    command: 'pnpm build && pnpm preview --host 127.0.0.1 --port 4173',
    cwd: '/Users/jadennation/DEV/01_active_projects/cyclops/apps/coordinator-web',
    port: 4173,
    reuseExistingServer: true,
  },
  projects: [
    {
      name: 'Mobile Safari',
      use: { ...devices['iPhone 13'] },
    },
  ],
});
