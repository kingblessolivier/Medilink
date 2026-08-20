import { Link } from "react-router-dom"
import { useI18n } from "../i18n"
import { Card, Chip } from "../ui"
import type { Provider } from "../api/types"

/**
 * A doctor, as a patient meets them.
 *
 * Two rules from docs/11 show up here:
 *
 * - **Initials, not a broken image.** Most clinicians have no photo on file.
 *   An avatar that falls back to initials is honest; a grey person-icon
 *   placeholder pretends there is something missing.
 * - **Verification is stated, not implied.** A profile is a public statement
 *   about a named person, so an unverified one says so rather than looking
 *   identical to a checked one. There are no ratings anywhere.
 */
export function DoctorCard({ doctor }: { doctor: Provider }) {
  const { t } = useI18n()
  const placement = doctor.placements?.[0]

  return (
    <Card as="article" interactive className="flex gap-3 p-4">
      <Avatar doctor={doctor} />

      <div className="min-w-0 flex-1">
        <h3 className="text-h3 leading-snug">
          <Link
            to={`/doctor/${doctor.slug}`}
            className="hover:text-primary hover:underline"
          >
            {doctor.display_name}
          </Link>
        </h3>

        {doctor.specialties.length > 0 && (
          <p className="mt-0.5 truncate text-small text-ink-muted">
            {doctor.specialties.join(" · ")}
          </p>
        )}

        {placement && (
          <p className="mt-1 truncate text-small text-ink-muted">
            {placement.facility_name}
          </p>
        )}

        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          {doctor.verified ? (
            <Chip tone="success">{t("verified")}</Chip>
          ) : (
            <Chip tone="unknown">{t("not_yet_verified")}</Chip>
          )}
          {doctor.languages.length > 0 && (
            <span className="text-caption text-ink-subtle">
              {doctor.languages.map((l) => l.toUpperCase()).join(" · ")}
            </span>
          )}
        </div>
      </div>
    </Card>
  )
}

function Avatar({ doctor }: { doctor: Provider }) {
  if (doctor.photo_url) {
    return (
      <img
        src={doctor.photo_url}
        alt=""
        loading="lazy"
        className="h-12 w-12 shrink-0 rounded-full border border-line object-cover"
      />
    )
  }

  return (
    <span
      aria-hidden="true"
      className="grid h-12 w-12 shrink-0 place-items-center rounded-full border border-primary-border bg-primary-subtle text-body font-semibold text-primary"
    >
      {doctor.initials}
    </span>
  )
}
