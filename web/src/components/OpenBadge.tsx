import { useI18n } from "../i18n"
import type { Facility } from "../api/types"

export function OpenBadge({ facility }: { facility: Facility }) {
  const { t } = useI18n()

  if (!facility.is_open) {
    return (
      <span className="text-body text-n700">
        {facility.opens_at
          ? t("closed_opens_at", { time: facility.opens_at })
          : t("closed")}
      </span>
    )
  }

  // A patient must not travel to a door that shuts on arrival.
  if (facility.closing_soon && facility.closes_at) {
    return (
      <span className="text-body font-medium text-warning">
        {t("closing_soon", { time: facility.closes_at })}
      </span>
    )
  }

  return (
    <span className="text-body text-n700">
      {facility.closes_at
        ? t("open_until", { time: facility.closes_at })
        : ""}
    </span>
  )
}
