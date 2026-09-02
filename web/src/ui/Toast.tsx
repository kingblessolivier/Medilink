/**
 * Toast - a transient confirmation, auto-dismissed after 4 seconds.
 *
 *  Only ever confirms something the user just did. Never used for anything they
 *  have to act on: four seconds is not long enough to read, decide and reach,
 *  and a patient who misses it has no way to bring it back.
 *
 * TASK 1C SCAFFOLD - interface only, no implementation yet. Not exported from
 * index.tsx until it is built, so nothing can import it by accident.
 */

export type ToastVariant = "success" | "error" | "warning"

export type ToastProps = {
  variant?: ToastVariant
  message: string
  /** Milliseconds before auto-dismiss. 4000 by default; 0 disables it. */
  duration?: number
  onDismiss: () => void
}

export function Toast(_props: ToastProps) {
  return null
}

export default Toast
