/**
 * StatusPill - the status of one queue entry.
 *
 *  The five values are the QueueEntry status field on the backend and nothing
 *  else. NO_SHOW and CANCELLED share a grey on purpose: both mean "not waiting
 *  any more", and distinguishing them by hue would imply a difference the
 *  receptionist does not need to act on.
 *
 * TASK 1C SCAFFOLD - interface only, no implementation yet. Not exported from
 * index.tsx until it is built, so nothing can import it by accident.
 */

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

export function StatusPill(_props: StatusPillProps) {
  return null
}

export default StatusPill
