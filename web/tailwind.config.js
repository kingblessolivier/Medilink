import medilink from "../design/tailwind-preset.js"

/** @type {import('tailwindcss').Config} */
export default {
  presets: [medilink],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
}
