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
        // The map is a 258 KB gzipped chunk. Precaching it would push it onto
        // every phone at install time and undo the lazy import - a patient who
        // never opens the map must never pay for it. Fetched on demand, then
        // cached for a month once they have.
        globIgnores: ["**/maplibre-gl-*.{js,css}"],
        runtimeCaching: [
          {
            urlPattern: /maplibre-gl-.*\.(js|css)$/,
            handler: "CacheFirst",
            options: {
              cacheName: "map",
              expiration: { maxAgeSeconds: 60 * 60 * 24 * 30 },
            },
          },
          {
            // Tiles are large and change rarely.
            urlPattern: /^https:\/\/.*(tiles|demotiles)\..*/,
            handler: "CacheFirst",
            options: {
              cacheName: "map-tiles",
              expiration: { maxEntries: 300, maxAgeSeconds: 60 * 60 * 24 * 14 },
            },
          },
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
