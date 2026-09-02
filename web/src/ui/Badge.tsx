/**
 * Badge - a small pill carrying a word and a tone.
 *
 *  Absorbs `Chip` from index.tsx when implemented. Tone never carries meaning
 *  on its own: the child text says what the state is, and the colour only
 *  reinforces it. A colour-blind user, or anyone reading in bright Kigali
 *  daylight, gets the same information either way.
 *
 * TASK 1C SCAFFOLD - interface only, no implementation yet. Not exported from
 * index.tsx until it is built, so nothing can import it by accident.
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

export function Badge(_props: BadgeProps) {
  return null
}

export default Badge
