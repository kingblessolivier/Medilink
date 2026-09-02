/**
 * InsuranceBadge - whether a facility accepts an insurer.
 *
 *  Three states, and the copy is fixed: "accepts [insurer]", never "you are
 *  covered". What this product knows is what the facility accepts. Whether a
 *  given patient's membership is active and paid up is a different question,
 *  answered by a system MediLink is not yet integrated with, and a patient who
 *  is turned away at a desk after reading "you are covered" here does not make
 *  the distinction on our behalf.
 *
 * TASK 1C SCAFFOLD - interface only, no implementation yet. Not exported from
 * index.tsx until it is built, so nothing can import it by accident.
 */

export type InsuranceStatus = "accepted" | "not-accepted" | "unknown"

export type InsuranceBadgeProps = {
  status: InsuranceStatus
  /** Insurer name, e.g. "Mutuelle". Interpolated into the label. */
  insurerName: string
  className?: string
}

export function InsuranceBadge(_props: InsuranceBadgeProps) {
  return null
}

export default InsuranceBadge
