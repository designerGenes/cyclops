import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: '/Users/jadennation/DEV/01_active_projects/cyclops/apps/coordinator-web/src/test/setup.ts',
    include: ['/Users/jadennation/DEV/01_active_projects/cyclops/apps/coordinator-web/src/test/**/*.test.tsx'],
    globals: true,
  },
  server: {
    port: 5173,
  },
});
