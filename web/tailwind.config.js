import medilink from "../design/tailwind-preset.js"

/**
 * NOTE: editing `../design/tailwind-preset.js` needs a dev-server RESTART.
 *
 * It lives outside this app's root, so Vite does not watch it and Tailwind
 * does not know it changed. The symptom is confusing: a token you just added
 * comes back as "The `shadow-raised` class does not exist", as though you had
 * typo'd it. `npm run dev` again and it is there.
 */

/** @type {import('tailwindcss').Config} */
export default {
  presets: [medilink],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
}
