/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: "#0f766e",
        success: "#15803d",
        warning: "#b45309",
        danger: "#b91c1c",
      },
      minHeight: { touch: "44px" },
    },
  },
  plugins: [],
}
