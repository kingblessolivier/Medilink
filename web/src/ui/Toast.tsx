/**
 * Toast - a transient confirmation, auto-dismissed after 4 seconds.
 *
 * Only ever confirms something the user just did. Never used for anything they
 * have to act on: four seconds is not long enough to read, decide and reach,
 * and a patient who misses it has no way to bring it back.
 *
 * `role="status"` rather than `alert` for the success case - an alert
 * interrupts a screen reader mid-sentence, which is the right thing for an
 * error and the wrong thing for "Appointment booked".
 */

import { useEffect } from "react"

export type ToastVariant = "success" | "error" | "warning"

export type ToastProps = {
  variant?: ToastVariant
  message: string
  /** Milliseconds before auto-dismiss. 4000 by default; 0 disables it. */
  duration?: number
  onDismiss: () => void
}

const VARIANT: Record<ToastVariant, string> = {
  success: "border-success/30 bg-white text-n900",
  error: "border-danger/30 bg-white text-n900",
  warning: "border-warning/40 bg-white text-n900",
}

const DOT: Record<ToastVariant, string> = {
  success: "bg-success",
  error: "bg-danger",
  warning: "bg-warning",
}

export function Toast({
  variant = "success",
  message,
  duration = 4000,
  onDismiss,
}: ToastProps) {
  useEffect(() => {
    if (duration <= 0) return
    const timer = setTimeout(onDismiss, duration)
    return () => clearTimeout(timer)
  }, [duration, onDismiss])

  return (
    <div
      role={variant === "error" ? "alert" : "status"}
      className={[
        "pointer-events-auto flex animate-slide-up items-center gap-3",
        "rounded-md border px-4 py-3 text-body-lg shadow-md",
        VARIANT[variant],
      ].join(" ")}
    >
      {/* Colour never carries the meaning on its own; the dot is a second
          cue beside the border, and the message says what happened. */}
      <span
        aria-hidden="true"
        className={`h-2 w-2 shrink-0 rounded-full ${DOT[variant]}`}
      />
      <span className="min-w-0 flex-1">{message}</span>
    </div>
  )
}

export default Toast
