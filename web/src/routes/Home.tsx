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
import { Button, Card, EmptyState, ErrorState, ListSkeleton, Notice } from "../ui"

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
    <div className="pb-24">
      <div className="mx-auto w-full max-w-3xl px-4 pt-4">
        {/* The language toggle moved to the top bar when the three apps
            became one - it belongs somewhere every surface has, not on the
            patient home page alone. What stays here is the greeting. */}
        <p className="mb-5 text-h3">
          {patient?.full_name
            ? t("greeting_named", { name: patient.full_name })
            : t("greeting")}
        </p>

        {/* ---- State B: in a queue. Above everything. ---- */}
        {queue.data && (
          <section className="mb-6" aria-label={t("your_queue")}>
            <QueueCard entry={queue.data} />
          </section>
        )}

        {/* ---- State C: an appointment is coming up. ---- */}
        {!queue.data && nextAppointment && (
          <section className="mb-6" aria-label={t("next_appointment")}>
            <AppointmentCard appointment={nextAppointment} />
          </section>
        )}

        {/* ---- Hero. Demoted when something is active, never removed. ---- */}
        {!queue.data && (
          <section className="mb-8">
            <h1 className="text-h1">{t("hero_title")}</h1>
            <p className="mt-1.5 max-w-prose text-body-lg text-ink-muted">
              {t("hero_body")}
            </p>

            <div className="mt-4">
              <GlobalSearch coords={coords} />
            </div>

            <div className="mt-3 flex flex-wrap gap-2">
              <Link to="/search" className="ml-btn-primary">
                {t("find_care")}
              </Link>
              {/* Hidden entirely when no clinician has signed off a protocol.
                  A button that errors is worse than no button. */}
              {triage.available && (
                <Link to="/care-guide" className="ml-btn-secondary">
                  {t("start_care_guide")}
                </Link>
              )}
            </div>

            <div className="mt-4">
              <InsurerChip insurer={insurer} onChange={setInsurer} />
            </div>
          </section>
        )}

        {geoFailed && (
          <div className="mb-6">
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

          <div className="space-y-3">
            {nearby.data?.results.slice(0, 3).map((facility) => (
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
            <div className="grid gap-3 sm:grid-cols-2">
              {doctors.data?.results.map((doctor) => (
                <DoctorCard key={doctor.slug} doctor={doctor} />
              ))}
            </div>
          </Section>
        )}

        {/* ---- Services. A list of links, not a wall of cards. ---- */}
        <Section title={t("popular_services")}>
          <div className="flex flex-wrap gap-2">
            {(serviceData?.results ?? []).slice(0, 8).map((service) => (
              <Link
                key={service.code}
                to={`/search?service=${service.code}`}
                className="ml-btn-secondary ml-btn-sm"
              >
                {serviceLabel(service)}
              </Link>
            ))}
          </div>
        </Section>

        {/* ---- Insurance ---- */}
        <Section title={t("insurance_title")}>
          <p className="mb-3 max-w-prose text-body text-ink-muted">
            {t("insurance_body")}
          </p>
          <div className="flex flex-wrap gap-2">
            {(insurerData?.results ?? []).slice(0, 6).map((option) => (
              <Link
                key={option.code}
                to={`/search?insurer=${option.code}`}
                className="ml-btn-secondary ml-btn-sm"
              >
                {option.name}
              </Link>
            ))}
          </div>
        </Section>

        {/* ---- Care Guide. Present only when a clinician has signed off. ---- */}
        {triage.available && (
          <Section title={t("care_guide_title")}>
            <Card className="p-5">
              <p className="max-w-prose text-body text-ink-muted">
                {t("care_guide_body")}
              </p>
              <Link to="/care-guide" className="ml-btn-primary mt-4">
                {t("start_care_guide")}
              </Link>
              <p className="mt-3 text-caption text-ink-subtle">
                {t("care_guide_disclaimer")}
              </p>
            </Card>
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
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <h2 className="ml-label">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  )
}
