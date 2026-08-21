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
        // Everything precached lands on every phone at install time, which
        // undoes a lazy import. Three things are deliberately left out:
        //
        //   maplibre-gl  258 KB gzipped, and only some journeys open a map
        //   Gallery      a developer tool
        //   routes-*     the facility workspace and the platform portal
        //
        // The last is the point of the merge: one app serves all three
        // surfaces, but a patient must not download a reception desk. Each is
        // fetched on demand and then cached, so staff pay the cost once.
        globIgnores: [
          "**/maplibre-gl-*.{js,css}",
          "**/Gallery-*.js",
          "**/routes-*.js",
        ],
        runtimeCaching: [
          {
            // The workspace and platform chunks, once somebody has actually
            // reached one of those surfaces.
            urlPattern: /\/assets\/routes-.*\.js$/,
            handler: "CacheFirst",
            options: {
              cacheName: "surfaces",
              expiration: { maxAgeSeconds: 60 * 60 * 24 * 30 },
            },
          },
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
