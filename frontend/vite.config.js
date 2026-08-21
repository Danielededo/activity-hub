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
    // trips it, and raising it is a decision with a reason attached.
    //
    // 650 -> 680 when the fitness-and-fatigue chart landed. It is a line chart
    // on the dashboard, so Recharts' line renderer moved from the lazy
    // activity-detail chunk into the eager one: the entry grew 24 kB and
    // WorkoutDetail's chunk halved, 33 kB to 16 kB. The split still earns its
    // keep — the route map and the per-activity traces stay deferred.
    chunkSizeWarningLimit: 680,
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './tests/setup.js',
    include: ['tests/**/*.test.{js,jsx}'],
  },
})
