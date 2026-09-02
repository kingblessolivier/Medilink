import medilink from "../design/tailwind-preset.js"

/**
 * Editing `../design/tailwind-preset.js` used to need a manual dev-server
 * restart: it lives outside this app's root, so Vite does not watch it and
 * Tailwind does not know it changed. The symptom was thoroughly misleading -
 * a token you had just added came back as "The `bg-n100` class does not
 * exist", exactly as though you had typo'd it, while `npm run build` passed.
 *
 * `watchDesignSystem()` in vite.config.ts now watches the file and restarts
 * the server for you. If you ever see that error again, the first thing to
 * check is whether the dev server you are looking at predates the change.
 */

/** @type {import('tailwindcss').Config} */
export default {
  presets: [medilink],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
}
