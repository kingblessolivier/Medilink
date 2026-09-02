/**
 * MediLink design system - Tailwind preset.
 *
 * The single source of truth for the one web app, which serves all three
 * surfaces - patient, facility workspace, platform admin.
 *
 * NOTHING IN THIS FILE IS A VALUE. Every entry points at a custom property
 * declared in web/src/styles/tokens.css, which is the only place a colour, a
 * size or a duration is actually written down. Changing the product's palette
 * is one edit to that file; this preset only decides what the utilities are
 * called. If you find yourself typing a hex here, it belongs in tokens.css.
 *
 * Colours are emitted as `rgb(var(--x-rgb) / <alpha-value>)` rather than
 * `var(--x)`. That is what keeps opacity modifiers alive: with a plain hex
 * custom property, `bg-primary/25` compiles to a colour the browser cannot
 * parse and the element renders transparent, silently. `npm run verify:tokens`
 * guards the hex/channel pairs those two forms depend on.
 *
 * Three rules the system encodes, because they are the ones a healthcare UI
 * gets wrong most often:
 *
 * 1. GREEN IS NOT THE INTERFACE. It carries the primary action, availability
 *    and verification - nothing else. Everything structural is neutral. A
 *    wholly green product reads as marketing, not as a tool somebody opens
 *    while worried.
 *
 * 2. SHAPE CARRIES MEANING. A pill is an action or a status; a 16px corner is
 *    a card; a 10px corner is an input. Rounding a card to a pill removes the
 *    only cue that says which is which.
 *
 * 3. AMBER IS A FILL, NEVER A LABEL. `accent` and `warning` measure 2.0:1 and
 *    2.85:1 on white - below the 3:1 a non-text control needs, let alone the
 *    4.5:1 for text. They colour a badge's background, carrying `n900` on top.
 *    The ETA is the one number a patient has to read.
 */

/** A colour that still answers to `/50`. */
const token = (name) => `rgb(var(--${name}-rgb) / <alpha-value>)`

/** Size, line height and weight, all three read from tokens.css. */
const type = (name) => [
  `var(--text-${name})`,
  {
    lineHeight: `var(--text-${name}-lh)`,
    fontWeight: `var(--text-${name}-weight)`,
  },
]

/** @type {import('tailwindcss').Config} */
export default {
  theme: {
    /* Replaced wholesale rather than extended. Tailwind's default palette is
       247 colours the design system has no opinion about, and leaving them
       reachable is how `bg-slate-100` ends up next to `bg-n100` in the same
       card. If a colour is not below, it is not in the product. */
    colors: {
      transparent: "transparent",
      current: "currentColor",
      inherit: "inherit",

      /* Not a palette colour - an absolute, and the only thing a modal
         scrim should ever be. Always used with an opacity modifier. */
      black: "rgb(0 0 0 / <alpha-value>)",
      white: token("white"),

      primary: {
        DEFAULT: token("primary"), // actions, links, active states, identity
        dark: token("primary-dark"), // hover, pressed, header backgrounds
        light: token("primary-light"), // selected rows, chips, tinted surfaces
      },

      accent: token("accent"), // queue badges, ETA, urgency - a fill only
      danger: token("danger"), // emergency, errors, destructive actions
      success: token("success"), // confirmed, attended, insurance active
      warning: token("warning"), // no-show, expiring, pending - a fill only

      n900: token("n900"), // primary text, headings
      n800: token("n800"), // dark surfaces: inverted panels, footers
      n700: token("n700"), // body copy
      n600: token("n600"), // secondary text, labels, captions
      n400: token("n400"), // placeholders, disabled text, decorative icons
      n300: token("n300"), // borders that must read: inputs, dividers
      n200: token("n200"), // default border, hairline separators
      n100: token("n100"), // page background, wells, inactive surfaces
    },

    fontFamily: {
      sans: ["var(--font-sans)"],
      /* Ticket codes and reference codes: read aloud across a reception desk,
         or typed off a paper slip. */
      mono: ["var(--font-mono)"],
    },

    /* Replaced, not extended: the default scale runs text-xs to text-9xl with
       no opinion about which is a heading. These eight are the whole product,
       and each carries its own weight and line height so `text-h1` is one
       decision rather than three classes that can disagree. */
    fontSize: {
      micro: type("micro"), // 11px - status pills, timestamps, legal
      label: type("label"), // 12px - input labels, badge text, table headers
      body: type("body"), // 14px - secondary body, table cells, hints
      "body-lg": type("body-lg"), // 16px - primary body text, descriptions
      h3: type("h3"), // 18px - card sub-sections, form group labels
      h2: type("h2"), // 24px - section headers, card titles
      h1: type("h1"), // 32px - page titles, screen headers
      /* The queue position, and nothing else in the product. */
      display: type("display"), // 72px
    },

    borderRadius: {
      none: "0",
      sm: "var(--radius-sm)", // 6px - badges, pills, tags
      DEFAULT: "var(--radius-sm)",
      md: "var(--radius-md)", // 10px - input fields, buttons
      lg: "var(--radius-lg)", // 16px - cards, panels
      pill: "var(--radius-pill)", // CTA buttons and status chips
      full: "9999px", // circles: avatars, map markers, dots
    },

    boxShadow: {
      none: "none",
      sm: "var(--shadow-sm)", // subtle card lift
      md: "var(--shadow-md)", // floating elements, modals
      lg: "var(--shadow-lg)", // phone shell, hero cards
      /* Applied as a shadow so it survives `overflow: hidden` on a scrolling
         table or a clipped card. Reception staff work the workspace entirely
         from the keyboard - this is how they know where they are. */
      focus: "var(--shadow-focus)",
      "input-focus": "var(--shadow-input-focus)",
    },

    extend: {
      spacing: {
        /* The numeric scale is deliberately absent: 4/8/12/16/24/32/40/48/80
           is already exactly Tailwind's 1/2/3/4/6/8/10/12/20, so overriding
           it would rename every `p-4` in the app to say the same thing.
           These are the two additions that carry meaning of their own. */

        /* The minimum comfortable touch target, and the height every
           interactive control snaps to. WCAG 2.5.8 asks for 24px; 44px is
           what a thumb on a phone held in one hand actually needs. */
        touch: "var(--touch-target)",

        /* Control heights, so a button's size is a token rather than an
           arbitrary value someone measured off a mock. */
        "control-sm": "var(--control-sm)",
        "control-md": "var(--control-md)",
        "control-lg": "var(--control-lg)",

        /* The named scale, for the places the roadmap speaks in names. Same
           values as the numeric steps, by construction. */
        xs: "var(--space-xs)",
        sm: "var(--space-sm)",
        md: "var(--space-md)",
        lg: "var(--space-lg)",
        xl: "var(--space-xl)",
        "2xl": "var(--space-2xl)",
      },

      maxWidth: {
        prose: "68ch",
        /* The reading column - a single stream of text, or one list. */
        content: "76rem",
        /* The full working width. Wider than `content` because discovery and
           workspace screens lay out in columns rather than one stream, and a
           76rem cap on a 1440px monitor left 350px dead on each side. */
        shell: "88rem",
      },

      backgroundImage: {
        /* The hero. A single soft wash rather than a photograph: stock imagery
           of smiling clinicians is the visual language of marketing, and this
           is a tool people open when they are unwell. Green appears only as an
           accent, so the eye lands on the search field. */
        "hero-wash":
          "radial-gradient(120% 120% at 85% -10%, var(--primary-light) 0%, var(--n100) 45%, var(--white) 100%)",
        "hero-grid":
          "linear-gradient(rgb(var(--primary-rgb) / 0.055) 1px, transparent 1px), linear-gradient(90deg, rgb(var(--primary-rgb) / 0.055) 1px, transparent 1px)",
      },

      backgroundSize: {
        grid: "44px 44px",
      },

      transitionDuration: {
        DEFAULT: "var(--duration-fast)",
        fast: "var(--duration-fast)", // hover, colour transitions
        base: "var(--duration-base)", // most interactive transitions
        slow: "var(--duration-slow)", // panels, modals, drawers
      },

      transitionTimingFunction: {
        standard: "var(--curve-standard)",
      },

      keyframes: {
        /* The queue position ticking down. The number is the product; when it
           changes, the change itself has to be visible from across a room. */
        "queue-tick": {
          "0%, 100%": { transform: "scale(1)" },
          "50%": { transform: "scale(1.08)" },
        },
        /* Toasts and modals arrive from below, never fade in place - motion
           from an edge tells you where a thing came from. */
        "slide-up": {
          from: { transform: "translateY(12px)", opacity: "0" },
          to: { transform: "translateY(0)", opacity: "1" },
        },
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
      },

      animation: {
        "queue-tick": "queue-tick 300ms var(--curve-standard)",
        "slide-up": "slide-up var(--duration-slow) var(--curve-standard)",
        "fade-in": "fade-in var(--duration-base) ease",
      },
    },
  },
}
