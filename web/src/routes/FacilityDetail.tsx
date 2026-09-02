import { Suspense, lazy } from "react"
import { Link, useParams } from "react-router-dom"
import { IconHospital } from "../ui/icons"
import { useQueries, useQuery } from "@tanstack/react-query"
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
  Skeleton,
  Tab,
  TabList,
  TabPanel,
  Tabs,
} from "../ui"
import type {
  Facility as NearbyFacility,
  FacilityDetail as Detail,
  ServiceCoverage,
} from "../api/types"

// Same treatment as FindCare: maplibre is 250 KB gzipped and must never sit in
// the entry bundle for a patient who only wanted opening hours.
const FacilityMap = lazy(() => import("../components/FacilityMap"))

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
    <div className="ml-page py-5 pb-24 md:pb-10">
      <Header facility={data} />

      <div className="mt-6">
        <Tabs defaultValue="overview">
          <TabList>
            <Tab value="overview">{t("tab_overview")}</Tab>
            <Tab value="services">{t("tab_services")}</Tab>
            <Tab value="doctors">{t("tab_doctors")}</Tab>
            <Tab value="insurance">{t("tab_insurance")}</Tab>
            <Tab value="appointments">{t("tab_appointments")}</Tab>
            <Tab value="queue">{t("tab_queue")}</Tab>
            <Tab value="hours">{t("opening_hours")}</Tab>
          </TabList>

          {/* -------------------------------------------------- overview */}
          <TabPanel value="overview">
            <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]">
              <section>
                <h2 className="text-h3">{t("availability_title")}</h2>
                {/* Per-service status is the answer to "how busy is the thing
                    I need", which is what a patient actually asks. */}
                <ul className="mt-3 divide-y divide-n200 rounded-lg border border-n200 bg-white">
                  {data.services.slice(0, 6).map((service) => (
                    // Stacks on a narrow screen. Side by side, the service
                    // name was the half that gave way - and it is the half
                    // that identifies the row, so "Kwivuza rusange" became
                    // "Kwivuza rusa..." next to an intact wait chip. The
                    // Kinyarwanda names are the longest of the three
                    // languages, so the default language was worst hit.
                    <li
                      key={service.code}
                      className="flex flex-col gap-1.5 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:gap-3"
                    >
                      <span className="min-w-0 text-body-lg sm:truncate">
                        {label(service)}
                      </span>
                      {/* The unknown state is suppressed per row and stated
                          once below instead. Six services with no live queue
                          data produced six identical "Wait time not
                          available" chips stacked down the page, which reads
                          as six broken widgets rather than one honest gap. */}
                      <WaitLine wait={service.wait} className="shrink-0" omitUnknown />
                    </li>
                  ))}
                </ul>
                {!data.services.slice(0, 6).some((s) => s.wait.status === "available") && (
                  <p className="mt-2 text-body text-n700">
                    {t("wait_unavailable_explained")}
                  </p>
                )}
              </section>

              {/* Location is not a row in a table. A patient deciding whether
                  to travel needs to see where this is, and the map is the
                  fastest way to answer that - so the address, the phone and
                  the map are one block, with directions as its action. */}
              <section>
                <h2 className="text-h3">{t("location_title")}</h2>
                <div className="mt-3 overflow-hidden rounded-lg border border-n200 bg-white">
                  <div className="h-52 border-b border-n200">
                    <Suspense
                      fallback={<Skeleton className="h-full w-full rounded-none" />}
                    >
                      <FacilityMap
                        facilities={[data as unknown as NearbyFacility]}
                        center={data.location}
                        selectedSlug={data.slug}
                        onSelect={() => {}}
                      />
                    </Suspense>
                  </div>
                  <div className="space-y-1 p-4">
                    <p className="text-body-lg">
                      {placeLabel(data.sector, data.district)}
                    </p>
                    {data.address && (
                      <p className="text-body text-n700">{data.address}</p>
                    )}
                    {data.phone && (
                      <p className="text-body">
                        <a href={`tel:${data.phone}`} className="text-primary underline">
                          {data.phone}
                        </a>
                      </p>
                    )}
                    <p className="pt-1 text-label text-n600">
                      {data.verified_at
                        ? t("verified_on", {
                            date: new Date(data.verified_at).toLocaleDateString(),
                          })
                        : t("not_yet_verified")}
                    </p>
                  </div>
                </div>
              </section>
            </div>
          </TabPanel>

          {/* -------------------------------------------------- services */}
          <TabPanel value="services">
            {data.services.length === 0 ? (
              <EmptyState icon={<IconHospital size={20} />} title={t("no_services_listed")} />
            ) : (
              <ul className="divide-y divide-n200 rounded-lg border border-n200 bg-white">
                {data.services.map((service) => (
                  <li key={service.code} className="px-4 py-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-body-lg font-medium">{label(service)}</span>
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
                          <span className="text-body-lg font-medium text-n900">
                            {option.name}
                          </span>
                          {option.note && (
                            <span className="mt-0.5 block text-body text-n700">
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
          {/* ---------------------------------------------- appointments */}
          <TabPanel value="appointments">
            {data.bookable ? (
              <AppointmentsPanel facility={data} label={label} />
            ) : (
              <Notice tone="info">{t("appointments_none_bookable")}</Notice>
            )}
          </TabPanel>

          {/* ----------------------------------------------------- queue */}
          <TabPanel value="queue">
            <QueuePanel facility={data} label={label} />
          </TabPanel>

          <TabPanel value="hours">
            <dl className="divide-y divide-n200 rounded-lg border border-n200 bg-white">
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
      <Link to="/search" className="text-body font-medium text-primary">
        {t("back")}
      </Link>

      <div className="mt-2 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-h1">{facility.name}</h1>
          <p className="mt-1 text-body-lg text-n700">
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
      <dd className="min-w-0 text-right text-body-lg">{children}</dd>
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


/**
 * When can I be seen here?
 *
 * One query per bookable service, run in parallel. A facility offers a
 * handful, and the alternative - making a patient pick a service before
 * seeing whether ANY of them has a free slot - is the question backwards.
 */
function AppointmentsPanel({
  facility,
  label,
}: {
  facility: Detail
  label: (s: { name_rw: string; name_en: string; name_fr: string }) => string
}) {
  const { t } = useI18n()
  const services = facility.services ?? []

  const queries = useQueries({
    queries: services.map((service) => ({
      queryKey: ["slots", facility.slug, service.code],
      queryFn: () => api.slots(facility.slug, { service: service.code }),
      staleTime: 60_000,
    })),
  })

  return (
    <ul className="divide-y divide-n200 rounded-lg border border-n200 bg-white">
      {services.map((service, index) => {
        const query = queries[index]
        const firstDay = query.data?.days?.find((day) =>
          day.slots.some((slot) => slot.remaining > 0),
        )
        const firstSlot = firstDay?.slots.find((slot) => slot.remaining > 0)

        return (
          <li
            key={service.code}
            className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
          >
            <span className="min-w-0 text-body-lg">{label(service)}</span>
            <span className="flex items-center gap-3">
              {query.isLoading && <Skeleton className="h-4 w-32" />}
              {!query.isLoading && !firstSlot && (
                <span className="text-body text-n700">
                  {t("appointments_no_slots")}
                </span>
              )}
              {firstSlot && (
                <>
                  <span className="text-body tabular-nums text-n900">
                    {new Date(firstSlot.start).toLocaleString(undefined, {
                      weekday: "short",
                      day: "numeric",
                      month: "short",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                  <Link
                    to={`/facility/${facility.slug}/book?service=${service.code}`}
                    className="ml-btn-primary ml-btn-sm shrink-0"
                  >
                    {t("book")}
                  </Link>
                </>
              )}
            </span>
          </li>
        )
      })}
    </ul>
  )
}

/**
 * How busy is it, per service, right now.
 *
 * The overview shows the same four states as a one-line chip. This adds the
 * thing the chip has no room for - how many people are actually waiting -
 * and says where the numbers come from, because a wait time nobody can
 * account for is a wait time nobody should trust.
 */
function QueuePanel({
  facility,
  label,
}: {
  facility: Detail
  label: (s: { name_rw: string; name_en: string; name_fr: string }) => string
}) {
  const { t } = useI18n()
  const services = facility.services ?? []
  const reporting = services.some((s) => s.wait.status !== "not_reported")

  return (
    <div>
      {!reporting && (
        <div className="mb-4">
          <Notice tone="info">{t("queue_not_reporting")}</Notice>
        </div>
      )}

      <ul className="divide-y divide-n200 rounded-lg border border-n200 bg-white">
        {services.map((service) => (
          <li
            key={service.code}
            className="flex flex-col gap-1.5 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:gap-3"
          >
            <span className="min-w-0 text-body-lg">{label(service)}</span>
            <span className="flex items-center gap-3">
              {/* People waiting is a plain count and always honest, even
                  where the minutes are not - so it is shown whenever we have
                  it, including under `insufficient_data`. */}
              {service.wait.people_waiting !== null &&
                service.wait.people_waiting !== undefined && (
                  <span className="text-body tabular-nums text-n700">
                    {service.wait.people_waiting > 0
                      ? t("queue_people_waiting", {
                          n: service.wait.people_waiting,
                        })
                      : t("queue_none_waiting")}
                  </span>
                )}
              <WaitLine wait={service.wait} className="shrink-0" />
            </span>
          </li>
        ))}
      </ul>

      <p className="mt-3 max-w-prose text-body text-n700">
        {t("queue_explainer")}
      </p>
    </div>
  )
}
