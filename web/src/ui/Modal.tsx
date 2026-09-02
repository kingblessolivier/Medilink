/**
 * Modal.
 *
 *  Closes on Escape and on an overlay click, traps focus while open, and returns
 *  focus to whatever opened it. A modal that strands the keyboard behind it is
 *  worse than no modal - reception staff work this product without a mouse.
 *
 * TASK 1C SCAFFOLD - interface only, no implementation yet. Not exported from
 * index.tsx until it is built, so nothing can import it by accident.
 */

import type { ReactNode } from "react"

export type ModalProps = {
  open: boolean
  onClose: () => void
  /** Announced as the dialog's accessible name. Required. */
  title: string
  children: ReactNode
  /** The actions row, pinned to the bottom of the card. */
  footer?: ReactNode
}

export function Modal(_props: ModalProps) {
  return null
}

export default Modal
