import { defineConfig, type Plugin } from "vite"
import { resolve } from "node:path"
import react from "@vitejs/plugin-react"
import { VitePWA } from "vite-plugin-pwa"

export default defineConfig({
  plugins: [
    react(),
    watchDesignSystem(),
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

/**
 * Restart the dev server when the design system changes.
 *
 * `design/tailwind-preset.js` lives outside this app's root, so Vite does not
 * watch it and Tailwind does not know it changed. The symptom is genuinely
 * misleading: a token you just added comes back as "The `bg-n100` class does
 * not exist", exactly as though you had typo'd it, and the page dies behind a
 * full-screen PostCSS overlay. The production build is fine the whole time,
 * which is what makes it so confusing - `npm run build` passes while the dev
 * server insists the class is missing.
 *
 * It cost a debugging session on the day before a launch. Watching the file
 * and restarting is three lines; remembering to restart by hand is not
 * something anybody should have to do twice.
 */
function watchDesignSystem(): Plugin {
  return {
    name: "medilink:watch-design-system",
    configureServer(server) {
      // `server.config.root` rather than `__dirname`: this config is loaded as
      // ESM, where `__dirname` is undefined, and the failure would be a crash
      // on startup rather than a missing feature.
      const preset = resolve(
        server.config.root,
        "../design/tailwind-preset.js",
      )
      server.watcher.add(preset)
      server.watcher.on("change", (file) => {
        if (resolve(file) !== preset) return
        server.config.logger.info(
          "\n  design system changed - restarting so Tailwind reloads it\n",
        )
        server.restart()
      })
    },
  }
}
