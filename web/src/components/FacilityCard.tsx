import { Link } from "react-router-dom"
import { useI18n } from "../i18n"
import { formatDistance } from "../lib/format"
import { Card, Chip } from "../ui"
import { IconHospital, IconPin, IconRoute } from "../ui/icons"
import type { Facility } from "../api/types"
import { WaitLine } from "./WaitLine"

/**
 * The unit of healthcare discovery.
 *
 * Answers, in reading order, the three questions a patient has before they
 * travel: can I get there, will they take my insurance, and how long will I
 * wait. Everything else is on the facility page.
 */

const LEVEL_LABEL: Record<string, string> = {
  health_post: "Health post",
  health_centre: "Health centre",
  district_hospital: "District hospital",
  referral_hospital: "Referral hospital",
  clinic: "Clinic",
  pharmacy: "Pharmacy",
}

type Props = {
  facility: Facility
  insurerName?: string
  /** Highlighted because the corresponding map marker is selected. */
  selected?: boolean
  onHighlight?: (slug: string | null) => void
}

export function FacilityCard({
  facility,
  insurerName,
  selected = false,
  onHighlight,
}: Props) {
  const { t } = useI18n()

  const distance = formatDistance(facility.distance_m, t("distance_nearby"))

  return (
    <Card
      as="article"
      interactive
      data-selected={selected || undefined}
      onMouseEnter={() => onHighlight?.(facility.slug)}
      onMouseLeave={() => onHighlight?.(null)}
            // flex-col + mt-auto on the actions: in a grid, tiles stretch to the
      // tallest in the row, and without this the buttons floated at different
      // heights across a row - which reads as misalignment, not as content.
      className={
        "flex h-full flex-col p-4 " +
        (selected ? "border-primary-border bg-primary-subtle/40" : "")
      }
    >
      <div className="flex items-start gap-3">
        {/* A fixed anchor at the top-left of every card. It is what makes a
            grid of these scan as a grid rather than as paragraphs. */}
        <span className="ml-icon-plate bg-primary-subtle text-primary">
          <IconHospital size={18} />
        </span>

        <div className="min-w-0 flex-1">
          <h3 className="text-h3 leading-snug">
            <Link
              to={`/facility/${facility.slug}`}
              className="hover:text-primary hover:underline"
            >
              {facility.name}
            </Link>
          </h3>
          <p className="mt-0.5 truncate text-small text-ink-muted">
            {LEVEL_LABEL[facility.level] ?? facility.level}
            {facility.sector ? ` · ${facility.sector}` : ""}
          </p>
        </div>

        {/* Hidden, not blanked: a district search has no distance to show,
            and an empty slot reads as a value that failed to load. */}
        {distance && (
          <span className="flex shrink-0 items-center gap-1 text-small font-medium tabular-nums text-ink-muted">
            <IconPin size={14} className="text-ink-subtle" />
            {distance}
          </span>
        )}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1.5">
        <OpenState facility={facility} />
        {insurerName && (
          <Chip tone={facility.accepts_insurer ? "success" : "unknown"}>
            {facility.accepts_insurer
              ? t("accepts", { insurer: insurerName })
              : t("does_not_accept", { insurer: insurerName })}
          </Chip>
        )}
      </div>

      {/* The OpenState chip above already says the facility is closed, and
          `wait.status === "closed"` renders the same word again - so a shut
          facility read "Closed · Closed". The wait line has nothing to add
          once the door is shut. */}
      {facility.wait.status !== "closed" && (
        <WaitLine wait={facility.wait} className="mt-2.5" />
      )}

      <div className="mt-4 flex flex-wrap items-center gap-2 pt-0 [&]:mt-auto">
        <a
          className="ml-btn-secondary ml-btn-sm"
          href={`https://www.google.com/maps/dir/?api=1&destination=${facility.location.lat},${facility.location.lng}`}
          target="_blank"
          rel="noreferrer"
        >
          <IconRoute size={15} />
          {t("directions")}
        </a>
        <Link
          to={`/facility/${facility.slug}`}
          className="ml-btn-tertiary ml-btn-sm"
        >
          {t("view_facility")}
        </Link>
        {facility.bookable && (
          <Link
            to={`/facility/${facility.slug}/book`}
            className="ml-btn-primary ml-btn-sm ml-auto"
          >
            {t("book")}
          </Link>
        )}
      </div>
    </Card>
  )
}

function OpenState({ facility }: { facility: Facility }) {
  const { t } = useI18n()

  if (!facility.is_open) {
    return (
      <Chip tone="neutral">
        {facility.opens_at
          ? t("closed_opens_at", { time: facility.opens_at })
          : t("closed")}
      </Chip>
    )
  }

  // A patient must not travel to a door that shuts on arrival.
  if (facility.closing_soon && facility.closes_at) {
    return (
      <Chip tone="warning">{t("closing_soon", { time: facility.closes_at })}</Chip>
    )
  }

  return (
    <Chip tone="success">
      {facility.closes_at ? t("open_until", { time: facility.closes_at }) : t("open")}
    </Chip>
  )
}
