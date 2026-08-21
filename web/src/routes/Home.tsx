import { useEffect } from "react"
import { Link, useNavigate } from "react-router-dom"
import { useI18n } from "../i18n"
import { useGeolocation } from "../hooks/useGeolocation"
import {
  useInsurers,
  useNearbyFacilities,
  useServiceTypes,
} from "../hooks/useNearbyFacilities"
import { useInsurerPreference } from "../hooks/useInsurerPreference"
import { useCurrentQueueEntry, useUpcomingAppointments } from "../hooks/useQueue"
import { usePatient } from "../hooks/useAuth"
import { useProviders } from "../hooks/useProviders"
import { useTriageStatus } from "../hooks/useTriageStatus"
import { FacilityCard } from "../components/FacilityCard"
import { DoctorCard } from "../components/DoctorCard"
import { GlobalSearch } from "../components/GlobalSearch"
import { InsurerChip } from "../components/InsurerChip"
import { DistrictPicker } from "../components/DistrictPicker"
import { QueueCard } from "../components/QueueCard"
import { AppointmentCard } from "../components/AppointmentCard"
import { Button, EmptyState, ErrorState, ListSkeleton, Notice } from "../ui"
import {
  IconChevronRight,
  IconClock,
  IconHeart,
  IconPin,
  IconSearch,
  IconShieldCheck,
  IconStethoscope,
} from "../ui/icons"

/**
 * What MediLink is, in three lines.
 *
 * No numbers. We have no honest adoption figures to quote yet, and inventing
 * them on a health service is exactly what docs/11 rule 1 forbids.
 */
const VALUE_POINTS = [
  { Glyph: IconPin, title: "value_nearby", body: "value_nearby_body" },
  { Glyph: IconClock, title: "value_wait", body: "value_wait_body" },
  { Glyph: IconShieldCheck, title: "value_insurance", body: "value_insurance_body" },
] as const

/**
 * Home - healthcare discovery, and the state ordering IS the product.
 *
 *   B  in a queue         -> the live card takes the screen; nothing competes
 *   C  appointment today  -> the appointment leads
 *   A  nothing active     -> discovery leads
 *
 * A patient already waiting must not scroll past a search box to find out
 * where they are in the queue.
 */
export function Home() {
  const { t, lang } = useI18n()
  const navigate = useNavigate()
  const { state: geo, locate } = useGeolocation()
  const { insurer, setInsurer } = useInsurerPreference()
  const patient = usePatient()

  const signedIn = patient !== null
  const queue = useCurrentQueueEntry(signedIn)
  const appointments = useUpcomingAppointments(signedIn)
  const nextAppointment = appointments.data?.[0] ?? null

  useEffect(() => {
    locate()
  }, [locate])

  const coords = geo.status === "ready" ? { lat: geo.lat, lng: geo.lng } : null
  const nearby = useNearbyFacilities(coords, { insurer })
  const doctors = useProviders({ limit: 4 })
  const { data: serviceData } = useServiceTypes()
  const { data: insurerData } = useInsurers()
  const triage = useTriageStatus()

  const insurerName = insurerData?.results.find((i) => i.code === insurer)?.name
  const busy = geo.status === "locating" || nearby.isLoading
  const geoFailed =
    geo.status === "denied" ||
    geo.status === "unavailable" ||
    geo.status === "out_of_bounds"

  const serviceLabel = (s: { name_rw: string; name_en: string; name_fr: string }) =>
    lang === "rw" ? s.name_rw : lang === "fr" ? s.name_fr : s.name_en

  return (
    <div className="pb-24 md:pb-10">
      {/* ---- States B and C sit ABOVE the hero and outside it.
             A patient already in a queue must not scroll past a search box
             to find out what number they are. ---- */}
      {(queue.data || nextAppointment) && (
        <div className="ml-shell pt-4">
          {queue.data ? (
            <section aria-label={t("your_queue")}>
              <QueueCard entry={queue.data} />
            </section>
          ) : (
            <section aria-label={t("next_appointment")}>
              <AppointmentCard appointment={nextAppointment!} />
            </section>
          )}
        </div>
      )}

      {/* ---- Hero. Demoted to a strip when something is active, never
             removed: discovery is still the product. ---- */}
      {!queue.data && (
        <section
          className={
            "relative overflow-hidden bg-hero-wash text-white " +
            (nextAppointment ? "mt-4" : "")
          }
        >
          {/* A faint grid rather than a photograph. Stock imagery of smiling
              clinicians is the visual language of marketing, and this is a
              tool people open when they are unwell. */}
          <span
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 bg-hero-grid bg-grid opacity-60"
          />
          <span
            aria-hidden="true"
            className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-white/5"
          />

          <div className="ml-shell relative grid gap-10 py-10 sm:py-14 lg:grid-cols-[minmax(0,1fr)_22rem] lg:items-center lg:gap-16 lg:py-20">
            <div className="max-w-2xl">
              <p className="text-small font-medium text-white/70">
                {patient?.full_name
                  ? t("greeting_named", { name: patient.full_name })
                  : t("greeting")}
              </p>
              <h1 className="mt-2 text-h1 sm:text-display">{t("hero_title")}</h1>
              <p className="mt-3 max-w-prose text-body-lg text-white/80">
                {t("hero_body")}
              </p>

              <div className="mt-6 [--tw-ring-color:transparent]">
                <GlobalSearch coords={coords} />
              </div>

              <div className="mt-4 flex flex-wrap gap-2">
                <Link
                  to="/search"
                  className="ml-btn inline-flex bg-white text-primary hover:bg-white/90"
                >
                  <IconSearch size={17} />
                  {t("find_care")}
                </Link>
                {/* Hidden entirely when no clinician has signed off a
                    protocol. A button that errors is worse than no button. */}
                {triage.available && (
                  <Link
                    to="/care-guide"
                    className="ml-btn inline-flex border border-white/30 text-white hover:bg-white/10"
                  >
                    <IconHeart size={17} />
                    {t("start_care_guide")}
                  </Link>
                )}
              </div>
            </div>

            {/* Three plain facts about what this is. They sit in the hero's
                right-hand column on a wide screen - which is what stops a
                1440px viewport being half empty green - and fall back to a
                strip underneath the copy on anything narrower. */}
            <ul className="grid gap-5 border-t border-white/15 pt-6 sm:grid-cols-3 lg:grid-cols-1 lg:border-l lg:border-t-0 lg:pl-8 lg:pt-0">
              {VALUE_POINTS.map(({ Glyph, title, body }) => (
                <li key={title} className="flex gap-3">
                  <span className="ml-icon-plate bg-white/10 text-white">
                    <Glyph size={18} />
                  </span>
                  <span>
                    <span className="block text-body font-medium">{t(title)}</span>
                    <span className="mt-0.5 block text-small text-white/70">
                      {t(body)}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </section>
      )}

      <div className="ml-shell pt-8">
        <div className="mb-6">
          <InsurerChip insurer={insurer} onChange={setInsurer} />
        </div>

        {geoFailed && (
          <div className="mb-6 max-w-2xl">
            {/* Home is a summary. Picking a district hands off to /search,
                where the filters and the full list already live, rather than
                growing a second half-featured results list here. */}
            <DistrictPicker
              message={
                geo.status === "out_of_bounds"
                  ? t("out_of_bounds")
                  : t("location_denied")
              }
              onPick={(district) =>
                navigate(`/search?district=${encodeURIComponent(district)}`)
              }
              onRetry={locate}
            />
          </div>
        )}

        {/* ---- Nearby ---- */}
        <Section
          title={t("nearby_open")}
          action={
            nearby.data && nearby.data.count > 3 ? (
              <Link to="/search" className="text-small font-medium text-primary">
                {t("see_all")}
              </Link>
            ) : null
          }
        >
          {busy && <ListSkeleton rows={3} />}

          {nearby.isError && (
            <ErrorState
              title={t("error_generic")}
              action={
                <Button size="sm" onClick={() => nearby.refetch()}>
                  {t("retry")}
                </Button>
              }
            />
          )}

          {nearby.data?.query.radius_expanded && (
            <div className="mb-3">
              <Notice tone="warning">
                {t("radius_expanded", {
                  original: 5,
                  actual: Math.round(nearby.data.query.radius / 1000),
                })}
              </Notice>
            </div>
          )}

          {nearby.data?.results.length === 0 && (
            <EmptyState
              title={t("no_results")}
              body={t("no_results_body")}
              action={
                <Link to="/search" className="ml-btn-secondary ml-btn-sm">
                  {t("change_filters")}
                </Link>
              }
            />
          )}

          {/* A grid, not a stack. Three full-width cards on a 1440px monitor
              was a column of 1100px-wide boxes with one line of text in each. */}
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {nearby.data?.results.slice(0, 6).map((facility) => (
              <FacilityCard
                key={facility.id}
                facility={facility}
                insurerName={insurerName}
              />
            ))}
          </div>
        </Section>

        {/* ---- Doctors. Omitted entirely when none are listed, rather than
               showing an empty shelf. ---- */}
        {(doctors.data?.count ?? 0) > 0 && (
          <Section
            title={t("doctors_near_you")}
            action={
              <Link to="/doctors" className="text-small font-medium text-primary">
                {t("see_all")}
              </Link>
            }
          >
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {doctors.data?.results.map((doctor) => (
                <DoctorCard key={doctor.slug} doctor={doctor} />
              ))}
            </div>
          </Section>
        )}

        {/* ---- Services. A list of links, not a wall of cards. ---- */}
        {/* Services were eight identical grey pills - indistinguishable, and
            impossible to scan for the one you came for. Now a tile each, with
            the same icon plate the rest of the product uses as an anchor. */}
        <Section title={t("popular_services")}>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {(serviceData?.results ?? []).slice(0, 8).map((service) => (
              <Link
                key={service.code}
                to={`/search?service=${service.code}`}
                className="ml-card-interactive group flex items-center gap-3 p-3.5"
              >
                <span className="ml-icon-plate bg-primary-subtle text-primary">
                  <IconStethoscope size={18} />
                </span>
                <span className="min-w-0 flex-1 truncate text-body font-medium">
                  {serviceLabel(service)}
                </span>
                <IconChevronRight
                  size={16}
                  className="shrink-0 text-ink-subtle transition-transform group-hover:translate-x-0.5"
                />
              </Link>
            ))}
          </div>
        </Section>

        {/* ---- Insurance ---- */}
        <Section title={t("insurance_title")}>
          <div className="ml-panel overflow-hidden">
            <div className="flex flex-col gap-6 p-5 sm:flex-row sm:items-start sm:p-6">
              <span className="ml-icon-plate h-11 w-11 bg-primary-subtle text-primary">
                <IconShieldCheck size={22} />
              </span>
              <div className="min-w-0 flex-1">
                <p className="max-w-prose text-body text-ink-muted">
                  {t("insurance_body")}
                </p>
                <div className="mt-4 flex flex-wrap gap-2">
                  {(insurerData?.results ?? []).slice(0, 8).map((option) => (
                    <Link
                      key={option.code}
                      to={`/search?insurer=${option.code}`}
                      className="ml-btn-secondary ml-btn-sm"
                    >
                      {option.name}
                    </Link>
                  ))}
                </div>
                {/* Rule 6, on the screen rather than only in the docs: we say
                    what a facility ACCEPTS, never that a patient is covered. */}
                <p className="mt-4 text-caption text-ink-subtle">
                  {t("insurance_accepts_note")}
                </p>
              </div>
            </div>
          </div>
        </Section>

        {/* ---- Care Guide. Present only when a clinician has signed off. ---- */}
        {triage.available && (
          <Section title={t("care_guide_title")}>
            <div className="ml-panel flex flex-col gap-6 p-5 sm:flex-row sm:items-start sm:p-6">
              <span className="ml-icon-plate h-11 w-11 bg-primary-subtle text-primary">
                <IconHeart size={22} />
              </span>
              <div className="min-w-0 flex-1">
                <p className="max-w-prose text-body text-ink-muted">
                  {t("care_guide_body")}
                </p>
                <Link to="/care-guide" className="ml-btn-primary mt-4">
                  {t("start_care_guide")}
                </Link>
                <p className="mt-3 text-caption text-ink-subtle">
                  {t("care_guide_disclaimer")}
                </p>
              </div>
            </div>
          </Section>
        )}
      </div>
    </div>
  )
}

/** A titled section. A divider and whitespace, not another card. */
function Section({
  title,
  action,
  children,
}: {
  title: string
  action?: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <section className="ml-section">
      {/* Was a 12px grey uppercase label that read as a form field caption.
          A section heading on a page this wide has to hold its own column. */}
      <div className="ml-section-head">
        <h2 className="text-h2">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  )
}
