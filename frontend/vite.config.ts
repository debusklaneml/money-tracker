/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    // Vitest owns the unit tests under src/. The Playwright E2E specs live in
    // e2e/ and use their own runner — keep Vitest out of them so the two
    // test() globals don't collide.
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
  },
})
