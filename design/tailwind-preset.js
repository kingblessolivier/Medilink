/**
 * MediLink design system - Tailwind preset.
 *
 * The single source of truth for the one web app, which serves all three
 * surfaces - patient, facility workspace, platform admin.
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
 * 2. RADIUS IS MODERATE. Containers stop at 12px. `2xl` (16px) exists only
 *    for full-width surfaces - a hero or a page panel - where 12px on a
 *    600px-tall block reads as an accident rather than a decision. Pill
 *    shapes stay reserved for status chips, where the shape carries meaning.
 *
 * 3. ELEVATION IS RESTRAINED, NOT ABSENT. It used to be one shadow, which
 *    left every card looking equally inert and gave hover nothing to say.
 *    There is now a three-step scale, and the steps are small on purpose:
 *    `raised` for something you can click, `floating` for something the
 *    page is briefly about, `overlay` for something on top of the page.
 *    Borders still do the separating; shadows only ever say "this is
 *    interactive" or "this is above".
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
        // Large surfaces only: hero, page panels, the map frame. Never a card.
        "2xl": "16px",
      },

      boxShadow: {
        // Hairline. Reads as a border, not a float.
        hairline: "0 0 0 1px rgba(23, 32, 28, 0.06)",
        // Something you can click. Barely there at rest - it exists so that
        // `raised-hover` has somewhere to move FROM.
        raised:
          "0 1px 2px rgba(23, 32, 28, 0.05), 0 1px 3px -1px rgba(23, 32, 28, 0.05)",
        "raised-hover":
          "0 2px 4px rgba(23, 32, 28, 0.06), 0 6px 14px -4px rgba(23, 32, 28, 0.10)",
        // Something the page is briefly about: a hero panel, a summary block.
        floating:
          "0 1px 2px rgba(23, 32, 28, 0.04), 0 12px 32px -8px rgba(23, 32, 28, 0.12)",
        // Things that genuinely sit on top of the page.
        overlay:
          "0 1px 2px rgba(23, 32, 28, 0.04), 0 8px 24px -4px rgba(23, 32, 28, 0.10)",
        // Focus ring, applied as a shadow so it survives overflow clipping.
        //
        // 0.22 opacity measured about 1.3:1 against the page - a hint of a
        // halo rather than an indicator, and WCAG 2.2 asks for 3:1 against
        // what is next to it. At 0.9 the same ring reads as a ring. This
        // matters more here than on most products: reception staff work the
        // workspace entirely from the keyboard, so this is how they know
        // where they are.
        focus: "0 0 0 3px rgba(11, 107, 85, 0.9)",
      },

      spacing: {
        // 44px: the minimum comfortable touch target, and the height every
        // interactive control snaps to.
        touch: "2.75rem",
      },

      maxWidth: {
        prose: "68ch",
        // The reading column - a single stream of text or one list.
        content: "76rem",
        // The full working width. Wider than `content` because the discovery
        // and workspace screens lay out in columns rather than one stream,
        // and a 76rem cap on a 1440px monitor left 350px dead on each side.
        shell: "88rem",
      },

      backgroundImage: {
        // The hero. A single soft wash rather than a photograph: stock
        // imagery of smiling clinicians is the visual language of marketing,
        // and this is a tool people open when they are unwell.
        //
        // It used to be a saturated green block with white text, which made
        // the first screen of the product a solid slab of brand colour and
        // put green - the colour that means "open", "verified", "available"
        // everywhere else - on 400px of decoration. Rule 1 of the design
        // system is that green is not the interface. The hero is now a light
        // surface with green used only as an accent, so the eye still lands
        // on the search field rather than on the background.
        "hero-wash":
          "radial-gradient(120% 120% at 85% -10%, #EEF5F2 0%, #F7F9F8 45%, #FFFFFF 100%)",
        "hero-grid":
          "linear-gradient(rgba(11,107,85,0.055) 1px, transparent 1px), linear-gradient(90deg, rgba(11,107,85,0.055) 1px, transparent 1px)",
      },

      backgroundSize: {
        grid: "44px 44px",
      },

      transitionDuration: {
        // Fast enough to feel instant, slow enough to be seen.
        DEFAULT: "140ms",
      },
    },
  },
}
