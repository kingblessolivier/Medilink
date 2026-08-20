import { useSearchParams } from "react-router-dom"
import { useQueries } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import { api } from "../api/client"
import { useI18n } from "../i18n"
import { useInsurerPreference } from "../hooks/useInsurerPreference"
import { useInsurers } from "../hooks/useNearbyFacilities"
import { Button, Chip, EmptyState, Skeleton } from "../ui"
import { WaitLine } from "../components/WaitLine"
import type { FacilityDetail } from "../api/types"

/**
 * Compare a handful of facilities.
 *
 * Capped at three, and kept to the six rows that actually decide where
 * somebody goes. The brief is explicit that this must not become a
 * spreadsheet, and a comparison a patient cannot read at a glance has failed
 * at the one job it has.
 *
 * Selection lives in the URL (`?f=slug&f=slug`) so a comparison can be sent to
 * whoever is helping the patient decide.
 */

const MAX = 3

export function Compare() {
  const { t, lang } = useI18n()
  const [params, setParams] = useSearchParams()
  const { insurer } = useInsurerPreference()
  const { data: insurerData } = useInsurers()

  const slugs = params.getAll("f").slice(0, MAX)
  const insurerName = insurerData?.results.find((i) => i.code === insurer)?.name

  const queries = useQueries({
    queries: slugs.map((slug) => ({
      queryKey: ["facility", slug],
      queryFn: () => api.facility(slug),
      staleTime: 60_000,
    })),
  })

  function remove(slug: string) {
    const next = new URLSearchParams()
    for (const value of slugs.filter((s) => s !== slug)) next.append("f", value)
    setParams(next, { replace: true })
  }

  if (slugs.length === 0) {
    return (
      <div className="ml-page py-6">
        <h1 className="mb-4 text-h1">{t("compare")}</h1>
        <EmptyState
          title={t("compare_empty")}
          body={t("compare_empty_body")}
          action={
            <Link to="/search" className="ml-btn-primary ml-btn-sm">
              {t("find_care")}
            </Link>
          }
        />
      </div>
    )
  }

  const loading = queries.some((q) => q.isLoading)
  const facilities = queries
    .map((q) => q.data)
    .filter((f): f is FacilityDetail => Boolean(f))

  const label = (s: { name_rw: string; name_en: string; name_fr: string }) =>
    lang === "rw" ? s.name_rw : lang === "fr" ? s.name_fr : s.name_en

  return (
    <div className="ml-page py-6">
      <h1 className="mb-4 text-h1">{t("compare")}</h1>

      {loading && <Skeleton className="h-64 w-full rounded-xl" />}

      {!loading && (
        <div className="overflow-x-auto">
          <table className="ml-table min-w-[40rem]">
            <thead>
              <tr>
                <th scope="col" className="w-40">
                  {t("compare_field")}
                </th>
                {facilities.map((facility) => (
                  <th key={facility.slug} scope="col">
                    <span className="block text-body font-semibold normal-case tracking-normal text-ink">
                      {facility.name}
                    </span>
                    <button
                      onClick={() => remove(facility.slug)}
                      className="mt-1 text-caption font-medium normal-case text-primary underline"
                    >
                      {t("remove")}
                    </button>
                  </th>
                ))}
              </tr>
            </thead>

            <tbody>
              <Row label={t("compare_status")}>
                {facilities.map((f) => (
                  <td key={f.slug}>
                    <Chip tone={f.is_open ? "success" : "neutral"}>
                      {f.is_open ? t("open") : t("closed")}
                    </Chip>
                  </td>
                ))}
              </Row>

              <Row label={t("compare_wait")}>
                {facilities.map((f) => (
                  <td key={f.slug}>
                    <WaitLine wait={f.wait} />
                  </td>
                ))}
              </Row>

              <Row label={t("filter_insurer")}>
                {facilities.map((f) => {
                  const accepts = f.insurers.some((i) => i.code === insurer)
                  return (
                    <td key={f.slug}>
                      {insurer ? (
                        <Chip tone={accepts ? "success" : "unknown"}>
                          {accepts
                            ? t("accepts", { insurer: insurerName ?? insurer })
                            : t("does_not_accept", {
                                insurer: insurerName ?? insurer,
                              })}
                        </Chip>
                      ) : (
                        <span className="text-small text-ink-muted">
                          {f.insurers.map((i) => i.name).join(", ") || "-"}
                        </span>
                      )}
                    </td>
                  )
                })}
              </Row>

              <Row label={t("services_offered")}>
                {facilities.map((f) => (
                  <td key={f.slug} className="text-small text-ink-muted">
                    {f.services.slice(0, 4).map(label).join(", ")}
                    {f.services.length > 4 &&
                      ` +${f.services.length - 4}`}
                  </td>
                ))}
              </Row>

              <Row label={t("compare_district")}>
                {facilities.map((f) => (
                  <td key={f.slug} className="text-small text-ink-muted">
                    {f.sector ? `${f.sector}, ` : ""}
                    {f.district}
                  </td>
                ))}
              </Row>

              <Row label="">
                {facilities.map((f) => (
                  <td key={f.slug}>
                    <div className="flex gap-2">
                      <Link
                        to={`/facility/${f.slug}`}
                        className="ml-btn-secondary ml-btn-sm"
                      >
                        {t("view_facility")}
                      </Link>
                      <a
                        href={f.directions_url}
                        target="_blank"
                        rel="noreferrer"
                        className="ml-btn-tertiary ml-btn-sm"
                      >
                        {t("directions")}
                      </a>
                    </div>
                  </td>
                ))}
              </Row>
            </tbody>
          </table>
        </div>
      )}

      {slugs.length < MAX && (
        <p className="mt-4 text-small text-ink-muted">
          {t("compare_add_more", { n: MAX - slugs.length })}{" "}
          <Link to="/search" className="font-medium text-primary underline">
            {t("find_care")}
          </Link>
        </p>
      )}

      <div className="mt-4">
        <Button
          variant="tertiary"
          size="sm"
          onClick={() => setParams(new URLSearchParams(), { replace: true })}
        >
          {t("clear")}
        </Button>
      </div>
    </div>
  )
}

function Row({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <tr>
      <th scope="row" className="text-left align-top">
        <span className="ml-label">{label}</span>
      </th>
      {children}
    </tr>
  )
}
