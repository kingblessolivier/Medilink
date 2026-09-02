/**
 * Spinner - the only busy indicator in the product.
 *
 * Lives in its own module because Button depends on it, and importing Button's
 * dependency back out of the barrel would make the barrel circular.
 */

const SIZE = {
  sm: "h-3 w-3 border-2",
  md: "h-4 w-4 border-2",
  lg: "h-6 w-6 border-[3px]",
} as const

export type SpinnerSize = keyof typeof SIZE

export type SpinnerProps = {
  size?: SpinnerSize
  className?: string
}

export function Spinner({ size = "md", className }: SpinnerProps) {
  return (
    <span
      // Decorative: whatever is spinning carries its own aria-busy, and a
      // screen reader announcing "image" here would add nothing.
      aria-hidden="true"
      className={[
        // `inline-block` matters. A bare <span> is display:inline, where the
        // height and width do nothing and this collapses to a 2px sliver. It
        // only ever looked right because every call site so far put it inside
        // an inline-flex button, which blockifies its children.
        "inline-block shrink-0 animate-spin rounded-full",
        // `border-current` inherits the text colour, so the spinner is the
        // right colour on a green button and on a white one without either
        // knowing about the other.
        "border-current border-t-transparent opacity-70",
        SIZE[size],
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    />
  )
}

export default Spinner
