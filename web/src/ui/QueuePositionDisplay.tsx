/**
 * QueuePositionDisplay - the most important component in the product.
 *
 *  It exists to produce one sentence honestly: "You are number 8. Leave home by
 *  10:15." Three rules, and none of them are styling:
 *
 *  - A NULL ETA RENDERS "Wait time not available". Not a placeholder, not
 *    "calculating...", not an estimate from an average. A fabricated number
 *    destroys trust permanently, and it is the one thing this product cannot
 *    recover from.
 *  - A NULL leaveHomeBy HIDES THE SECTION ENTIRELY. There is no honest way to
 *    render half of a departure time.
 *  - STALE DATA SAYS SO. Past two minutes without an update, the component
 *    shows how old the number is, because a queue position that stopped
 *    updating looks exactly like one that did not.
 *
 * TASK 1C SCAFFOLD - interface only, no implementation yet. Not exported from
 * index.tsx until it is built, so nothing can import it by accident.
 */

export type QueuePositionDisplayProps = {
  /** Places ahead of this patient, counted live. Never stored. */
  position: number
  /** Null whenever the facility reports no live queue data. */
  etaMinutes: number | null
  /** Null unless an ETA and a travel time are both known. */
  leaveHomeBy: string | null
  totalAhead: number
  totalSeen: number
  updatedAt: Date
}

export function QueuePositionDisplay(_props: QueuePositionDisplayProps) {
  return null
}

export default QueuePositionDisplay
