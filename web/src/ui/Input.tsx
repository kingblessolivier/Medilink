/**
 * Input.
 *
 *  Absorbs `TextInput` from index.tsx when implemented. Border 1.5px n300;
 *  focus takes the primary border plus the tinted 3px ring held in
 *  `--shadow-input-focus`. The error state is a danger border AND a message -
 *  never a red outline on its own, which tells a screen reader nothing.
 *
 * TASK 1C SCAFFOLD - interface only, no implementation yet. Not exported from
 * index.tsx until it is built, so nothing can import it by accident.
 */

import type { InputHTMLAttributes } from "react"

export type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  invalid?: boolean
}

export function Input(_props: InputProps) {
  return null
}

export default Input
