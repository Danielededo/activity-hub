import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  // Tailwind 4 is CSS-first: the theme lives in src/index.css, so there is no
  // tailwind.config.js and no postcss config to keep in sync.
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // Proxying /api keeps the browser's requests same-origin in development,
    // so CORS never enters the picture.
    proxy: {
      '/api': {
        target: process.env.VITE_API_TARGET || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    // Recharts is roughly 500 kB of the bundle and is needed for the first
    // chart on the page, so it cannot be deferred. The limit sits just above
    // the real size rather than being switched off: a genuine regression still
    // trips it.
    chunkSizeWarningLimit: 650,
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './tests/setup.js',
    include: ['tests/**/*.test.{js,jsx}'],
  },
})
