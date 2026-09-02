/**
 * StatusPill - the status of one queue entry.
 *
 * The five values are the QueueEntry status field on the backend and nothing
 * else. NO_SHOW and CANCELLED share a grey on purpose: both mean "not waiting
 * any more", and separating them by hue would imply a difference the
 * receptionist does not have to act on.
 *
 * WAITING is amber rather than green because it is the state that needs
 * attention, and a board where every row is green tells a receptionist
 * nothing about where to look.
 */

import { useI18n } from "../i18n"
import { Badge, type BadgeTone } from "./Badge"

export type QueueStatus =
  | "WAITING"
  | "CALLED"
  | "SERVED"
  | "NO_SHOW"
  | "CANCELLED"

export type StatusPillProps = {
  status: QueueStatus
  className?: string
}

const TONE: Record<QueueStatus, BadgeTone> = {
  WAITING: "accent",
  CALLED: "primary",
  SERVED: "success",
  NO_SHOW: "neutral",
  CANCELLED: "neutral",
}

/** Existing keys, already translated into all three languages. */
const KEY: Record<QueueStatus, string> = {
  WAITING: "appt_status_booked",
  CALLED: "appt_status_arrived",
  SERVED: "appt_status_served",
  NO_SHOW: "appt_status_no_show",
  CANCELLED: "appt_status_cancelled",
}

export function StatusPill({ status, className }: StatusPillProps) {
  const { t } = useI18n()

  return (
    <Badge tone={TONE[status]} className={className}>
      {t(KEY[status])}
    </Badge>
  )
}

export default StatusPill
