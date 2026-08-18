import { Link } from "react-router-dom"
import { useI18n } from "../i18n"
import { formatDistance } from "../lib/format"
import type { Facility } from "../api/types"
import { OpenBadge } from "./OpenBadge"
import { WaitLine } from "./WaitLine"

type Props = {
  facility: Facility
  insurerName?: string
}

export function FacilityCard({ facility, insurerName }: Props) {
  const { t } = useI18n()

  return (
    <article className="card mb-3">
      <header className="flex items-start justify-between gap-2">
        <h3 className="font-semibold leading-tight">
          <Link to={`/facility/${facility.slug}`} className="hover:underline">
            {facility.name}
          </Link>
        </h3>
        <span className="shrink-0 text-sm text-neutral-500">
          {formatDistance(facility.distance_m, t("distance_nearby"))}
        </span>
      </header>

      <div className="mt-0.5">
        <OpenBadge facility={facility} />
      </div>

      {insurerName && (
        <p
          className={
            facility.accepts_insurer
              ? "mt-1 text-sm text-success"
              : "mt-1 text-sm text-neutral-500"
          }
        >
          {/* Never encode meaning in colour alone - the word carries it. */}
          {facility.accepts_insurer
            ? t("accepts", { insurer: insurerName })
            : t("does_not_accept", { insurer: insurerName })}
        </p>
      )}

      <WaitLine wait={facility.wait} />

      <div className="mt-3 flex gap-2">
        <a
          className="btn-secondary flex-1"
          href={`https://www.google.com/maps/dir/?api=1&destination=${facility.location.lat},${facility.location.lng}`}
          target="_blank"
          rel="noreferrer"
        >
          {t("directions")}
        </a>
        {facility.bookable && (
          <Link className="btn-primary flex-1" to={`/facility/${facility.slug}`}>
            {t("book")}
          </Link>
        )}
      </div>
    </article>
  )
}
