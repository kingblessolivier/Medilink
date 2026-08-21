export default {
  plugins: {
    // Must run BEFORE tailwind so the shared design/base.css is inlined and
    // its @apply directives are processed. Without it the import is dropped
    // and both apps render unstyled.
    "postcss-import": {},
    tailwindcss: {},
    autoprefixer: {},
  },
}
