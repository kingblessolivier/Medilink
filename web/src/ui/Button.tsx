/**
 * Button.
 *
 * Every action in the product is one of four things, and the variant says
 * which: `primary` is the one thing this screen is for, `secondary` is a real
 * alternative, `ghost` is a way out, `danger` destroys something.
 *
 * Two details here are requirements rather than styling:
 *
 * - LOADING LOCKS THE WIDTH. The spinner replaces the label in place instead
 *   of pushing it sideways, because a button that resizes mid-tap moves out
 *   from under the thumb that is already travelling towards it. The label
 *   stays in the DOM, invisible, holding the box open.
 *
 * - LOADING DISABLES. A patient on a slow connection taps a submit button
 *   twice when nothing happens the first time, and the second tap books a
 *   second appointment. `disabled` is set from `loading` here, not left to
 *   each call site to remember.
 */

import type { ButtonHTMLAttributes, ReactNode } from "react"
import { Spinner } from "./Spinner"

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger"
export type ButtonSize = "sm" | "md" | "lg"

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant
  size?: ButtonSize
  /** Shows a spinner, locks the width and disables the button. */
  loading?: boolean
  /** A square control holding a single icon. Keeps the height as its width. */
  iconOnly?: boolean
  /** Stretch to the container. The usual shape on a phone. */
  full?: boolean
  children?: ReactNode
}

const VARIANT: Record<ButtonVariant, string> = {
  primary: "bg-primary text-white hover:bg-primary-dark active:bg-primary-dark",
  secondary:
    "border border-n300 bg-white text-n900 hover:bg-n100 active:bg-n200",
  ghost: "text-primary hover:bg-primary-light active:bg-primary-light",
  // Outlined rather than filled: a destructive action should be reachable
  // without being the loudest thing on the screen.
  danger: "border border-danger/30 bg-white text-danger hover:bg-danger/10",
}

const SIZE: Record<ButtonSize, string> = {
  // `ml-control-sm` carries the coarse-pointer bump back to 44px; see
  // design/base.css. Height cannot be a plain `h-control-sm` here for that
  // reason - the media query has to be able to win.
  sm: "ml-control-sm px-3 text-body",
  md: "h-control-md px-4 text-body",
  lg: "h-control-lg px-6 text-body-lg",
}

const SPINNER_SIZE = { sm: "sm", md: "md", lg: "lg" } as const

export function Button({
  variant = "secondary",
  size = "md",
  loading = false,
  iconOnly = false,
  full = false,
  disabled,
  children,
  className,
  ...rest
}: ButtonProps) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      // A spinner alone tells a screen reader nothing.
      aria-busy={loading || undefined}
      className={[
        "relative inline-flex items-center justify-center gap-2 rounded-pill",
        "font-medium transition-colors duration-fast",
        // 0.97 rather than a colour change: on a phone the finger covers the
        // button, so the only feedback the user can actually see is the edge
        // moving.
        "active:scale-[0.97]",
        "disabled:cursor-not-allowed disabled:opacity-45 disabled:active:scale-100",
        VARIANT[variant],
        SIZE[size],
        iconOnly && "aspect-square px-0",
        full && "w-full",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {loading && (
        <span className="absolute inset-0 grid place-items-center">
          <Spinner size={SPINNER_SIZE[size]} />
        </span>
      )}
      {/* Kept in the DOM while loading so the button does not change width.
          `invisible` rather than `hidden`: hidden would collapse the box. */}
      <span
        className={[
          "inline-flex items-center gap-2",
          loading && "invisible",
        ]
          .filter(Boolean)
          .join(" ")}
      >
        {children}
      </span>
    </button>
  )
}

export default Button
