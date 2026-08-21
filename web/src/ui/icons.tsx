import type { SVGProps } from "react"

/**
 * The icon set.
 *
 * Inline SVG, not an icon package. Three reasons: a dependency for twenty
 * glyphs is 40 KB a patient on 2G pays for, tree-shaking icon libraries is
 * unreliable in practice, and drawing them here means every one is on the
 * same 24px grid with the same 1.75 stroke - which is what makes a set look
 * like a set rather than a collection.
 *
 * All are stroke-based and inherit `currentColor`, so an icon takes the
 * colour of the text it sits beside and never needs its own palette.
 *
 * `aria-hidden` by default: an icon next to a label is decoration, and a
 * screen reader announcing "location pin, 2.4 km" is worse than "2.4 km".
 * Pass an `aria-label` explicitly on the rare icon that stands alone.
 */

type IconProps = SVGProps<SVGSVGElement> & { size?: number }

function Icon({ size = 16, children, ...rest }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden={rest["aria-label"] ? undefined : true}
      focusable="false"
      {...rest}
    >
      {children}
    </svg>
  )
}

/* ------------------------------------------------------------- wayfinding */

export const IconPin = (p: IconProps) => (
  <Icon {...p}>
    <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 1 1 16 0Z" />
    <circle cx="12" cy="10" r="3" />
  </Icon>
)

export const IconRoute = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="6" cy="19" r="3" />
    <circle cx="18" cy="5" r="3" />
    <path d="M9 19h6a4 4 0 0 0 0-8H9a4 4 0 0 1 0-8" />
  </Icon>
)

export const IconSearch = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="11" cy="11" r="7" />
    <path d="m20 20-3.5-3.5" />
  </Icon>
)

/* ------------------------------------------------------------------ time */

export const IconClock = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </Icon>
)

export const IconCalendar = (p: IconProps) => (
  <Icon {...p}>
    <rect x="3" y="5" width="18" height="16" rx="2" />
    <path d="M3 10h18M8 3v4M16 3v4" />
  </Icon>
)

/* ----------------------------------------------------------------- people */

export const IconUser = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="12" cy="8" r="4" />
    <path d="M4 21a8 8 0 0 1 16 0" />
  </Icon>
)

export const IconUsers = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="9" cy="8" r="3.5" />
    <path d="M2 20a7 7 0 0 1 14 0" />
    <path d="M17 5.5a3.5 3.5 0 0 1 0 6.9M18 20a7 7 0 0 0-2.5-5.4" />
  </Icon>
)

export const IconStethoscope = (p: IconProps) => (
  <Icon {...p}>
    <path d="M6 3v5a4 4 0 0 0 8 0V3" />
    <path d="M6 3H4.5M14 3h1.5" />
    <path d="M10 12v2a5 5 0 0 0 5 5 4 4 0 0 0 4-4v-1" />
    <circle cx="19" cy="11" r="2" />
  </Icon>
)

/* ------------------------------------------------------------------ care */

export const IconHospital = (p: IconProps) => (
  <Icon {...p}>
    <path d="M4 21V8l8-5 8 5v13" />
    <path d="M2 21h20" />
    <path d="M12 9v6M9 12h6" />
  </Icon>
)

export const IconShield = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 3l7 3v6c0 4.5-3 7.8-7 9-4-1.2-7-4.5-7-9V6l7-3Z" />
  </Icon>
)

export const IconShieldCheck = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 3l7 3v6c0 4.5-3 7.8-7 9-4-1.2-7-4.5-7-9V6l7-3Z" />
    <path d="m9 12 2 2 4-4" />
  </Icon>
)

export const IconHeart = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 20s-7-4.4-7-9.3A4.2 4.2 0 0 1 12 8a4.2 4.2 0 0 1 7 2.7c0 4.9-7 9.3-7 9.3Z" />
  </Icon>
)

/* ---------------------------------------------------------------- signals */

export const IconCheck = (p: IconProps) => (
  <Icon {...p}>
    <path d="m4 12 5 5L20 6" />
  </Icon>
)

export const IconAlert = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 4 2.5 20h19L12 4Z" />
    <path d="M12 10v4M12 17.5v.01" />
  </Icon>
)

export const IconInfo = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 11v5M12 7.5v.01" />
  </Icon>
)

/**
 * The one that carries a rule rather than a meaning.
 *
 * Used wherever the answer is "we do not know" - an unreported wait, an
 * unconfirmed insurer. Deliberately a dash rather than a question mark: a
 * question mark reads as "ask us", a dash reads as "no data", and no data is
 * exactly what it means.
 */
export const IconUnknown = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M8.5 12h7" />
  </Icon>
)

/* -------------------------------------------------------------- interface */

export const IconChevronRight = (p: IconProps) => (
  <Icon {...p}>
    <path d="m9 5 7 7-7 7" />
  </Icon>
)

export const IconArrowRight = (p: IconProps) => (
  <Icon {...p}>
    <path d="M4 12h15M13 6l6 6-6 6" />
  </Icon>
)

export const IconPhone = (p: IconProps) => (
  <Icon {...p}>
    <path d="M6 3h3l2 5-2.5 1.5a12 12 0 0 0 6 6L16 13l5 2v3a2 2 0 0 1-2.2 2A17 17 0 0 1 4 5.2 2 2 0 0 1 6 3Z" />
  </Icon>
)

export const IconGlobe = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M3 12h18M12 3a15 15 0 0 1 0 18 15 15 0 0 1 0-18Z" />
  </Icon>
)

export const IconChart = (p: IconProps) => (
  <Icon {...p}>
    <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
  </Icon>
)

export const IconBell = (p: IconProps) => (
  <Icon {...p}>
    <path d="M6 9a6 6 0 1 1 12 0c0 4 1.5 5.5 1.5 5.5h-15S6 13 6 9Z" />
    <path d="M10 18a2 2 0 0 0 4 0" />
  </Icon>
)
