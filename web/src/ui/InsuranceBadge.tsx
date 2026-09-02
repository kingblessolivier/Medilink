/**
 * InsuranceBadge - whether a facility accepts an insurer.
 *
 * Three states, and the copy is fixed: "accepts [insurer]", never "you are
 * covered". What this product knows is what a facility says it accepts.
 * Whether a given patient's membership is active and paid up is a different
 * question, answered by a system MediLink is not integrated with - and a
 * patient turned away at a desk after reading "you are covered" here does not
 * make that distinction on our behalf.
 *
 * The copy keys are the ones already translated into all three languages, so
 * the wording cannot drift from the rest of the product by being retyped.
 */

import { useI18n } from "../i18n"
import { Badge } from "./Badge"

export type InsuranceStatus = "accepted" | "not-accepted" | "unknown"

export type InsuranceBadgeProps = {
  status: InsuranceStatus
  /** Insurer name, e.g. "Mutuelle". Interpolated into the label. */
  insurerName: string
  className?: string
}

export function InsuranceBadge({
  status,
  insurerName,
  className,
}: InsuranceBadgeProps) {
  const { t } = useI18n()

  if (status === "unknown") {
    return (
      <Badge tone="unknown" className={className}>
        {t("insurance_status_unknown")}
      </Badge>
    )
  }

  return (
    <Badge
      tone={status === "accepted" ? "success" : "danger"}
      className={className}
    >
      {status === "accepted"
        ? t("accepts_insurer", { insurer: insurerName })
        : t("not_accepts_insurer", { insurer: insurerName })}
    </Badge>
  )
}

export default InsuranceBadge
