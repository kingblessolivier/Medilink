/**
 * FacilityCard - one facility in a list of results.
 *
 *  Absorbs components/FacilityCard.tsx when implemented. The wait badge is amber
 *  when a live figure exists and muted "Wait time not available" when it does
 *  not; those two states must never be confusable at a glance.
 *
 * TASK 1C SCAFFOLD - interface only, no implementation yet. Not exported from
 * index.tsx until it is built, so nothing can import it by accident.
 */

export type FacilityCardProps = {
  name: string
  slug: string
  distanceKm: number | null
  /** Null when the facility publishes no hours. */
  hoursLabel: string | null
  /** Null when no live queue data is reported. Never estimated. */
  waitMinutes: number | null
  insurerName: string | null
  insuranceStatus: "accepted" | "not-accepted" | "unknown"
  onBook?: () => void
}

export function FacilityCard(_props: FacilityCardProps) {
  return null
}

export default FacilityCard
