import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In dev the UI proxies /api to the gateway; in the container nginx does the same.
const target = process.env.GATEWAY_URL || 'http://localhost:8200'

export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': { target, changeOrigin: true } } },
  test: { environment: 'jsdom', globals: true },
})
