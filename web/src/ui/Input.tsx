/**
 * Input.
 *
 * The error state is a danger border AND `aria-invalid` - never a red outline
 * on its own, which tells a screen reader nothing and tells a colour-blind
 * user nothing either. The message itself belongs to `Field`, which owns the
 * label and the description wiring.
 */

import type { InputHTMLAttributes } from "react"

export type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  invalid?: boolean
}

export function Input({ invalid, className, ...rest }: InputProps) {
  return (
    <input
      {...rest}
      aria-invalid={invalid || undefined}
      className={["ml-field", invalid && "ml-field-invalid", className]
        .filter(Boolean)
        .join(" ")}
    />
  )
}

export default Input
