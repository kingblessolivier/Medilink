/**
 * Select.
 *
 * Styled to match Input exactly - same height, same border, same focus ring -
 * because a form where the text field and the dropdown are different shapes
 * reads as two forms stitched together.
 *
 * The chevron is drawn rather than left to the platform: the native arrow is a
 * different size, colour and inset on every browser, and it is the one part of
 * a select the page is allowed to restyle.
 */

import type { ReactNode, SelectHTMLAttributes } from "react"

export type SelectProps = SelectHTMLAttributes<HTMLSelectElement> & {
  invalid?: boolean
  children: ReactNode
}

export function Select({ invalid, className, children, ...rest }: SelectProps) {
  return (
    <div className="relative">
      <select
        {...rest}
        aria-invalid={invalid || undefined}
        className={[
          "ml-field appearance-none pr-9",
          invalid && "ml-field-invalid",
          className,
        ]
          .filter(Boolean)
          .join(" ")}
      >
        {children}
      </select>
      <svg
        aria-hidden="true"
        viewBox="0 0 20 20"
        className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-n600"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M6 8l4 4 4-4" />
      </svg>
    </div>
  )
}

export default Select
