import { Link, useParams } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { api } from "../api/client"
import { useI18n } from "../i18n"
import { specialtyNames } from "../lib/specialty"
import { Card, Chip, ErrorState, ListSkeleton, Notice } from "../ui"
import type { Provider } from "../api/types"

const LANGUAGE_NAME: Record<string, string> = {
  rw: "Kinyarwanda",
  en: "English",
  fr: "Francais",
  sw: "Kiswahili",
}

/**
 * A doctor's profile.
 *
 * Deliberately sparse. This is a public page about a named person, so it
 * carries only what a facility has told us and a human has checked: who they
 * are, what they practise, where, and in which languages.
 *
 * No ratings, no reviews, no qualifications we have not verified. An
 * unverified profile says so plainly rather than looking like a checked one.
 */
export function DoctorProfile() {
  const { slug = "" } = useParams()
  const { t, lang } = useI18n()

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["provider", slug],
    queryFn: () => api.provider(slug),
    staleTime: 5 * 60_000,
  })

  if (isLoading) {
    return (
      <div className="ml-page py-6">
        <ListSkeleton rows={2} />
      </div>
    )
  }

  if (isError || !data) {
    return (
      <div className="ml-page py-6">
        <ErrorState
          title={t("error_generic")}
          action={
            <button className="ml-btn-secondary ml-btn-sm" onClick={() => refetch()}>
              {t("retry")}
            </button>
          }
        />
      </div>
    )
  }

  return (
    <div className="ml-page py-6 pb-24">
      <Link to="/doctors" className="text-small font-medium text-primary">
        {t("back")}
      </Link>

      <header className="mt-3 flex flex-wrap items-start gap-4">
        <Avatar doctor={data} />
        <div className="min-w-0 flex-1">
          <h1 className="text-h1">{data.display_name}</h1>
          {data.specialties.length > 0 && (
            <p className="mt-1 text-body-lg text-ink-muted">
              {specialtyNames(data.specialties, lang)}
            </p>
          )}
          <div className="mt-2 flex flex-wrap gap-1.5">
            {data.verified ? (
              <Chip tone="success">{t("verified")}</Chip>
            ) : (
              <Chip tone="unknown">{t("not_yet_verified")}</Chip>
            )}
            {data.languages.map((code) => (
              <Chip key={code} tone="neutral">
                {LANGUAGE_NAME[code] ?? code.toUpperCase()}
              </Chip>
            ))}
          </div>
        </div>
      </header>

      {!data.verified && (
        <div className="mt-4">
          <Notice tone="warning">{t("doctor_unverified_note")}</Notice>
        </div>
      )}

      {data.bio_en && (
        <section className="ml-section">
          <h2 className="ml-label mb-2">{t("about")}</h2>
          <p className="max-w-prose text-body text-ink-muted">{data.bio_en}</p>
        </section>
      )}

      <section className="ml-section">
        <h2 className="ml-label mb-3">{t("practises_at")}</h2>

        {data.placements.length === 0 ? (
          <p className="text-body text-ink-muted">{t("no_placements")}</p>
        ) : (
          <div className="space-y-3">
            {data.placements.map((placement) => (
              <Card key={placement.facility_slug} className="p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="text-h3">
                      <Link
                        to={`/facility/${placement.facility_slug}`}
                        className="hover:text-primary hover:underline"
                      >
                        {placement.facility_name}
                      </Link>
                    </h3>
                    <p className="mt-0.5 text-small text-ink-muted">
                      {placement.district}
                      {placement.role_title ? ` · ${placement.role_title}` : ""}
                    </p>
                  </div>
                  <Link
                    to={`/facility/${placement.facility_slug}/book`}
                    className="ml-btn-primary ml-btn-sm"
                  >
                    {t("book")}
                  </Link>
                </div>

                {placement.services.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {placement.services.map((service) => (
                      <Link
                        key={service}
                        to={`/service/${service}`}
                        className="ml-chip-neutral hover:border-line-strong"
                      >
                        {service.replace(/_/g, " ")}
                      </Link>
                    ))}
                  </div>
                )}
              </Card>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

function Avatar({ doctor }: { doctor: Provider }) {
  if (doctor.photo_url) {
    return (
      <img
        src={doctor.photo_url}
        alt=""
        className="h-20 w-20 shrink-0 rounded-full border border-line object-cover"
      />
    )
  }
  return (
    <span
      aria-hidden="true"
      className="grid h-20 w-20 shrink-0 place-items-center rounded-full border border-primary-border bg-primary-subtle text-h1 font-semibold text-primary"
    >
      {doctor.initials}
    </span>
  )
}
