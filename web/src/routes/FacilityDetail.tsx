import { Link, useParams } from "react-router-dom"
import { IconHospital } from "../ui/icons"
import { useQuery } from "@tanstack/react-query"
import { api } from "../api/client"
import { useI18n } from "../i18n"
import { useProviders } from "../hooks/useProviders"
import { useInsurerPreference } from "../hooks/useInsurerPreference"
import { DoctorCard } from "../components/DoctorCard"
import { WaitLine } from "../components/WaitLine"
import {
  Chip,
  EmptyState,
  ErrorState,
  ListSkeleton,
  Notice,
  Tab,
  TabList,
  TabPanel,
  Tabs,
} from "../ui"
import type { FacilityDetail as Detail, ServiceCoverage } from "../api/types"

const WEEKDAYS = [0, 1, 2, 3, 4, 5, 6]

/**
 * The facility profile.
 *
 * Tabbed rather than one long page: a referral hospital has a dozen services,
 * as many doctors and six insurers, and showing all of it at once buries the
 * two things a patient came for - is it open, and can I be seen.
 */
export function FacilityDetail() {
  const { slug = "" } = useParams()
  const { t, lang } = useI18n()
  const { insurer } = useInsurerPreference()

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["facility", slug],
    queryFn: () => api.facility(slug),
    staleTime: 60_000,
  })

  const doctors = useProviders({ facility: slug, limit: 12 }, Boolean(slug))

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

  const label = (s: { name_rw: string; name_en: string; name_fr: string }) =>
    lang === "rw" ? s.name_rw : lang === "fr" ? s.name_fr : s.name_en

  return (
    <div className="ml-page py-5 pb-24">
      <Header facility={data} />

      <div className="mt-6">
        <Tabs defaultValue="overview">
          <TabList>
            <Tab value="overview">{t("tab_overview")}</Tab>
            <Tab value="services">{t("tab_services")}</Tab>
            <Tab value="doctors">{t("tab_doctors")}</Tab>
            <Tab value="insurance">{t("tab_insurance")}</Tab>
            <Tab value="hours">{t("opening_hours")}</Tab>
          </TabList>

          {/* -------------------------------------------------- overview */}
          <TabPanel value="overview">
            <div className="grid gap-6 lg:grid-cols-2">
              <section>
                <h2 className="text-h3 mb-2">{t("current_status")}</h2>
                {/* Per-service status is the answer to "how busy is the thing
                    I need", which is what a patient actually asks. */}
                <ul className="divide-y divide-line rounded-xl border border-line bg-surface">
                  {data.services.slice(0, 6).map((service) => (
                    <li
                      key={service.code}
                      className="flex items-center justify-between gap-3 px-4 py-3"
                    >
                      <span className="min-w-0 truncate text-body">
                        {label(service)}
                      </span>
                      <WaitLine wait={service.wait} />
                    </li>
                  ))}
                </ul>
              </section>

              <section>
                <h2 className="text-h3 mb-2">{t("facility_information")}</h2>
                <dl className="divide-y divide-line rounded-xl border border-line bg-surface">
                  <Row label={t("compare_district")}>
                    {placeLabel(data.sector, data.district)}
                  </Row>
                  {data.address && <Row label={t("address")}>{data.address}</Row>}
                  {data.phone && (
                    <Row label={t("phone")}>
                      <a href={`tel:${data.phone}`} className="text-primary underline">
                        {data.phone}
                      </a>
                    </Row>
                  )}
                  <Row label={t("verified")}>
                    {data.verified_at
                      ? new Date(data.verified_at).toLocaleDateString()
                      : t("not_yet_verified")}
                  </Row>
                </dl>
              </section>
            </div>
          </TabPanel>

          {/* -------------------------------------------------- services */}
          <TabPanel value="services">
            {data.services.length === 0 ? (
              <EmptyState icon={<IconHospital size={20} />} title={t("no_services_listed")} />
            ) : (
              <ul className="divide-y divide-line rounded-xl border border-line bg-surface">
                {data.services.map((service) => (
                  <li key={service.code} className="px-4 py-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-body font-medium">{label(service)}</span>
                      <WaitLine wait={service.wait} />
                    </div>
                    {insurer && (
                      <div className="mt-2">
                        <CoverageChip
                          coverage={service.coverage}
                          insurer={insurer}
                        />
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </TabPanel>

          {/* --------------------------------------------------- doctors */}
          <TabPanel value="doctors">
            {doctors.isLoading && <ListSkeleton rows={3} />}
            {doctors.data?.count === 0 && (
              <EmptyState icon={<IconHospital size={20} />}
                title={t("no_doctors_listed")}
                body={t("no_doctors_listed_body")}
              />
            )}
            <div className="grid gap-3 sm:grid-cols-2">
              {doctors.data?.results.map((doctor) => (
                <DoctorCard key={doctor.slug} doctor={doctor} />
              ))}
            </div>
          </TabPanel>

          {/* ------------------------------------------------- insurance */}
          <TabPanel value="insurance">
            <Notice tone="info">{t("insurance_disclaimer")}</Notice>

            {data.insurers.length === 0 ? (
              <div className="mt-3">
                <EmptyState icon={<IconHospital size={20} />} title={t("no_insurers_listed")} />
              </div>
            ) : (
              <div className="mt-3 ml-scroll-x">
                <table className="ml-table min-w-[34rem]">
                  <thead>
                    <tr>
                      <th scope="col">{t("filter_insurer")}</th>
                      <th scope="col">{t("tab_services")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.insurers.map((option) => (
                      <tr key={option.code}>
                        <th scope="row" className="text-left align-top">
                          <span className="text-body font-medium text-ink">
                            {option.name}
                          </span>
                          {option.note && (
                            <span className="mt-0.5 block text-small text-ink-muted">
                              {option.note}
                            </span>
                          )}
                        </th>
                        <td>
                          <div className="flex flex-wrap gap-1.5">
                            {data.services.map((service) => (
                              <ServiceCoverageChip
                                key={service.code}
                                name={label(service)}
                                coverage={service.coverage}
                                insurer={option.code}
                              />
                            ))}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </TabPanel>

          {/* ----------------------------------------------------- hours */}
          <TabPanel value="hours">
            <dl className="divide-y divide-line rounded-xl border border-line bg-surface">
              {WEEKDAYS.map((weekday) => {
                const periods = data.opening_hours
                  .filter((h) => h.weekday === weekday)
                  .map((h) => `${h.opens_at} - ${h.closes_at}`)
                return (
                  <Row key={weekday} label={t(`weekday_${weekday}`)}>
                    {periods.length ? periods.join(", ") : t("closed")}
                  </Row>
                )
              })}
            </dl>
          </TabPanel>
        </Tabs>
      </div>
    </div>
  )
}

function Header({ facility }: { facility: Detail }) {
  const { t } = useI18n()

  return (
    <header>
      <Link to="/search" className="text-small font-medium text-primary">
        {t("back")}
      </Link>

      <div className="mt-2 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-h1">{facility.name}</h1>
          <p className="mt-1 text-body text-ink-muted">
            {placeLabel(facility.sector, facility.district)}
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <Chip tone={facility.is_open ? "success" : "neutral"}>
              {facility.is_open ? t("open") : t("closed")}
            </Chip>
            {facility.verified_at ? (
              <Chip tone="success">{t("verified")}</Chip>
            ) : (
              <Chip tone="unknown">{t("not_yet_verified")}</Chip>
            )}
          </div>
        </div>

        <div className="flex gap-2">
          <a
            className="ml-btn-secondary"
            href={facility.directions_url}
            target="_blank"
            rel="noreferrer"
          >
            {t("directions")}
          </a>
          <Link to={`/facility/${facility.slug}/book`} className="ml-btn-primary">
            {t("book")}
          </Link>
        </div>
      </div>
    </header>
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
    <div className="flex items-baseline justify-between gap-4 px-4 py-3">
      <dt className="ml-label shrink-0">{label}</dt>
      <dd className="min-w-0 text-right text-body">{children}</dd>
    </div>
  )
}

/**
 * Coverage for the patient's own insurer.
 *
 * "Not confirmed" is the default and it is deliberately quiet. We hold
 * facility-declared acceptance, not eligibility - the copy never says
 * "you are covered".
 */
function CoverageChip({
  coverage,
  insurer,
}: {
  coverage: ServiceCoverage[]
  insurer: string
}) {
  const { t } = useI18n()
  const row = coverage.find((c) => c.insurer === insurer)
  const value = row?.coverage ?? "unknown"

  const tone =
    value === "full" ? "success" : value === "partial" ? "warning" : "unknown"
  const key =
    value === "full"
      ? "coverage_full"
      : value === "partial"
        ? "coverage_partial"
        : value === "not_covered"
          ? "coverage_none"
          : "coverage_unknown"

  return (
    <Chip tone={value === "not_covered" ? "danger" : tone}>
      {t(key)}
      {row?.note ? ` · ${row.note}` : ""}
    </Chip>
  )
}

function ServiceCoverageChip({
  name,
  coverage,
  insurer,
}: {
  name: string
  coverage: ServiceCoverage[]
  insurer: string
}) {
  const row = coverage.find((c) => c.insurer === insurer)
  const value = row?.coverage ?? "unknown"

  const tone =
    value === "full"
      ? "success"
      : value === "partial"
        ? "warning"
        : value === "not_covered"
          ? "danger"
          : "unknown"

  // The service name is always the label; coverage only tints it. Status is
  // never colour alone.
  const suffix =
    value === "full" ? "" : value === "partial" ? " (partial)" : value === "not_covered" ? " (no)" : " (?)"

  return <Chip tone={tone}>{name}{suffix}</Chip>
}

/**
 * "Nyarugenge, Nyarugenge" is what you get when a sector and its district
 * share a name, which several do in Kigali. A place named twice reads as a
 * data error even when the data is correct.
 */
function placeLabel(sector: string | undefined, district: string): string {
  if (!sector || sector.trim().toLowerCase() === district.trim().toLowerCase()) {
    return district
  }
  return `${sector}, ${district}`
}
