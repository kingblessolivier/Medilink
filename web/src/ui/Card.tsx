/**
 * Card.
 *
 * The only elevated surface in the product. Used for facilities, doctors,
 * appointments and summaries - everything else is a list, a table or a
 * section, and reaching for a card to group two paragraphs is how a page ends
 * up as a stack of boxes with no hierarchy left.
 *
 * `padding` deliberately has no default. Most call sites set their own with a
 * className, and a default here would silently double it.
 */

import type { ReactNode } from "react"

export type CardVariant = "default" | "interactive" | "selected" | "danger"
export type CardPadding = "sm" | "md" | "lg"

export type CardProps = {
  variant?: CardVariant
  /** sm 12px | md 24px | lg 32px. Omit to control padding from `className`. */
  padding?: CardPadding
  /** Render as something other than a div - `article` in a list, `li` in a ul. */
  as?: "div" | "article" | "section" | "li" | "label"
  /**
   * Deprecated spelling of `variant="interactive"`, kept because call sites
   * across the app still use it.
   *
   * It has to be destructured rather than left to fall through: `...rest` is
   * spread onto the element, so an unrecognised `interactive` lands in the
   * DOM as a bare attribute, React warns about a non-boolean value, and the
   * card silently loses the hover it was asking for.
   */
  interactive?: boolean
  className?: string
  children: ReactNode
} & Record<string, unknown>

const VARIANT: Record<CardVariant, string> = {
  default: "border-n200 bg-white",
  // It lifts rather than only tinting. A flat hover on a flat card is easy to
  // miss, and these are the cards a patient scans in a hurry. The movement is
  // 1px - enough to notice, not enough to shift the layout underneath it.
  interactive:
    "border-n200 bg-white shadow-sm transition-all duration-fast hover:-translate-y-px hover:border-n300 hover:shadow-md focus-within:border-primary focus-within:shadow-md",
  // 1.5px, not 1px: at 1px the selected border is the same weight as the
  // unselected one and the only difference left is hue, which is exactly the
  // cue a colour-blind user does not get.
  selected: "border-[1.5px] border-primary bg-primary-light",
  danger: "border-danger/30 bg-danger/10",
}

const PADDING: Record<CardPadding, string> = {
  sm: "p-3", // 12px
  md: "p-6", // 24px
  lg: "p-8", // 32px
}

export function Card({
  variant,
  padding,
  as: Tag = "div",
  interactive = false,
  className,
  children,
  ...rest
}: CardProps) {
  const resolved: CardVariant =
    variant ?? (interactive ? "interactive" : "default")

  return (
    <Tag
      {...rest}
      className={[
        "rounded-lg border",
        VARIANT[resolved],
        padding && PADDING[padding],
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {children}
    </Tag>
  )
}

export default Card
