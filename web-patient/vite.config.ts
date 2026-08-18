import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import { VitePWA } from "vite-plugin-pwa"

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      manifest: false, // served from public/manifest.json
      workbox: {
        runtimeCaching: [
          {
            // Fresh when online, usable when not.
            urlPattern: /\/api\/v1\/facilities\/nearby/,
            handler: "NetworkFirst",
            options: {
              cacheName: "nearby",
              expiration: { maxAgeSeconds: 60 * 60 * 24 },
            },
          },
          {
            urlPattern: /\/api\/v1\/(insurers|service-types|districts)/,
            handler: "CacheFirst",
            options: {
              cacheName: "reference",
              expiration: { maxAgeSeconds: 60 * 60 * 24 * 7 },
            },
          },
          {
            // A cached queue position is actively harmful: it would tell a
            // patient to stay home while they are being called. Phase 2.
            urlPattern: /\/api\/v1\/queue\//,
            handler: "NetworkOnly",
          },
        ],
      },
    }),
  ],
  server: {
    port: 5173,
    proxy: { "/api": "http://localhost:8000" },
  },
})
