/**
 * Modal.
 *
 * Closes on Escape and on an overlay click, traps focus while open, and
 * returns focus to whatever opened it. A modal that strands the keyboard
 * behind it is worse than no modal - reception staff work this product without
 * touching the mouse, and a trapped tab order is how they lose their place in
 * a queue they are halfway through calling.
 *
 * The overlay click listener is on mousedown-then-mouseup over the same
 * element, not on click: a drag that starts inside the card and releases over
 * the overlay - selecting text and overshooting - would otherwise close the
 * dialog and discard what was typed.
 */

import { useCallback, useEffect, useRef, type ReactNode } from "react"

export type ModalProps = {
  open: boolean
  onClose: () => void
  /** Announced as the dialog's accessible name. Required. */
  title: string
  children: ReactNode
  /** The actions row, pinned to the bottom of the card. */
  footer?: ReactNode
}

const FOCUSABLE =
  'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])'

export function Modal({ open, onClose, title, children, footer }: ModalProps) {
  const card = useRef<HTMLDivElement>(null)
  const overlayPressed = useRef(false)
  const returnFocusTo = useRef<HTMLElement | null>(null)

  const onKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation()
        onClose()
        return
      }
      if (event.key !== "Tab" || !card.current) return

      const items = card.current.querySelectorAll<HTMLElement>(FOCUSABLE)
      if (items.length === 0) return
      const first = items[0]
      const last = items[items.length - 1]

      // Wrap by hand. Without this the tab order walks out of the dialog and
      // into the page behind it, which is still there and still clickable.
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    },
    [onClose],
  )

  useEffect(() => {
    if (!open) return

    returnFocusTo.current = document.activeElement as HTMLElement | null
    document.addEventListener("keydown", onKeyDown)

    // The page behind must not scroll under the dialog on a phone, where the
    // overlay covers the viewport and the scroll looks like a broken modal.
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = "hidden"

    card.current?.querySelector<HTMLElement>(FOCUSABLE)?.focus()

    return () => {
      document.removeEventListener("keydown", onKeyDown)
      document.body.style.overflow = previousOverflow
      returnFocusTo.current?.focus()
    }
  }, [open, onKeyDown])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-0 sm:items-center sm:p-4"
      onMouseDown={(event) => {
        overlayPressed.current = event.target === event.currentTarget
      }}
      onMouseUp={(event) => {
        if (overlayPressed.current && event.target === event.currentTarget) {
          onClose()
        }
        overlayPressed.current = false
      }}
    >
      <div
        ref={card}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="w-full max-w-[480px] animate-slide-up rounded-lg bg-white p-6 shadow-lg"
      >
        <h2 className="text-h2 text-n900">{title}</h2>
        <div className="mt-4 text-body-lg text-n700">{children}</div>
        {footer && (
          <div className="mt-6 flex flex-wrap justify-end gap-2">{footer}</div>
        )}
      </div>
    </div>
  )
}

export default Modal
