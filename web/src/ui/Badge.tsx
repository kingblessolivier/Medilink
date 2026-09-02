/**
 * Badge - a small pill carrying a word and a tone.
 *
 * Tone never carries meaning on its own: the child text says what the state
 * is, and the colour only reinforces it. A colour-blind user, or anyone
 * reading a phone in bright Kigali daylight, gets the same information either
 * way.
 *
 * `accent` and `warning` appear here as tinted backgrounds with dark text, not
 * as text colours. At 2.0:1 and 2.85:1 on white they are unreadable as ink;
 * behind `n900` they are exactly what a queue badge should look like.
 */

import type { ReactNode } from "react"

export type BadgeTone =
  | "primary"
  | "success"
  | "warning"
  | "danger"
  | "accent"
  | "neutral"
  | "unknown"

export type BadgeProps = {
  tone?: BadgeTone
  /** The word. Required - a badge is never colour alone. */
  children: ReactNode
  className?: string
}

const TONE: Record<BadgeTone, string> = {
  primary: "border-primary/30 bg-primary-light text-primary",
  success: "border-success/30 bg-success/10 text-success",
  warning: "border-warning/40 bg-warning/10 text-n900",
  danger: "border-danger/30 bg-danger/10 text-danger",
  accent: "border-accent/40 bg-accent/20 text-n900",
  neutral: "border-n200 bg-n100 text-n700",
  // Data we do not have. Deliberately the quietest thing on the screen: a
  // patient must be able to tell "we do not know" from "we know" at a glance,
  // without reading it.
  unknown: "border-n200 bg-n100 text-n600",
}

export function Badge({ tone = "neutral", children, className }: BadgeProps) {
  return (
    <span
      // A stable hook for tests and end-to-end selectors. The class names are
      // Tailwind utilities and will change whenever a tone is retuned; the
      // fact that this is a badge, and which tone it carries, will not.
      data-badge={tone}
      className={[
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-pill border",
        "px-2.5 py-0.5 text-label",
        TONE[tone],
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {children}
    </span>
  )
}

export default Badge
