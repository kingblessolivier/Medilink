/**
 * MediLink design system - Tailwind preset.
 *
 * Shared by web-patient and web-provider so the two surfaces cannot drift.
 * Both import it in their tailwind.config.js via `presets: [medilink]`.
 *
 * Three rules this preset deliberately encodes, because they are the ones a
 * healthcare UI gets wrong most often:
 *
 * 1. GREEN IS NOT THE INTERFACE. It carries availability, verification,
 *    success and the primary action - nothing else. Everything structural is
 *    neutral. A wholly green product reads as marketing, not as a tool
 *    somebody uses while worried.
 *
 * 2. RADIUS IS MODERATE. The scale stops at 12px for containers. Pill shapes
 *    are reserved for status chips, where the shape itself carries meaning.
 *
 * 3. ELEVATION IS ALMOST FLAT. One functional shadow for overlays, one
 *    hairline for everything else. Borders separate; shadows only float.
 */

/** @type {import('tailwindcss').Config} */
export default {
  theme: {
    extend: {
      colors: {
        // Structure. Most of the product is built from these.
        canvas: "#F7F9F8", // page background
        surface: "#FFFFFF", // cards, sheets, tables
        "surface-sunken": "#F2F5F3", // wells, inactive tabs, table headers
        line: "#E3E8E5", // default border
        "line-strong": "#CDD6D1", // input borders, dividers that must read

        ink: "#17201C", // primary text
        // Darkened from #66716C, which measured 4.44 against danger-subtle
        // under ErrorState - just under AA, and it had to move anyway to
        // leave a visible gap above ink-subtle once that was fixed.
        "ink-muted": "#4F5A55", // secondary text - 7.18 on surface
        // Was #8B948F, which measured 3.12 on surface - well under AA on
        // text a patient has to read. 4.77 on surface, 4.52 on sunken.
        // NOT for use on a tinted status background: nothing clears 4.5
        // there without collapsing into ink-muted. Those surfaces carry
        // their own text colour (text-danger, text-info) instead.
        "ink-subtle": "#69726D", // captions, placeholders, stale data

        primary: {
          DEFAULT: "#0B6B55",
          hover: "#095A47",
          active: "#07513F",
          subtle: "#E7F1EE", // tinted background for selected rows
          border: "#B7D5CB",
        },

        // Status. Each has a subtle background so a chip needs no shadow.
        success: { DEFAULT: "#0B6B55", subtle: "#E7F1EE", border: "#B7D5CB" },
        warning: { DEFAULT: "#94620A", subtle: "#FBF2DE", border: "#E8D3A0" },
        danger: { DEFAULT: "#A3342B", subtle: "#FBEDEB", border: "#EFC7C2" },
        info: { DEFAULT: "#1F5F80", subtle: "#E8F1F6", border: "#BBD5E3" },

        // Unknown data. Deliberately the quietest thing on the screen: a
        // patient must be able to tell "we do not know" from "we know" at a
        // glance, without reading. See the wait-status rule in docs/04.
        // "Not confirmed" is the honesty label - the quietest thing on the
        // screen, but a patient still has to be able to READ it. #8B948F
        // measured 2.84 on its own subtle background.
        unknown: { DEFAULT: "#69726D", subtle: "#F2F5F3", border: "#E3E8E5" },
      },

      fontFamily: {
        sans: [
          "Inter",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
        // Ticket codes, queue numbers, reference codes - anything read aloud
        // across a reception desk or typed from a paper slip.
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },

      fontSize: {
        // A restrained scale. Healthcare screens carry a lot of information;
        // oversized type pushes it below the fold rather than clarifying it.
        caption: ["0.75rem", { lineHeight: "1rem", letterSpacing: "0.01em" }],
        small: ["0.8125rem", { lineHeight: "1.25rem" }],
        body: ["0.9375rem", { lineHeight: "1.5rem" }],
        "body-lg": ["1rem", { lineHeight: "1.625rem" }],
        h3: ["1.0625rem", { lineHeight: "1.5rem", letterSpacing: "-0.006em" }],
        h2: ["1.3125rem", { lineHeight: "1.75rem", letterSpacing: "-0.012em" }],
        h1: ["1.75rem", { lineHeight: "2.125rem", letterSpacing: "-0.018em" }],
        display: ["2.5rem", { lineHeight: "2.875rem", letterSpacing: "-0.024em" }],
        // The one intentionally enormous thing in the product: a queue
        // position, which must be readable at arm's length in a waiting room.
        queue: ["4.5rem", { lineHeight: "1", letterSpacing: "-0.03em" }],
      },

      borderRadius: {
        sm: "4px",
        DEFAULT: "6px",
        md: "8px",
        lg: "10px",
        xl: "12px", // containers stop here
      },

      boxShadow: {
        // Hairline. Reads as a border, not a float.
        hairline: "0 0 0 1px rgba(23, 32, 28, 0.06)",
        // The only real elevation: things that genuinely sit above the page.
        overlay:
          "0 1px 2px rgba(23, 32, 28, 0.04), 0 8px 24px -4px rgba(23, 32, 28, 0.10)",
        // Focus ring, applied as a shadow so it survives overflow clipping.
        focus: "0 0 0 3px rgba(11, 107, 85, 0.22)",
      },

      spacing: {
        // 44px: the minimum comfortable touch target, and the height every
        // interactive control snaps to.
        touch: "2.75rem",
      },

      maxWidth: {
        prose: "68ch",
        content: "76rem",
      },

      transitionDuration: {
        // Fast enough to feel instant, slow enough to be seen.
        DEFAULT: "140ms",
      },
    },
  },
}
