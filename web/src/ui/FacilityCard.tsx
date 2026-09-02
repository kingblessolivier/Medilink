/**
 * FacilityCard - one facility in a list of results.
 *
 * Presentational only. It takes a shape that is already resolved and renders
 * it; deciding what "accepted" means, or where the distance came from, belongs
 * to the screen above it.
 *
 * The wait badge is amber when a live figure exists and a quiet grey "Wait
 * time not available" when it does not. Those two states must never be
 * confusable at a glance - which is why the unknown case is not a dash, not an
 * empty slot, and not a lighter shade of the same amber.
 */

import { Badge } from "./Badge"
import { Button } from "./Button"
import { Card } from "./Card"
import { InsuranceBadge, type InsuranceStatus } from "./InsuranceBadge"
import { useI18n } from "../i18n"

export type FacilityCardProps = {
  name: string
  slug: string
  distanceKm: number | null
  /** Null when the facility publishes no hours. */
  hoursLabel: string | null
  /** Null when no live queue data is reported. Never estimated. */
  waitMinutes: number | null
  insurerName: string | null
  insuranceStatus: InsuranceStatus
  onBook?: () => void
}

export function FacilityCard({
  name,
  distanceKm,
  hoursLabel,
  waitMinutes,
  insurerName,
  insuranceStatus,
  onBook,
}: FacilityCardProps) {
  const { t } = useI18n()

  return (
    <Card as="article" variant="interactive" className="p-4">
      <h3 className="text-h3 text-n900">{name}</h3>

      <p className="mt-1 text-body text-n600">
        {distanceKm !== null && <>{distanceKm.toFixed(1)} km</>}
        {distanceKm !== null && hoursLabel !== null && " · "}
        {hoursLabel}
      </p>

      <div className="mt-3 flex flex-wrap gap-2">
        {waitMinutes === null ? (
          <Badge tone="unknown">{t("queue_eta_unknown")}</Badge>
        ) : (
          <Badge tone="accent">{t("wait_about", { minutes: waitMinutes })}</Badge>
        )}

        {insurerName && (
          <InsuranceBadge status={insuranceStatus} insurerName={insurerName} />
        )}
      </div>

      {onBook && (
        <Button variant="primary" size="sm" className="mt-4" onClick={onBook}>
          {t("book")}
        </Button>
      )}
    </Card>
  )
}

export default FacilityCard
